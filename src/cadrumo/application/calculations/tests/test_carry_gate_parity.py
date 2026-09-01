"""Public-behavior coverage for the shared revision-carry gate.

The period-revision-resolution R2 gate is shared by carry-read sites. These
tests exercise the resolvable cases through public application contracts:

- ``resolve_bindings_from_local_store`` for previous-filing binding prefill.
- ``evaluate_cross_period_clean_state`` for cross-period verification gates.

The unresolvable authority case is pinned directly on the shared gate because
the public carry readers only operate on registry-derived requirements.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from .._revision_carry_gate import revision_carry_outcome
from ..binding_prefill import resolve_bindings_from_local_store
from ..cross_period_clean_state import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodCleanStateVerdict,
    cross_period_dependency_requirements,
    evaluate_cross_period_clean_state,
)
from ..observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "9ab6fcf1-b639-4a5f-88ef-7a6e4e25b0eb"  # was 'revision-carry-gate-test'
_TAX_ID = "X1234567L"
_MODELO = "303"
_YEAR = 2025
_SOURCE_PERIOD = "1T"
_TARGET_PERIOD = "2T"
_M390_PERIOD = "0A"
_CLOCK = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_DIVERGENT_REVISION_ID = "definitely-not-the-right-revision-id-xyzzy"
_NONEXISTENT_MODELO = "999"
_M303_CARRY_BINDING_ID = "modelo-303-compensacion-pendiente-anteriores"
_M303_CARRY_SOURCE_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-disponible-fin-periodo",
    surface="_M303_CARRY_SOURCE_CASILLA",
)


def _law_revision_id(modelo: str = _MODELO, year: int = _YEAR, period: str = _SOURCE_PERIOD) -> str:
    snapshot = bundled_authority().snapshot(modelo, filing_year=year, period=period)
    return str(snapshot.revision.id)


def _m390_first_quarter_requirements():
    snapshot = bundled_authority().snapshot("390", filing_year=_YEAR, period=_M390_PERIOD)
    return snapshot, tuple(
        requirement
        for requirement in cross_period_dependency_requirements(snapshot)
        if requirement.source_modelo == _MODELO and requirement.period.registry_token == _SOURCE_PERIOD
    )


def _source_values(source_casilla_ids: tuple[CasillaId, ...]) -> dict[CasillaId, Decimal]:
    values = {_M303_CARRY_SOURCE_CASILLA: Decimal("500.00")}
    for index, casilla_id in enumerate(sorted(source_casilla_ids), start=1):
        values.setdefault(casilla_id, Decimal(index))
    return values


def _save_source_observation(
    repository: CalculationObservationRepository,
    *,
    source_casilla_ids: tuple[CasillaId, ...],
    stamped_revision_id: str,
) -> None:
    repository.save(
        repository.prepare_observation_envelope(
            registry_grounded_modelo_observation(
                modelo=_MODELO,
                filing_year=_YEAR,
                period=_SOURCE_PERIOD,
                casilla_values=_source_values(source_casilla_ids),
            ),
            source_kind="aeat_sede_justificante",
            captured_at=_CLOCK,
            stamped_revision_id=stamped_revision_id,
            source_metadata={
                "aeat_register_status": "ALTA",
                "aeat_expediente_id": "EXP-303-2025-1T",
                "authenticated_identity": _TAX_ID,
            },
        )
    )


def _cross_period_refused(
    verdict: CrossPeriodCleanStateVerdict,
    *,
    requirement_keys: set[tuple[str, int, str]],
) -> bool:
    evidence = tuple(
        item
        for item in verdict.dependencies
        if (
            item.requirement.source_modelo,
            item.requirement.filing_year,
            item.requirement.period.registry_token,
        )
        in requirement_keys
    )
    assert evidence, "M390 must expose first-quarter M303 cross-period dependencies"
    return any(CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE in item.blockers for item in evidence)


def _public_carry_outcomes(
    tmp_path: Path,
    stamped_revision_id: str,
) -> tuple[bool, bool]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        repository = CalculationObservationRepository()
        cross_snapshot, cross_requirements = _m390_first_quarter_requirements()
        source_casilla_ids = tuple(
            {casilla_id for requirement in cross_requirements for casilla_id in requirement.source_casilla_ids}
        )
        _save_source_observation(
            repository,
            source_casilla_ids=source_casilla_ids,
            stamped_revision_id=stamped_revision_id,
        )

        binding_snapshot = bundled_authority().snapshot(_MODELO, filing_year=_YEAR, period=_TARGET_PERIOD)
        binding_report = resolve_bindings_from_local_store(binding_snapshot, repository=repository)
        binding_refused = _M303_CARRY_BINDING_ID not in binding_report.binding_values

        cross_verdict = evaluate_cross_period_clean_state(
            cross_snapshot,
            bucket_id=_BUCKET_ID,
            observation_repository=repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id=_TAX_ID,
        )
        requirement_keys = {
            (requirement.source_modelo, requirement.filing_year, requirement.period.registry_token)
            for requirement in cross_requirements
        }
        return binding_refused, _cross_period_refused(cross_verdict, requirement_keys=requirement_keys)


@pytest.mark.parametrize("case", ["matching", "divergent"])
def test_public_carry_reads_match_shared_gate_for_resolvable_source(tmp_path: Path, case: str) -> None:
    """Binding-prefill and cross-period readers expose the shared R2 decision."""
    if case == "matching":
        stamp = _law_revision_id()
        expected = False
    else:
        stamp = _DIVERGENT_REVISION_ID
        expected = True
    shared_refused = revision_carry_outcome(
        stamp,
        source_modelo=_MODELO,
        source_filing_year=_YEAR,
        source_period=_SOURCE_PERIOD,
    ).refused
    binding_refused, cross_period_refused = _public_carry_outcomes(tmp_path / case, stamp)

    assert shared_refused is expected, f"shared gate disagreed with the spec for {case!r}"
    assert binding_refused is expected, f"binding prefill diverged from the shared gate for {case!r}"
    assert cross_period_refused is expected, f"cross-period clean state diverged from the shared gate for {case!r}"


def test_shared_gate_refuses_unresolvable_source() -> None:
    """A source context the registry cannot resolve is refused, not carried."""
    assert (
        revision_carry_outcome(
            _DIVERGENT_REVISION_ID,
            source_modelo=_NONEXISTENT_MODELO,
            source_filing_year=_YEAR,
            source_period=_SOURCE_PERIOD,
        ).refused
        is True
    )
