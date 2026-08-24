"""Poll company ATS boards (Greenhouse / Lever / Ashby) for new US
intern, co-op, and new-grad roles.

Postings hit the ATS before LinkedIn or the SimplifyJobs boards pick them
up, so this is the fastest signal. Companies live in ats_companies.json.
"""

import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from listing_util import (
    EARLY_ROLE_RE,
    display_key as listing_display_key,
    infer_track,
    is_priority,
    peer_display_ids,
)

SCRIPT_DIR = Path(__file__).resolve().parent
COMPANIES_PATH = SCRIPT_DIR / "ats_companies.json"
SEEN_PATH = Path("snapshots/ats-seen.json")
VERSION_PATH = Path("snapshots/ats-watch-version.json")
WATCH_VERSION = 4

# Keep out non-tech recruiting noise. Everything else intern-shaped is kept:
# SWE, frontend, mobile, data, PM, hardware, ML, security, quant, etc.
EXCLUDE_RE = re.compile(
    r"\bsales\b|account executive|recruiter|recruiting intern|"
    r"people (ops|partner)|human resources|\bhr intern\b|"
    r"legal intern|paralegal|accounting intern|facilities intern",
    re.I,
)

US_HINT_RE = re.compile(
    r"united states|\busa?\b|u\.s\.|remote.*(us|america)|"
    r"alabama|alaska|arizona|arkansas|california|colorado|connecticut|"
    r"delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|"
    r"kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|"
    r"mississippi|missouri|montana|nebraska|nevada|new hampshire|"
    r"new jersey|new mexico|new york|north carolina|north dakota|ohio|"
    r"oklahoma|oregon|pennsylvania|rhode island|south carolina|"
    r"south dakota|tennessee|texas|utah|vermont|virginia|washington|"
    r"west virginia|wisconsin|wyoming|"
    r"san francisco|\bnyc\b|seattle|austin|boston|chicago|denver|atlanta|"
    r"los angeles|mountain view|palo alto|sunnyvale|san jose|menlo park|"
    r"bellevue|redmond|\bd\.?c\.?\b|miami|dallas|houston|philadelphia|"
    r"pittsburgh|portland|san diego|santa clara|cupertino|irvine|"
    r"nashville|charlotte|phoenix|salt lake|"
    r",\s?(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|"
    r"MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|"
    r"TN|TX|UT|VT|VA|WA|WV|WI|WY)\b",
    re.I,
)

NON_US_RE = re.compile(
    r"canada|ontario|toronto|vancouver|montr[eé]al|quebec|calgary|ottawa|"
    r"waterloo|british columbia|united kingdom|\buk\b|london|ireland|"
    r"dublin|germany|berlin|munich|france|paris|netherlands|amsterdam|"
    r"belgium|spain|madrid|barcelona|portugal|lisbon|italy|milan|"
    r"switzerland|zurich|geneva|austria|vienna|poland|warsaw|krakow|"
    r"czech|prague|sweden|stockholm|norway|oslo|denmark|copenhagen|"
    r"finland|helsinki|estonia|tallinn|romania|bucharest|hungary|"
    r"budapest|israel|tel aviv|\buae\b|dubai|abu dhabi|saudi|riyadh|"
    r"india|bangalore|bengaluru|hyderabad|mumbai|delhi|gurgaon|gurugram|"
    r"chennai|pune|noida|singapore|malaysia|kuala lumpur|indonesia|"
    r"jakarta|vietnam|thailand|bangkok|philippines|manila|china|beijing|"
    r"shanghai|shenzhen|hangzhou|hong kong|taiwan|taipei|japan|tokyo|"
    r"osaka|korea|seoul|australia|sydney|melbourne|brisbane|new zealand|"
    r"auckland|brazil|paulo|mexico|guadalajara|argentina|buenos aires|"
    r"colombia|bogot|chile|santiago|nigeria|lagos|egypt|cairo|kenya|"
    r"nairobi|south africa|turkey|istanbul|ukraine|kyiv|serbia|belgrade|"
    r"bulgaria|sofia|croatia|zagreb|lithuania|vilnius|latvia|riga|"
    r"armenia|yerevan|cyprus|malta|luxembourg|emea|apac|latam|"
    r",\s?(?-i:ON|QC|BC|AB|MB|SK|NS|NB|NL|PE|YT)\b",
    re.I,
)

