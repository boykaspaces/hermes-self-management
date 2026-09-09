# First AWS Deployment

This runbook takes a new operator from a fresh public clone through a reviewed
CloudFormation deployment, the first successful Hermes conversation, and a
post-restart conversation. It does not depend on a private repository owned by
this project's maintainer and it never asks for a Secret value in a
CloudFormation parameter.

If any success marker is missing, stop at that layer and use
[`minimal/FIRST_DEPLOYMENT_RECOVERY.md`](./minimal/FIRST_DEPLOYMENT_RECOVERY.md)
before retrying or deleting resources.

## 0. Check suitability and default capabilities

Review these boundaries before creating any AWS resources:

| Area | Supported first-deployment contract |
|---|---|
| Operator workstation | macOS or Linux with Bash. On Windows, use WSL2; this runbook does not provide native PowerShell commands. |
| EC2 host | A reviewed Ubuntu 24.04 LTS x86_64 AMI on `t3.small` or `t3.medium`. Other distributions, architectures, and instance families are not covered by the template contract. |
| Network | The selected subnet must provide outbound IPv4 access for first-boot package, GitHub, npm, container-image, OpenAI, and AWS service traffic. The host has no inbound security-group rules and is managed through SSM. |
| Model access | `openai-codex` using owner-completed ChatGPT subscription OAuth. The configured model must be offered to that account. API-key and Bedrock fallback are removed rather than used automatically. |
| Dashboard | Enabled on instance loopback only and opened through SSM port forwarding; it is not public. |
| Telegram | Disabled in the example Runtime Profile. Enabling it requires a retained Secret and an intentional profile change. |
| Browser automation | Disabled (`browser.backend=off`) in the managed runtime configuration. |
| Agent Terminal | Rootless Podman is available, but container networking is disabled by default. The Agent therefore cannot clone a remote repository or install packages from the network in Terminal. |
| Git coding and Personal Tools | Disabled by default. Enabling restricted Git coding requires the separately deployed Personal Tools credential lease, explicit CloudFormation parameters, and a reviewed proxy allowlist. |

The EC2 bootstrap itself uses the host's outbound path to install its declared
software. Ad hoc package installation on the host is not a replacement for a
reviewed template or runtime-bundle change and is outside this reproducible
deployment contract. See
[`minimal/MODEL_PROVIDER_STRATEGY.md`](./minimal/MODEL_PROVIDER_STRATEGY.md)
for the model and no-fallback boundary.

## 1. Prerequisites and private workspace

Install the repository-supported local tool baseline:

| Tool | Required baseline |
|---|---|
| Bash | 3.2 or newer |
| AWS CLI | v2 |
| AWS Session Manager plugin | Installed and able to report its version; required by both SSM shell and Dashboard port-forward commands |
| `jq` | 1.6 or newer |
| Python | 3.9 or newer |
| Ruby | 2.6 or newer, with standard YAML and JSON libraries |
| Git | 2.20 or newer |
| `ripgrep` | 12 or newer |
| `shasum` | Installed and able to report its version |

