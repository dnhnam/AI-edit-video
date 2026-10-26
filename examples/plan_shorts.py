"""Từ một video dài, Claude chọn nhiều đoạn để làm thành nhiều video short.

    python plan_shorts.py work/podcast.transcript.json -o shorts --count 6 --min 20 --max 55 \
        --brief "TikTok/Reels cho chủ shop online; mỗi short một bài học cụ thể, hook mạnh"

Mỗi short là một EDL riêng (`shorts/short_01.edl.json`, ...) gồm các dải cụm lời thoại,
có thể ghép từ nhiều chỗ trong video gốc (ví dụ câu "hook" lấy từ phút 12, phần thân lấy
từ phút 10). File `shorts/index.md` liệt kê tất cả để người duyệt trước khi render.

Như plan_cuts.py: Claude chỉ chọn ID cụm, code mới là bên tính thời gian.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel, Field

from media import fmt_ts, group_phrases, load_transcript, pack_phrases
from plan_cuts import KeepRange, plan_to_segments

SYSTEM = """Bạn là biên tập viên chuyên làm video ngắn (TikTok, Reels, YouTube Shorts) từ \
nội dung dài. Bạn nhận transcript chia thành các cụm có ID dạng Pxxxx. Nhiệm vụ: tìm các \
khoảnh khắc có thể đứng một mình thành một short hấp dẫn.

Mỗi short phải:
- Có hook trong 1–3 giây đầu: một câu gây tò mò, một con số, một khẳng định mạnh. Được phép \
đưa câu hook từ chỗ khác lên đầu, miễn là không làm sai ý người nói.
- Trọn một ý: người xem chưa xem video gốc vẫn hiểu. Tránh mở đầu bằng "như tôi vừa nói", \
"cái đó"... mà không có ngữ cảnh.
- Kết thúc gọn: một kết luận, câu đắt giá hoặc lời kêu gọi; không dừng giữa chừng.
- Bỏ ậm ừ, câu nói hỏng, khoảng lặng; nhịp nhanh.
- Nằm trong khoảng thời lượng yêu cầu (cộng thời lượng các cụm).
- Không trùng nội dung với short khác.

Chỉ dùng ID có trong transcript; không tự đặt mốc thời gian. Thứ tự các dải trong `keep` là \
thứ tự phát. Sắp các short theo `score` giảm dần. Ghi vào `warnings` những chỗ cần người \
kiểm tra (tên riêng có thể bị chép sai, ý dễ bị hiểu lệch khi cắt khỏi ngữ cảnh)."""


class Short(BaseModel):
    title: str = Field(description="Tiêu đề đăng kèm video, ≤ 60 ký tự")
    hook: str = Field(description="Chữ hiện trên màn hình 2–3 giây đầu, ≤ 8 từ")
    keep: list[KeepRange]
    why: str = Field(description="Vì sao đoạn này hấp dẫn và tự đứng được")
    score: int = Field(description="Tiềm năng thu hút người xem, 1–10")
    hashtags: list[str]


class ShortsPlan(BaseModel):
    shorts: list[Short]
    warnings: list[str]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("transcript", help="Transcript JSON từ transcribe.py")
    parser.add_argument("-o", "--outdir", required=True, help="Thư mục ghi các EDL short")
    parser.add_argument("--count", type=int, default=5, help="Số short muốn có (mặc định 5)")
    parser.add_argument("--min", type=float, default=20, help="Thời lượng tối thiểu mỗi short (giây)")
    parser.add_argument("--max", type=float, default=60, help="Thời lượng tối đa mỗi short (giây)")
    parser.add_argument("--brief", default="", help="Nền tảng, khán giả, giọng điệu, chủ đề ưu tiên...")
    parser.add_argument("--effort", default="high", help="low|medium|high|xhigh|max (mặc định high)")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in dữ liệu sẽ gửi cho Claude")
    args = parser.parse_args()

    transcript = load_transcript(args.transcript)
    phrases = group_phrases(transcript["words"])
    duration = float(transcript.get("duration") or (phrases[-1].end if phrases else 0))
    user_text = (
        f"Hãy đề xuất {args.count} short, mỗi short dài {args.min:.0f}–{args.max:.0f} giây.\n"
        + (f"<brief>\n{args.brief}\n</brief>\n" if args.brief else "")
        + f"Video gốc dài {fmt_ts(duration)}, {len(phrases)} cụm lời thoại.\n\n"
        f"<transcript>\n{pack_phrases(phrases)}\n</transcript>"
    )
    if args.dry_run:
        print(user_text)
        print(f"\n[dry-run] ~{len(user_text)} ký tự sẽ được gửi cho Claude.")
        return

    from claude_helper import ask_structured

    plan = ask_structured(SYSTEM, user_text, ShortsPlan, effort=args.effort)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    rows, used, all_warnings = [], {}, list(plan.warnings)
    for n, short in enumerate(sorted(plan.shorts, key=lambda s: -s.score), 1):
        segments, warnings = plan_to_segments(short.keep, phrases, duration)
        if not segments:
            all_warnings.append(f"Short {n} ({short.title}) không có đoạn hợp lệ — bỏ qua.")
            continue
        total = sum(s["end"] - s["start"] for s in segments)
        if not args.min - 3 <= total <= args.max + 3:
            warnings.append(f"Dài {total:.0f}s, ngoài khoảng {args.min:.0f}–{args.max:.0f}s")
        for s in segments:
            for pid in range(s["phrases"][0], s["phrases"][1] + 1):
                if used.get(pid, n) != n:
                    warnings.append(f"Dùng lại P{pid:04d} đã có trong short {used[pid]}")
                    break
            used.update({pid: n for pid in range(s["phrases"][0], s["phrases"][1] + 1)})
        name = f"short_{n:02d}"
        edl = {
            "source": transcript.get("source"),
            "transcript": str(Path(args.transcript).resolve()),
            "title": short.title,
            "hook": short.hook,
            "hashtags": short.hashtags,
            "why": short.why,
            "score": short.score,
            "estimated_duration": round(total, 2),
            "segments": segments,
            "warnings": warnings,
        }
        (outdir / f"{name}.edl.json").write_text(json.dumps(edl, ensure_ascii=False, indent=2), encoding="utf-8")
        first = segments[0]
        rows.append(f"| {name} | {short.score} | {fmt_ts(total)} | {fmt_ts(first['start'])} | "
                    f"{short.hook} | {short.title} | {'; '.join(warnings)} |")
        all_warnings += [f"{name}: {w}" for w in warnings]

    index = [
        f"# Shorts từ {Path(str(transcript.get('source'))).name}\n",
        "| File | Điểm | Dài | Bắt đầu ở nguồn | Hook | Tiêu đề | Cảnh báo |",
        "|---|---|---|---|---|---|---|",
        *rows,
        "\n## Cần người kiểm tra\n",
        *[f"- {w}" for w in all_warnings],
    ]
    (outdir / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print("\n".join(index))
    print(f"\nĐã ghi {len(rows)} EDL vào {outdir}/. Duyệt index.md rồi render từng short bằng render_edl.py.")


if __name__ == "__main__":
    main()
