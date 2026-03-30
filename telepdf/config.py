from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = Path(os.environ.get("TELEPDF_HOME", str(Path.home() / ".telepdf"))).expanduser()
CONFIG_PATH = DATA_DIR / "config.json"
AUTH_STATE_PATH = DATA_DIR / "auth_state.json"
LEDGER_PATH = DATA_DIR / "ledger.json"
LEGACY_SESSION_PATH = DATA_DIR / "telegram_user"
SECURE_STORE_SERVICE = "telepdf"
API_HASH_SECRET = "telegram_api_hash"
SESSION_SECRET = "telegram_session_string"


@dataclass
class StoredConfig:
    api_id: str = ""
    api_hash: str = ""
    phone: str = ""


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return default.copy()
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    ensure_data_dir()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _load_keyring():
    try:
        import keyring
    except ImportError as exc:  # pragma: no cover - dependency is required in runtime
        raise ValueError("التخزين الآمن غير متاح حالياً. ثبّت keyring ثم أعد المحاولة.") from exc
    return keyring


def _get_secret(name: str) -> str:
    try:
        keyring = _load_keyring()
        return keyring.get_password(SECURE_STORE_SERVICE, name) or ""
    except Exception:
        return ""


def _set_secret(name: str, value: str) -> None:
    try:
        keyring = _load_keyring()
        keyring.set_password(SECURE_STORE_SERVICE, name, value)
    except Exception as exc:
        raise ValueError("تعذر الوصول إلى التخزين الآمن للنظام لحفظ البيانات الحساسة.") from exc


def _delete_secret(name: str) -> None:
    try:
        keyring = _load_keyring()
        keyring.delete_password(SECURE_STORE_SERVICE, name)
    except Exception:
        return


def _config_payload() -> Dict[str, Any]:
    payload = _read_json(CONFIG_PATH, default={"api_id": "", "phone": ""})
    legacy_api_hash = str(payload.get("api_hash", "") or "")
    if legacy_api_hash and not _get_secret(API_HASH_SECRET):
        _set_secret(API_HASH_SECRET, legacy_api_hash)
    if "api_hash" in payload and _get_secret(API_HASH_SECRET):
        payload.pop("api_hash", None)
        _write_json(CONFIG_PATH, payload)
    return payload


def load_config() -> StoredConfig:
    payload = _config_payload()
    return StoredConfig(
        api_id=str(payload.get("api_id", "")),
        api_hash=_get_secret(API_HASH_SECRET),
        phone=str(payload.get("phone", "")),
    )


def save_config(config: StoredConfig) -> None:
    _set_secret(API_HASH_SECRET, config.api_hash)
    _write_json(
        CONFIG_PATH,
        {
            "api_id": config.api_id,
            "phone": config.phone,
        },
    )


def clear_config() -> None:
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()
    _delete_secret(API_HASH_SECRET)


def load_auth_state() -> Dict[str, Any]:
    return _read_json(AUTH_STATE_PATH, default={})


def save_auth_state(payload: Dict[str, Any]) -> None:
    _write_json(AUTH_STATE_PATH, payload)


def clear_auth_state() -> None:
    if AUTH_STATE_PATH.exists():
        AUTH_STATE_PATH.unlink()


def load_session_string() -> str:
    return _get_secret(SESSION_SECRET)


def save_session_string(session_string: str) -> None:
    if session_string:
        _set_secret(SESSION_SECRET, session_string)


def clear_session_string() -> None:
    _delete_secret(SESSION_SECRET)


def _legacy_session_files() -> list[Path]:
    return [
        LEGACY_SESSION_PATH.with_suffix(".session"),
        LEGACY_SESSION_PATH.with_suffix(".session-journal"),
    ]


def legacy_session_exists() -> bool:
    return any(path.exists() for path in _legacy_session_files())


def clear_legacy_session_files() -> None:
    for path in _legacy_session_files():
        if path.exists():
            path.unlink()


def clear_ledger() -> None:
    if LEDGER_PATH.exists():
        LEDGER_PATH.unlink()


def clear_local_data() -> None:
    clear_auth_state()
    clear_config()
    clear_session_string()
    clear_legacy_session_files()
    clear_ledger()
