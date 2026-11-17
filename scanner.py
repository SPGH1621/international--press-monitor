"""Metadata-only index of public Telegram channel posts. No copyrighted PDFs downloaded."""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

CHANNEL = "demagazinesharing"
FEED = f"https://t.me/s/{CHANNEL}"
OUTPUT = Path(__file__).parent / "public" / "data.json"
MAX_PAGES = 6
MAX_ITEMS = 500
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PressMonitor/0.1; personal metadata indexer)",
    "Accept-Language": "en-US,en;q=0.9",
}

SOURCES = [
    ("economist", "The Economist", [r"\beconomist\b"]),
    ("ft", "Financial Times", [r"\bfinancial[\s_-]*times\b", r"\bft\b(?:[\s_-]*(?:asia|us|uk|europe|international))?"]),
    ("wsj", "The Wall Street Journal", [r"\bwall[\s_-]*street[\s_-]*journal\b", r"\bwsj\b"]),
    ("nyt", "The New York Times", [r"\bnew[\s_-]*york[\s_-]*times\b", r"\bnyt\b"]),
    ("barrons", "Barron's", [r"\bbarron['’]?s\b", r"\bbarrons\b"]),
    ("businessweek", "Bloomberg Businessweek", [r"\bbusiness[\s_-]*week\b"]),
]


def classify(filename: str) -> tuple[str, str] | None:
    name = filename.lower().replace(".", " ").replace("_", " ").replace("-", " ")
    for key, display, patterns in SOURCES:
        if any(re.search(p, name, flags=re.IGNORECASE) for p in patterns):
            return key, display
    return None


def safe_link(link: str) -> bool:
    parsed = urlparse(link)
    return parsed.scheme == "https" and parsed.netloc in ("t.me", "telegram.me") and parsed.path.startswith(f"/{CHANNEL}/")


def parse_page(html: str) -> tuple[list[dict], int | None, int]:
    soup = BeautifulSoup(html, "html.parser")
    elements = soup.select(".tgme_widget_message_wrap")
    results: list[dict] = []
    ids: list[int] = []
    for wrap in elements:
        post = wrap.select_one("[data-post]")
        post_ref = post.get("data-post", "") if post else ""
        id_part = str(post_ref).split("/")[-1]
        if not id_part.isdecimal():
            continue
        mid = int(id_part)
        ids.append(mid)
        message_link = f"https://t.me/{CHANNEL}/{mid}"
        dt = wrap.select_one(".tgme_widget_message_date time[datetime]")
        timestamp = dt.get("datetime", "") if dt else ""
        # Telegram's web preview exposes the document filename in this element.
        titles = [el.get_text(" ", strip=True) for el in wrap.select(".tgme_widget_message_document_title")]
        # Fallback: some post formats only include a filename in the caption.
        if not titles:
            caption = wrap.select_one(".tgme_widget_message_text")
            if caption:
                titles = re.findall(r"[^\n\r<>]{3,120}?\.pdf\b", caption.get_text("\n", strip=True), flags=re.IGNORECASE)
        for title in titles:
            filename = title.strip()
            if not filename.lower().endswith(".pdf"):
                continue
            source = classify(filename)
            if not source or not safe_link(message_link):
                continue
            results.append({
                "id": f"{mid}-{source[0]}",
                "source_id": source[0],
                "source": source[1],
                "filename": filename[:250],
                "message_id": mid,
                "posted_at": timestamp,
                "post_url": message_link,
            })
    return results, (min(ids) if ids else None), len(elements)


def load_previous() -> dict:
    if OUTPUT.exists():
        try:
            return json.loads(OUTPUT.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"items": [], "last_success_at": None}


def scan() -> dict:
    old = load_previous()
    prior = {item.get("id"): item for item in old.get("items", []) if item.get("id")}
    found: dict[str, dict] = {}
    older_than = None
    pages_fetched = 0
    message_count = 0
    seen_min_ids: set[int] = set()
    for _ in range(MAX_PAGES):
        params = {"before": older_than} if older_than else {}
        response = requests.get(FEED, params=params, headers=HEADERS, timeout=30)
        response.raise_for_status()
        items, min_id, wraps = parse_page(response.text)
        if wraps == 0:
            raise RuntimeError("Telegram web preview returned no message elements; access may be restricted")
        pages_fetched += 1
        message_count += wraps
        for item in items:
            found[item["id"]] = item
        if min_id is None or min_id in seen_min_ids:
            break
        seen_min_ids.add(min_id)
        older_than = min_id
        time.sleep(0.5)
    prior.update(found)
    merged = sorted(prior.values(), key=lambda item: item.get("message_id", 0), reverse=True)[:MAX_ITEMS]
    now = datetime.now(timezone.utc).isoformat()
    return {
        "channel": CHANNEL,
        "last_checked_at": now,
        "last_success_at": now,
        "status": "ok",
        "error": None,
        "pages_fetched": pages_fetched,
        "messages_scanned": message_count,
        "items": merged,
    }


def main() -> int:
    old = load_previous()
    try:
        data = scan()
        print(f"Scanned {data['messages_scanned']} posts, indexed {len(data['items'])} magazine PDFs")
    except Exception as exc:
        # Keep successful historical results, never erase on connection failure.
        data = {
            **old,
            "channel": CHANNEL,
            "last_checked_at": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "error": f"{type(exc).__name__}: {str(exc)[:170]}",
        }
        print("Scan failed; existing results preserved:", data["error"], file=sys.stderr)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0  # deploy error state to dashboard for transparent diagnostics


if __name__ == "__main__":
    raise SystemExit(main())
