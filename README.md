# Hermes Self Management

An opinionated, auditable AWS runtime for a long-running Hermes agent. It
combines an SSM-only EC2 host, Rootless Podman Terminal isolation, restricted
coding egress, subscription-first model policy, retained runtime Secrets,
budget controls, version-pinned upstream patches, and privacy-preserving token
observability.

## Repository map

| Path | Status | Owns | Read when |
|---|---|---|---|
| [`deploy/`](./deploy/README.md) | Current index | Runtime, Secret, and budget CloudFormation domains | Deploying or operating AWS infrastructure |
| [`deploy/minimal/`](./deploy/minimal/README.md) | Active deployment | Hermes EC2 runtime and host bootstrap | Building, validating, or upgrading the host |
| [`hermes-plugins/observability/token_observer/`](./hermes-plugins/observability/token_observer/README.md) | Active source | Redacted model/tool usage metrics and local viewer | Changing or installing observability |
| [`docs/`](./docs/README.md) | Current index | Architecture, security, repository map, and integration contracts | Understanding or extending the system |
| [`.hermes/context-index.md`](./.hermes/context-index.md) | Current index | Public repository-maintenance context | Resuming development work |
| [`tasks/`](./tasks/README.md) | Active index | Component Tasks and current work pointer | Reviewing or continuing repository work |
| [`PROJECT.md`](./PROJECT.md) | Stable identity | Repository goal and source-of-truth boundaries | Starting repository work |
| [`AGENTS.md`](./AGENTS.md) | Active instructions | AI editing and validation rules | Before changing files |

Start with the narrowest deployment or plugin README. This repository's own
maintenance Tasks are public. Production parameters, deployment records,
actual account resources, and live Hermes context belong in a private
operations repository.

## Validation

```sh
./scripts/validate.sh
```

The command validates CloudFormation/YAML, rendered policy examples, embedded
artifacts, User Data shell, Python source/tests, Markdown links, and the public
identifier boundary. It makes no AWS changes.

## Related components

- [Hermes Personal Tools](https://github.com/boykaspaces/hermes-personal-tools)
  supplies the optional MCP and short-lived credential-lease services.
- [Hermes Context Kit](https://github.com/boykaspaces/hermes-context-kit)
  supplies optional global project-context Skills and neutral templates.

Pin external component releases, object versions, and checksums in the private
operator repository rather than tracking mutable branches at deployment time.
