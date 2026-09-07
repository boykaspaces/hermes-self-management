# TASK-003: Improve Telegram Work Feedback

Status: Completed
Type: Component
Priority: High
Parent System Task: personal-hermes-agent:TASK-013

## Goal

Make Telegram turns visibly acknowledge and report ongoing work, and disable
per-operation approval prompts for local Skill and Memory writes without
broadening external authorization boundaries.

## Completed

- Confirmed the current Hermes runtime supports Telegram reactions, grouped
  tool progress, streaming, and long-running notifications.
- Updated runtime sync to enable processing reactions, grouped tool progress,
  Telegram streaming, one-minute heartbeats, and successful-turn cleanup.
- Set Skill and Memory `write_approval` defaults to `false` while retaining all
  external authorization boundaries.
- Added template invariants and passed the host-template and full repository
  validation suites.

## Remaining

None.

## Blockers

None.

## Relevant Files

- `deploy/minimal/cloudformation.yaml`
- `deploy/minimal/validate-template.sh`
- `deploy/minimal/README.md`

## Related Decisions

- `personal-hermes-agent:ADR-014`

## Next Step

None.

## Result

The reusable host template now provides visible Telegram work feedback and
approval-free local Skill/Memory writes without changing external authority.
