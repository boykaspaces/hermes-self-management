# First-Deployment Recovery

Use this runbook when the initial CloudFormation waiter fails, SSM never
connects, Runtime Profile application fails, OAuth cannot complete, or the
Dashboard cannot be reached. Diagnose one layer at a time and retry only after
the listed gate passes.

The initial Change Set helper uses CloudFormation's **preserve successfully
provisioned resources** behavior (`OnStackFailure=DO_NOTHING`). This normally
leaves a failed first deployment in `CREATE_FAILED` so its events, instance,
console output, and—when available—SSM logs remain inspectable. Preserved
resources can continue to incur charges. See the
[AWS failure-options contract](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stack-failure-options.html).

## Safety boundaries

- Keep the temporary deployer policy until recovery is complete. It permits
  Stack events and read-only EC2 console output; it does not add SSH, ingress,
  or serial-console access.
- Never paste OAuth device codes, `auth.json`, Secret values, session content,
  or unreviewed logs into source, tickets, or chat. Store evidence only in the
  private operator workspace created by Quickstart.
- Do not manually rerun `/var/lib/cloud/instance/scripts/part-001` or use
  `cloud-init clean`. First-boot User Data is not a supported idempotent repair
  command.
- Do not delete or roll back a Stack until its events and any recoverable host
  state have been reviewed. `rollback-stack` can delete a failed initial Stack
  because it has no previous stable state.
- Do not open port 22, add security-group ingress, bind the Dashboard publicly,
  or add a paid model fallback to make a diagnostic pass.

## 1. Capture the failure before changing anything

From the public clone, restore the same account, Region, Stack name, private
parameter file, and immutable template URL used for the failed attempt:

```sh
export AWS_REGION=us-west-2
export HERMES_STACK_NAME=my-hermes
export HERMES_PARAMETER_FILE=../my-hermes-ops/hermes-parameters.json
export HERMES_TEMPLATE_URL=REPLACE_WITH_REVIEWED_IMMUTABLE_TEMPLATE_URL
export HERMES_RECOVERY_DIR=../my-hermes-ops/first-deployment-recovery

mkdir -p "$HERMES_RECOVERY_DIR"
chmod 700 "$HERMES_RECOVERY_DIR"

aws cloudformation describe-stacks \
  --region "$AWS_REGION" \
  --stack-name "$HERMES_STACK_NAME" \
  > "$HERMES_RECOVERY_DIR/stack.json"

aws cloudformation describe-stack-events \
  --region "$AWS_REGION" \
  --stack-name "$HERMES_STACK_NAME" \
  > "$HERMES_RECOVERY_DIR/stack-events.json"

aws cloudformation describe-stack-resources \
  --region "$AWS_REGION" \
  --stack-name "$HERMES_STACK_NAME" \
  > "$HERMES_RECOVERY_DIR/stack-resources.json"
```

Display the current status and the newest failure events:

```sh
aws cloudformation describe-stacks \
  --region "$AWS_REGION" \
  --stack-name "$HERMES_STACK_NAME" \
  --query 'Stacks[0].[StackStatus,StackStatusReason]' \
  --output table

aws cloudformation describe-stack-events \
  --region "$AWS_REGION" \
  --stack-name "$HERMES_STACK_NAME" \
  --query 'StackEvents[?contains(ResourceStatus, `FAILED`)].[Timestamp,LogicalResourceId,ResourceStatus,ResourceStatusReason]' \
  --output table
```

If `HermesInstance` exists, capture its physical ID even when Stack Outputs
were never produced:

```sh
export HERMES_INSTANCE_ID="$(aws cloudformation describe-stack-resource \
  --region "$AWS_REGION" \
  --stack-name "$HERMES_STACK_NAME" \
  --logical-resource-id HermesInstance \
  --query 'StackResourceDetail.PhysicalResourceId' \
  --output text)"
test -n "$HERMES_INSTANCE_ID"
test "$HERMES_INSTANCE_ID" != None
```

Use the status, not the previous command or elapsed time, to choose the next
operation:

