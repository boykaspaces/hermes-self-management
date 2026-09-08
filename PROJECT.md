# Hermes Self Management

Project ID: hermes-self-management
Name: Hermes Self Management
Status: Active

## Goal

Provide a reproducible and security-bounded deployment for a self-managing
Hermes agent while keeping production state and identity outside public source.

## Sources of truth

- CloudFormation, scripts, policy templates, service units, and patch bundles
  own implementation truth.
- The nearest deployment or plugin README owns current operating instructions.
- `docs/SECURITY.md` owns the repository-level trust-boundary summary.
- `docs/FILE_MAP.md` owns navigation only.
- `tasks/` and `.context-kit/` own only this public repository's maintenance state.

## Context entry points

| Artifact | Purpose | Read when |
|---|---|---|
| [`.context-kit/manifest.json`](./.context-kit/manifest.json) | Adopted Context Kit contract | Changing or validating project context |
| [`.context-kit/index.md`](./.context-kit/index.md) | Current-first repository context | Starting or resuming maintenance |
| [`.context-kit/state.md`](./.context-kit/state.md) | Current repository summary | Asking what work is active |
| [`tasks/current.md`](./tasks/current.md) | Primary active Task pointer | Continuing current component work |
| [`docs/decisions/README.md`](./docs/decisions/README.md) | Repository decision index | Work depends on a durable local decision |

## Boundaries

- No production account identifiers, endpoints, parameter values, deployment
  records, credentials, consuming deployment Tasks/Checkpoints, or live
  `SOUL.md`. Public repository-maintenance context must remain generic.
- Host replacement, provider changes, network broadening, and patch migration
  require explicit review and validation by the consuming operator.
