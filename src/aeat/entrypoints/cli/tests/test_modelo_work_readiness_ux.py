"""Modelo work profile-readiness UX tests."""

from __future__ import annotations

import json

import pytest

from ....core import Modelo
from ._modelo_work_ux_support import (
    _PROFILE_ID,
    _attempt_incomplete_profile_create,
    _create_de_nonresident_legal_entity_profile,
    _create_profile,
    _invoke,
)
from ._modelo_work_ux_support import _isolated_cli_backend as _isolated_cli_backend
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_profile_create_refuses_incomplete_profile_before_modelo_work() -> None:
    """Incomplete profiles must fail before a modelo work unit can exist."""
    from ....application.workflow._profile_bucket_scan import read_profile_bucket

    result = _attempt_incomplete_profile_create()

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "REFUSED_WIZARD_MISSING_FLAG"
    assert payload["error"]["category"] == "REFUSED"
    message = payload["error"]["message"]
    assert "--entity-type" in message
    assert "--name" in message
    assert "--surnames" in message
    assert read_profile_bucket(_PROFILE_ID) is None
    assert "work_unit_id" not in result.output
    assert "Traceback" not in result.output


def test_work_create_refuses_status_blocked_profile_missing_activity() -> None:
    create = _invoke(
        [
            "--format", "json",
            "config", "profile", "create", _PROFILE_ID,
            "--quiet", "--accept-defaults",
            "--entity-type", "natural_person",
            "--irpf-income-categories", "actividad_economica",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--surnames", "Readiness",
        ],
    )  # fmt: skip
    assert create.exit_code == 0, create.output

    status = _invoke(["--format", "json", "config", "profile", "status"])
    assert status.exit_code == 0, status.output
    status_payload = _payload(status.output)
    assert status_payload["configured"] is False
    assert status_payload["activity_present"] is False

    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", Modelo.M130.value,
            "--year", "2025",
            "--period", "1T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "REFUSED_MODELO_PROFILE_READINESS"
    assert "activities.description" in payload["error"]["message"]
    assert "work_unit_id" not in result.output
    assert "Traceback" not in result.output

    listed = _invoke(["--format", "json", "app", "modelo", "work", "list"])
    assert listed.exit_code == 0, listed.output
    assert _payload(listed.output)["work_unit_count"] == 0


def test_work_create_refuses_pre_activity_m303_and_creates_no_unit() -> None:
    _create_profile(activity_start_date="2026-05-01")

    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "303",
            "--year", "2026",
            "--period", "1T",
        ],
    )  # fmt: skip

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "REFUSED_MODELO_PROFILE_READINESS"
    message = payload["error"]["message"]
    assert "pre-activity period" in message
    assert "2026-05-01" in message
    assert "2026-03-31" in message
    assert "Traceback" not in result.output

    listed = _invoke(["--format", "json", "app", "modelo", "work", "list"])
    assert listed.exit_code == 0, listed.output
    assert _payload(listed.output)["work_unit_count"] == 0


def test_modelo_readiness_reports_pre_activity_m303_before_work_create() -> None:
    _create_profile(activity_start_date="2026-05-01")

    result = _invoke(
        [
            "app", "modelo", "readiness",
            "--modelo", "303",
            "--revision-id", "2023-y-siguientes",
            "--year", "2026",
            "--period", "1T",
        ],
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert "ready\tFalse" in result.output
    assert "profile_ready\tFalse" in result.output
    assert "profile_refusal\tModelo 303 2026 1T is before the profile activity-start date 2026-05-01" in result.output
    assert "filing period ends on 2026-03-31" in result.output
    assert "pre-activity period" in result.output

    listed = _invoke(["--format", "json", "app", "modelo", "work", "list"])
    assert listed.exit_code == 0, listed.output
    assert _payload(listed.output)["work_unit_count"] == 0


def test_nonresident_legal_entity_m200_readiness_and_create_refuse_wrong_path() -> None:
    _create_de_nonresident_legal_entity_profile()

    readiness = _invoke(
        [
            "--format", "json",
            "app", "modelo", "readiness",
            "--modelo", "200",
            "--revision-id", "2024-y-siguientes",
            "--year", "2026",
            "--period", "0A",
        ],
    )  # fmt: skip

    assert readiness.exit_code == 0, readiness.output
    readiness_payload = _payload(readiness.output)
    assert readiness_payload["ready"] is False
    assert readiness_payload["profile_ready"] is False
    assert readiness_payload["profile_refusal"]
    assert "NON_RESIDENT_IRNR" in readiness_payload["profile_refusal"]
    assert "establecimiento permanente" in readiness_payload["profile_refusal"]

    create = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "200",
            "--year", "2026",
            "--period", "0A",
            "--revision", "2024-y-siguientes",
        ],
    )  # fmt: skip

    assert create.exit_code != 0, create.output
    create_payload = json.loads(create.output)
    assert create_payload["status"] == "error"
    assert create_payload["error"]["code"] == "REFUSED_CLI_BOUNDARY"
    assert "NON_RESIDENT_IRNR" in create_payload["error"]["message"]
    assert "establecimiento permanente" in create_payload["error"]["message"]

    bypass = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "200",
            "--year", "2026",
            "--period", "0A",
            "--revision", "2024-y-siguientes",
            "--allow-not-applicable",
        ],
    )  # fmt: skip

    assert bypass.exit_code != 0, bypass.output
    bypass_payload = json.loads(bypass.output)
    assert bypass_payload["status"] == "error"
    assert bypass_payload["error"]["code"] == "REFUSED_MODELO_PROFILE_READINESS"
    assert "NON_RESIDENT_IRNR" in bypass_payload["error"]["message"]

    listed = _invoke(["--format", "json", "app", "modelo", "work", "list"])
    assert listed.exit_code == 0, listed.output
    assert _payload(listed.output)["work_unit_count"] == 0


def test_work_create_refuses_pre_activity_m130_and_creates_no_unit() -> None:
    _create_profile(activity_start_date="2026-07-15")

    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", Modelo.M130.value,
            "--year", "2026",
            "--period", "2T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "REFUSED_MODELO_PROFILE_READINESS"
    message = payload["error"]["message"]
    assert f"Modelo {Modelo.M130.value} 2026 2T is before" in message
    assert "pre-activity period" in message
    assert "2026-07-15" in message
    assert "2026-06-30" in message
    assert "Traceback" not in result.output

    listed = _invoke(["--format", "json", "app", "modelo", "work", "list"])
    assert listed.exit_code == 0, listed.output
    assert _payload(listed.output)["work_unit_count"] == 0
