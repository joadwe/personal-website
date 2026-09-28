#!/bin/bash
# Install a per-user hourly launchd job for publishing Docker Scholar exports.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
label="co.uk.joshuawelsh.personal-website-scholar"
agent_path="$HOME/Library/LaunchAgents/$label.plist"
log_path="$HOME/Library/Logs/personal-website-scholar.log"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"

python3 - "$repo_root" "$agent_path" "$log_path" "$label" <<'PY'
import plistlib
import sys
from pathlib import Path

repo, agent, log, label = sys.argv[1:]
payload = {
    "Label": label,
    "ProgramArguments": ["/bin/bash", str(Path(repo) / "scripts" / "publish_scholar_updates.sh")],
    "WorkingDirectory": repo,
    "StartInterval": 3600,
    "RunAtLoad": True,
    "StandardOutPath": log,
    "StandardErrorPath": log,
}
Path(agent).write_bytes(plistlib.dumps(payload))
PY

launchctl bootout "gui/$(id -u)" "$agent_path" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$agent_path"
echo "Installed $label (checks hourly); log: $log_path"
