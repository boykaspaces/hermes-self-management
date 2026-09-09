import copy
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
    "validate_runtime_profile", ROOT / "validate_runtime_profile.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

APPLY_SPEC = importlib.util.spec_from_file_location(
    "apply_runtime_profile", ROOT / "apply_runtime_profile.py"
)
APPLY_MODULE = importlib.util.module_from_spec(APPLY_SPEC)
assert APPLY_SPEC.loader is not None
APPLY_SPEC.loader.exec_module(APPLY_MODULE)


class RuntimeProfileValidationTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads(
            (ROOT / "runtime-profile.example.json").read_text(encoding="utf-8")
        )

    def test_example_is_valid(self):
        MODULE.validate_profile(self.profile)

    def v1_profile(self):
        profile = copy.deepcopy(self.profile)
        profile["schema_version"] = 1
        profile.pop("context_workspace")
        return profile

    def enabled_profile(self, host_root, access="read-only"):
        profile = copy.deepcopy(self.profile)
        profile["context_workspace"] = {
            "enabled": True,
            "host_root": str(Path(host_root).resolve()),
            "project_access": access,
        }
        return profile

    def make_workspace(self, root):
        root = Path(root).resolve()
        (root / ".hermes").mkdir()
        (root / "projects").mkdir()
        return root

    def apply(self, profile, config=None):
        return APPLY_MODULE.apply_profile(
            profile,
            {} if config is None else config,
            git_coding_enabled=False,
            mcp_secret_authorized=False,
        )

    def test_v1_remains_valid_and_has_no_context_mount_behavior(self):
        profile = self.v1_profile()
        MODULE.validate_profile(profile)
        volumes = [
            "/existing:/workspace/.hermes:rw",
            "/projects:/workspace/projects:ro",
            "/data:/data:ro",
        ]
        updated = self.apply(profile, {"terminal": {"docker_volumes": volumes}})
        self.assertEqual(updated["terminal"]["docker_volumes"], volumes)

    def test_v1_rejects_context_workspace(self):
        profile = self.v1_profile()
        profile["context_workspace"] = copy.deepcopy(self.profile["context_workspace"])
        with self.assertRaisesRegex(ValueError, "unexpected"):
            MODULE.validate_profile(profile)

    def test_v2_requires_context_workspace(self):
        profile = copy.deepcopy(self.profile)
        profile.pop("context_workspace")
        with self.assertRaisesRegex(ValueError, "missing"):
            MODULE.validate_profile(profile)

    def test_schema_version_rejects_boolean_and_unknown_integer(self):
        for value in (True, 3):
            with self.subTest(value=value):
                profile = copy.deepcopy(self.profile)
                profile["schema_version"] = value
                with self.assertRaisesRegex(ValueError, "must be 1 or 2"):
                    MODULE.validate_profile(profile)

    def test_context_workspace_requires_exact_keys(self):
        profile = copy.deepcopy(self.profile)
        profile["context_workspace"]["destination"] = "/workspace"
        with self.assertRaisesRegex(ValueError, "unexpected"):
            MODULE.validate_profile(profile)

    def test_context_workspace_requires_boolean_enabled(self):
        profile = copy.deepcopy(self.profile)
        profile["context_workspace"]["enabled"] = "true"
        with self.assertRaisesRegex(ValueError, "must be a boolean"):
            MODULE.validate_profile(profile)

    def test_context_workspace_rejects_unsafe_host_roots(self):
        invalid = (
            "relative/path",
            "/",
            "//srv/hermes",
            "/srv/hermes/",
            "/srv//hermes",
            "/srv/./hermes",
            "/srv/other/../hermes",
            "/srv/hermes:bad",
            "/srv/hermes\n",
        )
        for host_root in invalid:
            with self.subTest(host_root=host_root):
                profile = copy.deepcopy(self.profile)
                profile["context_workspace"]["host_root"] = host_root
                with self.assertRaisesRegex(ValueError, "host_root"):
                    MODULE.validate_profile(profile)

    def test_context_workspace_rejects_invalid_project_access(self):
        profile = copy.deepcopy(self.profile)
        profile["context_workspace"]["project_access"] = "write"
        with self.assertRaisesRegex(ValueError, "project_access"):
            MODULE.validate_profile(profile)

    def test_unknown_key_is_rejected(self):
        profile = copy.deepcopy(self.profile)
        profile["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "unexpected"):
            MODULE.validate_profile(profile)

    def test_non_https_mcp_is_rejected(self):
        profile = copy.deepcopy(self.profile)
        profile["mcp"]["personal_tools_url"] = "http://example.com/mcp"
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            MODULE.validate_profile(profile)

    def test_duplicate_proxy_host_is_rejected(self):
        profile = copy.deepcopy(self.profile)
        profile["proxy"]["extra_allowed_hosts"].append("github.com")
        with self.assertRaisesRegex(ValueError, "duplicates"):
            MODULE.validate_profile(profile)

    def test_credential_material_is_rejected(self):
        profile = copy.deepcopy(self.profile)
        profile["model"]["default"] = "secret-value"
        with self.assertRaisesRegex(ValueError, "credential material"):
            MODULE.validate_profile(profile)

    def test_profile_is_applied_without_weakening_security_baseline(self):
        profile = copy.deepcopy(self.profile)
        profile["telegram"]["enabled"] = True
        profile["skills"]["write_approval"] = False
        profile["memory"]["write_approval"] = False
        config = {"model": {"api_key": "remove-me"}}
        updated = APPLY_MODULE.apply_profile(
            profile,
            config,
            git_coding_enabled=False,
            mcp_secret_authorized=False,
        )
        self.assertTrue(updated["platforms"]["telegram"]["enabled"])
        self.assertFalse(updated["skills"]["write_approval"])
        self.assertFalse(updated["memory"]["write_approval"])
        self.assertFalse(updated["browser"]["allow_private_urls"])
        self.assertFalse(updated["terminal"]["docker_network"])
        self.assertNotIn("api_key", updated["model"])

    def test_enabled_context_workspace_derives_only_fixed_mounts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_workspace(temporary)
            profile = self.enabled_profile(root, "read-write")
            updated = self.apply(profile)
        volumes = updated["terminal"]["docker_volumes"]
        self.assertEqual(
            volumes,
            [
                f"{root}/.hermes:/workspace/.hermes:ro",
                f"{root}/projects:/workspace/projects:rw",
            ],
        )
        destinations = {
            APPLY_MODULE._docker_volume_destination(volume) for volume in volumes
        }
        self.assertEqual(
            destinations,
            {"/workspace/.hermes", "/workspace/projects"},
        )
        self.assertNotIn("/workspace", destinations)
        self.assertNotIn("/workspace/.context-kit", destinations)
        self.assertNotIn("/run/hermes/credentials", destinations)

    def test_read_only_project_access_is_derived(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_workspace(temporary)
            volumes = self.apply(self.enabled_profile(root))["terminal"][
                "docker_volumes"
            ]
        self.assertEqual(volumes[-1], f"{root}/projects:/workspace/projects:ro")

    def test_context_mounts_replace_conflicts_and_preserve_unrelated_mounts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_workspace(temporary)
            existing = [
                "/old-registry:/workspace/.hermes:rw",
                "/duplicate-registry:/workspace/.hermes:ro",
                "/old-projects:/workspace/projects:ro",
                "/sandbox:/workspace:rw",
                "/data:/data:ro",
                "/lease:/run/hermes/credentials:ro",
            ]
            updated = self.apply(
                self.enabled_profile(root, "read-write"),
                {"terminal": {"docker_volumes": existing}},
            )
        volumes = updated["terminal"]["docker_volumes"]
        self.assertEqual(volumes[:2], ["/sandbox:/workspace:rw", "/data:/data:ro"])
        self.assertEqual(
            volumes[2:],
            [
                f"{root}/.hermes:/workspace/.hermes:ro",
                f"{root}/projects:/workspace/projects:rw",
            ],
        )

    def test_disabled_context_workspace_removes_only_owned_destinations(self):
        existing = [
            "/old-registry:/workspace/.hermes:rw",
            "/old-projects:/workspace/projects:ro",
            "/sandbox:/workspace:rw",
            "/data:/data:ro",
        ]
        updated = self.apply(
            self.profile,
            {"terminal": {"docker_volumes": existing}},
        )
        self.assertEqual(
            updated["terminal"]["docker_volumes"],
            ["/sandbox:/workspace:rw", "/data:/data:ro"],
        )

    def test_context_workspace_application_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_workspace(temporary)
            profile = self.enabled_profile(root)
            config = {"terminal": {"docker_volumes": ["/data:/data:ro"]}}
            first = self.apply(profile, config)
            first_volumes = list(first["terminal"]["docker_volumes"])
            second = self.apply(profile, first)
        self.assertEqual(second["terminal"]["docker_volumes"], first_volumes)

    def test_enabled_context_workspace_requires_existing_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            profile = self.enabled_profile(root)
            with self.assertRaisesRegex(ValueError, "registry.*existing directory"):
                self.apply(profile)

    def test_enabled_context_workspace_rejects_non_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / ".hermes").write_text("not a directory", encoding="utf-8")
            (root / "projects").mkdir()
            profile = self.enabled_profile(root)
            with self.assertRaisesRegex(ValueError, "registry.*directory"):
                self.apply(profile)

    def test_enabled_context_workspace_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            real_root = base / "real"
            real_root.mkdir()
            self.make_workspace(real_root)
            alias = base / "alias"
            alias.symlink_to(real_root, target_is_directory=True)
            profile = self.enabled_profile(real_root)
            profile["context_workspace"]["host_root"] = str(alias)
            with self.assertRaisesRegex(ValueError, "symlinks or aliases"):
                self.apply(profile)

    def test_enabled_context_workspace_rejects_child_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            root = base / "workspace"
            target = base / "registry"
            root.mkdir()
            target.mkdir()
            (root / ".hermes").symlink_to(target, target_is_directory=True)
            (root / "projects").mkdir()
            profile = self.enabled_profile(root)
            with self.assertRaisesRegex(ValueError, "symlinks or aliases"):
                self.apply(profile)

    def test_enabled_context_workspace_rejects_wrong_owner(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_workspace(temporary)
            profile = self.enabled_profile(root)
            with mock.patch.object(
                APPLY_MODULE.os,
                "geteuid",
                return_value=os.stat(root).st_uid + 1,
            ):
                with self.assertRaisesRegex(ValueError, "owned by the runtime user"):
                    self.apply(profile)

    def test_mcp_url_requires_authorized_secret(self):
        profile = copy.deepcopy(self.profile)
        profile["mcp"]["personal_tools_url"] = "https://example.com/mcp"
        with self.assertRaisesRegex(ValueError, "authorized client Secret"):
            APPLY_MODULE.apply_profile(
                profile,
                {},
                git_coding_enabled=False,
                mcp_secret_authorized=False,
            )


if __name__ == "__main__":
    unittest.main()
