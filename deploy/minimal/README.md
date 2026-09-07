# Minimal Hermes Host

This domain deploys a single Ubuntu EC2 host with no inbound security-group
rules, Systems Manager access, a non-root Hermes user, systemd-managed Gateway
and Dashboard, Rootless Podman Terminal execution, optional restricted Git
coding, retained context mounts, managed upstream patches, and Token Observer.

## Source map

| Path | Owns |
|---|---|
| `cloudformation.yaml` | Host, IAM role, network rules, first-boot User Data, immutable runtime-bundle identity, and outputs |
| `runtime-config.sh` | Idempotent Hermes runtime configuration applied before Gateway start |
| `build_runtime_bundle.py` | Deterministic bundle of runtime configuration, managed patches, and Token Observer |
| `publish-runtime-artifacts.sh` | Content-addressed runtime-bundle upload and deployment parameter output |
| `validate-template.sh` | Runtime-bundle, YAML, User Data, shell, IAM, and security-invariant checks |
| `publish-template.sh` | Content-addressed CloudFormation template upload and AWS validation |
| `patches/` | Version-specific upstream Hermes patch source and applied-file checksums |
| `apply-hermes-patches.sh` | Commit-bound apply, verify, and restore operations |
| `sync_hermes_patch_archive.py` | Deterministic managed-patch archive used by the runtime-bundle builder |
| `sync_token_observer_archive.py` | Deterministic Token Observer archive used by the runtime-bundle builder |
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
- immutable runtime-bundle bucket, content-addressed key, optional object version,
  and SHA-256 emitted by `publish-runtime-artifacts.sh`;
- optional state-backup bucket/key;
- expected model identifier exposed by the authenticated subscription account.

The template contains no production default AMI, Secret ARN, API endpoint,
account ID, instance ID, or bucket.

## Validate

```sh
./deploy/minimal/validate-template.sh
```

Build and validate the runtime bundle without publishing it:

```sh
python3 ./deploy/minimal/build_runtime_bundle.py --check
```

Publish the immutable runtime bundle first:

```sh
AWS_REGION="$AWS_REGION" \
HERMES_RUNTIME_ARTIFACT_BUCKET="$ARTIFACT_BUCKET" \
./deploy/minimal/publish-runtime-artifacts.sh
```

Then publish and validate the CloudFormation template:

```sh
AWS_REGION="$AWS_REGION" \
HERMES_TEMPLATE_BUCKET="$ARTIFACT_BUCKET" \
./deploy/minimal/publish-template.sh
```

Both publish scripts upload to content-addressed keys. The instance verifies the
runtime bundle SHA-256 before safely extracting it into a digest-named release
directory. CloudFormation Metadata contains only the artifact identity and a
small loader; the complete runtime configuration and payloads are not embedded
in the template or User Data. Upload and deployment are operator-controlled
writes.

## Deployment sequence

1. Render and review `policies/deployer-policy.json.tmpl` outside the repository.
2. Validate templates and create an EBS snapshot/rollback point for updates.
3. Publish the runtime bundle, then publish the content-addressed template and
   create a Change Set with the emitted runtime-bundle parameters.
4. Reject unexpected EC2 replacement; apply `stack-policy.json` before a
   production update.
5. Execute the Change Set and confirm the physical instance/volume behavior.
6. Complete subscription OAuth manually as the owner; never inject OAuth files
   through CloudFormation or backups.
7. Run Gateway, Dashboard, Podman, egress, patch, observability, and optional
   credential-lease smoke and negative tests.
8. Replace temporary deployer access with the rendered operator policy.

Changing runtime behavior normally advances the bundle key/SHA without changing
User Data. A cached digest remains usable if S3 is temporarily unavailable;
rollback advances the stack back to a previously reviewed bundle identity.

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

## Telegram work feedback

The runtime sync enables Telegram processing reactions, grouped tool progress,
per-platform streaming, and one-minute long-running notifications. Temporary
progress bubbles are deleted after a successful final response and retained on
failure as diagnostic breadcrumbs.

Skill and Memory writes do not require Hermes' per-operation approval prompt.
This only changes local knowledge-write interaction; it does not broaden IAM,
Secret, network, container, external-send, or protected Git-ref boundaries.
