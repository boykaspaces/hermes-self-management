# TASK-007: Preserve Runtime Profile Bytes

Status: Completed
Type: Component
Priority: High
Parent System Task: personal-hermes-agent:TASK-016

## Goal

Preserve the exact SSM Runtime Profile bytes when caching the profile on the
Hermes host so the deployed cache has the same SHA-256 as the reviewed source.

## Completed

- Reproduced the production-only extra trailing newline introduced by AWS CLI
  `text` output.
- Changed the Metadata loader to extract `Parameter.Value` from JSON without
  appending output bytes.
- Added a template validation assertion for the lossless extraction path.
- Passed production acceptance on the original EC2 instance, including exact
  cached-profile SHA-256, Gateway, Telegram, Personal Tools, and proxy checks.

## Remaining

None.

## Blockers

None.

## Relevant Files

- `deploy/minimal/cloudformation.yaml`
- `deploy/minimal/validate-template.sh`

## Related Work

- `personal-hermes-agent:TASK-016`

## Next Step

None.

## Result

The cached Runtime Profile remains byte-for-byte identical to the reviewed
private source and its published SSM value.
