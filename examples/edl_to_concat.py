"""Dựng project Concat từ một hoặc nhiều EDL: mỗi EDL thành một tab timeline.

Script tự chạy Concat ở chế độ không giao diện (`concat --mcp headless`) và gửi các lệnh
dựng qua MCP. Không gọi Claude, không tốn token. Xong việc, mở project trong Concat để
duyệt, chỉnh tay và xuất.

    # Một bản dựng ngang
    python edl_to_concat.py work/talk.edl.json --name talk_v01

    # Nhiều short dọc từ một video dài: 8 tab trong cùng một project
    python edl_to_concat.py shorts/*.edl.json --name podcast_shorts --aspect 9:16 --hook

    # Xem trước kế hoạch, không chạy Concat
    python edl_to_concat.py shorts/*.edl.json --name test --aspect 9:16 --dry-run

Mỗi tab gồm: các đoạn của EDL nối liền trên lane chính (fade âm ở mỗi điểm cắt), phụ đề
khớp timeline mới (nếu EDL có transcript), chữ hook (--hook), B-roll trên lane riêng
(nếu EDL có mục "broll"). Sau khi dựng, script đọc lại timeline để kiểm tra từng đoạn.

Viết cho Concat v0.2.8. Đường dẫn Concat: --concat, biến CONCAT_EXE, hoặc chỗ cài mặc định.
Concat chỉ ghi file trong thư mục người dùng (đặt CONCAT_MCP_ROOTS để mở rộng).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from media import fmt_ts, load_transcript, probe, remap_words, words_to_cues

ASPECTS = {"source": None, "16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080),
           "4:5": (1080, 1350)}
FONT = "Hanken Grotesk"  # có sẵn trong Concat và đủ dấu tiếng Việt
MIN_CLIP = 1 / 60         # clip ngắn nhất Concat cho phép


class ConcatError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# MCP qua stdio: JSON-RPC 2.0, mỗi dòng một thông điệp
# ---------------------------------------------------------------------------

class McpClient:
    def __init__(self, command: list[str]):
        self.log = tempfile.NamedTemporaryFile("w+b", suffix=".log", delete=False)
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self.log)
        self.next_id = 0
        self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "edl_to_concat", "version": "1.0"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _send(self, message: dict) -> None:
        # Ghi dạng bytes để Windows không đổi "\n" thành "\r\n".
        self.proc.stdin.write((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))
        self.proc.stdin.flush()

    def request(self, method: str, params: dict) -> dict:
        self.next_id += 1
        self._send({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params})
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise ConcatError(f"Concat dừng giữa chừng.\n{self.log_tail()}")
            message = json.loads(line.decode("utf-8"))
            if message.get("id") != self.next_id:
                continue  # thông báo tiến độ, bỏ qua
            if "error" in message:
                raise ConcatError(f"{method}: {message['error'].get('message')}")
            return message["result"]

    def call(self, tool: str, arguments: dict) -> dict:
        result = self.request("tools/call", {"name": tool, "arguments": arguments})
        text = "".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
        if result.get("isError"):
            raise ConcatError(f"{tool}: {text}")
        return result.get("structuredContent") or (json.loads(text) if text.strip().startswith("{") else {})

    def log_tail(self, lines: int = 15) -> str:
        self.log.flush()
        self.log.seek(0)
        return "\n".join(self.log.read().decode("utf-8", "replace").splitlines()[-lines:])

    def close(self) -> None:
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.log.close()
        os.unlink(self.log.name)


def find_concat(explicit: str | None) -> list[str]:
    """Lệnh khởi động Concat. CONCAT_MCP_COMMAND (dùng cho test) thay được cả lệnh."""
    if os.environ.get("CONCAT_MCP_COMMAND"):
        return shlex.split(os.environ["CONCAT_MCP_COMMAND"], posix=os.name != "nt")
    candidates = [explicit, os.environ.get("CONCAT_EXE")]
    if os.name == "nt":
        candidates += [os.path.expandvars(r"%LOCALAPPDATA%\Programs\Concat\concat.exe"),
                       r"C:\Program Files\Concat\concat.exe"]
    else:
        candidates += ["/Applications/Concat.app/Contents/MacOS/concat", "/usr/bin/concat", shutil.which("concat")]
    for c in candidates:
        if c and Path(c).exists():
            return [c]
    raise SystemExit("Không tìm thấy Concat. Cài Concat hoặc chỉ đường dẫn bằng --concat / CONCAT_EXE.")


# ---------------------------------------------------------------------------
# Kế hoạch dựng (thuần tính toán, kiểm thử được)
# ---------------------------------------------------------------------------

def rate_fraction(fps: float | None) -> tuple[int, int]:
    if not fps:
        return 30, 1
    for num, den in ((24000, 1001), (30000, 1001), (60000, 1001)):
        if abs(fps - num / den) < 0.01:
            return num, den
    return int(round(fps)), 1


def frame_for(aspect: str, src_w: int, src_h: int) -> tuple[int, int]:
    return ASPECTS[aspect] or (src_w, src_h)


def focus_offset(src_w: int, src_h: int, dst_w: int, dst_h: int, focus: float) -> float:
    """offsetX (phần của bề ngang khung) để khung "fill" lệch theo `focus` như render_edl.py."""
    k = (src_w / src_h) / (dst_w / dst_h)
    return round((0.5 - focus) * (k - 1), 4) if k > 1 else 0.0


def trims_for(segments: list[dict], media_duration: float) -> list[tuple[float, float]]:
    """(delta đầu, delta cuối) cho từng clip dài bằng cả video nguồn: cắt đầu bỏ phần
    trước `start`, cắt cuối bỏ phần sau `end`."""
    return [(round(s["start"], 4), round(s["end"] - media_duration, 4)) for s in segments]


def caption_cues(edl: dict, vertical: bool):
    if not edl.get("transcript") or not Path(edl["transcript"]).exists():
        return []
    words = remap_words(load_transcript(edl["transcript"])["words"], edl["segments"])
    return words_to_cues(words, max_chars=16, max_dur=1.6) if vertical else words_to_cues(words)


def caption_style(text: str, vertical: bool) -> dict:
    return {"content": text, "fontFamily": FONT, "fontSize": 0.032 if vertical else 0.04,
            "fontWeight": 800 if vertical else 600, "color": "#ffffff", "strokeWidth": 0.004,
            "strokeColor": "#000000", "maxWidth": 0.9}


def hook_style(text: str) -> dict:
    return {"content": text, "fontFamily": FONT, "fontSize": 0.045, "fontWeight": 800,
            "color": "#ffffff", "background": "#000000b3", "maxWidth": 0.85}


def describe_plan(edls: list[tuple[Path, dict]], args) -> None:
    for n, (path, edl) in enumerate(edls, 1):
        info = probe(edl["source"])
        w, h = frame_for(args.aspect, info.width or 1920, info.height or 1080)
        total = sum(s["end"] - s["start"] for s in edl["segments"])
        cues = caption_cues(edl, h > w) if not args.no_captions else []
        print(f"Tab {n:02d} «{tab_name(n, path, edl)}»: {w}x{h}, {len(edl['segments'])} đoạn, "
              f"{fmt_ts(total, True)}, {len(cues)} dòng phụ đề, {len(edl.get('broll', []))} B-roll"
              f"{', hook: ' + repr(edl.get('hook')) if args.hook and edl.get('hook') else ''}")
        for (head, tail), s in zip(trims_for(edl["segments"], info.duration), edl["segments"]):
            print(f"   nguồn {fmt_ts(s['start'], True)}–{fmt_ts(s['end'], True)}  "
                  f"(cắt đầu +{head:.3f}s, cắt cuối {tail:.3f}s)")


def tab_name(n: int, path: Path, edl: dict) -> str:
    name = edl.get("title") or path.name.removesuffix(".edl.json").removesuffix(".json")
    return f"{n:02d} {name}"[:60]


# ---------------------------------------------------------------------------
# Dựng
# ---------------------------------------------------------------------------

class Builder:
    def __init__(self, client: McpClient, project: str):
        self.client, self.project = client, project

    def edit(self, command: dict) -> dict:
        return self.client.call("edit_apply", {"path": self.project, "command": command})

    def batch(self, commands: list[dict]) -> dict:
        return self.edit({"op": "batch", "commands": commands}) if commands else {}

    def read(self) -> dict:
        return self.client.call("timeline_read", {"path": self.project})

    def media_id(self, file: str) -> tuple[str, float]:
        summary = self.client.call("media_import", {"path": self.project, "file": file})
        want = os.path.normcase(os.path.abspath(file))
        for item in summary.get("media", []):
            if os.path.normcase(os.path.abspath(item.get("path", ""))) == want:
                return item["id"], float(item.get("duration") or 0)
        if summary.get("createdId"):
            return summary["createdId"], probe(file).duration
        raise ConcatError(f"Không thấy {file} trong bin sau khi import.")

    def build_timeline(self, n: int, path: Path, edl: dict, args, first: bool) -> list[str]:
        info = probe(edl["source"])
        src_w, src_h = info.width or 1920, info.height or 1080
        w, h = frame_for(args.aspect, src_w, src_h)
        num, den = rate_fraction(info.fps)
        video = {"width": w, "height": h, "rateNum": num, "rateDen": den}
        segments = [s for s in edl["segments"] if s["end"] - s["start"] > 0.05]

        if not first:
            self.edit({"op": "addTimeline"})
        timeline_id = self.read()["timeline"]["id"]
        self.batch([{"op": "setTimelineVideo", "timelineId": timeline_id, "video": video},
                    {"op": "renameTimeline", "timelineId": timeline_id, "name": tab_name(n, path, edl)}])

        # Lane chính: đặt cả video nguồn N lần nối nhau, rồi cắt đầu/cuối từng bản (ripple)
        # trong một lệnh gộp: chỉ 3 lượt gọi dù EDL có bao nhiêu đoạn, và là một bước undo.
        media, duration = self.media_id(edl["source"])
        created = self.edit({"op": "addClipsInSequence", "mediaIds": [media] * len(segments), "start": 0})
        summary = self.read()
        lane = next(c["track"] for c in summary["timeline"]["clips"] if c["id"] == created.get("createdId"))
        main = [c for c in summary["timeline"]["clips"] if c["track"] == lane and c.get("media") == media]
        if len(main) != len(segments):
            raise ConcatError(f"Mong đợi {len(segments)} clip trên lane chính, thấy {len(main)}.")
        duration = duration or main[0]["duration"]
        commands = []
        for clip, (head, tail) in zip(main, trims_for(segments, duration)):
            if head > 0:
                commands.append({"op": "trimClip", "clipId": clip["id"], "edge": "start", "delta": head, "ripple": True})
            if tail < 0:
                commands.append({"op": "trimClip", "clipId": clip["id"], "edge": "end", "delta": tail, "ripple": True})
            commands.append({"op": "updateClip", "clipId": clip["id"],
                             "patch": {"fadeIn": args.fade, "fadeOut": args.fade}})
        reframe = (w / h) != (src_w / src_h)
        if reframe and args.fit == "fill":
            offset = focus_offset(src_w, src_h, w, h, args.focus)
            for clip in main:
                commands.append({"op": "frameClip", "clipId": clip["id"], "framing": "fill"})
                if offset:
                    commands.append({"op": "setClipTransform", "clipId": clip["id"], "offsetX": offset})
        elif reframe:
            commands += [{"op": "frameClip", "clipId": clip["id"], "framing": "fit"} for clip in main]
            commands.append({"op": "setTimelineBackground", "timelineId": timeline_id,
                             "background": {"kind": "blur", "amount": 0.6}})
        self.batch(commands)

        # B-roll trên một lane mới ở trên cùng, tắt tiếng, phủ kín khung.
        broll = sorted(edl.get("broll", []), key=lambda b: b["start"])
        if broll:
            track = self.edit({"op": "addTrack"})["createdId"]
            for b in broll:
                file = b["file"] if Path(b["file"]).is_absolute() else str((path.parent / b["file"]).resolve())
                bid, bdur = self.media_id(file)
                clip = self.edit({"op": "addClip", "mediaId": bid, "trackId": track, "start": b["start"]})["createdId"]
                skip = b.get("source_start", 0.0)
                cmds = [{"op": "trimClip", "clipId": clip, "edge": "start", "delta": skip, "ripple": True}] if skip > 0 else []
                cmds += [{"op": "trimClip", "clipId": clip, "edge": "end",
                          "delta": round(b["duration"] - ((bdur or b["duration"]) - skip), 4), "ripple": True},
                         {"op": "updateClip", "clipId": clip, "patch": {"muted": True}},
                         {"op": "frameClip", "clipId": clip, "framing": "fill"}]
                self.batch(cmds)

        # Chữ đặt sau cùng, mỗi loại một lane riêng ở trên cùng (trên cả B-roll), để khi
        # duyệt trong Concat dễ chọn cả lane phụ đề mà sửa hoặc đổi kiểu một lượt.
        vertical = h > w
        hook = (args.hook_text or edl.get("hook")) if args.hook else None
        cues = [] if args.no_captions else caption_cues(edl, vertical)
        if cues:
            lane_cap = self.edit({"op": "addTrack"})["createdId"]
            texts = []
            for i, c in enumerate(cues):
                end = cues[i + 1].start if i + 1 < len(cues) else c.end
                duration = round(max(min(max(c.end - c.start, 0.2), end - c.start), MIN_CLIP), 3)
                texts.append({"op": "addTextClip", "trackId": lane_cap, "start": round(c.start, 3),
                              "duration": duration, "style": caption_style(c.text, vertical),
                              "offsetY": 0.2 if vertical else 0.36})
            self.batch(texts)
        if hook:
            lane_hook = self.edit({"op": "addTrack"})["createdId"]
            self.edit({"op": "addTextClip", "trackId": lane_hook, "start": 0.0, "duration": args.hook_duration,
                       "style": hook_style(hook), "offsetY": -0.33 if vertical else -0.32})
        return self.verify(main, segments, lane)

    def verify(self, main: list[dict], segments: list[dict], lane: str) -> list[str]:
        """Đọc lại timeline: mỗi đoạn phải bắt đầu đúng chỗ trong nguồn, nối liền nhau."""
        ids = {c["id"] for c in main}
        clips = sorted((c for c in self.read()["timeline"]["clips"] if c["id"] in ids), key=lambda c: c["start"])
        problems, at = [], 0.0
        for i, (c, s) in enumerate(zip(clips, segments), 1):
            want = s["end"] - s["start"]
            if abs(c.get("sourceStart", 0) - s["start"]) > 0.05 or abs(c["duration"] - want) > 0.05 \
                    or abs(c["start"] - at) > 0.05 or c["track"] != lane:
                problems.append(f"đoạn {i}: nguồn {c.get('sourceStart')} dài {c['duration']} tại {c['start']} "
                                f"(mong đợi {s['start']:.3f}, {want:.3f}, {at:.3f})")
            at += want
        if len(clips) != len(segments):
            problems.append(f"có {len(clips)} clip, mong đợi {len(segments)}")
        return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("edl", nargs="+", help="Một hoặc nhiều EDL (chấp nhận *.edl.json)")
    parser.add_argument("--name", required=True, help="Tên project (thư mục sẽ được tạo)")
    parser.add_argument("--location", help="Thư mục chứa project (mặc định: thư mục của EDL đầu tiên)")
    parser.add_argument("--aspect", choices=list(ASPECTS), default="source")
    parser.add_argument("--fit", choices=["fill", "blur"], default="fill",
                        help="Khi đổi khung: fill = cắt cho đầy khung; blur = giữ cả hình, nền mờ")
    parser.add_argument("--focus", type=float, default=0.5, help="Vị trí cắt ngang khi fill: 0 trái, 0.5 giữa, 1 phải")
    parser.add_argument("--hook", action="store_true", help="Thêm chữ hook (trường 'hook' trong EDL)")
    parser.add_argument("--hook-text", help="Chữ hook dùng cho mọi tab, thay cho trường trong EDL")
    parser.add_argument("--hook-duration", type=float, default=2.5)
    parser.add_argument("--no-captions", action="store_true", help="Không thêm phụ đề")
    parser.add_argument("--fade", type=float, default=0.03, help="Fade âm thanh mỗi điểm cắt (giây)")
    parser.add_argument("--concat", help="Đường dẫn tới concat.exe / concat")
    parser.add_argument("--mode", choices=["headless", "window", "auto"], default="headless",
                        help="headless: tự chạy engine, không cần mở Concat (mặc định)")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in kế hoạch, không chạy Concat")
    args = parser.parse_args()
    if args.hook_text:
        args.hook = True

    paths = [Path(p) for pattern in args.edl for p in (sorted(glob.glob(pattern)) or [pattern])]
    edls = [(p, json.loads(p.read_text(encoding="utf-8"))) for p in paths]
    location = Path(args.location or paths[0].parent).resolve()
    project = str(location / args.name)
    if args.dry_run:
        print(f"Project: {project}")
        describe_plan(edls, args)
        return
    if Path(project).exists():
        raise SystemExit(f"{project} đã tồn tại — chọn --name khác để không ghi đè project cũ.")

    client = McpClient(find_concat(args.concat) + ["--mcp", args.mode])
    try:
        version = client.call("concat_version", {})
        mcp = version.get("mcp") if isinstance(version.get("mcp"), dict) else {}
        print(f"Concat {version.get('build') or version.get('version') or ''} — chế độ {mcp.get('mode', '?')}")
        first = edls[0][1]
        info = probe(first["source"])
        w, h = frame_for(args.aspect, info.width or 1920, info.height or 1080)
        num, den = rate_fraction(info.fps)
        client.call("project_create", {"location": str(location), "name": args.name,
                                       "video": {"width": w, "height": h, "rateNum": num, "rateDen": den}})
        builder = Builder(client, project)
        all_ok = True
        for n, (path, edl) in enumerate(edls, 1):
            problems = builder.build_timeline(n, path, edl, args, first=n == 1)
            total = sum(s["end"] - s["start"] for s in edl["segments"])
            status = "OK" if not problems else "CẦN KIỂM TRA"
            print(f"[{status}] tab {tab_name(n, path, edl)} — {fmt_ts(total, True)}")
            for p in problems:
                print(f"    ⚠ {p}")
            all_ok &= not problems
        client.call("project_close", {"path": project, "save": True})
    except ConcatError as e:
        print(f"Lỗi từ Concat: {e}", file=sys.stderr)
        print(client.log_tail(), file=sys.stderr)
        raise SystemExit(1)
    finally:
        client.close()
    print(f"\nĐã lưu project: {project}\nMở thư mục này trong Concat để duyệt, chỉnh và xuất từng tab.")
    if not all_ok:
        print("Có tab lệch so với EDL — xem các dòng ⚠ ở trên trước khi xuất.")


if __name__ == "__main__":
    main()
