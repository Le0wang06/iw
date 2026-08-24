"""Download every board listed in sources.json into the runner workspace."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

SOURCES_PATH = Path(__file__).with_name("sources.json")
UA = "InternMonkey (https://github.com/Le0wang06/iw, 1.0)"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read().decode("utf-8", errors="replace")


def main() -> None:
    Path("snapshots").mkdir(exist_ok=True)
    boards = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))["boards"]
    for board in boards:
        path = Path(board["file"])
        empty = board.get("empty", "")
        text = None
        for url in board["urls"]:
            try:
                text = fetch(url)
                break
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
                print(f"WARN {board['key']} {url}: {exc}", file=sys.stderr)
        path.write_text(text if text is not None else empty, encoding="utf-8")
        print(f"Fetched {board['key']}: {path.stat().st_size} bytes", file=sys.stderr)


if __name__ == "__main__":
    main()
