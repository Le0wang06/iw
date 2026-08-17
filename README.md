# iw

GitHub Actions bot that emails **Leo** (`098leowang@gmail.com`) when new software engineering internship listings show up.

It checks two sources every 30 minutes:

1. **SimplifyJobs boards** — [Summer 2027](https://github.com/SimplifyJobs/Summer2027-Internships) main list and off-season list. Only **Software Engineering** rows with an active Apply link are alerted.
2. **Company ATS boards** — Greenhouse, Lever, and Ashby postings for **227 companies**. Filters to US intern / co-op roles that look like backend, infra, DevOps, or general SWE.

When something new is found, an HTML email goes to **098leowang@gmail.com**. A GitHub issue is also opened and `@Le0wang06` is mentioned.

Seen listings are stored under `snapshots/` so the same role is not alerted twice.

## Status

Mail and Actions are already configured on this repo:

| Secret | Value |
| --- | --- |
| `MAIL_USERNAME` | `098leowang@gmail.com` |
| `MAIL_TO` | `098leowang@gmail.com` |
| `MAIL_PASSWORD` | Gmail app password (stored in GitHub Actions secrets) |

**Internship Board Watcher** runs at `:00` and `:30`. **ATS Board Watcher** runs at `:15` and `:45`. Quiet checks do not send mail.

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

Board listings come from [SimplifyJobs](https://github.com/SimplifyJobs/Summer2027-Internships). Recreated from [internship-watcher](https://github.com/Yash-Swaminathan/internship-watcher) with permission.
