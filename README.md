# iw

**InternMonkey** is a Discord bot that notifies you when a new intern or new-grad job listing is posted.

Fast path is [cron-job.org](https://cron-job.org/en/) (`repository_dispatch`): **boards every 2 minutes**, **ATS every 5 minutes**. GitHub’s own schedule is an **hourly backup** if those pings stop. Overlapping runs share a concurrency group so extra pings wait instead of stacking.

| Source | What you get |
| --- | --- |
| [SimplifyJobs Summer 2027](https://github.com/SimplifyJobs/Summer2027-Internships) | Summer internships — all categories |
| [SimplifyJobs Off-Season](https://github.com/SimplifyJobs/Summer2027-Internships/blob/dev/README-Off-Season.md) | **Fall 2026, Winter 2027, Spring 2027** |
| [SimplifyJobs New Grad](https://github.com/SimplifyJobs/New-Grad-Positions) | Full-time new-grad roles |
| [Vansh & Ouckah](https://github.com/vanshb03/Summer2027-Internships) | Extra summer + off-season + [New Grad 2027](https://github.com/vanshb03/New-Grad-2027) |
| [cvrve New-Grad](https://github.com/cvrve/New-Grad) | Extra new-grad list, separate from Vansh |
| [ApplyGuy 2027](https://github.com/ApplyGuy/2027-Internships) | Verified company-page internships, all seasons |
| [zshah101 intern list](https://github.com/zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships) | Workday and extra ATS internships (JSON, includes Fall 2026) |
| [ambicuity New-Grad-Jobs](https://github.com/ambicuity/New-Grad-Jobs) | Early-career / new-grad / intern titles from company APIs |
| [SpeedyApply SWE](https://github.com/speedyapply/2027-SWE-College-Jobs) + [AI/ML](https://github.com/speedyapply/2027-AI-College-Jobs) | Daily SWE and AI intern **and USA new-grad** lists |
| [aprameyak/2027-tech-jobs](https://github.com/aprameyak/2027-tech-jobs) | Summer + **off-cycle / Winter 2027** community list |
| ~240 company ATS boards | Greenhouse / Lever / Ashby intern, co-op, **and new-grad** roles |

When something new is found, Discord is pinged. Cards include term, track (SWE / AI / Quant / …), and priority companies first. Email and GitHub issues stay off unless you opt in.

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

To set up the fast path, create a free [cron-job.org](https://console.cron-job.org/) account, make an API key under Settings, then:

```powershell
$env:CRON_JOB_API_KEY = "your-cron-job-org-api-key"
$env:GH_TOKEN = "github-token-with-actions-write-on-this-repo"
python .github/workflow-scripts/register_cronjob_org.py
```

That registers two HTTP POST jobs: boards every 2 minutes, ATS every 5 minutes.

## Adding sources

Board URLs live in `.github/workflow-scripts/sources.json`. Add a block with `key`, `file`, `title`, `parser` (`simplify`, `markdown`, or `jobsjson`), and one or more `urls`. The watcher fetches and parses from that file — no workflow curl list.

ATS companies live in `.github/workflow-scripts/ats_companies.json`:

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
.github/workflows/          scheduled watchers (hourly backup + dispatch)
.github/workflow-scripts/   sources.json, parsers, ATS list, Discord
snapshots/                  seen-state only (committed by Actions)
```

## Credit

Listings come from SimplifyJobs, Vansh/Ouckah, cvrve, ApplyGuy, zshah101, ambicuity, SpeedyApply, aprameyak, and company ATS boards. Recreated from [internship-watcher](https://github.com/Yash-Swaminathan/internship-watcher) with permission.
