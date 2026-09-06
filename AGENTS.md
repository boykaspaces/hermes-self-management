# Repository AI Instructions

## Entry and retrieval

- Start with `README.md`; follow the narrowest deployment or plugin route.
- Prefer CloudFormation, scripts, policy templates, tests, and the nearest
  README over summaries.
- Load version-specific patch files only when changing or validating that patch
  set.

## Boundaries

- Never add production identifiers, deployment records, credentials, live
  runtime state, or environment overrides.
- Do not broaden network, IAM, filesystem, container, model-fallback, or Secret
  boundaries without an explicit decision and matching negative tests.
- Preserve immutable upstream revisions and artifact checksums.
- Update affected indexes when paths or ownership change.

## Validation

- Run `scripts/validate.sh` after repository-wide changes.
- Run `deploy/minimal/validate-template.sh` after host-template changes.
- Run the Token Observer unit tests after plugin changes.
