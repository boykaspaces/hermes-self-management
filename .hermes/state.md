# Project State

Project: hermes-self-management
Status: Active
Active Task: None

## Current summary

The public runtime component explicitly adopts Context Kit 0.2.0 project spec
v1 with the repository profile. Mutable, non-secret consumer preferences are
loaded from a separately validated SSM runtime profile instead of CloudFormation
or first-boot User Data. Generic runtime orchestration, managed patches, and
Token Observer remain in the immutable, checksummed S3 bundle.

## Primary focus

No active Task. Runtime Profile TASK-005 is ready for
`personal-hermes-agent:TASK-014`; Context Kit adoption TASK-006 is ready for
`personal-hermes-agent:TASK-015`.

## Active constraints

- Production bindings and deployment evidence remain in private operations.
- Public source must build and validate without private repository access.
