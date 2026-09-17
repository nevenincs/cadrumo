"""CLI path for operator-supplied local prior filing observations."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    open_test_profile_session,
    seed_test_profile_record,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority

from ....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile
from ....application.calculations.binding_prefill import resolve_bindings_from_local_store
from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ....domain.calculations.registry.casilla_membership import casillas_by_id
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from ....tests.cli_envelope import unwrap_envelope_notices, unwrap_schema_envelope
from ._m130_source_support import seed_m130_expense_transaction, seed_m130_income_transaction
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LOCAL_OBSERVATION_PROFILE_ID = "24242424-2424-4424-8424-242424242424"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Real active encrypted profile storage for local-observation CLI tests."""

    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_LOCAL_OBSERVATION_PROFILE_ID,
        label="Local observation CLI test",
    ) as profile:
        yield profile


def _seed_natural_person_profile(runtime_profile: TestRuntimeProfile) -> None:
    with bundled_indexed_authority().operation() as operation:
        record = _natural_person_record(runtime_profile, operation=operation)
    seed_test_profile_record(record, root=runtime_profile.storage_root, label="Local observation CLI test")


def _natural_person_record(
    runtime_profile: TestRuntimeProfile,
    *,
    operation: PinnedAuthorityOperation,
) -> UserProfileRecord:
    # The pinned authority supplies the profile schema, so the record validates
    # against the canonical version rather than a copied literal.
    return create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=runtime_profile.bucket_id,
        setup_state=ProfileSetupState.COMPLETE,
        facts=(
            UserProfileFact(path="identity.name", value="Sofia"),
            UserProfileFact(path="identity.surnames", value="Scratch"),
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="activities.description", value="professional services"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="provenance.source", value="manual_cli"),
        ),
    )


def test_observe_local_m100_prior_feeds_m100_and_m130_previous_filing_prefill(
    runtime_profile: TestRuntimeProfile, *, operation: PinnedAuthorityOperation
) -> None:
    """A CLI-recorded local M100/2024 observation resolves Sofia's two prior-filing carries.

    The assertion drives the real CLI command, persists into the real encrypted
    observation store, and then reads through the real previous-filing resolver.
    Expected values are the operator's literal zero observation and the registry
    selectors: M100/2025 reads prior M100 casilla 1391, while M130/1T reads the
    sum of prior M100 casillas 0224/1479/1553/1577.
    """

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "filing-record",
            "observe-local",
            "--reason",
            "synthetic prior-year reconstruction",
            "--modelo",
            "100",
            "--year",
            "2024",
            "--period",
            "0A",
            "--by",
            "sofia-local",
            "--set",
            "1391=0",
            "--set",
            "0224=0",
            "--set",
            "1479=0",
            "--set",
            "1553=0",
            "--set",
            "1577=0",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    envelope = json.loads(result.output)
    assert envelope["status"] == "warning"
    payload = unwrap_schema_envelope(result.output)
    assert payload["operation"] == "modelo.filing_record.observe_local"
    assert payload["action"] == "recorded"
    assert payload["reason"] == "synthetic prior-year reconstruction"
    assert payload["observation_key"] == "100:2024:0A"
    assert payload["observation_layers"]["official"] is None
    assert payload["observation_layers"]["pending_local"]["source_kind"] == "operator_manual"
    assert payload["observation_layers"]["effective_source_kind"] == "operator_manual"
    assert payload["source_kind"] == "operator_manual"
    assert payload["official_evidence"] is False
    assert payload["filing_record_created"] is False
    assert payload["aeat_accepted"] is False
    assert payload["casilla_values"] == {
        "0224": "0",
        "1391": "0",
        "1479": "0",
        "1553": "0",
        "1577": "0",
    }
    notices = unwrap_envelope_notices(result.output)
    assert [notice["code"] for notice in notices] == ["modelo.filing_record.observe_local.non_official"]

    with open_test_profile_session(runtime_profile.bucket_id):
        repository = CalculationObservationRepository()
        observed = repository.load_observation("100", Period.from_year_and_code(2024, "0A"))
        assert observed is not None
        assert observed.source_kind == "operator_manual"
        assert observed.stamped_revision_id == "2024"
        assert observed.source_metadata["official_evidence"] == "false"
        assert observed.source_metadata["filing_record_created"] == "false"
        assert observed.source_metadata["captured_by"] == "sofia-local"
        assert observed.observation.casilla_values["1391"] == Decimal("0")

        m100_snapshot = published_snapshot("100", filing_year=2025, period="0A")
        m100_prefill = resolve_bindings_from_local_store(
            m100_snapshot,
            repository=repository,
            iva_history_repository=IvaCompensationHistoryRepository(),
            operation=operation,
        )
        assert m100_prefill.binding_values["renta-base-liquidable-negativa-general-anterior"] == Decimal("0")

        m130_snapshot = published_snapshot("130", filing_year=2025, period="1T")
        m130_prefill = resolve_bindings_from_local_store(
            m130_snapshot,
            repository=repository,
            iva_history_repository=IvaCompensationHistoryRepository(),
            operation=operation,
        )
        assert m130_prefill.binding_values["irpf.previous_year_economic_activity_net_income"] == Decimal("0")

    _seed_natural_person_profile(runtime_profile)
    created = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "130",
            "--year",
            "2025",
            "--period",
            "1T",
            "--revision",
            "2019-y-siguientes",
        ],
    )
    assert created.exit_code == 0, created.output
    work_unit_id = unwrap_schema_envelope(created.output)["work_unit_id"]
    seed_m130_income_transaction(amount=Decimal("6000.00"), filing_year=2025, source_key="local-observation")
    seed_m130_expense_transaction(amount=Decimal("2000.00"), filing_year=2025, source_key="local-observation")

    calculated = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            work_unit_id,
            "--casilla",
            "05=0.00",
            "--casilla",
            "06=0.00",
            "--binding",
            "modelo-130-resultados-negativos-anteriores=0",
        ],
    )
    assert calculated.exit_code == 0, calculated.output
    assert "irpf.previous_year_economic_activity_net_income' expected one observed filing" not in calculated.output
    calculated_payload = unwrap_schema_envelope(calculated.output)
    previous_income = calculated_payload["binding_overrides"]["irpf.previous_year_economic_activity_net_income"]
    assert Decimal(previous_income) == Decimal("0")
    assert Decimal(calculated_payload["casilla_values"]["13"]) == Decimal("100.00")


