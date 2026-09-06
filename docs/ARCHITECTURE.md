# Architecture

```text
operator -> CloudFormation / SSM
                 |
                 v
      EC2 host (no inbound rules)
        ├─ Hermes Gateway + Dashboard (systemd)
        ├─ host-owned OAuth and runtime Secret sync
        ├─ Rootless Podman Terminal containers
        ├─ optional egress proxy + credential provisioner
        └─ Token Observer + loopback-only viewer

private ops -> immutable parameters and release pins
      ├─ hermes-self-management
      ├─ hermes-personal-tools
      └─ hermes-context-kit
```

The public runtime repository never depends on private ops. Private ops
consumes reviewed public releases and records the deployed commit, object
version, checksum, Stack, parameter set, and rollback target.

The deployment uses whole-host controls for IAM, Secrets, systemd, storage, and
networking while limiting agent command execution to Rootless Podman. It does
not claim that the entire Hermes process runs inside a container.
