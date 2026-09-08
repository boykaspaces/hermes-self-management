# AWS Bootstrap Building Blocks

This directory contains optional, consumer-neutral resources for a first
Hermes deployment. None of these files knows an operator's account, Region,
resource IDs, endpoints, credentials, or private operations repository.

| Path | Purpose |
|---|---|
| `discover-environment.sh` | Read-only inventory of candidate VPCs, subnets, effective route-table evidence, and recent Canonical Ubuntu AMIs |
| `network-cloudformation.yaml` | Optional dedicated IPv4 VPC, Internet Gateway, route table, and public subnet |
| `artifacts-cloudformation.yaml` | Retained, encrypted, versioned, private S3 bucket for immutable templates and runtime bundles |
| `validate-template.sh` | Offline syntax and security-invariant checks for the bootstrap resources |

The discovery helper deliberately does not choose a VPC, subnet, or AMI. A
subnet's public-IP flag alone does not prove the intended egress path. Set both
`HERMES_VPC_ID` and `HERMES_SUBNET_ID` to display the subnet's explicit route
table and its VPC main route table before recording private deployment
parameters.

Use the optional network template only when an existing reviewed VPC/subnet is
not suitable. It creates no security-group ingress. The minimal host template
creates its own no-ingress security group and uses Systems Manager instead of
SSH.

The artifact bucket has no fixed name so separate AWS accounts can deploy the
same template without global S3-name collisions. It is retained if the
bootstrap Stack is deleted; remove retained objects and the bucket only through
an explicit operator recovery or teardown procedure.

See [`../QUICKSTART.md`](../QUICKSTART.md) for the complete clone-to-Change-Set
sequence.
