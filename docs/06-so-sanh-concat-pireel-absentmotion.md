# Phần 6 — So sánh Concat với pireel và AbsentMotion

*Kiểm tra ngày 13/11/2026, bằng cách đọc mã nguồn và README của từng repo (chưa chạy thử).*

- [jub0t/concat](https://github.com/jub0t/concat): phần mềm dựng video trên máy tính, thay CapCut.
- [pireel/pireel](https://github.com/pireel/pireel): trình dựng video chạy trên web, nhúng được
  vào trang khác, AI là trung tâm.
- [Comett1225/AbsentMotion](https://github.com/Comett1225/AbsentMotion): motion graphics trên
  điện thoại, thay Alight Motion và CapCut; có bản máy tính từ 5.0.

**Kết luận:** giữ **Concat** làm nơi dựng chính trong quy trình "AI dựng, người duyệt", vì
chạy offline, có MCP cho Claude Code và khớp với các script của repo này. pireel đáng theo dõi
nếu cần xuất sang Premiere/Resolve/Final Cut hoặc muốn một trình dựng web có agent tích hợp.
AbsentMotion hợp để tự tay làm đồ hoạ động, không thay được Concat trong pipeline vì không có
giao diện cho AI điều khiển.

---

## 1. Bảng so sánh

| | Concat | pireel | AbsentMotion |
|---|---|---|---|
| Loại | Dựng video trên máy tính | Trình dựng web nhúng được (component React) | Motion graphics, Android trước, có bản máy tính |
| Công nghệ | Rust, GPU | TypeScript/React, xử lý trong trình duyệt (WebCodecs qua mediabunny) | Kotlin + C++ |
| Giấy phép | AGPL-3.0 | AGPL-3.0 (phần nối agent: Apache-2.0) | GPL-3.0 |
| Cho AI điều khiển | MCP có sẵn (`concat --mcp`), chạy offline | Agent nằm trong trình dựng, khoảng 60 công cụ; bạn tự cung cấp model, chép lời, lưu trữ | Không có MCP hay API |
| Chạy offline | Có | Dựng, xem, xuất: có; AI: cần dịch vụ ngoài | Có hoàn toàn |
| Phụ đề tự động | Whisper trong app (chọn ngôn ngữ, chỉ nghe giọng nói) | Qua dịch vụ chép lời bạn cung cấp; ngắt câu theo cụm ý | whisper.cpp trên máy |
| Xuất sang phần mềm dựng khác | Chưa | XML cho Premiere, DaVinci Resolve, Final Cut, kèm SRT | Không |
| Mức trưởng thành | Beta 0.2.x, cập nhật rất nhanh | Repo công khai mới (commit đầu thấy được từ 03/11/2026) | 5.1.0 (12/11/2026) |

## 2. pireel mạnh hơn Concat ở đâu

- **Sinh ra để AI dựng.** Có sẵn công cụ agent mức cao: `rough_cut`, `remove_silence`,
  `remove_words`, `plan_montage`, `set_captions`, `save_edit_plan`, `finish_edit` (agent tự soát và
  liệt kê hết lỗi còn lại). Concat chỉ có lệnh dựng cấp thấp; phần "trí tuệ" phải tự viết, như
  `plan_cuts.py` và `edl_to_concat.py` của repo này.
- **Xuất timeline sang phần mềm chuyên nghiệp** (xmeml, FCPXML, SRT): duyệt và chỉnh tiếp trên
  Premiere, Resolve hay Final Cut.
- **Phụ đề và trình bày tốt hơn:** ngắt theo cụm ý, không cắt giữa từ, chọn chữ cần nhấn; "brand"
  ghi lại phong cách phụ đề, font, đồ hoạ của một người sáng tạo; picture-in-picture; khung theo
  người đang nói.
- **Nối được Claude:** dùng Vercel AI SDK; bạn tự dựng endpoint chat (`chatEndpoint`) gọi Claude.

**Hạn chế:** các quy trình đáng giá nhất (video dài ra short, lồng tiếng, B-roll, xoá vật thể)
nằm ở dịch vụ trả phí pireel.com; bản mở mã chỉ là trình dựng. Xử lý trong trình duyệt nên
video 4K dài sẽ nặng.

## 3. AbsentMotion mạnh hơn Concat ở đâu

- **Motion graphics:** 213 hiệu ứng, keyframe nhiều kiểu easing, camera 3D, đèn, mô hình 3D, chữ
  3D, mask động (rotoscoping), motion tracking, slow motion bằng optical flow, time remap.
- **Nhập được** file Adobe Animate (.fla) và project Alight Motion.
- **Chạy tốt trên điện thoại** (Android 8 trở lên), Chromebook, và Windows/Mac/Linux; có giao diện
  tiếng Việt.
- **Offline hoàn toàn:** phụ đề tự động, đọc chữ thành giọng nói, tách nền.

**Hạn chế với quy trình của repo này:** không có MCP, API hay chế độ dòng lệnh để Claude Code
điều khiển.

## 4. Lỗi black preview của Concat

- **Triệu chứng:** màn xem trước đen cho tới hết phiên, nhất là trên Windows (các issue #709,
  #712, #733, #737, #686).
- **Nguyên nhân** (theo ghi chú commit): GPU bị mất thiết bị trên Direct3D 12; Concat xin thiết
  bị mới mỗi khung hình trong khi vẫn giữ thiết bị hỏng, nên Direct3D 12 không mở được thiết bị
  nào nữa.
- **Cách khắc phục trong v0.2.11:** thả thiết bị hỏng, thử lại, rồi lùi dần xuống **vẽ bằng
  CPU**: không còn đen, nhưng chậm và **không có hiệu ứng**, kèm một thông báo trên màn hình. Lỗi
  GPU gốc chưa hết.
- **Với Claude Code:** khi Concat phải vẽ bằng CPU và bỏ hiệu ứng, `preview_frame` qua MCP **báo
  lỗi** thay vì trả về ảnh thiếu hiệu ứng. Gặp lỗi đó ở bước soát khung hình là dấu hiệu GPU có
  vấn đề.
- **Trong lúc chưa có v0.2.11:** dùng mục Start menu "Concat (safe graphics)" (`concat --software`,
  có từ v0.2.9) để vẽ cửa sổ bằng CPU.
