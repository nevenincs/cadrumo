"""Real-behavior tests for the Modelo 303 <-> Modelo 349 intra-community reconcile.

The cross-validator reads the persisted totals of both declarations for the same
bucket and period and surfaces a non-blocking WARNING advisory when the Modelo
303 intra-community total (box 10 acquisitions + box 59 supplies) diverges from
the Modelo 349 resumen total (``decl.importe-operaciones``) beyond a de-minimis
euro tolerance. These tests build both sides with the real secure backend and the
registry-grounded observation fixtures, then assert the advisory fires on a
genuine divergence and stays silent when the totals reconcile. The expected
fire/silent outcomes derive from the reconcile contract (which boxes, which
tolerance), not from re-running any registry formula, so they are not
tautological calculation assertions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ...tests import isolated_profile_backend as _isolated_backend

__all__ = ["_isolated_backend"]

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....core.resources import resources
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    WorkUnit,
    derive_calculation_revision_id,
    derive_work_unit_id,
    upsert_calculation_revision,
    upsert_work_unit,
)
from ....tests import general_m303_filing_evidence
from ....tests.registry_observations import registry_grounded_observations
from ...workflow import workflow_state_repository
from .._m303_m349_reconcile import m303_m349_intracom_reconcile_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_TAX_ID = "00000000T"
_CLOCK = datetime(2025, 4, 15, tzinfo=UTC)
_M303_ADQUISICIONES: CasillaId = validated_casilla_id("10", surface="test")
_M303_ENTREGAS: CasillaId = validated_casilla_id("59", surface="test")
_M349_IMPORTE_OPERACIONES: CasillaId = validated_casilla_id("decl.importe-operaciones", surface="test")


def _seed_work_unit(*, modelo: str, filing_year: int, period: str) -> WorkUnit:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    typed_period = Period.from_year_and_code(filing_year, period)
    revision_id = (
        resources()
        .modelos.authority.snapshot(modelo, filing_year=filing_year, period=typed_period.registry_token)
        .revision.id
    )
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
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit


def _build_revision(work_unit: WorkUnit, casilla_values: dict[CasillaId, Decimal]) -> CalculationRevision:
    filing_instance_evidence = (
        general_m303_filing_evidence(work_unit.period, reference="test:m303-m349-reconcile")
        if str(work_unit.modelo) == "303"
        else None
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        casilla_values=casilla_values,
        observations=registry_grounded_observations(
            modelo=str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            casilla_values=casilla_values,
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )


def _persist_revision(work_unit: WorkUnit, casilla_values: dict[CasillaId, Decimal]) -> CalculationRevision:
    revision = _build_revision(work_unit, casilla_values)
    repo = CalculationRevisionCatalogueRepository()
    repo.save(upsert_calculation_revision(repo.load(), revision))
    return revision


def _m303_values(*, adquisiciones: Decimal, entregas: Decimal) -> dict[CasillaId, Decimal]:
    return {_M303_ADQUISICIONES: adquisiciones, _M303_ENTREGAS: entregas}


def _m349_values(*, importe: Decimal) -> dict[CasillaId, Decimal]:
    return {_M349_IMPORTE_OPERACIONES: importe}


def _reconcile(work_unit: WorkUnit, target: CalculationRevision):
    return m303_m349_intracom_reconcile_findings(
        work_unit=work_unit,
        target=target,
        work_unit_repository=WorkUnitCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
    )


def test_advisory_fires_when_m303_intracom_exceeds_m349_resumen() -> None:
    m303 = _seed_work_unit(modelo="303", filing_year=2024, period="1T")
    m349 = _seed_work_unit(modelo="349", filing_year=2024, period="1T")
    target = _build_revision(m303, _m303_values(adquisiciones=Decimal("6000"), entregas=Decimal("4000")))
    _persist_revision(m349, _m349_values(importe=Decimal("8000")))

    findings = _reconcile(m303, target)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind is ModeloVerificationFindingKind.RECONCILIATION_MISMATCH
    assert finding.severity is ModeloVerificationFindingSeverity.WARNING
    # 303 total 6000 + 4000 = 10000 vs 349 resumen 8000 -> gap 2000.
    assert finding.message_locale_key == "application.modelo.findings.m303_m349_intracom_reconciliation_mismatch"
    assert finding.message_facts["m303_total"] == Decimal("10000")
    assert finding.message_facts["m349_total"] == Decimal("8000")
    assert finding.message_facts["gap"] == Decimal("2000")
    assert finding.legal_refs  # grounded, non-empty


def test_advisory_silent_when_totals_reconcile() -> None:
    m303 = _seed_work_unit(modelo="303", filing_year=2024, period="1T")
    m349 = _seed_work_unit(modelo="349", filing_year=2024, period="1T")
    target = _build_revision(m303, _m303_values(adquisiciones=Decimal("6000"), entregas=Decimal("4000")))
    _persist_revision(m349, _m349_values(importe=Decimal("10000")))

    assert _reconcile(m303, target) == []


def test_advisory_fires_when_verifying_the_m349_side() -> None:
    m303 = _seed_work_unit(modelo="303", filing_year=2024, period="1T")
    m349 = _seed_work_unit(modelo="349", filing_year=2024, period="1T")
    _persist_revision(m303, _m303_values(adquisiciones=Decimal("6000"), entregas=Decimal("4000")))
    target = _build_revision(m349, _m349_values(importe=Decimal("8000")))

    findings = _reconcile(m349, target)

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.RECONCILIATION_MISMATCH
    assert findings[0].message_facts["m303_total"] == Decimal("10000")
    assert findings[0].message_facts["m349_total"] == Decimal("8000")


def test_no_finding_when_sibling_declaration_absent() -> None:
    m303 = _seed_work_unit(modelo="303", filing_year=2024, period="1T")
    target = _build_revision(m303, _m303_values(adquisiciones=Decimal("6000"), entregas=Decimal("4000")))

    assert _reconcile(m303, target) == []


def test_within_de_minimis_gap_is_silent() -> None:
    m303 = _seed_work_unit(modelo="303", filing_year=2024, period="1T")
    m349 = _seed_work_unit(modelo="349", filing_year=2024, period="1T")
    target = _build_revision(m303, _m303_values(adquisiciones=Decimal("6000"), entregas=Decimal("4000")))
    # gap of 0.50 EUR <= 1.00 de-minimis tolerance -> no advisory.
    _persist_revision(m349, _m349_values(importe=Decimal("9999.50")))

    assert _reconcile(m303, target) == []


def test_no_finding_when_nothing_intracommunity_declared() -> None:
    m303 = _seed_work_unit(modelo="303", filing_year=2024, period="1T")
    m349 = _seed_work_unit(modelo="349", filing_year=2024, period="1T")
    target = _build_revision(m303, _m303_values(adquisiciones=Decimal("0"), entregas=Decimal("0")))
    _persist_revision(m349, _m349_values(importe=Decimal("0")))

    assert _reconcile(m303, target) == []


def test_reconcile_skipped_for_unrelated_modelo() -> None:
    m130 = _seed_work_unit(modelo="130", filing_year=2024, period="1T")
    # The reconcile short-circuits before reading any casilla for a non-303/349
    # modelo, so an empty-values draft (no grounded observations required) suffices.
    target = _build_revision(m130, {})

    assert _reconcile(m130, target) == []
