"""Modelo work profile-readiness UX tests."""

from __future__ import annotations

import json

import pytest

from ....core import Modelo
from ....core.config import override_settings
from ....core.resources import resources
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.profile_capsule import open_test_profile_session
from ....tests.user_profile import register_cli_profile
from ._modelo_work_ux_support import (
    _PROFILE_ID,
    _create_attribution_entity_intracom_profile,
    _create_de_nonresident_legal_entity_profile,
    _create_gb_non_resident_profile,
    _create_profile,
    _invoke,
)
from ._modelo_work_ux_support import _isolated_cli_backend as _isolated_cli_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_REPRESENTANTE_PROFILE_PATHS = frozenset(
    {
        "taxpayer_type.representante_fiscal_nif",
        "taxpayer_type.representante_fiscal_nombre",
    },
)


def _remove_representante_fields_from_operator_profile() -> None:
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket
    from ....tests.profile_capsule import load_test_profile_record, replace_test_profile_record

    pointer = read_profile_bucket(_PROFILE_ID)
    assert pointer is not None
    with open_test_profile_session(pointer.bucket_id):
        record = load_test_profile_record(pointer.bucket_id)
        replace_test_profile_record(
            record.model_copy(
                update={
                    "facts": tuple(fact for fact in record.facts if fact.path not in _REPRESENTANTE_PROFILE_PATHS),
                },
            ),
        )


def test_work_create_refuses_status_blocked_profile_missing_activity() -> None:
    register_cli_profile(
        label=_PROFILE_ID,
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "identity.tax_id": "12345678Z",
            "identity.name": "Operator",
            "identity.surnames": "Readiness",
        },
    )

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
    assert "Activity description" in payload["error"]["message"]
    assert "work_unit_id" not in result.output
    assert "Traceback" not in result.output

    listed = _invoke(["--format", "json", "app", "modelo", "work", "list"])
    assert listed.exit_code == 0, listed.output
    assert _payload(listed.output)["work_unit_count"] == 0


def test_incomplete_setup_readiness_matches_work_create_and_names_completion_door() -> None:
    """Fact-complete is not operator-declared complete on either surface."""
    register_cli_profile(label="issue-113-incomplete", complete=False)

    readiness = _invoke(
        [
            "--format", "json",
            "app", "modelo", "readiness",
            "--modelo", Modelo.M130.value,
            "--revision-id", "2019-y-siguientes",
            "--year", "2026",
            "--period", "2T",
        ],
    )  # fmt: skip
    assert readiness.exit_code == 0, readiness.output
    readiness_payload = _payload(readiness.output)
    assert readiness_payload["profile_ready"] is False
    assert readiness_payload["ready"] is False
    assert "aeat config profile complete-setup" in readiness_payload["profile_refusal"]

    create = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", Modelo.M130.value,
            "--year", "2026",
            "--period", "2T",
        ],
    )  # fmt: skip
    assert create.exit_code != 0
    error = json.loads(create.output)["error"]
    assert error["code"] == "REFUSED_MODELO_PROFILE_READINESS"
    assert "aeat config profile complete-setup" in error["message"]

    completed = _invoke(["--format", "json", "config", "profile", "complete-setup"])
    assert completed.exit_code == 0, completed.output

    after = _invoke(
        [
            "--format", "json",
            "app", "modelo", "readiness",
            "--modelo", Modelo.M130.value,
            "--revision-id", "2019-y-siguientes",
            "--year", "2026",
            "--period", "2T",
        ],
    )  # fmt: skip
    assert after.exit_code == 0, after.output
    assert _payload(after.output)["profile_ready"] is True


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
            "--revision-id", str(resources().modelos.authority.snapshot("303", filing_year=2026, period="1T").revision.id),
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


