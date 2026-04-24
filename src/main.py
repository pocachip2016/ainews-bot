"""AI 뉴스 파이프라인: collect → classify → format → send."""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv

from src.classify import classify_articles
from src.collect import collect_all, mark_seen
from src.format_kakao import format_for_kakao
from src.kakao_send import send_kakao_memo


def _send_alert(text: str) -> None:
    try:
        send_kakao_memo({
            "object_type": "text",
            "text": text,
            "link": {"web_url": "https://www.google.com", "mobile_web_url": "https://www.google.com"},
        })
    except Exception as e:
        print(f"[alert] Kakao 알림 전송 실패: {e}", file=sys.stderr)


def run(dry_run: bool = False) -> int:
    load_dotenv()
    try:
        return _run(dry_run)
    except Exception as e:
        print(f"[main] 파이프라인 오류: {e}", file=sys.stderr)
        if not dry_run:
            _send_alert(f"🚨 AI 뉴스 파이프라인 오류\n{type(e).__name__}: {e}")
        return 1


def _run(dry_run: bool) -> int:
    print("[1/4] 수집 중...", file=sys.stderr)
    articles = collect_all(dry_run=dry_run)
    print(f"      → {len(articles)}건 수집", file=sys.stderr)
    if not articles:
        print("새 기사가 없습니다.", file=sys.stderr)
        if not dry_run:
            _send_alert("📭 AI 뉴스: 오늘 수집된 신규 기사가 없습니다.")
        return 0

    print("[2/4] 분류·요약...", file=sys.stderr)
    classified = classify_articles(articles)
    counts = {k: len(v) for k, v in classified.items()}
    print(f"      → top={counts.get('top',0)} normal={counts.get('normal',0)} fyi={counts.get('fyi',0)}", file=sys.stderr)

    print("[3/4] 카카오 메시지 포맷...", file=sys.stderr)
    messages = format_for_kakao(classified)
    print(f"      → {len(messages)}개 메시지 생성", file=sys.stderr)

    if dry_run:
        print("\n=== DRY RUN 출력 ===", file=sys.stderr)
        json.dump(messages, sys.stdout, ensure_ascii=False, indent=2)
        return 0

    print("[4/4] 카카오 전송...", file=sys.stderr)
    for i, msg in enumerate(messages, 1):
        result = send_kakao_memo(msg)
        print(f"      [{i}/{len(messages)}] {result}", file=sys.stderr)

    mark_seen(articles)
    print("완료.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="API 미호출, 샘플 데이터로 포맷만 확인")
    args = parser.parse_args()
    sys.exit(run(dry_run=args.dry_run))
