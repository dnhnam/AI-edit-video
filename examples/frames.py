"""Trích khung hình từ video và đóng gói thành content block ảnh cho Claude.

Claude không nhận file video; cách làm chuẩn là lấy mẫu khung hình (JPEG nhỏ)
và gắn nhãn thời gian cho từng ảnh.
"""
from __future__ import annotations

import base64
import re
import subprocess
from pathlib import Path

from media import fmt_ts, run

# Cạnh dài 512 px: đủ để nhận ra bố cục, người, chữ lớn; mỗi ảnh 16:9 tốn khoảng
# ceil(512/28) * ceil(288/28) = 19 * 11 = 209 token.
DEFAULT_LONG_EDGE = 512


def _scale_filter(long_edge: int) -> str:
    return (f"scale='if(gt(iw,ih),{long_edge},-2)':'if(gt(iw,ih),-2,{long_edge})'")


def extract_frame(video: str | Path, t: float, out: Path, long_edge: int = DEFAULT_LONG_EDGE) -> Path:
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{max(t, 0):.3f}", "-i", str(video),
         "-frames:v", "1", "-vf", _scale_filter(long_edge), "-q:v", "4", str(out)])
    return out


def scene_change_times(video: str | Path, threshold: float = 0.3) -> list[float]:
    """Dùng bộ lọc `select=gt(scene,...)` của ffmpeg để tìm điểm chuyển cảnh."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(video), "-an",
         "-vf", f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    return [float(m) for m in re.findall(r"pts_time:([0-9.]+)", proc.stderr)]


def estimate_tokens(width: int, height: int, long_edge: int = DEFAULT_LONG_EDGE) -> int:
    scale = long_edge / max(width, height)
    w, h = round(width * scale), round(height * scale)
    return -(-w // 28) * -(-h // 28)


def image_block(path: Path) -> dict:
    data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}


def labeled_frames(frames: list[tuple[str, float, Path]]) -> list[dict]:
    """[(nhãn, thời điểm, file)] -> content blocks: nhãn văn bản đứng trước mỗi ảnh."""
    blocks: list[dict] = []
    for label, t, path in frames:
        blocks.append({"type": "text", "text": f"{label} — {fmt_ts(t, True)}"})
        blocks.append(image_block(path))
    return blocks
