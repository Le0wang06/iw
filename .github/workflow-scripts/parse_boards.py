import html
import json
import os
import re
import sys
from pathlib import Path

from listing_util import (
    EARLY_ROLE_RE,
    display_key as listing_display_key,
    infer_track,
    is_priority,
    peer_display_ids,
)

TR_RE = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
ANCHOR_RE = re.compile(r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL | re.IGNORECASE)
APPLY_RE = re.compile(
    r'<a\s+href="([^"]+)"[^>]*>\s*<img[^>]*alt="Apply"',
    re.IGNORECASE,
)
POSTING_RE = re.compile(r"https://simplify\.jobs/p/([0-9a-fA-F-]{36})")
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^)]+)\)")
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")

SEEN_PATH = "snapshots/seen.json"
VERSION_PATH = "snapshots/watch-version.json"
WATCH_VERSION = 4
BARE_URL_RE = re.compile(r"https?://[^\s)<>\"']+")
BOARDS = json.loads(
    Path(__file__).with_name("sources.json").read_text(encoding="utf-8")
)["boards"]


def strip_html(fragment: str) -> str:
    fragment = fragment.replace("<br>", " · ").replace("<br/>", " · ").replace("<br />", " · ")
    fragment = TAG_RE.sub("", fragment)
    fragment = html.unescape(fragment)
    return WHITESPACE_RE.sub(" ", fragment).strip()


def row_id(block: str, company: str, role: str, location: str, apply_url: str) -> str:
    m = POSTING_RE.search(block)
    if m:
        return "p:" + m.group(1).lower()
    if apply_url:
        return "a:" + apply_url.split("?")[0].rstrip("/")
    slug = f"{company}|{role}|{location}".lower()
    slug = slug.replace("🎓", "").replace("🛂", "").replace("🇺🇸", "")
    return "t:" + WHITESPACE_RE.sub(" ", slug).strip()


def parse_simplify(path: str) -> dict:
    """Active listings from Simplify-style HTML tables. All categories."""
    if not os.path.exists(path):
        return {}
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    rows = {}
    last_company = None
    for block in TR_RE.findall(text):
        tds = TD_RE.findall(block)
        if len(tds) < 4:
            continue
        first_td_stripped = strip_html(tds[0])
        anchors = ANCHOR_RE.findall(tds[0])
        if anchors:
            company_name = strip_html(anchors[0][1])
            last_company = company_name
        elif "↳" in first_td_stripped and last_company:
            company_name = last_company
        else:
            continue
        role = strip_html(tds[1])
        location = strip_html(tds[2])
        terms = strip_html(tds[3]) if len(tds) >= 5 else ""
        apply_match = APPLY_RE.search(block)
        if not apply_match:
            hrefs = [href for href, _ in ANCHOR_RE.findall(block)]
            hrefs = [h for h in hrefs if "simplify.jobs/c/" not in h]
            apply_url = hrefs[-1] if hrefs else ""
        else:
            apply_url = apply_match.group(1)
        if not apply_url or "🔒" in block:
            continue
        rid = row_id(block, company_name, role, location, apply_url)
        rows[rid] = {
            "company": company_name,
            "role": role,
            "location": location,
            "apply_url": apply_url,
            "terms": terms,
        }
    return rows


def parse_markdown(path: str) -> dict:
    """Markdown tables used by Vansh/Ouckah and similar lists."""
    if not os.path.exists(path):
        return {}
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    rows = {}
    last_company = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cols = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cols) < 4:
            continue
        if cols[0].lower() in {"company", "name"}:
            continue
        if set(cols[0]) <= set("-: "):
            continue
        company_raw = strip_html(cols[0])
        if "↳" in company_raw and last_company:
            company_name = last_company
        else:
            company_name = company_raw
            last_company = company_name
        role = strip_html(cols[1])
        location = strip_html(cols[2])
        blob = " ".join(cols)
        hrefs = [h for h, _ in ANCHOR_RE.findall(blob)]
        hrefs += [url for _, url in MD_LINK_RE.findall(blob)]
        hrefs += BARE_URL_RE.findall(blob)
        apply_url = next((u for u in hrefs if u.startswith("http")), "")
        if not apply_url or "🔒" in line:
            continue
        terms = ""
        for col in cols[3:]:
            cell = strip_html(col)
            if re.search(r"winter|spring|summer|fall|2026|2027", cell, re.I):
                terms = cell
                break
        rid = row_id(line, company_name, role, location, apply_url)
        rows[rid] = {
            "company": company_name,
            "role": role,
            "location": location,
            "apply_url": apply_url,
            "terms": terms,
        }
    return rows


def _jobs_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("jobs", "items", "results", "data"):
            val = data.get(key)
            if isinstance(val, list):
                return val
            if isinstance(val, dict) and isinstance(val.get("jobs"), list):
                return val["jobs"]
    return []


