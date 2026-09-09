# Project State

Project: hermes-self-management
Status: Active
Active Task: None

## Current summary

TASK-017's bounded candidate corrects TASK-016's `Parent System Task` field to
the bare canonical identity required by the reviewed multi-repository
validator. The correction changes no P-006 implementation, patch archive,
Runtime Profile, deployment artifact, or private source lock.

TASK-010 is accepted on `main` and corrects the first-deployment Runtime Profile
parameter-name handoff: Quickstart now uses one exported SSM name for profile
publication and private CloudFormation parameter-file generation, while a
contract test prevents a second concrete example path from drifting
independently.

TASK-011 is accepted on `main` and aligns the temporary minimal-host deployer
policy with the public first-deployment workflow. It covers exact Runtime
Profile access, separate template and runtime-bundle prefixes, route-table
discovery, and the documented boundary between account bootstrap and the
restricted deployment identity.

TASK-012 is accepted on `main` and connects the reviewed Change Set to a
complete first-use acceptance path: execution, owner OAuth, model confirmation,
localhost-only Dashboard access, one successful conversation, and a second
successful conversation after restart.

TASK-013 is accepted on `main` and makes the supported workstation and EC2
target, required local tools, model authentication, outbound-network
dependency, and default runtime capability limits explicit before any AWS
resource creation. Its versioned preflight checks those local dependencies and
can optionally verify AWS identity through a read-only STS call.

TASK-014 is accepted on `main` and pins and verifies the first-boot installer,
upstream dependency locks, Agent Browser package, and coding-container image,
then records the software versions actually installed for troubleshooting and
rollback.

TASK-015 is accepted on `main` and adds a status-aware first-deployment recovery path with
preserved failure evidence, bounded Stack retry rules, and symptom-specific
diagnostics for CloudFormation, SSM, Runtime Profile, OAuth, and Dashboard
failures.

TASK-016's bounded P-006 candidate is complete: exact destination
classification preserves the ordinary parent sandbox for nested
`/workspace/...` volumes, while an exact parent replacement retains existing
behavior. Review and accept the proposal before the private integration
repository advances its source lock. Structured Context workspace
configuration and live deployment remain separate later Tasks.

The public runtime component explicitly adopts Context Kit 0.5.0 project spec
v2 with the repository profile, Hermes adapter v3, GitHub workflow adapter v1,
and the advisory `delivery-governance` extension. The extension names the
optional `ai-delivery-governance` Skill without claiming it is installed in a
live runtime. Mutable, non-secret consumer preferences are
loaded from a separately validated SSM runtime profile instead of CloudFormation
or first-boot User Data. A public first-deployment path now covers read-only AWS
discovery, optional neutral bootstrap infrastructure, immutable artifact
publication, external consumer parameters, and human-reviewed Change Set
creation without private operations access. The TASK-009 candidate completes
the bounded Context Kit v2 migration and advisory-governance recovery, review,
and validation cycle while leaving live installation, integration, and
deployment state unchanged.

## Primary focus

Review and accept the bounded TASK-017 metadata proposal before private source
acceptance. No primary active Task is selected here.

## Active constraints

- Production bindings and deployment evidence remain in private operations.
- Public source must build and validate without private repository access.
