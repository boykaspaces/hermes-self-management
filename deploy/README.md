# Deployment Index

| Path | Status | Owns | Read when |
|---|---|---|---|
| [`QUICKSTART.md`](./QUICKSTART.md) | Active | Fresh-clone prerequisites, private parameter boundary, artifact publication, and initial Change Set review | Deploying this repository in a new AWS account |
| [`preflight.sh`](./preflight.sh) | Active | Versioned local-tool checks and optional read-only AWS identity validation | Verifying a workstation before creating deployment resources |
| [`bootstrap/`](./bootstrap/README.md) | Optional | Read-only environment discovery, dedicated VPC/subnet, and retained private artifact bucket | Existing account resources are unknown or unsuitable |
| [`minimal/`](./minimal/README.md) | Active | SSM-only EC2 host, Rootless Podman Terminal, model policy, first-deployment recovery, managed patches, observability install, and optional Personal Tools integration | Deploying, recovering, or upgrading Hermes |
| [`hermes-runtime-secrets/`](./hermes-runtime-secrets/README.md) | Active | Retained Telegram runtime Secret container | Creating or rotating runtime credentials |
| [`budget/`](./budget/README.md) | Active | Model-cost warning/cutoff and account-wide budget | Establishing cost controls |

For a first deployment, follow `QUICKSTART.md`; the public repository does not
assume access to this project's private operations repository. Deploy retained
Secrets before the host and the budget after the host role exists. Record
actual parameters, Stack IDs, artifact versions, checksums, and rollback
targets only in the consuming operator's private system.
