"""Post new_jobs.json to Discord from GitHub Actions.

Uses DISCORD_BOT_TOKEN + DISCORD_CHANNEL_ID, or DISCORD_WEBHOOK_URL.
Missing config skips cleanly so forks without secrets still pass.
Never fails the workflow: a bad listing or a Discord blip must not
email the owner every two minutes.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from listing_util import infer_term, infer_track, is_priority, role_type

JOBS_PATH = Path("new_jobs.json")
API = "https://discord.com/api/v10"
USER_AGENT = "InternMonkey (https://github.com/Le0wang06/iw, 1.0)"
URL_RE = re.compile(r"^https://[^\s<>\"']+$", re.I)

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


def clean_url(url: str) -> str:
    url = (url or "").strip().rstrip(").,]>\"'")
    if not URL_RE.match(url) or len(url) > 512:
        return ""
    return url


def job_term(it: dict, kind: str) -> str:
    return infer_term(
        it.get("terms") or "",
        it.get("source") or "",
        it.get("role") or "",
        it.get("company") or "",
        kind=kind,
    )


def job_track(it: dict) -> str:
    return it.get("track") or infer_track(it.get("role") or "", it.get("terms") or "")


def job_embed(it: dict, kind: str) -> dict:
    company = (it.get("company") or "Company").strip() or "Company"
    role = (it.get("role") or "Role not listed").strip()
    loc = (it.get("location") or "Not listed").strip() or "Not listed"
    source = (it.get("source") or "").strip() or (
        "Company ATS" if kind == "ats" else "Internship board"
    )
    url = clean_url(it.get("url") or "")
    term = job_term(it, kind)
    track = job_track(it)
    rtype = role_type(role, term)
    apply_line = f"\n[Apply]({url})" if url else ""
    embed = {
        "author": {"name": company[:256]},
        "title": role[:256],
        "description": (
            f"**{rtype}** · {track}\n"
            f"**Term:** {term}\n"
            f"**Location:** {loc}"
            f"{apply_line}"
        )[:4096],
        "color": TERM_COLORS.get(term, 0x2563EB),
        "footer": {"text": f"{source} · InternMonkey"[:2048]},
    }
    if url:
        embed["url"] = url
    return embed


def apply_button(it: dict) -> list:
    url = clean_url(it.get("url") or "")
    if not url:
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
            0 if is_priority(it.get("company") or "") else 1,
            job_term(it, kind),
            job_track(it),
            (it.get("company") or "").lower(),
            (it.get("role") or "").lower(),
        ),
    )
    n = len(items)
    noun = "listing" if n == 1 else "listings"
    counts = Counter(job_term(it, kind) for it in items)
    summary = " · ".join(f"{term} ({count})" for term, count in counts.most_common())
    header = (f"**{n} new {noun}**" + (f" · {summary}" if summary else ""))[:2000]
    out = []
    for i, it in enumerate(items):
        body = {
            "embeds": [job_embed(it, kind)],
            "allowed_mentions": {"parse": []},
        }
        components = apply_button(it)
        if components:
            body["components"] = components
        if i == 0:
            body["content"] = header
        out.append(body)
    return out


def post_json(url: str, body: dict, headers: dict) -> bool:
    data = json.dumps(body).encode("utf-8")
    req_headers = {**headers, "Content-Type": "application/json"}
    for attempt in range(6):
        req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
            return True
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", errors="replace")[:400]
            if err.code == 429:
                wait = err.headers.get("Retry-After") or "2"
                try:
                    delay = min(float(wait), 15.0)
                except ValueError:
                    delay = 2.0
                print(f"Discord 429; retry in {delay}s", file=sys.stderr)
                time.sleep(delay + 0.4)
                continue
            print(f"Discord HTTP {err.code}: {detail}", file=sys.stderr)
            return False
        except (urllib.error.URLError, TimeoutError) as err:
            print(f"Discord network error: {err}", file=sys.stderr)
            if attempt < 5:
                time.sleep(1.5)
                continue
            return False
    print("Discord still rate-limited; skipping this listing", file=sys.stderr)
    return False


def send(body: dict) -> bool:
    token = (os.environ.get("DISCORD_BOT_TOKEN") or "").strip()
    channel = (os.environ.get("DISCORD_CHANNEL_ID") or "").strip()
    webhook = (os.environ.get("DISCORD_WEBHOOK_URL") or "").strip()
    headers = {"User-Agent": USER_AGENT}
    if webhook:
        return post_json(webhook, body, headers)
    if token and channel:
        headers["Authorization"] = f"Bot {token}"
        return post_json(f"{API}/channels/{channel}/messages", body, headers)
    print("Discord secrets not set; skipping")
    return True


def main() -> None:
    data = load_jobs()
    if not data:
        print("No new_jobs.json; skipping Discord")
        return
    posted = 0
    bodies = payloads(data)
    for i, body in enumerate(bodies):
        if send(body):
            posted += 1
        if i + 1 < len(bodies):
            time.sleep(0.35)
    print(f"Posted {posted}/{len(bodies)} listing(s) to Discord")


if __name__ == "__main__":
    main()
