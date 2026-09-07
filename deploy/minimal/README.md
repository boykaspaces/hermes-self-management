# Minimal Hermes Host

This domain deploys a single Ubuntu EC2 host with no inbound security-group
rules, Systems Manager access, a non-root Hermes user, systemd-managed Gateway
and Dashboard, Rootless Podman Terminal execution, optional restricted Git
coding, retained context mounts, managed upstream patches, and Token Observer.

## Source map

| Path | Owns |
|---|---|
| `cloudformation.yaml` | Host, IAM role, network rules, bootstrap, units, runtime configuration, and outputs |
| `validate-template.sh` | Embedded artifact, YAML, User Data, shell, IAM, and security-invariant checks |
| `publish-template.sh` | Content-addressed upload for templates larger than the inline CloudFormation limit |
| `patches/` | Version-specific upstream Hermes patch source and applied-file checksums |
| `apply-hermes-patches.sh` | Commit-bound apply, verify, and restore operations |
| `sync_hermes_patch_archive.py` | Deterministic patch bundle embedded into Instance metadata |
| `sync_token_observer_archive.py` | Deterministic plugin bundle embedded into Instance metadata |
| `HERMES_UPGRADE_RUNBOOK.md` | Required upgrade, patch migration, regression, and rollback sequence |
| `MODEL_PROVIDER_STRATEGY.md` | Subscription-first provider and no-automatic-fallback policy |
| `policies/` | Rendered operator/deployer policy examples |
| `stack-policy.json` | Replacement/deletion guard for the EC2 instance |

## Required deployment inputs

Choose and record privately:

- VPC and subnet with the intended outbound path;
- reviewed AMI ID for the target Region;
- exact Hermes Git commit compatible with the managed patch set;
- optional retained Telegram Secret ARN;
- optional Personal Tools MCP URL and client-token Secret ARN;
- optional Credential Lease API ID and immutable credential-agent artifact;
- optional state-backup bucket/key;
- expected model identifier exposed by the authenticated subscription account.

The template contains no production default AMI, Secret ARN, API endpoint,
account ID, instance ID, or bucket.

## Validate

```sh
./deploy/minimal/validate-template.sh
```

For AWS validation of the large template:

```sh
AWS_REGION="$AWS_REGION" \
HERMES_TEMPLATE_BUCKET="$ARTIFACT_BUCKET" \
./deploy/minimal/publish-template.sh
```

The publish script uploads to a content-addressed key and then invokes AWS
template validation. Upload and deployment are operator-controlled writes.

## Deployment sequence

1. Render and review `policies/deployer-policy.json.tmpl` outside the repository.
2. Validate templates and create an EBS snapshot/rollback point for updates.
3. Publish the content-addressed template and create a Change Set.
4. Reject unexpected EC2 replacement; apply `stack-policy.json` before a
   production update.
5. Execute the Change Set and confirm the physical instance/volume behavior.
6. Complete subscription OAuth manually as the owner; never inject OAuth files
   through CloudFormation or backups.
7. Run Gateway, Dashboard, Podman, egress, patch, observability, and optional
   credential-lease smoke and negative tests.
8. Replace temporary deployer access with the rendered operator policy.

See `HERMES_UPGRADE_RUNBOOK.md` before changing `HermesGitRef` or a managed
patch set.

## Git coding boundary

The host provisioner is optional and receives IAM authority only when
`GitCodingEnabled=true`. The coding container receives a read-only tmpfs lease
mount, no instance role, no container-engine socket, and egress through the
configured proxy. Repository protected-ref rules must be proven before enabling
credential issuance.

On subscription-OAuth hosts the runtime uses
`hermes egress setup --allowlist-only`: no model Provider API Key is required,
and the generated proxy policy contains only the explicit
`proxy.extra_allowed_hosts` catalogue. Setup fails closed when that catalogue is
empty. The host Credential Provisioner is installed beside `HERMES_BIN`
(`/home/hermes/.local/bin` in this template), while its short-lived lease output
remains under the user runtime directory mounted read-only into the coding
container. Docker reaches the loopback-bound proxy through
`host.docker.internal`; Rootless Podman uses its `10.0.2.2` host-loopback
gateway with `slirp4netns:allow_host_loopback=true`. That Podman override is
omitted when Terminal networking is disabled, so `--network=none` remains the
effective setting.

This is explicit-proxy enforcement, not transparent kernel-level egress
redirection. Proxy-aware Git, curl, and package tooling follow the allowlist,
but a process that deliberately removes the injected proxy and CA variables
may use the container's ordinary network path. Treat network-layer enforcement
as a separate deployment hardening requirement when the threat model includes
actively hostile code inside the coding container.
