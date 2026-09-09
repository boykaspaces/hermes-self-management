# TASK-015: Add First-Deployment Failure Recovery

Status: Completed
Priority: High

## Goal

Give a new operator a safe, copyable path to diagnose and recover from a
failed first deployment without blindly rerunning creation, losing useful
evidence, exposing services, or guessing which CloudFormation operation is
valid.

## Acceptance Criteria

- Initial Change Sets preserve provisioned resources on failure so an operator
  can inspect a failed host, while the helper still never executes or deletes
  a Change Set or Stack.
- The Change Set helper distinguishes a new Stack from a preserved
  `CREATE_FAILED` or `UPDATE_FAILED` Stack, prepares only the valid CREATE or
  recovery UPDATE request, and rejects unsafe or ambiguous states.
- A first-deployment recovery runbook covers Stack failure, unavailable SSM,
  Runtime Profile failure, OAuth failure, and Dashboard failure with log
  locations, diagnostic commands, success evidence, and explicit retry gates.
- The restricted deployment identity can read EC2 console output needed when
  SSM is unavailable without adding ingress or write authority.
- Quickstart routes a failed waiter directly to recovery and distinguishes the
  create and recovery-update waiters.
- Positive and negative tests plus complete repository and Context Kit
  validation pass without creating, updating, or deleting AWS resources.

## Completed

- Confirmed TASK-014 was merged into the accepted `main` baseline.
- Verified first boot reports through an EC2 `CreationPolicy` and explicit
  CloudFormation success/failure signals.
- Verified the current helper always requests `CREATE`, uses default rollback
  behavior, and provides no status-aware recovery path.
- Confirmed the restricted deployer lacks EC2 console-output access needed when
  SSM never connects.
- Changed initial Change Set creation to preserve provisioned resources on
  failure and made the helper inspect the current Stack before choosing CREATE
  or a failed-first-deployment recovery UPDATE.
- Added fail-closed handling for active, healthy, rolled-back,
  deletion-failed, rollback-failed, unknown, and unauthorized Stack-status
  checks; the helper still never executes or deletes resources.
- Added a first-deployment recovery runbook with private evidence capture,
  status decisions, log locations, diagnostic commands, retry gates, recovery
  UPDATE execution, and explicit destructive cleanup warnings.
- Added read-only `ec2:GetConsoleOutput` to the restricted deployment identity
  so failed hosts can be diagnosed without SSM, SSH, or ingress.
- Routed Quickstart failures to the recovery runbook and documented the exact
  helper contracts and correct create/update waiters.
- Added positive and negative helper, documentation, and IAM tests.
- Passed complete repository and Context Kit validation without creating,
  updating, or deleting AWS resources.

## Remaining

None.

## Blockers

None.

## Relevant Files

- `deploy/minimal/create-change-set.sh`
- `deploy/minimal/FIRST_DEPLOYMENT_RECOVERY.md`
- `deploy/QUICKSTART.md`
- `deploy/minimal/policies/deployer-policy.json.tmpl`
- `deploy/bootstrap/tests/test_bootstrap.py`
- `deploy/minimal/tests/test_deployer_policy.py`
- `tasks/TASK-015.md`

## Result

A failed first deployment now retains evidence by default and has one bounded
route from observed Stack state to diagnosis, retry, or explicit cleanup. New
operators receive copyable commands and success gates for CloudFormation, SSM,
Runtime Profile, OAuth, and Dashboard failures without weakening the runtime's
network, identity, Secret, or model-fallback boundaries.

## Next Step

Review and accept this final bounded proposal from the first-deployment review.
