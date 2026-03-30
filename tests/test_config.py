from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
    def test_save_and_load_roundtrip_uses_secure_store_for_api_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original_data_dir = config.DATA_DIR
            original_config_path = config.CONFIG_PATH
            original_auth_state_path = config.AUTH_STATE_PATH
            secrets: dict[str, str] = {}
            try:
                config.DATA_DIR = Path(tmpdir)
                config.CONFIG_PATH = config.DATA_DIR / "config.json"
                config.AUTH_STATE_PATH = config.DATA_DIR / "auth_state.json"

                with patch.object(config, "_set_secret", side_effect=lambda name, value: secrets.__setitem__(name, value)):
                    payload = config.StoredConfig(api_id="12345", api_hash="hash", phone="+96500000000")
                    config.save_config(payload)

                with patch.object(config, "_get_secret", side_effect=lambda name: secrets.get(name, "")):
                    loaded = config.load_config()

                self.assertEqual(loaded.api_id, "12345")
                self.assertEqual(loaded.api_hash, "hash")
                self.assertEqual(loaded.phone, "+96500000000")

                saved_json = config._read_json(config.CONFIG_PATH, {})
                self.assertEqual(saved_json, {"api_id": "12345", "phone": "+96500000000"})

                config.save_auth_state({"phone_code_hash": "abc"})
                self.assertEqual(config.load_auth_state()["phone_code_hash"], "abc")
                config.clear_auth_state()
                self.assertEqual(config.load_auth_state(), {})
            finally:
                config.DATA_DIR = original_data_dir
                config.CONFIG_PATH = original_config_path
                config.AUTH_STATE_PATH = original_auth_state_path

    def test_legacy_plaintext_api_hash_is_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original_data_dir = config.DATA_DIR
            original_config_path = config.CONFIG_PATH
            try:
                config.DATA_DIR = Path(tmpdir)
                config.CONFIG_PATH = config.DATA_DIR / "config.json"
                config._write_json(
                    config.CONFIG_PATH,
                    {
                        "api_id": "99",
                        "api_hash": "legacy-secret",
                        "phone": "+96511111111",
                    },
                )

                saved_secrets: dict[str, str] = {}
                with patch.object(config, "_get_secret", side_effect=lambda name: saved_secrets.get(name, "")), patch.object(
                    config,
                    "_set_secret",
                    side_effect=lambda name, value: saved_secrets.__setitem__(name, value),
                ):
                    loaded = config.load_config()

                self.assertEqual(loaded.api_hash, "legacy-secret")
                self.assertEqual(saved_secrets[config.API_HASH_SECRET], "legacy-secret")
                self.assertNotIn("api_hash", config._read_json(config.CONFIG_PATH, {}))
            finally:
                config.DATA_DIR = original_data_dir
                config.CONFIG_PATH = original_config_path

    def test_plaintext_api_hash_is_kept_if_secure_store_cannot_confirm_migration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original_data_dir = config.DATA_DIR
            original_config_path = config.CONFIG_PATH
            try:
                config.DATA_DIR = Path(tmpdir)
                config.CONFIG_PATH = config.DATA_DIR / "config.json"
                config._write_json(
                    config.CONFIG_PATH,
                    {
                        "api_id": "99",
                        "api_hash": "legacy-secret",
                        "phone": "+96511111111",
                    },
                )

                saved_secrets: dict[str, str] = {}

                def fake_get_secret(name: str) -> str:
                    return ""

                with patch.object(config, "_get_secret", side_effect=fake_get_secret), patch.object(
                    config,
                    "_set_secret",
                    side_effect=lambda name, value: saved_secrets.__setitem__(name, value),
                ):
                    loaded = config.load_config()

                self.assertEqual(loaded.api_hash, "")
                self.assertEqual(saved_secrets[config.API_HASH_SECRET], "legacy-secret")
                self.assertEqual(config._read_json(config.CONFIG_PATH, {})["api_hash"], "legacy-secret")
            finally:
                config.DATA_DIR = original_data_dir
                config.CONFIG_PATH = original_config_path

    def test_clear_local_data_removes_config_ledger_and_session_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original_data_dir = config.DATA_DIR
            original_config_path = config.CONFIG_PATH
            original_auth_state_path = config.AUTH_STATE_PATH
            original_ledger_path = config.LEDGER_PATH
            original_legacy_session_path = config.LEGACY_SESSION_PATH
            deleted: list[str] = []
            try:
                config.DATA_DIR = Path(tmpdir)
                config.CONFIG_PATH = config.DATA_DIR / "config.json"
                config.AUTH_STATE_PATH = config.DATA_DIR / "auth_state.json"
                config.LEDGER_PATH = config.DATA_DIR / "ledger.json"
                config.LEGACY_SESSION_PATH = config.DATA_DIR / "telegram_user"

                config._write_json(config.CONFIG_PATH, {"api_id": "1", "phone": "+965"})
                config._write_json(config.AUTH_STATE_PATH, {"phone_code_hash": "abc"})
                config._write_json(config.LEDGER_PATH, {"entries": {}})
                config.LEGACY_SESSION_PATH.with_suffix(".session").write_text("legacy", encoding="utf-8")

                with patch.object(config, "_delete_secret", side_effect=lambda name: deleted.append(name)):
                    config.clear_local_data()

                self.assertFalse(config.CONFIG_PATH.exists())
                self.assertFalse(config.AUTH_STATE_PATH.exists())
                self.assertFalse(config.LEDGER_PATH.exists())
                self.assertFalse(config.LEGACY_SESSION_PATH.with_suffix(".session").exists())
                self.assertIn(config.API_HASH_SECRET, deleted)
                self.assertIn(config.SESSION_SECRET, deleted)
            finally:
                config.DATA_DIR = original_data_dir
                config.CONFIG_PATH = original_config_path
                config.AUTH_STATE_PATH = original_auth_state_path
                config.LEDGER_PATH = original_ledger_path
                config.LEGACY_SESSION_PATH = original_legacy_session_path


if __name__ == "__main__":
    unittest.main()
