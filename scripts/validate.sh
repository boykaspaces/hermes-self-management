#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for path in PROJECT.md AGENTS.md .context-kit/manifest.json .context-kit/index.md .context-kit/state.md \
  .context-kit/checkpoints/README.md tasks/README.md tasks/current.md \
  docs/decisions/README.md deploy/QUICKSTART.md deploy/bootstrap/README.md \
  deploy/preflight.sh deploy/minimal/FIRST_DEPLOYMENT_RECOVERY.md \
  deploy/bootstrap/artifacts-cloudformation.yaml deploy/bootstrap/network-cloudformation.yaml \
  deploy/bootstrap/discover-environment.sh deploy/bootstrap/validate-template.sh \
  deploy/minimal/parameters.example.json deploy/minimal/publish-runtime-profile.sh \
  deploy/minimal/create-change-set.sh; do
  test -f "$repo_root/$path" || { echo "missing context path: $path" >&2; exit 1; }
done

python3 - "$repo_root/.context-kit/manifest.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    manifest = json.load(handle)
expected = {
    "schema_version": 2,
    "spec_version": 2,
    "kit_version": "0.5.0",
    "profile": "repository",
    "features": ["tasks", "decisions", "checkpoints"],
    "extensions": {
        "delivery-governance": {
            "mode": "advisory",
            "skill": "ai-delivery-governance",
            "version": 1,
        }
    },
    "runtime_adapters": [{"name": "hermes", "version": 3}],
    "workflow_adapter": {"name": "github", "version": 1},
}
if manifest != expected:
    raise SystemExit("unexpected Context Kit adoption manifest")
PY

if rg -n --glob '!scripts/validate.sh' '(210122338617|i-0f170ae7baf762606|2ugu1wgqaa|boyka5945@gmail\.com|arn:aws:[^:]*:[^:]*:210122338617|personal-tools-artifacts-210122338617)' "$repo_root"; then
  echo 'private deployment identifier detected' >&2
  exit 1
fi

if find "$repo_root" \( -name DEPLOYMENT_RECORD.md -o -name '*.pem' -o -name '*.key' -o -name .env \) -print -quit | grep -q .; then
  echo 'private deployment record or credential file detected' >&2
  exit 1
fi

bash -n "$repo_root/deploy/minimal/validate-template.sh"
bash -n "$repo_root/deploy/preflight.sh"
bash -n "$repo_root/deploy/minimal/publish-template.sh"
bash -n "$repo_root/deploy/minimal/publish-runtime-profile.sh"
bash -n "$repo_root/deploy/minimal/create-change-set.sh"
bash -n "$repo_root/deploy/minimal/apply-hermes-patches.sh"
bash -n "$repo_root/deploy/bootstrap/discover-environment.sh"
bash -n "$repo_root/deploy/bootstrap/validate-template.sh"
bash -n "$repo_root/deploy/budget/validate-template.sh"
bash -n "$repo_root/deploy/hermes-runtime-secrets/validate-template.sh"

"$repo_root/deploy/minimal/validate-template.sh"
"$repo_root/deploy/bootstrap/validate-template.sh"
"$repo_root/deploy/budget/validate-template.sh"
"$repo_root/deploy/hermes-runtime-secrets/validate-template.sh"

python3 -m unittest discover -s "$repo_root/hermes-plugins/observability/token_observer/tests" -p 'test_*.py'
python3 -m unittest discover -s "$repo_root/deploy/bootstrap/tests" -p 'test_*.py'

ruby - "$repo_root" <<'RUBY'
require "pathname"
root = Pathname.new(ARGV.fetch(0))
errors = []
root.glob("**/*.md").sort.each do |file|
  file.read.scan(/\[[^\]]*\]\(([^)]+)\)/).flatten.each do |raw|
    target = raw.strip
    next if target.empty? || target.start_with?("http://", "https://", "mailto:", "#")
    target = target.split("#", 2).first
    next if target.empty?
    resolved = file.dirname.join(target).cleanpath
    errors << "#{file.relative_path_from(root)}: #{raw}" unless resolved.exist?
  end
end
abort(errors.join("\n")) unless errors.empty?
puts 'markdown-relative-links-ok'
RUBY

active_task="$(awk -F': ' '/^Active Task:/ {print $2}' "$repo_root/tasks/current.md")"
state_task="$(awk -F': ' '/^Active Task:/ {print $2}' "$repo_root/.context-kit/state.md")"
test "$active_task" = "$state_task" || {
  echo 'Task and State current pointers disagree' >&2
  exit 1
}

echo 'hermes-self-management repository validation passed'
