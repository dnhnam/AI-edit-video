"""Bước 2 — Claude đọc transcript và lên kế hoạch cắt (EDL) theo brief.

Điểm mấu chốt: Claude chỉ được CHỌN ID của các cụm lời thoại có sẵn; mốc thời
gian do code tính từ transcript. Nhờ vậy Claude không thể "bịa" timestamp, và
mọi điểm cắt đều rơi vào khoảng giữa hai từ.

    python plan_cuts.py work/interview.transcript.json \
        --brief "Bản 90 giây cho Facebook: giữ phần kể chuyện khởi nghiệp, bỏ ậm ừ và câu nói hỏng" \
        -o work/interview.edl.json

Xem trước dữ liệu gửi cho Claude mà không gọi API:  --dry-run
Kết quả là file EDL dạng JSON để NGƯỜI duyệt trước khi render (render_edl.py).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel, Field

from media import Phrase, fmt_ts, group_phrases, load_transcript, pack_phrases

SYSTEM = """Bạn là biên tập viên dựng phim giàu kinh nghiệm. Bạn nhận transcript đã chia \
thành các cụm lời thoại có ID dạng Pxxxx kèm mốc thời gian. Nhiệm vụ: chọn các dải cụm \
cần GIỮ để tạo bản dựng thô (rough cut) đúng brief.

