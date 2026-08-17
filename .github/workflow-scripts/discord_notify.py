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
from collections import Counter
from pathlib import Path

JOBS_PATH = Path("new_jobs.json")
API = "https://discord.com/api/v10"
JOBS_PER_MESSAGE = 4
BANNER_PATH = Path(__file__).resolve().parents[2] / "assets" / "discord-banner.png"
BANNER_REMOTE = (
    "https://raw.githubusercontent.com/Le0wang06/iw/main/assets/discord-banner.png"
)

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

KIND_LABEL = {
    "ats": "Company career page (ATS)",
    "boards": "Internship board",
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


def chunked(items: list, size: int) -> list:
    return [items[i : i + size] for i in range(0, len(items), size)]


def blob(it: dict) -> str:
    return " ".join(
        str(it.get(k) or "")
        for k in ("terms", "source", "role", "company")
    )


def infer_term(it: dict, kind: str) -> str:
    text = blob(it)
    for rx, label in TERM_RULES:
        if rx.search(text):
            return label
    if kind == "ats":
        return "Internship"
    return "Internship / New Grad"


def job_kind_line(it: dict, term: str) -> str:
    role = it.get("role") or ""
    if re.search(r"new[- ]?grad|university grad|early career", role, re.I) or term == "New Grad":
        return "Full-time new-grad role"
    if re.search(r"co[- ]?op", role, re.I) or term == "Co-op":
        return "Co-op"
    if term in {"Summer 2027", "Winter 2027", "Fall 2026", "Spring 2027"}:
        return f"{term} internship"
    return "Internship / co-op"


def header_embed(kind: str, items: list, counts: Counter, attach: bool) -> dict:
    n = len(items)
    noun = "listing" if n == 1 else "listings"
    lines = [
        f"**{n} new {noun}** just opened.",
        "",
    ]
    for term, count in counts.most_common():
        extra = " role" if count == 1 else " roles"
        lines.append(f"• **{term}** — {count}{extra}")
    lines += [
        "",
        KIND_LABEL.get(kind, "Internship watcher"),
        "Each card below is one job. Open **Apply** for the full description.",
    ]
    embed = {
        "title": "New internship & new-grad roles",
        "description": "\n".join(lines)[:4096],
        "color": 0x2563EB,
        "footer": {"text": "iw · InternSeek"},
    }
    if attach and BANNER_PATH.exists():
        embed["image"] = {"url": "attachment://discord-banner.png"}
    else:
        embed["image"] = {"url": BANNER_REMOTE}
    return embed


def job_embed(it: dict, kind: str) -> dict:
    company = (it.get("company") or "Company").strip() or "Company"
    role = (it.get("role") or "Role not listed").strip()
    loc = (it.get("location") or "Not listed").strip() or "Not listed"
    source = (
        (it.get("source") or "").strip()
        or KIND_LABEL.get(kind, "Internship board")
    )
    url = (it.get("url") or "").strip()
    term = infer_term(it, kind)
    notes = (it.get("terms") or "").strip()
    kind_line = job_kind_line(it, term)

    description = (
        f"**{kind_line}** at **{company}**.\n\n"
        f"This alert is the posting title, term, and apply link. "
        f"The full job description lives on the application page."
    )
    if notes and notes.lower() not in {
        term.lower(),
        loc.lower(),
        role.lower(),
        source.lower(),
    }:
        description += f"\n\n_{notes[:400]}_"

    embed = {
        "author": {"name": company[:256]},
        "title": role[:256],
        "description": description[:4096],
        "color": TERM_COLORS.get(term, 0x2563EB),
        "fields": [
            {"name": "Term", "value": term[:1024], "inline": True},
            {"name": "Location", "value": loc[:1024], "inline": True},
            {"name": "Source", "value": source[:1024], "inline": False},
        ],
        "footer": {"text": "iw · InternSeek"},
    }
    if url.startswith("http"):
        embed["url"] = url
    return embed


def buttons_for(items: list) -> list:
    row = []
    seen = set()
    for it in items:
        url = (it.get("url") or "").strip()
        if not url.startswith("http") or url in seen:
            continue
        seen.add(url)
        company = (it.get("company") or "Apply").strip() or "Apply"
        label = f"Apply · {company}"[:80]
        row.append({"type": 2, "style": 5, "label": label, "url": url})
        if len(row) == 5:
            break
    if not row:
        return []
    return [{"type": 1, "components": row}]


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
    counts = Counter(infer_term(it, kind) for it in items)
    groups = chunked(items, JOBS_PER_MESSAGE)
    out = []
    for i, group in enumerate(groups):
        embeds = []
        if i == 0:
            embeds.append(header_embed(kind, items, counts, attach=BANNER_PATH.exists()))
        embeds.extend(job_embed(it, kind) for it in group)
        n = len(items)
        noun = "listing" if n == 1 else "listings"
        body = {
            "embeds": embeds,
            "components": buttons_for(group),
            "allowed_mentions": {"parse": []},
        }
        if i == 0:
            body["content"] = f"**{n} new {noun}**"
        elif len(groups) > 1:
            body["content"] = f"**More listings** ({i + 1}/{len(groups)})"
        out.append(body)
    return out


def post_json(url: str, body: dict, headers: dict, banner: bytes | None) -> None:
    if banner and any(
        (e.get("image") or {}).get("url") == "attachment://discord-banner.png"
        for e in body.get("embeds", [])
    ):
        post_multipart(url, body, headers, banner)
        return
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    _send(req)


def post_multipart(url: str, body: dict, headers: dict, banner: bytes) -> None:
    boundary = "----iwDiscordFormBoundary"
    payload = json.dumps(body).encode("utf-8")
    chunks = [
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="payload_json"\r\n',
        b"Content-Type: application/json\r\n\r\n",
        payload,
        b"\r\n",
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="files[0]"; '
        b'filename="discord-banner.png"\r\n',
        b"Content-Type: image/png\r\n\r\n",
        banner,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    data = b"".join(chunks)
    hdrs = dict(headers)
    hdrs["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    _send(req)


def _send(req: urllib.request.Request) -> None:
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")[:500]
        raise SystemExit(f"Discord HTTP {err.code}: {detail}") from err


def send(body: dict, banner: bytes | None) -> None:
    token = (os.environ.get("DISCORD_BOT_TOKEN") or "").strip()
    channel = (os.environ.get("DISCORD_CHANNEL_ID") or "").strip()
    webhook = (os.environ.get("DISCORD_WEBHOOK_URL") or "").strip()
    headers = {
        "User-Agent": "InternSeek (https://github.com/Le0wang06/iw, 1.0)",
    }
    if webhook:
        post_json(webhook, body, headers, banner)
        return
    if token and channel:
        headers["Authorization"] = f"Bot {token}"
        post_json(f"{API}/channels/{channel}/messages", body, headers, banner)
        return
    print("Discord secrets not set; skipping")
    sys.exit(0)


def main() -> None:
    data = load_jobs()
    if not data:
        print("No new_jobs.json; skipping Discord")
        return
    banner = BANNER_PATH.read_bytes() if BANNER_PATH.exists() else None
    for body in payloads(data):
        send(body, banner)
    print(f"Posted {len(data['items'])} listing(s) to Discord")


if __name__ == "__main__":
    main()
