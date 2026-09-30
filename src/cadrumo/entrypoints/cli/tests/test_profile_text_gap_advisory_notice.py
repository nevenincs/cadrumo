"""A profile left without an identity fact reaches the operator as a valid notice.

A required Modelo 100 text casilla that reads the declarant's profile stays
empty when the profile does not declare the fact, and the calculation advises
which profile fields would fill it. That advisory travels through the notice
contract, which refuses executable command prose outside ``Notice.action``: an
advisory whose remedy named the command broke the whole calculate call instead
of warning.

These tests drive ``app modelo work calculate`` through the real CLI against an
isolated real-session backend and the published registry. Nothing is mocked.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile
from ....core.json_contract import Notice
from ....domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ....tests.cli_envelope import require_schema_envelope, unwrap_envelope_notices
from .cli_runner import invoke_cached_cli
from .modelo_cli import create_modelo_work_unit_via_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_PROFILE_ID = "5b7d2e40-0000-4000-8000-00000000a7c1"
_LABEL = "Profile text gap advisory test profile"
_CODE = "modelo.work.calculate.source_advisory"
_DECLARANTE_NAME = "DP_APENOM_D"
_MARITAL_STATUS = "ECIVIL"
_DECLARATION_TYPE = "TIPOTRIBUTACION"
_CALCULATE_FLAGS: tuple[str, ...] = (
    "--casilla", "0003=24000",
    "--binding", "renta-certificado-trabajo-retenciones=2400",
    "--binding", "renta-base-liquidable-negativa-general-anterior=0",
)  # fmt: skip


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID, label=_LABEL) as profile:
        yield profile


def _seed_salaried_profile(runtime_profile: TestRuntimeProfile, *identity: UserProfileFact) -> None:
    """Seed a salaried natural person whose Renta codes are stored as the CLI stores them.

    The marital-status and declaration-type answers are digit codes, which the
    profile keeps as numbers; they must still fill their text casillas.
    """
    record = create_user_profile_record(
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=(
            *identity,
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="trabajo"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="activities.description", value="salaried employment"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="renta_taxpayer.birth_date", value="1985-06-15"),
            UserProfileFact(path="renta_taxpayer.sex", value="H"),
            UserProfileFact(path="renta_taxpayer.marital_status", value=Decimal("1")),
            UserProfileFact(path="renta_filing.declaration_type", value=Decimal("1")),
        ),
        context=profile_creation_context_for_test(),
    )
    seed_test_profile_record(record, root=runtime_profile.storage_root, label=_LABEL)


def _calculate_m100_2025() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    work_unit_id = create_modelo_work_unit_via_cli(modelo="100", filing_year=2025, period="0A", revision="2025")
    result = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "calculate", work_unit_id, *_CALCULATE_FLAGS]
    )
    assert result.exit_code == 0, result.output
    return require_schema_envelope(result.output), unwrap_envelope_notices(result.output)


def _profile_gap_notices(notices: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The profile text-gap advisories, keyed by the casilla each speaks about."""
    return {
        notice["context"]["casilla_id"]: notice
        for notice in notices
        if notice["code"] == _CODE
        and notice["context"].get("source_kind") == "profile"
        and notice["context"].get("reason") == "unresolved_binding"
    }


def test_an_undeclared_name_reaches_the_operator_as_a_valid_advisory_notice(
    runtime_profile: TestRuntimeProfile,
) -> None:
    _seed_salaried_profile(runtime_profile)

    payload, notices = _calculate_m100_2025()

    assert _DECLARANTE_NAME not in payload["input_values_by_casilla_id"]
    advisory = _profile_gap_notices(notices)[_DECLARANTE_NAME]
    # The emitted document satisfies the contract a consumer validates against.
    notice = Notice.model_validate_json(Notice.model_validate(advisory, strict=False).model_dump_json())
    assert notice.action is None
    assert notice.context is not None
    assert notice.context["binding_id"] == "renta-profile-display-name"
    remedy = notice.context["remedy"]
    assert "identity.surnames" in remedy
    assert "identity.name" in remedy
    assert notice.context["legal_refs"]


def test_a_declared_profile_raises_no_gap_advisory(runtime_profile: TestRuntimeProfile) -> None:
    """The negative control: the same calculation over a complete identity advises nothing.

    The digit-coded marital status and declaration type are declared too, so the
    casillas they fill are held and never reported as undeclared.
    """
    _seed_salaried_profile(
        runtime_profile,
        UserProfileFact(path="identity.name", value="Ana"),
        UserProfileFact(path="identity.surnames", value="Perez Gil"),
    )

    payload, notices = _calculate_m100_2025()

    held = payload["input_values_by_casilla_id"]
    assert held[_DECLARANTE_NAME] == "Perez Gil Ana"
    assert held[_MARITAL_STATUS] == "1"
    assert held[_DECLARATION_TYPE] == "1"
    assert _profile_gap_notices(notices) == {}
