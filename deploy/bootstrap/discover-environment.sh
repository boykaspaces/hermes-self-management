#!/usr/bin/env bash
set -euo pipefail

region="${AWS_REGION:?set AWS_REGION to the intended deployment Region}"
vpc_id="${HERMES_VPC_ID:-}"
subnet_id="${HERMES_SUBNET_ID:-}"

command -v aws >/dev/null 2>&1 || {
  echo 'aws CLI is required' >&2
  exit 1
}

if [[ -n "$vpc_id" && ! "$vpc_id" =~ ^vpc-[0-9a-f]{8,17}$ ]]; then
  echo 'HERMES_VPC_ID must be a complete VPC ID' >&2
  exit 1
fi
if [[ -n "$subnet_id" && ! "$subnet_id" =~ ^subnet-[0-9a-f]{8,17}$ ]]; then
  echo 'HERMES_SUBNET_ID must be a complete subnet ID' >&2
  exit 1
fi
if [[ -n "$subnet_id" && -z "$vpc_id" ]]; then
  echo 'set HERMES_VPC_ID when HERMES_SUBNET_ID is set' >&2
  exit 1
fi

account_id="$(aws sts get-caller-identity \
  --region "$region" \
  --query Account \
  --output text)"

printf 'AWS account: %s\n' "$account_id"
printf 'AWS Region:  %s\n\n' "$region"

if [[ -n "$vpc_id" ]]; then
  printf 'Selected VPC\n'
  aws ec2 describe-vpcs \
    --region "$region" \
    --vpc-ids "$vpc_id" \
    --query 'Vpcs[].{VpcId:VpcId,Default:IsDefault,Cidr:CidrBlock,State:State}' \
    --output table
  subnet_filter=(--filters "Name=vpc-id,Values=$vpc_id" 'Name=state,Values=available')
else
  printf 'Available VPCs (none is selected automatically)\n'
  aws ec2 describe-vpcs \
    --region "$region" \
    --filters 'Name=state,Values=available' \
    --query 'Vpcs[].{VpcId:VpcId,Default:IsDefault,Cidr:CidrBlock,State:State}' \
    --output table
  subnet_filter=(--filters 'Name=state,Values=available')
fi

printf '\nCandidate subnets (verify the associated route table before selection)\n'
aws ec2 describe-subnets \
  --region "$region" \
  "${subnet_filter[@]}" \
  --query 'Subnets[].{SubnetId:SubnetId,VpcId:VpcId,AZ:AvailabilityZone,Cidr:CidrBlock,PublicIp:MapPublicIpOnLaunch,AvailableIPs:AvailableIpAddressCount}' \
  --output table

if [[ -n "$subnet_id" ]]; then
  printf '\nSelected subnet (must belong to the selected VPC)\n'
  aws ec2 describe-subnets \
    --region "$region" \
    --subnet-ids "$subnet_id" \
    --filters "Name=vpc-id,Values=$vpc_id" \
    --query 'Subnets[].{SubnetId:SubnetId,VpcId:VpcId,AZ:AvailabilityZone,Cidr:CidrBlock,PublicIp:MapPublicIpOnLaunch}' \
    --output table

  printf '\nExplicit route-table association for the selected subnet (empty means use the VPC main route table)\n'
  aws ec2 describe-route-tables \
    --region "$region" \
    --filters "Name=association.subnet-id,Values=$subnet_id" \
    --query 'RouteTables[].{RouteTableId:RouteTableId,Routes:Routes[].{Destination:DestinationCidrBlock,Gateway:GatewayId,NatGateway:NatGatewayId,State:State}}' \
    --output json

  printf '\nVPC main route table (effective when no explicit association exists)\n'
  aws ec2 describe-route-tables \
    --region "$region" \
    --filters "Name=vpc-id,Values=$vpc_id" 'Name=association.main,Values=true' \
    --query 'RouteTables[].{RouteTableId:RouteTableId,Routes:Routes[].{Destination:DestinationCidrBlock,Gateway:GatewayId,NatGateway:NatGatewayId,State:State}}' \
    --output json
fi

printf '\nRecent Canonical Ubuntu 24.04 amd64 gp3 AMIs (review and pin one)\n'
aws ec2 describe-images \
  --region "$region" \
  --owners 099720109477 \
  --filters \
    'Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*' \
    'Name=state,Values=available' \
    'Name=architecture,Values=x86_64' \
  --query 'reverse(sort_by(Images,&CreationDate))[:5].{AmiId:ImageId,Created:CreationDate,Name:Name}' \
  --output table

cat <<'EOF'

No VPC, subnet, or AMI was selected. Before deployment, verify the chosen
subnet's effective route table has the intended outbound path and record the
reviewed IDs in a private parameter file outside this clone.
EOF
