# TASK-017: Repair the TASK-016 Parent Link

Status: Completed
Type: Component
Governance: Required
Priority: High
Parent System Task: personal-hermes-agent:TASK-025

## Goal

Make the completed TASK-016 parent relationship machine-valid so the private
integration repository can verify and accept the already merged P-006 source.

## Acceptance Criteria

- AC-1: TASK-016 declares its `Parent System Task` as the bare canonical value
  `personal-hermes-agent:TASK-025` expected by the reviewed multi-repository
  validator.
- AC-2: Repository-context validation and the parent System Task relationship
  check accept the corrected component revision.
- AC-3: No P-006 implementation, patch archive, Runtime Profile, deployment
  template, infrastructure, service, credential, or live runtime changes.

## Supported Scope

- One metadata correction in `tasks/TASK-016.md`.
- The minimum Task, State, index, and review evidence needed to deliver and
  audit that correction.

## Out of Scope

- Changing P-006 behavior or tests.
- Advancing the private component lock or deployment binding.
- Structured Context workspace configuration, installation, deployment, or
  project adoption.

## Capability Audit

Applicability: Not Required
Gate Result: Not Required
Matrix: `tasks/evidence/TASK-017/capability.md`

The failure is a deterministic metadata-format mismatch. Existing canonical
Component Tasks and the packaged template already demonstrate the accepted
bare field form; no external runtime primitive is involved.

## Required Validation

- Hermes Context Kit multi-repository repository validation.
- Parent System Task relationship validation from the private integration
  candidate without advancing its lock.
- Public `scripts/validate.sh` and Context Kit project validation.
- Exact-head Final Audit.

## Review

Ledger: `tasks/evidence/TASK-017/review.md`

## Completed

- Reproduced the integration failure against exact merged revision
  `c06f3d401a8ec0f5e1487e83c16016ac91049956`.
- Reduced the repair to the TASK-016 parent-field representation plus required
  project-context routing.
- Froze the bounded repair contract at
  `3e8f71adb8b8868129c8caed894e19bff0ef3640`.
- Replaced only TASK-016's Markdown-delimited parent value with the canonical
  bare System Task identity.
- Passed the public native suite, Context Kit project validation, and reviewed
  multi-repository repository validation.

## Remaining

None.

## Blockers

None.

## Relevant Files

- `tasks/TASK-016.md`
- `tasks/TASK-017.md`
- `tasks/evidence/TASK-017/`

## Next Step

None for TASK-017. Review and accept this metadata-only proposal before the
private integration repository advances its source lock.

## Result

TASK-016 now exposes the canonical parent System Task value in the exact
machine-readable form required for cross-repository relationship validation,
without changing P-006 or any runtime/deployment artifact.
