# Phần 4 — Use case trên Windows với Claude Code

Bốn tình huống thực tế, chạy trên **Windows 10/11** với **Claude Code** (gõ `claude` trong
PowerShell):

| # | Use case | Công cụ chính |
|---|---|---|
| 1 | [Dựng với Concat](#use-case-1--dựng-với-concat) | Claude Code + Concat (MCP) |
| 2 | [Dựng một video short](#use-case-2--dựng-một-video-short-1560-giây) | `plan_cuts.py`, `render_edl.py --aspect 9:16` |
| 3 | [Từ video dài ra nhiều short](#use-case-3--từ-video-dài-ra-nhiều-short) | `plan_shorts.py` + vòng lặp render |
| 4 | [B-roll từ Pexels hoặc Magnific](#use-case-4--b-roll-từ-pexels-hoặc-magnific) | `broll.py`, MCP Magnific |

Bạn có thể tự gõ lệnh, hoặc **giao cho Claude Code chạy** bằng các prompt mẫu trong từng mục.
Cách thứ hai là cách nên dùng: Claude Code chạy lệnh, đọc kết quả, sửa lỗi và dừng lại chờ
bạn duyệt ở mỗi bước quan trọng.

---

## 0. Chuẩn bị một lần

### 0.1. Cài phần mềm (PowerShell)

```powershell
# Claude Code (cần gói Pro, Max, Team, Enterprise hoặc tài khoản Console)
irm https://claude.ai/install.ps1 | iex          # hoặc: winget install Anthropic.ClaudeCode
winget install Git.Git                           # khuyên dùng: Claude Code dùng Git Bash làm shell
winget install Gyan.FFmpeg                       # ffmpeg + ffprobe
winget install Python.Python.3.12
# Đóng PowerShell, mở lại, rồi kiểm tra:
claude --version; ffmpeg -version; py --version
```

**Concat** (cho use case 1): tải bản Windows (setup hoặc `.msi`) từ
[trang chủ](https://concatenate.pages.dev/#download) hoặc
[GitHub Releases](https://github.com/jub0t/Concat/releases). Bản Windows chưa được ký số: nếu
SmartScreen chặn, chọn **More info → Run anyway**. Đường dẫn sau khi cài:

- Cài cho riêng bạn: `%LOCALAPPDATA%\Programs\Concat\concat.exe`
- Cài cho mọi người hoặc bằng `.msi`: `C:\Program Files\Concat\concat.exe`

### 0.2. Lấy repo ví dụ và cài thư viện Python

```powershell
cd $HOME
git clone https://github.com/dnhnam/AI-edit-video
cd AI-edit-video\examples
py -m venv .venv
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned   # chỉ cần nếu Activate.ps1 bị chặn
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt faster-whisper
```

### 0.3. Khoá API

```powershell
setx PYTHONUTF8 1                       # tránh lỗi in tiếng Việt khi ghi log ra file
setx ANTHROPIC_API_KEY "sk-ant-..."     # cho các script gọi Claude API (console.anthropic.com)
setx PEXELS_API_KEY "..."               # miễn phí tại pexels.com/api (use case 4)
```

Mở terminal mới sau `setx`. **Lưu ý:** khi thấy `ANTHROPIC_API_KEY`, Claude Code sẽ hỏi có
dùng key này không. Chọn **No** nếu muốn Claude Code tính vào gói Pro/Max của bạn; các script
Python do Claude Code chạy vẫn đọc được key và tính phí theo API.

### 0.4. Tạo thư mục dự án và nối MCP

Đặt dự án **bên trong thư mục người dùng** (`C:\Users\<bạn>\...`), vì MCP của Concat mặc định
chỉ ghi file ở đó. Muốn dùng ổ khác thì đặt biến `CONCAT_MCP_ROOTS` (các đường dẫn ngăn cách
bằng `;`).

```powershell
mkdir $HOME\Videos\du-an-1\raw, $HOME\Videos\du-an-1\work, $HOME\Videos\du-an-1\out, $HOME\Videos\du-an-1\assets
cd $HOME\Videos\du-an-1
copy $HOME\AI-edit-video\templates\CLAUDE.md .         # sửa phần "Dự án này"

# MCP cho dự án này (ghi vào .mcp.json)
claude mcp add --scope project concat -- "$env:LOCALAPPDATA\Programs\Concat\concat.exe" --mcp
claude mcp add --scope project --transport http magnific https://mcp.magnific.com   # nếu có gói Magnific

claude
```

Trong Claude Code, gõ `/mcp` để xem trạng thái các server và đăng nhập Magnific qua trình
duyệt. Claude Code sẽ hỏi bạn duyệt các server khai báo trong `.mcp.json` ở lần đầu.

Nếu lệnh `claude mcp add` báo lỗi tham số (thường gặp khi `claude` được cài bằng npm, vì
PowerShell nuốt mất dấu `--`), hãy tạo file `.mcp.json` ở gốc thư mục dự án:

```json
{
  "mcpServers": {
    "concat": {
      "command": "C:\\Users\\<bạn>\\AppData\\Local\\Programs\\Concat\\concat.exe",
      "args": ["--mcp"]
    },
    "magnific": { "type": "http", "url": "https://mcp.magnific.com" }
  }
}
```

Thêm vào cuối `CLAUDE.md` của dự án để Claude Code biết dùng script nào:

```markdown
## Công cụ
- Python venv: C:\Users\<bạn>\AI-edit-video\examples\.venv\Scripts\python.exe
- Script: C:\Users\<bạn>\AI-edit-video\examples\ (transcribe, plan_cuts, plan_shorts,
  render_edl, review_cuts, broll, translate_srt, shot_log). Đọc --help trước khi dùng.
- MCP: concat (dựng trên timeline), magnific (stock, video AI).
```

---

## Use case 1 — Dựng với Concat

**Tình huống:** buổi nói chuyện 8 phút quay ngang → bản YouTube khoảng 3 phút. AI làm bản
dựng thô **trên timeline Concat**, sau đó bạn mở Concat để chỉnh tiếp bằng chuột: nhạc, chuyển
cảnh, màu, chữ.

**Vì sao dùng Concat thay vì chỉ render bằng ffmpeg:** kết quả là một **project sửa được**
chứ không phải file video đã "đóng băng". Phụ đề là các đối tượng chữ trên timeline (đổi
font, sửa chính tả dễ dàng), các đoạn cắt vẫn kéo dài hoặc rút ngắn được, và có sẵn hiệu ứng,
chống rung, keyframe. Tất cả chạy trên máy, miễn phí.

### Bước 1 — Kế hoạch cắt (như các phần trước)

Prompt cho Claude Code:

```text
Video nguồn: raw\talk.mp4. Brief: bản YouTube khoảng 3 phút cho chủ shop online, giữ phần
3 mẹo chụp ảnh sản phẩm, bỏ ậm ừ, câu nói hỏng và đoạn quảng cáo cuối.
1. Chạy transcribe.py (tiếng Việt, gợi ý tên riêng: "Shopee, Lazada, Canon").
2. Chạy plan_cuts.py với brief trên, cho tôi xem paper edit và dừng lại chờ tôi duyệt.
3. Sau khi tôi đồng ý, chạy render_edl.py --preview để có bản xem nhanh và file .srt khớp
   timeline mới.
```

### Bước 2 — Dựng project Concat từ EDL

```text
Dùng MCP concat:
1. Tạo project "talk_v01" trong thư mục work\, khung 1920x1080, 30 fps.
2. Import raw\talk.mp4.
3. Với từng đoạn trong work\talk.edl.json, theo đúng thứ tự: đặt clip nối tiếp nhau trên
   cùng một lane, cắt đầu/cuối cho khớp start/end của đoạn (clip_add rồi clip_trim), không
   để khoảng trống. Thêm fade âm 0.03 giây ở hai đầu mỗi clip.
4. Đọc out\talk_v01_preview.srt và thêm toàn bộ phụ đề bằng captions_add.
5. Gọi timeline_read để kiểm tra tổng thời lượng khớp với estimated_duration trong EDL.
6. Dùng preview_frame xem khung hình ngay trước và sau từng điểm cắt; điểm nào là jump cut
   rõ thì phóng to clip phía sau lên 112% bằng clip_transform.
7. project_save, rồi báo tôi đường dẫn project và danh sách điểm cắt cần nghe lại.
```

Claude Code sẽ tự gọi `project_create`, `media_import`, `clip_add`, `clip_trim`,
`captions_add`, `timeline_read`, `preview_frame`, `clip_transform`, `project_save`. Bạn chỉ
cần duyệt khi được hỏi.

### Bước 3 — Bạn hoàn thiện trong Concat

Mở Concat → mở thư mục project vừa tạo → chỉnh nhịp, thêm nhạc, chuyển cảnh, màu sắc.

- Khi project đang mở trên cửa sổ, agent không được ghi vào project đó (Concat khoá thư mục
  bằng `concat.lock`). Muốn Claude sửa tiếp: đóng project trong Concat, hoặc bật **Settings >
  Automation > Scripts and apps** để agent đi qua cửa sổ (chế độ `window`).
- Agent chỉ sửa project của chính nó; chưa có chế độ "sửa trực tiếp project bạn đang xem".

### Bước 4 — Xuất file

Xuất trong giao diện Concat, hoặc nhờ Claude:

```text
Mở project work\talk_v01, export ra out\talk_v01_final.mp4, H.264, crf 18, rồi chờ xong
(export_wait) và báo dung lượng file.
```

### Các lệnh bằng lời hay dùng với Concat

| Bạn nói | Công cụ MCP Claude dùng |
|---|---|
| "Bỏ đoạn 01:12–01:18, dồn phần sau lên" | `clips_split`, `clips_remove` (ripple) |
| "Chống rung clip thứ 3, giữ chuyển động máy chậm" | `clip_stabilize` |
| "Zoom chậm từ 100% lên 110% trong clip mở đầu" | `keyframe_set` (scale) |
| "Thêm tiêu đề 'Mẹo số 1' ở giây 00:35 trong 3 giây" | `title_add` |
| "Làm bản dọc 9:16 với nền mờ phía sau" | `project_set_video`, `timeline_background` (blur), `clip_frame` |
| "Có những hiệu ứng chuyển cảnh nào?" | `effects_list` |

---

## Use case 2 — Dựng một video short (15–60 giây)

**Tình huống:** quay bằng điện thoại 3 phút review một sản phẩm → một short 45 giây cho
TikTok / Reels / YouTube Shorts.

### Bằng một prompt cho Claude Code

```text
Làm một short dọc từ raw\review.mp4.
Brief: 40–45 giây, TikTok, khán giả 20–30 tuổi. Hook: câu "đừng mua trước khi xem cái này".
Giữ: 3 điểm mạnh và 1 điểm yếu của sản phẩm. Bỏ: phần mở hộp dài, ậm ừ, khoảng lặng.
Nhịp nhanh, mỗi đoạn ≤ 6 giây.
Quy trình:
1. transcribe.py → plan_cuts.py với brief trên → cho tôi xem paper edit, chờ duyệt.
2. Đặt trường "hook" trong EDL thành câu chữ ngắn ≤ 6 từ.
3. render_edl.py --aspect 9:16 --burn-subs --short-captions --hook --preview.
   Nếu người nói lệch khỏi giữa khung thì thử --focus; nếu khung rộng có 2 người thì --fit blur.
4. review_cuts.py trên bản preview, tóm tắt các jump cut cần che.
5. Chờ tôi duyệt, rồi render bản cuối (bỏ --preview) và chuẩn hoá âm lượng -14 LUFS.
```

### Các lệnh tương ứng (nếu tự chạy)

```powershell
$py = "$HOME\AI-edit-video\examples\.venv\Scripts\python.exe"
$ex = "$HOME\AI-edit-video\examples"
& $py "$ex\transcribe.py" raw\review.mp4 -o work\review.transcript.json --language vi
& $py "$ex\plan_cuts.py" work\review.transcript.json -o work\review.edl.json --brief "(brief ở trên)"
& $py "$ex\render_edl.py" work\review.edl.json -o out\review_v01_preview.mp4 `
      --aspect 9:16 --burn-subs --short-captions --hook "Đừng mua trước khi xem" --preview
& $py "$ex\review_cuts.py" out\review_v01_preview.mp4 work\review.edl.json -o work\review.review.json
& $py "$ex\render_edl.py" work\review.edl.json -o out\review_v01.mp4 --aspect 9:16 --burn-subs --short-captions --hook
ffmpeg -i out\review_v01.mp4 -af loudnorm=I=-14:TP=-1.5:LRA=11 -c:v copy out\review_v01_final.mp4
```

### `render_edl.py` có gì cho short

| Tuỳ chọn | Tác dụng |
|---|---|
| `--aspect 9:16` | Khung 1080×1920 (có cả `1:1`, `16:9`) |
| `--fit crop` / `--fit blur` | Cắt cho đầy khung, hoặc giữ cả hình và làm mờ nền phía sau |
| `--focus 0.3` | Vị trí cắt ngang: 0 = mép trái, 0.5 = giữa, 1 = mép phải |
| `--short-captions` | Phụ đề 2–4 chữ mỗi lần, chữ to, đậm, đặt cao khỏi thanh nút của ứng dụng |
| `--hook ["chữ"]` | Chữ hook trên đầu khung trong 2,5 giây đầu (bỏ trống = lấy trường `hook` trong EDL) |

### Checklist riêng cho short

- [ ] Hook trong 1–3 giây đầu, bằng cả lời nói và chữ trên màn hình
- [ ] Không có khoảng lặng > 0,3 giây; cứ 3–5 giây lại có thay đổi hình (cắt, zoom, B-roll)
- [ ] Phụ đề không nằm ở 20% dưới cùng và mép phải (vùng nút like/comment)
- [ ] Kết bằng một câu chốt hoặc lời kêu gọi; cân nhắc kết nối được vòng lặp về đầu video
- [ ] Âm lượng khoảng -14 LUFS; nhạc nền (nếu có) có giấy phép
- [ ] Kiểm tra giới hạn độ dài hiện tại của từng nền tảng trước khi đăng

**Lưu ý với tiếng Việt:** `--short-captions` tách theo số âm tiết nên đôi khi tách đôi một từ
ghép ("chúng / ta"). Xem lại file `.srt` và sửa tay những dòng như vậy, hoặc nhờ Claude Code
"gộp lại các dòng phụ đề tách đôi từ ghép".

### Làm bằng Concat (nếu muốn chỉnh tay sau)

```text
Tạo project Concat "review_short" khung 1080x1920, 30 fps. Dựng các đoạn trong
work\review.edl.json như use case 1, dùng clip_frame "fill" cho từng clip, thêm phụ đề từ
out\review_v01_preview.srt bằng captions_add với offsetY 0.22 (cao hơn mặc định để tránh
thanh nút), thêm title_add chữ hook ở trên cùng trong 2.5 giây đầu. Lưu project.
```

---

## Use case 3 — Từ video dài ra nhiều short

**Tình huống:** podcast 60 phút → 8 short 25–55 giây, mỗi short một ý trọn vẹn.

### Bước 1 — Claude chọn các short

```powershell
& $py "$ex\transcribe.py" raw\podcast.mp4 -o work\podcast.transcript.json --language vi `
      --prompt "tên khách mời, tên thương hiệu"
& $py "$ex\plan_shorts.py" work\podcast.transcript.json -o shorts --count 8 --min 25 --max 55 `
      --brief "TikTok/Reels cho chủ shop online; mỗi short một bài học cụ thể; hook mạnh; giọng thân thiện"
```

`plan_shorts.py` ghi ra:

- `shorts\short_01.edl.json` ... `short_08.edl.json`, mỗi file gồm các đoạn (có thể ghép từ
  nhiều chỗ trong podcast, ví dụ đưa câu hook từ phút 12 lên đầu), cùng `title`, `hook`,
  `hashtags`, `score`;
- `shorts\index.md`: bảng xếp hạng các short theo điểm, kèm cảnh báo (trùng nội dung giữa
  các short, sai độ dài, tên riêng cần kiểm tra).

Như `plan_cuts.py`, Claude chỉ chọn ID cụm lời thoại; code tính thời gian.

### Bước 2 — Duyệt

Mở `shorts\index.md`. Xoá file EDL của short bạn không thích, sửa `hook` hoặc `title` trực
tiếp trong JSON. Cần kiểm tra kỹ: **câu bị cắt khỏi ngữ cảnh có làm sai ý người nói không**.

### Bước 3 — Render hàng loạt

```powershell
mkdir out\shorts -Force
Get-ChildItem shorts\*.edl.json | ForEach-Object {
    $out = "out\shorts\" + ($_.Name -replace '\.edl\.json$', '_preview.mp4')
    & $py "$ex\render_edl.py" $_.FullName -o $out --aspect 9:16 --burn-subs --short-captions --hook --preview
}
```

Xem các bản preview, chỉnh EDL nếu cần, rồi chạy lại vòng lặp không có `--preview`.

### Bằng một prompt cho Claude Code

```text
Từ raw\podcast.mp4, làm 8 short 25–55 giây cho TikTok/Reels (brief: ...).
1. transcribe.py rồi plan_shorts.py; tóm tắt index.md cho tôi, chờ tôi chọn short nào giữ.
2. Với các short được giữ: render preview 9:16 có phụ đề và hook, chạy review_cuts.py cho
   từng bản, báo những jump cut cần che.
3. Viết caption đăng bài cho từng short (≤ 150 ký tự + 3–5 hashtag), lưu vào out\shorts\captions.md.
4. Chờ tôi duyệt rồi mới render bản cuối.
```

### Mẹo

- Chất lượng hơn số lượng: yêu cầu nhiều (12 short) rồi chỉ giữ 5–6 short điểm cao nhất.
- Thử 2 hook cho cùng một short (sửa trường `hook`, render 2 bản) để thử A/B.
- Podcast nhiều người nói: hỏi ý kiến khách mời trước khi cắt lời của họ thành short riêng.
- Chi phí một lần `plan_shorts.py` cho podcast 1 giờ (Opus 5.5, effort high) thường dưới 1 USD;
  script in số token sau mỗi lần gọi để bạn theo dõi.
- Render hàng loạt bằng ffmpeg nhanh hơn. Chỉ đưa 1–2 short tốt nhất vào Concat để trau chuốt
  thêm (nhạc, hiệu ứng).

---

## Use case 4 — B-roll từ Pexels hoặc Magnific

B-roll là cảnh minh hoạ phủ lên hình người nói, trong khi vẫn nghe tiếng của họ. Nó giúp
minh hoạ điều đang nói, che jump cut và làm nhịp nhanh hơn. Quy trình gồm 3 bước:

1. **Claude chọn ô B-roll** (`broll.py plan`): đọc lời thoại của bản dựng, chọn thời điểm và độ
   dài (1,5–5 giây), viết từ khoá tìm kiếm tiếng Anh và mô tả cảnh. Như mọi chỗ khác, Claude
   chọn ID dòng phụ đề, còn code tính thời gian, bỏ ô quá sớm (2 giây đầu) và ô chồng nhau.
2. **Lấy cảnh**: tự động từ Pexels (`broll.py pexels`), hoặc chọn từ Magnific qua MCP rồi
   thêm bằng `broll.py add`.
3. **Render**: `render_edl.py` phủ B-roll lên hình đúng thời điểm, giữ tiếng gốc, phụ đề nằm
   trên B-roll.

### 4a. Pexels (miễn phí, cần API key)

```powershell
& $py "$ex\broll.py" plan shorts\short_01.edl.json -o shorts\short_01.edl.json `
      --brief "hình ảnh quán cà phê nhỏ, ánh sáng ấm, người Việt"
& $py "$ex\broll.py" pexels shorts\short_01.edl.json -o shorts\short_01.edl.json --orientation portrait
& $py "$ex\render_edl.py" shorts\short_01.edl.json -o out\short_01.mp4 --aspect 9:16 --burn-subs --short-captions --hook
```

`broll.py pexels`:

- tìm trên Pexels cho từng ô (`--orientation portrait` cho video dọc), bỏ clip ngắn hơn ô;
- tải ảnh xem trước của 4 ứng viên mỗi ô, thu nhỏ còn 384 px rồi gửi cho Claude chọn cảnh
  khớp nhất (`--pick first` để bỏ qua bước này và lấy kết quả đầu tiên);
- tải bản mp4 gần 1080p nhất vào `assets\broll\`, ghi mục `broll` vào EDL;
- ghi file `*.credits.txt` để ghi công tác giả.

**Giấy phép Pexels:** dùng miễn phí, kể cả mục đích thương mại, không bắt buộc ghi nguồn
nhưng nên ghi. Hướng dẫn của Pexels API yêu cầu có đường dẫn về Pexels và ghi công tác giả
khi có thể. Không bán lại nguyên bản clip, không dùng theo cách khiến người trong video bị hiểu
là xác nhận cho sản phẩm của bạn. Đọc bản đầy đủ tại pexels.com/license trước khi dùng cho
quảng cáo. API giới hạn số request theo giờ và tháng; xem header `X-Ratelimit-Remaining` nếu
chạy nhiều.

### 4b. Magnific (gói trả phí; stock và video AI qua MCP)

Magnific là tên mới của Freepik từ 28/4/2026, gồm kho stock hơn 250 triệu tài nguyên và các
model tạo video. MCP server chính thức: `https://mcp.magnific.com` (đã thêm ở mục 0.4).

**Stock video (khuyên dùng trước):**

```text
Chạy broll.py plan cho shorts\short_01.edl.json (không dùng Pexels).
Với mỗi ô trong broll_slots: dùng MCP magnific stock_search với content_type "video",
video_type "footage", orientation "portrait", query = trường query của ô; cho tôi xem 4 ứng
viên tốt nhất mỗi ô (tiêu đề, link xem trước, free hay premium) và chờ tôi chọn.
Sau khi tôi chọn: stock_download (type "video", max_bytes 150000000) lấy link, tải file về
assets\broll\magnific_<id>.mp4, rồi chạy
broll.py add shorts\short_01.edl.json --file <file> --slot <N> --credit "Magnific stock #<id>".
Cuối cùng render preview 9:16 để tôi xem.
```

**Video AI khi không có stock phù hợp:**

```text
Ô 3 cần cảnh "bàn tay rót cà phê phin, cận cảnh, ánh sáng ấm, 4 giây, dọc 9:16".
Ước tính credit bằng simulate_cost cho video_generate trước, báo tôi con số và chờ đồng ý.
Sau khi tạo xong (creations_wait), tải về assets\broll\ và thêm vào ô 3 bằng broll.py add,
credit "AI-generated (Magnific)".
```

**Lưu ý với Magnific:**

- Tài nguyên `free` và `premium` có điều kiện khác nhau; gói miễn phí yêu cầu ghi nguồn. Lọc
  bằng tham số `license` của `stock_search` theo gói bạn đang dùng.
- Video AI tốn credit: luôn hỏi `simulate_cost` trước. Tránh tạo cảnh có người thật, logo hay
  thương hiệu, và **gắn nhãn nội dung AI** theo quy định của từng nền tảng.
- MCP còn có `video_cut`, `video_zoom`, `video_color_grade`, `video_music`, `audio_tts`...
  nhưng các bước dựng chính nên giữ ở `render_edl.py` hoặc Concat để quy trình nhất quán.

### 4c. Đặt B-roll trong Concat thay vì ffmpeg

```text
Trong project Concat work\talk_v01: thêm một lane mới ở trên (track_add), import các file
trong mục broll của work\talk.edl.json, đặt mỗi file vào đúng start của nó trên lane mới
(clip_add), cắt cho đúng duration (clip_trim), clip_frame "fill", tắt tiếng B-roll
(clip_update muted: true). Kiểm tra bằng preview_frame ở giữa mỗi B-roll, rồi lưu.
```

---

## Chọn đường nào?

| Nhu cầu | Đường đi |
|---|---|
| Nhiều video, cần nhanh và lặp lại được | Script + ffmpeg (`render_edl.py`), Claude Code điều phối |
| Một video cần trau chuốt bằng tay sau bản dựng AI | Script lên kế hoạch → Concat dựng timeline → bạn hoàn thiện |
| Short hàng loạt từ podcast hoặc livestream | `plan_shorts.py` + vòng lặp render; đưa 1–2 short tốt nhất vào Concat |
| Cảnh minh hoạ miễn phí | Pexels (`broll.py pexels`) |
| Cảnh minh hoạ chất lượng cao, đa dạng, hoặc cảnh không quay được | Magnific stock, rồi video AI nếu cần |
