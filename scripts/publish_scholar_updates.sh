#!/bin/bash
# Run by launchd on the Mac that hosts the google-scholar Docker container.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=15"
cd "$repo_root"

if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "Scholar publisher requires the main branch."
  exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Scholar publisher skipped: the website has local changes."
  exit 0
fi

git fetch origin main
git merge --ff-only origin/main

# A failed earlier push may leave a generated commit ahead of origin. Do not
# publish any other pending commit from this unattended job.
while IFS= read -r subject; do
  if [[ "$subject" != "chore: update Scholar publications and citations" ]]; then
    echo "Scholar publisher stopped: an unrelated local commit is ahead of origin/main."
    exit 1
  fi
done < <(git log origin/main..HEAD --format=%s)

python_bin="$repo_root/.venv/bin/python"
mkdocs_bin="$repo_root/.venv/bin/mkdocs"
if [[ ! -x "$python_bin" || ! -x "$mkdocs_bin" ]]; then
  uv sync --locked
fi

"$python_bin" scripts/sync_scholar_export.py
if ! git diff --quiet -- docs/data/scholar-dashboard.json docs/publications.md; then
  "$mkdocs_bin" build --strict
  git add -- docs/data/scholar-dashboard.json docs/publications.md
  git commit -m "chore: update Scholar publications and citations"
fi

git push origin main
