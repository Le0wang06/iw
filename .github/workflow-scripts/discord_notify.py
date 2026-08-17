"""Post new_jobs.json to Discord from GitHub Actions.

Uses DISCORD_BOT_TOKEN + DISCORD_CHANNEL_ID, or DISCORD_WEBHOOK_URL.
Missing config skips cleanly so forks without secrets still pass.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

JOBS_PATH = Path("new_jobs.json")
API = "https://discord.com/api/v10"
USER_AGENT = "InternSeek (https://github.com/Le0wang06/iw, 1.0)"

TERM_RULES = [
    (re.compile(r"winter\s*2027|off[- ]season|off[- ]cycle", re.I), "Winter 2027"),
    (re.compile(r"fall\s*2026", re.I), "Fall 2026"),
    (re.compile(r"spring\s*2027", re.I), "Spring 2027"),
    (re.compile(r"summer\s*2027|\bsummer\b", re.I), "Summer 2027"),
    (re.compile(r"new[- ]?grad|university grad|early career", re.I), "New Grad"),
    (re.compile(r"co[- ]?op", re.I), "Co-op"),
    (re.compile(r"intern", re.I), "Internship"),
]

TERM_COLORS = {
    "Winter 2027": 0x22D3EE,
    "Fall 2026": 0xF59E0B,
    "Spring 2027": 0x34D399,
    "Summer 2027": 0x3B82F6,
    "New Grad": 0xA78BFA,
    "Co-op": 0x14B8A6,
    "Internship": 0x059669,
}


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


def infer_term(it: dict, kind: str) -> str:
    text = " ".join(
        str(it.get(k) or "") for k in ("terms", "source", "role", "company")
    )
    for rx, label in TERM_RULES:
        if rx.search(text):
            return label
    if kind == "ats":
        return "Internship"
    return "Internship / New Grad"


def role_type(it: dict, term: str) -> str:
    role = it.get("role") or ""
    if re.search(r"new[- ]?grad|university grad|early career", role, re.I) or term == "New Grad":
        return "New Grad (full-time)"
    if re.search(r"co[- ]?op", role, re.I) or term == "Co-op":
        return "Co-op"
    return "Internship"


def job_embed(it: dict, kind: str) -> dict:
    company = (it.get("company") or "Company").strip() or "Company"
    role = (it.get("role") or "Role not listed").strip()
    loc = (it.get("location") or "Not listed").strip() or "Not listed"
    source = (it.get("source") or "").strip() or (
        "Company ATS" if kind == "ats" else "Internship board"
    )
    url = (it.get("url") or "").strip()
    term = infer_term(it, kind)
    rtype = role_type(it, term)
    apply_line = f"\n[Apply]({url})" if url.startswith("http") else ""

    embed = {
        "author": {"name": company[:256]},
        "title": role[:256],
        "description": (
            f"**{rtype}**\n"
            f"**Term:** {term}\n"
            f"**Location:** {loc}"
            f"{apply_line}"
        )[:4096],
        "color": TERM_COLORS.get(term, 0x2563EB),
        "footer": {"text": f"{source} · InternSeek"},
    }
    if url.startswith("http"):
        embed["url"] = url
    return embed


def apply_button(it: dict) -> list:
    url = (it.get("url") or "").strip()
    if not url.startswith("http"):
        return []
    company = (it.get("company") or "Apply").strip() or "Apply"
    return [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 5,
                    "label": f"Apply · {company}"[:80],
                    "url": url,
                }
            ],
        }
    ]


def payloads(data: dict) -> list:
    kind = data.get("kind") or "boards"
    items = sorted(
        data["items"],
        key=lambda it: (
            infer_term(it, kind),
            (it.get("company") or "").lower(),
            (it.get("role") or "").lower(),
        ),
    )
    n = len(items)
    noun = "listing" if n == 1 else "listings"
    out = []
    for i, it in enumerate(items):
        body = {
            "embeds": [job_embed(it, kind)],
            "components": apply_button(it),
            "allowed_mentions": {"parse": []},
        }
        if i == 0:
            body["content"] = f"**{n} new {noun}**"
        out.append(body)
    return out


def post_json(url: str, body: dict, headers: dict) -> None:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
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
    headers = {"User-Agent": USER_AGENT}
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
