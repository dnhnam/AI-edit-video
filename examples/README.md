# Ví dụ code: dựng video với Claude API + ffmpeg

| Script | Việc | Gọi Claude? |
|---|---|---|
| `transcribe.py` | Chép lời có mốc thời gian từng từ (faster-whisper, chạy local) | Không |
| `plan_cuts.py` | Claude đọc transcript và chọn đoạn theo brief, xuất EDL + paper edit | Có (văn bản) |
| `render_edl.py` | Render EDL bằng ffmpeg: fade âm tại điểm cắt, phụ đề khớp timeline mới, preview 540p | Không |
| `review_cuts.py` | Claude soát khung trước/sau mỗi điểm cắt, gợi ý punch-in hoặc b-roll | Có (ảnh) |
| `shot_log.py` | Claude lập shot log, chương YouTube, thumbnail từ khung hình mẫu | Có (ảnh + văn bản) |
| `translate_srt.py` | Dịch hoặc biên tập phụ đề, giữ nguyên mốc thời gian | Có (văn bản) |
| `claude_helper.py` | Hàm `ask_structured()` dùng chung: structured outputs, streaming, fallback | — |
| `media.py`, `frames.py` | Tiện ích ffprobe, transcript, SRT, trích khung hình | — |

## Cài đặt

```bash
# ffmpeg: https://ffmpeg.org/download.html  (macOS: brew install ffmpeg)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install faster-whisper            # nếu dùng transcribe.py
export ANTHROPIC_API_KEY=sk-ant-...   # hoặc đăng nhập bằng: ant auth login
```

Model mặc định là `claude-opus-5-5`. Đổi bằng biến môi trường, ví dụ
`CLAUDE_MODEL=claude-sonnet-5-5` cho việc khối lượng lớn, chi phí thấp hơn.

## Chạy thử từ đầu đến cuối

```bash
python transcribe.py raw/talk.mp4 -o work/talk.transcript.json --language vi
python plan_cuts.py work/talk.transcript.json -o work/talk.edl.json \
    --brief "Bản 90 giây, giữ phần kể chuyện, bỏ ậm ừ và câu nói hỏng"
python render_edl.py work/talk.edl.json -o out/talk_preview.mp4 --preview --burn-subs
python review_cuts.py out/talk_preview.mp4 work/talk.edl.json -o work/talk.review.json
python render_edl.py work/talk.edl.json -o out/talk_final.mp4
python translate_srt.py out/talk_final.srt -o out/talk_final.en.srt --to English
python shot_log.py raw/talk.mp4 -o work/talk.shots.json --every 10 --transcript work/talk.transcript.json
```

`plan_cuts.py --dry-run` và `shot_log.py --dry-run` chỉ in dữ liệu hoặc ước tính token,
không gọi API.

## Định dạng EDL

File JSON đơn giản, sửa tay được:

```json
{
  "source": "/path/raw/talk.mp4",
  "transcript": "/path/work/talk.transcript.json",
  "segments": [
    {"start": 204.72, "end": 209.20, "reason": "hook", "text": "Tháng đầu tiên lỗ hơn trăm triệu."},
    {"start": 195.82, "end": 201.45, "reason": "bối cảnh", "text": "Hồi đó tụi mình chỉ có ba người..."}
  ]
}
```

Các đoạn được phát theo thứ tự trong `segments`; được phép đảo thứ tự so với video gốc.

## Kiểm thử offline

```bash
pip install pytest && python -m pytest ../tests -q
```

Các test không gọi Claude. Chúng kiểm tra việc chia cụm, đổi ID thành thời gian, phụ đề
theo timeline mới, chuẩn hoá chương, và render thật một video tổng hợp bằng ffmpeg.
