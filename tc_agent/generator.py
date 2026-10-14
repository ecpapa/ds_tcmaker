"""타일 이미지를 Claude에 보내 분석 리포트와 테스트 케이스(TestSuite)를 받는다."""

from __future__ import annotations

from pathlib import Path

import anthropic

from .loader import SpecDocument
from .schema import TestSuite

MODEL = "claude-opus-5-5"
# Messages API 한 요청에 넣을 수 있는 이미지 수와 요청 크기 한도
MAX_IMAGES = 100
MAX_REQUEST_BYTES = 30_000_000
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.md"


class GenerationError(RuntimeError):
    pass


def build_content(doc: SpecDocument) -> list[dict]:
    content: list[dict] = []
    if doc.tiles:
        content.append({
            "type": "text",
            "text": f"기획서 파일: {doc.path.name}\n아래는 기획서 보드를 자른 타일 {len(doc.tiles)}장입니다. "
                    "라벨의 r은 행, c는 열 번호이며 왼쪽 위부터 오른쪽 아래 순서입니다.",
        })
    for tile in doc.tiles:
        caption = f"[TILE {tile.label}] 위치: {tile.region}"
        if tile.text:
            caption += f"\n<text_layer>\n{tile.text}\n</text_layer>"
        content.append({"type": "text", "text": caption})
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": tile.b64},
        })
    if doc.text:
        content.append({"type": "text", "text": f"<spec file=\"{doc.path.name}\">\n{doc.text}\n</spec>"})
    content.append({
        "type": "text",
        "text": "위 기획서 전체를 분석 프레임워크 순서대로 분석하고, 블랙박스 테스트 케이스를 빠짐없이 생성하세요.",
    })
    return content


def generate(doc: SpecDocument, effort: str = "high", client: anthropic.Anthropic | None = None) -> TestSuite:
    payload = sum(len(t.b64) for t in doc.tiles)
    if len(doc.tiles) > MAX_IMAGES or payload > MAX_REQUEST_BYTES:
        raise GenerationError(
            f"타일 {len(doc.tiles)}장 / {payload / 1e6:.1f}MB 로 한 요청 한도(이미지 {MAX_IMAGES}장, 약 32MB)를 넘어요. "
            "--tile-pt 값을 키우거나(예: 2000) 기획서를 화면 단위로 나눠서 넣어주세요."
        )
    client = client or anthropic.Anthropic()
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=128000,
        system=system_prompt,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        output_format=TestSuite,
        # 안전 분류기가 요청을 거절하면 서버가 다른 모델로 자동 재시도한다
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": build_content(doc)}],
    ) as stream:
        for event in stream:
            if event.type == "content_block_start" and event.content_block.type == "text":
                print("  - 응답 작성 중...", flush=True)
        message = stream.get_final_message()

    usage = message.usage
    print(f"  - 토큰: 입력 {usage.input_tokens:,} / 출력 {usage.output_tokens:,} (stop: {message.stop_reason})")

    if message.stop_reason == "refusal":
        raise GenerationError(f"모델이 요청을 거절했습니다: {message.stop_details}")
    if message.stop_reason == "max_tokens":
        raise GenerationError("출력 한도에 도달해 결과가 잘렸습니다. 기획서를 나눠서 실행해 보세요.")
    if message.parsed_output is None:
        raise GenerationError("응답을 TestSuite 구조로 해석하지 못했습니다.")
    return message.parsed_output
