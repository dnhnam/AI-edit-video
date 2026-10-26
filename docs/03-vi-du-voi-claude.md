# Phần 3 — Ví dụ thực hành với Claude

Các ví dụ đi từ dễ đến khó: chỉ cần chat trên claude.ai → Claude Code chạy ffmpeg → pipeline
qua Claude API → Claude điều khiển phần mềm dựng qua MCP.

| # | Ví dụ | Bề mặt | Cần cài đặt |
|---|---|---|---|
| 1 | Paper edit từ transcript | claude.ai | Không |
| 2 | Tiêu đề, mô tả, chương, ý tưởng Shorts | claude.ai | Không |
| 3 | Chọn thumbnail, soát khung hình | claude.ai (tải ảnh lên) | Không |
| 4 | Dựng bằng hội thoại trong thư mục dự án | Claude Code + ffmpeg | ffmpeg |
| 5 | Pipeline tự động: transcript → EDL → render → soát lỗi | Claude API (repo này) | Python, ffmpeg, API key |
| 6 | Shot log, chia chương bằng thị giác | Claude API (repo này) | Python, ffmpeg, API key |
| 7 | Motion graphics bằng code | Claude Code + Remotion | Node.js |
| 8 | Điều khiển DaVinci Resolve / Premiere / Adobe | Claude + MCP / connector | Resolve Studio 21.1, hoặc server cộng đồng |
| 9 | Dự án mã nguồn mở video-use | Claude Code | ffmpeg, key ElevenLabs |
| 10 | Concat: phần mềm dựng mã nguồn mở có MCP | Claude Code + Concat | Concat (Windows, macOS, Linux, Android) |

Các use case chi tiết trên Windows (Concat, video short, video dài ra nhiều short, B-roll từ
Pexels hoặc Magnific) nằm ở [Phần 4](04-use-case-windows-claude-code.md).

---

## Ví dụ 1 — Paper edit từ transcript (claude.ai)

**Tình huống:** bạn có buổi phỏng vấn 40 phút và cần một clip 2 phút.

1. Lấy transcript có mốc thời gian: dùng tính năng chép lời của CapCut, Premiere, Descript,
   YouTube Studio, hoặc `examples/transcribe.py`. Xuất ra file `.srt` hoặc `.txt`.
2. Tải file lên claude.ai (hoặc dán vào) cùng prompt:

```text
<transcript> (đính kèm file interview.srt) </transcript>

<brief>
Clip 2 phút cho LinkedIn từ buổi phỏng vấn CEO startup logistics.
Khán giả: quản lý chuỗi cung ứng. Mục tiêu: hiểu vì sao họ chuyển sang giao hàng
theo khung giờ. Hook: con số ấn tượng nhất mà CEO nhắc đến.
Bỏ: phần giới thiệu công ty, mọi đoạn nói về gọi vốn.
</brief>

Hãy làm paper edit:
1. Bảng các đoạn GIỮ theo thứ tự phát: mốc bắt đầu–kết thúc (lấy đúng từ transcript,
   không tự đặt), câu đầu và câu cuối của đoạn, lý do giữ.
2. Tổng thời lượng ước tính.
3. Những chỗ ý bị đứt hoặc cần chèn b-roll.
4. Hai phương án hook khác để tôi chọn.
Nếu một câu có nhiều lần nói, chọn lần trôi chảy nhất và ghi rõ đã bỏ lần nào.
```

**Kết quả mong đợi (minh hoạ):**

| # | Nguồn | Mở đầu → kết thúc | Lý do |
|---|---|---|---|
| 1 | 12:04–12:15 | "Chúng tôi giảm 38% chuyến giao thất bại…" → "…chỉ sau 3 tháng." | Hook: con số cụ thể |
| 2 | 03:40–04:22 | "Trước đây tài xế…" → "…khách không có nhà." | Nêu vấn đề |
| … | … | … | … |

**Lưu ý:** đối chiếu lại mốc thời gian trên timeline. Khi làm trên claude.ai, Claude vẫn có
thể chép sai mốc, nên ví dụ 5 dùng cách "chọn ID" để loại hẳn lỗi này.

