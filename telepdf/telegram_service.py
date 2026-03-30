from __future__ import annotations

import asyncio
import csv
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from telethon import TelegramClient
from telethon.errors import PhoneCodeExpiredError, PhoneCodeInvalidError, SessionPasswordNeededError

from .config import (
    LEDGER_PATH,
    SESSION_PATH,
    StoredConfig,
    clear_auth_state,
    load_auth_state,
    load_config,
    save_auth_state,
    save_config,
)
from .state import DownloadLedger, build_saved_filename, message_link, normalize_source_identifier


@dataclass
class JobState:
    status: str = "idle"
    source: str = ""
    output_dir: str = ""
    scanned_messages: int = 0
    discovered_pdfs: int = 0
    downloaded_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    last_file: str = ""
    error: str = ""
    started_at: str = ""
    finished_at: str = ""


class TelepdfArchiver:
    def __init__(self) -> None:
        self._ledger = DownloadLedger(LEDGER_PATH)
        self._lock = threading.Lock()
        self._job = JobState()
        self._authorized_cache = False
        self._pending_password = False
        self.refresh_authorized_state()

    def get_status(self) -> Dict[str, Any]:
        config = load_config()
        with self._lock:
            job = self._job.__dict__.copy()
            pending_password = self._pending_password
            authorized = self._authorized_cache
        return {
            "config": {
                "api_id_set": bool(config.api_id),
                "api_hash_set": bool(config.api_hash),
                "phone": config.phone,
            },
            "auth": {
                "authorized": authorized,
                "pending_password": pending_password,
            },
            "job": job,
        }

    def save_config(self, api_id: str, api_hash: str, phone: str) -> Dict[str, Any]:
        config = StoredConfig(api_id=str(api_id).strip(), api_hash=str(api_hash).strip(), phone=str(phone).strip())
        if not config.api_id or not config.api_hash or not config.phone:
            raise ValueError("api_id, api_hash, and phone are required.")
        if not config.api_id.isdigit():
            raise ValueError("api_id must be numeric.")
        save_config(config)
        self.refresh_authorized_state()
        return self.get_status()

    def send_code(self) -> Dict[str, Any]:
        config = self._require_config()
        result = asyncio.run(self._send_code_async(config))
        save_auth_state({"phone": config.phone, "phone_code_hash": result.phone_code_hash})
        with self._lock:
            self._pending_password = False
        return {"message": f"Verification code sent to {config.phone}."}

    async def _send_code_async(self, config: StoredConfig) -> Any:
        client = TelegramClient(str(SESSION_PATH), int(config.api_id), config.api_hash)
        await client.connect()
        try:
            return await client.send_code_request(config.phone)
        finally:
            await client.disconnect()

    def verify_code(self, code: str, password: str = "") -> Dict[str, Any]:
        config = self._require_config()
        auth_state = load_auth_state()
        phone_code_hash = auth_state.get("phone_code_hash", "")
        if not phone_code_hash:
            raise ValueError("No pending login was found. Send the code first.")
        try:
            asyncio.run(self._verify_code_async(config, str(code).strip(), phone_code_hash, str(password).strip()))
        except SessionPasswordNeededError:
            with self._lock:
                self._pending_password = True
            raise ValueError("Telegram 2FA password is required.")
        except PhoneCodeInvalidError as exc:
            raise ValueError("The Telegram login code is invalid.") from exc
        except PhoneCodeExpiredError as exc:
            raise ValueError("The Telegram login code has expired. Send a new code.") from exc
        clear_auth_state()
        self.refresh_authorized_state()
        return {"message": "Telegram login completed successfully."}

    async def _verify_code_async(
        self,
        config: StoredConfig,
        code: str,
        phone_code_hash: str,
        password: str,
    ) -> None:
        client = TelegramClient(str(SESSION_PATH), int(config.api_id), config.api_hash)
        await client.connect()
        try:
            try:
                await client.sign_in(phone=config.phone, code=code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                if not password:
                    raise
                await client.sign_in(password=password)
        finally:
            await client.disconnect()

    def refresh_authorized_state(self) -> bool:
        config = load_config()
        authorized = False
        if config.api_id and config.api_hash:
            try:
                authorized = asyncio.run(self._is_authorized_async(config))
            except Exception:
                authorized = False
        with self._lock:
            self._authorized_cache = authorized
            if authorized:
                self._pending_password = False
        return authorized

    async def _is_authorized_async(self, config: StoredConfig) -> bool:
        client = TelegramClient(str(SESSION_PATH), int(config.api_id), config.api_hash)
        await client.connect()
        try:
            return await client.is_user_authorized()
        finally:
            await client.disconnect()

    def start_download(self, source_identifier: str, output_dir: str) -> Dict[str, Any]:
        source = normalize_source_identifier(source_identifier)
        if not source:
            raise ValueError("A Telegram source is required.")
        target_dir = Path(output_dir or "").expanduser()
        if not str(target_dir).strip():
            raise ValueError("An output directory is required.")
        if not self.refresh_authorized_state():
            raise ValueError("Telegram is not authorized yet. Complete login first.")

        with self._lock:
            if self._job.status == "running":
                raise ValueError("Another download job is already running.")
            self._job = JobState(
                status="running",
                source=source,
                output_dir=str(target_dir.resolve()),
                started_at=datetime.now(timezone.utc).isoformat(),
            )

        thread = threading.Thread(
            target=self._run_download_job_sync,
            args=(source, str(target_dir.resolve())),
            daemon=True,
        )
        thread.start()
        return {"message": "Download job started."}

    def _run_download_job_sync(self, source_identifier: str, output_dir: str) -> None:
        try:
            asyncio.run(self._download_job_async(source_identifier, output_dir))
        except Exception as exc:
            self._finish_job(status="failed", error=str(exc))

    async def _download_job_async(self, source_identifier: str, output_dir: str) -> None:
        config = self._require_config()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        client = TelegramClient(str(SESSION_PATH), int(config.api_id), config.api_hash)
        await client.connect()
        try:
            entity = await client.get_entity(source_identifier)
            username = getattr(entity, "username", "") or normalize_source_identifier(source_identifier)

            async for message in client.iter_messages(entity, reverse=True):
                self._bump_job(scanned_messages=1)
                if not self._message_is_pdf(message):
                    continue

                self._bump_job(discovered_pdfs=1)
                existing = self._ledger.get(source_identifier, output_dir, message.id)
                saved_path = existing.get("saved_path", "") if existing else ""
                if existing and saved_path and Path(saved_path).exists():
                    self._bump_job(skipped_count=1, last_file=existing.get("saved_filename", ""))
                    continue

                original_name = self._original_filename(message)
                saved_filename = build_saved_filename(message.date, message.id, original_name)
                target_path = self._ensure_unique_path(output_path / saved_filename)

                saved_file = await message.download_media(file=str(target_path))
                if not saved_file:
                    self._bump_job(failed_count=1, last_file=saved_filename)
                    continue

                document_id = getattr(message.document, "id", None)
                record = {
                    "source": source_identifier,
                    "source_username": username,
                    "message_id": message.id,
                    "document_id": str(document_id or ""),
                    "message_date": message.date.isoformat(),
                    "original_filename": original_name,
                    "saved_filename": Path(saved_file).name,
                    "saved_path": str(Path(saved_file).resolve()),
                    "mime_type": getattr(message.file, "mime_type", ""),
                    "telegram_link": message_link(username, message.id),
                    "output_dir": str(output_path.resolve()),
                }
                self._ledger.upsert(source_identifier, output_dir, message.id, record)
                self._bump_job(downloaded_count=1, last_file=Path(saved_file).name)
        finally:
            await client.disconnect()

        self._write_csv_snapshot(source_identifier, output_dir)
        self._finish_job(status="completed")

    def _write_csv_snapshot(self, source_identifier: str, output_dir: str) -> None:
        rows = self._ledger.list_for_output(source_identifier, output_dir)
        csv_path = Path(output_dir) / "telegram_pdf_index.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "message_id",
                    "document_id",
                    "message_date",
                    "source",
                    "source_username",
                    "original_filename",
                    "saved_filename",
                    "saved_path",
                    "mime_type",
                    "telegram_link",
                    "output_dir",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def _ensure_unique_path(self, target_path: Path) -> Path:
        if not target_path.exists():
            return target_path
        stem = target_path.stem
        suffix = target_path.suffix
        counter = 1
        while True:
            candidate = target_path.with_name(f"{stem}_{counter}{suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def _original_filename(self, message: Any) -> str:
        filename = getattr(message.file, "name", "")
        if filename:
            return filename
        return f"document_{message.id}.pdf"

    def _message_is_pdf(self, message: Any) -> bool:
        if not getattr(message, "document", None):
            return False
        mime_type = (getattr(message.file, "mime_type", "") or "").lower()
        file_name = (getattr(message.file, "name", "") or "").lower()
        return mime_type == "application/pdf" or file_name.endswith(".pdf")

    def _require_config(self) -> StoredConfig:
        config = load_config()
        if not config.api_id or not config.api_hash or not config.phone:
            raise ValueError("Save api_id, api_hash, and phone first.")
        return config

    def _bump_job(self, **increments: Any) -> None:
        with self._lock:
            for key, value in increments.items():
                current = getattr(self._job, key)
                if isinstance(current, int):
                    setattr(self._job, key, current + int(value))
                else:
                    setattr(self._job, key, value)

    def _finish_job(self, status: str, error: str = "") -> None:
        with self._lock:
            self._job.status = status
            self._job.error = error
            self._job.finished_at = datetime.now(timezone.utc).isoformat()
