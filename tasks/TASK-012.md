# TASK-012: Complete the First-Conversation Quickstart

Status: Completed
Priority: High

## Goal

Extend the public Quickstart from a reviewed Change Set through execution,
owner OAuth, model confirmation, localhost-only Dashboard access, one successful
conversation, and a second successful conversation after an instance reboot.

## Acceptance Criteria

- Quickstart provides copyable commands to execute the reviewed Change Set,
  wait for `CREATE_COMPLETE`, capture the instance ID, and confirm SSM is
  online.
- Owner authentication uses the pinned Hermes command and links directly to
  the repository's model-provider strategy and official OpenAI authentication
  guidance.
- The host template outputs a copyable SSM Dashboard port-forward command and
  loopback URL without adding inbound network access.
- The acceptance path defines observable success markers for service health,
  model availability, the first Dashboard conversation, EC2 reboot recovery,
  and the second conversation.
- Contract tests and complete repository validation pass without executing a
  Change Set, authenticating an account, opening an SSM session, or changing
  AWS resources.

## Completed

- Confirmed TASK-011 was merged into the accepted `main` baseline.
- Verified the pinned Hermes CLI exposes `auth`, `model`, Dashboard Chat, and
  one-shot chat paths.
- Checked the official OpenAI device-code authentication boundary and official
  AWS Change Set waiter and Session Manager port-forwarding commands.
- Extended Quickstart through Change Set execution, stack and SSM readiness,
  owner OAuth, model confirmation, Gateway reload, Dashboard forwarding, the
  first conversation, and stop/start persistence acceptance.
- Added CloudFormation Outputs for the Dashboard port-forward command and
  loopback URL without changing the host network boundary.
- Added regression coverage for the ordered first-use path and new Outputs.
- Passed complete repository validation and Context Kit validation without
  making AWS, OAuth, SSM, or model calls.

## Remaining

None.

## Blockers

None.

## Relevant Files

- `deploy/QUICKSTART.md`
- `deploy/minimal/cloudformation.yaml`
- `deploy/minimal/validate-template.sh`
- `deploy/bootstrap/tests/test_bootstrap.py`
- `tasks/TASK-012.md`

## Result

The public first-deployment path now has copyable commands and observable
success criteria from a reviewed Change Set through the first successful
conversation and a second successful conversation after an instance restart.

## Next Step

Review and accept this bounded proposal before starting the separate
prerequisite-and-feature-limit remediation Task.
