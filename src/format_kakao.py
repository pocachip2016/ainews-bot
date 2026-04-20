"""분류된 기사 묶음을 카카오톡 '나에게 보내기' template_object로 포맷."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
BUCKET_LABELS = [
    ("top", "🔥 TOP"),
    ("normal", "📰 일반"),
    ("fyi", "💡 참고"),
]
TEXT_LIMIT = 380  # 카카오 text 템플릿 본문 안전 한도


def _header() -> str:
    now = datetime.now(KST)
    return f"🌅 AI 뉴스 브리핑 · {now.strftime('%m/%d(%a)')}"


def _format_item(item: dict[str, Any]) -> str:
    src = item.get("source", "")
    cat = item.get("category", "")
    tag = f"[{src}/{cat}]" if cat else f"[{src}]"
    title = item.get("title", "").strip()
    summary = item.get("summary_ko", "").strip()
    body = f"• {tag} {title}"
    if summary:
        body += f"\n  {summary}"
    body += f"\n  {item.get('url', '')}"
    return body


def _build_text_blocks(classified: dict[str, list[dict[str, Any]]]) -> list[str]:
    blocks: list[str] = []
    current = _header()

    for key, label in BUCKET_LABELS:
        items = classified.get(key, [])
        if not items:
            continue
        section = f"\n\n{label}\n" + "\n".join(_format_item(i) for i in items)
        if len(current) + len(section) > TEXT_LIMIT * 4:
            blocks.append(current)
            current = label + "\n" + "\n".join(_format_item(i) for i in items)
        else:
            current += section

    if current:
        blocks.append(current)
    return blocks


def format_for_kakao(classified: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """카카오 memo/default/send 의 template_object 리스트 반환."""
    blocks = _build_text_blocks(classified)
    if not blocks:
        return []

    first_url = ""
    for key, _ in BUCKET_LABELS:
        if classified.get(key):
            first_url = classified[key][0].get("url", "") or ""
            break

    messages = []
    for idx, text in enumerate(blocks):
        link_url = first_url if idx == 0 and first_url else "https://news.google.com/"
        messages.append(
            {
                "object_type": "text",
                "text": text[: TEXT_LIMIT * 5],
                "link": {"web_url": link_url, "mobile_web_url": link_url},
                "button_title": "기사 보기",
            }
        )
    return messages
