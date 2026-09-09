# Project State

Project: hermes-self-management
Status: Active
Active Task: None

## Current summary

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

The TASK-012 candidate connects the reviewed Change Set to a complete first-use
acceptance path: execution, owner OAuth, model confirmation, localhost-only
Dashboard access, one successful conversation, and a second successful
conversation after restart. Static and offline validation passed; live AWS and
account acceptance remain operator-owned checks.

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

Review and accept the bounded TASK-012 proposal before starting the separate
prerequisite-and-feature-limit remediation Task. No primary active Task is
selected here.

## Active constraints

- Production bindings and deployment evidence remain in private operations.
- Public source must build and validate without private repository access.
