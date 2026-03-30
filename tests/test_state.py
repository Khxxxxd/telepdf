from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from telepdf.state import DownloadLedger, build_saved_filename, normalize_source_identifier, safe_filename


class StateHelpersTest(unittest.TestCase):
    def test_normalize_source_identifier(self) -> None:
        self.assertEqual(normalize_source_identifier("https://t.me/s/KuwaitLaws"), "KuwaitLaws")
        self.assertEqual(normalize_source_identifier("@KuwaitLaws"), "KuwaitLaws")

    def test_safe_filename_and_saved_name(self) -> None:
        name = safe_filename('law: 12/2024 ? draft ')
        self.assertEqual(name, "law_ 12_2024 _ draft")
        saved = build_saved_filename(datetime(2025, 1, 4), 88, "مرسوم: خاص.pdf")
        self.assertEqual(saved, "20250104_88_مرسوم_ خاص.pdf")


class DownloadLedgerTest(unittest.TestCase):
    def test_upsert_and_list_for_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = DownloadLedger(Path(tmpdir) / "ledger.json")
            ledger.upsert(
                source="ExampleSource",
                output_dir=tmpdir,
                message_id=10,
                payload={
                    "source": "ExampleSource",
                    "message_id": 10,
                    "message_date": "2025-01-02T00:00:00",
                    "saved_filename": "file.pdf",
                    "saved_path": str(Path(tmpdir) / "file.pdf"),
                },
            )
            rows = ledger.list_for_output("examplesource", tmpdir)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["message_id"], 10)


if __name__ == "__main__":
    unittest.main()