| Stack status | Required action |
|---|---|
| Stack does not exist | Correct the inputs, choose a new Change Set name, and run the helper. It prepares `CREATE` with failure preservation. |
| `REVIEW_IN_PROGRESS` | An initial Change Set has not been executed. Review that Change Set or explicitly delete the stale Change Set. Do not create another one until the review Stack disappears. |
| Any `*_IN_PROGRESS` | Wait and inspect events. Do not submit a competing operation. |
| `CREATE_FAILED` or `UPDATE_FAILED` | Evidence is preserved. Diagnose the symptom below; after its retry gate passes, run the helper to prepare a recovery `UPDATE`. |
| `ROLLBACK_COMPLETE` | The failed attempt already rolled back and cannot be updated. Capture evidence, assess data loss, delete the Stack explicitly, wait for deletion, then prepare a new `CREATE`. |
| `UPDATE_ROLLBACK_FAILED` | Fix the rollback cause and use `continue-update-rollback`; do not use the first-deployment helper until the Stack reaches a stable status. |
| `ROLLBACK_FAILED` or `DELETE_FAILED` | Inspect failed resource events and resolve that resource first. Do not force-delete or skip resources without a separate review. |
| `CREATE_COMPLETE`, `UPDATE_COMPLETE`, or `UPDATE_ROLLBACK_COMPLETE` | The Stack is stable. Do not use this first-deployment helper for a normal update; continue with the symptom-specific service checks or the upgrade runbook. |

For `REVIEW_IN_PROGRESS`, list the existing Change Sets and delete only the
explicitly reviewed stale one:

```sh
aws cloudformation list-change-sets \
  --region "$AWS_REGION" \
  --stack-name "$HERMES_STACK_NAME"
aws cloudformation delete-change-set \
  --region "$AWS_REGION" \
  --change-set-name REPLACE_WITH_STALE_CHANGE_SET_ID
```

For `UPDATE_ROLLBACK_FAILED`, first correct the resource named by the failure
event, then resume the rollback without skipping resources:

```sh
aws cloudformation continue-update-rollback \
  --region "$AWS_REGION" \
  --stack-name "$HERMES_STACK_NAME"
aws cloudformation wait stack-update-rollback-complete \
  --region "$AWS_REGION" \
  --stack-name "$HERMES_STACK_NAME"
```

## 2. Stack or first-boot failure

An event such as `Received FAILURE signal` for `HermesInstance` means User Data
failed before `/home/hermes/.bootstrap-complete` was written. If SSM connects,
open a shell and inspect:

```sh
cloud-init status --long
sudo test -f /home/hermes/.bootstrap-complete \
  && echo bootstrap-complete \
  || echo bootstrap-incomplete
sudo journalctl -u cloud-final.service -b --no-pager -n 300
sudo tail -n 300 /var/log/cloud-init-output.log
```

`/var/log/cloud-init.log` contains cloud-init orchestration details;
`/var/log/cloud-init-output.log` and the `cloud-final.service` journal contain
the rendered script's command output. Keep copies private and redact them
before sharing. Common failures here include package/network access, an
installer or lock checksum mismatch, S3 artifact access, Runtime Profile
access or validation, patch application, browser/image downloads, and service
health checks.

If SSM does not connect, continue with section 3. The restricted deployer can
still save the latest instance console output:

```sh
aws ec2 get-console-output \
  --region "$AWS_REGION" \
  --instance-id "$HERMES_INSTANCE_ID" \
  --latest \
  --query Output \
  --output text \
  > "$HERMES_RECOVERY_DIR/ec2-console-output.txt"
chmod 600 "$HERMES_RECOVERY_DIR/ec2-console-output.txt"
```

Retry gate: the failing dependency or permission is identified and corrected;
the parameter file and immutable artifacts still match the reviewed inputs;
and no unknown host state must be preserved manually. If source, template, or
runtime-bundle content changes, validate and publish a new immutable artifact
before retrying.

## 3. SSM does not connect

From the operator workstation, check the instance, both EC2 status checks, the
attached instance profile, and SSM registration:

```sh
aws ec2 describe-instances \
  --region "$AWS_REGION" \
  --instance-ids "$HERMES_INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].{State:State.Name,Subnet:SubnetId,PublicIp:PublicIpAddress,Profile:IamInstanceProfile.Arn}' \
  --output table

aws ec2 describe-instance-status \
  --region "$AWS_REGION" \
  --instance-ids "$HERMES_INSTANCE_ID" \
  --include-all-instances \
  --query 'InstanceStatuses[0].{State:InstanceState.Name,System:SystemStatus.Status,Instance:InstanceStatus.Status}' \
  --output table

aws ssm describe-instance-information \
  --region "$AWS_REGION" \
  --filters "Key=InstanceIds,Values=$HERMES_INSTANCE_ID" \
  --query 'InstanceInformationList[0].{Ping:PingStatus,Agent:AgentVersion,Platform:PlatformName}' \
  --output table

aws ssm get-connection-status \
  --region "$AWS_REGION" \
  --target "$HERMES_INSTANCE_ID"
```

