# iw

GitHub Actions bot that posts new internship / new-grad listings to **Discord**. Email and GitHub issues are optional.

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

When something new is found, Discord is pinged. Email and GitHub issues stay off unless you opt in.

The first run after adding sources records the current boards without emailing the backlog. After that, only **new** postings are sent.

## Alerts

Default: **Discord only**. Quiet checks do nothing.

| Name | Required | What it is |
| --- | --- | --- |
| `DISCORD_CHANNEL_ID` (secret) | yes, for Discord | Channel the bot should post in |
| `DISCORD_BOT_TOKEN` (secret) | yes, for Discord | Bot token from the Developer Portal **Bot** tab (not the client secret) |
| `DISCORD_WEBHOOK_URL` (secret) | alternative | Incoming webhook URL if you do not want a bot |
| `ENABLE_EMAIL` (variable) | optional | Set to `true` plus `MAIL_*` secrets to send SMTP mail |
| `MAIL_TO` (secret) | optional | Address to email |
| `MAIL_USERNAME` (secret) | optional | SMTP username (Gmail address) |
| `MAIL_PASSWORD` (secret) | optional | Gmail app password |
| `ENABLE_GITHUB_ISSUES` (variable) | optional | Set to `true` to also open a GitHub issue per alert |

**Internship Board Watcher** and **ATS Board Watcher** still run on GitHub’s 5-minute schedule (and faster via cron-job.org).

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
