# Phần 1 — Dùng AI để biên tập video: tổng quan, điểm mạnh, điểm yếu

*Cập nhật: tháng 10/2026. Công cụ AI thay đổi rất nhanh, nên các tính năng và giá cụ thể
cần kiểm tra lại trên trang chính thức trước khi dùng.*

---

## Tóm tắt nhanh

1. **"AI dựng video" thật ra là bốn việc khác nhau:** hiểu nội dung, quyết định dựng,
   thực thi lệnh dựng, và tạo/biến đổi hình ảnh. Mỗi việc cần một loại công cụ khác.
2. **AI đã làm tốt các việc lặp lại:** chép lời, phụ đề, bỏ khoảng lặng và tiếng ậm ừ,
   tìm đoạn hay trong footage dài, cắt clip ngắn, đổi khung hình dọc/ngang, dịch.
3. **AI còn yếu ở gu và nhịp:** cảm xúc, nhịp dựng, lúc nào nên giữ một khoảng lặng,
   chọn nhạc. Nó cũng dễ cho ra kết quả "na ná nhau". Phần tạo hình (generative) vẫn
   chưa ổn định.
4. **Claude không xem video trực tiếp và không tạo ra pixel.** Claude đọc văn bản
   (transcript) và ảnh (khung hình trích ra), suy luận, lên kế hoạch, viết lệnh/code, rồi
   điều khiển ffmpeg, Remotion, DaVinci Resolve hay Premiere qua code hoặc MCP. Hãy coi
   Claude như **biên tập viên kiêm kỹ sư pipeline**, không phải một trình dựng phim.
5. **Mô hình hiệu quả nhất hiện nay:** AI làm bản nháp và việc tay chân, người duyệt và
   quyết định phần sáng tạo.

---

## 1. "AI dựng video" gồm những gì?

| Lớp | Việc cụ thể | Công nghệ điển hình | Claude có làm được không? |
|---|---|---|---|
| **1. Hiểu nội dung** | Chép lời (ASR), tách người nói, phát hiện chuyển cảnh, mô tả khung hình, nhận ra tiếng cười/nhạc | Whisper, ElevenLabs Scribe, bộ lọc scene của ffmpeg, mô hình thị giác | **Một phần.** Claude hiểu ảnh rất tốt nhưng không nghe được âm thanh, nên cần ASR bên ngoài |
| **2. Quyết định dựng** | Chọn đoạn giữ/bỏ, sắp mạch kể, viết paper edit/EDL, đặt chương, viết tiêu đề/mô tả, biên tập phụ đề | LLM | **Đây là thế mạnh chính của Claude** |
| **3. Thực thi** | Cắt, ghép, chèn chữ, đốt phụ đề, chỉnh âm lượng, xuất file | ffmpeg, NLE (Premiere, Resolve, CapCut), Remotion | **Gián tiếp:** Claude viết và chạy lệnh (Claude Code) hoặc điều khiển phần mềm qua MCP |
| **4. Tạo / biến đổi pixel** | Tạo cảnh từ văn bản, kéo dài clip, xoá vật thể, tách nền, upscale, khử nhiễu, lồng tiếng, đổi khẩu hình | Runway, Veo, Firefly, các model chuyên biệt | **Không.** Claude không tạo ra ảnh hay video; chỉ có thể gọi công cụ khác làm việc này |

Phân lớp như vậy giúp tránh kỳ vọng sai. Ví dụ "nhờ Claude xoá người qua đường khỏi
cảnh quay" là việc của lớp 4, không phải của Claude. Còn "tìm 5 câu hay nhất trong buổi
phỏng vấn 2 tiếng rồi ghép thành clip 60 giây" là việc của lớp 2 và 3, chính là chỗ Claude
làm tốt.

---

## 2. Bức tranh công cụ năm 2026

