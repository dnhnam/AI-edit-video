"""Chèn B-roll: Claude chọn chỗ cần cảnh minh hoạ, rồi lấy cảnh từ Pexels hoặc từ file bạn có.

Ba lệnh con, dùng theo thứ tự:

    # 1) Claude đọc lời thoại của bản dựng và đề xuất các "ô" B-roll (thời điểm, độ dài,
    #    từ khoá tìm kiếm tiếng Anh, mô tả cảnh cần có)
    python broll.py plan shorts/short_01.edl.json -o shorts/short_01.edl.json

    # 2a) Tìm trên Pexels, Claude xem ảnh xem trước để chọn cảnh hợp nhất, tải về assets/broll/
    python broll.py pexels shorts/short_01.edl.json -o shorts/short_01.edl.json --orientation portrait

    # 2b) Hoặc thêm file tự có (tải từ Magnific, quay thêm...) vào một ô hoặc một thời điểm
    python broll.py add shorts/short_01.edl.json --file assets/broll/cafe.mp4 --slot 2 \
        --credit "Magnific (Freepik) #123456"

Sau đó render như bình thường: render_edl.py sẽ phủ B-roll lên hình, giữ tiếng gốc.
Cần biến môi trường PEXELS_API_KEY cho lệnh `pexels` (lấy miễn phí tại pexels.com/api).
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from pydantic import BaseModel, Field

from media import fmt_ts, load_transcript, remap_words, words_to_cues

PEXELS_API = os.environ.get("PEXELS_API_BASE", "https://api.pexels.com")
USER_AGENT = "AI-edit-video/1.0"

PLAN_SYSTEM = """Bạn là biên tập viên dựng phim. Bạn nhận lời thoại của một bản dựng, chia \
thành các dòng có ID dạng Cxxx kèm thời điểm trên timeline mới. Hãy chọn những chỗ nên phủ \
cảnh minh hoạ (B-roll) lên hình người nói, để: minh hoạ điều đang được nhắc tới, che vết cắt \
(jump cut), hoặc làm nhịp nhanh hơn.

