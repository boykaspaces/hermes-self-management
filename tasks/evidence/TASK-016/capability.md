# Capability Audit — TASK-016

Status: Frozen
Applicability: Required
Gate Result: Pass

## Minimum Desired Outcome

Preserve Hermes' ordinary parent `/workspace` sandbox when consumer-neutral
nested volumes are configured, without designing or deploying those volumes in
the same Component Task.

## Required Guarantees

| ID | Guarantee | Required Primitive | Evidence | Failure Boundary | Result | Disposition |
|---|---|---|---|---|---|---|
| CAP-1 | A nested destination does not replace the parent workspace | Exact Docker volume destination classification | The pinned source currently uses substring matching in container setup | Any future `/workspace/...` mount suppresses the persistent bind or ephemeral tmpfs | Unsupported | Repair |
| CAP-2 | An exact `/workspace` destination retains current replacement behavior | Exact destination parser plus container-argument tests | Existing source deliberately suppresses the generated parent mount for an explicit replacement | The repair could create duplicate parent mounts | Supported | Keep and Test |
| CAP-3 | The repair is deterministic against the accepted source | Existing ordered patch application, verification, archive, and checksum pipeline | P-002, P-003, and P-005 establish the version-pinned mechanism | An untracked source edit could drift between build and restore | Supported | Extend with P-006 |
| CAP-4 | Public evidence remains consumer-neutral | Component Task and repository-native tests | No live host or consumer path is needed to prove argument classification | Private identifiers or deployment claims could leak into public source | Supported | Keep |
| CAP-5 | Structured workspace configuration can wait | Separate System/Component Task boundary | Exact classification is independently testable before schema design | Combining both increments widens review and obscures the prerequisite | Supported | Defer Feature |

## Contract Disposition

- Repair CAP-1 with exact parsed-destination comparison.
- Preserve and expand tests for CAP-2.
- Extend the existing pinned patch mechanism for CAP-3.
- Keep CAP-4 as a public/private evidence boundary.
- Defer CAP-5 to a separate later Task after P-006 is accepted.

## Gate Evaluation

- Required retained guarantees: CAP-2 through CAP-4.
- Required repair: CAP-1.
- Deferred feature: CAP-5.
- Retained Unknown guarantees: None.
- Authorized risk acceptances: None.

Gate Result: `Pass`
