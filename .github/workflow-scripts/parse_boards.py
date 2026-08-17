import html
import json
import os
import re
import sys
from pathlib import Path

TR_RE = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
COMPANY_RE = re.compile(
    r'<a\s+href="(https://simplify\.jobs/c/[^"]+)"[^>]*>([^<]+)</a>'
)
APPLY_RE = re.compile(
    r'<a\s+href="([^"]+)"[^>]*>\s*<img[^>]*alt="Apply"',
    re.IGNORECASE,
)
POSTING_RE = re.compile(r"https://simplify\.jobs/p/([0-9a-fA-F-]{36})")
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")

SEEN_PATH = "snapshots/seen.json"

# Both boards group listings under "## <emoji> <Category> Internship Roles"
# headers. Only the Software Engineering section should produce alerts —
# Product, Data Science/AI/ML, Quant, and Hardware rows are skipped.
SWE_SECTION_RE = re.compile(
    r"^##[^\n]*Software Engineering Internship Roles(.*?)(?=^## |\Z)",
    re.DOTALL | re.MULTILINE,
)


def swe_section(text: str) -> str:
    m = SWE_SECTION_RE.search(text)
    if m:
        return m.group(1)
    # Header not found (board format changed): fall back to the whole file
    # so new roles are never silently dropped.
    print("WARNING: Software Engineering section header not found; "
          "parsing entire board", file=sys.stderr)
    return text


def strip_html(fragment: str) -> str:
    fragment = fragment.replace("<br>", " · ").replace("<br/>", " · ").replace("<br />", " · ")
    fragment = TAG_RE.sub("", fragment)
    fragment = html.unescape(fragment)
    return WHITESPACE_RE.sub(" ", fragment).strip()


def row_id(block: str, company: str, role: str, location: str, apply_url: str) -> str:
    # The simplify.jobs/p/<uuid> link is the only identifier that survives
    # edits to the row's text (role renamed, locations added, 🎓 tags, etc.).
    m = POSTING_RE.search(block)
    if m:
        return "p:" + m.group(1).lower()
    if apply_url:
        return "a:" + apply_url.split("?")[0].rstrip("/")
    slug = f"{company}|{role}|{location}".lower()
    slug = slug.replace("🎓", "").replace("🛂", "").replace("🇺🇸", "")
    return "t:" + WHITESPACE_RE.sub(" ", slug).strip()


def parse_rows(path: str) -> dict:
    """Return {stable_id: row} for every ACTIVE listing in the board file.

    Rows without an Apply link are closed/archived listings (the boards embed
    an "Inactive roles" archive with thousands of old rows) and are skipped —
    they were the source of old internships being emailed as new.
    """
    if not os.path.exists(path):
        return {}
    text = swe_section(Path(path).read_text(encoding="utf-8", errors="replace"))
    rows = {}
    last_company = None
    for block in TR_RE.findall(text):
        tds = TD_RE.findall(block)
        if len(tds) < 4:
            continue
        first_td_stripped = strip_html(tds[0])
        m = COMPANY_RE.search(tds[0])
        if m:
            company_name = strip_html(m.group(2))
            last_company = company_name
        elif "↳" in first_td_stripped and last_company:
            company_name = last_company
        else:
            continue
        role = strip_html(tds[1])
        location = strip_html(tds[2])
        # The apply cell is tds[3] on the main board but tds[4] on the
        # off-season board (extra "Terms" column), so search the whole row.
        apply_match = APPLY_RE.search(block)
        if not apply_match or "🔒" in block:
            continue
        apply_url = apply_match.group(1)
        rid = row_id(block, company_name, role, location, apply_url)
        rows[rid] = {
            "company": company_name,
            "role": role,
            "location": location,
            "apply_url": apply_url,
        }
    return rows


def load_seen() -> tuple:
    """Return (seen_ids, exists). Falls back to seeding from the previous
    snapshots the first time so the switch-over doesn't spam or miss rows."""
    if os.path.exists(SEEN_PATH):
        try:
            return set(json.loads(Path(SEEN_PATH).read_text(encoding="utf-8"))), True
        except (ValueError, OSError):
            pass
    seeded = set()
    for path in ("snapshots/previous-main.md", "snapshots/previous-offseason.md"):
        rows = parse_rows(path)
        seeded |= set(rows)
        seeded |= {display_id(row) for row in rows.values()}
    return seeded, False


def save_seen(seen: set) -> None:
    Path(SEEN_PATH).parent.mkdir(exist_ok=True)
    Path(SEEN_PATH).write_text(
        json.dumps(sorted(seen), indent=0) + "\n", encoding="utf-8"
    )


def display_key(it: dict) -> tuple:
    role = it["role"].replace("🎓", "").replace("🛂", "").replace("🇺🇸", "")
    return (
        it["company"].strip().lower(),
        WHITESPACE_RE.sub(" ", role).strip().lower(),
        it["location"].strip().lower(),
    )


