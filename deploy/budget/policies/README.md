# Budget Policy Templates

| Template | Use |
|---|---|
| `deployer-policy.json.tmpl` | Temporary Stack, Budget action, IAM role/policy, and target-role access |
| `readonly-policy.json.tmpl` | Long-lived visibility into the exact Stack, budgets, action history, and target role |

Substitute `AWS_ACCOUNT_ID`, `BUDGET_REGION`, `BUDGET_STACK_NAME`,
`MODEL_BUDGET_NAME`, `ACCOUNT_BUDGET_NAME`, and `HERMES_ROLE_NAME` in a
temporary rendered file. Validate with `jq`, review, apply, and never commit the
rendered production policy.
