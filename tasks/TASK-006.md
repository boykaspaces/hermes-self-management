# TASK-006: Preserve Runtime Profile Bytes

Status: Completed
Type: Component
Priority: High
Parent System Task: personal-hermes-agent:TASK-015

## Goal

Preserve the exact SSM Runtime Profile bytes when caching the profile on the
Hermes host so the deployed cache has the same SHA-256 as the reviewed source.

## Completed

- Reproduced the production-only extra trailing newline introduced by AWS CLI
  `text` output.
- Changed the Metadata loader to extract `Parameter.Value` from JSON without
  appending output bytes.
- Added a template validation assertion for the lossless extraction path.
- Passed the complete repository validator, including 7 Runtime Profile tests,
  template/User Data checks, and 19 Token Observer tests.

## Remaining

None.

## Blockers

None.

## Relevant Files

- `deploy/minimal/cloudformation.yaml`
- `deploy/minimal/validate-template.sh`

## Related Work

- `personal-hermes-agent:TASK-015`

## Next Step

None.

## Result

The cached production Runtime Profile can now be compared byte-for-byte with
the reviewed private source and its published SSM value.
