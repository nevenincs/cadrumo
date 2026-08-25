"""CLI ratchet for unauthorized-but-computable modelo calculate advisories.

See Also:
    :func:`~entrypoints.cli._modelo_work_calculate_cli._work_calculate_authorization_output`
        CLI projection that turns the unauthorized-backend advisory into text
        lines, JSON payload state, and a warning notice.
    :func:`~application.modelo.authorization_advisory_for_modelo`
        Application derivation that emits an advisory only for unauthorized
        modelos with a local calculation engine.
    :class:`~core.access_gate.ModeloAuthorization`
        Derived authorization capability queried by the test before driving
        the real Modelo 117 work-calculate flow.
    :func:`~tests.cli_envelope.unwrap_envelope_notices`
        Envelope helper used to assert the advisory travels on the uniform
        notices channel.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.access_gate import AuthorizationState
from ....core.resources import resources
from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.cli_envelope import unwrap_envelope_notices, unwrap_schema_envelope
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "0ac1e000-0000-4000-8000-000000000117"
_MODELO = "117"
_REVISION = "2019-y-siguientes"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Real active bucket runtime for the unauthorized-backend CLI ratchet."""

    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="Unauthorized backend advisory profile",
    ) as profile:
        yield profile


def _store_capital_withholding_profile(runtime_profile: TestRuntimeProfile) -> None:
    record = UserProfileRecord(
        schema_id="cadrumo.user_profile",
        # Sourced from the schema, never pinned: a literal goes stale the moment
        # the profile schema is revised, and the record then refuses to validate
        # against its own canonical version.
        schema_version=load_user_profile_schema().version,
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=(
            UserProfileFact(path="identity.name", value="Advisory Operator"),
            UserProfileFact(path="identity.surnames", value="Calculation"),
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="withholding.pays_capital_income_with_retencion", value=True),
            UserProfileFact(path="activities.description", value="capital withholding payer"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="provenance.source", value="manual_cli"),
        ),
    )
    seed_test_profile_record(record, root=runtime_profile.storage_root, label="Unauthorized backend advisory profile")


def _create_modelo_117_work_unit() -> str:
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", _MODELO, "--year", "2026", "--period", "1T",
            "--revision", _REVISION,
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = unwrap_schema_envelope(result.output)
    assert payload["status"] == "created"
    assert payload["applicability_guard_bypassed"] is False
    work_unit_id = payload["work_unit_id"]
    assert isinstance(work_unit_id, str)
    return work_unit_id


def _calculate_args(work_unit_id: str) -> list[str]:
    return [
        "app",
        "modelo",
        "work",
        "calculate",
        work_unit_id,
        "--casilla",
        "03=190.00",
        "--casilla",
        "06=0.00",
        "--casilla",
        "08=0.00",
        "--casilla",
        "10=0.00",
        "--output-language",
        "en",
    ]


def test_work_calculate_warns_but_computes_unauthorized_modelo_117(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """A real unauthorized modelo with an engine computes and emits the advisory."""

    capability = resources().modelos.authority.authorization(_MODELO)
    assert capability.state is AuthorizationState.UNAUTHORIZED
    assert capability.has_engine is True

    _store_capital_withholding_profile(runtime_profile)
    work_unit_id = _create_modelo_117_work_unit()

    text_result = invoke_cached_cli(_calculate_args(work_unit_id))
    assert text_result.exit_code == 0, text_result.output
    assert "Traceback" not in text_result.output
    assert "authorization_state\tunauthorized" in text_result.output
    assert "calculation backend is UNAUTHORIZED" in text_result.output
    assert "computed and saved" in text_result.output
    assert "casilla\t11\t190.00" in text_result.output

    json_result = invoke_cached_cli(["--format", "json", *_calculate_args(work_unit_id)])
    assert json_result.exit_code == 0, json_result.output
    payload = unwrap_schema_envelope(json_result.output)
    notices = unwrap_envelope_notices(json_result.output)
    advisory = next(notice for notice in notices if notice["code"] == "modelo.work.calculate.unauthorized_backend")

    assert payload["saved"] is True
    assert payload["casilla_values"]["11"] == "190.00"
    assert payload["authorization_state"] == "unauthorized"
    assert advisory["severity"] == "warning"
    assert advisory["context"] == {"authorization_state": "unauthorized"}
    assert "calculation backend is UNAUTHORIZED" in advisory["message"]