Also capture EC2 console output as shown in section 2. Confirm that the
reviewed subnet provides the intended outbound IPv4 path and DNS, the instance
has the Stack-created IAM profile, and HTTPS traffic can reach the Region's
SSM services. Do not infer outbound connectivity solely from the subnet's
public-IP setting.

If SSM connects later, inspect both possible Ubuntu agent units before
continuing:

```sh
sudo systemctl status amazon-ssm-agent.service --no-pager \
  || sudo systemctl status snap.amazon-ssm-agent.amazon-ssm-agent.service --no-pager
sudo journalctl -u amazon-ssm-agent.service -b --no-pager -n 200 \
  || sudo journalctl -u snap.amazon-ssm-agent.amazon-ssm-agent.service -b --no-pager -n 200
```

Retry gate: EC2 reports both status checks `ok`, the expected instance profile
is attached, and `get-connection-status` reports `connected`. SSM connectivity
does not by itself complete the Stack; return to section 2 if bootstrap is
incomplete.

## 4. Runtime Profile cannot be read or applied

Verify the exact parameter name exported during Quickstart and retrieve its
metadata without printing its value:

```sh
test -n "$HERMES_RUNTIME_PROFILE_PARAMETER"
aws ssm get-parameter \
  --region "$AWS_REGION" \
  --name "$HERMES_RUNTIME_PROFILE_PARAMETER" \
  --query 'Parameter.{Name:Name,Type:Type,Version:Version,Modified:LastModifiedDate}' \
  --output table
```

Save and validate the current non-secret value inside the private recovery
directory:

```sh
aws ssm get-parameter \
  --region "$AWS_REGION" \
  --name "$HERMES_RUNTIME_PROFILE_PARAMETER" \
  --output json \
  | jq -erj '.Parameter.Value' \
  > "$HERMES_RECOVERY_DIR/runtime-profile.json"
chmod 600 "$HERMES_RECOVERY_DIR/runtime-profile.json"
python3 deploy/minimal/validate_runtime_profile.py \
  "$HERMES_RECOVERY_DIR/runtime-profile.json"
```

Confirm the Stack parameter, instance-role policy, and published parameter all
name the same path. On a connected host, inspect the cached copy and rerun the
versioned loader only after the parameter and IAM access are fixed:

```sh
sudo -u hermes -H test -s /home/hermes/.hermes/runtime/profile/current.json
sudo stat -c '%a %U %G %n' \
  /home/hermes/.hermes/runtime/profile/current.json
sudo -u hermes -H env \
  PATH=/home/hermes/.local/bin:/usr/local/bin:/usr/bin:/bin \
  /usr/local/sbin/hermes-sync-runtime-config
```

Retry gate: local validation prints `runtime-profile-ok`, the host
loader exits zero, and `/home/hermes/.hermes/runtime/profile/current.json` is a
nonempty mode-`0600` file. During the first deployment there is no valid cache
to fall back to, so an SSM read failure must be corrected before bootstrap can
complete.

## 5. OAuth or model selection fails

Run authentication only as the `hermes` owner and do not print or copy the
credential file:

```sh
sudo -iu hermes bash -lc \
  'PATH="$HOME/.local/bin:$PATH" hermes auth status openai-codex'
sudo -iu hermes bash -lc \
  'PATH="$HOME/.local/bin:$PATH" hermes auth add openai-codex'
sudo -iu hermes bash -lc \
  'PATH="$HOME/.local/bin:$PATH" hermes model'
```

Use the displayed device-code flow as the ChatGPT subscription owner. If the
configured model is absent, update and republish the private Runtime Profile
with a model actually offered to that account; do not enable API-key or paid
fallback. Then restart and inspect Gateway:

```sh
HERMES_UID="$(id -u hermes)"
sudo -u hermes -H env \
  XDG_RUNTIME_DIR="/run/user/$HERMES_UID" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$HERMES_UID/bus" \
  systemctl --user restart hermes-gateway.service
sudo -u hermes -H env \
  XDG_RUNTIME_DIR="/run/user/$HERMES_UID" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$HERMES_UID/bus" \
  journalctl --user -u hermes-gateway.service -b --no-pager -n 200
```