Install AWS CLI v2 from the
[official AWS instructions](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
and use the current vendor release of the
[AWS Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html).
Clone the public component directly; no private operations repository is
required or fetched:

```sh
git clone https://github.com/boykaspaces/hermes-self-management.git
cd hermes-self-management
```

Authenticate the AWS CLI to the intended account and choose one Region
explicitly:

```sh
export AWS_REGION=us-west-2
AWS_REGION="$AWS_REGION" ./deploy/preflight.sh --aws
aws sts get-caller-identity
```

`preflight.sh` is versioned with this repository. It prints every detected tool
version and finishes with `preflight-ok version=1`. With `--aws`, it additionally
performs only the read-only `sts:GetCallerIdentity` check; it does not create or
change AWS resources. Stop before deployment if it reports any
`preflight-error`.

Use separate reviewed identities for distinct deployment phases:

| Phase | Required identity boundary |
|---|---|
| Account discovery and optional bootstrap | An account-bootstrap identity allowed to read VPC, subnet, route-table, and AMI metadata and, when needed, create the dedicated network and artifact-bucket Stacks. The minimal-host deployer policy does not create these prerequisites. |
| Optional retained Secret container | The separate deployer policy under `deploy/hermes-runtime-secrets/policies/`; populate its value with a credential operator, not the deployer. |
| Profile and artifact publication plus host Stack | The temporary rendered `deploy/minimal/policies/deployer-policy.json.tmpl`, after the artifact bucket and exact Runtime Profile name are known. |
| Ongoing host access | The rendered minimal-host operator policy after removing temporary deployer access. |

The temporary minimal-host policy requires separate template and runtime-bundle
prefixes plus the exact Runtime Profile parameter name. Follow its
[`policies/README.md`](./minimal/policies/README.md) rendering contract. Do not
use an administrator identity as evidence that the restricted deployment path
works.

Create a private operator directory outside this clone. It may be a private
repository, an encrypted local directory, or another controlled system:

```sh
mkdir -p ../my-hermes-ops
chmod 700 ../my-hermes-ops
```

Store non-secret parameter files, selected resource IDs, artifact versions,
checksums, Change Set reviews, and rollback evidence there. Never commit
credentials, OAuth files, Telegram tokens, or Secret values.

## 2. Discover or create network resources

List the current account and Region without selecting anything:

```sh
AWS_REGION="$AWS_REGION" ./deploy/bootstrap/discover-environment.sh
```

To narrow the subnet list after reviewing a VPC:

```sh
AWS_REGION="$AWS_REGION" \
HERMES_VPC_ID=vpc-REPLACE_WITH_REVIEWED_ID \
./deploy/bootstrap/discover-environment.sh
```

After choosing a candidate subnet, display the explicit subnet association and
the VPC main route table used when no explicit association exists:

```sh
AWS_REGION="$AWS_REGION" \
HERMES_VPC_ID=vpc-REPLACE_WITH_REVIEWED_ID \
HERMES_SUBNET_ID=subnet-REPLACE_WITH_REVIEWED_ID \
./deploy/bootstrap/discover-environment.sh
```

Inspect the selected subnet's effective route table and record the VPC,
subnet, Availability Zone, route target, and reviewed AMI in the private
workspace. Do not infer Internet access only from `MapPublicIpOnLaunch`.

If no existing network is suitable, deploy the optional dedicated network:

```sh
aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name my-hermes-network \
  --template-file deploy/bootstrap/network-cloudformation.yaml

aws cloudformation describe-stacks \
  --region "$AWS_REGION" \
  --stack-name my-hermes-network \
  --query 'Stacks[0].Outputs'
```

Review CIDRs before deployment. The bootstrap network provides direct IPv4
Internet egress and creates no ingress rules; a private-subnet/NAT or
VPC-endpoint design is an operator-owned alternative.

## 3. Create a private artifact bucket

Deploy the consumer-neutral bucket template and capture its output:

```sh
aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name my-hermes-artifacts \
  --template-file deploy/bootstrap/artifacts-cloudformation.yaml

export ARTIFACT_BUCKET="$(aws cloudformation describe-stacks \
  --region "$AWS_REGION" \
  --stack-name my-hermes-artifacts \
  --query 'Stacks[0].Outputs[?OutputKey==`ArtifactBucketName`].OutputValue' \
  --output text)"
```

The bucket is encrypted, versioned, blocks public access, denies non-TLS
requests, and is retained when its bootstrap Stack is deleted.

## 4. Prepare and publish the consumer profile

Copy the neutral example outside the public clone:

```sh
cp deploy/minimal/runtime-profile.example.json \
  ../my-hermes-ops/runtime-profile.json
chmod 600 ../my-hermes-ops/runtime-profile.json
```

Edit only non-secret behavior such as model selection, Telegram desired state,
Terminal resources, browser timeouts, approval preferences, and proxy hosts.
The validator rejects credential-shaped fields and limits the profile to the
SSM Standard parameter size.

Publish and byte-verify it:

```sh
export HERMES_RUNTIME_PROFILE_PARAMETER=/my-hermes/runtime/profile

AWS_REGION="$AWS_REGION" \
HERMES_RUNTIME_PROFILE_FILE=../my-hermes-ops/runtime-profile.json \
HERMES_RUNTIME_PROFILE_PARAMETER="$HERMES_RUNTIME_PROFILE_PARAMETER" \
./deploy/minimal/publish-runtime-profile.sh
```

The profile is an SSM `String`, not a Secret. Do not put tokens, passwords,
private keys, or OAuth material in it. Keep the exported parameter name for the
private CloudFormation parameter file below; the publisher also prints it as
`RuntimeProfileParameterName` for deployment evidence.

## 5. Create optional retained runtime credentials

For Telegram, deploy the retained empty Secret container and capture its ARN:

```sh
aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name my-hermes-runtime-secrets \
  --template-file deploy/hermes-runtime-secrets/cloudformation.yaml \
  --parameter-overrides \
    ProjectTag=my-hermes-agent \
    TelegramRuntimeSecretName=my-hermes-agent/telegram

aws cloudformation describe-stacks \
  --region "$AWS_REGION" \
  --stack-name my-hermes-runtime-secrets \
  --query 'Stacks[0].Outputs[?OutputKey==`TelegramRuntimeSecretArn`].OutputValue' \
  --output text
```

Populate its JSON value through a narrow credential-operator identity or the
AWS Console; do not place the value on a command line or in CloudFormation.
Only the resulting ARN is passed to the host Stack. Skip this entire step when
Telegram is disabled in the Runtime Profile.

Personal Tools is optional. An operator who only wants the base Hermes Agent
leaves `mcp.personal_tools_url` empty and `GitCodingEnabled=false`. To enable
those capabilities, deploy
[Hermes Personal Tools](https://github.com/boykaspaces/hermes-personal-tools).
Its Stack outputs provide the MCP URL, client-token Secret ARN, and optional
credential-lease API ID. Keep those account-bound outputs in the private
workspace.

## 6. Build and publish immutable artifacts

Run all offline validation first:

```sh
./scripts/validate.sh
```

Publish the deterministic runtime bundle:

```sh
AWS_REGION="$AWS_REGION" \
HERMES_RUNTIME_ARTIFACT_BUCKET="$ARTIFACT_BUCKET" \
./deploy/minimal/publish-runtime-artifacts.sh
```

Record every emitted Bucket, Key, Object Version, and SHA-256. Then publish the
content-addressed host template:

```sh
AWS_REGION="$AWS_REGION" \
  HERMES_TEMPLATE_BUCKET="$ARTIFACT_BUCKET" \
  ./deploy/minimal/publish-template.sh
```

The final line is the immutable template URL. Copy it into the private
operator workspace, then export it explicitly as `HERMES_TEMPLATE_URL`; do not
capture the whole command output because it also contains validation results.

Both operations write to the operator's own private bucket. The host verifies
the runtime-bundle digest before extraction.

## 7. Prepare private parameters and create a Change Set

Create the private parameter file outside this clone. The `jq` step writes the
same Runtime Profile parameter name used by the publisher instead of relying on
a second concrete example path. Replace every remaining placeholder with a
reviewed value or another publisher output:

```sh
jq --arg name "$HERMES_RUNTIME_PROFILE_PARAMETER" \
  'map(if .ParameterKey == "RuntimeProfileParameterName" then .ParameterValue = $name else . end)' \
  deploy/minimal/parameters.example.json \
  > ../my-hermes-ops/hermes-parameters.json
chmod 600 ../my-hermes-ops/hermes-parameters.json
```

The example deliberately carries the reviewed Hermes commit together with its
installer, `uv.lock`, and `package-lock.json` SHA-256 values, plus an exact
Agent Browser version and digest-pinned coding image. Treat them as one
installation identity. If the Hermes commit changes, recalculate all three
source hashes from that commit and repeat the upgrade review; never retain an
old hash merely to make validation pass.

Add optional `TelegramRuntimeSecretArn`,
`PersonalToolsClientTokenSecretArn`, or credential-agent parameters only when
those capabilities are intentionally enabled. Do not add Secret values.

Create, but do not execute, the initial Change Set:

```sh
export HERMES_STACK_NAME=my-hermes

AWS_REGION="$AWS_REGION" \
HERMES_STACK_NAME="$HERMES_STACK_NAME" \
HERMES_TEMPLATE_URL="$HERMES_TEMPLATE_URL" \
HERMES_PARAMETER_FILE=../my-hermes-ops/hermes-parameters.json \
HERMES_CHANGE_SET_NAME=initial-reviewed-deployment \
./deploy/minimal/create-change-set.sh
```

The helper rejects parameter files inside the public clone and rejects example
placeholders. It never calls `execute-change-set`. For a genuinely new Stack,
stop unless it prints this operation contract:

```text
StackStatusBefore=DOES_NOT_EXIST
ChangeSetType=CREATE
FailureResourcesPreserved=on-stack-failure-do-nothing
Waiter=stack-create-complete
```

Failure preservation keeps useful events and resources available for
diagnosis, but those resources can incur charges. If the helper reports a
failed existing Stack or refuses its status, follow the recovery runbook
instead of executing it as a new deployment.

## 8. Review and execute the Change Set

Wait for the Change Set to finish preparing, then inspect every resource and
replacement decision:

```sh
aws cloudformation describe-change-set \
  --region "$AWS_REGION" \
  --change-set-name CHANGE_SET_ID_FROM_THE_HELPER
```

Confirm the EC2 security group has no inbound rule, the selected subnet and
AMI are expected, IAM and Secret access are narrowly scoped, artifact
identities are immutable, the installer/lock/browser/image values match the
reviewed installation identity, and no unknown replacement is present. Execute
only after that human review.

Export the exact Change Set ID printed by the helper, execute it, and wait for
the first-boot resource signal:

```sh
export HERMES_CHANGE_SET_ID=REPLACE_WITH_REVIEWED_CHANGE_SET_ID

aws cloudformation execute-change-set \
  --region "$AWS_REGION" \
  --change-set-name "$HERMES_CHANGE_SET_ID"

aws cloudformation wait stack-create-complete \
  --region "$AWS_REGION" \
  --stack-name "$HERMES_STACK_NAME"
```

Do not rerun section 7 if the waiter exits nonzero. Preserve the command
output, inspect the Stack status, and follow
[`FIRST_DEPLOYMENT_RECOVERY.md`](./minimal/FIRST_DEPLOYMENT_RECOVERY.md). It
provides the separate `UPDATE` Change Set and `stack-update-complete` waiter
needed for a preserved failed creation. On success, confirm the exact Stack
status and capture the instance ID:

```sh
aws cloudformation describe-stacks \
  --region "$AWS_REGION" \
  --stack-name "$HERMES_STACK_NAME" \
  --query 'Stacks[0].StackStatus' \
  --output text

export HERMES_INSTANCE_ID="$(aws cloudformation describe-stacks \
  --region "$AWS_REGION" \
  --stack-name "$HERMES_STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`InstanceId`].OutputValue' \
  --output text)"

aws ssm get-connection-status \
  --region "$AWS_REGION" \
  --target "$HERMES_INSTANCE_ID" \
  --query Status \
  --output text
```

Success means the Stack reports `CREATE_COMPLETE` for the initial operation or
`UPDATE_COMPLETE` after a documented recovery, the instance ID is nonempty,
and SSM reports `connected`.

## 9. Open an SSM shell and complete owner OAuth

Open the shell using the Stack's `ConnectCommand` Output or run:

```sh
aws ssm start-session \
  --region "$AWS_REGION" \
  --target "$HERMES_INSTANCE_ID"
```

Inside the SSM shell, check both services, authenticate as the Hermes owner,
and inspect the resulting credential status and model catalogue:

```sh
HERMES_UID="$(id -u hermes)"
sudo -u hermes -H env \
  XDG_RUNTIME_DIR="/run/user/$HERMES_UID" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$HERMES_UID/bus" \
  systemctl --user is-active hermes-gateway.service
sudo systemctl is-active hermes-dashboard.service
curl --fail --silent http://127.0.0.1:9119/api/health >/dev/null \
  && echo dashboard-health-ok

sudo -iu hermes bash -lc \
  'PATH="$HOME/.local/bin:$PATH" hermes auth add openai-codex'
sudo -iu hermes bash -lc \
  'PATH="$HOME/.local/bin:$PATH" hermes auth status openai-codex'
sudo -iu hermes bash -lc \
  'PATH="$HOME/.local/bin:$PATH" hermes model'

HERMES_UID="$(id -u hermes)"
sudo -u hermes -H env \
  XDG_RUNTIME_DIR="/run/user/$HERMES_UID" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$HERMES_UID/bus" \
  systemctl --user restart hermes-gateway.service
sudo -u hermes -H env \
  XDG_RUNTIME_DIR="/run/user/$HERMES_UID" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$HERMES_UID/bus" \
  systemctl --user is-active hermes-gateway.service
```

Follow the displayed device-code URL as the ChatGPT subscription owner. Never
paste the device code or `auth.json` into logs, tickets, or source. Success
means both services are active, `openai-codex` has a usable OAuth credential,
the Runtime Profile's `model.default` is offered to this account, and the final
command prints `active` after Gateway reloads the credential and reapplies the
Runtime Profile. The
official OpenAI authentication model distinguishes ChatGPT subscription login
from usage-billed API-key login; this deployment intentionally uses the former.
See [official OpenAI authentication guidance](https://learn.chatgpt.com/docs/auth)
for the device-code flow and credential boundary.

`hermes model` is interactive and may write the local config. The Runtime
Profile remains authoritative and is reapplied before Gateway starts. If the
configured model is unavailable, stop here, update and republish the private
Runtime Profile with an offered model, reconnect through SSM, and apply it with:

```sh
HERMES_UID="$(id -u hermes)"
sudo -u hermes -H env \
  XDG_RUNTIME_DIR="/run/user/$HERMES_UID" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$HERMES_UID/bus" \
  systemctl --user restart hermes-gateway.service
sudo -u hermes -H env \
  XDG_RUNTIME_DIR="/run/user/$HERMES_UID" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$HERMES_UID/bus" \
  systemctl --user is-active hermes-gateway.service
```

Confirm the final command prints `active` before continuing; do not add a paid
fallback. Follow
[`MODEL_PROVIDER_STRATEGY.md`](./minimal/MODEL_PROVIDER_STRATEGY.md) for the
complete OAuth, model-selection, no-fallback, and restart contract. Exit the
SSM shell after these checks.

## 10. Forward and open the localhost-only Dashboard

Using an identity with the rendered operator-policy permissions, run the
Stack's `DashboardPortForwardCommand` Output or the equivalent command below in
a local terminal. Keep it running:

```sh
aws ssm start-session \
  --region "$AWS_REGION" \
  --target "$HERMES_INSTANCE_ID" \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["9119"],"localPortNumber":["9119"]}'
```

Open <http://127.0.0.1:9119>, select the **Chat** page, start a new chat, and
send:

```text
Reply with exactly HERMES_FIRST_CONVERSATION_OK and do not call tools.
```

Success means the reply completes, contains `HERMES_FIRST_CONVERSATION_OK`, and
the session appears in the Dashboard's Sessions page with the expected model.
The Dashboard remains bound to instance loopback; do not add an inbound
security-group rule or bind it to a public interface.

## 11. Prove restart persistence with a second conversation

Stop the port-forwarding session with `Ctrl-C`, then perform a deterministic
instance stop/start cycle and wait for EC2 and SSM to recover:

```sh
aws ec2 stop-instances \
  --region "$AWS_REGION" \
  --instance-ids "$HERMES_INSTANCE_ID"
aws ec2 wait instance-stopped \
  --region "$AWS_REGION" \
  --instance-ids "$HERMES_INSTANCE_ID"

aws ec2 start-instances \
  --region "$AWS_REGION" \
  --instance-ids "$HERMES_INSTANCE_ID"
aws ec2 wait instance-status-ok \
  --region "$AWS_REGION" \
  --instance-ids "$HERMES_INSTANCE_ID"

for attempt in $(seq 1 60); do
  HERMES_SSM_STATUS="$(aws ssm get-connection-status \
    --region "$AWS_REGION" \
    --target "$HERMES_INSTANCE_ID" \
    --query Status \
    --output text 2>/dev/null || true)"
  [ "$HERMES_SSM_STATUS" = connected ] && break
  sleep 5
done
test "$HERMES_SSM_STATUS" = connected
```

Open an SSM shell again and repeat the two `systemctl is-active` commands, the
Dashboard `/api/health` request, and `hermes auth status openai-codex` from
section 9. Each service must report `active`, the health request must print
`dashboard-health-ok`, and the OAuth status must remain usable.

Start the Dashboard port-forward command again, reopen
<http://127.0.0.1:9119>, create a new chat, and send:

```text
Reply with exactly HERMES_RESTART_CONVERSATION_OK and do not call tools.
```

Success means the second reply completes with
`HERMES_RESTART_CONVERSATION_OK`, the expected model is still selected, and the
first session remains visible. This proves the services, Runtime Profile, OAuth
cache, and session state survive a host restart at the functional level.

## 12. Record acceptance

Run the Gateway, Dashboard, Telegram, Runtime Profile, Secret, Podman, egress,
patch, and observability checks in [`minimal/README.md`](./minimal/README.md).
From an SSM shell, review the non-secret files under
`/home/hermes/.hermes/install-manifest/` and record them with the actual Stack
IDs, parameters, outputs, artifact versions, two conversation markers, restart
acceptance, and rollback targets only in the operator's private system. Do not
record OAuth material or session content.
