# Project State

Project: hermes-self-management
Status: Active
Active Task: None

## Current summary

The public runtime component is independently deployable and validated. Runtime
configuration, managed patches, and Token Observer are delivered as one
immutable, checksummed S3 bundle while CloudFormation owns its identity and a
small loader; User Data remains pinned and unchanged. The bundle retains the
completed OAuth-only allowlist egress and Rootless Podman routing work from
TASK-002.

## Primary focus

No active Task. The completed TASK-004 candidate is ready for publication and
deployment acceptance by `personal-hermes-agent:TASK-013`.

## Active constraints

- Production bindings and deployment evidence remain in private operations.
- Public source must build and validate without private repository access.
