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

## Boundaries

- No production account identifiers, endpoints, parameter values, deployment
  records, credentials, live `SOUL.md`, Tasks, or Checkpoints.
- Host replacement, provider changes, network broadening, and patch migration
  require explicit review and validation by the consuming operator.
