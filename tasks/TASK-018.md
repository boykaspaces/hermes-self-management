# TASK-018: Add Structured Context Workspace Mounts

Status: Completed
Type: Component
Governance: Required
Delivery Stage: Review
Priority: High
Parent System Task: personal-hermes-agent:TASK-026

## Goal

Add a versioned, structured Runtime Profile contract that maps only the
Context Kit registry and managed-project root into Hermes file-tool containers,
without exposing raw Docker volume strings or deploying a consumer profile.

## Acceptance Criteria

- AC-1: Runtime Profile schema v1 remains accepted with no Context workspace
  behavior; schema v2 requires one exact `context_workspace` object with
  `enabled`, `host_root`, and explicit `project_access` fields.
- AC-2: `host_root` is an absolute normalized non-root POSIX path. When enabled,
  the adapter verifies that the root, `.hermes`, and `projects` paths are real
  directories owned by the runtime user and rejects symlinks or aliases.
- AC-3: The adapter derives exactly two fixed container destinations: registry
  `/workspace/.hermes` is read-only and managed projects
  `/workspace/projects` use the declared read-only or read-write access.
- AC-4: Applying v2 replaces duplicates or conflicts only at those two owned
  destinations, preserves unrelated mounts, and never emits a whole-workspace,
  `.context-kit`, credential, engine-socket, or arbitrary destination mount.
- AC-5: P-006 continues to preserve the ordinary parent `/workspace` sandbox
  for both structured nested mounts, and credential injection remains a
  separate later runtime-config step.
- AC-6: Positive, negative, migration, idempotence, and disable-path tests;
  template validation; runtime bundle synchronization; complete repository
  validation; and exact-head Final Audit pass.
- AC-7: No private host path, consumer Runtime Profile, component lock,
  deployment binding, infrastructure, service, credential, registry, project,
  or live Hermes runtime is changed.

## Supported Scope

- Runtime Profile v1/v2 validation and schema migration behavior.
- Deterministic translation from one structured host root to two fixed narrow
  Docker bind mounts.
- Runtime user ownership, directory, normalization, and symlink checks.
- Consumer-neutral example, tests, runtime bundle, and affected documentation.

## Out of Scope

- Consumer-supplied raw `docker_volumes` or container destinations.
- Creating host directories, choosing a private production path, or changing
  directory ownership.
- Publishing/applying a Runtime Profile, installing a Runtime Bundle,
  restarting services, or accepting a live Agent session.
- Registering, restoring, adopting, or editing a managed project.

## Capability Audit

Applicability: Required
Gate Result: Pass
Matrix: `tasks/evidence/TASK-018/capability.md`

The pre-design probe used the exact locked source. It proved that two narrow
mounts survive the current profile application path, the credential mount is
still appended independently, the proposed v2 profile remains below the 4 KiB
limit, and the current strict schema rejects the unimplemented field.

## Required Validation

- Runtime Profile v1 compatibility and v2 positive/negative unit tests.
- Exact generated mount, conflict replacement, idempotence, disable, directory
  ownership, symlink, and unsafe-path tests.
- P-006 focused upstream tests and complete patch lifecycle checks.
- `deploy/minimal/validate-template.sh`, public `scripts/validate.sh`, Context
  Kit project/repository validation, and parent System Task relationship.
- Exact-head Final Audit.

## Review

Ledger: `tasks/evidence/TASK-018/review.md`

## Completed

- Confirmed private TASK-025 PR #15 merged and selected exact public revision
  `467cec2d168cd81e2b1e9c0ab51c4a011535b15a`.
- Completed the in-memory, non-deployment feasibility probe against that exact
  source: two narrow mounts preserved, credential mount independent, proposed
  compact profile 1304 bytes, and current schema failed closed.
- Froze the Component contract as
  `332b140e8c21a25577f38f11cf06611538e030d1` and verified its exact parent
  relationship to `personal-hermes-agent:TASK-026`.
- Added strict v1/v2 schema migration, structured path validation, existing
  real-directory and runtime-user ownership checks, and deterministic fixed
  registry/projects mount generation.
- Preserved v1 mount behavior, unrelated mounts, the separately injected
  credential mount, and the ordinary P-006 parent sandbox while replacing v2
  conflicts only at the two owned destinations.
- Added migration, field-shape, unsafe-path, read-only/read-write, exact-mount,
  conflict, disable, idempotence, missing-directory, non-directory, symlink,
  child-symlink, and wrong-owner coverage. The Runtime Profile suite passed 25
  tests and template validation passed 30 tests in total.
- Re-ran 19 focused P-006 upstream tests against pinned Hermes revision
  `29112bef099274229cadff79cdff7bf7b99c4b77`; all passed.
- Passed the complete public repository suite, Context Kit validation,
  repository validation, and schema-v2 parent System Task validation for
  implementation revision `7d98d9c77a2572535724b9b544017f0bae170c84`.
- Confirmed no private profile, host path, component lock, deployment binding,
  infrastructure, service, registry, project, credential, or live runtime was
  changed.

## Remaining

None within the public source candidate. User review and merge remain external
acceptance gates before private source acceptance starts.

## Blockers

None.

## Relevant Files

- `deploy/minimal/validate_runtime_profile.py`
- `deploy/minimal/apply_runtime_profile.py`
- `deploy/minimal/runtime-profile.example.json`
- `deploy/minimal/tests/test_runtime_profile.py`
- `deploy/minimal/README.md`
- `tasks/evidence/TASK-018/`

## Next Step

Review and merge the public proposal. Do not begin private source acceptance or
live deployment until that merge is confirmed.

## Result

Runtime Profile schema v2 now exposes one structured Context workspace option
that can derive only the read-only registry and explicitly scoped managed-
projects mounts. Schema v1 remains compatible, unsafe or ambiguous roots fail
closed, and no consumer deployment state changed.