def _observe_local(*arguments: str) -> dict[str, Any]:
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "filing-record",
            "observe-local",
            "--modelo",
            "130",
            "--year",
            "2025",
            "--period",
            "1T",
            "--by",
            "operator-override",
            *arguments,
        ],
    )
    assert result.exit_code == 0, result.output
    return unwrap_schema_envelope(result.output)


def test_observe_local_overrides_official_evidence_with_audit_and_clear_restores_it(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """An override sits above the official layer with its audit; ``--clear`` restores the official value."""
    period = Period.from_year_and_code(2025, "1T")
    casilla_id = validated_casilla_id("01")
    revision = published_snapshot("130", filing_year=2025, period=period.registry_token).revision
    declared = casillas_by_id(revision)[casilla_id]
    with open_test_profile_session(runtime_profile.bucket_id):
        repository = CalculationObservationRepository()
        repository.save(
            repository.prepare_observation_envelope(
                RegistryModeloObservation(
                    modelo="130",
                    filing_year=2025,
                    period=period.registry_token,
                    observations=(
                        CasillaObservation(
                            casilla_id=casilla_id,
                            value=Decimal("1000.00"),
                            legal_refs=declared.legal_refs,
                            source_refs=declared.source_refs,
                        ),
                    ),
                ),
                source_kind="aeat_sede_justificante",
                captured_at=datetime(2025, 4, 18, 9, 30, tzinfo=UTC),
                stamped_revision_id=str(revision.id),
                source_metadata={"aeat_register_status": "ALTA", "aeat_expediente_id": "202513000000001Z"},
            ),
        )

    overridden = _observe_local("--reason", "receipt mistyped the income", "--set", "01=1100.00")

    assert overridden["action"] == "recorded"
    layers = overridden["observation_layers"]
    assert layers["official"]["source_kind"] == "aeat_sede_justificante"
    assert layers["official"]["casilla_values"] == {"01": "1000.00"}
    assert layers["pending_local"]["casilla_values"] == {"01": "1100.00"}
    assert layers["effective_source_kind"] == "operator_manual"
    assert layers["override"]["actor"] == "operator-override"
    assert layers["override"]["reason"] == "receipt mistyped the income"
    assert layers["override"]["replaced_source_kind"] == "aeat_sede_justificante"
    assert layers["override"]["replaced_values"] == {"01": "1000.00"}
    with open_test_profile_session(runtime_profile.bucket_id):
        effective = CalculationObservationRepository().load_observation("130", period)
        assert effective is not None
        assert effective.source_kind == "operator_manual"
        assert effective.observation.casilla_values["01"] == Decimal("1100.00")

    cleared = _observe_local("--reason", "receipt confirmed correct", "--clear")

    assert cleared["action"] == "cleared"
    assert cleared["casilla_values"] == {}
    assert cleared["observation_layers"]["pending_local"] is None
    assert cleared["observation_layers"]["override"] is None
    assert cleared["observation_layers"]["effective_source_kind"] == "aeat_sede_justificante"
    with open_test_profile_session(runtime_profile.bucket_id):
        restored = CalculationObservationRepository().load_observation("130", period)
        assert restored is not None
        assert restored.source_kind == "aeat_sede_justificante"
        assert restored.observation.casilla_values["01"] == Decimal("1000.00")


def test_observe_local_refuses_values_with_clear_and_a_missing_reason(runtime_profile: TestRuntimeProfile) -> None:
    """``--clear`` takes no values and every mode requires ``--reason``."""
    del runtime_profile
    base = ["--format", "json", "app", "modelo", "filing-record", "observe-local"]
    target = ["--modelo", "130", "--year", "2025", "--period", "1T"]

    with_values = invoke_cached_cli([*base, *target, "--reason", "r", "--clear", "--set", "01=1.00"])
    without_reason = invoke_cached_cli([*base, *target, "--set", "01=1.00"])

    assert with_values.exit_code != 0
    assert "--clear" in with_values.output
    assert without_reason.exit_code != 0
    assert "--reason" in without_reason.output
