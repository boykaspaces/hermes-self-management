# Project State

Project: hermes-self-management
Status: Active
Active Task: None

## Current summary

The public runtime component is independently deployable and validated. Mutable,
non-secret consumer preferences are now loaded from a separately validated SSM
runtime profile instead of CloudFormation or first-boot User Data. Generic
runtime orchestration, managed patches, and Token Observer remain in the
immutable, checksummed S3 bundle.

## Primary focus

No active Task. The completed TASK-005 candidate is ready for publication and
integration by `personal-hermes-agent:TASK-014`.

## Active constraints

- Production bindings and deployment evidence remain in private operations.
- Public source must build and validate without private repository access.