def test_m210_engine_live_work_create_refuses_legacy_non_eea_irnr_missing_representante() -> None:
    _create_gb_non_resident_profile()
    _remove_representante_fields_from_operator_profile()

    with override_settings(cadrumo_m210_engine_live=True):
        result = _invoke(
            [
                "--format", "json",
                "app", "modelo", "work", "create",
                "--modelo", "210",
                "--year", "2025",
                "--period", "EVENT-1",
                "--revision", "2025",
            ],
        )  # fmt: skip

    assert result.exit_code != 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "REFUSED_MODELO_PROFILE_READINESS"
    message = payload["error"]["message"]
    assert "Fiscal representative NIF" in message
    assert "Fiscal representative name" in message
    assert "trlirnr-rdleg-5-2004:art-10" in message
    assert "REFUSED_CLI_VALIDATION_BOUNDARY" not in result.output
    assert "Traceback" not in result.output

    listed = _invoke(["--format", "json", "app", "modelo", "work", "list"])
    assert listed.exit_code == 0, listed.output
    assert _payload(listed.output)["work_unit_count"] == 0


def test_work_create_not_applicable_m130_wins_over_pre_activity_for_irnr_profile() -> None:
    register_cli_profile(
        label=_PROFILE_ID,
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "irpf.estimation_regime": "directa_normal",
            "identity.tax_id": "X1234567L",
            "identity.name": "Non Resident",
            "identity.surnames": "Readiness",
            "activities.description": "design",
            "taxpayer_type.fiscal_residency": "non_resident_irnr",
            "taxpayer_type.country_of_fiscal_residence": "FR",
            "censo.activity_start_date": "2026-07-15",
        },
    )

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

    assert result.exit_code != 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    error = payload["error"]
    assert error["code"] == "REFUSED_CLI_BOUNDARY"
    message = error["message"]
    assert Modelo.M130.value in message
    assert "NON_RESIDENT_IRNR" in message
    assert "--allow-not-applicable" in message
    assert "REFUSED_MODELO_PROFILE_READINESS" not in result.output
    assert "pre-activity period" not in result.output
    assert "Traceback" not in result.output

    listed = _invoke(["--format", "json", "app", "modelo", "work", "list"])
    assert listed.exit_code == 0, listed.output
    assert _payload(listed.output)["work_unit_count"] == 0


def test_modelo_349_readiness_allows_attribution_entity_before_work_create() -> None:
    """Modelo 349 applicability was widened to include attribution entities.

    An attribution entity that trades intracommunity is a legitimate M349
    filer (RD 1624/1992 art. 79), so the profile gate must pass; readiness
    still withholds ``ready`` until the invoice-source bindings are present,
    and ``work create`` must succeed rather than refuse.
    """
    _create_attribution_entity_intracom_profile()

    readiness = _invoke(
        [
            "--format", "json",
            "app", "modelo", "readiness",
            "--modelo", "349",
            "--revision-id", "2020-y-siguientes",
            "--year", "2026",
            "--period", "1T",
        ],
    )  # fmt: skip

    assert readiness.exit_code == 0, readiness.output
    readiness_payload = _payload(readiness.output)
    assert readiness_payload["registry_ready"] is True
    assert readiness_payload["profile_ready"] is True
    assert readiness_payload["profile_refusal"] == ""
    assert readiness_payload["ready"] is False
    assert readiness_payload["binding_ready"] is False
    assert readiness_payload["missing_bindings"]

    create = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "349",
            "--year", "2026",
            "--period", "1T",
            "--revision", "2020-y-siguientes",
        ],
    )  # fmt: skip

    assert create.exit_code == 0, create.output
    create_payload = _payload(create.output)
    assert create_payload["status"] == "created"
    assert create_payload["modelo"] == "349"

    listed = _invoke(["--format", "json", "app", "modelo", "work", "list"])
    assert listed.exit_code == 0, listed.output
    assert _payload(listed.output)["work_unit_count"] == 1


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

    assert bypass.exit_code == 0, bypass.output
    bypass_payload = _payload(bypass.output)
    assert bypass_payload["status"] == "created"
    assert bypass_payload["modelo"] == "200"
    assert bypass_payload["applicability_guard_bypassed"] is True

    listed = _invoke(["--format", "json", "app", "modelo", "work", "list"])
    assert listed.exit_code == 0, listed.output
    assert _payload(listed.output)["work_unit_count"] == 1


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
