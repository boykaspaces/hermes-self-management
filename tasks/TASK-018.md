# TASK-018: Add Structured Context Workspace Mounts

Status: In Progress
Type: Component
Governance: Required
Delivery Stage: Plan
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

## Remaining

- Freeze the contract, implement schema v2 and deterministic translation, then
  run the declared review and validation.

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

Freeze this contract, then implement the v1-compatible v2 schema and exact
two-mount translation with focused negative tests.