---

## Ví dụ 2 — Metadata và ý tưởng clip ngắn (claude.ai)

```text
Dựa trên transcript đính kèm (video YouTube 18 phút về nấu phở tại nhà):
1. 5 tiêu đề ≤ 60 ký tự, mỗi tiêu đề theo một góc khác nhau (tò mò, lợi ích, con số,
   sai lầm, câu chuyện). Không giật tít sai sự thật.
2. Mô tả 150 từ, có 3 dòng đầu hấp dẫn và lời kêu gọi đăng ký.
3. Chương YouTube: dòng đầu là 00:00, mỗi chương ≥ 10 giây, tên chương ≤ 40 ký tự.
4. 3 ý tưởng Shorts ≤ 45 giây: mốc nguồn, câu hook mở đầu, câu chữ trên màn hình.
```

Đây là việc Claude làm nhanh và tốt nhất: văn bản đầu vào, văn bản đầu ra, người duyệt
trong vài phút.

---

## Ví dụ 3 — Chọn thumbnail và soát khung hình (claude.ai)

Trích 10–20 khung ứng viên (claude.ai nhận tối đa 20 ảnh mỗi lượt):

```bash
ffmpeg -i vlog.mp4 -vf "select='gt(scene,0.3)',scale=1280:-2" -fps_mode vfr -frames:v 20 cand_%02d.jpg
# ffmpeg < 5.1: thay -fps_mode vfr bằng -vsync vfr
```

Tải lên rồi hỏi:

```text
Đây là 20 khung hình ứng viên cho thumbnail video "Một ngày ở Hội An".
Chấm điểm 1–5 theo: chủ thể rõ, cảm xúc, chỗ trống để đặt chữ, đọc được ở kích thước nhỏ.
Chọn 3 khung tốt nhất, gợi ý vị trí và nội dung chữ (≤ 4 từ) cho từng khung.
Chỉ ra khung nào bị mờ, lệch nét hoặc cháy sáng.
```

---

## Ví dụ 4 — Claude Code + ffmpeg: dựng bằng hội thoại

**Chuẩn bị:**

```bash
mkdir -p my-video/{raw,work,out,assets} && cd my-video
cp ~/Downloads/*.mp4 raw/
cp path/to/AI-edit-video/templates/CLAUDE.md .   # sửa phần "Dự án này"
claude
```

File [`templates/CLAUDE.md`](../templates/CLAUDE.md) đặt luật chơi: không đụng vào `raw/`,
kế hoạch trước rồi mới render, preview trước, tự kiểm tra sau mỗi lần render.

**Một buổi làm việc mẫu** (bạn gõ, Claude Code tự chạy lệnh và báo lại):

| Bạn nói | Claude Code thường làm |
|---|---|
| "Kiểm tra các file trong raw/ và tóm tắt." | Chạy `ffprobe` từng file: độ dài, độ phân giải, fps, track âm thanh |
| "Tìm các khoảng lặng > 0,7 giây trong raw/talk.mp4." | `ffmpeg -i raw/talk.mp4 -af silencedetect=noise=-35dB:d=0.7 -f null -`, rồi tổng hợp danh sách |
| "Bỏ các khoảng lặng đó, cho tôi xem kế hoạch trước." | Viết EDL vào `work/`, báo tổng thời lượng trước/sau, chờ bạn đồng ý |
| "OK, render preview." | Render 540p vào `out/talk_v01_preview.mp4`, liệt kê các điểm cắt để bạn nghe |
| "Làm bản dọc 9:16 cho TikTok, đốt phụ đề." | `-vf "crop=ih*9/16:ih,scale=1080:1920,subtitles=work/talk.srt"` |
| "Chuẩn hoá âm lượng cho YouTube." | `-af loudnorm=I=-14:TP=-1.5:LRA=11 -c:v copy` |
| "Ghi lại những gì đã chốt." | Cập nhật `project.md` |

