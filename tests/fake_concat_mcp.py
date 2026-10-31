"""Server MCP giả lập Concat, chỉ dùng cho test của edl_to_concat.py.

Mô phỏng các công cụ và lệnh dựng mà script dùng, theo quy tắc đọc trong mã nguồn
Concat v0.2.8 (concat-project/src/commands): lane lưu từ dưới lên, cắt đầu kiểu ripple giữ
nguyên vị trí clip và kéo các clip sau, chữ "above" nằm trên mọi lane đang có hình...
Đây KHÔNG phải Concat: nó chỉ kiểm tra script gửi đúng lệnh theo đúng thứ tự.
Lệnh hoặc trường lạ bị từ chối để bắt lỗi chính tả.
"""
import copy
import json
import subprocess
import sys
from pathlib import Path

MIN = 1 / 60
FIELDS = {
    "addTimeline": set(), "batch": {"commands"},
    "setTimelineVideo": {"timelineId", "video"}, "renameTimeline": {"timelineId", "name"},
    "setTimelineBackground": {"timelineId", "background"},
    "addClipsInSequence": {"mediaIds", "start", "trackId", "ripple"},
    "trimClip": {"clipId", "edge", "delta", "ripple"}, "updateClip": {"clipId", "patch"},
    "frameClip": {"clipId", "framing", "at"}, "setClipTransform": {"clipId", "scale", "offsetX", "offsetY", "rotation"},
    "addTrack": {"bottom"}, "addClip": {"mediaId", "trackId", "start", "ripple"},
    "addTextClip": {"trackId", "above", "start", "style", "duration", "offsetY"},
}
PATCH = {"fadeIn", "fadeOut", "muted", "volume", "opacity"}


class Refused(Exception):
    pass


class Project:
    def __init__(self, path, video):
        self.path, self.counter, self.media, self.timelines = path, 0, [], []
        self.add_timeline(video)

    def mint(self, prefix):
        self.counter += 1
        return f"{prefix}{self.counter}"

    def add_timeline(self, video=None):
        tl = {"id": self.mint("tl"), "name": f"Timeline {len(self.timelines) + 1}",
              "video": video or {"width": 1920, "height": 1080, "rateNum": 30, "rateDen": 1},
              "tracks": [self.mint("t") for _ in range(4)], "clips": [], "background": None}
        self.timelines.append(tl)
        self.active = tl
        return tl["id"]

    def timeline(self, tid):
        tl = next((t for t in self.timelines if t["id"] == tid), None)
        if tl is None:
            raise Refused(f"no timeline {tid}")
        return tl

    def clip(self, cid):
        c = next((c for c in self.active["clips"] if c["id"] == cid), None)
        if c is None:
            raise Refused(f"no clip {cid}")
        return c

    def media_duration(self, mid):
        return next(m["duration"] for m in self.media if m["id"] == mid)

    def busy(self, track, start, end):
        return any(c["track"] == track and c["start"] < end - 1e-9 and start < c["start"] + c["duration"] - 1e-9
                   for c in self.active["clips"])

    def shift_after(self, clip, at, by):
        for c in self.active["clips"]:
            if c is not clip and c["track"] == clip["track"] and c["start"] >= at - 1e-6:
                c["start"] = round(c["start"] + by, 6)

    def apply(self, cmd):
        op = cmd.get("op")
        if op not in FIELDS:
            raise Refused(f"unknown op {op}")
        extra = set(cmd) - FIELDS[op] - {"op"}
        if extra:
            raise Refused(f"{op}: unknown fields {sorted(extra)}")
        tl = self.active
        if op == "batch":
            saved = copy.deepcopy((self.counter, self.media, self.timelines, self.timelines.index(self.active)))
            created = None
            try:
                for c in cmd["commands"]:
                    created = self.apply(c) or created
            except Refused:
                self.counter, self.media, self.timelines, idx = saved
                self.active = self.timelines[idx]
                raise
            return created
        if op == "addTimeline":
            return self.add_timeline()
        if op == "setTimelineVideo":
            self.timeline(cmd["timelineId"])["video"] = cmd["video"]
        elif op == "renameTimeline":
            self.timeline(cmd["timelineId"])["name"] = cmd["name"]
        elif op == "setTimelineBackground":
            self.timeline(cmd["timelineId"])["background"] = cmd["background"]
        elif op == "addClipsInSequence":
            total = sum(self.media_duration(m) for m in cmd["mediaIds"])
            track = cmd.get("trackId") or next(t for t in tl["tracks"] if not self.busy(t, cmd["start"], cmd["start"] + total))
            at, last = cmd["start"], None
            for m in cmd["mediaIds"]:
                last = self.mint("c")
                d = self.media_duration(m)
                tl["clips"].append({"id": last, "kind": "video", "track": track, "media": m, "start": at,
                                    "duration": d, "sourceStart": 0.0})
                at += d
            return last
        elif op == "trimClip":
            c, d = self.clip(cmd["clipId"]), cmd["delta"]
            if cmd["edge"] == "start":
                d = max(-c["sourceStart"], min(d, c["duration"] - MIN))
                end_before = c["start"] + c["duration"]
                c["sourceStart"] += d
                c["duration"] -= d
                if cmd.get("ripple"):
                    self.shift_after(c, end_before, -d)  # đầu clip giữ nguyên, các clip sau dồn lên
                else:
                    c["start"] += d
            elif cmd["edge"] == "end":
                room = (self.media_duration(c["media"]) - c["sourceStart"] - c["duration"]) if c.get("media") else 1e9
                d = max(-(c["duration"] - MIN), min(d, room))
                end_before = c["start"] + c["duration"]
                c["duration"] += d
                if cmd.get("ripple"):
                    self.shift_after(c, end_before, d)
            else:
                raise Refused("edge is start or end")
        elif op == "updateClip":
            bad = set(cmd["patch"]) - PATCH
            if bad:
                raise Refused(f"patch fields {sorted(bad)}")
            self.clip(cmd["clipId"]).update(cmd["patch"])
        elif op == "frameClip":
            if cmd["framing"] not in ("fit", "fill"):
                raise Refused("framing")
            self.clip(cmd["clipId"])["framing"] = cmd["framing"]
        elif op == "setClipTransform":
            self.clip(cmd["clipId"]).update({k: v for k, v in cmd.items() if k not in ("op", "clipId")})
        elif op == "addTrack":
            tid = self.mint("t")
            if cmd.get("bottom"):
                tl["tracks"].insert(0, tid)
            else:
                tl["tracks"].append(tid)
            return tid
        elif op == "addClip":
            if cmd["trackId"] not in tl["tracks"]:
                raise Refused("TrackGone")
            cid = self.mint("c")
            tl["clips"].append({"id": cid, "kind": "video", "track": cmd["trackId"], "media": cmd["mediaId"],
                                "start": cmd["start"], "duration": self.media_duration(cmd["mediaId"]), "sourceStart": 0.0})
            return cid
        elif op == "addTextClip":
            start, dur = cmd["start"], cmd.get("duration") or 4.0
            if cmd.get("trackId"):
                track = cmd["trackId"]
                if track not in tl["tracks"]:
                    raise Refused("TrackGone")
                if self.busy(track, start, start + dur):
                    # Concat dời chữ tới chỗ trống gần nhất; test coi đó là lỗi thời gian.
                    raise Refused(f"text at {start} overlaps on {track}")
            else:
                rows = [i + 1 for i, t in enumerate(tl["tracks"]) if self.busy(t, start, start + dur)]
                floor = max(rows, default=0)
                track = next((t for t in tl["tracks"][floor:] if not self.busy(t, start, start + dur)), None)
                if track is None:
                    track = self.mint("t")
                    tl["tracks"].append(track)
            cid = self.mint("c")
            tl["clips"].append({"id": cid, "kind": "text", "track": track, "start": start, "duration": dur,
                                "text": cmd["style"]["content"], "style": cmd["style"], "offsetY": cmd.get("offsetY", 0)})
            return cid
        return None

    def summary(self, created=None):
        tl = self.active
        clips = sorted(tl["clips"], key=lambda c: c["start"])
        out = {"project": {"width": tl["video"]["width"], "height": tl["video"]["height"]},
               "timeline": {"id": tl["id"], "name": tl["name"],
                            "duration": round(max((c["start"] + c["duration"] for c in clips), default=0), 3),
                            "tracks": [{"id": t, "index": i} for i, t in enumerate(tl["tracks"])],
                            "clips": [{**{k: (round(v, 4) if isinstance(v, float) else v) for k, v in c.items()},
                                       "end": round(c["start"] + c["duration"], 4)} for c in clips]},
               "media": self.media}
        if len(self.timelines) > 1:
            out["timelines"] = [{"id": t["id"], "name": t["name"]} for t in self.timelines]
        if created:
            out["createdId"] = created
        return out


