from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path

import telepdf.config as config


class ConfigPathsTest(unittest.TestCase):
    def test_default_data_dir_uses_user_home(self) -> None:
        self.assertEqual(config.DATA_DIR.name, ".telepdf")
        self.assertTrue(str(config.DATA_DIR).startswith(str(Path.home())))

    def test_env_override_is_honored_on_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            previous = os.environ.get("TELEPDF_HOME")
            os.environ["TELEPDF_HOME"] = tmpdir
            try:
                reloaded = importlib.reload(config)
                self.assertEqual(reloaded.DATA_DIR, Path(tmpdir))
            finally:
                if previous is None:
                    os.environ.pop("TELEPDF_HOME", None)
                else:
                    os.environ["TELEPDF_HOME"] = previous
                importlib.reload(config)


class ConfigPersistenceTest(unittest.TestCase):
    def test_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original_data_dir = config.DATA_DIR
            original_config_path = config.CONFIG_PATH
            original_auth_state_path = config.AUTH_STATE_PATH
            try:
                config.DATA_DIR = Path(tmpdir)
                config.CONFIG_PATH = config.DATA_DIR / "config.json"
                config.AUTH_STATE_PATH = config.DATA_DIR / "auth_state.json"

                payload = config.StoredConfig(api_id="12345", api_hash="hash", phone="+96500000000")
                config.save_config(payload)
                loaded = config.load_config()

                self.assertEqual(loaded.api_id, "12345")
                self.assertEqual(loaded.api_hash, "hash")
                self.assertEqual(loaded.phone, "+96500000000")

                config.save_auth_state({"phone_code_hash": "abc"})
                self.assertEqual(config.load_auth_state()["phone_code_hash"], "abc")
                config.clear_auth_state()
                self.assertEqual(config.load_auth_state(), {})
            finally:
                config.DATA_DIR = original_data_dir
                config.CONFIG_PATH = original_config_path
                config.AUTH_STATE_PATH = original_auth_state_path


if __name__ == "__main__":
    unittest.main()
