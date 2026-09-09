# Minimal Host Policy Templates

| Template | Use |
|---|---|
| `deployer-policy.json.tmpl` | Temporary reviewed minimal-host deployment access after bootstrap resources exist; includes discovery, one Runtime Profile, two artifact prefixes, the host Stack, IAM, EC2, snapshots, SSM sessions, and read-only instance console output for failed first-boot diagnosis |
| `operator-policy.json.tmpl` | Long-lived access limited to one instance, Stack, and the operator's own SSM sessions |

Render to a temporary file outside Git. Required placeholders across the two
templates are:

`AWS_ACCOUNT_ID`, `AWS_REGION`, `ARTIFACT_BUCKET`, `TEMPLATE_PREFIX`,
`RUNTIME_ARTIFACT_PREFIX`, `RUNTIME_PROFILE_PARAMETER_NAME`,
`HERMES_STACK_NAME`, `HERMES_ROLE_PREFIX`, `HERMES_INSTANCE_ID`, and
`PROJECT_TAG`. `RUNTIME_PROFILE_PARAMETER_NAME` must retain its leading slash;
the policy template appends it to the SSM `parameter` ARN prefix.

The repository publishers currently require these two distinct S3 prefixes:

| Placeholder | Current publisher value |
|---|---|
| `TEMPLATE_PREFIX` | `hermes-self-management/cloudformation` |
| `RUNTIME_ARTIFACT_PREFIX` | `hermes-self-management/runtime` |

Render `RUNTIME_PROFILE_PARAMETER_NAME` from the same
`HERMES_RUNTIME_PROFILE_PARAMETER` value used by
`publish-runtime-profile.sh`. The policy grants only `GetParameter` and
`PutParameter` on that exact parameter; deletion remains a separate teardown
decision.

This policy does not create the optional bootstrap VPC, subnet, route table,
Internet Gateway, or artifact bucket. Create those prerequisites with a
separately reviewed account-bootstrap identity, then render this policy with
the resulting bucket and selected resource names. The optional retained Secret
container has its own deployer policy under
[`../../hermes-runtime-secrets/policies/`](../../hermes-runtime-secrets/policies/).

Review the rendered policy and target resources before applying it. Remove the
deployer policy after the change window. Never commit rendered policies.
`ec2:GetConsoleOutput` is the only recovery-specific EC2 read and is needed
when the SSM agent never becomes reachable; it does not grant serial-console,
shell, ingress, reboot, or instance-mutation access.
