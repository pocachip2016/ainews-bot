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


def run(dry_run: bool = False) -> int:
    load_dotenv()

    print("[1/4] 수집 중...", file=sys.stderr)
    articles = collect_all()
    print(f"      → {len(articles)}건 수집", file=sys.stderr)
    if not articles:
        print("새 기사가 없습니다. 종료.", file=sys.stderr)
        return 0

    print("[2/4] Claude 분류·요약...", file=sys.stderr)
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
    parser.add_argument("--dry-run", action="store_true", help="전송 없이 메시지만 출력")
    args = parser.parse_args()
    sys.exit(run(dry_run=args.dry_run))
