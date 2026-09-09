# TASK-016: Preserve the Sandbox with Nested Workspace Mounts

Status: In Progress
Type: Component
Governance: Required
Delivery Stage: Plan
Priority: High
Parent System Task: `personal-hermes-agent:TASK-025`

## Goal

Add one deterministic patch to the pinned Hermes source so a configured
nested `/workspace/...` volume does not suppress the ordinary parent
`/workspace` sandbox mount.

## Accepted Inputs

- Parent System Task: `personal-hermes-agent:TASK-025`
- Pinned Hermes revision:
  `29112bef099274229cadff79cdff7bf7b99c4b77`
- Existing ordered patch set: P-002, P-003, and P-005
- Private feasibility evidence remains in the integration repository and is
  not copied into this public component.

These are source-delivery inputs. This Task does not advance a private
component lock or claim a live runtime update.

## Acceptance Criteria

- AC-1: P-006 changes only the pinned Hermes Docker volume classification and
  its focused upstream tests; the pinned upstream revision remains unchanged.
- AC-2: Only a parsed container destination exactly equal to `/workspace`
  suppresses the ordinary parent sandbox mount.
- AC-3: Nested `/workspace/...` destinations and `/workspace` text in a source
  path do not suppress the parent mount; malformed or unsupported entries do
  not gain replacement semantics.
- AC-4: Regression tests cover exact destinations with and without mount
  options, nested destinations, unrelated destinations, and malformed entries
  under both persistent bind and ephemeral tmpfs behavior.
- AC-5: Patch application, verification, archive synchronization, embedded
  runtime artifacts, and patched-file checksums include P-006 deterministically.
- AC-6: Focused pinned-upstream tests, `deploy/minimal/validate-template.sh`,
  complete `scripts/validate.sh`, Initial Audit, any required Delta Review, and
  exact-head Final Audit pass.
- AC-7: No Runtime Profile schema, generated consumer volume, CloudFormation,
  live configuration, infrastructure, service, credential, project registry,
  component lock, or deployment binding changes.

## Supported Scope

- P-006 against the exact pinned Hermes source.
- Focused upstream regression coverage for volume destination classification
  and the resulting parent sandbox argument.
- Public patch inventory, deterministic application, archive, verification,
  checksums, and documentation directly affected by P-006.
- Public Task, capability evidence, and review ledger without private consumer
  identifiers or deployment evidence.

## Out of Scope

- Adding a structured Context workspace option to the Runtime Profile.
- Selecting consumer host paths or generating registry/project volume entries.
- Publishing or applying runtime artifacts, restarting services, adopting a
  project, or rerunning the blocked parent adoption Task.
- Changing the general Docker volume contract beyond exact parent-workspace
  replacement detection.

## Capability Audit

Applicability: Required
Gate Result: Pass
Matrix: `tasks/evidence/TASK-016/capability.md`

The audit found one independently repairable prerequisite: the pinned source
uses substring matching, so a narrow nested volume incorrectly disables the
parent sandbox. Exact destination parsing and focused container-argument tests
are sufficient to converge before any higher-level profile design.

## Required Validation

- Apply P-002, P-003, P-005, and P-006 to a clean checkout of the exact pinned
  Hermes revision and run the focused Docker environment tests.
- Run patch verification and archive synchronization checks.
- Run `deploy/minimal/validate-template.sh` and `scripts/validate.sh`.
- Recover this Task and evidence through the public project-context route.
- Bind Final Audit evidence to the exact pull-request head.

## Review

Ledger: `tasks/evidence/TASK-016/review.md`

## Completed

- Confirmed the accepted public baseline and next Component Task identifier.
- Confirmed the exact pinned upstream revision and existing patch pipeline.
- Reduced the parent proposal after feasibility inspection exposed the nested
  destination classification defect.
- Created the bounded Component Task, Capability Gate 0 evidence, checkpoint,
  and review ledger.

## Remaining

- Freeze the Task contract after validation.
- Implement P-006 and focused regression tests.
- Update deterministic patch/archive/checksum owners and affected docs.
- Complete review and exact-head validation, then publish one public PR.

## Blockers

None.

## Relevant Files

- `deploy/minimal/patches/P-006-preserve-workspace-for-nested-mounts.patch`
- `deploy/minimal/apply-hermes-patches.sh`
- `deploy/minimal/sync_hermes_patch_archive.py`
- `deploy/minimal/PATCHED_SHA256SUMS`
- `deploy/minimal/runtime-config.sh`
- `deploy/minimal/validate-template.sh`
- `deploy/minimal/README.md`
- `tasks/evidence/TASK-016/`

## Next Step

Freeze this contract, then implement and validate only P-006.
