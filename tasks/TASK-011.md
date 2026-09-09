# TASK-011: Align Deployer IAM With First Deployment

Status: Completed
Priority: High

## Goal

Make the temporary minimal-host deployer policy authorize the current
first-deployment workflow with explicit least-privilege boundaries for AWS
discovery, the consumer Runtime Profile, and both artifact prefixes, while
documenting the separate bootstrap identity boundary.

## Acceptance Criteria

- The discovery permissions include every EC2 read action used by
  `discover-environment.sh`.
- Runtime Profile read/write access is limited to the explicitly rendered SSM
  parameter name and no retired runtime-state path remains.
- S3 bucket-location, prefix listing, and object access distinguish the
  template and runtime-bundle prefixes without applying an unsupported prefix
  condition to bucket-location reads.
- Quickstart and the policy README distinguish account bootstrap, optional
  Secret deployment, minimal-host deployment, and long-lived operation.
- Focused policy tests and complete repository validation pass without making
  AWS changes.

## Completed

- Confirmed TASK-010 was merged into the accepted `main` baseline.
- Audited the policy against the discovery and artifact publication scripts.
- Added `ec2:DescribeRouteTables` and a contract test deriving every required
  EC2 discovery action from `discover-environment.sh`.
- Replaced the retired runtime-state SSM path with exact `GetParameter` and
  `PutParameter` access to the rendered Runtime Profile parameter name.
- Split bucket-location access from prefix-constrained listing so
  `GetBucketLocation` is not subject to an inapplicable `s3:prefix` condition.
- Added distinct template and runtime-bundle prefixes to list and object
  permissions, with tests tied to both publisher scripts.
- Documented separate account-bootstrap, retained-Secret deployer,
  minimal-host deployer, and long-lived operator boundaries.
- Passed 11 minimal-host tests, 7 bootstrap tests, 19 Token Observer tests,
  complete repository validation, and Context Kit project validation.

## Remaining

None.

## Blockers

None.

## Result

The rendered minimal-host deployer policy now matches the repository's
discovery, Runtime Profile publication, template publication, and runtime-bundle
publication paths without granting global SSM parameter reads or silently
omitting the runtime artifact prefix. The public instructions identify which
deployment phases require separate identities. Validation is static and
offline; an operator must still perform the documented restricted-identity AWS
acceptance in their own account.

## Relevant Files

- `deploy/minimal/policies/deployer-policy.json.tmpl`
- `deploy/minimal/policies/README.md`
- `deploy/minimal/validate-template.sh`
- `deploy/minimal/tests/test_deployer_policy.py`
- `deploy/QUICKSTART.md`
- `tasks/TASK-011.md`

## Next Step

None for TASK-011. Review and accept this bounded proposal before starting the
separate post-Change-Set onboarding remediation Task.
