# Minimal Host Policy Templates

| Template | Use |
|---|---|
| `deployer-policy.json.tmpl` | Temporary reviewed CloudFormation, EC2, IAM, S3 template, snapshot, and SSM deployment access |
| `operator-policy.json.tmpl` | Long-lived access limited to one instance, Stack, and the operator's own SSM sessions |

Render to a temporary file outside Git. Required placeholders across the two
templates are:

`AWS_ACCOUNT_ID`, `AWS_REGION`, `ARTIFACT_BUCKET`, `TEMPLATE_PREFIX`,
`HERMES_STACK_NAME`, `HERMES_ROLE_PREFIX`, `HERMES_INSTANCE_ID`, and
`PROJECT_TAG`.

Review the rendered policy and target resources before applying it. Remove the
deployer policy after the change window. Never commit rendered policies.