| Nhóm | Ví dụ | Mạnh ở | Cần lưu ý |
|---|---|---|---|
| Dựng bằng transcript | Descript; tính năng text-based editing của Premiere Pro | Sửa video như sửa văn bản; bỏ "ừm/à" hàng loạt | Bản miễn phí thường giới hạn xuất file hoặc gắn watermark |
| Cắt clip ngắn tự động | OpusClip, CapCut | Từ video dài ra nhiều clip dọc chỉ trong vài phút | Dễ ra kết quả theo khuôn mẫu, na ná nhau; tính phí theo credit |
| Phần mềm dựng chuyên nghiệp (NLE) có AI | Premiere Pro (text-based editing, Generative Extend, AI Assistant bản beta); DaVinci Resolve (Magic Mask, Voice Isolation, IntelliScript...) | Timeline đầy đủ, màu, âm thanh, quy trình chuyên nghiệp | AI Assistant của Premiere dùng model của Adobe, không cắm Claude vào được |
| Video tạo sinh | Runway, Veo, Firefly Video | Tạo cảnh, kéo dài clip, hiệu ứng | Khó giữ nhất quán nhân vật, chữ và tay; thường phải sửa lại thủ công |
| Agent + code | Claude Code + ffmpeg (ví dụ dự án mã nguồn mở [video-use](https://github.com/browser-use/video-use)); Remotion + Agent Skills | Linh hoạt tuyệt đối, tái lập được, chạy hàng loạt | Cần quen dòng lệnh; vẫn phải duyệt kết quả |
| Claude điều khiển NLE qua MCP | DaVinci Resolve 21.1 Studio (MCP tích hợp sẵn); MCP cộng đồng cho Resolve, Premiere, After Effects, ffmpeg; connector "Adobe for creativity" | Ra lệnh bằng ngôn ngữ tự nhiên ngay trên project thật | MCP gốc của Resolve chỉ có ở bản Studio (trả phí); server cộng đồng chưa được kiểm định |

Một số mốc đáng chú ý:

- **28/4/2026:** Anthropic ra mắt 9 connector cho công việc sáng tạo (Adobe, Blender, Ableton,
  Autodesk Fusion, Splice, SketchUp, Affinity by Canva, Resolume...). Connector "Adobe for
  creativity" nối Claude với hơn 50 công cụ của Adobe, trong đó có Premiere và Express, phục
  vụ các việc như đổi kích thước video cho YouTube Shorts.
- **9/2026:** DaVinci Resolve 21.1 thêm máy chủ MCP tích hợp để Claude, Claude Code và Codex
  sắp xếp media, dựng highlight từ video dài, bỏ clip thừa và render hàng loạt bằng lệnh tự
  nhiên. Tính năng này chỉ có ở bản Studio, thiết lập qua *File > Setup AI Assistants*.
- **4/2026:** [video-use](https://github.com/browser-use/video-use) (giấy phép MIT) ra mắt:
  thả footage vào thư mục, chat với Claude Code, nhận về `final.mp4`. Dự án này thể hiện rõ
  cách làm "transcript trước, hình ảnh khi cần".

---

## 3. Claude đứng ở đâu: năng lực và giới hạn có số liệu

### Claude nhận được gì

- **Văn bản:** transcript, kịch bản, EDL, phụ đề. Cửa sổ ngữ cảnh 1 triệu token (Opus 5.5)
  đủ chứa transcript của nhiều giờ nói.
- **Ảnh:** JPEG, PNG, GIF (chỉ khung đầu), WebP, tức là khung hình trích từ video.
- **Không nhận file video hay âm thanh.** Muốn Claude "xem" video, phải trích khung hình;
  muốn Claude "nghe", phải chép lời bằng ASR trước.
- **Không tạo ảnh hay video.** Claude chỉ hiểu và phân tích hình ảnh.

### Giới hạn ảnh trên API (theo tài liệu chính thức)

| Thông số | Giá trị |
|---|---|
| Số ảnh tối đa mỗi request | 600 (model có 1 triệu token ngữ cảnh), 100 (model 200k), 20 trên claude.ai |
| Kích thước tối đa | 8000×8000 px; nếu request có hơn 20 ảnh, nên giữ mỗi ảnh ≤ 2000 px |
| Dung lượng | 10 MB mỗi ảnh (base64); tổng request 32 MB |
| Cách tính token | `ceil(rộng/28) × ceil(cao/28)`. Ví dụ ảnh 1920×1080 tốn khoảng 2.691 token trên Claude 4.7 trở lên |
| Hạn chế | Không nêu được danh tính người thật; đếm vật và xác định vị trí chỉ gần đúng; dễ sai với ảnh nhỏ dưới 200 px |

### Ước tính chi phí cho 1 giờ footage (Claude Opus 5.5, đầu vào $4 / 1 triệu token)

| Cách cho Claude "xem" | Lượng token đầu vào | Chi phí ước tính | Nhận xét |
|---|---|---|---|
| Chỉ transcript (khoảng 9–10 nghìn từ, kèm mốc thời gian) | vài chục nghìn | khoảng $0,1–0,2 | Rẻ, nhanh; nên là bước đầu tiên |
| 1 khung mỗi 5 giây, ảnh 512 px (khoảng 209 token mỗi khung) | 720 khung ≈ 150 nghìn | khoảng $0,6 (chia 2 request vì quá 600 ảnh) | Đủ để lập shot log và chia chương |
| 1 khung mỗi giây, ảnh 1080p gốc | 3.600 × 2.691 ≈ 9,7 triệu | khoảng $39, vượt cả cửa sổ ngữ cảnh | Không khả thi và cũng không cần |

Bài học: **dùng transcript làm "bề mặt" chính, chỉ lấy khung hình khi cần quyết định**
(chuyển cảnh, chọn thumbnail, kiểm tra điểm cắt). Dự án video-use ước tính cách làm ngược
lại, đọc 30.000 khung hình, tốn khoảng 45 triệu token, trong khi transcript đã nén chỉ
khoảng 12 KB.

### Vai trò phù hợp nhất cho Claude

1. **Biên tập viên nội dung:** đọc transcript, chọn đoạn, sắp mạch, viết paper edit.
2. **Trợ lý dựng (assistant editor):** lập shot log, gắn marker, chia chương, viết metadata.
3. **Kỹ sư pipeline:** viết và chạy lệnh ffmpeg, code Remotion, script tự động hoá.
4. **Người điều khiển phần mềm:** thao tác trên project Resolve/Premiere qua MCP.
5. **Người kiểm tra chất lượng:** soát khung trước/sau điểm cắt, đối chiếu phụ đề, kiểm tra
   brief đã được đáp ứng chưa.

---

## 4. Điểm mạnh

### 4.1. Tự động hoá việc lặp lại và tốn thời gian
Chép lời, tạo phụ đề, bỏ khoảng lặng và tiếng ậm ừ, đổi khung hình 16:9 sang 9:16, xuất
nhiều phiên bản. Đây là những việc chiếm nhiều giờ của người dựng nhưng ít cần sáng tạo.
Các hướng dẫn năm 2026 thống nhất rằng AI xử lý tốt nhóm việc này, nhưng dự án quan trọng
vẫn nên có người duyệt.

### 4.2. Hiểu nội dung ở mức ý nghĩa
Thay vì tua 3 tiếng footage, bạn có thể hỏi "đoạn nào khách mời kể về lần thất bại đầu
tiên?". LLM đọc transcript và trả lời theo ý nghĩa, không chỉ theo từ khoá. Với footage dài
(hội thảo, podcast, phỏng vấn), lợi ích này rất lớn.

### 4.3. Ra bản nháp nhanh
Paper edit hay rough cut trong vài phút giúp người dựng bỏ qua giai đoạn "trang giấy trắng"
và dành thời gian cho tinh chỉnh: nhịp, cảnh chèn, âm nhạc, màu.

### 4.4. Đa ngôn ngữ
Dịch phụ đề, chuẩn hoá thuật ngữ, viết tiêu đề, mô tả, chương và hashtag cho nhiều thị
trường. Đây vốn là thế mạnh tự nhiên của LLM.

### 4.5. Tái lập được và kiểm soát được
Khi quyết định dựng được ghi thành văn bản (EDL dạng JSON, lệnh ffmpeg, code Remotion), bạn
có thể so sánh phiên bản, lưu bằng git, sửa một dòng rồi render lại, hoặc áp cùng quy trình
cho 50 video. Phần mềm dựng kéo-thả khó làm được điều này.

### 4.6. Mở rộng quy mô
Một video dài thành 10 clip ngắn; một khoá học 40 bài cùng được gắn phụ đề, chương và thumbnail
theo một chuẩn chung.

### 4.7. Hạ rào cản kỹ thuật
Người không thạo ffmpeg hay After Effects vẫn làm được việc khó: Claude Code viết lệnh
ffmpeg, viết code Remotion cho motion graphics (biểu đồ động, lower-third, intro), giải
thích từng tham số.

---

## 5. Điểm yếu và rủi ro

### 5.1. Gu thẩm mỹ, nhịp và cảm xúc
AI giỏi **bỏ cái thừa** hơn là **tạo nhịp**. Những quyết định như J-cut/L-cut, giữ một khoảng
lặng có chủ ý, chèn cảnh phản ứng hay cắt theo nhịp nhạc vẫn cần con người. Công cụ dựa
nhiều vào template dễ cho ra video "giống nhau".

### 5.2. "Nhìn" thưa và "nghe" gián tiếp
Lấy mẫu khung hình có thể bỏ sót chuyển động nhanh, hành động ngắn, chi tiết nhỏ. Claude
không nghe được âm thanh, nên giọng điệu, sự mỉa mai, tiếng cười, nhạc nền hay tiếng ồn chỉ
được biết qua những gì ASR ghi lại. Một câu "hay quá ha" có thể là khen thật hoặc mỉa mai.

### 5.3. Ảo giác và sai lệch thời gian
Nếu để LLM tự viết timestamp, nó có thể đưa ra mốc không tồn tại, hoặc lệch vài trăm mili
giây khiến cắt giữa từ, nghe "bụp". Cách khắc phục (xem Phần 2): cho Claude **chọn ID**
trong danh sách có sẵn, còn **code tính thời gian**.

### 5.4. Lỗi dây chuyền từ ASR, nhất là với tiếng Việt
Thiếu dấu, nhầm thanh điệu, giọng vùng miền, tên riêng, thuật ngữ tiếng Anh chen giữa câu.
Transcript sai thì mọi quyết định phía sau đều sai theo. Nên dùng model ASR lớn, đưa danh
sách tên riêng làm gợi ý, và rà transcript trước khi dựng.

### 5.5. Giới hạn kỹ thuật
Nhiều công cụ trên mây không nhận được file 4K hoặc file raw dài, hoặc nén mạnh trước khi xử
lý. Với LLM, giới hạn số ảnh và kích thước request buộc phải lấy mẫu thưa và chia nhỏ.

### 5.6. Video tạo sinh chưa ổn định
Kết quả text-to-video còn thiếu nhất quán (nhân vật, chữ, bàn tay) và thường phải sửa lại
trong phần mềm dựng.

### 5.7. Chi phí ẩn
Thuê bao, credit theo phút, token ảnh, và đặc biệt là thời gian cho những vòng sửa khi brief
không rõ ràng.

### 5.8. Quyền riêng tư, bản quyền, đạo đức
- Tải footage của khách hàng lên dịch vụ đám mây cần sự đồng ý và cần kiểm tra chính sách lưu
  trữ dữ liệu.
- Nhạc, stock footage và font phải có giấy phép.
- Nhân bản giọng nói hay đổi khẩu hình của người thật phải được họ cho phép. Nội dung do AI
  tạo cần được gắn nhãn theo quy định của từng nền tảng.

### 5.9. Phụ thuộc hệ sinh thái
MCP gốc của Resolve chỉ có ở bản Studio, AI Assistant của Premiere không cho cắm model ngoài,
còn server MCP cộng đồng có thể ngừng được bảo trì. Tính năng thay đổi theo từng tháng.

### 5.10. Bằng chứng còn mỏng
Phần lớn các con số như "tiết kiệm 60–80% thời gian" hay "bỏ ậm ừ chính xác 85–90%" là
**tự báo cáo của nhà cung cấp hoặc người sáng tạo nội dung**, không phải thử nghiệm có đối
chứng. Nghiên cứu học thuật tiêu biểu như **LAVE** (ACM IUI 2024, trợ lý dựng video dùng LLM)
chỉ thử với 8 người. Hãy tự đo trên chính dự án của bạn.

---

## 6. Kết luận: nên giao gì cho AI, giữ gì cho người

| Giao cho AI (có người duyệt nhanh) | Giữ cho người quyết định |
|---|---|
| Chép lời, phụ đề, dịch | Câu chuyện chính, thông điệp, cấu trúc |
| Bỏ khoảng lặng, ậm ừ, câu nói hỏng | Nhịp dựng, J/L-cut, khoảng lặng có chủ ý |
| Tìm và đề xuất đoạn hay, highlight | Chọn cuối cùng đoạn nào lên sóng |
| Shot log, marker, chương, thumbnail ứng viên | Màu sắc, âm nhạc, phong cách hình ảnh |
| Đổi khung hình, xuất nhiều phiên bản, chuẩn hoá âm lượng | Nội dung nhạy cảm, pháp lý, đạo đức |
| Viết lệnh ffmpeg / code Remotion | Duyệt bản cuối trước khi xuất bản |

---

## Nguồn tham khảo

- Anthropic — [Vision (tài liệu Claude API)](https://platform.claude.com/docs/en/build-with-claude/vision): giới hạn ảnh, cách tính token, hạn chế
- [browser-use/video-use](https://github.com/browser-use/video-use): pipeline "transcript + hình ảnh khi cần", tự kiểm tra tại điểm cắt
- [a1adams/mcp-servers-for-video-editing](https://github.com/a1adams/mcp-servers-for-video-editing): bảng so sánh MCP cho Resolve, Premiere, After Effects, ffmpeg, Descript (cập nhật 6/10/2026)
- CineD — [DaVinci Resolve 21.1: AI assistant integration via MCP](https://www.cined.com/es/davinci-resolve-21-1-released-ai-assistant-integration-via-mcp-individual-hdr-trims-and-python-scripting-moves-to-studio/); Digital Production — [Resolve 21.1 Adds MCP](https://digitalproduction.com/2026/09/08/resolve-21-1-adds-mcp-and-finally-gets-presets/); [Motion Media — Resolve 21.1](https://www.motionmedia.com/mm-blog/davinci-resolve-21-1-update-new-features)
- [weandthecolor — Adobe for creativity connector trong Claude](https://weandthecolor.com/how-does-the-adobe-for-creativity-connector-work-in-claude/210357); [NYU Shanghai RITS — 9 connector sáng tạo](https://rits.shanghai.nyu.edu/ai/anthropic-plugs-claude-into-adobe-blender-and-ableton-with-nine-new-connectors/)
- [Tella — Remotion Agent Skills với Claude Code](https://www.tella.com/blog/how-to-use-remotion-agent-skills-with-claude-code); [OpenReplay — Making videos with Claude Code + Remotion](https://blog.openreplay.com/making-videos-claude-code-remotion/)
- Wang et al. — [LAVE: LLM-Powered Agent Assistance and Language Augmentation for Video Editing](https://arxiv.org/abs/2402.10294) (IUI 2024)
- [Prompt-Driven Agentic Video Editing System](https://arxiv.org/pdf/2509.16811) (arXiv 2025)
- Các bài tổng hợp công cụ năm 2026 (chủ yếu từ nhà cung cấp, cần đọc có chọn lọc): [Atlantic.Net](https://www.atlantic.net/gpu-server-hosting/top-ai-video-editing-platforms-choosing-the-right-tool/), [Aiarty](https://www.aiarty.com/edit-video/ai-video-editing-tools.htm), [Wideframe — xu hướng 2026](https://try.wideframe.com/blog/ai-video-editing-trends-2026/), [IntelligentHQ](https://www.intelligenthq.com/best-ai-video-editing-tools-2026/), [Vozo — quy trình YouTube](https://www.vozo.ai/blogs/youtube/ai-video-editing-youtube-workflow)
- Bài viết về giới hạn "Claude có xem được video không": [AnimSpec](https://animspec.com/blog/can-claude-watch-videos), [claude-video-vision plugin](https://github.com/jordanrendric/claude-video-vision), [Issue #12676 — anthropics/claude-code](https://github.com/anthropics/claude-code/issues/12676)