def display_id(it: dict) -> str:
    # Persisted alongside posting ids so a re-posted role with identical
    # company/role/location (new req id) is never emailed a second time.
    return "d:" + "|".join(display_key(it))


def dedupe_for_display(new_main: list, new_off: list) -> tuple:
    """Never show the same internship twice in one email, even when it
    appears on both boards or under multiple posting ids."""
    shown = set()
    out_main, out_off = [], []
    for items, out in ((new_main, out_main), (new_off, out_off)):
        for it in items:
            k = display_key(it)
            if k in shown:
                continue
            shown.add(k)
            out.append(it)
    return out_main, out_off


def render_html(new_main: list, new_off: list) -> str:
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
                '</td>'
                '<td style="padding:10px 0;border-bottom:1px solid #eee;'
                'vertical-align:middle;text-align:right;white-space:nowrap;">'
                f'{apply_cell}'
                '</td>'
                '</tr>'
            )
        parts.append('</table>')
        return "\n".join(parts)

    total = len(new_main) + len(new_off)
    return (
        '<html><body style="font-family:-apple-system,BlinkMacSystemFont,'
        '\'Segoe UI\',Roboto,sans-serif;background:#f7f7f7;margin:0;padding:20px;">'
        '<div style="max-width:640px;margin:0 auto;background:#fff;padding:24px;'
        'border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.08);">'
        f'<h1 style="font-size:18px;margin:0 0 4px;color:#111;">'
        f'{total} new internship listing{"s" if total != 1 else ""}</h1>'
        '<p style="font-size:12px;color:#888;margin:0 0 8px;">'
        'Software engineering roles on the SimplifyJobs Summer 2026 boards.</p>'
        f'{section("Main Board (Summer 2026)", new_main)}'
        f'{section("Off-Season Board", new_off)}'
        '<hr style="border:0;border-top:1px solid #eee;margin:20px 0 8px;">'
        '<p style="color:#aaa;font-size:11px;margin:0;">'
        'Sent by iw · '
        '<a href="https://github.com/Le0wang06/iw/actions" '
        'style="color:#aaa;">workflow logs</a></p>'
        '</div></body></html>'
    )


def render_plain(new_main: list, new_off: list) -> str:
    total = len(new_main) + len(new_off)
    lines = [f"{total} new internship listing(s)", ""]
    for title, items in [("MAIN BOARD (Summer 2026)", new_main), ("OFF-SEASON BOARD", new_off)]:
        lines.append(f"== {title}: {len(items)} new ==")
        if not items:
            lines.append("  (none)")
        for it in items:
            lines.append(f"  {it['company']} - {it['role']}")
            lines.append(f"    Location: {it['location']}")
            lines.append(f"    Apply: {it['apply_url'] or '(no direct link)'}")
        lines.append("")
    return "\n".join(lines)


def build_subject(new_main: list, new_off: list) -> str:
    total = len(new_main) + len(new_off)
    if total == 0:
        return "No new internship listings"
    companies = [it["company"] for it in new_main + new_off]
    unique = list(dict.fromkeys(companies))
    preview = ", ".join(unique[:3])
    suffix = f" +{len(unique) - 3} more" if len(unique) > 3 else ""
    plural = "s" if total != 1 else ""
    return f"{total} new internship{plural}: {preview}{suffix}"


def main():
    curr_main = parse_rows("current-main.md")
    curr_off = parse_rows("current-offseason.md")

    seen, had_seen_file = load_seen()
    first_run = not had_seen_file and not seen

    def is_new(rid, row):
        return rid not in seen and display_id(row) not in seen

    new_main = [row for rid, row in curr_main.items() if is_new(rid, row)]
    new_off = [
        row for rid, row in curr_off.items()
        if is_new(rid, row) and rid not in curr_main
    ]
    new_main, new_off = dedupe_for_display(new_main, new_off)

    if first_run:
        # No history at all: record the current boards without emailing.
        new_main, new_off = [], []

    for rows in (curr_main, curr_off):
        seen |= set(rows)
        seen |= {display_id(row) for row in rows.values()}
    save_seen(seen)

    total = len(new_main) + len(new_off)
    print(f"Parsed: curr_main={len(curr_main)} curr_off={len(curr_off)} "
          f"seen={len(seen)} seen_file={'yes' if had_seen_file else 'seeded'}")
    print(f"New: main={len(new_main)} off={len(new_off)} total={total}")

    html_body = render_html(new_main, new_off)
    plain_body = render_plain(new_main, new_off)
    subject = build_subject(new_main, new_off)

    if total:
        Path("alert.md").write_text(
            f"@Le0wang06\n\n{plain_body}\n",
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