**Vì sao cách này hiệu quả:** bạn nói bằng ngôn ngữ tự nhiên; Claude biết tham số ffmpeg,
tự chạy, đọc lỗi và sửa. Mọi lệnh đều hiển thị để bạn duyệt trước khi chạy.

---

## Ví dụ 5 — Pipeline qua Claude API (mã nguồn trong `examples/`)

```bash
cd examples
pip install -r requirements.txt faster-whisper
export ANTHROPIC_API_KEY=...        # hoặc: ant auth login

# 1. Chép lời (chạy local, footage không rời máy)
python transcribe.py ../raw/interview.mp4 -o ../work/interview.transcript.json \
    --language vi --prompt "Claude, Anthropic, DaVinci Resolve"

# 2. Claude lên kế hoạch cắt theo brief (xem trước dữ liệu gửi đi: --dry-run)
python plan_cuts.py ../work/interview.transcript.json -o ../work/interview.edl.json \
    --brief "$(cat ../brief.md)"

# 3. Người duyệt paper edit in ra màn hình, sửa ../work/interview.edl.json nếu cần

# 4. Render preview + phụ đề khớp timeline mới
python render_edl.py ../work/interview.edl.json -o ../out/v01_preview.mp4 --preview --burn-subs

# 5. Claude soát khung trước/sau mỗi điểm cắt
python review_cuts.py ../out/v01_preview.mp4 ../work/interview.edl.json -o ../work/review.json

# 6. Bản cuối và phụ đề tiếng Anh
python render_edl.py ../work/interview.edl.json -o ../out/v01_final.mp4
python translate_srt.py ../out/v01_final.srt -o ../out/v01_final.en.srt --to English
```

**Ba lựa chọn thiết kế đáng chú ý:**

**(a) Transcript được nén thành các cụm có ID**, mỗi dòng một cụm, có đánh dấu khoảng lặng
dài:

```text
P0041 [03:12.40–03:15.10] Hồi đó tụi mình ừm, tụi mình
P0042 [03:15.90–03:21.30] Hồi đó tụi mình chỉ có ba người và một chiếc xe máy.
P0043 [03:24.80–03:29.05] (+3.5s lặng) Tháng đầu tiên lỗ hơn trăm triệu.
```

**(b) Claude trả về JSON theo schema, chỉ gồm ID**, không gồm thời gian:

```python
class KeepRange(BaseModel):
    first_id: int
    last_id: int
    reason: str

class CutPlan(BaseModel):
    title: str
    summary: str
    keep: list[KeepRange]
    warnings: list[str]

plan = ask_structured(SYSTEM, user_text, CutPlan, effort="high")
```

Hàm `ask_structured` ([`claude_helper.py`](../examples/claude_helper.py)) gọi Claude Opus 5.5
với structured outputs, streaming, và bật fallback phía server:

```python
with client.beta.messages.stream(
    model="claude-opus-5-5",
    max_tokens=32000,
    system=system,
    messages=[{"role": "user", "content": content}],
    output_format=CutPlan,                 # Pydantic → JSON Schema
    output_config={"effort": "high"},
    betas=["server-side-fallback-2026-07-01"],
    fallbacks="default",
) as stream:
    plan = stream.get_final_message().parsed_output
```

**(c) Code đổi ID thành thời gian** (`plan_to_segments`): kiểm tra ID có tồn tại không, gộp
các dải liền nhau, chừa 80 ms trước và 150 ms sau lời nói nhưng không lấn quá nửa khoảng
lặng sang cụm bị bỏ. Khi render, mỗi điểm cắt được fade âm thanh 30 ms để tránh tiếng "bụp".

Kết quả in ra là một paper edit dễ đọc:

```text
# Từ hai bàn tay trắng
Mở bằng con số lỗ tháng đầu, rồi kể lại hành trình theo thứ tự thời gian.

 1. [00:00] nguồn 03:24.72–03:29.20 — hook: con số gây sốc
    “Tháng đầu tiên lỗ hơn trăm triệu.”
 2. [00:04] nguồn 03:15.82–03:21.45 — giữ lần nói trôi chảy (bỏ P0041)
    “Hồi đó tụi mình chỉ có ba người và một chiếc xe máy.”
 ...
⚠ P0057: "Vi-ê-tê-lơ" có thể là tên riêng bị ASR viết sai
```

