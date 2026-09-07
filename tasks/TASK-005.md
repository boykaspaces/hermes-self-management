# TASK-005: Externalize Consumer Runtime Profile

Status: Completed
Type: Component
Priority: High
Parent System Task: personal-hermes-agent:TASK-014

## Goal

Keep first-boot User Data limited to host bootstrap and move mutable,
non-secret consumer preferences out of CloudFormation into a separately
validated runtime profile.

## Completed

- Added a strict 4 KiB consumer-profile validator and neutral example.
- Added atomic profile application for model, Telegram, MCP, browser, Terminal,
  agent, Memory, Skill approval, and proxy allowlist settings.
- Added an SSM profile loader with last-known-valid caching before Gateway
  start.
- Removed mutable Hermes configuration commands from first-boot User Data.
- Passed the complete repository validator, including deterministic bundle,
  strict profile/application tests, template/User Data checks, 19 Token
  Observer tests, and Markdown validation.

## Remaining

None.

## Blockers

None.

## Relevant Files

- `deploy/minimal/cloudformation.yaml`
- `deploy/minimal/runtime-config.sh`
- `deploy/minimal/runtime-profile.example.json`
- `deploy/minimal/validate_runtime_profile.py`
- `deploy/minimal/apply_runtime_profile.py`

## Related Work

- `personal-hermes-agent:ADR-015`

## Next Step

None.

## Result

The public component now provides a consumer-neutral, validated profile
contract and keeps mutable personal behavior out of CloudFormation and
first-boot User Data. Production publication and rollout remain owned by the
private parent System Task.
