from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = Path(os.environ.get("TELEPDF_HOME", str(Path.home() / ".telepdf"))).expanduser()
CONFIG_PATH = DATA_DIR / "config.json"
AUTH_STATE_PATH = DATA_DIR / "auth_state.json"
LEDGER_PATH = DATA_DIR / "ledger.json"
SESSION_PATH = DATA_DIR / "telegram_user"


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


def load_config() -> StoredConfig:
    payload = _read_json(CONFIG_PATH, default=asdict(StoredConfig()))
    return StoredConfig(
        api_id=str(payload.get("api_id", "")),
        api_hash=str(payload.get("api_hash", "")),
        phone=str(payload.get("phone", "")),
    )


def save_config(config: StoredConfig) -> None:
    _write_json(CONFIG_PATH, asdict(config))


def load_auth_state() -> Dict[str, Any]:
    return _read_json(AUTH_STATE_PATH, default={})


def save_auth_state(payload: Dict[str, Any]) -> None:
    _write_json(AUTH_STATE_PATH, payload)


def clear_auth_state() -> None:
    if AUTH_STATE_PATH.exists():
        AUTH_STATE_PATH.unlink()