Quy tắc:
- Chỉ dùng ID có trong transcript; không tự đặt mốc thời gian.
- Mỗi mục trong `keep` là một dải liên tục first_id..last_id (gồm cả hai đầu).
- Thứ tự các mục trong `keep` là thứ tự phát trong video mới. Giữ trình tự gốc, trừ khi \
brief yêu cầu đảo (ví dụ đưa một câu "hook" lên đầu).
- Bỏ ậm ừ, nói lắp, câu nói hỏng rồi nói lại (giữ lần nói tốt nhất, thường là lần cuối), \
đoạn lạc đề và khoảng lặng dài.
- Mỗi ý giữ lại phải trọn vẹn và tự đứng được; không cắt làm câu mất nghĩa.
- Nếu brief có độ dài mục tiêu, cộng thời lượng các cụm để bám sát mục tiêu đó.
- Ghi vào `warnings` mọi chỗ không chắc chắn: tên riêng có vẻ bị ASR viết sai, hai lần \
nói gần giống nhau, ý bị đứt, chỗ cần cảnh chèn (b-roll) để che vết cắt."""


class KeepRange(BaseModel):
    first_id: int = Field(description="Số ID của cụm đầu tiên, ví dụ 12 cho P0012")
    last_id: int = Field(description="Số ID của cụm cuối cùng (gồm cả cụm này)")
    reason: str = Field(description="Vì sao giữ đoạn này, ngắn gọn")


class CutPlan(BaseModel):
    title: str = Field(description="Tên gợi ý cho bản dựng")
    summary: str = Field(description="Tóm tắt mạch nội dung của bản dựng, 2-4 câu")
    keep: list[KeepRange]
    warnings: list[str]


def plan_to_segments(keep: list[KeepRange], phrases: list[Phrase], duration: float,
                     pad_before: float = 0.08, pad_after: float = 0.15) -> tuple[list[dict], list[str]]:
    """Đổi dải ID thành đoạn thời gian; kiểm tra và gộp các dải liền kề."""
    by_id = {p.id: p for p in phrases}
    warnings: list[str] = []
    ranges: list[KeepRange] = []
    for r in keep:
        if r.first_id not in by_id or r.last_id not in by_id or r.first_id > r.last_id:
            warnings.append(f"Bỏ dải không hợp lệ P{r.first_id:04d}–P{r.last_id:04d}")
            continue
        if ranges and r.first_id == ranges[-1].last_id + 1:
            # Liền mạch với dải trước trong video gốc -> gộp, tránh tạo vết cắt thừa.
            ranges[-1] = KeepRange(first_id=ranges[-1].first_id, last_id=r.last_id,
                                   reason=f"{ranges[-1].reason}; {r.reason}")
        else:
            ranges.append(r)

    used: set[int] = set()
    segments = []
    for r in ranges:
        ids = set(range(r.first_id, r.last_id + 1))
        if ids & used:
            warnings.append(f"Dải P{r.first_id:04d}–P{r.last_id:04d} dùng lại cụm đã có ở đoạn khác")
        used |= ids
        first, last = by_id[r.first_id], by_id[r.last_id]
        prev_end = by_id[r.first_id - 1].end if r.first_id - 1 in by_id else 0.0
        next_start = by_id[r.last_id + 1].start if r.last_id + 1 in by_id else duration
        # Chừa chút "hơi thở" quanh lời nói, nhưng không lấn quá nửa khoảng lặng
        # sang cụm bị bỏ bên cạnh.
        start = max(first.start - pad_before, (prev_end + first.start) / 2, 0.0)
        end = min(last.end + pad_after, (last.end + next_start) / 2, duration)
        segments.append({
            "start": round(start, 3),
            "end": round(end, 3),
            "phrases": [r.first_id, r.last_id],
            "reason": r.reason,
            "text": " ".join(by_id[i].text for i in range(r.first_id, r.last_id + 1)),
        })
    return segments, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("transcript", help="Transcript JSON từ transcribe.py")
    parser.add_argument("--brief", required=True, help="Mô tả bản dựng mong muốn (mục tiêu, độ dài, nền tảng, giọng điệu...)")
    parser.add_argument("-o", "--output", required=True, help="File EDL JSON đầu ra")
    parser.add_argument("--max-gap", type=float, default=0.5, help="Khoảng lặng (giây) để tách cụm, mặc định 0.5")
    parser.add_argument("--effort", default="high", help="Mức suy luận: low|medium|high|xhigh|max (mặc định high)")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in dữ liệu sẽ gửi cho Claude")
    args = parser.parse_args()

    transcript = load_transcript(args.transcript)
    phrases = group_phrases(transcript["words"], max_gap=args.max_gap)
    duration = float(transcript.get("duration") or (phrases[-1].end if phrases else 0))
    packed = pack_phrases(phrases)
    user_text = (
        f"<brief>\n{args.brief}\n</brief>\n\n"
        f"Thời lượng video gốc: {fmt_ts(duration)} — {len(phrases)} cụm lời thoại.\n\n"
        f"<transcript>\n{packed}\n</transcript>"
    )

    if args.dry_run:
        print(user_text)
        print(f"\n[dry-run] ~{len(user_text)} ký tự sẽ được gửi cho Claude.")
        return

    from claude_helper import ask_structured  # import muộn để --dry-run không cần SDK

    plan = ask_structured(SYSTEM, user_text, CutPlan, effort=args.effort)
    segments, warnings = plan_to_segments(plan.keep, phrases, duration)
    total = sum(s["end"] - s["start"] for s in segments)

    edl = {
        "source": transcript.get("source"),
        "transcript": str(Path(args.transcript).resolve()),
        "title": plan.title,
        "summary": plan.summary,
        "brief": args.brief,
        "estimated_duration": round(total, 2),
        "segments": segments,
        "warnings": plan.warnings + warnings,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(edl, ensure_ascii=False, indent=2), encoding="utf-8")

    # In bản "paper edit" để người duyệt nhanh trước khi render.
    print(f"\n# {plan.title}\n{plan.summary}\n")
    t = 0.0
    for i, s in enumerate(segments, 1):
        print(f"{i:>2}. [{fmt_ts(t)}] nguồn {fmt_ts(s['start'], True)}–{fmt_ts(s['end'], True)} "
              f"— {s['reason']}\n    “{s['text'][:160]}{'…' if len(s['text']) > 160 else ''}”")
        t += s["end"] - s["start"]
    print(f"\nTổng: {fmt_ts(total)} (gốc {fmt_ts(duration)}), {len(segments)} đoạn.")
    for w in edl["warnings"]:
        print(f"⚠ {w}")
    print(f"\nĐã ghi {args.output}. Duyệt/sửa file này rồi chạy render_edl.py.")


if __name__ == "__main__":
    main()
