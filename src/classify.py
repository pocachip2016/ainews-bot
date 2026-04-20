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
RETRY_BASE = 120.0
SYSTEM_PROMPT = """너는 전문 AI 기술 분석가이자 뉴스레터 편집자야. 다음 4가지 카테고리에 대해 지난 24시간 동안의 최신 동향을 뉴스레터 형식으로 정리해줘.
1.주요 LLM 동향: Claude, Gemini, GPT 등 주요 모델의 업데이트, 성능 지표(벤치마크), 신규 기능 소식
2.엔지니어링 트렌드: 하네스(Harness) 및 에이전틱(Agentic) 엔지니어링, 멀티 에이전트 시스템 및 워크플로우 자동화 동향
3.생산성 도구: Obsidian, Typeless 등 AI 기반 개인 지식 관리 도구 및 관련 신규 플러그인 소식
4. 글로벌 산업 동향: AI ROI(비즈니스 가치), 월드 모델(World Models), 소버린 AI 및 엣지 AI 관련 주요 기업/국가 뉴스
5. 각 카테고리별로 가장 중요한 뉴스 3~5개를 선정하고, 핵심 요약과 관련 링크를 포함해줘. 마지막에는 오늘 학습하기 좋은 최신 AI 관련 영상 2~3개를 추천하고 짧은 추천 이유를 남겨줘.

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