WHITESPACE_RE = re.compile(r"\s+")


def wanted_title(title: str) -> bool:
    if not EARLY_ROLE_RE.search(title):
        return False
    if EXCLUDE_RE.search(title):
        return False
    return True


def is_us(location: str) -> bool:
    """US hint wins, then a clearly-foreign hint loses; ambiguous strings
    (bare "Remote", city-only names) are kept rather than dropped."""
    if not location:
        return True
    if US_HINT_RE.search(location):
        return True
    if NON_US_RE.search(location):
        return False
    return True


def fetch_json(url: str, data=None):
    last_err = None
    for _ in range(2):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 InternMonkey/1.0",
                "Accept": "application/json",
            }
            body = None
            method = "GET"
            if data is not None:
                headers["Content-Type"] = "application/json"
                headers["Accept-Language"] = "en-US"
                body = json.dumps(data).encode("utf-8")
                method = "POST"
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 - retry once, then report
            last_err = e
    raise last_err


def workday_jobs(company: dict) -> list:
    host = company["host"]
    tenant = company["tenant"]
    site = company["site"]
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    searches = company.get("search") or ["Internship", "new college graduate"]
    out, seen_ids = [], set()
    for search in searches:
        offset = 0
        for _ in range(12):
            data = fetch_json(
                url,
                {
                    "appliedFacets": {},
                    "limit": 20,
                    "offset": offset,
                    "searchText": search,
                },
            )
            postings = data.get("jobPostings") or []
            if not postings:
                break
            for job in postings:
                path = job.get("externalPath") or ""
                jid = path or job.get("title") or ""
                if not jid or jid in seen_ids:
                    continue
                seen_ids.add(jid)
                out.append(
                    {
                        "id": f"w:{tenant}:{jid}",
                        "title": job.get("title") or "",
                        "location": job.get("locationsText") or "",
                        "url": f"https://{host}/en-US/{site}{path}",
                    }
                )
            offset += 20
            if offset >= int(data.get("total") or 0):
                break
    return out


def phenom_jobs(company: dict) -> list:
    api = company["api"]
    domain = company.get("domain") or company["slug"]
    job_url = company.get("job_url") or f"https://explore.jobs.{domain}/careers/job/"
    queries = company.get("query") or ["intern", "new grad"]
    out, seen_ids = [], set()
    for query in queries:
        start = 0
        for _ in range(8):
            url = (
                api
                + "?domain="
                + urllib.parse.quote(domain)
                + "&start="
                + str(start)
                + "&num=50&query="
                + urllib.parse.quote(query)
            )
            data = fetch_json(url)
            positions = data.get("positions") or []
            if not positions:
                break
            for job in positions:
                jid = str(job.get("id") or job.get("ats_job_id") or "")
                if not jid or jid in seen_ids:
                    continue
                seen_ids.add(jid)
                locs = job.get("locations") or []
                location = " / ".join(str(x) for x in locs if x) or (
                    job.get("location") or ""
                )
                out.append(
                    {
                        "id": f"p:{company['slug']}:{jid}",
                        "title": job.get("name") or job.get("posting_name") or "",
                        "location": location,
                        "url": job_url.rstrip("/") + "/" + jid,
                    }
                )
            start += 50
            count = int(data.get("count") or 0)
            if start >= count:
                break
    return out


