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
PREFLIGHT = ROOT / "deploy" / "preflight.sh"


class BootstrapContractTest(unittest.TestCase):
    def _preflight_environment(self, temporary_path, include_plugin=True):
        versions = {
            "jq": "jq-1.6",
            "python3": "Python 3.9.0",
            "ruby": "ruby 2.6.0p0 (example revision)",
            "git": "git version 2.20.0",
            "rg": "ripgrep 12.0.0",
            "shasum": "6.02",
        }
        if include_plugin:
            versions["session-manager-plugin"] = "1.2.0.0"

        for name, version in versions.items():
            executable = temporary_path / name
            executable.write_text(
                f"#!/bin/sh\nprintf '%s\\n' '{version}'\n",
                encoding="utf-8",
            )
            executable.chmod(0o700)

        capture = temporary_path / "aws-arguments.txt"
        fake_aws = temporary_path / "aws"
        fake_aws.write_text(
            "#!/bin/sh\n"
            "if [ \"${1:-}\" = sts ]; then\n"
            "  printf '%s\\n' \"$@\" >\"$AWS_CAPTURE\"\n"
            "  printf '%s\\n' 000000000000\n"
            "else\n"
            "  printf '%s\\n' 'aws-cli/2.15.0 Python/3.11.0 Linux/6.1'\n"
            "fi\n",
            encoding="utf-8",
        )
        fake_aws.chmod(0o700)

        environment = os.environ.copy()
        environment.update(
            {
                "AWS_CAPTURE": str(capture),
                "AWS_REGION": "us-west-2",
                "PATH": f"{temporary_path}:/usr/bin:/bin",
            }
        )
        return environment, capture

    def _run_change_set_helper(
        self, temporary_path, stack_status, change_set_name="first-deployment-recovery-1"
    ):
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
            "#!/bin/sh\n"
            "if [ \"${1:-} ${2:-}\" = 'cloudformation describe-stacks' ]; then\n"
            "  case \"$AWS_STACK_STATUS\" in\n"
            "    DOES_NOT_EXIST)\n"
            "      printf '%s\\n' 'ValidationError: Stack with id example-hermes does not exist' >&2\n"
            "      exit 255\n"
            "      ;;\n"
            "    ACCESS_DENIED)\n"
            "      printf '%s\\n' 'AccessDenied: not authorized' >&2\n"
            "      exit 254\n"
            "      ;;\n"
            "    *) printf '%s\\n' \"$AWS_STACK_STATUS\" ;;\n"
            "  esac\n"
            "elif [ \"${1:-} ${2:-}\" = 'cloudformation create-change-set' ]; then\n"
            "  printf '%s\\n' \"$@\" >\"$AWS_CAPTURE\"\n"
            "  printf '%s\\n' 'arn:aws:cloudformation:us-west-2:000000000000:changeSet/example/00000000'\n"
            "else\n"
            "  printf '%s\\n' 'unexpected aws command' >&2\n"
            "  exit 253\n"
            "fi\n",
            encoding="utf-8",
        )
        fake_aws.chmod(0o700)
        environment = os.environ.copy()
        environment.update(
            {
                "AWS_CAPTURE": str(capture),
                "AWS_STACK_STATUS": stack_status,
                "AWS_REGION": "us-west-2",
                "HERMES_STACK_NAME": "example-hermes",
                "HERMES_TEMPLATE_URL": "https://example.invalid/template.yaml",
                "HERMES_PARAMETER_FILE": str(parameter_file),
                "PATH": f"{temporary_path}:{environment['PATH']}",
            }
        )
        if change_set_name is not None:
            environment["HERMES_CHANGE_SET_NAME"] = change_set_name
        else:
            environment.pop("HERMES_CHANGE_SET_NAME", None)
        completed = subprocess.run(
            [str(MINIMAL / "create-change-set.sh")],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        arguments = capture.read_text(encoding="utf-8") if capture.exists() else ""
        return completed, arguments

    def test_preflight_checks_versions_and_only_reads_aws_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = pathlib.Path(temporary)
            environment, capture = self._preflight_environment(temporary_path)
            completed = subprocess.run(
                [str(PREFLIGHT), "--aws"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertIn("session-manager-plugin=1.2.0.0", completed.stdout)
            self.assertIn("preflight-ok version=1", completed.stdout)
            arguments = capture.read_text(encoding="utf-8")
            self.assertIn("get-caller-identity", arguments)
            self.assertNotRegex(
                arguments,
                r"(?m)^(?:create|delete|deploy|execute|put|start|stop|update)(?:-|$)",
            )

    def test_preflight_fails_when_session_manager_plugin_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            environment, _capture = self._preflight_environment(
                pathlib.Path(temporary), include_plugin=False
            )
            completed = subprocess.run(
                [str(PREFLIGHT)],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn(
                "preflight-error: session-manager-plugin is required",
                completed.stderr,
            )

    def test_preflight_rejects_an_unsupported_tool_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = pathlib.Path(temporary)
            environment, _capture = self._preflight_environment(temporary_path)
            old_python = temporary_path / "python3"
            old_python.write_text(
                "#!/bin/sh\nprintf '%s\\n' 'Python 3.8.0'\n",
                encoding="utf-8",
            )
            old_python.chmod(0o700)
            completed = subprocess.run(
                [str(PREFLIGHT)],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn(
                "preflight-error: Python 3.9 or newer is required",
                completed.stderr,
            )

    def test_quickstart_declares_supported_defaults_before_resources(self):
        quickstart = (ROOT / "deploy" / "QUICKSTART.md").read_text(encoding="utf-8")
        self.assertLess(
            quickstart.index("## 0. Check suitability and default capabilities"),
            quickstart.index("## 1. Prerequisites and private workspace"),
        )
        for expected in (
            "AWS Session Manager plugin",
            "Ubuntu 24.04 LTS x86_64",
            "openai-codex",
            "cannot clone a remote repository or install packages",
            "browser.backend=off",
            "preflight-ok version=1",
        ):
            self.assertIn(expected, quickstart)

        profile = json.loads(
            (MINIMAL / "runtime-profile.example.json").read_text(encoding="utf-8")
        )
        parameters = json.loads(
            (MINIMAL / "parameters.example.json").read_text(encoding="utf-8")
        )
        values = {item["ParameterKey"]: item["ParameterValue"] for item in parameters}
        apply_source = (MINIMAL / "apply_runtime_profile.py").read_text(
            encoding="utf-8"
        )
        self.assertFalse(profile["telegram"]["enabled"])
        self.assertEqual(values["GitCodingEnabled"], "false")
        self.assertIn('"backend": "off"', apply_source)
        self.assertIn('"docker_network": False', apply_source)
        self.assertIn('"provider": "openai-codex"', apply_source)
        self.assertIn('config.pop("fallback_model", None)', apply_source)

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

    def test_first_boot_uses_reviewed_immutable_installation_inputs(self):
        template = (MINIMAL / "cloudformation.yaml").read_text(encoding="utf-8")
        parameters = json.loads(
            (MINIMAL / "parameters.example.json").read_text(encoding="utf-8")
        )
        values = {item["ParameterKey"]: item["ParameterValue"] for item in parameters}

        expected = {
            "HermesGitRef": "29112bef099274229cadff79cdff7bf7b99c4b77",
            "HermesInstallerSHA256": (
                "85ef536d455e51ab67aa74d79272efd49fe717597dbaadfd3cca179a905f4706"
            ),
            "HermesUvLockSHA256": (
                "383cd8f98ec23dc3fe4cf63759ec73be5a869cc953f068b4e79ec4e8ed00287d"
            ),
            "HermesPackageLockSHA256": (
                "83beeba3f6e7826312444c7b64067488afae9ed88ad7326ecef61ac235bab86d"
            ),
            "AgentBrowserVersion": "0.26.0",
            "CodingContainerBaseImage": (
                "docker.io/nikolaik/python-nodejs@sha256:"
                "6ed4d9fb74dc6c7a5caa9120d8d3c507dbf97fb112b7b09d0d9f7d71f1ce919d"
            ),
        }
        self.assertEqual({key: values[key] for key in expected}, expected)

        for marker in (
            "raw.githubusercontent.com/NousResearch/hermes-agent/"
            "${HermesGitRef}/scripts/install.sh",
            "${HermesInstallerSHA256}",
            "${HermesUvLockSHA256}",
            "${HermesPackageLockSHA256}",
            "--commit '${HermesGitRef}'",
            "/home/hermes/.hermes/bin/uv sync --extra all --locked",
            "agent-browser@${AgentBrowserVersion}",
            "podman pull '${CodingContainerBaseImage}'",
            "/home/hermes/.hermes/install-manifest/python-packages.txt",
            "npm ls --all --json --workspace web",
            "coding_container_resolved_digest=",
        ):
            self.assertIn(marker, template)

        self.assertNotIn("hermes-agent.nousresearch.com/install.sh", template)
        self.assertNotIn('pip install -e ".[all]"', template)
        self.assertNotIn("agent-browser@^", template)
        self.assertNotIn(
            "podman pull docker.io/nikolaik/python-nodejs:python3.11-nodejs20",
            template,
        )

    def test_runtime_profile_parameter_name_has_one_quickstart_source(self):
        parameters = json.loads(
            (MINIMAL / "parameters.example.json").read_text(encoding="utf-8")
        )
        values = {item["ParameterKey"]: item["ParameterValue"] for item in parameters}
        quickstart = (ROOT / "deploy" / "QUICKSTART.md").read_text(encoding="utf-8")

        self.assertEqual(
            values["RuntimeProfileParameterName"],
            "REPLACE_WITH_RUNTIME_PROFILE_PARAMETER_NAME",
        )
        self.assertRegex(
            quickstart,
            r"export HERMES_RUNTIME_PROFILE_PARAMETER=/[^\s]+/runtime/profile",
        )
        self.assertIn(
            'HERMES_RUNTIME_PROFILE_PARAMETER="$HERMES_RUNTIME_PROFILE_PARAMETER"',
            quickstart,
        )
        self.assertIn('--arg name "$HERMES_RUNTIME_PROFILE_PARAMETER"', quickstart)
        self.assertIn(
            '.ParameterKey == "RuntimeProfileParameterName"',
            quickstart,
        )

    def test_quickstart_reaches_a_post_restart_conversation(self):
        quickstart = (ROOT / "deploy" / "QUICKSTART.md").read_text(encoding="utf-8")
        ordered_markers = [
            "aws cloudformation execute-change-set",
            "aws cloudformation wait stack-create-complete",
            "dashboard-health-ok",
            "hermes auth add openai-codex",
            "hermes auth status openai-codex",
            "hermes model",
            "AWS-StartPortForwardingSession",
            "HERMES_FIRST_CONVERSATION_OK",
            "aws ec2 stop-instances",
            "aws ec2 wait instance-stopped",
            "aws ec2 start-instances",
            "aws ec2 wait instance-status-ok",
            "HERMES_RESTART_CONVERSATION_OK",
        ]
        positions = [quickstart.index(marker) for marker in ordered_markers]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("export HERMES_STACK_NAME=my-hermes", quickstart)
        self.assertIn("MODEL_PROVIDER_STRATEGY.md", quickstart)
        self.assertIn("https://learn.chatgpt.com/docs/auth", quickstart)

        template = (MINIMAL / "cloudformation.yaml").read_text(encoding="utf-8")
        self.assertIn("DashboardPortForwardCommand", template)
        self.assertIn("http://127.0.0.1:9119", template)
        self.assertIn("AWS-StartPortForwardingSession", template)
        self.assertIn(
            "--parameters '{\"portNumber\":[\"9119\"],\"localPortNumber\":[\"9119\"]}'",
            template,
        )

    def test_first_deployment_recovery_has_bounded_symptom_routes(self):
        quickstart = (ROOT / "deploy" / "QUICKSTART.md").read_text(
            encoding="utf-8"
        )
        recovery = (MINIMAL / "FIRST_DEPLOYMENT_RECOVERY.md").read_text(
            encoding="utf-8"
        )
        helper = (MINIMAL / "create-change-set.sh").read_text(encoding="utf-8")

        self.assertIn("FIRST_DEPLOYMENT_RECOVERY.md", quickstart)
        self.assertIn("FailureResourcesPreserved=on-stack-failure-do-nothing", quickstart)
        self.assertIn("--on-stack-failure DO_NOTHING", helper)
        for marker in (
            "## 2. Stack or first-boot failure",
            "## 3. SSM does not connect",
            "## 4. Runtime Profile cannot be read or applied",
            "## 5. OAuth or model selection fails",
            "## 6. Dashboard or port forwarding fails",
            "describe-stack-events",
            "/var/log/cloud-init-output.log",
            "ec2 get-console-output",
            "ssm get-connection-status",
            "validate_runtime_profile.py",
            "journalctl --user -u hermes-gateway.service",
            "journalctl -u hermes-dashboard.service",
            "FailureResourcesPreserved=execute-disable-rollback-required",
            "wait stack-update-complete",
            "wait stack-delete-complete",
        ):
            self.assertIn(marker, recovery)
        self.assertIn("Do not manually rerun `/var/lib/cloud/instance/scripts/part-001`", recovery)
        self.assertNotIn("authorize-security-group-ingress", recovery)
        self.assertNotIn("--change-set-type CREATE", recovery)

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
        self.assertNotIn("delete-stack", source)
        self.assertNotIn("rollback-stack", source)
        self.assertIn("inside the public clone", source)

    def test_change_set_helper_creates_review_only_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            completed, arguments = self._run_change_set_helper(
                pathlib.Path(temporary), "DOES_NOT_EXIST"
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("create-change-set", arguments)
            self.assertIn("CREATE", arguments)
            self.assertIn("--on-stack-failure", arguments)
            self.assertIn("DO_NOTHING", arguments)
            self.assertIn("CAPABILITY_IAM", arguments)
            self.assertNotIn("execute-change-set", arguments)
            self.assertIn("StackStatusBefore=DOES_NOT_EXIST", completed.stdout)
            self.assertIn("ChangeSetType=CREATE", completed.stdout)
            self.assertIn("Waiter=stack-create-complete", completed.stdout)
            self.assertIn("does not execute", completed.stdout)

    def test_change_set_helper_prepares_recovery_update_for_preserved_failure(self):
        for stack_status in ("CREATE_FAILED", "UPDATE_FAILED"):
            with self.subTest(stack_status=stack_status):
                with tempfile.TemporaryDirectory() as temporary:
                    completed, arguments = self._run_change_set_helper(
                        pathlib.Path(temporary), stack_status
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertIn("create-change-set", arguments)
                    self.assertIn("UPDATE", arguments)
                    self.assertNotIn("--on-stack-failure", arguments)
                    self.assertIn(
                        f"StackStatusBefore={stack_status}", completed.stdout
                    )
                    self.assertIn("ChangeSetType=UPDATE", completed.stdout)
                    self.assertIn(
                        "FailureResourcesPreserved="
                        "execute-disable-rollback-required",
                        completed.stdout,
                    )
                    self.assertIn("Waiter=stack-update-complete", completed.stdout)

    def test_change_set_helper_requires_a_new_name_for_recovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            completed, arguments = self._run_change_set_helper(
                pathlib.Path(temporary), "CREATE_FAILED", change_set_name=None
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(arguments, "")
            self.assertIn("new recovery-specific name", completed.stderr)

    def test_change_set_helper_rejects_unsafe_stack_states_and_aws_errors(self):
        for stack_status in (
            "CREATE_IN_PROGRESS",
            "ROLLBACK_COMPLETE",
            "UPDATE_ROLLBACK_FAILED",
            "CREATE_COMPLETE",
            "ACCESS_DENIED",
        ):
            with self.subTest(stack_status=stack_status):
                with tempfile.TemporaryDirectory() as temporary:
                    completed, arguments = self._run_change_set_helper(
                        pathlib.Path(temporary), stack_status
                    )
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertEqual(arguments, "")
                    self.assertIn("no Change Set was created", completed.stderr)

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
