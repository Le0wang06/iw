"""Download every board listed in sources.json into the runner workspace."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SOURCES_PATH = Path(__file__).with_name("sources.json")
ETAGS_PATH = Path("snapshots/board-etags.json")
UA = "InternMonkey (https://github.com/Le0wang06/iw, 1.0)"


def load_etags() -> dict:
    if not ETAGS_PATH.exists():
        return {}
    try:
        data = json.loads(ETAGS_PATH.read_text(encoding="utf-8"))
    except (ValueError, OSError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def fetch(url: str, etag: str | None) -> tuple[str | None, str | None, int]:
    headers = {"User-Agent": UA}
    if etag:
        headers["If-None-Match"] = etag
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return text, resp.headers.get("ETag"), resp.status
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return None, etag, 304
        raise


def fetch_board(board: dict, etags: dict) -> tuple[str, int, dict | None]:
    path = Path(board["file"])
    empty = board.get("empty", "")
    key = board["key"]
    stored = etags.get(key) or {}
    last_exc = None
    for url in board["urls"]:
        prev = stored.get("etag") if stored.get("url") == url else None
        try:
            text, etag, status = fetch(url, prev)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last_exc = exc
            print(f"WARN {key} {url}: {exc}", file=sys.stderr)
            continue
        meta = {"url": url, "etag": etag} if etag else None
        if status == 304:
            return key, 304, meta
        path.write_text(text, encoding="utf-8")
        return key, path.stat().st_size, meta
    if last_exc is not None and not path.exists():
        path.write_text(empty, encoding="utf-8")
        return key, path.stat().st_size, None
    if not path.exists():
        path.write_text(empty, encoding="utf-8")
        return key, path.stat().st_size, None
    return key, path.stat().st_size, None


def main() -> None:
    Path("snapshots").mkdir(exist_ok=True)
    boards = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))["boards"]
    etags = load_etags()
    next_etags = dict(etags)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_board, board, etags): board for board in boards}
        for fut in as_completed(futures):
            key, size, meta = fut.result()
            if meta:
                next_etags[key] = meta
            if size == 304:
                print(f"Unchanged {key}", file=sys.stderr)
            else:
                print(f"Fetched {key}: {size} bytes", file=sys.stderr)
    ETAGS_PATH.write_text(json.dumps(next_etags, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