def oracle_jobs(company: dict) -> list:
    host = company["host"]
    site = company.get("site") or "CX"
    keywords = company.get("keywords") or ["internship", "new graduate"]
    apply = company.get("apply") or (
        f"https://{host}/hcmUI/CandidateExperience/en/sites/"
        f"{company.get('slug', 'careers')}/job/"
    )
    out, seen_ids = [], set()
    for keyword in keywords:
        offset = 0
        for _ in range(12):
            finder = (
                "findReqs;keyword="
                + urllib.parse.quote(keyword, safe="")
                + f",siteNumber={site},limit=25,offset={offset}"
            )
            url = (
                f"https://{host}/hcmRestApi/resources/latest/"
                "recruitingCEJobRequisitions?onlyData=true"
                "&expand=requisitionList.workLocation&finder="
                + finder
            )
            data = fetch_json(url)
            item = (data.get("items") or [{}])[0]
            jobs = item.get("requisitionList") or []
            if not jobs:
                break
            for job in jobs:
                jid = str(job.get("Id") or "")
                if not jid or jid in seen_ids:
                    continue
                country = str(job.get("PrimaryLocationCountry") or "").upper()
                if country and country not in {"US", "USA"}:
                    continue
                seen_ids.add(jid)
                work = job.get("workLocation") or []
                if isinstance(work, dict):
                    work = [work]
                loc_names = [
                    w.get("Name") or w.get("PrimaryLocation") or ""
                    for w in work
                    if isinstance(w, dict)
                ]
                location = " / ".join(x for x in loc_names if x) or str(
                    job.get("PrimaryLocationCountry") or ""
                )
                out.append(
                    {
                        "id": f"o:{company['slug']}:{jid}",
                        "title": job.get("Title") or "",
                        "location": location,
                        "url": apply.rstrip("/") + "/" + jid,
                    }
                )
            offset += 25
            if offset >= int(item.get("TotalJobsCount") or 0):
                break
    return out


TWOSIGMA_JOB_RE = re.compile(
    r'href="(?:https://careers\.twosigma\.com)?(/careers/JobDetail/([^"/]+)/(\d+))"',
    re.I,
)


def _twosigma_title_loc(slug: str) -> tuple:
    for marker, loc_end in (
        ("United-States-", "United States"),
        ("United-Kingdom-of-Great-Britain-and-Northern-Ireland-", "United Kingdom"),
        ("United-Kingdom-", "United Kingdom"),
    ):
        idx = slug.find(marker)
        if idx >= 0:
            loc = slug[:idx].replace("-", " ").strip() + ", " + loc_end
            title = slug[idx + len(marker) :].replace("-", " ").strip()
            return title, loc
    return slug.replace("-", " "), ""