def duration_of(file):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def main():
    projects = {}
    for raw in sys.stdin.buffer:
        msg = json.loads(raw)
        if "id" not in msg:
            continue
        if msg["method"] == "initialize":
            result = {"protocolVersion": msg["params"]["protocolVersion"], "capabilities": {"tools": {}},
                      "serverInfo": {"name": "fake-concat", "version": "0"}}
        else:
            name, a = msg["params"]["name"], msg["params"].get("arguments") or {}
            try:
                if name == "concat_version":
                    value = {"build": "fake", "mcp": {"mode": "headless"}}
                elif name == "project_create":
                    path = str(Path(a["location"]) / a["name"])
                    projects[path] = Project(path, a.get("video"))
                    value = projects[path].summary()
                else:
                    p = projects[a["path"]]
                    if name == "media_import":
                        if not any(m["path"] == a["file"] for m in p.media):
                            p.media.append({"id": p.mint("m"), "path": a["file"], "name": Path(a["file"]).name,
                                            "kind": "video", "duration": duration_of(a["file"])})
                        value = p.summary()
                    elif name == "edit_apply":
                        value = p.summary(p.apply(a["command"]))
                    elif name == "timeline_read":
                        value = p.summary()
                    elif name == "project_close":
                        Path(a["path"]).mkdir(parents=True, exist_ok=True)
                        (Path(a["path"]) / "fake-project.json").write_text(
                            json.dumps({"timelines": p.timelines, "media": p.media}, ensure_ascii=False, indent=1),
                            encoding="utf-8")
                        value = {"closed": True}
                    else:
                        raise Refused(f"unknown tool {name}")
                result = {"content": [{"type": "text", "text": json.dumps(value)}], "isError": False,
                          "structuredContent": value}
            except Refused as e:
                result = {"content": [{"type": "text", "text": f"{e} (code: refused)"}], "isError": True}
        sys.stdout.buffer.write((json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}) + "\n").encode())
        sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
