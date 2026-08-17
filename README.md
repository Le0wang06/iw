# iw

GitHub Actions bot that emails you when new software engineering internship listings show up.

It checks two sources on a 30-minute schedule (and can be run by hand from the Actions tab):

1. **SimplifyJobs boards** — Summer 2026 main list and off-season list. Only **Software Engineering** rows with an active Apply link are alerted.
2. **Company ATS boards** — Greenhouse, Lever, and Ashby postings for **227 companies**. Filters to US intern / co-op roles that look like backend, infra, DevOps, or general SWE (frontend, mobile, hardware, and similar titles are skipped). ATS listings often appear before they land on LinkedIn or the Simplify boards.

When something new is found, you get an HTML email with company, role, location, and an Apply button. Seen listings are stored under `snapshots/` so the same role is not emailed twice.

## Setup

1. Fork this repo (or clone it and push to your own).
2. Enable **Actions** on the fork.
3. Add these repository secrets (`Settings` → `Secrets and variables` → `Actions`):

   | Secret | Purpose |
   | --- | --- |
   | `MAIL_USERNAME` | SMTP login, usually your Gmail address |
   | `MAIL_PASSWORD` | Gmail [app password](https://support.google.com/accounts/answer/185833) (not your normal password) |
   | `MAIL_TO` | Address that should receive alerts |

4. Trigger **Internship Board Watcher** and **ATS Board Watcher** once from the Actions tab to confirm mail works. The first run records the current boards and does not send a backlog of old listings.

## Adding companies

Edit `.github/workflow-scripts/ats_companies.json`. Each entry needs an ATS type, board slug, and display name:

```json
{
  "ats": "greenhouse",
  "slug": "stripe",
  "name": "Stripe"
}
```

`ats` must be `greenhouse`, `lever`, or `ashby`. The `slug` is the company identifier in that ATS URL.

## Layout

```
.github/workflows/          scheduled watchers
.github/workflow-scripts/   parsers and company list
snapshots/                  last-seen board state (committed by Actions)
```

## Credit

Board listings come from [SimplifyJobs](https://github.com/SimplifyJobs/Summer2026-Internships). Recreated from [internship-watcher](https://github.com/Yash-Swaminathan/internship-watcher) with permission.
