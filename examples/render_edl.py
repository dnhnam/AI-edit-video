"""Bước 3 — Render EDL thành video bằng ffmpeg (không cần Claude).

    # Bản xem trước nhanh, 540p, kèm phụ đề đốt vào hình
    python render_edl.py work/interview.edl.json -o out/preview.mp4 --preview --burn-subs

    # Bản cuối, chất lượng cao, phụ đề xuất ra file .srt riêng
    python render_edl.py work/interview.edl.json -o out/final.mp4

    # Short dọc 9:16: cắt giữa khung, phụ đề kiểu Shorts, chữ hook ở đầu video
    python render_edl.py shorts/short_01.edl.json -o out/short_01.mp4 \
        --aspect 9:16 --burn-subs --short-captions --hook

- Mỗi đoạn được fade âm thanh rất ngắn (mặc định 30 ms) ở hai đầu để không bị "bụp"
  tại điểm cắt.
- Nếu EDL có mục "broll" (xem broll.py), các clip B-roll được phủ lên hình ở đúng thời
  điểm, giữ nguyên tiếng của video chính.
- Footage gốc không bao giờ bị ghi đè; chỉ ghi ra file output.
- Nếu EDL có đường dẫn transcript, script tự tạo phụ đề .srt khớp với timeline mới.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from media import (Cue, fmt_ts, load_transcript, probe, remap_words, require_ffmpeg, run,
                   words_to_cues, write_srt)

ASPECTS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}

# Kiểu chữ libass. Cỡ chữ tính theo khung 288 dòng của SRT, nên tự co giãn theo video.
STYLE_NORMAL = "Fontsize=20,Outline=2,MarginV=30"
# Phụ đề kiểu Shorts: chữ to, đậm, đặt cao hơn để tránh thanh nút của TikTok/Reels.
STYLE_SHORT = "Fontsize=13,Bold=1,Outline=3,Shadow=0,Alignment=2,MarginV=70"
STYLE_HOOK = "Fontsize=15,Bold=1,BorderStyle=3,Outline=6,BackColour=&H40000000,Alignment=6,MarginV=40"


def even(x: float) -> int:
    return max(2, int(round(x / 2)) * 2)


def frame_size(src_w: int, src_h: int, aspect: str, preview: bool) -> tuple[int, int]:
    if aspect == "source":
        w, h = src_w, src_h
        if preview and h > 540:
            w, h = src_w * 540 / src_h, 540
    else:
        w, h = ASPECTS[aspect]
        if preview:
            w, h = w / 2, h / 2
    return even(w), even(h)


def reframe_filter(src: str, dst: str, w: int, h: int, aspect: str, fit: str, focus: float) -> str:
    """Đưa hình về khung w×h: cắt (crop) theo vị trí `focus`, hoặc nền mờ (blur)."""
    if aspect == "source":
        return f"[{src}]scale={w}:{h},setsar=1[{dst}]"
    if fit == "blur":
        return (
            f"[{src}]split=2[bgsrc][fgsrc];"
            f"[bgsrc]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=20:2[bg];"
            f"[fgsrc]scale={w}:{h}:force_original_aspect_ratio=decrease,setsar=1[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[{dst}]"
        )
    return (f"[{src}]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h}:(iw-ow)*{focus:.3f}:(ih-oh)/2,setsar=1[{dst}]")


def build_filtergraph(segments: list[dict], broll: list[dict], has_audio: bool, fade: float,
                      size: tuple[int, int], aspect: str = "source", fit: str = "crop",
                      focus: float = 0.5, subtitle_filters: list[str] | None = None) -> str:
    w, h = size
    parts, pads = [], []
    for i, seg in enumerate(segments):
        dur = seg["end"] - seg["start"]
        parts.append(f"[{i}:v:0]trim=duration={dur:.3f},setpts=PTS-STARTPTS[v{i}]")
        pads.append(f"[v{i}]")
        if has_audio:
            f = min(fade, dur / 4)
            parts.append(
                f"[{i}:a:0]atrim=duration={dur:.3f},asetpts=PTS-STARTPTS,"
                f"afade=t=in:st=0:d={f:.3f},afade=t=out:st={dur - f:.3f}:d={f:.3f}[a{i}]"
            )
            pads.append(f"[a{i}]")
    audio_out = "[outa]" if has_audio else ""
    parts.append(f"{''.join(pads)}concat=n={len(segments)}:v=1:a={int(has_audio)}[cat]{audio_out}")
    parts.append(reframe_filter("cat", "base0", w, h, aspect, fit, focus))

    # B-roll: mỗi clip được dời tới đúng thời điểm trên timeline mới rồi phủ kín khung.
    current = "base0"
    for k, b in enumerate(broll):
        idx = len(segments) + k
        start, dur = b["start"], b["duration"]
        parts.append(
            f"[{idx}:v:0]trim=duration={dur:.3f},setpts=PTS-STARTPTS+{start:.3f}/TB,"
            f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1[b{k}]"
        )
        parts.append(f"[{current}][b{k}]overlay=eof_action=pass:"
                     f"enable='between(t,{start:.3f},{start + dur:.3f})'[base{k + 1}]")
        current = f"base{k + 1}"

    parts.append(f"[{current}]{','.join(subtitle_filters or ['null'])}[outv]")
    return ";\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("edl", help="File EDL JSON (từ plan_cuts.py, plan_shorts.py hoặc tự viết)")
    parser.add_argument("-o", "--output", required=True, help="File video đầu ra (.mp4)")
    parser.add_argument("--source", help="Ghi đè đường dẫn video nguồn trong EDL")
    parser.add_argument("--preview", action="store_true", help="Render nhanh, nửa độ phân giải, để duyệt")
    parser.add_argument("--aspect", choices=["source", *ASPECTS], default="source",
                        help="Khung hình đầu ra: source (giữ nguyên), 9:16, 1:1, 16:9")
    parser.add_argument("--fit", choices=["crop", "blur"], default="crop",
                        help="Khi đổi khung: crop = cắt cho đầy khung; blur = giữ cả hình, nền mờ")
    parser.add_argument("--focus", type=float, default=0.5,
                        help="Vị trí cắt ngang khi --fit crop: 0 = mép trái, 0.5 = giữa, 1 = mép phải")
    parser.add_argument("--burn-subs", action="store_true", help="Đốt phụ đề vào hình")
    parser.add_argument("--short-captions", action="store_true",
                        help="Phụ đề kiểu Shorts: mỗi lần vài chữ, chữ to, đặt cao khỏi thanh nút")
    parser.add_argument("--hook", nargs="?", const="", default=None, metavar="TEXT",
                        help="Hiện chữ hook ở đầu video (bỏ trống TEXT = dùng trường 'hook' trong EDL)")
    parser.add_argument("--hook-duration", type=float, default=2.5, help="Thời gian hiện chữ hook (giây)")
    parser.add_argument("--fade", type=float, default=0.03, help="Độ dài fade âm thanh mỗi điểm cắt (giây)")
    parser.add_argument("--crf", type=int, default=18, help="Chất lượng x264 (thấp = đẹp hơn), mặc định 18")
    args = parser.parse_args()

    require_ffmpeg()
    edl_path = Path(args.edl)
    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    source = Path(args.source or edl["source"]).resolve()
    output = Path(args.output).resolve()
    if output == source:
        raise SystemExit("Output trùng với file nguồn — không ghi đè footage gốc.")
    segments = [s for s in edl["segments"] if s["end"] - s["start"] > 0.05]
    if not segments:
        raise SystemExit("EDL không có đoạn nào.")

    info = probe(source)
    for s in segments:
        if s["start"] < 0 or s["end"] > info.duration + 0.05:
            raise SystemExit(f"Đoạn {s['start']}–{s['end']} nằm ngoài video nguồn ({info.duration:.2f}s).")
    total = sum(s["end"] - s["start"] for s in segments)

    broll = []
    for b in edl.get("broll", []):
        file = Path(b["file"])
        if not file.is_absolute():
            file = (edl_path.parent / file).resolve()
        if not file.exists():
            raise SystemExit(f"Không thấy file B-roll: {file}")
        dur = min(b["duration"], total - b["start"])
        if dur > 0.2:
            broll.append({**b, "file": str(file), "duration": dur})

    size = frame_size(info.width or 1920, info.height or 1080, args.aspect, args.preview)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        subtitle_filters: list[str] = []

        srt_text = None
        if edl.get("transcript") and Path(edl["transcript"]).exists():
            words = remap_words(load_transcript(edl["transcript"])["words"], segments)
            cues = (words_to_cues(words, max_chars=16, max_dur=1.6) if args.short_captions
                    else words_to_cues(words))
            srt_text = write_srt(cues)
            output.with_suffix(".srt").write_text(srt_text, encoding="utf-8")
            if args.burn_subs:
                # ffmpeg chạy với cwd=tmp nên chỉ cần tên file, tránh lỗi escape đường dẫn Windows.
                (Path(tmp) / "subs.srt").write_text(srt_text, encoding="utf-8")
                style = STYLE_SHORT if args.short_captions else STYLE_NORMAL
                subtitle_filters.append(f"subtitles=subs.srt:force_style='{style}'")
        elif args.burn_subs:
            print("Không có transcript trong EDL — bỏ qua phụ đề.")

        if args.hook is not None:
            hook = args.hook or edl.get("hook", "")
            if hook:
                (Path(tmp) / "hook.srt").write_text(
                    write_srt([Cue(1, 0.0, min(args.hook_duration, total), hook)]), encoding="utf-8")
                subtitle_filters.append(f"subtitles=hook.srt:force_style='{STYLE_HOOK}'")
            else:
                print("EDL không có trường 'hook' — bỏ qua chữ hook.")

        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats"]
        for s in segments:
            # Seek riêng từng đoạn ở phía input: nhanh, chính xác tới frame khi encode lại,
            # và không phải giữ cả video trong bộ nhớ khi các đoạn bị đảo thứ tự.
            cmd += ["-ss", f"{s['start']:.3f}", "-t", f"{s['end'] - s['start']:.3f}", "-i", str(source)]
        for b in broll:
            cmd += ["-ss", f"{b.get('source_start', 0):.3f}", "-t", f"{b['duration']:.3f}", "-i", b["file"]]
        graph = build_filtergraph(segments, broll, info.has_audio, args.fade, size,
                                  args.aspect, args.fit, args.focus, subtitle_filters)
        cmd += ["-filter_complex", graph, "-map", "[outv]"]
        if info.has_audio:
            cmd += ["-map", "[outa]", "-c:a", "aac", "-b:a", "192k"]
        cmd += [
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "veryfast" if args.preview else "medium",
            "-crf", str(28 if args.preview else args.crf),
            "-movflags", "+faststart", str(output),
        ]
        print(f"Render {len(segments)} đoạn, {len(broll)} B-roll, khung {size[0]}x{size[1]} -> {output}")
        run(cmd, cwd=tmp)

    out_info = probe(output)
    print(f"Xong: {fmt_ts(out_info.duration, True)} (dự kiến {fmt_ts(total, True)}).")
    if srt_text:
        print(f"Phụ đề: {output.with_suffix('.srt')}")
    cuts, t = [], 0.0
    for s in segments[:-1]:
        t += s["end"] - s["start"]
        cuts.append(fmt_ts(t, True))
    if cuts:
        print("Hãy xem kỹ các điểm cắt tại: " + ", ".join(cuts))


if __name__ == "__main__":
    main()
