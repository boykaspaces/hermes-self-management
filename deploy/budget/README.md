# Budget and Model-Cutoff Stack

The template creates an account-wide notification budget and a model-cost
budget whose 100 percent action attaches an explicit Bedrock inference deny
policy to one existing Hermes instance role.

Required inputs are the notification email and exact Hermes role name. Limits,
budget names, project tag, and resource prefix are parameters. The account-wide
budget alerts only; it does not attempt to disable unrelated AWS services.

```sh
./deploy/budget/validate-template.sh
```

Deploy only after the target Hermes role exists. Render the policy templates
from `policies/` outside Git, review their account/Region/budget/role targets,
and keep deployer access temporary. Record notifications, action state, and
cutoff recovery privately.
