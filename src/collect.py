"""RSS 피드를 파싱해 최근 24시간 기사를 수집하고 중복 제거."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import feedparser
import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT / "config" / "sources.yaml"
SEEN_PATH = ROOT / "data" / "seen.json"
MAX_PER_FEED = 5
WINDOW_HOURS = 24
SEEN_RETENTION_DAYS = 30
FEEDPARSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AiNewsBot/1.0; +https://github.com/pocachip2016/ainews-bot)"
}


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


def _entry_published(entry: Any) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = getattr(entry, key, None) or entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def _strip_html(text: str) -> str:
    import re

    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def collect_all() -> list[dict[str, Any]]:
    sources = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8"))
    seen = _load_seen()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)

    articles: list[dict[str, Any]] = []
    for src in sources:
        try:
            feed = feedparser.parse(src["url"], request_headers=FEEDPARSER_HEADERS)
        except Exception as e:
            print(f"[collect] {src['name']} 파싱 실패: {e}", file=sys.stderr)
            continue

        http_status = getattr(feed, "status", None)
        total = len(feed.entries)
        if http_status and http_status >= 400:
            print(f"[collect] {src['name']} HTTP {http_status} — 건너뜀", file=sys.stderr)
            continue

        picked = 0
        skipped_seen = 0
        skipped_old = 0
        for entry in feed.entries:
            if picked >= MAX_PER_FEED:
                break
            url = entry.get("link", "")
            if not url or _hash_url(url) in seen:
                skipped_seen += 1
                continue
            published = _entry_published(entry)
            if published and published < cutoff:
                skipped_old += 1
                continue
            articles.append(
                {
                    "title": entry.get("title", "").strip(),
                    "url": url,
                    "source": src["name"],
                    "category": src.get("category", ""),
                    "region": src.get("region", ""),
                    "published": published.isoformat() if published else "",
                    "summary_raw": _strip_html(entry.get("summary", ""))[:400],
                }
            )
            picked += 1
        print(
            f"[collect] {src['name']}: 전체={total} 신규={picked} 기수집={skipped_seen} 오래됨={skipped_old}",
            file=sys.stderr,
        )

    return articles


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
