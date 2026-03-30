from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MULTISPACE = re.compile(r"\s+")


def normalize_source_identifier(source: str) -> str:
    value = (source or "").strip()
    value = value.removeprefix("https://")
    value = value.removeprefix("http://")
    value = value.removeprefix("t.me/")
    value = value.removeprefix("www.t.me/")
    if value.startswith("s/"):
        value = value[2:]
    value = value.strip("/")
    if value.startswith("@"):
        value = value[1:]
    return value


def safe_filename(name: str, replacement: str = "_") -> str:
    candidate = (name or "").strip()
    candidate = INVALID_FILENAME_CHARS.sub(replacement, candidate)
    candidate = MULTISPACE.sub(" ", candidate).strip(" .")
    return candidate or "document"


def build_saved_filename(message_date: datetime, message_id: int, original_name: str) -> str:
    original_path = Path(original_name or "document.pdf")
    suffix = original_path.suffix.lower() or ".pdf"
    stem = safe_filename(original_path.stem)
    stamp = message_date.strftime("%Y%m%d")
    return f"{stamp}_{message_id}_{stem}{suffix}"


def source_key(source_identifier: str) -> str:
    return normalize_source_identifier(source_identifier).lower()


def message_link(username: Optional[str], message_id: int) -> str:
    if not username:
        return ""
    return f"https://t.me/{username}/{message_id}"


class DownloadLedger:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"entries": {}}
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(self._data, handle, ensure_ascii=False, indent=2)

    def _entry_key(self, source: str, output_dir: str, message_id: int) -> str:
        return f"{source_key(source)}::{Path(output_dir).expanduser().resolve()}::{message_id}"

    def get(self, source: str, output_dir: str, message_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._data["entries"].get(self._entry_key(source, output_dir, message_id))

    def upsert(self, source: str, output_dir: str, message_id: int, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._data["entries"][self._entry_key(source, output_dir, message_id)] = payload
            self._save()

    def list_for_output(self, source: str, output_dir: str) -> List[Dict[str, Any]]:
        resolved_output = str(Path(output_dir).expanduser().resolve())
        key_prefix = f"{source_key(source)}::{resolved_output}::"
        with self._lock:
            items = [
                item
                for key, item in self._data["entries"].items()
                if key.startswith(key_prefix)
            ]
        return sorted(items, key=lambda item: (item.get("message_date", ""), item.get("message_id", 0)))
