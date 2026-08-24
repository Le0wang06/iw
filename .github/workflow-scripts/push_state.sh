#!/usr/bin/env bash
# Commit snapshot files and push with retries so board + ATS watchers
# can land on main without losing the other runner's seen-state commit.
set -euo pipefail

msg="$1"
shift

git config user.name "github-actions"
git config user.email "actions@github.com"
git add "$@"
if git diff --quiet && git diff --staged --quiet; then
  exit 0
fi
git commit -m "$msg"

for i in 1 2 3 4 5 6 7 8; do
  if git pull --rebase origin main && git push; then
    exit 0
  fi
  git rebase --abort >/dev/null 2>&1 || true
  sleep $((i * 2))
done

echo "git push failed after retries" >&2
exit 1
