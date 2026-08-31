"""CLI regression for malformed active-pointer pre-profile language fallback."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ....core.bucket_pointer import pointer_path
from ....core.i18n._render import clear_output_language_cache, tr
from ....core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ....tests.secure_sql import dev_test_database_password, isolated_profile_storage_root
from ....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _profile_storage_env(*, storage_root: Path, tmp_path: Path) -> dict[str, str]:
    """Build a fresh process environment for the installed CLI entry point."""
    env = os.environ.copy()
    for name in (
        "CADRUMO_ACTIVE_PROFILE",
        "CADRUMO_DATABASE_URL",
        "CADRUMO_LOCAL_STORAGE_ROOT",
        "CADRUMO_OUTPUT_LANGUAGE",
        "CADRUMO_SECRET_PASSPHRASE",
        "CADRUMO_SECRET_STORE_BACKEND",
        "CADRUMO_SECRET_STORE_DIR",
    ):
        env.pop(name, None)
    env.update(
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root),
            "CADRUMO_SECRET_STORE_BACKEND": "auto",
            "CADRUMO_SECRET_STORE_DIR": str(tmp_path / "fallback-store"),
            "CADRUMO_SECRET_PASSPHRASE": dev_test_database_password(),
        },
    )
    return env


def _run_cli(*args: str, storage_root: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """Execute the production entry point in a fresh interpreter."""
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-c",
            "from cadrumo.entrypoints._cli_main import main; main()",
            *args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
        env=_profile_storage_env(storage_root=storage_root, tmp_path=tmp_path),
    )


def test_malformed_active_pointer_error_documents_spanish_pre_profile_fallback(tmp_path: Path) -> None:
    """A malformed active pointer has no trustworthy bucket from which to read Catalan."""

    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        register_cli_profile(
            label="catala",
            facts={
                "taxpayer_type.entity_type": "natural_person",
                "identity.tax_id": "00000000T",
                "identity.name": "Catala",
                "identity.surnames": "Test",
                "activities.description": "Serveis",
                PROFILE_OUTPUT_LANGUAGE_PATH: "ca",
            },
        )
        pointer_path(storage_root).write_text("schema_version = 1\n", encoding="utf-8")
        clear_output_language_cache()
        result = _run_cli("config", "profile", "view", storage_root=storage_root, tmp_path=tmp_path)
        clear_output_language_cache()

    output = result.stdout + result.stderr
    assert result.returncode == 4, output
    assert tr("errors.integrity.integrity_active_profile_pointer", locale="es") in output
    assert tr("errors.integrity.integrity_active_profile_pointer", locale="ca") not in output
    assert "aeat config repair profile" not in output
    assert "Traceback" not in output


def test_malformed_active_pointer_projects_the_canonical_repair_action_to_json(tmp_path: Path) -> None:
    """The process boundary preserves the core observation through the live action resolver."""
    storage_root = tmp_path / "cadrumo-storage"
    storage_root.mkdir(parents=True)
    pointer_file = pointer_path(storage_root)
    pointer_file.write_text("schema_version = 1\n", encoding="utf-8")

    result = _run_cli("--format", "json", "config", "profile", "view", storage_root=storage_root, tmp_path=tmp_path)

    assert result.returncode == 4, result.stderr
    error = json.loads(result.stderr)["error"]
    assert error["context"] == {
        "path": str(pointer_file),
        "pointer_corrupt": "true",
        "root_fallback_refused": "true",
    }
    assert error["action"] == {
        "failed_condition_id": "profile.active.pointer.valid",
        "evidence": [
            {
                "condition_id": "profile.active.pointer.valid",
                "evidence_id": "profile.active.pointer.corruption",
                "provenance": "runtime_observation",
                "values": {
                    "path": str(pointer_file),
                    "pointer_corrupt": True,
                    "root_fallback_refused": True,
                },
            },
        ],
        "action": {
            "action_id": "operator.profile.repair_active_pointer",
            "target_command_key": "config.repair.profile",
            "cli_path": ["config", "repair", "profile"],
        },
        "argument_bindings": [
            {
                "argument_name": "clear_active",
                "status": "resolved",
                "value": True,
                "source": "operator_action.verdict_context",
                "source_key": "clear_active",
                "source_evidence_id": None,
            },
            {
                "argument_name": "yes",
                "status": "missing",
                "value": None,
                "source": None,
                "source_key": None,
                "source_evidence_id": None,
            },
        ],
        "missing_argument_names": ["yes"],
        "conditionality": "requires_arguments",
        "no_recovery_outcome": None,
    }
