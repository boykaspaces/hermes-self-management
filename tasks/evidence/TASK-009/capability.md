# Capability Audit — TASK-009

Status: Passed
Applicability: Required
Gate Result: Pass

## Environment

- Project: `hermes-self-management`
- Existing accepted project base: `bf03d65d501b4f8cde5a992685d0c54e66fd8aa4`
- Existing adopted Kit: `0.2.0`, specification v1, repository profile
- Target accepted Kit: `80eea0d7a828ed50ddc92a9baea55d0dec1f8e00`
- Target Kit metadata: `0.5.0`, specification v2
- Prototype source: isolated clone of accepted component candidate
  `f540a990124ae813074d54c73e94bff21087a712`
- Evidence date: 2026-09-09

## Required Guarantees

| ID | Guarantee | Required Primitive | Evidence | Failure Boundary | Result | Disposition |
|---|---|---|---|---|---|---|
| CAP-1 | The accepted migration tool recognizes the existing v1 repository profile without guessing identity | Context Kit v2 migration check | Isolated check selected project `hermes-self-management`, profile `repository`, and proposed only the v2 namespace | Ambiguous identity, profile, or unsupported legacy state | Supported | Keep |
| CAP-2 | Migration preserves existing state while creating a valid v2 namespace | Context Kit migration apply and validator | Isolated apply created manifest, state, index, and checkpoint index; validation returned `context-kit-ok` | Silent legacy deletion or state loss | Supported | Keep |
| CAP-3 | The advisory extension and governed Task coexist with v2 validation | Manifest extension object and optional Task fields | Isolated manifest enabled `delivery-governance`; a `Governance: Required` Task and active pointers validated | Schema or parser rejection | Supported | Keep |
| CAP-4 | Consumer-native validation can move to v2 owners without modifying product/runtime behavior | Repository-controlled validation script | Isolated validator accepted the exact v2 manifest and `.context-kit/state.md`; all native validation passed | Product validation coupled irreducibly to legacy namespace | Supported | Keep |
| CAP-5 | Source adoption proves the optional Skill is installed and discovered in live Hermes | Host-owned runtime installation and discovery | No live host mutation was performed | Repository proposal falsely reports live readiness | Unsupported | Reduce Contract |
| CAP-6 | This repository has enforced exact-head GitHub checks for the adoption | Repository workflow and branch policy | No repository workflow is assumed by this Task; exact-head validation is local plus disclosed PR evidence | Local result misreported as required remote enforcement | Unsupported | Reduce Contract |

## Feasibility Evidence

The accepted migration check reported:

```text
would migrate profile repository to project spec v2
create .context-kit/manifest.json
create .context-kit/state.md
create .context-kit/index.md
create .context-kit/checkpoints/README.md
retain legacy .hermes files for reviewed removal after validation
```

After isolated apply, extension adoption, Task routing, and native-validator
owner updates:

```text
context-kit-ok: hermes-self-management (repository)
markdown-relative-links-ok
hermes-self-management repository validation passed
```

The native suite included 7 runtime-profile tests, 19 Token Observer tests,
6 bootstrap tests, CloudFormation/template validation, shell parsing, private
identifier checks, and Markdown links. Token Observer's loopback tests required
their existing non-sandboxed local execution boundary.

## Contract Reduction

- The proposal records source/project adoption only, not live Skill readiness.
- Exact-head validation is a clean local result bound to the PR head and is not
  described as a required GitHub status check.
- Private lock, integration, and deployment acceptance remain unchanged.
- Legacy project-context files are removed only after the new namespace passes
  both validators in the proposal.

## Gate Result

PASS — every guarantee retained by the Task contract has executable evidence.
Unsupported live installation and remote-enforcement claims were removed
rather than assumed or accepted as risk.
