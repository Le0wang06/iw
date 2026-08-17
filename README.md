# iw

GitHub Actions bot that emails **Leo** (`098leowang@gmail.com`) when new internship / new-grad listings show up.

It checks **every 30 minutes** across multiple public lists, not just one Summer SWE board:

| Source | What you get |
| --- | --- |
| [SimplifyJobs Summer 2027](https://github.com/SimplifyJobs/Summer2027-Internships) | Summer internships — SWE, PM, data/AI/ML, quant, hardware |
| [SimplifyJobs Off-Season](https://github.com/SimplifyJobs/Summer2027-Internships/blob/dev/README-Off-Season.md) | **Fall 2026, Winter 2027, Spring 2027** internships |
| [SimplifyJobs New Grad](https://github.com/SimplifyJobs/New-Grad-Positions) | Full-time new-grad roles |
| [Vansh & Ouckah Summer 2027](https://github.com/vanshb03/Summer2027-Internships) | Extra summer list |
| [Vansh & Ouckah Off-Season](https://github.com/vanshb03/Summer2027-Internships/blob/dev/OFFSEASON_README.md) | Extra winter / fall / spring list |
| [ApplyGuy 2027 Internships](https://github.com/ApplyGuy/2027-Internships) | Verified company-page internships, all seasons |
| 227 company ATS boards | Greenhouse / Lever / Ashby intern and co-op roles, all functions |

When something new is found, an HTML email goes to **098leowang@gmail.com**. A GitHub issue is also opened and `@Le0wang06` is mentioned.

The first run after this expansion records the current boards without emailing the backlog. After that, only **new** postings are sent.

## Status

Mail and Actions are already configured:

| Secret | Value |
| --- | --- |
| `MAIL_USERNAME` | `098leowang@gmail.com` |
| `MAIL_TO` | `098leowang@gmail.com` |
| `MAIL_PASSWORD` | Gmail app password (stored in GitHub Actions secrets) |

**Internship Board Watcher** runs at `:00` and `:30`. **ATS Board Watcher** runs at `:15` and `:45`. Quiet checks do not send mail.

## Adding ATS companies

Edit `.github/workflow-scripts/ats_companies.json`:

```json
{
  "ats": "greenhouse",
  "slug": "stripe",
  "name": "Stripe"
}
```

`ats` must be `greenhouse`, `lever`, or `ashby`.

## Layout

```
.github/workflows/          scheduled watchers
.github/workflow-scripts/   parsers and company list
snapshots/                  last-seen board state (committed by Actions)
```

## Credit

Listings come from SimplifyJobs, Vansh/Ouckah, ApplyGuy, and company ATS boards. Recreated from [internship-watcher](https://github.com/Yash-Swaminathan/internship-watcher) with permission.
