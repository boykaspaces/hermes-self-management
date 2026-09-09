# Checkpoint

Project: hermes-self-management
Task: TASK-016
Status: Archived
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

None.

## Remaining

- Publish one public PR and wait for user review and merge.

## Blockers

None.

## Relevant Files

- `tasks/TASK-016.md`
- `tasks/evidence/TASK-016/`
- `deploy/minimal/patches/`
- `deploy/minimal/apply-hermes-patches.sh`
- `deploy/minimal/patches/hermes-v0.21.0-29112bef/PATCHED_SHA256SUMS`

## Git State

- Branch: `codex/context-workspace-mounts-rebased`
- Accepted base: `92de1aa192e1d4bd8280b0f62c14fb91c0c54421`
- Contract revision: `19c1ed254aef8734f34a4f209892444c3c2b9817`.

## Validation State

- Capability Gate 0: Pass.
- Contract validation: pass.
- Initial Audit: pass with no blocking finding.
- Final Audit: pending exact pull-request head.
- Live deployment: unchanged and out of scope.

## Resume Hint

Publish and review the completed public Component candidate. Do not add
Runtime Profile fields or deploy the patch.