def parse_jobs_json(path: str, early_only: bool = False) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    except (ValueError, OSError):
        return {}
    rows = {}
    for job in _jobs_list(data):
        if not isinstance(job, dict) or job.get("is_closed"):
            continue
        company = str(job.get("company") or "").strip()
        role = str(job.get("title") or job.get("role") or "").strip()
        location = job.get("location") or ""
        if isinstance(location, list):
            location = " / ".join(str(x) for x in location if x)
        location = str(location).strip()
        apply_url = str(
            job.get("listingUrl") or job.get("url") or job.get("apply_url") or ""
        ).strip()
        if not company or not role or not apply_url:
            continue
        if early_only and not EARLY_ROLE_RE.search(role):
            continue
        category = job.get("category")
        if isinstance(category, dict):
            category = category.get("name") or ""
        terms = str(job.get("season") or category or job.get("program") or "")
        jid = str(job.get("id") or apply_url)
        rid = "j:" + jid
        rows[rid] = {
            "company": company,
            "role": role,
            "location": location,
            "apply_url": apply_url,
            "terms": terms,
        }
    return rows


PARSERS = {
    "simplify": parse_simplify,
    "markdown": parse_markdown,
    "jobsjson": parse_jobs_json,
}


def parse_board(board: dict) -> dict:
    parser = PARSERS[board["parser"]]
    if board["parser"] == "jobsjson":
        return parser(board["file"], early_only=board.get("early_only", False))
    return parser(board["file"])


def load_seen() -> tuple:
    if os.path.exists(SEEN_PATH):
        try:
            return set(json.loads(Path(SEEN_PATH).read_text(encoding="utf-8"))), True
        except (ValueError, OSError):
            pass
    seeded = set()
    for path in ("snapshots/previous-main.md", "snapshots/previous-offseason.md",
                 "snapshots/previous-summer.md"):
        rows = parse_simplify(path)
        seeded |= set(rows)
        seeded |= {display_id(row) for row in rows.values()}
    return seeded, False


def load_version() -> int:
    if not os.path.exists(VERSION_PATH):
        return 1
    try:
        data = json.loads(Path(VERSION_PATH).read_text(encoding="utf-8"))
        return int(data.get("version", 1))
    except (ValueError, OSError, TypeError):
        return 1


def save_version() -> None:
    Path(VERSION_PATH).parent.mkdir(exist_ok=True)
    Path(VERSION_PATH).write_text(
        json.dumps({"version": WATCH_VERSION}) + "\n", encoding="utf-8"
    )


def save_seen(seen: set) -> None:
    Path(SEEN_PATH).parent.mkdir(exist_ok=True)
    Path(SEEN_PATH).write_text(
        json.dumps(sorted(seen), indent=0) + "\n", encoding="utf-8"
    )


def display_key(it: dict) -> str:
    return listing_display_key(it["company"], it["role"], it["location"])


def display_id(it: dict) -> str:
    return "d:" + display_key(it)


def dedupe_sections(sections: list) -> list:
    shown = set()
    out = []
    for title, items in sections:
        kept = []
        for it in items:
            k = display_key(it)
            if k in shown:
                continue
            shown.add(k)
            kept.append(it)
        out.append((title, kept))
    return out


def render_html(sections: list) -> str:
    def section(title: str, items: list) -> str:
        if not items:
            return (
                f'<h2 style="font-size:15px;color:#666;margin:20px 0 6px;">'
                f'{html.escape(title)}</h2>'
                f'<p style="color:#999;font-size:13px;margin:0 0 12px;">No new roles.</p>'
            )
        parts = [
            f'<h2 style="font-size:15px;color:#111;margin:20px 0 8px;'
            f'border-bottom:1px solid #ddd;padding-bottom:4px;">'
            f'{html.escape(title)} · {len(items)} new</h2>'
        ]
        parts.append('<table cellpadding="0" cellspacing="0" border="0" '
                     'style="width:100%;border-collapse:collapse;">')
        for it in items:
            extra = it.get("terms") or ""
            extra_html = (
                f'<div style="font-size:12px;color:#2563eb;margin-top:2px;">'
                f'{html.escape(extra)}</div>'
                if extra else ""
            )
            apply_cell = (
                f'<a href="{html.escape(it["apply_url"])}" '
                f'style="display:inline-block;padding:6px 14px;background:#2563eb;'
                f'color:#fff;text-decoration:none;border-radius:4px;font-size:13px;'
                f'font-weight:600;">Apply</a>'
                if it["apply_url"]
                else '<span style="color:#999;font-size:12px;">no direct link</span>'
            )
            parts.append(
                '<tr>'
                '<td style="padding:10px 0;border-bottom:1px solid #eee;vertical-align:top;">'
                f'<div style="font-weight:600;font-size:14px;color:#111;">'
                f'{html.escape(it["company"])}</div>'
                f'<div style="font-size:14px;color:#333;margin-top:2px;">'
                f'{html.escape(it["role"])}</div>'
                f'<div style="font-size:12px;color:#666;margin-top:2px;">'
                f'{html.escape(it["location"])}</div>'
                f'{extra_html}'
                '</td>'
                '<td style="padding:10px 0;border-bottom:1px solid #eee;'
                'vertical-align:middle;text-align:right;white-space:nowrap;">'
                f'{apply_cell}'
                '</td>'
                '</tr>'
            )
        parts.append('</table>')
        return "\n".join(parts)

    total = sum(len(items) for _, items in sections)
    body = "".join(section(title, items) for title, items in sections)
    return (
        '<html><body style="font-family:-apple-system,BlinkMacSystemFont,'
        '\'Segoe UI\',Roboto,sans-serif;background:#f7f7f7;margin:0;padding:20px;">'
        '<div style="max-width:640px;margin:0 auto;background:#fff;padding:24px;'
        'border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.08);">'
        f'<h1 style="font-size:18px;margin:0 0 4px;color:#111;">'
        f'{total} new listing{"s" if total != 1 else ""}</h1>'
        '<p style="font-size:12px;color:#888;margin:0 0 8px;">'
        'Summer 2027, Winter 2027 / off-season, new grad, and extra boards. '
        'All roles, not just SWE.</p>'
        f'{body}'
        '<hr style="border:0;border-top:1px solid #eee;margin:20px 0 8px;">'
        '<p style="color:#aaa;font-size:11px;margin:0;">'
        'Sent by iw · '
        '<a href="https://github.com/Le0wang06/iw/actions" '
        'style="color:#aaa;">workflow logs</a></p>'
        '</div></body></html>'
    )


