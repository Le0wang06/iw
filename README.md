# iw

GitHub Actions bot that alerts **Leo** (`@Le0wang06`) when new software engineering internship listings show up.

It checks two sources every 30 minutes (and can be run by hand from the Actions tab):

1. **SimplifyJobs boards** — Summer 2026/2027 main list and off-season list. Only **Software Engineering** rows with an active Apply link are alerted.
2. **Company ATS boards** — Greenhouse, Lever, and Ashby postings for **227 companies**. Filters to US intern / co-op roles that look like backend, infra, DevOps, or general SWE (frontend, mobile, hardware, and similar titles are skipped). ATS listings often appear before they land on LinkedIn or the Simplify boards.

When something new is found:

- A GitHub issue is opened and `@Le0wang06` is mentioned (this is the default alert path).
- If `MAIL_PASSWORD` is set, an HTML email also goes to **098leowang@gmail.com**.

Seen listings are stored under `snapshots/` so the same role is not alerted twice.

## Setup (this repo)

`MAIL_USERNAME` and `MAIL_TO` are already set to `098leowang@gmail.com`.

To also get Gmail (not just GitHub issue notifications):

1. Create a Gmail [app password](https://support.google.com/accounts/answer/185833) (Google Account → Security → 2-Step Verification → App passwords).
2. Add it as the repository secret `MAIL_PASSWORD` at [Settings → Secrets](https://github.com/Le0wang06/iw/settings/secrets/actions). Use the app password, not your normal Gmail password.

Both workflows are enabled on a 30-minute schedule.

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
