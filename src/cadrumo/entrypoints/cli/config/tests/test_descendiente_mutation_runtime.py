"""Installed descendant CLI mutation through the verified profile worker."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from .....adapters.persistence.profile.tests.profile_registration import register_cli_profile
from .....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from .....core.config import load_settings
from .....tests.cli_envelope import unwrap_envelope_notices, unwrap_schema_envelope
from ...tests.cli_runner import invoke_cached_cli
from .isolated_storage_fixture import native_profile_view_server, profile_persisted_facts

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.serial,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]


def _descendant_cli(*args: str, label: str, passphrase: str):
    return invoke_cached_cli(
        ("--format", "json", "--profile", label, "--profile-secrets-stdin", "config", "profile", "descendiente", *args),
        input=json.dumps({"profile_passphrase": passphrase}),
    )


def test_add_and_remove_preserve_envelope_notice_and_reindexed_encrypted_facts(tmp_path: Path) -> None:
    """Both verbs reach one exact encrypted profile and retain their CLI shape."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        register_cli_profile(label="Descendant operator", log_in=False)
        passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()
        with native_profile_view_server(root):
            added = _descendant_cli(
                "add",
                "--descendiente",
                "NACIMIENTO=2015-04-01",
                "--descendiente",
                "NACIMIENTO=2021-04-15,GASTOS_GUARDERIA_MENSUAL=1-4:150;5-7:200,MESES_TRABAJO=1-12,SEGUNDO_CICLO_INFANTIL_INICIO_MES=8",
                label="Descendant operator",
                passphrase=passphrase,
            )
            assert added.exit_code == 0, added.output
            assert unwrap_schema_envelope(added.output) == {
                "profile": "Descendant operator",
                "added": 2,
                "total": 2,
            }
            notice = [
                item
                for item in unwrap_envelope_notices(added.output)
                if item["code"] == "config.profile.descendiente.ambiguous_relacion"
            ]
            assert len(notice) == 1
            assert notice[0]["context"] == {"indices": "1"}

            invalid = _descendant_cli(
                "add", "--descendiente", "DISCAPACIDAD=50", label="Descendant operator", passphrase=passphrase
            )
            assert invalid.exit_code == 2, invalid.output
            assert "NACIMIENTO" in invalid.output

            missing = _descendant_cli("remove", "5", label="Descendant operator", passphrase=passphrase)
            assert missing.exit_code == 2, missing.output

            removed = _descendant_cli("remove", "0", label="Descendant operator", passphrase=passphrase)
            assert removed.exit_code == 0, removed.output
            assert unwrap_schema_envelope(removed.output) == {
                "profile": "Descendant operator",
                "removed_index": 0,
                "total": 1,
            }
            listed = _descendant_cli("list", label="Descendant operator", passphrase=passphrase)
            assert listed.exit_code == 0, listed.output
            rows = unwrap_schema_envelope(listed.output)["descendientes"]
            assert [row["birth_date"] for row in rows] == ["2021-04-15"]
            assert rows[0]["meses_madre_trabajo"] == list(range(1, 13))

        facts = profile_persisted_facts()
        assert facts["renta_family.descendientes_count"] == "1"
        assert facts["renta_family.descendiente.0.birth_date"] == "2021-04-15"
        assert not any(path.startswith("renta_family.descendiente.1.") for path in facts)
