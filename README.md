# iw

GitHub Actions bot that emails **Leo** (`098leowang@gmail.com`) when new internship / new-grad listings show up.

It checks **every 5 minutes** (GitHub’s fastest built-in schedule). [cron-job.org](https://cron-job.org/en/) can ping even faster (boards every 2 minutes) via `repository_dispatch`.

| Source | What you get |
| --- | --- |
| [SimplifyJobs Summer 2027](https://github.com/SimplifyJobs/Summer2027-Internships) | Summer internships — all categories |
| [SimplifyJobs Off-Season](https://github.com/SimplifyJobs/Summer2027-Internships/blob/dev/README-Off-Season.md) | **Fall 2026, Winter 2027, Spring 2027** |
| [SimplifyJobs New Grad](https://github.com/SimplifyJobs/New-Grad-Positions) | Full-time new-grad roles |
| [Vansh & Ouckah](https://github.com/vanshb03/Summer2027-Internships) | Extra summer + off-season + [New Grad 2027](https://github.com/vanshb03/New-Grad-2027) |
| [ApplyGuy 2027](https://github.com/ApplyGuy/2027-Internships) | Verified company-page internships, all seasons |
| [zshah101 intern list](https://github.com/zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships) | Workday and extra ATS internships (JSON, includes Fall 2026) |
| [ambicuity New-Grad-Jobs](https://github.com/ambicuity/New-Grad-Jobs) | Early-career / new-grad / intern titles from company APIs |
| [SpeedyApply SWE](https://github.com/speedyapply/2027-SWE-College-Jobs) + [AI/ML](https://github.com/speedyapply/2027-AI-College-Jobs) | Daily SWE and AI intern lists |
| [aprameyak/2027-tech-jobs](https://github.com/aprameyak/2027-tech-jobs) | Summer + **off-cycle / Winter 2027** community list |
| 227 company ATS boards | Greenhouse / Lever / Ashby intern and co-op roles |

When something new is found, an HTML email goes to **098leowang@gmail.com**. A GitHub issue is also opened and `@Le0wang06` is mentioned.

The first run after adding sources records the current boards without emailing the backlog. After that, only **new** postings are sent.

## Status

Mail and Actions are already configured:

| Secret | Value |
| --- | --- |
| `MAIL_USERNAME` | `098leowang@gmail.com` |
| `MAIL_TO` | `098leowang@gmail.com` |
| `MAIL_PASSWORD` | Gmail app password (stored in GitHub Actions secrets) |

**Internship Board Watcher** runs every 5 minutes. **ATS Board Watcher** runs every 5 minutes, offset by 2 minutes. Quiet checks do not send mail.

To go faster than GitHub’s 5-minute floor, create a free [cron-job.org](https://console.cron-job.org/) account, make an API key under Settings, then:

```powershell
$env:CRON_JOB_API_KEY = "your-cron-job-org-api-key"
$env:GH_TOKEN = "github-token-with-actions-write-on-this-repo"
python .github/workflow-scripts/register_cronjob_org.py
```

That registers two HTTP POST jobs: boards every 2 minutes, ATS every 5 minutes.

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

Listings come from SimplifyJobs, Vansh/Ouckah, ApplyGuy, zshah101, ambicuity, SpeedyApply, aprameyak, and company ATS boards. Recreated from [internship-watcher](https://github.com/Yash-Swaminathan/internship-watcher) with permission.