---

## Ví dụ 6 — Shot log và chương bằng thị giác

```bash
python shot_log.py ../raw/vlog.mp4 -o ../work/vlog.shots.json --scenes \
    --transcript ../work/vlog.transcript.json \
    --brief "Tìm cảnh mở đầu hấp dẫn, cảnh dùng làm b-roll, và cảnh hỏng (mờ, tối, rung)"
```

- Trích khung tại các điểm chuyển cảnh (`--scenes`) hoặc đều đặn (`--every 5`), thu nhỏ còn
  cạnh dài 512 px (khoảng 209 token mỗi khung 16:9), mỗi khung có nhãn `Khung N — mm:ss`.
- Script in ước tính token **trước khi gọi API** (`--dry-run` để chỉ xem ước tính).
- Prompt hệ thống nhắc Claude rằng khung hình là mẫu thưa, không được đoán sự kiện giữa hai
  khung và không nêu danh tính người thật.
- Đầu ra: `vlog.shots.json` và `vlog.shots.md`, gồm bảng cảnh quay (loại cảnh, mô tả, lỗi
  kỹ thuật, dùng làm gì, điểm chất lượng), chương YouTube đã chuẩn hoá (bắt đầu 00:00, mỗi
  chương ≥ 10 giây) và thumbnail ứng viên.

---

## Ví dụ 7 — Motion graphics bằng Remotion + Claude Code

Remotion biến video thành code React, nên Claude Code có thể viết, xem trước và render
chính xác. Phù hợp cho video giải thích, biểu đồ động, lower-third, intro/outro, phụ đề động.

```bash
npx create-video@latest my-explainer && cd my-explainer
npx skills add remotion-dev/skills      # bộ Agent Skills chính thức của Remotion
claude
```

Bộ skills cung cấp `/remotion-best-practices`, `/remotion-create`, `/remotion-captions`,
`/remotion-render`, `/remotion-studio`... để Claude viết đúng mô hình "theo frame" của
Remotion.

Prompt mẫu:

```text
Tạo composition "Revenue2026" 1920x1080, 30fps, dài 12 giây:
- 0–2s: tiêu đề "Doanh thu 2026" trượt lên, font Be Vietnam Pro, nền #0F172A.
- 2–10s: biểu đồ cột 4 quý (120, 180, 150, 240 tỷ), các cột mọc lần lượt kèm số đếm tăng dần.
- 10–12s: logo ở assets/logo.svg mờ dần vào.
Mở Studio để tôi xem; khi tôi đồng ý thì render ra out/revenue.mp4.
```

**Lưu ý:** Remotion mạnh cho đồ hoạ dựng từ dữ liệu, không thay được phần mềm dựng cho
footage quay thật. Kết hợp được: render lower-third hoặc biểu đồ bằng Remotion rồi chồng
lên video dựng bằng ffmpeg hay NLE.

---

## Ví dụ 8 — Claude điều khiển phần mềm dựng qua MCP

### DaVinci Resolve 21.1 Studio (MCP tích hợp sẵn)
Thiết lập: *File > Setup AI Assistants*, rồi kết nối Claude Desktop hoặc Claude Code. Bản
Resolve miễn phí không dùng được MCP gốc; một số server cộng đồng
(`samuelgursky/davinci-resolve-mcp`, `hiteshK03/davinci-resolve-mcp`) đi qua script cầu nối
chạy bên trong Resolve.

Prompt mẫu:

```text
Trong bin "Interview_Day2", tạo timeline mới "Highlight_3min":
- chỉ lấy các clip có người nói, bỏ clip ngắn hơn 3 giây;
- đặt marker đỏ ở những đoạn âm thanh bị rè hoặc quá nhỏ;
- thêm phụ đề tự động tiếng Việt;
- đưa vào render queue hai bản: YouTube 1080p và 9:16 cho Reels.
Trước khi render, liệt kê những gì bạn đã làm để tôi kiểm tra.
```

