"""Kiểm thử offline (không gọi Claude): python -m pytest tests/"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))

from media import Word, group_phrases, parse_srt, remap_words, words_to_cues, write_srt  # noqa: E402
from plan_cuts import CutPlan, KeepRange, plan_to_segments  # noqa: E402
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
    segs, warns = plan_to_segments(plan, phrases, duration=30.0)
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
