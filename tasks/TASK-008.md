# TASK-008: Add a Public AWS Bootstrap Path

Status: Completed
Type: Component
Priority: High
Parent System Task: personal-hermes-agent:TASK-017

## Goal

Let a new operator clone this public repository and prepare a secure,
reviewable first deployment of their own AWS-hosted Hermes Agent without any
dependency on a private operations repository or another consumer's production
identifiers.

## Completed

- Confirmed the reusable runtime, profile, Secret, and host templates already
  remain free of consuming production values.
- Added a clone-to-Change-Set quickstart that stores consumer parameters and
  deployment evidence outside the public clone.
- Added read-only account, VPC, subnet, route-table, and AMI discovery without
  silently selecting an account resource.
- Added optional reusable bootstrap templates for a no-ingress public
  VPC/subnet and a retained, encrypted, versioned private artifact bucket.
- Added a complete non-secret parameter example, an external Runtime Profile
  publisher, and a review-only Change Set creation helper.
- Added functional bootstrap tests and repository validation for the public
  deployment boundary.
- Passed the full component validation suite and AWS CloudFormation
  `validate-template` for both bootstrap templates in `ap-southeast-1`.

## Remaining

None.

## Blockers

None.

## Relevant Files

- `README.md`
- `deploy/README.md`
- `deploy/bootstrap/`
- `deploy/minimal/README.md`
- `deploy/minimal/parameters.example.json`
- `scripts/validate.sh`

## Next Step

Accept the resulting public source revision through
`personal-hermes-agent:TASK-017`. No production deployment is required for this
documentation, bootstrap-template, and review-only helper change.

## Result

A new operator can clone this repository, create or inspect prerequisites in
their own AWS account, keep all real identifiers in their own private system,
publish immutable artifacts, and prepare a human-reviewed initial Change Set
without access to the maintainer's private operations repository.
