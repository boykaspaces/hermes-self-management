# First AWS Deployment

This runbook takes a new operator from a fresh public clone to a reviewable
CloudFormation Change Set for their own Hermes host. It does not depend on a
private repository owned by this project's maintainer and it never asks for a
Secret value in a CloudFormation parameter.

## 1. Prerequisites and private workspace

Install `aws` CLI v2, `jq`, Python 3, Ruby, Git, and `ripgrep`. Clone the public
component directly; no private operations repository is required or fetched:

```sh
git clone https://github.com/boykaspaces/hermes-self-management.git
cd hermes-self-management
```

Authenticate the AWS CLI to the intended account and choose one Region
explicitly:

```sh
export AWS_REGION=us-west-2
aws sts get-caller-identity
```

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

Add optional `TelegramRuntimeSecretArn`,
`PersonalToolsClientTokenSecretArn`, or credential-agent parameters only when
those capabilities are intentionally enabled. Do not add Secret values.

Create, but do not execute, the initial Change Set:

```sh
AWS_REGION="$AWS_REGION" \
HERMES_STACK_NAME=my-hermes \
HERMES_TEMPLATE_URL="$HERMES_TEMPLATE_URL" \
HERMES_PARAMETER_FILE=../my-hermes-ops/hermes-parameters.json \
HERMES_CHANGE_SET_NAME=initial-reviewed-deployment \
./deploy/minimal/create-change-set.sh
```

The helper rejects parameter files inside the public clone and rejects example
placeholders. It never calls `execute-change-set`.

## 8. Review, execute, and finish owner authentication

Wait for the Change Set to finish preparing, then inspect every resource and
replacement decision:

```sh
aws cloudformation describe-change-set \
  --region "$AWS_REGION" \
  --change-set-name CHANGE_SET_ID_FROM_THE_HELPER
```

Confirm the EC2 security group has no inbound rule, the selected subnet and
AMI are expected, IAM and Secret access are narrowly scoped, artifact
identities are immutable, and no unknown replacement is present. Execute only
after that human review.

After the Stack reaches `CREATE_COMPLETE`, use its Outputs for the SSM session
command. Complete ChatGPT subscription OAuth manually as the owner; OAuth
files are not transported through CloudFormation, User Data, S3 artifacts, or
the Runtime Profile.

Run the Gateway, Dashboard, Telegram, Runtime Profile, Secret, Podman, egress,
patch, and observability checks in [`minimal/README.md`](./minimal/README.md).
Record actual Stack IDs, parameters, outputs, artifact versions, acceptance,
and rollback targets only in the operator's private system.
