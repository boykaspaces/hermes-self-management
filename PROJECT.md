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
- `tasks/` and `.hermes/` own only this public repository's maintenance state.

## Context entry points

| Artifact | Purpose | Read when |
|---|---|---|
| [`.hermes/context-index.md`](./.hermes/context-index.md) | Current-first repository context | Starting or resuming maintenance |
| [`.hermes/state.md`](./.hermes/state.md) | Current repository summary | Asking what work is active |
| [`tasks/current.md`](./tasks/current.md) | Primary active Task pointer | Continuing current component work |
| [`docs/decisions/README.md`](./docs/decisions/README.md) | Repository decision index | Work depends on a durable local decision |

## Boundaries

- No production account identifiers, endpoints, parameter values, deployment
  records, credentials, consuming deployment Tasks/Checkpoints, or live
  `SOUL.md`. Public repository-maintenance context must remain generic.
- Host replacement, provider changes, network broadening, and patch migration
  require explicit review and validation by the consuming operator.
