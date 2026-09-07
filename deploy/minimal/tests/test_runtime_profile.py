import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


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
