# Checkpoint

Project: hermes-self-management
Task: TASK-016
Status: Current
Created: 2026-09-09

## Objective

Deliver P-006 so nested `/workspace/...` mounts preserve Hermes' ordinary
parent sandbox, without adding or deploying structured mount configuration.

## Completed

- Confirmed the accepted public baseline and pinned Hermes revision.
- Reduced the parent proposal to one independently testable compatibility
  patch after source inspection exposed substring classification.
- Created the Component Task, capability evidence, and review ledger.

## In Progress

- Freeze the Task contract and implement P-006 with focused tests.

## Remaining

- Update patch archive, verification, checksums, and affected documentation.
- Run Initial Audit, resolve findings if any, and complete validation.
- Publish one public PR and wait for user review and merge.

## Blockers

None.

## Relevant Files

- `tasks/TASK-016.md`
- `tasks/evidence/TASK-016/`
- `deploy/minimal/patches/`
- `deploy/minimal/apply-hermes-patches.sh`
- `deploy/minimal/PATCHED_SHA256SUMS`

## Git State

- Branch: `codex/context-workspace-mounts-rebased`
- Accepted base: `92de1aa192e1d4bd8280b0f62c14fb91c0c54421`
- Contract revision: pending.

## Validation State

- Capability Gate 0: Pass.
- Contract validation: pending.
- Initial Audit and Final Audit: pending.
- Live deployment: unchanged and out of scope.

## Resume Hint

Freeze this contract, implement only P-006, then validate and publish the
public Component PR. Do not add Runtime Profile fields or deploy the patch.
