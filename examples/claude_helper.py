"""Gọi Claude và nhận về JSON đã kiểm tra theo schema (Pydantic).

- Model mặc định: Claude Opus 5.5 (`claude-opus-5-5`). Đổi bằng biến môi trường
  CLAUDE_MODEL, ví dụ `CLAUDE_MODEL=claude-sonnet-5-5` cho việc khối lượng lớn.
- Xác thực: SDK tự đọc ANTHROPIC_API_KEY (hoặc profile từ `ant auth login`).
- Dùng structured outputs để Claude luôn trả JSON hợp lệ — không phải "bóc" JSON
  từ văn bản tự do.
- Bật fallback phía server (`fallbacks: "default"`): nếu bộ lọc an toàn từ chối
  nhầm một yêu cầu bình thường, API tự chạy lại trên model dự phòng.
"""
from __future__ import annotations

import os
import sys
from typing import TypeVar

import anthropic
from pydantic import BaseModel

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")

# Model hỗ trợ fallback phía server (Claude API). Haiku không có fallback.
_SERVER_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}

T = TypeVar("T", bound=BaseModel)


class ClaudeError(RuntimeError):
    pass


def ask_structured(
    system: str,
    content: str | list,
    output_model: type[T],
    *,
    effort: str = "medium",
    max_tokens: int = 32000,
) -> T:
    """Gửi một lượt hỏi và trả về đối tượng `output_model` đã được kiểm tra.

    `content` có thể là chuỗi hoặc danh sách content block (văn bản + ảnh).
    `effort`: low | medium | high | xhigh | max — càng cao càng kỹ và càng tốn token.
    """
    client = anthropic.Anthropic()
    extra: dict = {}
    if MODEL in _SERVER_FALLBACK_MODELS:
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}

    # Dùng streaming để yêu cầu dài (nhiều ảnh, output lớn) không bị timeout HTTP.
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": content}],
        output_format=output_model,
        output_config={"effort": effort},
        **extra,
    ) as stream:
        response = stream.get_final_message()

    usage = response.usage
    print(f"[claude] model={response.model} input_tokens={usage.input_tokens} "
          f"output_tokens={usage.output_tokens} stop={response.stop_reason}", file=sys.stderr)

    if response.stop_reason == "refusal":
        details = response.stop_details
        raise ClaudeError(f"Claude từ chối yêu cầu: {getattr(details, 'category', None)} — "
                          f"{getattr(details, 'explanation', '')}")
    if response.stop_reason == "max_tokens":
        raise ClaudeError("Kết quả bị cắt vì chạm max_tokens — chia nhỏ đầu vào hoặc tăng max_tokens.")
    if response.parsed_output is None:
        raise ClaudeError("Không đọc được JSON trả về.")
    return response.parsed_output
