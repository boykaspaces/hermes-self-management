import json
import os
import pathlib
import re
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
BOOTSTRAP = ROOT / "deploy" / "bootstrap"
MINIMAL = ROOT / "deploy" / "minimal"


class BootstrapContractTest(unittest.TestCase):
    def test_parameter_example_is_non_secret_and_complete(self):
        parameters = json.loads(
            (MINIMAL / "parameters.example.json").read_text(encoding="utf-8")
        )
        values = {item["ParameterKey"]: item["ParameterValue"] for item in parameters}
        required = {
            "VpcId",
            "SubnetId",
            "AmiId",
            "RuntimeBundleArtifactS3Bucket",
            "RuntimeBundleArtifactS3Key",
            "RuntimeBundleArtifactS3ObjectVersion",
            "RuntimeBundleArtifactSHA256",
            "RuntimeProfileParameterName",
        }
        self.assertTrue(required.issubset(values))
        self.assertFalse(
            any(re.search(r"token|password|private.?key|oauth", key, re.I) for key in values)
        )

    def test_discovery_script_is_read_only(self):
        source = (BOOTSTRAP / "discover-environment.sh").read_text(encoding="utf-8")
        self.assertIn("get-caller-identity", source)
        self.assertIn("describe-vpcs", source)
        self.assertIn("describe-subnets", source)
        self.assertIn("describe-route-tables", source)
        self.assertIn("describe-images", source)
        self.assertNotRegex(
            source,
            r"aws\s+(?:cloudformation|ec2|s3|ssm|secretsmanager)\s+"
            r"(?:create|delete|deploy|execute|put|start|stop|update)",
        )

    def test_change_set_helper_never_executes(self):
        source = (MINIMAL / "create-change-set.sh").read_text(encoding="utf-8")
        self.assertIn("create-change-set", source)
        self.assertNotIn("execute-change-set", source)
        self.assertIn("inside the public clone", source)

    def test_change_set_helper_creates_review_only_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = pathlib.Path(temporary)
            parameter_file = temporary_path / "parameters.json"
            parameter_file.write_text(
                json.dumps(
                    [
                        {"ParameterKey": "VpcId", "ParameterValue": "vpc-00000000"},
                        {
                            "ParameterKey": "SubnetId",
                            "ParameterValue": "subnet-00000000",
                        },
                    ]
                ),
                encoding="utf-8",
            )
            capture = temporary_path / "aws-arguments.txt"
            fake_aws = temporary_path / "aws"
            fake_aws.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$@\" >\"$AWS_CAPTURE\"\n"
                "printf '%s\\n' 'arn:aws:cloudformation:us-west-2:000000000000:changeSet/example/00000000'\n",
                encoding="utf-8",
            )
            fake_aws.chmod(0o700)
            environment = os.environ.copy()
            environment.update(
                {
                    "AWS_CAPTURE": str(capture),
                    "AWS_REGION": "us-west-2",
                    "HERMES_STACK_NAME": "example-hermes",
                    "HERMES_TEMPLATE_URL": "https://example.invalid/template.yaml",
                    "HERMES_PARAMETER_FILE": str(parameter_file),
                    "PATH": f"{temporary}:{environment['PATH']}",
                }
            )
            completed = subprocess.run(
                [str(MINIMAL / "create-change-set.sh")],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            arguments = capture.read_text(encoding="utf-8")
            self.assertIn("create-change-set", arguments)
            self.assertIn("CREATE", arguments)
            self.assertIn("CAPABILITY_IAM", arguments)
            self.assertNotIn("execute-change-set", arguments)
            self.assertIn("does not execute", completed.stdout)

    def test_runtime_profile_check_uses_external_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = pathlib.Path(temporary) / "runtime-profile.json"
            profile.write_text(
                (MINIMAL / "runtime-profile.example.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment.update(
                {
                    "AWS_REGION": "us-west-2",
                    "HERMES_RUNTIME_PROFILE_FILE": str(profile),
                    "HERMES_RUNTIME_PROFILE_PARAMETER": "/example-hermes/runtime/profile",
                }
            )
            completed = subprocess.run(
                [str(MINIMAL / "publish-runtime-profile.sh"), "--check"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertIn("runtime-profile-validation-ok", completed.stdout)

    def test_bootstrap_templates_preserve_security_boundaries(self):
        bucket = (BOOTSTRAP / "artifacts-cloudformation.yaml").read_text(
            encoding="utf-8"
        )
        network = (BOOTSTRAP / "network-cloudformation.yaml").read_text(
            encoding="utf-8"
        )
        for expected in (
            "VersioningConfiguration",
            "BucketEncryption",
            "BlockPublicPolicy: true",
            "aws:SecureTransport: false",
            "DeletionPolicy: Retain",
        ):
            self.assertIn(expected, bucket)
        self.assertIn("MapPublicIpOnLaunch: true", network)
        self.assertIn("DestinationCidrBlock: 0.0.0.0/0", network)
        self.assertNotIn("AWS::EC2::SecurityGroupIngress", network)


if __name__ == "__main__":
    unittest.main()
