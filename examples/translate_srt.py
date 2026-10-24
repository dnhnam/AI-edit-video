"""Dịch / biên tập phụ đề SRT bằng Claude, giữ nguyên mốc thời gian.

    python translate_srt.py out/final.srt -o out/final.en.srt --to "tiếng Anh"
    python translate_srt.py talk.en.srt -o talk.vi.srt --to "tiếng Việt" \
        --glossary "prompt=prompt, timeline=timeline, Claude Code=Claude Code"

Claude nhận từng dòng kèm ID và chỉ trả lại văn bản; code ráp lại với thời gian
gốc và kiểm tra không thiếu dòng nào.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel

from media import Cue, chunked, parse_srt, write_srt

SYSTEM = """Bạn là biên dịch viên phụ đề chuyên nghiệp. Dịch tự nhiên, đúng văn nói, \
giữ giọng người nói. Phụ đề phải đọc kịp: ưu tiên câu ngắn gọn, tối đa khoảng 42 ký tự \
mỗi dòng, tối đa 2 dòng. Giữ nguyên tên riêng, tên sản phẩm và thuật ngữ trong glossary. \
Trả về đúng một mục cho mỗi ID nhận được, không gộp hay tách dòng."""


class Line(BaseModel):
    id: int
    text: str


class Translation(BaseModel):
    lines: list[Line]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("srt")
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--to", required=True, help="Ngôn ngữ đích, ví dụ 'tiếng Việt', 'English'")
    parser.add_argument("--glossary", default="", help="Danh sách thuật ngữ cần giữ/dịch cố định")
    parser.add_argument("--batch", type=int, default=150, help="Số dòng mỗi lượt gọi")
    args = parser.parse_args()

    from claude_helper import ask_structured

    cues = parse_srt(Path(args.srt).read_text(encoding="utf-8"))
    translated: dict[int, str] = {}
    prev_context: list[Cue] = []
    for batch in chunked(cues, args.batch):
        payload = [{"id": c.index, "text": c.text} for c in batch]
        context = "\n".join(c.text for c in prev_context[-5:])
        user = (f"Ngôn ngữ đích: {args.to}\n"
                + (f"<glossary>{args.glossary}</glossary>\n" if args.glossary else "")
                + (f"<previous_lines>\n{context}\n</previous_lines>\n" if context else "")
                + f"<lines>\n{json.dumps(payload, ensure_ascii=False)}\n</lines>")
        result = ask_structured(SYSTEM, user, Translation, effort="low")
        got = {line.id: line.text.strip() for line in result.lines}
        missing = [c.index for c in batch if c.index not in got]
        if missing:
            raise SystemExit(f"Claude trả thiếu {len(missing)} dòng (ví dụ ID {missing[:5]}) — thử giảm --batch.")
        translated.update(got)
        prev_context = batch
        print(f"Đã dịch {len(translated)}/{len(cues)} dòng")

    out = [Cue(c.index, c.start, c.end, translated[c.index]) for c in cues]
    Path(args.output).write_text(write_srt(out), encoding="utf-8")

    # Tốc độ đọc > ~20 ký tự/giây thường là quá nhanh với người xem.
    for c in out:
        cps = len(c.text.replace("\n", "")) / max(c.end - c.start, 0.1)
        if cps > 20:
            print(f"⚠ Dòng {c.index} đọc nhanh ({cps:.0f} ký tự/giây): {c.text}")
    print(f"Đã ghi {args.output}")


if __name__ == "__main__":
    main()
