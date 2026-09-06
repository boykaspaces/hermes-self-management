# Repository AI Instructions

## Entry and retrieval

- Start with `README.md`; use `.hermes/context-index.md` for repository
  maintenance state, then follow the narrowest deployment or plugin route.
- Prefer CloudFormation, scripts, policy templates, tests, and the nearest
  README over summaries.
- Load version-specific patch files only when changing or validating that patch
  set.

## Project and system context

- Use `project-context-management` from the reviewed Hermes Context Kit for
  this repository's Task, State, Checkpoint, ADR, and index mutations.
- Also use `multi-repo-system-management` when a Task has a parent System Task,
  changes another repository, advances a component revision, or requires an
  integration Handoff.
- If the integration repository is inaccessible, produce a validated Handoff;
  do not claim its Task, lock, deployment, or acceptance state changed.

## Boundaries

- Never add production identifiers, deployment records, credentials, live
  runtime state, consuming deployment context, or environment overrides.
- Do not broaden network, IAM, filesystem, container, model-fallback, or Secret
  boundaries without an explicit decision and matching negative tests.
- Preserve immutable upstream revisions and artifact checksums.
- Update affected indexes when paths or ownership change.

## Validation

- Run `scripts/validate.sh` after repository-wide changes.
- Run `deploy/minimal/validate-template.sh` after host-template changes.
- Run the Token Observer unit tests after plugin changes.
