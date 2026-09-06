# TASK-002: Support OAuth-Only Restricted Coding Egress

Status: Completed
Type: Component
Priority: High
Parent System Task: personal-hermes-agent:TASK-008

## Goal

Make the optional Git coding runtime start safely when Hermes uses subscription
OAuth and has no model Provider API Key, while retaining default-deny
allowlisted container egress and correcting the host Credential Provisioner
installation path.

## Completed

- Confirmed the managed coding image, read-only lease mount, and Credential
  Provisioner signing path work in the consuming deployment.
- Reproduced that Hermes 0.21 `egress setup` rejects an empty model-provider
  mapping even though the underlying proxy can enforce an allowlist without a
  secrets transform.
- Added a version-pinned `--allowlist-only` CLI patch that refuses an empty
  explicit host catalogue and rejects incompatible secret-mapping options.
- Corrected Credential Provisioner installation to use the directory that owns
  `HERMES_BIN` instead of nesting it under `HERMES_HOME`.
- Added archive membership, applied-file digest, template invariant, and
  upstream regression validation.
- Updated the component operating and security documentation.

## Remaining

None.

## Blockers

None.

## Relevant Files

- `deploy/minimal/cloudformation.yaml`
- `deploy/minimal/validate-template.sh`
- `deploy/minimal/README.md`
- `docs/SECURITY.md`

## Next Step

The parent System Task may pin this component's immutable candidate, deploy it,
and record consuming-system acceptance evidence.

## Result

OAuth-only hosts can configure explicit, default-deny coding egress without a
dummy model Provider API Key. The managed patch set applies cleanly to the
pinned Hermes commit, its targeted regressions pass, and the host template
installs the Credential Provisioner at the executable path used by systemd.
