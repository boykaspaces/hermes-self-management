import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
MINIMAL = ROOT / "deploy" / "minimal"
POLICY = MINIMAL / "policies" / "deployer-policy.json.tmpl"

REPLACEMENTS = {
    "${AWS_ACCOUNT_ID}": "123456789012",
    "${AWS_REGION}": "us-east-1",
    "${ARTIFACT_BUCKET}": "example-artifact-bucket",
    "${TEMPLATE_PREFIX}": "hermes-self-management/cloudformation",
    "${RUNTIME_ARTIFACT_PREFIX}": "hermes-self-management/runtime",
    "${RUNTIME_PROFILE_PARAMETER_NAME}": "/example-hermes/runtime/profile",
    "${HERMES_STACK_NAME}": "example-hermes",
    "${HERMES_ROLE_PREFIX}": "example-hermes-",
    "${PROJECT_TAG}": "hermes-self-management",
}


def render_policy() -> dict[str, object]:
    body = POLICY.read_text(encoding="utf-8")
    for source, target in REPLACEMENTS.items():
        body = body.replace(source, target)
    return json.loads(body)


class DeployerPolicyTest(unittest.TestCase):
    def setUp(self):
        policy = render_policy()
        self.statements = {
            statement["Sid"]: statement for statement in policy["Statement"]
        }

    def test_discovery_ec2_reads_are_authorized(self):
        discovery = (ROOT / "deploy" / "bootstrap" / "discover-environment.sh").read_text(
            encoding="utf-8"
        )
        commands = set(re.findall(r"aws ec2 (describe-[a-z-]+)", discovery))
        required_actions = {
            "ec2:" + "".join(part.title() for part in command.split("-"))
            for command in commands
        }
        statement = self.statements["ReadDeploymentDependenciesInTargetRegion"]
        self.assertTrue(required_actions.issubset(statement["Action"]))
        self.assertIn("ec2:DescribeRouteTables", required_actions)

    def test_failed_boot_console_output_is_read_only(self):
        statement = self.statements["ReadDeploymentDependenciesInTargetRegion"]
        self.assertIn("ec2:GetConsoleOutput", statement["Action"])
        self.assertEqual(statement["Effect"], "Allow")
        self.assertEqual(statement["Resource"], "*")
        self.assertEqual(
            statement["Condition"]["StringEquals"]["aws:RequestedRegion"],
            "us-east-1",
        )

    def test_runtime_profile_access_is_exact_and_not_global(self):
        statement = self.statements["ManageOnlyConfiguredRuntimeProfile"]
        self.assertEqual(
            statement["Action"],
            ["ssm:GetParameter", "ssm:PutParameter"],
        )
        self.assertEqual(
            statement["Resource"],
            "arn:aws:ssm:us-east-1:123456789012:parameter/example-hermes/runtime/profile",
        )
        global_actions = self.statements[
            "ReadDeploymentDependenciesInTargetRegion"
        ]["Action"]
        self.assertNotIn("ssm:GetParameter", global_actions)
        self.assertNotIn("runtime/telegram-enabled", POLICY.read_text(encoding="utf-8"))

    def test_bucket_location_has_no_prefix_condition(self):
        statement = self.statements["ReadHermesArtifactBucketLocation"]
        self.assertEqual(statement["Action"], "s3:GetBucketLocation")
        self.assertNotIn("Condition", statement)

    def test_listing_and_objects_cover_both_publisher_prefixes(self):
        expected_prefixes = [
            "hermes-self-management/cloudformation/*",
            "hermes-self-management/runtime/*",
        ]
        list_statement = self.statements["ListOnlyHermesArtifactPrefixes"]
        self.assertEqual(
            list_statement["Condition"]["StringLike"]["s3:prefix"],
            expected_prefixes,
        )

        object_statement = self.statements["ManageOnlyHermesDeploymentArtifacts"]
        self.assertEqual(
            object_statement["Resource"],
            [
                "arn:aws:s3:::example-artifact-bucket/"
                "hermes-self-management/cloudformation/*",
                "arn:aws:s3:::example-artifact-bucket/"
                "hermes-self-management/runtime/*",
            ],
        )

        template_publisher = (MINIMAL / "publish-template.sh").read_text(
            encoding="utf-8"
        )
        runtime_publisher = (MINIMAL / "publish-runtime-artifacts.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('key="hermes-self-management/cloudformation/', template_publisher)
        self.assertIn('key="hermes-self-management/runtime/', runtime_publisher)


if __name__ == "__main__":
    unittest.main()
