#!/bin/bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo="${HERMES_REPO:-/home/hermes/.hermes/hermes-agent}"
patch_set="${HERMES_PATCH_SET:-$script_dir/patches/hermes-v0.21.0-29112bef}"
mode="${1:-apply}"
python_bin="${HERMES_PYTHON:-$repo/venv/bin/python}"

case "$mode" in
  apply|verify|restore) ;;
  *) echo "Usage: $0 [apply|verify|restore]" >&2; exit 2 ;;
esac

git -C "$repo" rev-parse --git-dir >/dev/null
test -f "$patch_set/commit.txt"
if [ ! -x "$python_bin" ]; then
  python_bin="$(command -v python3)"
fi
expected_commit="$(tr -d '[:space:]' <"$patch_set/commit.txt")"
case "$expected_commit" in
  *[!0-9a-f]*|'') echo "Invalid expected commit in $patch_set/commit.txt" >&2; exit 1 ;;
esac
test "${#expected_commit}" -eq 40

actual_commit="$(git -C "$repo" rev-parse HEAD)"
if [ "$actual_commit" != "$expected_commit" ]; then
  echo "Refusing to manage patches: expected Hermes $expected_commit, found $actual_commit" >&2
  exit 1
fi

patches=(
  "$patch_set/P-002-browser-private-url.patch"
  "$patch_set/P-003-podman-reuse.patch"
  "$patch_set/P-005-egress-allowlist-only.patch"
  "$patch_set/P-006-preserve-workspace-for-nested-mounts.patch"
)

verify_files() {
  (
    cd "$repo"
    sha256sum --check "$patch_set/PATCHED_SHA256SUMS"
    git diff --check
    "$python_bin" -m py_compile \
      tools/browser_tool.py \
      tools/environments/docker.py \
      hermes_cli/proxy_cli.py \
      tests/test_iron_proxy_cli.py
  )
}

if [ "$mode" = verify ]; then
  verify_files
  echo "Hermes managed patches verified for $actual_commit"
  exit 0
fi

if [ "$mode" = restore ]; then
  for ((index=${#patches[@]}-1; index>=0; index--)); do
    patch="${patches[$index]}"
    if git -C "$repo" apply --reverse --check "$patch" 2>/dev/null; then
      git -C "$repo" apply --reverse "$patch"
      echo "Restored upstream content: $(basename "$patch")"
    elif git -C "$repo" apply --check "$patch" 2>/dev/null; then
      echo "Already upstream-clean: $(basename "$patch")"
    else
      echo "Refusing partial restore; patch state is ambiguous: $patch" >&2
      exit 1
    fi
  done
  git -C "$repo" diff --check
  echo "Hermes managed patches restored to upstream content for $actual_commit"
  exit 0
fi

for patch in "${patches[@]}"; do
  if git -C "$repo" apply --check "$patch" 2>/dev/null; then
    git -C "$repo" apply "$patch"
    echo "Applied: $(basename "$patch")"
  elif git -C "$repo" apply --reverse --check "$patch" 2>/dev/null; then
    echo "Already applied: $(basename "$patch")"
  else
    echo "Refusing automatic rewrite; patch does not cleanly apply or reverse: $patch" >&2
    exit 1
  fi
done

verify_files
echo "Hermes managed patches applied for $actual_commit"
