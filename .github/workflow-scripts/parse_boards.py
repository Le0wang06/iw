import html
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
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def strip_html(fragment: str) -> str:
    fragment = fragment.replace("<br>", " · ").replace("<br/>", " · ").replace("<br />", " · ")
    fragment = TAG_RE.sub("", fragment)
    fragment = html.unescape(fragment)
    return WHITESPACE_RE.sub(" ", fragment).strip()


def parse_rows(path: str) -> dict:
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
        apply_match = APPLY_RE.search(tds[3])
        apply_url = apply_match.group(1) if apply_match else ""
        key = (company_name, role, location)
        rows[key] = {
            "company": company_name,
            "role": role,
            "location": location,
            "apply_url": apply_url,
        }
    return rows


def diff(previous: dict, current: dict) -> list:
    if not previous:
        return []
    return [current[k] for k in current if k not in previous]


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
        'Detected on the SimplifyJobs Summer 2026 boards.</p>'
        f'{section("Main Board (Summer 2026)", new_main)}'
        f'{section("Off-Season Board", new_off)}'
        '<hr style="border:0;border-top:1px solid #eee;margin:20px 0 8px;">'
        '<p style="color:#aaa;font-size:11px;margin:0;">'
        'Sent by internship-watcher · '
        '<a href="https://github.com/Yash-Swaminathan/internship-watcher/actions" '
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
    prev_main = parse_rows("snapshots/previous-main.md")
    curr_main = parse_rows("current-main.md")
    prev_off = parse_rows("snapshots/previous-offseason.md")
    curr_off = parse_rows("current-offseason.md")

    new_main = diff(prev_main, curr_main)
    new_off = diff(prev_off, curr_off)
    total = len(new_main) + len(new_off)

    print(f"Parsed: prev_main={len(prev_main)} curr_main={len(curr_main)} "
          f"prev_off={len(prev_off)} curr_off={len(curr_off)}")
    print(f"New: main={len(new_main)} off={len(new_off)} total={total}")

    html_body = render_html(new_main, new_off)
    plain_body = render_plain(new_main, new_off)
    subject = build_subject(new_main, new_off)

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
