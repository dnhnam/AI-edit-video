"""Tiện ích xử lý media dùng chung: ffprobe, transcript, phụ đề SRT.

Không gọi Claude ở đây — mọi thứ trong file này chạy offline và có thể kiểm thử.
"""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# ffmpeg / ffprobe
# ---------------------------------------------------------------------------

def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise SystemExit(f"Không tìm thấy `{tool}`. Cài ffmpeg trước (https://ffmpeg.org/download.html).")


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Chạy lệnh, in lỗi rõ ràng nếu thất bại."""
    proc = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise SystemExit(f"Lệnh thất bại ({proc.returncode}): {' '.join(cmd[:6])} ...\n{tail}")
    return proc


@dataclass
class MediaInfo:
    duration: float
    width: int | None
    height: int | None
    fps: float | None
    has_audio: bool


def probe(path: str | Path) -> MediaInfo:
    proc = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ])
    data = json.loads(proc.stdout)
    video = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    has_audio = any(s.get("codec_type") == "audio" for s in data["streams"])
    fps = None
    if video and video.get("avg_frame_rate", "0/0") != "0/0":
        num, den = video["avg_frame_rate"].split("/")
        fps = float(num) / float(den) if float(den) else None
    return MediaInfo(
        duration=float(data["format"]["duration"]),
        width=video.get("width") if video else None,
        height=video.get("height") if video else None,
        fps=fps,
        has_audio=has_audio,
    )


# ---------------------------------------------------------------------------
# Thời gian
# ---------------------------------------------------------------------------

def fmt_ts(seconds: float, millis: bool = False) -> str:
    """12.5 -> '00:12' (hoặc '00:12.50'); tự thêm giờ khi cần."""
    seconds = max(0.0, seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    sec = f"{s:05.2f}" if millis else f"{int(s):02d}"
    return f"{int(h)}:{int(m):02d}:{sec}" if h >= 1 else f"{int(m):02d}:{sec}"


def srt_time(seconds: float) -> str:
    ms = int(round(max(0.0, seconds) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt_time(text: str) -> float:
    h, m, rest = text.strip().replace(".", ",").split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------
# Định dạng transcript dùng trong repo (transcribe.py sinh ra):
# {"source": "video.mp4", "duration": 123.4, "language": "vi",
#  "words": [{"start": 0.52, "end": 0.80, "text": "Xin"}, ...]}

@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Phrase:
    id: int
    start: float
    end: float
    words: list[Word] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


def load_transcript(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data["words"] = [Word(float(w["start"]), float(w["end"]), str(w["text"]).strip())
                     for w in data["words"] if str(w["text"]).strip()]
    return data


_SENTENCE_END = re.compile(r"[.!?…。]$")


def group_phrases(words: list[Word], max_gap: float = 0.5, max_len: float = 12.0) -> list[Phrase]:
    """Gộp từ thành cụm (phrase) — đơn vị nhỏ nhất mà Claude được phép giữ/bỏ.

    Tách cụm khi: khoảng lặng giữa hai từ > max_gap, câu kết thúc bằng dấu câu,
    hoặc cụm đã dài hơn max_len giây. Ranh giới cụm luôn nằm giữa hai từ, nên
    không bao giờ cắt giữa một từ.
    """
    phrases: list[Phrase] = []
    current: list[Word] = []
    for word in words:
        if current:
            gap = word.start - current[-1].end
            too_long = word.end - current[0].start > max_len
            if gap > max_gap or too_long or _SENTENCE_END.search(current[-1].text):
                phrases.append(Phrase(len(phrases) + 1, current[0].start, current[-1].end, current))
                current = []
        current.append(word)
    if current:
        phrases.append(Phrase(len(phrases) + 1, current[0].start, current[-1].end, current))
    return phrases


def pack_phrases(phrases: list[Phrase]) -> str:
    """Biểu diễn transcript gọn để gửi cho Claude: một dòng mỗi cụm, kèm ID và
    khoảng lặng phía trước (giúp Claude thấy chỗ ngập ngừng)."""
    lines = []
    prev_end = 0.0
    for p in phrases:
        pause = p.start - prev_end
        pause_note = f" (+{pause:.1f}s lặng)" if pause >= 1.0 else ""
        lines.append(f"P{p.id:04d} [{fmt_ts(p.start, True)}–{fmt_ts(p.end, True)}]{pause_note} {p.text}")
        prev_end = p.end
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phụ đề
# ---------------------------------------------------------------------------

@dataclass
class Cue:
    index: int
    start: float
    end: float
    text: str


def parse_srt(text: str) -> list[Cue]:
    cues = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("﻿", "").strip())
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2 or "-->" not in lines[1]:
            continue
        start, end = (parse_srt_time(t) for t in lines[1].split("-->"))
        cues.append(Cue(int(lines[0]), start, end, "\n".join(lines[2:]).strip()))
    return cues


def write_srt(cues: list[Cue]) -> str:
    return "\n".join(
        f"{i}\n{srt_time(c.start)} --> {srt_time(c.end)}\n{c.text}\n"
        for i, c in enumerate(cues, 1)
    )


def remap_words(words: list[Word], segments: list[dict]) -> list[Word]:
    """Đưa thời gian của từ từ timeline gốc sang timeline sau khi cắt.

    segments: [{"start": s, "end": e}, ...] theo thứ tự xuất hiện trong video mới.
    Từ nào có điểm giữa nằm trong một segment thì được giữ lại.
    """
    out: list[Word] = []
    offset = 0.0
    for seg in segments:
        s, e = seg["start"], seg["end"]
        for w in words:
            mid = (w.start + w.end) / 2
            if s <= mid < e:
                out.append(Word(offset + max(w.start, s) - s, offset + min(w.end, e) - s, w.text))
        offset += e - s
    return out


def words_to_cues(words: list[Word], max_chars: int = 42, max_dur: float = 5.0,
                  max_gap: float = 0.6) -> list[Cue]:
    """Chia từ thành các dòng phụ đề dễ đọc."""
    cues: list[Cue] = []
    current: list[Word] = []

    def flush():
        if current:
            cues.append(Cue(len(cues) + 1, current[0].start, current[-1].end,
                            " ".join(w.text for w in current)))
            current.clear()

    for w in words:
        if current:
            if w.start - current[-1].end > max_gap or _SENTENCE_END.search(current[-1].text):
                flush()
            else:
                text_len = len(" ".join(x.text for x in current)) + 1 + len(w.text)
                too_long = text_len > max_chars or w.end - current[0].start > max_dur
                # Không để từ cuối câu rơi lẻ loi sang một dòng riêng.
                ends_sentence = _SENTENCE_END.search(w.text) and text_len <= max_chars + 12
                if too_long and not ends_sentence:
                    flush()
        current.append(w)
    flush()
    # Kéo dài nhẹ mỗi dòng để mắt kịp đọc, nhưng không đè lên dòng sau.
    for a, b in zip(cues, cues[1:]):
        a.end = min(max(a.end, a.start + 1.0), b.start)
    if cues:
        cues[-1].end = max(cues[-1].end, cues[-1].start + 1.0)
    return cues


def chunked(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def ceil_div(a: float, b: float) -> int:
    return int(math.ceil(a / b))
