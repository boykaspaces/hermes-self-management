# TASK-013: Document Prerequisites and Runtime Defaults

Status: Completed
Priority: High

## Goal

Make first-deployment suitability, local tool prerequisites, model
authentication, and default runtime capability limits explicit before an
operator creates AWS resources, with a versioned read-only preflight command.

## Acceptance Criteria

- Quickstart starts with a concise suitability table covering the supported
  operator environment, EC2 host, outbound-network requirement, model
  authentication, Dashboard access, Telegram, browser, Terminal networking,
  and optional Git coding and Personal Tools capabilities.
- The prerequisites include the Session Manager plugin and make clear that the
  default Agent Terminal cannot install dependencies or clone repositories
  from the network.
- A versioned preflight script checks the supported local platform, required
  commands, meaningful minimum versions, and optional read-only AWS identity
  access without mutating AWS.
- Regression tests cover successful preflight, a missing Session Manager
  plugin, the read-only AWS boundary, and the documented defaults.
- Complete repository and Context Kit validation pass without creating or
  changing AWS resources.

## Completed

- Confirmed TASK-012 was merged into the accepted `main` baseline.
- Verified the template targets Ubuntu 24.04 LTS x86_64 on t3 instances and
  requires outbound access during first boot.
- Verified the Runtime Profile forces `openai-codex`, removes automatic
  fallback, disables Telegram and browser automation by default, and keeps
  Terminal networking disabled unless reviewed Git coding is enabled.
- Added the pre-resource suitability table and explicit default-capability
  limits to Quickstart, including the Agent Terminal's no-network behavior.
- Added versioned `deploy/preflight.sh` checks for the supported workstation,
  local tool baseline, Session Manager plugin, and optional read-only AWS
  identity validation.
- Added positive and negative preflight tests plus documentation-to-runtime
  contract checks.
- Passed complete repository validation, the local preflight, and Context Kit
  validation without creating or changing AWS resources.

## Remaining

None.

## Blockers

None.

## Relevant Files

- `deploy/QUICKSTART.md`
- `deploy/preflight.sh`
- `deploy/bootstrap/tests/test_bootstrap.py`
- `scripts/validate.sh`
- `tasks/TASK-013.md`

## Result

New operators can now determine compatibility and understand the deployment's
default model, access, browser, Telegram, Terminal, and optional-integration
boundaries before spending time or creating AWS resources. The preflight
provides a reproducible version and dependency baseline.

## Next Step

Review and accept this bounded proposal before starting the separate
dependency-pinning remediation Task.
