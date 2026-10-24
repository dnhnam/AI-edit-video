# Dự án dựng video với Claude Code

> Mẫu `CLAUDE.md` để đặt ở gốc thư mục dự án video. Claude Code tự đọc file này
> mỗi phiên. Sửa phần "Dự án này" cho từng video.

## Dự án này

- Mục tiêu: <ví dụ: video YouTube 8–10 phút giới thiệu sản phẩm X>
- Khán giả: <ví dụ: chủ shop online, không rành kỹ thuật>
- Nền tảng & định dạng: <ví dụ: YouTube 16:9 1080p + 3 Shorts 9:16 ≤ 60 giây>
- Giọng điệu & nhịp: <ví dụ: thân thiện, nhịp nhanh, không nhạc nền khi đang nói>
- Bắt buộc giữ: <ví dụ: phần demo tính năng thanh toán>
- Không được dùng: <ví dụ: đoạn có màn hình lộ email khách hàng>

## Cấu trúc thư mục

```
raw/      footage gốc — CHỈ ĐỌC, không bao giờ sửa, đổi tên hay xoá
work/     transcript, EDL, shot log, file tạm
out/      bản preview và bản xuất cuối, đặt tên kèm phiên bản: v01, v02...
assets/   logo, nhạc, font đã có bản quyền
project.md  nhật ký: quyết định đã chốt, phản hồi của tôi, việc còn dở
```

## Quy tắc làm việc

1. **Không phá huỷ.** Không ghi đè file trong `raw/`. Mọi lệnh ffmpeg phải ghi ra
   `work/` hoặc `out/`. Không dùng `-y` lên file đã tồn tại trong `out/` mà không hỏi.
2. **Kiểm tra trước khi làm.** Chạy `ffprobe` để biết độ dài, độ phân giải, fps,
   số track âm thanh trước khi xử lý một file mới.
3. **Kế hoạch trước, render sau.** Với mọi thay đổi về nội dung (cắt, đảo đoạn), đưa
   tôi xem paper edit hoặc EDL (đoạn nào, từ giây nào đến giây nào, vì sao) và chờ tôi
   đồng ý.
4. **Dựa vào transcript, không đoán.** Điểm cắt phải lấy từ mốc thời gian trong
   transcript (`work/*.transcript.json`), đặt vào khoảng lặng giữa hai từ. Không tự
   bịa timestamp. Khi cần xem hình, trích vài khung bằng ffmpeg rồi mới nhận xét.
5. **Preview rẻ trước.** Render bản 540p (`-preset veryfast -crf 28`) để duyệt; chỉ
   render bản cuối khi tôi chốt.
6. **Tự kiểm tra sau mỗi lần render:** so độ dài thực tế với dự kiến, trích khung
   trước/sau mỗi điểm cắt để soát jump cut và khung đen, báo lại danh sách điểm cắt
   để tôi nghe lại âm thanh.
7. **Âm thanh:** fade 20–30 ms tại mỗi điểm cắt; chuẩn hoá loudness -14 LUFS cho
   YouTube (`loudnorm=I=-14:TP=-1.5:LRA=11`) ở bước cuối.
8. **Ghi nhật ký.** Sau mỗi buổi, cập nhật `project.md`: đã làm gì, tôi đã chốt gì,
   còn gì chưa xong.
9. **Hỏi khi không chắc** về gu thẩm mỹ (nhạc, màu, nhịp). Đưa 2–3 phương án ngắn
   thay vì tự quyết.

## Công cụ có sẵn

- `ffmpeg`, `ffprobe`
- Script trong `examples/` của repo AI-edit-video: `transcribe.py`, `plan_cuts.py`,
  `render_edl.py`, `review_cuts.py`, `shot_log.py`, `translate_srt.py`
