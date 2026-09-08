# Project State

Project: hermes-self-management
Status: Active
Active Task: TASK-009

## Current summary

The public runtime component explicitly adopts Context Kit 0.5.0 project spec
v2 with the repository profile, Hermes adapter v3, GitHub workflow adapter v1,
and the advisory `delivery-governance` extension. The extension names the
optional `ai-delivery-governance` Skill without claiming it is installed in a
live runtime. Mutable, non-secret consumer preferences are
loaded from a separately validated SSM runtime profile instead of CloudFormation
or first-boot User Data. A public first-deployment path now covers read-only AWS
discovery, optional neutral bootstrap infrastructure, immutable artifact
publication, external consumer parameters, and human-reviewed Change Set
creation without private operations access. TASK-009 is preparing the bounded
Context Kit v2 and advisory-governance adoption proposal without changing
runtime or deployment source.

## Primary focus

Complete TASK-009's project-context migration and governance dogfood cycle,
then stop at its pull request for user review before any integration update.

## Active constraints

- Production bindings and deployment evidence remain in private operations.
- Public source must build and validate without private repository access.
