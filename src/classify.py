"""수집된 기사를 AI 관련 여부로 필터링하고 중요도별로 분류·요약.

Gemini 2.5 Flash 무료 쿼터: 10 RPM / 250K TPM / 500 RPD
배치당 20건, 배치 간 7초 대기 → 60건 기준 ~21초 소요.
429(ResourceExhausted) 시 지수 백오프 재시도.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

from google import genai
from google.genai import types
from google.genai.errors import ServerError, ClientError

MODEL = "gemini-2.5-flash"
MAX_PER_BUCKET = 5
BATCH_SIZE = 20
INTER_BATCH_DELAY = 7.0
MAX_RETRIES = 4
RETRY_BASE = 60.0

SYSTEM_PROMPT = """당신은 AI 업계 뉴스 큐레이터입니다.
입력된 기사 목록에서 다음 두 단계를 수행합니다.

[1단계] AI 관련성 필터
- 통과: LLM·생성형AI·머신러닝·딥러닝·AI 칩/하드웨어·AI 정책/규제·
  AI 스타트업/투자·AI 응용(에이전트·로보틱스·자율주행 등).
- 제외: AI와 무관한 일반 IT(모바일 신제품, 일반 보안, 게임, 가상화폐 등),
  AI 언급이 단순 키워드 수준에 그치는 경우.

[2단계] 중요도 3단계 분류 + 한국어 요약
- top: 업계 주요 발표·대형 모델 출시·정책·M&A (최대 5건)
- normal: 일반 뉴스·제품 업데이트·기업 동향 (최대 5건)
- fyi: 연구·arXiv·기타 참고 자료 (최대 5건)

각 항목 요약은 한국어 2~3문장. 원문 카테고리/출처는 그대로 보존.

응답은 반드시 아래 JSON 스키마만 출력 (다른 설명·마크다운 금지):
{
  "top":    [{"title": "...", "url": "...", "source": "...", "category": "...", "summary_ko": "..."}],
  "normal": [...],
  "fyi":    [...]
}
"""


def _call_with_retry(client: genai.Client, prompt: str) -> dict:
    delay = RETRY_BASE
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            return json.loads(response.text)
        except (ServerError, ClientError) as e:
            code = getattr(e, "code", 0) or getattr(e, "status_code", 0)
            retryable = code in (429, 500, 503)
            if not retryable or attempt == MAX_RETRIES - 1:
                raise
            wait = delay if code == 429 else min(delay, 30.0)
            print(
                f"[classify] {code} → {wait:.0f}초 후 재시도 ({attempt + 1}/{MAX_RETRIES - 1})",
                file=sys.stderr,
            )
            time.sleep(wait)
            delay *= 2
    return {}


def _merge(base: dict, extra: dict) -> dict:
    for key in ("top", "normal", "fyi"):
        base.setdefault(key, [])
        base[key].extend(extra.get(key, []))
    return base


def _cap(result: dict) -> dict:
    return {k: result.get(k, [])[:MAX_PER_BUCKET] for k in ("top", "normal", "fyi")}


def classify_articles(articles: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    if not articles:
        return {"top": [], "normal": [], "fyi": []}

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    batches = [articles[i : i + BATCH_SIZE] for i in range(0, len(articles), BATCH_SIZE)]
    merged: dict = {}

    for idx, batch in enumerate(batches):
        if idx > 0:
            print(f"[classify] 배치 간 {INTER_BATCH_DELAY:.0f}초 대기...", file=sys.stderr)
            time.sleep(INTER_BATCH_DELAY)

        prompt = (
            f"다음은 RSS에서 수집한 기사 {len(batch)}건입니다. "
            f"AI 관련만 통과시키고 중요도별로 분류·요약하세요.\n\n"
            f"```json\n{json.dumps(batch, ensure_ascii=False, indent=2)}\n```"
        )

        print(
            f"[classify] 배치 {idx + 1}/{len(batches)} ({len(batch)}건) 처리 중...",
            file=sys.stderr,
        )
        try:
            result = _call_with_retry(client, prompt)
            merged = _merge(merged, result)
        except Exception as e:
            print(f"[classify] 배치 {idx + 1} 실패 → 건너뜀: {e}", file=sys.stderr)

    if not merged:
        return _fallback_bucket(articles)

    return _cap(merged)


def _fallback_bucket(articles: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    items = [
        {
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "source": a.get("source", ""),
            "category": a.get("category", ""),
            "summary_ko": a.get("summary_raw", "")[:120],
        }
        for a in articles[: MAX_PER_BUCKET * 2]
    ]
    return {"top": [], "normal": items[:MAX_PER_BUCKET], "fyi": items[MAX_PER_BUCKET:]}


if __name__ == "__main__":
    articles = json.load(sys.stdin)
    json.dump(classify_articles(articles), sys.stdout, ensure_ascii=False, indent=2)