def html_jobs(company: dict) -> list:
    out, seen_ids = [], set()
    for page_url in company.get("urls") or []:
        req = urllib.request.Request(
            page_url,
            headers={"User-Agent": "Mozilla/5.0 InternMonkey/1.0"},
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            html_text = resp.read().decode("utf-8", "replace")
        for path, slug, jid in TWOSIGMA_JOB_RE.findall(html_text):
            if jid in seen_ids:
                continue
            seen_ids.add(jid)
            title, location = _twosigma_title_loc(slug)
            out.append(
                {
                    "id": f"h:{company['slug']}:{jid}",
                    "title": title,
                    "location": location,
                    "url": "https://careers.twosigma.com" + path,
                }
            )
    return out


def board_jobs(company: dict) -> list:
    """Return [{id, title, location, url}] for one company's board."""
    ats, slug = company["ats"], company["slug"]
    if ats == "workday":
        return workday_jobs(company)
    if ats == "phenom":
        return phenom_jobs(company)
    if ats == "oracle":
        return oracle_jobs(company)
    if ats == "html":
        return html_jobs(company)
    if ats == "greenhouse":
        data = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
        return [
            {
                "id": f"g:{slug}:{j['id']}",
                "title": j["title"],
                "location": (j.get("location") or {}).get("name", ""),
                "url": j.get("absolute_url", ""),
            }
            for j in data.get("jobs", [])
        ]
    if ats == "lever":
        data = fetch_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
        return [
            {
                "id": f"l:{slug}:{j.get('id', j.get('hostedUrl', ''))}",
                "title": j.get("text", ""),
                "location": (j.get("categories") or {}).get("location") or "",
                "url": j.get("hostedUrl", ""),
            }
            for j in data
        ]
    if ats == "ashby":
        data = fetch_json(
            "https://api.ashbyhq.com/posting-api/job-board/"
            + urllib.parse.quote(slug)
        )
        jobs = []
        for j in data.get("jobs", []):
            locs = [j.get("location", "")] + [
                s.get("location", "") for s in j.get("secondaryLocations", [])
            ]
            jobs.append(
                {
                    "id": f"a:{slug}:{j.get('id', j.get('jobUrl', ''))}",
                    "title": j.get("title", ""),
                    "location": " / ".join(x for x in locs if x),
                    "url": j.get("jobUrl") or j.get("applyUrl", ""),
                }
            )
        return jobs
    raise ValueError(f"unknown ats {ats!r}")


def display_id(company_name: str, it: dict) -> str:
    return "d:" + listing_display_key(company_name, it["title"], it.get("location") or "")


def collect_matches() -> tuple:
    """Fetch every board; return (matches, failed_names). A failed board is
    skipped for this run — its ids stay in seen, so nothing re-alerts."""
    companies = json.loads(COMPANIES_PATH.read_text(encoding="utf-8"))
    matches, failed = [], []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(board_jobs, c): c for c in companies}
        for fut in as_completed(futures):
            c = futures[fut]
            try:
                jobs = fut.result()
            except Exception as e:  # noqa: BLE001 - one bad board can't kill the run
                failed.append(c["name"])
                print(f"WARN: {c['ats']}:{c['slug']} failed: {e}", file=sys.stderr)
                continue
            for j in jobs:
                if wanted_title(j["title"]) and is_us(j["location"]):
                    j["company"] = c["name"]
                    matches.append(j)
    matches.sort(
        key=lambda j: (
            0 if is_priority(j["company"]) else 1,
            j["company"].lower(),
            j["title"].lower(),
        )
    )
    return matches, failed


def render_html(items: list) -> str:
    rows = []
    for it in items:
        rows.append(
            '<tr>'
            '<td style="padding:10px 0;border-bottom:1px solid #eee;vertical-align:top;">'
            f'<div style="font-weight:600;font-size:14px;color:#111;">'
            f'{html.escape(it["company"])}</div>'
            f'<div style="font-size:14px;color:#333;margin-top:2px;">'
            f'{html.escape(it["title"])}</div>'
            f'<div style="font-size:12px;color:#666;margin-top:2px;">'
            f'{html.escape(it["location"] or "Location not listed")}</div>'
            '</td>'
            '<td style="padding:10px 0;border-bottom:1px solid #eee;'
            'vertical-align:middle;text-align:right;white-space:nowrap;">'
            f'<a href="{html.escape(it["url"])}" '
            f'style="display:inline-block;padding:6px 14px;background:#059669;'
            f'color:#fff;text-decoration:none;border-radius:4px;font-size:13px;'
            f'font-weight:600;">Apply</a>'
            '</td>'
            '</tr>'
        )
    return (
        '<html><body style="font-family:-apple-system,BlinkMacSystemFont,'
        '\'Segoe UI\',Roboto,sans-serif;background:#f7f7f7;margin:0;padding:20px;">'
        '<div style="max-width:640px;margin:0 auto;background:#fff;padding:24px;'
        'border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.08);">'
        f'<h1 style="font-size:18px;margin:0 0 4px;color:#111;">'
        f'{len(items)} new intern / new-grad role{"s" if len(items) != 1 else ""}</h1>'
        '<p style="font-size:12px;color:#888;margin:0 0 8px;">'
        'Straight from company ATS boards (Greenhouse / Lever / Ashby) — '
        'intern, co-op, and new-grad roles.</p>'
        '<table cellpadding="0" cellspacing="0" border="0" '
        'style="width:100%;border-collapse:collapse;">'
        + "\n".join(rows) +
        '</table>'
        '<hr style="border:0;border-top:1px solid #eee;margin:20px 0 8px;">'
        '<p style="color:#aaa;font-size:11px;margin:0;">'
        'Sent by iw (ATS) · '
        '<a href="https://github.com/Le0wang06/iw/actions" '
        'style="color:#aaa;">workflow logs</a></p>'
        '</div></body></html>'
    )


