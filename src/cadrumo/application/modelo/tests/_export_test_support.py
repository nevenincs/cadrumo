"""Shared real-behavior support for modelo export tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....core.identity import nif_check_letter
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.deadlines import (
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloIVAProfile,
    TaxpayerProfile,
)
from ....domain.modelos import ModeloCode, WorkUnit, derive_work_unit_id, upsert_calculation_revision, upsert_work_unit
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    FilingInstanceEvidence,
    derive_calculation_revision_id,
)
from ....tests.filing_evidence import general_m303_filing_evidence
from ....tests.profile_capsule import open_test_profile_session
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...workflow.persistence import workflow_state_repository

_ACTIVE_STORAGE_STACK: ExitStack | None = None
_PROFILE_SPAN_OPEN = False
_M130_INPUT_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INPUT_CASILLA")
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id("03", surface="_M130_RENDIMIENTO_NETO_CASILLA")
_M130_RESULT_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_RESULT_CASILLA")
_M303_RESULT_CASILLA: CasillaId = validated_casilla_id("71", surface="_M303_RESULT_CASILLA")
_SPANISH_IBAN = "ES9121000418450200051332"
_M200_REFUND_RESULT_CASILLA: CasillaId = validated_casilla_id(
    "DP200014B:00599",
    surface="_M200_REFUND_RESULT_CASILLA",
)
_SEEDED_REVISION_AT = datetime(2026, 6, 3, 16, 0, tzinfo=UTC)


def _general_m303_filing_evidence(period: Period) -> FilingInstanceEvidence:
    """Delegate to the one shared typed-evidence fixture builder."""
    return general_m303_filing_evidence(period, reference="test:export:exonerado-not-applicable")


def _casilla_id_from_payload(value: object) -> CasillaId:
    return validated_casilla_id(value, surface="test casilla id")


def _snapshot_ref(*, modelo: str, period: Period, revision_id: str) -> RegistrySnapshotRef:
    return RegistrySnapshotRef(
        modelo=modelo,
        revision_id=revision_id,
        modelo_year=period.filing_year,
        period=period.registry_token,
    )


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="12345678Z",
        iva_regime=IVARegime.GENERAL,
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.COMMON_REGIME,
            regime_composition=M303RegimeComposition.GENERAL,
            redeme_enrolled=False,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
        ),
    )


@contextmanager
def isolated_backend_context(tmp_path: Path) -> Iterator[None]:
    global _ACTIVE_STORAGE_STACK, _PROFILE_SPAN_OPEN

    with ExitStack() as stack:
        stack.enter_context(isolated_profile_storage_root(tmp_path=tmp_path))
        _ACTIVE_STORAGE_STACK = stack
        _PROFILE_SPAN_OPEN = False
        try:
            yield
        finally:
            _PROFILE_SPAN_OPEN = False
            _ACTIVE_STORAGE_STACK = None


@pytest.fixture
def isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_backend_context(tmp_path):
        yield


def _ensure_operator_storage_span() -> None:
    global _PROFILE_SPAN_OPEN

    if _PROFILE_SPAN_OPEN:
        return
    if _ACTIVE_STORAGE_STACK is None:
        raise RuntimeError("modelo export test storage span is not active")
    _ACTIVE_STORAGE_STACK.enter_context(open_test_profile_session("11111111-1111-4111-8111-111111111111"))
    _PROFILE_SPAN_OPEN = True


def _seed_profile(*, tax_id: str | None = None, profile_overrides: dict[str, str] | None = None) -> str:
    _ensure_operator_storage_span()
    overrides = {
        "identity.name": "Test",
        "identity.surnames": "Operator",
        "iva.m303_regime_composition": "general",
        "iva.redeme_enrolled": "false",
        "iva.cash_accounting_regime_enrolled": "false",
        "iva.voluntary_sii_enrolled": "false",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        **dict(profile_overrides or {}),
    }
    if tax_id is not None:
        overrides["identity.tax_id"] = tax_id
    # Seeded through a detached WorkflowState, never a repository read: the
    # capsule publishes by an atomic no-replace rename onto
    # ``buckets/<profile-id>``, which a workflow-state repository
    # construction would otherwise materialise first and collide with.
    register_minimal_profile(profile_id="11111111-1111-4111-8111-111111111111", overrides=overrides or None)
    bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    assert bucket_id is not None
    return bucket_id


def _seed_revision(
    *,
    bucket_id: str,
    state: CalculationRevisionState,
    modelo: str = "130",
    filing_year: int = 2026,
    period: str = "1T",
    input_values_by_casilla_id: dict[CasillaId, str] | None = None,
    binding_overrides: dict[BindingId, str] | None = None,
    casilla_values: dict[CasillaId, Decimal] | None = None,
    filing_instance_evidence: FilingInstanceEvidence | None = None,
) -> tuple[str, str]:
    input_values_by_casilla_id = dict(input_values_by_casilla_id or dict[CasillaId, str]())
    binding_overrides = dict(binding_overrides or dict[BindingId, str]())
    casilla_values = dict(casilla_values or {})
    typed_period = Period.from_year_and_code(filing_year, period)
    snapshot = bundled_authority().snapshot(
        modelo,
        filing_year=filing_year,
        period=typed_period.registry_token,
    )
    revision_id = snapshot.revision.id
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{typed_period.registry_token}",
        created_at=_SEEDED_REVISION_AT,
        updated_at=_SEEDED_REVISION_AT,
    )
    WorkUnitCatalogueRepository().save(
        upsert_work_unit(WorkUnitCatalogueRepository().load(), work_unit),
    )
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=state,
        created_at=_SEEDED_REVISION_AT,
        updated_at=_SEEDED_REVISION_AT,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        filing_instance_evidence=filing_instance_evidence,
        observations=registry_grounded_observations(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            casilla_values=casilla_values,
        )
        if casilla_values
        else (),
        verified_at=_SEEDED_REVISION_AT if state is not CalculationRevisionState.BORRADOR else None,
        verified_by="operator" if state is not CalculationRevisionState.BORRADOR else None,
        source_provenance=(),
    )
    cr_repo = CalculationRevisionCatalogueRepository()
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    return work_unit_id, calculation_revision_id


def _load_seeded_work_unit_and_revision(
    work_unit_id: str,
    calculation_revision_id: str,
) -> tuple[WorkUnit, CalculationRevision]:
    work_unit = WorkUnitCatalogueRepository().load().get(work_unit_id)
    revision = CalculationRevisionCatalogueRepository().load().get(calculation_revision_id)
    assert work_unit is not None
    assert revision is not None
    return work_unit, revision


def _synthetic_valid_nif(number: int) -> str:
    return f"{number:08d}{nif_check_letter(number)}"
