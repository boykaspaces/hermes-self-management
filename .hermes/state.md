# Project State

Project: hermes-self-management
Status: Active
Active Task: None

## Current summary

The public runtime component explicitly adopts Context Kit 0.2.0 project spec
v1 with the repository profile. Mutable, non-secret consumer preferences are
loaded from a separately validated SSM runtime profile instead of CloudFormation
or first-boot User Data. A public first-deployment path now covers read-only AWS
discovery, optional neutral bootstrap infrastructure, immutable artifact
publication, external consumer parameters, and human-reviewed Change Set
creation without private operations access.

## Primary focus

No active Task. Public AWS bootstrap path TASK-008 is component-validated and
ready for integration acceptance through `personal-hermes-agent:TASK-017`.

## Active constraints

- Production bindings and deployment evidence remain in private operations.
- Public source must build and validate without private repository access.
