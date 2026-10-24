"""Bước 1 — Chuyển giọng nói thành transcript có mốc thời gian từng từ.

Claude không nghe được âm thanh, nên bước này dùng mô hình ASR chạy local
(faster-whisper). Kết quả là "bề mặt chính" để Claude đọc và lên kế hoạch dựng.

    pip install faster-whisper
    python transcribe.py raw/interview.mp4 -o work/interview.transcript.json --language vi

Có thể thay bằng dịch vụ ASR khác (WhisperX, ElevenLabs Scribe, Deepgram...),
miễn là xuất ra cùng định dạng JSON (xem media.py).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from media import probe, require_ffmpeg


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", help="File video/âm thanh nguồn")
    parser.add_argument("-o", "--output", required=True, help="File transcript JSON đầu ra")
    parser.add_argument("--language", default=None, help="Mã ngôn ngữ, ví dụ vi, en (bỏ trống = tự nhận)")
    parser.add_argument("--model", default="large-v3",
                        help="Model whisper: tiny|base|small|medium|large-v3 (mặc định large-v3, chính xác nhất cho tiếng Việt)")
    parser.add_argument("--prompt", default=None,
                        help="Gợi ý từ vựng/tên riêng để ASR viết đúng, ví dụ: 'Claude, Anthropic, DaVinci Resolve'")
    args = parser.parse_args()

    require_ffmpeg()
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit("Chưa cài faster-whisper: pip install faster-whisper")

    info = probe(args.video)
    if not info.has_audio:
        raise SystemExit("File không có track âm thanh.")

    model = WhisperModel(args.model, device="auto", compute_type="auto")
    segments, asr_info = model.transcribe(
        args.video,
        language=args.language,
        word_timestamps=True,
        initial_prompt=args.prompt,
    )

    words = []
    for seg in segments:
        for w in seg.words or []:
            text = w.word.strip()
            if text:
                words.append({"start": round(w.start, 3), "end": round(w.end, 3),
                              "text": text, "prob": round(w.probability, 3)})
        print(f"\r{seg.end:7.1f}s / {info.duration:.1f}s", end="", flush=True)
    print()

    out = {"source": str(Path(args.video).resolve()), "duration": info.duration,
           "language": asr_info.language, "words": words}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    low_conf = sum(1 for w in words if w["prob"] < 0.5)
    print(f"Đã ghi {len(words)} từ vào {args.output} (ngôn ngữ: {asr_info.language}).")
    if words and low_conf / len(words) > 0.1:
        print(f"Cảnh báo: {low_conf} từ có độ tin cậy thấp — nên rà lại tên riêng/thuật ngữ trước khi dựng.")


if __name__ == "__main__":
    main()
