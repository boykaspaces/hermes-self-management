# Runtime Secret Policy Templates

| Template | Use |
|---|---|
| `deployer-policy.json.tmpl` | Temporary creation/update of the one Stack and Secret container |
| `credential-operator-policy.json.tmpl` | Narrow out-of-band Secret value update without Secret readback |

Substitute `AWS_ACCOUNT_ID`, `AWS_REGION`, `RUNTIME_SECRET_STACK_NAME`, and
`TELEGRAM_SECRET_NAME` in a temporary file. Validate and review the rendered
resources before application. Never commit the rendered policy or Secret value.
