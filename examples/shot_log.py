"""Claude "xem" footage qua khung hình mẫu: lập shot log, gợi ý chương và thumbnail.

    # Lấy 1 khung mỗi 5 giây
    python shot_log.py raw/vlog.mp4 -o work/vlog.shots.json --every 5

    # Lấy khung tại các điểm chuyển cảnh, kết hợp transcript để đặt tên chương
    python shot_log.py raw/vlog.mp4 -o work/vlog.shots.json --scenes \
        --transcript work/vlog.transcript.json \
        --brief "Tìm cảnh mở đầu hấp dẫn, cảnh làm b-roll, và cảnh hỏng (mờ, tối, rung)"

Kết quả: file JSON + file Markdown (bảng cảnh quay, chương YouTube dạng 00:00 Tiêu đề).
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from frames import estimate_tokens, extract_frame, labeled_frames, scene_change_times
from media import fmt_ts, group_phrases, load_transcript, pack_phrases, probe, require_ffmpeg

SYSTEM = """Bạn là trợ lý dựng phim (assistant editor) chuyên ghi chép footage. Bạn nhận \
các khung hình mẫu, mỗi khung có nhãn "Khung N — thời điểm". Khung hình chỉ là mẫu thưa: \
đừng suy đoán chuyển động, âm thanh hay sự kiện xảy ra giữa hai khung. Không nêu tên người \
thật; mô tả họ bằng vai trò hoặc ngoại hình (ví dụ "người dẫn áo xanh"). Nếu có transcript, \
dùng nó để hiểu nội dung, nhưng mô tả hình ảnh phải dựa trên những gì thấy trong khung."""


class Shot(BaseModel):
    frame: int = Field(description="Số N của khung")
    description: str = Field(description="Mô tả ngắn những gì thấy trong khung")
    shot_type: Literal["wide", "medium", "close_up", "extreme_close_up",
                       "screen_recording", "text_graphic", "other"]
    quality_issues: list[str] = Field(description="Ví dụ: mờ nét, thiếu sáng, cháy sáng, rung, lệch khung; rỗng nếu ổn")
    usable_as: list[str] = Field(description="Ví dụ: hook, b-roll, thumbnail, cảnh chuyển; rỗng nếu không dùng được")
    score: int = Field(description="Chất lượng sử dụng 1-5")


class Chapter(BaseModel):
    start_frame: int
    title: str


class ShotLog(BaseModel):
    shots: list[Shot]
    chapters: list[Chapter]
    thumbnail_frames: list[int] = Field(description="Tối đa 3 khung hợp làm thumbnail, tốt nhất trước")
    notes: str = Field(description="Nhận xét chung cho người dựng")


def pick_times(duration: float, every: float, scenes: list[float] | None, max_frames: int) -> list[float]:
    if scenes is not None:
        times = [0.0] + [t for t in scenes if t > 0.5]
    else:
        times = [i * every for i in range(int(duration // every) + 1)]
    times = [t for t in times if t < duration - 0.1] or [0.0]
    if len(times) > max_frames:
        step = len(times) / max_frames
        times = [times[int(i * step)] for i in range(max_frames)]
    return times


def youtube_chapters(chapters: list[tuple[float, str]], min_len: float = 10.0) -> list[tuple[float, str]]:
    """YouTube yêu cầu chương đầu ở 00:00 và mỗi chương dài ít nhất 10 giây."""
    out: list[tuple[float, str]] = []
    for t, title in sorted(chapters):
        if not out:
            out.append((0.0, title))
        elif t - out[-1][0] >= min_len:
            out.append((t, title))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video")
    parser.add_argument("-o", "--output", required=True, help="File JSON đầu ra (kèm file .md cùng tên)")
    parser.add_argument("--every", type=float, default=5.0, help="Lấy 1 khung mỗi N giây (mặc định 5)")
    parser.add_argument("--scenes", action="store_true", help="Lấy khung tại điểm chuyển cảnh thay vì đều đặn")
    parser.add_argument("--max-frames", type=int, default=120, help="Số khung tối đa gửi cho Claude")
    parser.add_argument("--transcript", help="Transcript JSON (tùy chọn) để Claude hiểu nội dung lời nói")
    parser.add_argument("--brief", default="Lập shot log, chia chương, gợi ý thumbnail.", help="Yêu cầu cụ thể")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ trích khung và ước tính token")
    args = parser.parse_args()

    require_ffmpeg()
    info = probe(args.video)
    scenes = scene_change_times(args.video) if args.scenes else None
    times = pick_times(info.duration, args.every, scenes, args.max_frames)
    per_frame = estimate_tokens(info.width or 1280, info.height or 720)
    print(f"{len(times)} khung × ~{per_frame} token ≈ {len(times) * per_frame:,} token ảnh.")

    with tempfile.TemporaryDirectory() as tmp:
        frames = []
        for i, t in enumerate(times, 1):
            path = extract_frame(args.video, t, Path(tmp) / f"f{i:04d}.jpg")
            frames.append((f"Khung {i}", t, path))
        if args.dry_run:
            return

        content: list[dict] = []
        if args.transcript:
            tr = load_transcript(args.transcript)
            content.append({"type": "text", "text": f"<transcript>\n{pack_phrases(group_phrases(tr['words']))}\n</transcript>"})
        content += labeled_frames(frames)
        content.append({"type": "text", "text": (
            f"Video dài {fmt_ts(info.duration)}, {len(times)} khung mẫu ở trên.\n"
            f"<brief>\n{args.brief}\n</brief>\n"
            "Trả về shot log cho từng khung, các chương (theo số khung bắt đầu) và thumbnail."
        )})

        from claude_helper import ask_structured  # import muộn để --dry-run không cần SDK
        log = ask_structured(SYSTEM, content, ShotLog, effort="medium")

    time_of = {i: t for i, t in enumerate(times, 1)}
    shots = [{**s.model_dump(), "time": round(time_of.get(s.frame, 0.0), 2)} for s in log.shots if s.frame in time_of]
    chapters = youtube_chapters([(time_of[c.start_frame], c.title) for c in log.chapters if c.start_frame in time_of])
    result = {
        "source": str(Path(args.video).resolve()),
        "shots": shots,
        "chapters": [{"time": t, "title": title} for t, title in chapters],
        "thumbnails": [{"frame": f, "time": time_of[f]} for f in log.thumbnail_frames if f in time_of],
        "notes": log.notes,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [f"# Shot log — {Path(args.video).name}\n", log.notes, "\n## Chương (dán vào mô tả YouTube)\n"]
    md += [f"{fmt_ts(t)} {title}" for t, title in chapters]
    md += ["\n## Cảnh quay\n", "| Thời điểm | Loại | Mô tả | Vấn đề | Dùng làm | Điểm |", "|---|---|---|---|---|---|"]
    md += [f"| {fmt_ts(s['time'])} | {s['shot_type']} | {s['description']} | {', '.join(s['quality_issues'])} "
           f"| {', '.join(s['usable_as'])} | {s['score']} |" for s in shots]
    out.with_suffix(".md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Đã ghi {out} và {out.with_suffix('.md')}")


if __name__ == "__main__":
    main()