Retry gate: `hermes auth status openai-codex` reports a usable credential, the
configured model is offered, Gateway remains `active`, and its journal shows
no provider-authentication failure. Follow `MODEL_PROVIDER_STRATEGY.md` for the
full no-fallback contract.

## 6. Dashboard or port forwarding fails

First separate a host-side service failure from a workstation forwarding
failure. Inside SSM:

```sh
sudo systemctl status hermes-dashboard.service --no-pager
sudo journalctl -u hermes-dashboard.service -b --no-pager -n 200
curl --fail --silent http://127.0.0.1:9119/api/health >/dev/null \
  && echo dashboard-health-ok
```

If host health succeeds, verify the local Session Manager plugin and check
whether port 9119 is already occupied:

```sh
session-manager-plugin --version
python3 -c \
  'import socket; s=socket.socket(); s.bind(("127.0.0.1", 9119)); print("local-port-9119-available")'
```

Stop an obsolete local listener, or forward to a different **local** port
without changing the instance service or security group:

```sh
aws ssm start-session \
  --region "$AWS_REGION" \
  --target "$HERMES_INSTANCE_ID" \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["9119"],"localPortNumber":["9121"]}'
```

Then open <http://127.0.0.1:9121>. Retry gate: the host health command prints
`dashboard-health-ok`, the port-forward session stays open, and the local URL
loads. Keep the Dashboard bound to instance loopback.

## 7. Prepare and execute a recovery attempt

Only continue after the relevant retry gate passes. Use a new Change Set name
so evidence from the earlier attempt remains unambiguous:

```sh
export HERMES_CHANGE_SET_NAME=first-deployment-recovery-1

AWS_REGION="$AWS_REGION" \
HERMES_STACK_NAME="$HERMES_STACK_NAME" \
HERMES_TEMPLATE_URL="$HERMES_TEMPLATE_URL" \
HERMES_PARAMETER_FILE="$HERMES_PARAMETER_FILE" \
HERMES_CHANGE_SET_NAME="$HERMES_CHANGE_SET_NAME" \
./deploy/minimal/create-change-set.sh
```

For a preserved failure, stop unless the helper prints all of:

```text
StackStatusBefore=CREATE_FAILED
ChangeSetType=UPDATE
FailureResourcesPreserved=execute-disable-rollback-required
Waiter=stack-update-complete
```

Review the entire Change Set again. If it contains an unexpected replacement,
delete that Change Set and correct the template or parameters; do not execute
it. Execute an approved recovery UPDATE with rollback disabled so evidence is
preserved again if it fails:

```sh
export HERMES_CHANGE_SET_ID=REPLACE_WITH_REVIEWED_RECOVERY_CHANGE_SET_ID

aws cloudformation execute-change-set \
  --region "$AWS_REGION" \
  --change-set-name "$HERMES_CHANGE_SET_ID" \
  --disable-rollback

aws cloudformation wait stack-update-complete \
  --region "$AWS_REGION" \
  --stack-name "$HERMES_STACK_NAME"
```

Success means the Stack reaches `UPDATE_COMPLETE`, SSM reports `connected`,
`/home/hermes/.bootstrap-complete` exists, both services are active, and the
Dashboard health check succeeds. Resume Quickstart at owner OAuth or the first
missing acceptance marker—not at resource creation.

## 8. Clean up an unrecoverable rolled-back attempt

Use this path only for `ROLLBACK_COMPLETE`, or when an operator has explicitly
decided to abandon a preserved failed Stack. Stack deletion terminates the
instance and its `DeleteOnTermination` root volume; copy needed evidence and
snapshot any state that must survive before proceeding.

```sh
aws cloudformation delete-stack \
  --region "$AWS_REGION" \
  --stack-name "$HERMES_STACK_NAME"

aws cloudformation wait stack-delete-complete \
  --region "$AWS_REGION" \
  --stack-name "$HERMES_STACK_NAME"
```

If the waiter fails, inspect the newest `DELETE_FAILED` event and resolve that
specific resource. Do not use force deletion as a generic retry. After
`describe-stacks` confirms the Stack no longer exists, choose a new Change Set
name and run the helper; it must print `ChangeSetType=CREATE` and
`FailureResourcesPreserved=on-stack-failure-do-nothing`.
