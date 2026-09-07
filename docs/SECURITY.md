# Security Model

## Host and access

- No public inbound port is required; operator access uses AWS Systems Manager.
- Hermes runs as a non-root user. The Terminal backend uses Rootless Podman.
- The coding container receives neither the instance role nor a Podman/Docker
  socket.
- Persistent workspace mounts and credential lease mounts are explicit and
  narrowly scoped.

## Network

- The host needs controlled outbound access for AWS management, installation,
  providers, and updates.
- Coding-container egress is separately catalogued and routed through the
  configured proxy when Git coding is enabled.
- Subscription OAuth does not require a dummy model Provider API Key: the
  managed allowlist-only setup writes no provider secret mappings and admits
  only the explicit coding-host catalogue.
- Private, loopback, link-local, cloud metadata, and uncatalogued public
  targets are denied on the configured explicit-proxy path.
- This component does not transparently force every socket through the proxy.
  Code that deliberately clears proxy and CA variables can still use the
  ordinary container network; require network-layer enforcement for a threat
  model that includes hostile sandbox processes.
- Adding a domain or disabling isolation is an operator-reviewed security
  change, not agent self-maintenance.

## Credentials

- OAuth files remain host-owned, mode `0600`, and outside templates/backups.
- Runtime and provider Secrets are populated out of band.
- Coding uses short-lived leases from Hermes Personal Tools; the container can
  technically read its lease, so expiry, fixed repository scope, protected
  refs, no IAM, and restricted egress are required compensating controls.

## Agent self-maintenance

Hermes may maintain low-risk project state and approved user-layer settings.
Operator/managed scope must lock access control, secret redaction, minimum
approval posture, container backend, filesystem roots, network boundaries,
metadata denial, and privileged host capabilities.

The repository contains mechanisms and defaults, not a substitute for the
operator's threat model or cloud-account review.
