# AI biên tập video — nghiên cứu và ví dụ với Claude

Nghiên cứu về việc dùng AI để biên tập (dựng) video: AI làm được gì, điểm mạnh, điểm yếu,
cách áp dụng hiệu quả, kèm ví dụ thực hành và mã nguồn chạy được với **Claude**
(claude.ai, Claude Code, Claude API, MCP).

*Cập nhật: tháng 10/2026.*

## Kết luận chính

1. **"AI dựng video" gồm 4 lớp:** hiểu nội dung (ASR, thị giác), quyết định dựng (chọn đoạn,
   sắp mạch), thực thi (ffmpeg, phần mềm dựng) và tạo pixel (video tạo sinh). Claude mạnh
   nhất ở lớp **quyết định**, và điều phối được lớp **thực thi** qua code hoặc MCP.
2. **Claude không xem video trực tiếp và không tạo hình ảnh.** Claude đọc transcript và
   khung hình trích ra (tối đa 600 ảnh mỗi request API), rồi lên kế hoạch, viết lệnh và kiểm tra.
3. **Điểm mạnh:** tự động hoá việc lặp lại (phụ đề, bỏ khoảng lặng, cắt clip ngắn, đổi khung
   hình), tìm nội dung theo ý nghĩa trong footage dài, ra bản nháp nhanh, đa ngôn ngữ, tái lập
   và chạy hàng loạt.
4. **Điểm yếu:** gu thẩm mỹ, nhịp và cảm xúc; "nhìn" thưa, không nghe được âm thanh; có thể
   bịa timestamp; lỗi ASR (nhất là tiếng Việt) lan sang các bước sau; video tạo sinh chưa ổn
   định; số liệu "tiết kiệm thời gian" chủ yếu do nhà cung cấp tự báo cáo.
5. **Cách làm hiệu quả:** transcript là bề mặt chính, hình ảnh chỉ lấy khi cần; **AI chọn ID,
   code tính thời gian**; bắt buộc đầu ra có cấu trúc; kế hoạch → người duyệt → render
   preview → tự kiểm tra → bản cuối; không bao giờ ghi đè footage gốc.

## Nội dung

| Tài liệu | Nội dung |
|---|---|
| [Phần 1 — Tổng quan, điểm mạnh, điểm yếu](docs/01-nghien-cuu-tong-quan.md) | 4 lớp của AI dựng video, bức tranh công cụ 2026, năng lực và giới hạn của Claude (có số liệu và chi phí), điểm mạnh, rủi ro, nguồn tham khảo |
| [Phần 2 — Quy trình hiệu quả](docs/02-quy-trinh-hieu-qua.md) | 10 nguyên tắc, quy trình mẫu, chọn công cụ theo loại video, mẹo prompt, checklist chất lượng, quyền riêng tư |
| [Phần 3 — Ví dụ với Claude](docs/03-vi-du-voi-claude.md) | 10 ví dụ: claude.ai, Claude Code + ffmpeg, pipeline API, shot log bằng thị giác, Remotion, MCP cho DaVinci Resolve / Premiere / Adobe, video-use, Concat; bảng prompt kém và prompt tốt |
| [Phần 4 — Use case trên Windows với Claude Code](docs/04-use-case-windows-claude-code.md) | Cài đặt trên Windows; 4 use case: dựng với Concat, dựng video short, video dài ra nhiều short, B-roll từ Pexels hoặc Magnific |
| [Phần 5 — Đánh giá Claude Code + Concat](docs/05-danh-gia-claude-code-concat.md) | Video dài → project Concat nhiều tab → người duyệt và xuất: khả năng, căn cứ, hạn chế, cách kiểm chứng |
| [`examples/`](examples) | Mã Python: chép lời → Claude lập EDL hoặc chọn nhiều short → Claude chọn B-roll → render ffmpeg (16:9 hoặc 9:16) hoặc dựng project Concat (`edl_to_concat.py`) → Claude soát điểm cắt → dịch phụ đề → shot log |
| [`templates/CLAUDE.md`](templates/CLAUDE.md) | Mẫu luật làm việc cho Claude Code trong một dự án video |
| [`templates/brief.md`](templates/brief.md) | Mẫu brief dựng video, kèm ví dụ brief kém và brief tốt |

## Chạy nhanh ví dụ code

```bash
cd examples
pip install -r requirements.txt faster-whisper
export ANTHROPIC_API_KEY=sk-ant-...

python transcribe.py raw/talk.mp4 -o work/talk.transcript.json --language vi
python plan_cuts.py work/talk.transcript.json -o work/talk.edl.json --brief "Bản 90 giây, bỏ ậm ừ"
python render_edl.py work/talk.edl.json -o out/preview.mp4 --preview --burn-subs
```

Xem chi tiết trong [`examples/README.md`](examples/README.md).
