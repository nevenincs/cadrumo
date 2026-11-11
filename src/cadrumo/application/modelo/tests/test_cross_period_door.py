"""The door an unclean cross-period source names, chosen by its first blocker.

A Modelo 130 first quarter reads the previous ejercicio's net activity income
from that year's Modelo 100 (RIRPF art. 110.3). When the filer only stated that
figure, the source is unclean on the operator's word alone, and the refusal must
still say how to settle it: capture the filed Renta from the AEAT.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.tests.authored_editions import authored_revisions, filing_year_envelope
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...calculations.cross_period_models import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
)
from ..verification_cross_period import cross_period_door

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "13000000-0000-4000-8000-000000000130"
_NOW = datetime(1980, 9, 21, 10, 0, tzinfo=UTC)
_PRIOR_YEAR = filing_year_envelope().horizon - 2


def _prior_renta_evidence(*blockers: CrossPeriodCleanStateBlocker) -> CrossPeriodDependencyEvidence:
    return CrossPeriodDependencyEvidence(
        requirement=CrossPeriodDependencyRequirement(
            source_modelo="100",
            filing_year=_PRIOR_YEAR,
            period=Period.from_year_and_code(_PRIOR_YEAR, "0A"),
            source_casilla_ids=(validated_casilla_id("0224", surface="test"),),
            origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
            origin_ids=("irpf.previous_year_economic_activity_net_income",),
            legal_refs=("rd-439-2007:art-110",),
            source_refs=("aeat-modelo-130-instrucciones",),
        ),
        blockers=blockers,
    )


def _door(evidence: CrossPeriodDependencyEvidence) -> tuple[str, dict[str, str | int] | None]:
    with bundled_indexed_authority().operation() as operation:
        return cross_period_door(
            evidence,
            bucket_id=_BUCKET_ID,
            work_catalogue=WorkUnitCatalogue(),
            calculation_catalogue=CalculationRevisionCatalogue(),
            operation=operation,
        )


def test_a_prior_year_figure_only_the_filer_stated_is_captured_from_the_aeat() -> None:
    door = _door(
        _prior_renta_evidence(
            CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE,
            CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD,
        )
    )

    assert door == ("filed_evidence_missing", {"modelos": "100", "period": "0A", "year": _PRIOR_YEAR})


def test_a_blocker_nothing_settles_still_names_no_door() -> None:
    door = _door(_prior_renta_evidence(CrossPeriodCleanStateBlocker.FILING_KIND_DISAGREEMENT))

    assert door == ("unclean", None)


def _attest_target() -> WorkUnit:
    year = filing_year_envelope().floor
    period = Period.from_year_and_code(year, "1T")
    revision_id = _revision_governing("130", year)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo="130", filing_year=year, period=period, revision_id=revision_id
        ),
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=year,
        period=period,
        revision_id=revision_id,
        name="Pagos fraccionados",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _revision_governing(modelo_id: str, year: int) -> str:
    return next(
        str(revision.id) for revision in reversed(authored_revisions(modelo_id)) if revision.valid_from.year <= year
    )


def _outside_envelope_evidence(*blockers: CrossPeriodCleanStateBlocker) -> CrossPeriodDependencyEvidence:
    year = filing_year_envelope().floor - 1
    return CrossPeriodDependencyEvidence(
        requirement=_prior_renta_evidence().requirement.model_copy(
            update={
                "filing_year": year,
                "period": Period.from_year_and_code(year, "0A"),
                "source_outside_envelope": True,
            }
        ),
        blockers=blockers,
    )


def _door_for(
    evidence: CrossPeriodDependencyEvidence, target: WorkUnit | None
) -> tuple[str, dict[str, str | int] | None]:
    with bundled_indexed_authority().operation() as operation:
        return cross_period_door(
            evidence,
            bucket_id=_BUCKET_ID,
            work_catalogue=WorkUnitCatalogue(),
            calculation_catalogue=CalculationRevisionCatalogue(),
            operation=operation,
            target=target,
        )


@pytest.mark.parametrize(
    "blocker",
    [CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE, CrossPeriodCleanStateBlocker.MISSING_OBSERVATION],
)
def test_a_source_the_envelope_refuses_names_the_statement_of_its_figure_as_the_way_on(
    blocker: CrossPeriodCleanStateBlocker,
) -> None:
    target = _attest_target()

    door = _door_for(_outside_envelope_evidence(blocker), target)

    assert door == (
        "attest_prior_value",
        {
            "work_unit_id": target.work_unit_id,
            "modelo": "130",
            "year": target.filing_year,
            "period": "1T",
            "binding_id": "irpf.previous_year_economic_activity_net_income",
        },
    )


def test_a_source_the_envelope_refuses_names_no_door_without_the_declaration_it_would_be_stated_on() -> None:
    door = _door_for(_outside_envelope_evidence(CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE), None)

    assert door[0] != "attest_prior_value"


def test_a_source_the_envelope_admits_keeps_the_door_it_had() -> None:
    door = _door_for(
        _prior_renta_evidence(
            CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE,
            CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD,
        ),
        _attest_target(),
    )

    assert door == ("filed_evidence_missing", {"modelos": "100", "period": "0A", "year": _PRIOR_YEAR})
