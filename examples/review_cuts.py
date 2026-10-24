"""Bước 4 — Tự kiểm tra bản render: Claude xem khung trước/sau mỗi điểm cắt.

Phát hiện jump cut khó chịu (cùng khung hình, đầu người "nhảy"), cắt vào khung
đen/chớp sáng, và gợi ý cách che (punch-in, b-roll, crossfade, dời điểm cắt).

    python review_cuts.py out/preview.mp4 work/interview.edl.json -o work/review.json

Lưu ý: chỉ xem hình. Lỗi âm thanh (tiếng bụp, hụt hơi) vẫn cần tai người nghe.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from frames import extract_frame, labeled_frames
from media import fmt_ts, probe, require_ffmpeg

SYSTEM = """Bạn là biên tập viên kiểm tra chất lượng bản dựng. Với mỗi điểm cắt bạn thấy \
hai khung: ngay TRƯỚC và ngay SAU vết cắt. Đánh giá chuyển cảnh có mượt không. Jump cut \
trong video nói chuyện (talking head) là chấp nhận được nếu có chủ ý; chỉ gắn cờ khi \
khung hình gần như giống hệt nhưng tư thế/đầu nhảy rõ rệt, hoặc khi có khung đen/chớp/mờ."""


class CutReview(BaseModel):
    cut: int
    verdict: Literal["ok", "jump_cut", "mismatch", "black_or_flash"]
    explanation: str
    suggestion: Literal["none", "punch_in", "b_roll", "crossfade", "move_cut"]


class Review(BaseModel):
    cuts: list[CutReview]
    overall: str


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", help="Video đã render")
    parser.add_argument("edl", help="EDL đã dùng để render")
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()

    require_ffmpeg()
    segments = json.loads(Path(args.edl).read_text(encoding="utf-8"))["segments"]
    info = probe(args.video)
    cut_times, t = [], 0.0
    for s in segments[:-1]:
        t += s["end"] - s["start"]
        cut_times.append(t)
    if not cut_times:
        raise SystemExit("Chỉ có một đoạn — không có điểm cắt nào để kiểm tra.")

    # Khoảng cách 0.1 s giữa khung trước/sau là đủ nhỏ để thấy độ "nhảy" của vết cắt.
    with tempfile.TemporaryDirectory() as tmp:
        frames = []
        for i, ct in enumerate(cut_times, 1):
            before = extract_frame(args.video, max(ct - 0.1, 0), Path(tmp) / f"c{i}_a.jpg")
            after = extract_frame(args.video, min(ct + 0.05, info.duration - 0.05), Path(tmp) / f"c{i}_b.jpg")
            frames += [(f"Điểm cắt {i} — TRƯỚC", ct - 0.1, before), (f"Điểm cắt {i} — SAU", ct + 0.05, after)]
        content = labeled_frames(frames) + [{"type": "text", "text": f"Đánh giá {len(cut_times)} điểm cắt ở trên."}]

        from claude_helper import ask_structured
        review = ask_structured(SYSTEM, content, Review, effort="medium")

    Path(args.output).write_text(json.dumps(
        {"cuts": [{**c.model_dump(), "time": round(cut_times[c.cut - 1], 2)}
                  for c in review.cuts if 1 <= c.cut <= len(cut_times)],
         "overall": review.overall}, ensure_ascii=False, indent=2), encoding="utf-8")
    for c in review.cuts:
        if c.verdict != "ok" and 1 <= c.cut <= len(cut_times):
            print(f"⚠ {fmt_ts(cut_times[c.cut - 1], True)} [{c.verdict}] {c.explanation} → {c.suggestion}")
    print(review.overall)


if __name__ == "__main__":
    main()
