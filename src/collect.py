"""Gemini Google Search 그라운딩으로 최근 24시간 AI 뉴스 수집.

gemini-2.5-flash-lite: Google Search grounding 무료 티어 지원.
--dry-run 시 API 미호출 (샘플 데이터 반환).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
SEEN_PATH = ROOT / "data" / "seen.json"
SEEN_RETENTION_DAYS = 30
GROUNDING_MODEL = "gemini-2.5-flash-lite"
MAX_ARTICLES = 30

SEARCH_QUERIES = [
    ("OpenAI Anthropic Claude Google AI Gemini latest news today", "기업·제품", "global"),
    ("artificial intelligence LLM news today 2026", "미디어", "global"),
    ("AI startup investment generative AI research announcement", "연구", "global"),
    ("인공지능 AI 뉴스 최신 오늘", "국내", "kr"),
]

_SAMPLE_ARTICLES: list[dict[str, Any]] = [
    {
        "title": "[DRY-RUN] OpenAI releases GPT-5",
        "url": "https://example.com/gpt5",
        "source": "example.com",
        "category": "기업·제품",
        "region": "global",
        "published": "",
        "summary_raw": "Sample article for dry-run testing.",
    },
    {
        "title": "[DRY-RUN] 국내 AI 규제 법안 통과",
        "url": "https://example.com/ai-law",
        "source": "example.com",
        "category": "국내",
        "region": "kr",
        "published": "",
        "summary_raw": "테스트용 샘플 기사입니다.",
    },
]


def _hash_url(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _load_seen() -> dict[str, str]:
    if not SEEN_PATH.exists():
        return {}
    data = json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    if isinstance(data, list):
        today = datetime.now(timezone.utc).date().isoformat()
        return {h: today for h in data}
    return data


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def collect_all(dry_run: bool = False) -> list[dict[str, Any]]:
    if dry_run:
        print("[collect] DRY-RUN: API 미호출, 샘플 데이터 반환", file=sys.stderr)
        return _SAMPLE_ARTICLES

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    seen = _load_seen()
    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    failed = 0
    for query, category, region in SEARCH_QUERIES:
        try:
            response = client.models.generate_content(
                model=GROUNDING_MODEL,
                contents=f"Search and list recent news articles about: {query}",
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.1,
                ),
            )
            candidate = response.candidates[0]
            meta = getattr(candidate, "grounding_metadata", None)
            chunks = getattr(meta, "grounding_chunks", []) if meta else []

            picked = 0
            for chunk in chunks:
                web = getattr(chunk, "web", None)
                if not web:
                    continue
                url = getattr(web, "uri", "") or ""
                title = getattr(web, "title", "") or ""
                if not url or url in seen_urls or _hash_url(url) in seen:
                    continue
                seen_urls.add(url)
                results.append({
                    "title": title,
                    "url": url,
                    "source": _domain(url),
                    "category": category,
                    "region": region,
                    "published": "",
                    "summary_raw": "",
                })
                picked += 1

            print(f"[collect] '{query[:45]}': {picked}건", file=sys.stderr)

        except Exception as e:
            failed += 1
            print(f"[collect] 검색 실패 ({query[:45]}): {e}", file=sys.stderr)

    if failed == len(SEARCH_QUERIES):
        raise RuntimeError(f"모든 Gemini 검색 쿼리 실패 ({failed}/{len(SEARCH_QUERIES)})")

    print(f"[collect] 총 {len(results)}건 신규 수집", file=sys.stderr)
    return results[:MAX_ARTICLES]


def mark_seen(articles: list[dict[str, Any]]) -> None:
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    seen = _load_seen()
    today = datetime.now(timezone.utc).date().isoformat()
    for a in articles:
        if a.get("url"):
            seen[_hash_url(a["url"])] = today
    cutoff = (datetime.now(timezone.utc) - timedelta(days=SEEN_RETENTION_DAYS)).date().isoformat()
    seen = {h: d for h, d in seen.items() if d >= cutoff}
    SEEN_PATH.write_text(
        json.dumps(seen, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )


if __name__ == "__main__":
    json.dump(collect_all(), sys.stdout, ensure_ascii=False, indent=2)
