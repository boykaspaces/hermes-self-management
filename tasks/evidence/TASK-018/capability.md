# Capability Audit — TASK-018

Status: Frozen
Applicability: Required
Gate Result: Pass

## Minimum Desired Outcome

Prove the proposed structured profile can reuse the current application and
credential pipeline before changing its schema or translation.

## Required Guarantees

| ID | Guarantee | Evidence | Result | Disposition |
|---|---|---|---|---|
| CAP-1 | Existing profile application preserves two non-credential narrow mounts | Exact locked `apply_profile` retained registry and projects mounts | Supported | Keep |
| CAP-2 | Credential injection remains independent | Probe appended the credential destination after profile application | Supported | Keep |
| CAP-3 | Structured v2 remains within SSM Standard size | Proposed compact profile measured 1304 bytes against 4096-byte limit | Supported | Keep |
| CAP-4 | Unimplemented schema does not silently accept the field | Exact v1 validator rejected the proposed `context_workspace` key | Supported | Keep fail-closed behavior |
| CAP-5 | Nested mounts preserve the parent sandbox | Accepted P-006 tests and TASK-025 source graph | Supported | Keep dependency |

## Boundaries

- In-memory probe only; no repository or runtime mutation.
- Generic paths only; no private deployment identifiers or consumer values.
- Not proved here: directory verification, schema migration, live profile
  application, persistent Agent behavior, project adoption, or deployment.
