from __future__ import annotations

import unittest
from unittest.mock import patch

from telethon.sessions import StringSession

from telepdf.telegram_service import JobState, TelepdfArchiver


class TelepdfArchiverStopTest(unittest.TestCase):
    def test_stop_download_marks_running_job_as_stopping(self) -> None:
        with patch.object(TelepdfArchiver, "refresh_authorized_state", return_value=False):
            archiver = TelepdfArchiver()

        archiver._job = JobState(status="running", source="example", output_dir="/tmp/out")
        result = archiver.stop_download()

        self.assertEqual(result["message"], "تم طلب إيقاف المهمة. سيجري الإيقاف بعد إنهاء الملف الحالي.")
        self.assertEqual(archiver._job.status, "stopping")
        self.assertTrue(archiver._stop_requested.is_set())

    def test_stop_download_rejects_when_no_job_is_running(self) -> None:
        with patch.object(TelepdfArchiver, "refresh_authorized_state", return_value=False):
            archiver = TelepdfArchiver()

        with self.assertRaisesRegex(ValueError, "لا توجد مهمة تنزيل قيد التشغيل لإيقافها"):
            archiver.stop_download()

    def test_finish_job_clears_stop_request(self) -> None:
        with patch.object(TelepdfArchiver, "refresh_authorized_state", return_value=False):
            archiver = TelepdfArchiver()

        archiver._stop_requested.set()
        archiver._finish_job(status="stopped")

        self.assertEqual(archiver._job.status, "stopped")
        self.assertFalse(archiver._stop_requested.is_set())
        self.assertTrue(archiver._job.finished_at)

    def test_logout_clears_local_session(self) -> None:
        with patch.object(TelepdfArchiver, "refresh_authorized_state", return_value=False), patch(
            "telepdf.telegram_service.clear_auth_state"
        ) as clear_auth, patch("telepdf.telegram_service.clear_session_string") as clear_session, patch(
            "telepdf.telegram_service.clear_legacy_session_files"
        ) as clear_legacy:
            archiver = TelepdfArchiver()

            result = archiver.logout()

        self.assertEqual(result["message"], "تم تسجيل الخروج وحذف الجلسة المحلية.")
        clear_auth.assert_called_once()
        clear_session.assert_called_once()
        clear_legacy.assert_called_once()

    def test_clear_local_storage_calls_cleanup(self) -> None:
        with patch.object(TelepdfArchiver, "refresh_authorized_state", return_value=False), patch(
            "telepdf.telegram_service.clear_local_data"
        ) as clear_local:
            archiver = TelepdfArchiver()

            result = archiver.clear_local_storage()

        self.assertEqual(result["message"], "تم حذف بيانات التطبيق المحلية. ملفات PDF المحفوظة لم يتم لمسها.")
        clear_local.assert_called_once()

    def test_persist_session_only_deletes_legacy_files_after_confirmed_secure_save(self) -> None:
        saved_value = {"session": ""}

        def fake_save(value: str) -> None:
            saved_value["session"] = value

        def fake_load() -> str:
            return saved_value["session"]

        with patch.object(TelepdfArchiver, "refresh_authorized_state", return_value=False), patch(
            "telepdf.telegram_service.save_session_string"
        , side_effect=fake_save) as save_session, patch(
            "telepdf.telegram_service.load_session_string",
            side_effect=fake_load,
        ), patch(
            "telepdf.telegram_service.clear_legacy_session_files"
        ) as clear_legacy:
            archiver = TelepdfArchiver()

            class LegacySession:
                dc_id = 2
                server_address = "149.154.167.51"
                port = 443
                auth_key = type("AuthKey", (), {"key": b"x" * 256})()

            client = type("Client", (), {"session": LegacySession()})()

            archiver._persist_session(client)

        save_session.assert_called_once()
        clear_legacy.assert_called_once()

    def test_persist_session_keeps_legacy_files_if_secure_store_cannot_read_back_session(self) -> None:
        with patch.object(TelepdfArchiver, "refresh_authorized_state", return_value=False), patch(
            "telepdf.telegram_service.save_session_string"
        ) as save_session, patch("telepdf.telegram_service.load_session_string", return_value=""), patch(
            "telepdf.telegram_service.clear_legacy_session_files"
        ) as clear_legacy:
            archiver = TelepdfArchiver()

            class LegacySession:
                dc_id = 2
                server_address = "149.154.167.51"
                port = 443
                auth_key = type("AuthKey", (), {"key": b"x" * 256})()

            client = type("Client", (), {"session": LegacySession()})()

            archiver._persist_session(client)

        save_session.assert_called_once()
        clear_legacy.assert_not_called()

    def test_persist_session_saves_string_session_directly(self) -> None:
        with patch.object(TelepdfArchiver, "refresh_authorized_state", return_value=False), patch(
            "telepdf.telegram_service.save_session_string"
        ) as save_session:
            archiver = TelepdfArchiver()
            session = StringSession()
            session.set_dc(2, "149.154.167.51", 443)
            session.auth_key = type("AuthKey", (), {"key": b"x" * 256})()
            client = type("Client", (), {"session": session})()

            archiver._persist_session(client)

        save_session.assert_called_once()


if __name__ == "__main__":
    unittest.main()
