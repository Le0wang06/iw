"""Post new_jobs.json to Discord from GitHub Actions.

Uses DISCORD_BOT_TOKEN + DISCORD_CHANNEL_ID, or DISCORD_WEBHOOK_URL.
Missing config skips cleanly so forks without secrets still pass.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

JOBS_PATH = Path("new_jobs.json")
API = "https://discord.com/api/v10"
CHUNK = 8


def load_jobs() -> dict | None:
    if not JOBS_PATH.exists():
        return None
    try:
        data = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if not data.get("items"):
        return None
    return data


def chunked(items: list, size: int) -> list:
    return [items[i : i + size] for i in range(0, len(items), size)]


def embed_for(kind: str, subject: str, items: list, page: int, pages: int) -> dict:
    color = 0x059669 if kind == "ats" else 0x2563EB
    title = subject if pages == 1 else f"{subject} ({page}/{pages})"
    fields = []
    for it in items:
        name = (it.get("company") or "Company")[:256]
        role = it.get("role") or ""
        loc = it.get("location") or "Location not listed"
        extra = it.get("terms") or it.get("source") or ""
        url = it.get("url") or ""
        lines = [role, loc]
        if extra and extra != loc:
            lines.append(extra)
        if url:
            lines.append(f"[Apply]({url})")
        value = "\n".join(lines)[:1024]
        fields.append({"name": name, "value": value or "—", "inline": False})
    return {
        "title": title[:256],
        "color": color,
        "fields": fields,
        "footer": {"text": "iw · github.com/Le0wang06/iw"},
    }


def buttons_for(items: list) -> list:
    row = []
    for it in items[:5]:
        url = it.get("url") or ""
        if not url.startswith("http"):
            continue
        label = (it.get("company") or "Apply")[:80]
        row.append({"type": 2, "style": 5, "label": label, "url": url})
    if not row:
        return []
    return [{"type": 1, "components": row}]


def payloads(data: dict) -> list:
    kind = data.get("kind") or "boards"
    subject = data.get("subject") or "New listings"
    items = data["items"]
    pages = chunked(items, CHUNK)
    out = []
    for i, group in enumerate(pages, start=1):
        body = {
            "embeds": [embed_for(kind, subject, group, i, len(pages))],
            "components": buttons_for(group),
            "allowed_mentions": {"parse": []},
        }
        if i == 1:
            body["content"] = f"**{subject}**"
        out.append(body)
    return out


def post_json(url: str, body: dict, headers: dict) -> None:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")[:500]
        raise SystemExit(f"Discord HTTP {err.code}: {detail}") from err


def send(body: dict) -> None:
    token = (os.environ.get("DISCORD_BOT_TOKEN") or "").strip()
    channel = (os.environ.get("DISCORD_CHANNEL_ID") or "").strip()
    webhook = (os.environ.get("DISCORD_WEBHOOK_URL") or "").strip()
    headers = {"Content-Type": "application/json"}
    if webhook:
        post_json(webhook, body, headers)
        return
    if token and channel:
        headers["Authorization"] = f"Bot {token}"
        post_json(f"{API}/channels/{channel}/messages", body, headers)
        return
    print("Discord secrets not set; skipping")
    sys.exit(0)


def main() -> None:
    data = load_jobs()
    if not data:
        print("No new_jobs.json; skipping Discord")
        return
    for body in payloads(data):
        send(body)
    print(f"Posted {len(data['items'])} listing(s) to Discord")


if __name__ == "__main__":
    main()