Quy tắc:
- Không phủ B-roll trong 2 giây đầu (người xem cần thấy người nói và hook) và ở câu kết.
- Mỗi ô dài 1.5–5 giây; giữa hai ô nên có ít nhất 3 giây thấy lại người nói.
- `query_en`: 2–4 từ khoá tiếng Anh, cụ thể và quay được thật (ví dụ "barista pouring latte", \
không phải "success"). Tránh cảnh có logo, thương hiệu, người nổi tiếng.
- `description`: mô tả bằng tiếng Việt cảnh lý tưởng, để người duyệt và bước chọn cảnh dùng.
- Chất lượng hơn số lượng: chỉ đề xuất chỗ thật sự có lợi."""

PICK_SYSTEM = """Bạn chọn cảnh B-roll. Với mỗi ô, bạn thấy mô tả cảnh cần có và ảnh xem trước \
của vài ứng viên (nhãn "Ô N — ứng viên K"). Chọn ứng viên khớp nội dung nhất, hình rõ, không \
có chữ/logo nổi bật, hợp tông với video. Nếu không ứng viên nào đạt, trả candidate = 0."""


class Slot(BaseModel):
    cue_id: int = Field(description="Số ID của dòng nơi B-roll bắt đầu, ví dụ 7 cho C007")
    duration: float = Field(description="Độ dài B-roll, giây")
    query_en: str
    description: str
    reason: str


class BrollPlan(BaseModel):
    slots: list[Slot]


class Pick(BaseModel):
    slot: int
    candidate: int = Field(description="Số K của ứng viên được chọn, 0 nếu không có")
    reason: str


class Picks(BaseModel):
    picks: list[Pick]


def output_cues(edl: dict):
    words = load_transcript(edl["transcript"])["words"]
    return words_to_cues(remap_words(words, edl["segments"]))


def slots_from_plan(plan: BrollPlan, cues, total: float, skip_start: float = 2.0,
                    min_gap: float = 2.0) -> list[dict]:
    """Đổi ID dòng thành thời gian; bỏ ô sai, ô quá sớm, ô chồng nhau."""
    by_id = {c.index: c for c in cues}
    slots: list[dict] = []
    for s in sorted(plan.slots, key=lambda s: s.cue_id):
        cue = by_id.get(s.cue_id)
        if cue is None or cue.start < skip_start:
            continue
        start = round(cue.start, 3)
        duration = round(max(1.5, min(5.0, s.duration, total - start - 0.5)), 3)
        if duration < 1.5 or (slots and start < slots[-1]["start"] + slots[-1]["duration"] + min_gap):
            continue
        slots.append({"slot": len(slots) + 1, "start": start, "duration": duration, "query": s.query_en,
                      "description": s.description, "reason": s.reason})
    return slots


def cmd_plan(args) -> None:
    edl = json.loads(Path(args.edl).read_text(encoding="utf-8"))
    if not edl.get("transcript"):
        raise SystemExit("EDL cần trường 'transcript' để biết lời thoại.")
    cues = output_cues(edl)
    total = sum(s["end"] - s["start"] for s in edl["segments"])
    lines = "\n".join(f"C{c.index:03d} [{fmt_ts(c.start, True)}] {c.text}" for c in cues)
    user = (f"Bản dựng dài {fmt_ts(total, True)}.\n"
            + (f"<brief>\n{args.brief}\n</brief>\n" if args.brief else "")
            + f"<lines>\n{lines}\n</lines>")

    from claude_helper import ask_structured
    plan = ask_structured(PLAN_SYSTEM, user, BrollPlan, effort="medium")
    edl["broll_slots"] = slots_from_plan(plan, cues, total)
    Path(args.output).write_text(json.dumps(edl, ensure_ascii=False, indent=2), encoding="utf-8")
    for s in edl["broll_slots"]:
        print(f"Ô {s['slot']}: {fmt_ts(s['start'], True)} +{s['duration']:.1f}s  [{s['query']}]  {s['description']}")
    print(f"Đã ghi {len(edl['broll_slots'])} ô vào {args.output}")


# --- Pexels -----------------------------------------------------------------

def _get(url: str, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def pexels_search(query: str, orientation: str, api_key: str, per_page: int = 10) -> list[dict]:
    params = urllib.parse.urlencode({"query": query, "orientation": orientation,
                                     "size": "medium", "per_page": per_page})
    headers = {"Authorization": api_key}
    try:
        data = _get(f"{PEXELS_API}/v1/videos/search?{params}", headers)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        data = _get(f"{PEXELS_API}/videos/search?{params}", headers)  # đường dẫn cũ
    return json.loads(data).get("videos", [])


def best_file(video: dict, short_side: int = 1080) -> dict | None:
    """Bản mp4 có cạnh ngắn gần `short_side` nhất (không nhỏ hơn 720 nếu có thể)."""
    files = [f for f in video.get("video_files", [])
             if f.get("file_type") == "video/mp4" and f.get("width") and f.get("height")]
    if not files:
        return None
    big_enough = [f for f in files if min(f["width"], f["height"]) >= 720] or files
    return min(big_enough, key=lambda f: abs(min(f["width"], f["height"]) - short_side))


def thumbnail_block(url: str, tmp: Path, name: str) -> dict:
    from frames import image_block
    from media import run
    raw = tmp / f"{name}_raw.jpg"
    raw.write_bytes(_get(url))
    small = tmp / f"{name}.jpg"
    # Thu nhỏ trước khi gửi: đỡ token và không vượt giới hạn kích thước ảnh khi gửi nhiều ảnh.
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw),
         "-vf", "scale='min(384,iw)':-2", "-q:v", "4", str(small)])
    return image_block(small)


def cmd_pexels(args) -> None:
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        raise SystemExit("Thiếu PEXELS_API_KEY (đăng ký miễn phí tại https://www.pexels.com/api/).")
    edl_path = Path(args.edl)
    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    slots = edl.get("broll_slots") or []
    if not slots:
        raise SystemExit("EDL chưa có broll_slots — chạy `broll.py plan` trước.")
    assets = Path(args.assets)
    assets.mkdir(parents=True, exist_ok=True)

    candidates: dict[int, list[dict]] = {}
    for s in slots:
        videos = [v for v in pexels_search(s["query"], args.orientation, api_key)
                  if v.get("duration", 0) >= s["duration"] and best_file(v)]
        candidates[s["slot"]] = videos[: args.candidates]
        print(f"Ô {s['slot']} [{s['query']}]: {len(candidates[s['slot']])} ứng viên")

    choice: dict[int, dict] = {}
    if not any(candidates.values()):
        print("Không tìm thấy ứng viên nào — thử từ khoá khác trong broll_slots.")
    elif args.pick == "first":
        choice = {n: vids[0] for n, vids in candidates.items() if vids}
    else:
        with tempfile.TemporaryDirectory() as tmp:
            content: list[dict] = []
            for s in slots:
                if not candidates[s["slot"]]:
                    continue
                content.append({"type": "text", "text": f"Ô {s['slot']} — cần: {s['description']} "
                                                        f"(từ khoá: {s['query']}, {s['duration']:.1f}s)"})
                for k, v in enumerate(candidates[s["slot"]], 1):
                    content.append({"type": "text", "text": f"Ô {s['slot']} — ứng viên {k}"})
                    content.append(thumbnail_block(v["image"], Path(tmp), f"s{s['slot']}_{k}"))
            content.append({"type": "text", "text": "Chọn một ứng viên cho mỗi ô."})
            from claude_helper import ask_structured
            picks = ask_structured(PICK_SYSTEM, content, Picks, effort="low")
        for p in picks.picks:
            vids = candidates.get(p.slot, [])
            if 1 <= p.candidate <= len(vids):
                choice[p.slot] = vids[p.candidate - 1]
                print(f"Ô {p.slot}: chọn ứng viên {p.candidate} — {p.reason}")

    edl.setdefault("broll", [])
    credits = []
    for s in slots:
        video = choice.get(s["slot"])
        if not video:
            print(f"Ô {s['slot']}: không có cảnh phù hợp — bỏ trống.")
            continue
        f = best_file(video)
        dest = assets / f"pexels_{video['id']}_{f['width']}x{f['height']}.mp4"
        if not dest.exists():
            dest.write_bytes(_get(f["link"]))
        credit = f"Video by {video['user']['name']} on Pexels: {video['url']}"
        edl["broll"].append({"start": s["start"], "duration": s["duration"], "file": str(dest.resolve()),
                             "source_start": 0.0, "credit": credit, "slot": s["slot"]})
        credits.append(credit)
    Path(args.output).write_text(json.dumps(edl, ensure_ascii=False, indent=2), encoding="utf-8")
    credits_file = Path(args.output).with_suffix(".credits.txt")
    credits_file.write_text("Stock footage from Pexels (https://www.pexels.com)\n" + "\n".join(credits) + "\n",
                            encoding="utf-8")
    print(f"Đã thêm {len(credits)} B-roll vào {args.output}; ghi công tác giả: {credits_file}")


def cmd_add(args) -> None:
    edl = json.loads(Path(args.edl).read_text(encoding="utf-8"))
    if args.slot is not None:
        slot = next((s for s in edl.get("broll_slots", []) if s["slot"] == args.slot), None)
        if slot is None:
            raise SystemExit(f"Không có ô {args.slot} trong broll_slots.")
        start, duration = slot["start"], args.duration or slot["duration"]
    elif args.at is not None and args.duration:
        start, duration = args.at, args.duration
    else:
        raise SystemExit("Cần --slot, hoặc cả --at và --duration.")
    file = Path(args.file)
    if not file.exists():
        raise SystemExit(f"Không thấy file {file}")
    edl.setdefault("broll", []).append({"start": start, "duration": duration, "file": str(file.resolve()),
                                        "source_start": args.source_start, "credit": args.credit})
    Path(args.output or args.edl).write_text(json.dumps(edl, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Đã thêm B-roll {file.name} tại {fmt_ts(start, True)} (+{duration:.1f}s).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="Claude đề xuất các ô B-roll")
    p.add_argument("edl")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--brief", default="", help="Phong cách hình ảnh mong muốn, chủ đề...")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("pexels", help="Tìm, chọn và tải B-roll từ Pexels")
    p.add_argument("edl")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--orientation", choices=["portrait", "landscape", "square"], default="landscape",
                   help="portrait cho video dọc 9:16")
    p.add_argument("--candidates", type=int, default=4, help="Số ứng viên mỗi ô gửi cho Claude")
    p.add_argument("--pick", choices=["claude", "first"], default="claude",
                   help="claude = Claude xem ảnh để chọn; first = lấy kết quả đầu tiên")
    p.add_argument("--assets", default="assets/broll", help="Thư mục lưu file tải về")
    p.set_defaults(func=cmd_pexels)

    p = sub.add_parser("add", help="Thêm một file B-roll tự có (Magnific, quay thêm...)")
    p.add_argument("edl")
    p.add_argument("--file", required=True)
    p.add_argument("--slot", type=int, help="Đặt vào ô đã lên kế hoạch")
    p.add_argument("--at", type=float, help="Hoặc: thời điểm trên timeline mới (giây)")
    p.add_argument("--duration", type=float)
    p.add_argument("--source-start", type=float, default=0.0, help="Bắt đầu lấy từ giây thứ mấy của file B-roll")
    p.add_argument("--credit", default="", help="Ghi công nguồn/tác giả")
    p.add_argument("-o", "--output", help="Mặc định ghi đè EDL đầu vào")
    p.set_defaults(func=cmd_add)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
