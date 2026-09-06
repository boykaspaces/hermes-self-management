#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if rg -n --glob '!scripts/validate.sh' '(210122338617|i-0f170ae7baf762606|2ugu1wgqaa|boyka5945@gmail\.com|arn:aws:[^:]*:[^:]*:210122338617|personal-tools-artifacts-210122338617)' "$repo_root"; then
  echo 'private deployment identifier detected' >&2
  exit 1
fi

if find "$repo_root" \( -name DEPLOYMENT_RECORD.md -o -name '*.pem' -o -name '*.key' -o -name .env \) -print -quit | grep -q .; then
  echo 'private deployment record or credential file detected' >&2
  exit 1
fi

bash -n "$repo_root/deploy/minimal/validate-template.sh"
bash -n "$repo_root/deploy/minimal/publish-template.sh"
bash -n "$repo_root/deploy/minimal/apply-hermes-patches.sh"
bash -n "$repo_root/deploy/budget/validate-template.sh"
bash -n "$repo_root/deploy/hermes-runtime-secrets/validate-template.sh"

"$repo_root/deploy/minimal/validate-template.sh"
"$repo_root/deploy/budget/validate-template.sh"
"$repo_root/deploy/hermes-runtime-secrets/validate-template.sh"

python3 -m unittest discover -s "$repo_root/hermes-plugins/observability/token_observer/tests" -p 'test_*.py'

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

echo 'hermes-self-management repository validation passed'
