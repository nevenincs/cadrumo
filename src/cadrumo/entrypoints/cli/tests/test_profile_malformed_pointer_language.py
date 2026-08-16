"""CLI regression for malformed active-pointer pre-profile language fallback."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core import pointer_path
from ....core.i18n import clear_output_language_cache, tr
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import dev_test_database_password
from ....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _profile_storage_env(tmp_path: Path) -> dict[str, str | None]:
    return {
        "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "cadrumo-storage"),
        "CADRUMO_SECRET_STORE_BACKEND": "file",
        "CADRUMO_SECRET_STORE_DIR": str(tmp_path / "fallback-store"),
        "CADRUMO_SECRET_PASSPHRASE": dev_test_database_password(),
        "CADRUMO_ACTIVE_PROFILE": None,
        "CADRUMO_DATABASE_URL": None,
        "CADRUMO_OUTPUT_LANGUAGE": None,
    }


def test_malformed_active_pointer_error_documents_spanish_pre_profile_fallback(tmp_path: Path) -> None:
    """A malformed active pointer has no trustworthy bucket from which to read Catalan."""

    env = _profile_storage_env(tmp_path)
    storage_root = Path(env["CADRUMO_LOCAL_STORAGE_ROOT"] or "")

    register_cli_profile(
        label="catala",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.tax_id": "00000000T",
            "identity.name": "Catala",
            "identity.surnames": "Test",
            "activities.description": "Serveis",
            "preferences.output_language": "ca",
        },
    )

    pointer_path(storage_root).write_text("schema_version = 1\n", encoding="utf-8")
    clear_output_language_cache()
    result = invoke_cached_cli(("config", "profile", "show"), env=env)
    clear_output_language_cache()

    assert result.exit_code == 4, result.output
    assert tr("errors.integrity.integrity_active_profile_pointer", locale="es") in result.output
    assert tr("errors.integrity.integrity_active_profile_pointer", locale="ca") not in result.output
    assert "aeat config repair profile" not in result.output
    assert "Traceback" not in result.output
