# Deployment Index

| Path | Status | Owns | Read when |
|---|---|---|---|
| [`minimal/`](./minimal/README.md) | Active | SSM-only EC2 host, Rootless Podman Terminal, model policy, managed patches, observability install, and optional Personal Tools integration | Deploying or upgrading Hermes |
| [`hermes-runtime-secrets/`](./hermes-runtime-secrets/README.md) | Active | Retained Telegram runtime Secret container | Creating or rotating runtime credentials |
| [`budget/`](./budget/README.md) | Active | Model-cost warning/cutoff and account-wide budget | Establishing cost controls |

Deploy retained Secrets before the host. Deploy the budget after the host role
exists. Record actual parameters, Stack IDs, artifact versions, checksums, and
rollback targets only in the private operations repository.
