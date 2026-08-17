"""Register cron-job.org pings that fire the GitHub Actions watchers.

Needs:
  CRON_JOB_API_KEY  from https://console.cron-job.org/settings
  GH_TOKEN          a GitHub token that can dispatch workflows on Le0wang06/iw
                    (repo scope, or fine-grained Actions: write on this repo)

Usage:
  python .github/workflow-scripts/register_cronjob_org.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

CRON_API = "https://api.cron-job.org"
REPO = "Le0wang06/iw"
DISPATCH_URL = f"https://api.github.com/repos/{REPO}/dispatches"

# Every 2 minutes — faster than GitHub's 5-minute schedule floor.
EVERY_TWO_MINUTES = list(range(0, 60, 2))
EVERY_FIVE_OFFSET = list(range(1, 60, 5))


def cron_request(method: str, path: str, api_key: str, payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        CRON_API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "iw-cron-setup",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"cron-job.org {method} {path} failed: {exc.code} {body}") from exc


def github_job(title: str, event_type: str, minutes: list[int], gh_token: str) -> dict:
    return {
        "job": {
            "enabled": True,
            "title": title,
            "url": DISPATCH_URL,
            "saveResponses": True,
            "requestMethod": 1,  # POST
            "schedule": {
                "timezone": "America/Los_Angeles",
                "expiresAt": 0,
                "hours": [-1],
                "mdays": [-1],
                "minutes": minutes,
                "months": [-1],
                "wdays": [-1],
            },
            "notification": {
                "onFailure": True,
                "onSuccess": True,
            },
            "extendedData": {
                "headers": {
                    "Authorization": f"Bearer {gh_token}",
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                "body": json.dumps({"event_type": event_type}),
            },
        }
    }


def main() -> None:
    api_key = os.environ.get("CRON_JOB_API_KEY", "").strip()
    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    gh_token = gh_token.strip()
    if not api_key:
        raise SystemExit(
            "Set CRON_JOB_API_KEY from https://console.cron-job.org/settings"
        )
    if not gh_token:
        raise SystemExit("Set GH_TOKEN to a GitHub token that can dispatch workflows")

    existing = cron_request("GET", "/jobs", api_key)
    by_title = {job.get("title"): job for job in existing.get("jobs", [])}

    wanted = [
        ("iw boards every 2 min", "iw-cron-boards", EVERY_TWO_MINUTES),
        ("iw ATS every 5 min", "iw-cron-ats", EVERY_FIVE_OFFSET),
    ]
    for title, event, minutes in wanted:
        payload = github_job(title, event, minutes, gh_token)
        current = by_title.get(title)
        if current:
            job_id = current["jobId"]
            cron_request("PATCH", f"/jobs/{job_id}", api_key, payload)
            print(f"updated job {job_id}: {title}")
        else:
            created = cron_request("PUT", "/jobs", api_key, payload)
            print(f"created job {created.get('jobId')}: {title}")


if __name__ == "__main__":
    main()
