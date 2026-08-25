"""Parity tests: aeat config profile create/show/status read one profile bucket.

Pins the contract that ``aeat config profile create``, ``aeat config
profile show`` and ``aeat config profile status`` share the active
profile bucket selected by ``WorkflowState``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ...tests.cli_runner import invoke_cached_cli
from ...tests.profile_capsule import open_test_profile_session
from ...tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_config_create_then_config_show_round_trips_iva_regime(
    tmp_path: Path,
) -> None:
    """A value written during profile create is readable via profile show."""

    with isolated_profile_storage_root(tmp_path=tmp_path):
        created = invoke_cached_cli(
            [
                "config",
                "profile",
                "create",
                "default",
                "--quiet",
                "--tax-id",
                "00000000T",
                "--entity-type",
                "natural_person",
                "--name",
                "Operator",
                "--surnames",
                "Example",
                "--activity",
                "design",
                "--iva-regime",
                "GENERAL",
            ],
        )
        assert created.exit_code == 0, created.output

        show_via_config = invoke_cached_cli(["--format", "json", "config", "profile", "show", "default"])
        assert show_via_config.exit_code == 0, show_via_config.output
        _show_payload = json.loads(show_via_config.output)
        assert isinstance(_show_payload, dict)
        assert "schema_version" in _show_payload and "result" in _show_payload
        _facts_payload = _show_payload["result"]
        facts = {row["path"]: row["value"] for row in _facts_payload["facts"]}
        assert facts["iva.regime"] == "GENERAL"

        from ...tests.profile_capsule import load_test_profile_record
        from ..user_profile.projections import fact_value
        from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket

        # The bucket directory is named by the minted UUID; resolve it
        # from the operator label "default" carried in the manifest.
        pointer = read_profile_bucket("default")
        assert pointer is not None
        with open_test_profile_session(pointer.bucket_id):
            record = load_test_profile_record(pointer.bucket_id)
            assert fact_value(record, "iva.regime") == "GENERAL"


def test_config_create_then_config_status_surfaces_assigned_value(
    tmp_path: Path,
) -> None:
    """A value written during profile create surfaces in profile status."""

    with isolated_profile_storage_root(tmp_path=tmp_path):
        created = invoke_cached_cli(
            [
                "config",
                "profile",
                "create",
                "default",
                "--quiet",
                "--tax-id",
                "00000000T",
                "--entity-type",
                "natural_person",
                "--name",
                "Operator",
                "--surnames",
                "Example",
                "--activity",
                "design",
                "--iva-regime",
                "SIMPLIFICADO",
            ],
        )
        assert created.exit_code == 0, created.output

        status_result = invoke_cached_cli(["config", "profile", "status"])
        assert status_result.exit_code == 0, status_result.output
        assert "SIMPLIFICADO" in status_result.output


def test_retired_config_profile_set_is_not_registered(
    tmp_path: Path,
) -> None:
    """The retired point-mutation command must not re-enter the CLI tree."""

    with isolated_profile_storage_root(tmp_path=tmp_path):
        result = invoke_cached_cli(["config", "profile", "set", "not.a.real.key", "value"])
        assert result.exit_code != 0
        assert "No such command" in result.output
