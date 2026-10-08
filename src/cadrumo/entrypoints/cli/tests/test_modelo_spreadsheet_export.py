"""Native-worker calculation-workbook export through the live ``aeat`` parser."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.storage.calc_sheets.records import TabName
from ....core.config import override_settings
from ....tests.cli_envelope import require_error_document, unwrap_schema_envelope
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]


def _export(profile: NativeCliProfileFixture, output: Path, *extra: str) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        result = invoke_cached_cli(
            (
                "--language",
                "en",
                "--format",
                "json",
                "--profile",
                profile.label,
                "--profile-secrets-stdin",
                "app",
                "modelo",
                "spreadsheet",
                "export",
                "--modelo",
                "303",
                "--year",
                "2025",
                "--period",
                "1T",
                "--output",
                str(output),
                *extra,
            ),
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )
    assert profile.passphrase not in result.output
    return result


def test_the_workbook_lands_at_the_chosen_path_described_by_the_facts_of_its_bytes(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-spreadsheet-export", facts={})
        export_directory = tmp_path / "exports"
        export_directory.mkdir()
        output = export_directory / "modelo-303-2025-1T.xlsx"

        result = _export(profile, output)

        assert result.exit_code == 0, result.output
        payload = unwrap_schema_envelope(result.output)
        landed = output.read_bytes()
        assert payload["output_path"] == str(output)
        assert payload["byte_size"] == len(landed)
        assert payload["sha256"] == hashlib.sha256(landed).hexdigest()
        assert (payload["modelo"], payload["period"], payload["year"]) == ("303", "1T", 2025)
        assert payload["tab_names"] == [tab.value for tab in TabName]
        assert payload["casilla_count"] > 0
        with zipfile.ZipFile(output) as workbook:
            assert "xl/workbook.xml" in workbook.namelist()
        assert [path.name for path in export_directory.iterdir()] == [output.name]


def test_an_existing_file_is_refused_untouched_and_replaced_only_on_explicit_choice(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-spreadsheet-export-existing", facts={})
        export_directory = tmp_path / "exports"
        export_directory.mkdir()
        output = export_directory / "modelo-303-2025-1T.xlsx"
        output.write_bytes(b"an earlier export")

        refused = _export(profile, output)

        assert refused.exit_code != 0
        assert "existing file" in str(require_error_document(refused.output)["error"]["message"])
        assert output.read_bytes() == b"an earlier export"
        assert [path.name for path in export_directory.iterdir()] == [output.name]

        replaced = _export(profile, output, "--replace")

        assert replaced.exit_code == 0, replaced.output
        assert zipfile.is_zipfile(output)
        assert unwrap_schema_envelope(replaced.output)["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()


def test_a_missing_parent_directory_is_refused_before_any_file_is_written(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-spreadsheet-export-missing-parent", facts={})
        output = tmp_path / "absent" / "modelo-303-2025-1T.xlsx"

        refused = _export(profile, output)

        assert refused.exit_code != 0
        assert "parent directory does not exist" in str(require_error_document(refused.output)["error"]["message"])
        assert not output.exists()
        assert not output.parent.exists()