def render_plain(sections: list) -> str:
    total = sum(len(items) for _, items in sections)
    lines = [f"{total} new listing(s)", ""]
    for title, items in sections:
        lines.append(f"== {title}: {len(items)} new ==")
        if not items:
            lines.append("  (none)")
        for it in items:
            lines.append(f"  {it['company']} - {it['role']}")
            lines.append(f"    Location: {it['location']}")
            if it.get("terms"):
                lines.append(f"    Terms: {it['terms']}")
            lines.append(f"    Apply: {it['apply_url'] or '(no direct link)'}")
        lines.append("")
    return "\n".join(lines)


def build_subject(sections: list) -> str:
    items = [it for _, group in sections for it in group]
    total = len(items)
    if total == 0:
        return "No new internship listings"
    companies = list(dict.fromkeys(it["company"] for it in items))
    preview = ", ".join(companies[:3])
    suffix = f" +{len(companies) - 3} more" if len(companies) > 3 else ""
    plural = "s" if total != 1 else ""
    return f"{total} new role{plural}: {preview}{suffix}"


def main():
    seen, had_seen_file = load_seen()
    reseeding = load_version() < WATCH_VERSION or (not had_seen_file and not seen)

    parsed_boards = []
    for board in BOARDS:
        rows = parse_board(board)
        parsed_boards.append((board, rows))
        print(f"Parsed {board['key']}: {len(rows)}", file=sys.stderr)

    peer = peer_display_ids("boards")

    def is_new(rid, row):
        did = display_id(row)
        return rid not in seen and did not in seen and did not in peer

    sections = []
    for board, rows in parsed_boards:
        new_items = [row for rid, row in rows.items() if is_new(rid, row)]
        if reseeding:
            new_items = []
        sections.append((board["title"], new_items))
        seen |= set(rows)
        seen |= {display_id(row) for row in rows.values()}

    sections = dedupe_sections(sections)
    save_seen(seen)
    save_version()

    total = sum(len(items) for _, items in sections)
    print(f"seen={len(seen)} reseeding={'yes' if reseeding else 'no'} total_new={total}")

    html_body = render_html(sections)
    plain_body = render_plain(sections)
    subject = build_subject(sections)

    if total:
        Path("alert.md").write_text(
            f"{plain_body}\n",
            encoding="utf-8",
        )
        jobs = []
        for title, group in sections:
            for it in group:
                jobs.append(
                    {
                        "company": it["company"],
                        "role": it["role"],
                        "location": it["location"],
                        "url": it["apply_url"],
                        "source": title,
                        "terms": it.get("terms") or "",
                        "track": infer_track(it["role"], it.get("terms") or ""),
                    }
                )
        jobs.sort(
            key=lambda it: (
                0 if is_priority(it["company"]) else 1,
                it["source"],
                it["company"].lower(),
                it["role"].lower(),
            )
        )
        Path("new_jobs.json").write_text(
            json.dumps(
                {"kind": "boards", "subject": subject, "items": jobs},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        print("---HTML---")
        print(html_body[:800])
        print("---PLAIN---")
        print(plain_body)
        print("---SUBJECT---")
        print(subject)
        return

    with open(output_path, "a", encoding="utf-8") as f:
        f.write(f"total={total}\n")
        f.write(f"subject={subject}\n")
        f.write("html_body<<HTMLEOF\n")
        f.write(html_body)
        f.write("\nHTMLEOF\n")
        f.write("plain_body<<PLAINEOF\n")
        f.write(plain_body)
        f.write("\nPLAINEOF\n")


if __name__ == "__main__":
    main()
