"""Bước 3 — Render EDL thành video bằng ffmpeg (không cần Claude).

    # Bản xem trước nhanh, 540p, kèm phụ đề đốt vào hình
    python render_edl.py work/interview.edl.json -o out/preview.mp4 --preview --burn-subs

    # Bản cuối, chất lượng cao, phụ đề xuất ra file .srt riêng
    python render_edl.py work/interview.edl.json -o out/final.mp4

- Mỗi đoạn được fade âm thanh rất ngắn (mặc định 30 ms) ở hai đầu để không bị "bụp"
  tại điểm cắt.
- Footage gốc không bao giờ bị ghi đè; chỉ ghi ra file output.
- Nếu EDL có đường dẫn transcript, script tự tạo phụ đề .srt khớp với timeline mới.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from media import fmt_ts, load_transcript, probe, remap_words, require_ffmpeg, run, words_to_cues, write_srt


def build_filtergraph(segments: list[dict], has_audio: bool, fade: float, post_filters: list[str]) -> str:
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
    video_out = "[cv]" if post_filters else "[outv]"
    parts.append(f"{''.join(pads)}concat=n={len(segments)}:v=1:a={int(has_audio)}{video_out}{audio_out}")
    if post_filters:
        parts.append(f"[cv]{','.join(post_filters)}[outv]")
    return ";\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("edl", help="File EDL JSON (từ plan_cuts.py hoặc tự viết)")
    parser.add_argument("-o", "--output", required=True, help="File video đầu ra (.mp4)")
    parser.add_argument("--source", help="Ghi đè đường dẫn video nguồn trong EDL")
    parser.add_argument("--preview", action="store_true", help="Render nhanh 540p để duyệt")
    parser.add_argument("--burn-subs", action="store_true", help="Đốt phụ đề vào hình")
    parser.add_argument("--fade", type=float, default=0.03, help="Độ dài fade âm thanh mỗi điểm cắt (giây)")
    parser.add_argument("--crf", type=int, default=18, help="Chất lượng x264 (thấp = đẹp hơn), mặc định 18")
    args = parser.parse_args()

    require_ffmpeg()
    edl = json.loads(Path(args.edl).read_text(encoding="utf-8"))
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

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        post_filters = ["scale=-2:540"] if args.preview else []

        srt_text = None
        if edl.get("transcript") and Path(edl["transcript"]).exists():
            words = load_transcript(edl["transcript"])["words"]
            srt_text = write_srt(words_to_cues(remap_words(words, segments)))
            output.with_suffix(".srt").write_text(srt_text, encoding="utf-8")
            if args.burn_subs:
                # ffmpeg chạy với cwd=tmp nên chỉ cần tên file, tránh lỗi escape đường dẫn.
                (Path(tmp) / "subs.srt").write_text(srt_text, encoding="utf-8")
                post_filters.append("subtitles=subs.srt:force_style='Fontsize=20,Outline=2,MarginV=30'")
        elif args.burn_subs:
            print("Không có transcript trong EDL — bỏ qua phụ đề.")

        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats"]
        for s in segments:
            # Seek riêng từng đoạn ở phía input: nhanh, chính xác tới frame khi encode lại,
            # và không phải giữ cả video trong bộ nhớ khi các đoạn bị đảo thứ tự.
            cmd += ["-ss", f"{s['start']:.3f}", "-t", f"{s['end'] - s['start']:.3f}", "-i", str(source)]
        cmd += [
            "-filter_complex", build_filtergraph(segments, info.has_audio, args.fade, post_filters),
            "-map", "[outv]",
        ]
        if info.has_audio:
            cmd += ["-map", "[outa]", "-c:a", "aac", "-b:a", "192k"]
        cmd += [
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "veryfast" if args.preview else "medium",
            "-crf", str(28 if args.preview else args.crf),
            "-movflags", "+faststart", str(output),
        ]
        print(f"Render {len(segments)} đoạn -> {output}")
        run(cmd, cwd=tmp)

    out_info = probe(output)
    expected = sum(s["end"] - s["start"] for s in segments)
    print(f"Xong: {fmt_ts(out_info.duration, True)} (dự kiến {fmt_ts(expected, True)}).")
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
