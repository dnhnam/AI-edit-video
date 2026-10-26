"""Kiểm thử offline (không gọi Claude): python -m pytest tests/"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))

from broll import BrollPlan, Slot, best_file, slots_from_plan  # noqa: E402
from media import Cue, Word, group_phrases, parse_srt, remap_words, words_to_cues, write_srt  # noqa: E402
from plan_cuts import CutPlan, KeepRange, plan_to_segments  # noqa: E402
from render_edl import frame_size  # noqa: E402
from shot_log import pick_times, youtube_chapters  # noqa: E402


def make_words(sentences, gap=1.2):
    words, t = [], 0.5
    for s in sentences:
        for w in s.split():
            words.append(Word(t, t + 0.35, w))
            t += 0.45
        t += gap
    return words


SENTENCES = ["Xin chào các bạn.", "Hôm nay ừm nói về AI.", "Hôm nay nói về AI dựng video.", "Cảm ơn đã xem."]


def test_group_phrases_splits_on_pause_and_punctuation():
    phrases = group_phrases(make_words(SENTENCES))
    assert [p.text for p in phrases] == SENTENCES
    assert [p.id for p in phrases] == [1, 2, 3, 4]


def test_plan_to_segments_validates_merges_and_pads():
    phrases = group_phrases(make_words(SENTENCES))
    plan = CutPlan(title="t", summary="s", warnings=[], keep=[
        KeepRange(first_id=1, last_id=1, reason="a"),
        KeepRange(first_id=3, last_id=3, reason="b"),
        KeepRange(first_id=4, last_id=4, reason="c"),   # liền với 3 -> gộp
        KeepRange(first_id=9, last_id=9, reason="sai"),  # không tồn tại -> bỏ
    ])
    segs, warns = plan_to_segments(plan.keep, phrases, duration=30.0)
    assert len(segs) == 2 and segs[1]["phrases"] == [3, 4]
    assert any("P0009" in w for w in warns)
    # Padding không lấn quá nửa khoảng lặng sang cụm bị bỏ (P0002).
    p2, p3 = phrases[1], phrases[2]
    assert segs[1]["start"] >= (p2.end + p3.start) / 2 - 1e-6
    assert segs[0]["start"] < phrases[0].start


def test_remap_words_and_cues_follow_new_timeline():
    words = make_words(SENTENCES)
    phrases = group_phrases(words)
    segments = [{"start": phrases[3].start, "end": phrases[3].end}, {"start": phrases[0].start, "end": phrases[0].end}]
    remapped = remap_words(words, segments)
    assert [w.text for w in remapped][:4] == ["Cảm", "ơn", "đã", "xem."]
    assert remapped[0].start == pytest.approx(0.0)
    cues = words_to_cues(remapped)
    assert [c.text for c in cues] == ["Cảm ơn đã xem.", "Xin chào các bạn."]
    assert parse_srt(write_srt(cues))[1].text == "Xin chào các bạn."


def test_shot_log_helpers():
    assert pick_times(20, 5, None, 100) == [0, 5, 10, 15]
    assert len(pick_times(1000, 1, None, 50)) == 50
    assert youtube_chapters([(5, "A"), (12, "B"), (14, "C"), (40, "D")]) == [(0.0, "A"), (12, "B"), (40, "D")]


def test_frame_size():
    assert frame_size(1920, 1080, "source", False) == (1920, 1080)
    assert frame_size(1920, 1080, "source", True) == (960, 540)
    assert frame_size(1920, 1080, "9:16", False) == (1080, 1920)
    assert frame_size(1920, 1080, "9:16", True) == (540, 960)


def test_broll_slots_skip_early_overlapping_and_invalid():
    cues = [Cue(1, 0.5, 2.0, "a"), Cue(2, 3.0, 5.0, "b"), Cue(3, 6.0, 8.0, "c"), Cue(4, 12.0, 14.0, "d")]
    plan = BrollPlan(slots=[Slot(cue_id=i, duration=d, query_en="q", description="x", reason="y")
                            for i, d in [(1, 3), (2, 3), (3, 3), (4, 9), (77, 3)]])
    slots = slots_from_plan(plan, cues, total=15.0)
    # C001 quá sớm, C003 chồng lên ô C002, C077 không tồn tại; ô C004 bị cắt còn tối đa đến hết video.
    assert [(s["start"], s["duration"]) for s in slots] == [(3.0, 3.0), (12.0, 2.5)]


def test_best_file_prefers_mp4_near_1080():
    video = {"video_files": [
        {"file_type": "video/mp4", "width": 360, "height": 640},
        {"file_type": "video/mp4", "width": 2160, "height": 3840},
        {"file_type": "video/mp4", "width": 1080, "height": 1920},
        {"file_type": "video/hls", "width": None, "height": None},
    ]}
    assert best_file(video)["width"] == 1080


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="cần ffmpeg")
def test_render_vertical_with_broll(tmp_path):
    src, clip = tmp_path / "src.mp4", tmp_path / "broll.mp4"
    for path, spec in [(src, "testsrc=size=640x360:rate=25:duration=8"), (clip, "smptebars=size=640x360:rate=25:duration=4")]:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", spec, "-f", "lavfi", "-i",
                        "sine=duration=8", "-shortest", "-c:v", "libx264", str(path)], check=True)
    edl = tmp_path / "edl.json"
    edl.write_text(json.dumps({"source": str(src), "hook": "Hook",
                               "segments": [{"start": 1, "end": 6}],
                               "broll": [{"start": 1.0, "duration": 2.0, "file": "broll.mp4"}]}))
    out = tmp_path / "short.mp4"
    subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "examples" / "render_edl.py"),
                    str(edl), "-o", str(out), "--preview", "--aspect", "9:16", "--hook"], check=True)
    wh = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height",
                         "-of", "csv=p=0", str(out)], capture_output=True, text=True, check=True).stdout.strip()
    assert wh == "540,960"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="cần ffmpeg")
def test_render_edl_end_to_end(tmp_path):
    src = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=10",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=10", "-shortest", "-c:v", "libx264",
                    "-c:a", "aac", str(src)], check=True)
    edl = tmp_path / "edl.json"
    edl.write_text(json.dumps({"source": str(src), "segments": [{"start": 6, "end": 8}, {"start": 1, "end": 3.5}]}))
    out = tmp_path / "out.mp4"
    subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "examples" / "render_edl.py"),
                    str(edl), "-o", str(out), "--preview"], check=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(out)], capture_output=True, text=True, check=True).stdout)
    assert dur == pytest.approx(4.5, abs=0.15)
