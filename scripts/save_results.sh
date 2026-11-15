#!/usr/bin/env bash
# Commit new episode files and push, retrying if another run pushed in the meantime.
set -u
git config user.name "paperbot"
git config user.email "paperbot@users.noreply.github.com"
git add -A episodes config
git diff --cached --quiet && exit 0
git commit -q -m "$1"
for attempt in 1 2 3 4 5; do
  git pull -q --rebase origin main && git push -q origin main && exit 0
  sleep $((attempt * 5))
done
echo "::error::could not push results"; exit 1