### Premiere Pro, After Effects
Không có MCP chính thức cho Claude; AI Assistant trong Premiere dùng model của Adobe. Có
server cộng đồng như `hetpatel-11/Adobe_Premiere_Pro_MCP` (cắt, trim, ripple delete, phụ đề
từ SRT, xuất qua Media Encoder; cần mở panel cầu nối, telemetry bật mặc định) và
`Dakkshin/after-effects-mcp`. Hãy kiểm tra mã nguồn trước khi cài.

### Connector "Adobe for creativity"
Bật trong phần Connectors của Claude. Phù hợp với các việc theo kết quả: "đổi video này
sang 9:16 cho YouTube Shorts", "cắt nhanh bản 15 giây". Cần tài khoản Adobe.

### ffmpeg qua MCP
Nếu dùng Claude Desktop (không có shell như Claude Code), server như `kevinwatt/ffmpeg-mcp-lite`
cho Claude cắt, đốt phụ đề và xuất file trên máy bạn.

**Nguyên tắc chung với MCP:** luôn làm trên bản sao project, yêu cầu Claude liệt kê thay đổi
trước khi render, và chỉ cài server từ nguồn bạn tin tưởng.

---

## Ví dụ 9 — video-use (mã nguồn mở, MIT)

[browser-use/video-use](https://github.com/browser-use/video-use) là bộ công cụ cho Claude Code:

1. Chép lời bằng ElevenLabs Scribe (mốc thời gian từng từ, người nói, sự kiện âm thanh).
2. Nén transcript thành file khoảng 12 KB, đây là "tầm nhìn" chính của agent.
3. Claude lập kế hoạch, **hỏi ý kiến bạn trước khi cắt**, rồi viết EDL.
4. Render: bỏ ậm ừ và khoảng chết, chỉnh màu, fade âm 30 ms, đốt phụ đề, thêm overlay động
   (Remotion, Manim, PIL...).
5. Tự đánh giá tại từng điểm cắt bằng ảnh ghép filmstrip + dạng sóng; tự sửa tối đa 3 lần
   rồi mới đưa bạn xem.

Repo này dùng lại cùng triết lý "văn bản trước, hình ảnh khi cần" và "hỏi → xác nhận → làm
→ tự kiểm tra", nhưng viết gọn để dễ đọc và sửa.

---

## Ví dụ 10 — Concat: phần mềm dựng mã nguồn mở có MCP

[Concat](https://github.com/jub0t/concat) là phần mềm dựng video mã nguồn mở thay thế
CapCut, viết bằng Rust, chạy trên Windows, macOS, Linux và Android (giấy phép AGPL-3.0, bản
beta 0.2.x tại thời điểm viết). Mọi thứ chạy trên máy: phụ đề tự động bằng Whisper, đọc chữ
thành giọng nói, tách nền, keyframe, khoảng 100 hiệu ứng, xuất tối đa 4K (H.264, HEVC, AV1),
không watermark, không cần tài khoản.

Điểm khiến Concat hợp với pipeline của repo này: **MCP server có sẵn** (`concat --mcp`).
Claude Code điều khiển được Concat bằng chính các lệnh dựng mà giao diện dùng. So với MCP của
DaVinci Resolve 21.1 (chỉ có ở bản Studio trả phí), Concat miễn phí và mở mã.

**Cài cho Claude Code trên Windows** (PowerShell):

```powershell
claude mcp add --scope project concat -- "$env:LOCALAPPDATA\Programs\Concat\concat.exe" --mcp
# Cài bằng .msi hoặc cho mọi người: "C:\Program Files\Concat\concat.exe"
```

**Hai chế độ chạy:**

- `headless` (mặc định khi Concat đóng): MCP tự chạy engine của Concat, không cần mở cửa sổ.
- `window`: bật **Settings > Automation > Scripts and apps** trong Concat; agent đi qua cửa
  sổ đang mở và không thể ghi đè project bạn đang xem.

**Các nhóm công cụ** (theo tài liệu `docs/MCP.md` của Concat):

| Nhóm | Công cụ |
|---|---|
| Project | `project_create`, `project_open`, `project_save`, `project_close`, `project_set_video` |
| Đọc | `timeline_read` (gọn: lane, clip, id), `project_get` (đầy đủ), `concat_version` |
| Media | `media_probe`, `media_import` |
| Dựng | `clip_add`, `clips_add_sequence`, `clip_trim`, `clips_split`, `clips_move`, `clips_remove`, `clip_update`, `clip_transform`, `clip_speed`, `clip_frame`, `track_add` |
| Hình ảnh | `clip_mask`, `clip_stabilize`, `timeline_background` |
| Chữ | `title_add`, `captions_add` (danh sách `{start, end, text}`) |
| Keyframe, hiệu ứng | `keyframe_set`, `keyframe_clear`, `effects_list`, `effect_layer_add`, `effect_key_set` |
| Khác | `edit_apply` (mọi lệnh dựng, hoặc một batch thành một bước undo), `edit_undo`, `edit_redo`, `template_list`, `template_instantiate` |
| Xuất | `export_start`, `export_status`, `export_wait`, `export_cancel` |
| Nhìn | `preview_frame` (khung hình đã ghép hoàn chỉnh, kèm chữ và hiệu ứng) |

**Vị trí trong pipeline:**

| Bước | Dùng gì |
|---|---|
| Chép lời có mốc thời gian từng từ | `transcribe.py`. Whisper của Concat chỉ tạo phụ đề trong giao diện và không gọi được qua MCP |
| Claude lên kế hoạch cắt | `plan_cuts.py` / `plan_shorts.py` |
| Dựng thành timeline sửa được | **Concat** (`clip_add` + `clip_trim` cho từng đoạn của EDL) |
| Phụ đề | File `.srt` từ `render_edl.py` → `captions_add`, thành chữ sửa được trên timeline |
| Soát điểm cắt, che jump cut | `preview_frame`, rồi `clip_transform` / `keyframe_set` |
| Hoàn thiện (nhạc, màu, chuyển cảnh) | Bạn, trên giao diện Concat |

**Hạn chế:**

- Còn beta: API có thể đổi giữa các phiên bản.
- Không có lệnh "lấy đoạn từ giây A đến giây B": mỗi đoạn cần `clip_add` rồi `clip_trim`, nên
  EDL nhiều đoạn sẽ tốn nhiều lượt gọi hơn một lệnh ffmpeg.
- Agent chỉ sửa project của chính nó, không sửa project đang mở trên cửa sổ.
- Mặc định chỉ ghi file trong thư mục người dùng (đặt `CONCAT_MCP_ROOTS` để mở rộng).

Hướng dẫn từng bước: [Phần 4 — Use case 1](04-use-case-windows-claude-code.md#use-case-1--dựng-với-concat).

---

## Prompt kém và prompt tốt

| Kém | Tốt hơn | Vì sao |
|---|---|---|
| "Cắt video này cho hay." | "Bản 60 giây cho TikTok, hook là câu về khoản nợ 2 tỷ, giữ 3 bài học theo thứ tự, mỗi đoạn ≤ 8 giây." | Có mục tiêu, độ dài, cấu trúc, tiêu chí |
| "Xem video và tìm cảnh đẹp." | "Đây là 60 khung (mỗi 5 giây, có nhãn thời gian). Chọn 5 khung làm b-roll cho đoạn nói về ẩm thực; bỏ khung mờ hoặc tối." | Claude không xem được video; nói rõ dữ liệu là gì |
| "Cho tôi timestamp các đoạn hay." | "Chỉ dùng ID cụm trong transcript; trả về JSON gồm first_id, last_id, reason." | Tránh timestamp bịa |
| "Làm lại đi." | "Đoạn 3 dài quá, chỉ giữ câu cuối; đổi đoạn 5 lên đầu làm hook." | Phản hồi cụ thể, sửa đúng chỗ |
| "Người này là ai trong video?" | "Đánh dấu các khung có người dẫn áo xanh xuất hiện." | Claude không nhận diện danh tính người thật |
