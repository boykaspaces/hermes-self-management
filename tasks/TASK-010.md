# TASK-010: Fix Runtime Profile Parameter Handoff

Status: Completed
Priority: High

## Goal

Remove the first-deployment Runtime Profile parameter-name mismatch and make the
published parameter name flow explicitly into the private CloudFormation
parameter file.

## Acceptance Criteria

- Quickstart defines one Runtime Profile parameter name and uses it for
  publication and private parameter-file preparation.
- `parameters.example.json` cannot silently select a different concrete SSM
  path.
- Bootstrap contract tests fail if the explicit handoff is removed or a
  concrete example path returns.
- Repository validation passes without changing AWS resources, IAM policy,
  runtime behavior, or deployment state.

## Completed

- Created the bounded remediation Task from the accepted `main` branch.
- Replaced the concrete Runtime Profile path in `parameters.example.json` with
  an unresolved placeholder that the Change Set helper already rejects.
- Defined the consumer's selected SSM parameter name once in Quickstart and
  reused it for profile publication.
- Generated the private CloudFormation parameter file with `jq`, injecting the
  exact exported name instead of copying a second concrete path.
- Added a bootstrap contract test covering the placeholder, publisher input,
  and parameter-file handoff.
- Passed the seven focused bootstrap tests, complete repository validation, and
  Context Kit project validation.

## Remaining

None.

## Blockers

None.

## Result

The first-deployment instructions now have one operator-selected Runtime
Profile parameter name. The same exported value is used to publish the profile
and populate `RuntimeProfileParameterName` in the private CloudFormation
parameter file, while an unresolved placeholder prevents the public example
from silently selecting a different path.

## Relevant Files

- `deploy/QUICKSTART.md`
- `deploy/minimal/parameters.example.json`
- `deploy/bootstrap/tests/test_bootstrap.py`
- `tasks/TASK-010.md`

## Next Step

None for TASK-010. Review and accept this bounded proposal before starting the
separate deployer-IAM remediation Task.
