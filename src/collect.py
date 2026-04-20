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


def _hash_url(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _load_seen() -> set[str]:
    if not SEEN_PATH.exists():
        return set()
    return set(json.loads(SEEN_PATH.read_text(encoding="utf-8")))


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
            feed = feedparser.parse(src["url"])
        except Exception as e:
            print(f"[collect] {src['name']} 파싱 실패: {e}", file=sys.stderr)
            continue

        picked = 0
        for entry in feed.entries:
            if picked >= MAX_PER_FEED:
                break
            url = entry.get("link", "")
            if not url or _hash_url(url) in seen:
                continue
            published = _entry_published(entry)
            if published and published < cutoff:
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

    return articles


def mark_seen(articles: list[dict[str, Any]]) -> None:
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    seen = _load_seen()
    for a in articles:
        if a.get("url"):
            seen.add(_hash_url(a["url"]))
    SEEN_PATH.write_text(json.dumps(sorted(seen), ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    json.dump(collect_all(), sys.stdout, ensure_ascii=False, indent=2)
