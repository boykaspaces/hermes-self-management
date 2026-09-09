# TASK-014: Pin First-Boot Installation Inputs

Status: Completed
Priority: High

## Goal

Make the same reviewed template inputs produce a stable Hermes first-boot
software baseline by pinning and verifying the upstream installer, enforcing
the upstream dependency locks, fixing browser and container identities, and
recording the versions actually installed.

## Acceptance Criteria

- User Data downloads the installer from the configured full Hermes commit,
  verifies its reviewed SHA-256 before execution, and passes that commit to the
  installer before dependency installation.
- The final Python environment is synchronized with the verified upstream
  `uv.lock`; the prior unlocked editable `pip install` is absent.
- The upstream `package-lock.json` is verified before `npm ci`.
- Agent Browser uses an exact version and the coding container accepts only an
  immutable digest reference; no corresponding range or tag-only pull remains.
- First boot records source identities, runtime tool versions, the actual
  Python package set, and the actual Node dependency tree without recording
  credentials.
- Static negative tests and complete repository validation pass without
  running the remote installer or changing AWS resources.

## Completed

- Confirmed TASK-013 was merged into the accepted `main` baseline.
- Verified the pinned Hermes commit contains `scripts/install.sh`, `uv.lock`,
  and `package-lock.json`, and that its installer accepts `--commit` and prefers
  `uv sync --locked`.
- Verified the current template re-resolves Python packages after checkout,
  uses an Agent Browser semver range, and pulls a tag-only container image.
- Resolved the reviewed x86_64 coding-container image digest and calculated
  SHA-256 values for the installer and upstream lock files at the pinned commit.
- Added commit-scoped installer retrieval with SHA-256 verification and passed
  the reviewed commit explicitly to the upstream installer.
- Verified both upstream lock files before enforcing the final Python and Node
  dependency installations; removed the unlocked editable `pip install`.
- Replaced the Agent Browser version range and tag-only coding image with an
  exact package version and digest-only image reference.
- Added a private on-instance installation manifest containing source
  identities, tool versions, the installed Python package set, and Node
  dependency trees without credentials.
- Documented the installation-identity update and evidence-retrieval contract,
  and added positive and negative regression coverage.
- Passed complete repository validation and Context Kit validation without
  running the remote installer or changing AWS resources.

## Remaining

None.

## Blockers

None.

## Relevant Files

- `deploy/minimal/cloudformation.yaml`
- `deploy/minimal/parameters.example.json`
- `deploy/minimal/validate-template.sh`
- `deploy/minimal/README.md`
- `deploy/bootstrap/tests/test_bootstrap.py`
- `tasks/TASK-014.md`

## Result

The reviewed template now rejects mutable browser and container identities,
verifies the Hermes installer and dependency locks before use, and records the
software actually installed. This removes the known unlocked dependency step
and gives first-boot failures a concrete, non-secret comparison baseline while
stopping short of claiming bit-for-bit reproducibility for operating-system or
installer-managed tool downloads.

## Next Step

Review and accept this bounded proposal before starting the separate
first-deployment failure-recovery remediation Task.
