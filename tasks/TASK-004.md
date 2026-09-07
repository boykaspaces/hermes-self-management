# TASK-004: Extract Immutable Runtime Artifacts

Status: Completed
Type: Component
Priority: High
Parent System Task: personal-hermes-agent:TASK-013

## Goal

Keep EC2 User Data focused on first-boot initialization while moving runtime
configuration, managed patches, and Token Observer payloads out of the
CloudFormation template into immutable, checksummed S3 artifacts.

## Completed

- Confirmed the current template already separates RuntimeConfigScript into EC2
  Metadata, but still embeds the complete script and two Base64 archives.
- Preserved the validated Telegram feedback and local Skill/Memory approval
  settings from TASK-003 as requirements of the extracted runtime artifact.
- Added a deterministic runtime bundle containing `runtime-config.sh`, the
  managed patch archive, and the Token Observer archive.
- Added a content-addressed S3 publisher and an EC2 Metadata loader that verifies
  SHA-256, safely extracts allowlisted regular files, and caches digest-named
  releases for rollback and transient S3 failures.
- Reduced the CloudFormation template from 92,421 to 38,234 bytes while keeping
  User Data byte-for-byte unchanged at 13,978 bytes and SHA-256
  `ebcded4c2ab9d61c9576c6e561539c11f958acb2750c952d560ef041508e35ef`.
- Added least-privilege read access to only the selected runtime bundle and
  pinned the User Data digest as an intentional-change guard.
- Passed template validation, deterministic artifact checks, all 19 Token
  Observer tests, Markdown link validation, and the full repository validator.

## Remaining

None.

## Blockers

None.

## Relevant Files

- `deploy/minimal/cloudformation.yaml`
- `deploy/minimal/runtime-config.sh`
- `deploy/minimal/publish-runtime-artifacts.sh`
- `deploy/minimal/validate-template.sh`
- `deploy/minimal/README.md`

## Related Work

- TASK-003

## Next Step

None.

## Result

Runtime behavior is now delivered as one immutable, checksummed bundle while
CloudFormation retains infrastructure, the artifact identity, and a small
loader. Existing instances can adopt it in place without changing User Data.