def render_plain(items: list) -> str:
    lines = [f"{len(items)} new intern / new-grad role(s)", ""]
    for it in items:
        lines.append(f"  {it['company']} - {it['title']}")
        lines.append(f"    Location: {it['location'] or '(not listed)'}")
        lines.append(f"    Apply: {it['url']}")
    return "\n".join(lines)


def build_subject(items: list) -> str:
    if not items:
        return "No new ATS intern / new-grad roles"
    unique = list(dict.fromkeys(it["company"] for it in items))
    preview = ", ".join(unique[:3])
    suffix = f" +{len(unique) - 3} more" if len(unique) > 3 else ""
    plural = "s" if len(items) != 1 else ""
    return f"{len(items)} new intern / new-grad role{plural} (ATS): {preview}{suffix}"


def load_ats_version() -> int:
    if not VERSION_PATH.exists():
        return 1
    try:
        return int(json.loads(VERSION_PATH.read_text(encoding="utf-8")).get("version", 1))
    except (ValueError, OSError, TypeError):
        return 1


def main():
    matches, failed = collect_matches()

    first_run = not SEEN_PATH.exists()
    seen = set()
    if not first_run:
        try:
            seen = set(json.loads(SEEN_PATH.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            first_run = True
    reseeding = first_run or load_ats_version() < WATCH_VERSION
    peer = peer_display_ids("ats")

    new, shown = [], set()
    for it in matches:
        did = display_id(it["company"], it)
        if it["id"] in seen or did in seen or did in peer:
            continue
        dkey = did
        if dkey in shown:
            continue
        shown.add(dkey)
        new.append(it)

    for it in matches:
        seen.add(it["id"])
        seen.add(display_id(it["company"], it))
    SEEN_PATH.parent.mkdir(exist_ok=True)
    SEEN_PATH.write_text(
        json.dumps(sorted(seen), indent=0) + "\n", encoding="utf-8"
    )
    VERSION_PATH.write_text(
        json.dumps({"version": WATCH_VERSION}) + "\n", encoding="utf-8"
    )

    if reseeding:
        # No history, or the match filter just expanded: record without emailing.
        new = []

    print(f"Matches: {len(matches)} across boards, failed_boards={len(failed)} "
          f"{failed if failed else ''}")
    print(f"New: {len(new)} reseeding={'yes' if reseeding else 'no'}")

    total = len(new)
    subject = build_subject(new)
    html_body = render_html(new)
    plain_body = render_plain(new)

    if total:
        Path("alert.md").write_text(
            f"{plain_body}\n",
            encoding="utf-8",
        )
        Path("new_jobs.json").write_text(
            json.dumps(
                {
                    "kind": "ats",
                    "subject": subject,
                    "items": [
                        {
                            "company": it["company"],
                            "role": it["title"],
                            "location": it["location"],
                            "url": it["url"],
                            "source": f"{it['company']} ATS",
                            "terms": "",
                            "track": infer_track(it["title"]),
                        }
                        for it in new
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        print("---SUBJECT---")
        print(subject)
        print("---PLAIN---")
        print(plain_body)
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
