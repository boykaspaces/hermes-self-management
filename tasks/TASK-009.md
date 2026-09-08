# TASK-009: Pilot Advisory Delivery Governance Adoption

Status: In Progress
Delivery Stage: Fix
Governance: Required
Priority: High

## Goal

Migrate this existing repository-profile project from its accepted Context Kit
0.2.0/specification-v1 context to Context Kit 0.5.0/specification-v2, explicitly
adopt the optional advisory delivery-governance capability, and prove that this
Task can be recovered, reviewed, validated, and completed from persistent
project artifacts without relying on conversation history.

## Accepted Dependencies

- Existing project identity: `hermes-self-management`
- Existing accepted project base: `bf03d65d501b4f8cde5a992685d0c54e66fd8aa4`
- Ops-selected component candidate contained by that base:
  `f540a990124ae813074d54c73e94bff21087a712`
- Accepted Context Kit source: `80eea0d7a828ed50ddc92a9baea55d0dec1f8e00`
- Optional Skill: `ai-delivery-governance` version `0.1.0`

These are source and protocol inputs. This Task does not advance the private
component lock or claim live runtime installation.

## Acceptance Criteria

- AC-1: `Project ID: hermes-self-management` remains unchanged while the
  explicit adoption manifest migrates to Context Kit 0.5.0, specification v2,
  repository profile, Hermes adapter v3, and GitHub workflow adapter v1.
- AC-2: The manifest enables `delivery-governance` in advisory mode and names
  `ai-delivery-governance`; installation availability is not misreported as a
  live runtime fact.
- AC-3: `PROJECT.md`, `README.md`, `AGENTS.md`, the context index, state, and
  file map route current project-context operations through `.context-kit/`.
  Legacy `.hermes/` project-context duplicates are removed only after v2
  validation succeeds.
- AC-4: Recovery from `PROJECT.md` through `.context-kit/index.md`,
  `tasks/current.md`, and this Task reconstructs the selected project, active
  work, frozen contract, evidence, and next action without conversation
  history.
- AC-5: This Task exercises Capability Gate 0, contract freeze, Initial Audit,
  focused fixes when required, Delta Review, deterministic validation,
  candidate completion, and exact-head Final Audit using Task-linked evidence.
- AC-6: The repository-native validator owns the exact v2 adoption manifest
  and `.context-kit/state.md` pointer, and both Context Kit validation and the
  complete native repository validation pass.
- AC-7: No infrastructure, runtime bundle, patch, IAM, network, Secret,
  production binding, deployment evidence, private component lock, or other
  repository changes.

## Supported Scope

- The existing `hermes-self-management` repository-profile project.
- Context Kit's supported specification-v1 to specification-v2 migration.
- Public project-context routing and repository-local validation.
- Advisory governance of this one bounded adoption proposal.
- GitHub proposal identity plus exact-candidate local validation evidence.

## Out of Scope

- Installing Skills into `/home/hermes/.hermes` or verifying a live Hermes
  runtime; the rollout reserves that for a later deployment increment.
- Updating `self-management-agent-ops`, `components/lock.json`, any System
  Task, integration state, or deployment binding.
- Changing CloudFormation, deployment scripts, runtime profiles, patches,
  plugins, application code, credentials, or production identifiers.
- Enrolling `hermes-personal-tools` or another project.
- Adding governance automation or a required GitHub status check.

## Capability Audit

Applicability: Required
Gate Result: Pass
Matrix: `tasks/evidence/TASK-009/capability.md`

The isolated feasibility project proved that the accepted migration tool can
create and validate the v2 namespace, retain the old namespace until review,
accept the advisory extension and governed Task, and converge with the
consumer's native validator after that validator switches to the v2 owner.

## Required Validation

- Context Kit `80eea0d7a828ed50ddc92a9baea55d0dec1f8e00` migration check and repository validation.
- `./scripts/validate.sh` in the consumer repository; its existing Token
  Observer tests require local loopback binding outside the file sandbox.
- Manual recovery traversal from `PROJECT.md` to the active Task and evidence.
- Clean exact-candidate validation followed by GitHub pull-request head
  comparison and disclosed Final Audit evidence.

## Review

Ledger: `tasks/evidence/TASK-009/review.md`

## Completed

- Resolved the target identity from `PROJECT.md` and confirmed no active Task.
- Confirmed current accepted `main` contains the ops-selected component
  candidate without changing the private lock.
- Read the project-context protocol from the project's accepted Context Kit
  0.2.0 release before creating this Task.
- Ran an isolated 0.2.0/spec-v1 to 0.5.0/spec-v2 migration check and apply.
- Verified the isolated v2 project with the accepted Context Kit validator.
- Added the advisory extension and a minimal governed Task in the isolated
  project; both Context Kit and complete consumer validation passed.
- Recorded that existing Token Observer tests require local loopback authority
  and fail inside the file sandbox independently of this adoption.
- Froze the Task contract at
  `b24d5ae325b7c4bc4ea849bb0eaf9258eb334434` after the accepted 0.2.0
  validator and complete consumer validation passed.
- Applied the accepted Context Kit migration to specification v2 with Hermes
  adapter v3 and GitHub workflow adapter v1.
- Enabled advisory `delivery-governance` and named the optional
  `ai-delivery-governance` Skill without claiming live installation.
- Updated the public recovery routes and native manifest/state validation to
  the `.context-kit/` owner.
- Passed Context Kit and complete consumer validation before removing the four
  legacy `.hermes/` project-context duplicates.
- Committed the bounded implementation candidate at
  `92938e8a7d6675226d6c012cf78866fd98c325ec`.
- Recovered the project, active Task, frozen contract, evidence, and next
  action through the persisted `PROJECT.md` route without conversation state.
- Completed Initial Audit with one P1 stale recovery-action finding and no
  product, runtime, integration, or deployment source changes.

## Remaining

- Resolve R-001 and run Delta Review against the Task recovery state.
- Run required validation and exact-head Final Audit.

## Blockers

None.

## Relevant Files

- `.context-kit/manifest.json`
- `.context-kit/index.md`
- `.context-kit/state.md`
- `.context-kit/checkpoints/README.md`
- `PROJECT.md`
- `README.md`
- `AGENTS.md`
- `docs/FILE_MAP.md`
- `scripts/validate.sh`
- `tasks/TASK-009.md`
- `tasks/evidence/TASK-009/`

## Next Step

Resolve R-001 by replacing the stale implementation action with the current
review/validation action, then verify recovery routing in Delta Review.
