"""Prior definitive sources of the provisional prorrata over real stored observations.

LIVA art. 104.Dos.1 / 105.Uno: a Modelo 390 filer's prior definitive is box
[118] of the annual summary; a filer exempt from the 390 states it in the
final-period Modelo 303; with neither held the taxpayer states it. Every case
runs for each supported year whose prior year is also supported, read from the
registry envelope.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.calculations.observations_repository import ObservationEnvelopePayload
from .....application.prorrata_register.seed import (
    PRORRATA_OPERATOR_STATED,
    PRORRATA_RETURN_CONTRADICTS_FIGURE,
    PRORRATA_SEVERAL_ACTIVITIES,
    evaluate_carried_prior_definitiva_seed_from_observations,
    prior_definitiva_source_coordinates,
)
from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.period import Period, StandardPeriodCode
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.binding_targets import casillas_by_binding
from .....domain.calculations.registry.form_codes import form_for_role
from .....domain.calculations.registry.prorrata_register_activity_bindings import (
    ProrrataActivityField,
    ProrrataRegisterActivityProvider,
)
from .....domain.calculations.registry.prorrata_register_catalogue import (
    carried_prior_definitiva_prorrata_provenance,
    operator_stated_prior_definitiva_prorrata_provenance,
)
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.calculations.registry.tests.registry_observations import registry_grounded_modelo_observation
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..calculation_observations import CalculationObservationRepository
from .modelo_303_filed_disposition import modelo_303_filed_disposition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SOURCE_KIND = "aeat_sede_justificante"
_PERIODIC_PERCENTAGE: CasillaId = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")
_ANNUAL_PERCENTAGE = Decimal("64")
_PERIODIC_PERCENTAGE_VALUE = Decimal("71")

_YEARS = filing_year_envelope().years
_SEED_YEARS = tuple(year for year in _YEARS if year - 1 in _YEARS)


def _captured_at(prior_year: int) -> datetime:
    return datetime(prior_year + 1, 1, 30, 10, 0, tzinfo=UTC)


def _annual_percentage_casillas(operation: PinnedAuthorityOperation, prior_year: int) -> dict[int, CasillaId]:
    revision = operation.snapshot(
        form_for_role("iva.annual_summary"),
        filing_year=prior_year,
        period=StandardPeriodCode.ANNUAL.value,
        grade=RegistryAuthorityGrade.CALCULATION,
    ).revision
    targets = casillas_by_binding(revision)
    rows: dict[int, CasillaId] = {}
    for binding in revision.bindings:
        provider = binding.provider
        if (
            isinstance(provider, ProrrataRegisterActivityProvider)
            and provider.field is ProrrataActivityField.PORCENTAJE
        ):
            rows[provider.slot] = targets[binding.id][0]
    return rows


def _save(
    repo: CalculationObservationRepository,
    operation: PinnedAuthorityOperation,
    *,
    modelo: str,
    prior_year: int,
    period: str,
    casilla_values: dict[CasillaId, Decimal],
) -> None:
    source_headers = ()
    if modelo == form_for_role("iva.periodic"):
        casilla_values, source_headers = modelo_303_filed_disposition(
            casilla_values, source_locator="prior-settlement:declaration-type"
        )
    observation = registry_grounded_modelo_observation(
        modelo=modelo,
        filing_year=prior_year,
        period=period,
        casilla_values=casilla_values,
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    revision_id = operation.snapshot(
        modelo, filing_year=prior_year, period=period, grade=RegistryAuthorityGrade.CALCULATION
    ).revision.id
    repo.save(
        repo.prepare_observation_envelope(
            observation,
            source_kind=_SOURCE_KIND,
            captured_at=_captured_at(prior_year),
            source_headers=source_headers,
            stamped_revision_id=revision_id,
        )
    )


def _save_annual(
    repo: CalculationObservationRepository,
    operation: PinnedAuthorityOperation,
    prior_year: int,
    percentages: tuple[Decimal, ...],
) -> None:
    rows = _annual_percentage_casillas(operation, prior_year)
    _save(
        repo,
        operation,
        modelo=form_for_role("iva.annual_summary"),
        prior_year=prior_year,
        period=StandardPeriodCode.ANNUAL.value,
        casilla_values={rows[slot]: value for slot, value in enumerate(percentages, start=1)},
    )


def _save_periodic(
    repo: CalculationObservationRepository, operation: PinnedAuthorityOperation, prior_year: int
) -> None:
    _save(
        repo,
        operation,
        modelo=form_for_role("iva.periodic"),
        prior_year=prior_year,
        period=StandardPeriodCode.Q4.value,
        casilla_values={_PERIODIC_PERCENTAGE: _PERIODIC_PERCENTAGE_VALUE},
    )


def _prior_sources(repo: CalculationObservationRepository, prior_year: int) -> tuple[ObservationEnvelopePayload, ...]:
    held = (
        repo.load_observation(modelo, Period.from_year_and_code(prior_year, token))
        for modelo, token in prior_definitiva_source_coordinates()
    )
    return tuple(item for item in held if item is not None)


@pytest.mark.parametrize("ejercicio", _SEED_YEARS)
def test_the_prior_annual_summary_box_seeds_before_the_final_periodic_return(
    tmp_path: Path, ejercicio: int, *, operation: PinnedAuthorityOperation
) -> None:
    prior_year = ejercicio - 1
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = CalculationObservationRepository(objects=profile.repository)
        _save_periodic(repo, operation, prior_year)
        _save_annual(repo, operation, prior_year, (_ANNUAL_PERCENTAGE,))
        evaluation = evaluate_carried_prior_definitiva_seed_from_observations(
            ejercicio=ejercicio, observations=_prior_sources(repo, prior_year), operation=operation
        )

    assert evaluation.findings == ()
    seed = evaluation.seed
    assert seed is not None
    assert seed.source_modelo == form_for_role("iva.annual_summary")
    assert seed.source_period == StandardPeriodCode.ANNUAL.value
    assert seed.source_casilla_id == _annual_percentage_casillas(operation, prior_year)[1]
    assert seed.entry.provisional_percentage == _ANNUAL_PERCENTAGE
    assert seed.entry.provisional_provenance == carried_prior_definitiva_prorrata_provenance()
    assert not seed.operator_stated


@pytest.mark.parametrize("ejercicio", _SEED_YEARS)
def test_a_filer_exempt_from_the_annual_summary_seeds_from_the_final_periodic_return(
    tmp_path: Path, ejercicio: int, *, operation: PinnedAuthorityOperation
) -> None:
    prior_year = ejercicio - 1
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = CalculationObservationRepository(objects=profile.repository)
        _save_periodic(repo, operation, prior_year)
        evaluation = evaluate_carried_prior_definitiva_seed_from_observations(
            ejercicio=ejercicio, observations=_prior_sources(repo, prior_year), operation=operation
        )

    seed = evaluation.seed
    assert evaluation.findings == ()
    assert seed is not None
    assert seed.source_modelo == form_for_role("iva.periodic")
    assert seed.entry.provisional_percentage == _PERIODIC_PERCENTAGE_VALUE


@pytest.mark.parametrize("ejercicio", _SEED_YEARS)
def test_with_neither_return_held_only_a_statement_seeds_and_it_is_disclosed(
    ejercicio: int, *, operation: PinnedAuthorityOperation
) -> None:
    unstated = evaluate_carried_prior_definitiva_seed_from_observations(
        ejercicio=ejercicio, observations=(), operation=operation
    )
    stated = evaluate_carried_prior_definitiva_seed_from_observations(
        ejercicio=ejercicio, observations=(), operation=operation, stated_percentage=Decimal("58")
    )

    assert (unstated.seed, unstated.findings) == (None, ())
    seed = stated.seed
    assert seed is not None
    assert seed.operator_stated
    assert seed.entry.provisional_percentage == Decimal("58")
    assert seed.entry.provisional_provenance == operator_stated_prior_definitiva_prorrata_provenance()
    assert seed.entry.source_observation_ref is None
    assert seed.source_modelo == form_for_role("iva.annual_summary")
    assert seed.source_casilla_id == _annual_percentage_casillas(operation, ejercicio - 1)[1]
    assert not stated.blocked
    assert [finding.code for finding in stated.findings] == [PRORRATA_OPERATOR_STATED]


@pytest.mark.parametrize("ejercicio", _SEED_YEARS)
def test_a_held_return_stating_another_figure_blocks_the_statement(
    tmp_path: Path, ejercicio: int, *, operation: PinnedAuthorityOperation
) -> None:
    prior_year = ejercicio - 1
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = CalculationObservationRepository(objects=profile.repository)
        _save_annual(repo, operation, prior_year, (_ANNUAL_PERCENTAGE,))
        sources = _prior_sources(repo, prior_year)
        contradicted = evaluate_carried_prior_definitiva_seed_from_observations(
            ejercicio=ejercicio, observations=sources, operation=operation, stated_percentage=Decimal("12")
        )
        agreeing = evaluate_carried_prior_definitiva_seed_from_observations(
            ejercicio=ejercicio, observations=sources, operation=operation, stated_percentage=_ANNUAL_PERCENTAGE
        )

    assert contradicted.seed is None
    assert contradicted.blocked
    assert [finding.code for finding in contradicted.findings] == [PRORRATA_RETURN_CONTRADICTS_FIGURE]
    assert agreeing.seed is not None
    assert not agreeing.seed.operator_stated
    assert agreeing.findings == ()


@pytest.mark.parametrize("ejercicio", _SEED_YEARS)
def test_an_annual_summary_with_several_activities_leaves_the_percentage_not_computed(
    tmp_path: Path, ejercicio: int, *, operation: PinnedAuthorityOperation
) -> None:
    prior_year = ejercicio - 1
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = CalculationObservationRepository(objects=profile.repository)
        _save_periodic(repo, operation, prior_year)
        _save_annual(repo, operation, prior_year, (_ANNUAL_PERCENTAGE, Decimal("30")))
        evaluation = evaluate_carried_prior_definitiva_seed_from_observations(
            ejercicio=ejercicio,
            observations=_prior_sources(repo, prior_year),
            operation=operation,
            stated_percentage=_ANNUAL_PERCENTAGE,
        )

    assert evaluation.seed is None
    assert evaluation.blocked
    assert [finding.code for finding in evaluation.findings] == [PRORRATA_SEVERAL_ACTIVITIES]
