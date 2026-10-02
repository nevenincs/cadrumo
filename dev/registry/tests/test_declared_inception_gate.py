"""A declared inception gates temporal selection; an unauthored-debt declaration does not.

Every case is derived from the live declarations and editions: the years come
from the support envelope and from each modelo's own earliest authored edition.
The synthetic cases place a declaration on a copy of a live modelo, so the gate
is exercised even when no live modelo happens to declare its inception inside
the envelope, and the undeclared copy proves the refusal comes from the gate
rather than from the corpus.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from cadrumo.domain.calculations.registry.errors import (
    FilingYearOutsideSupportEnvelopeError,
    NoRevisionForPeriodError,
)
from cadrumo.domain.calculations.registry.modelo_inception import DeclaredInception, UnauthoredBefore
from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
    SupportedFilingYearsCatalogue,
)
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection
from cadrumo.domain.calculations.registry.temporal import (
    ModeloRevisionDirectory,
    revision_temporal_resolution,
    select_authored_revision_metadata,
    select_revision,
    select_revision_for_year,
    select_revision_metadata,
    select_revision_metadata_for_year,
)

from ..conformance.registry_schema_support import committed_registry_tree
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _earliest_authored_year(modelo: ModeloDefinition) -> int:
    """Return the earliest filing year any edition of ``modelo`` authors."""
    firsts = [
        min(revision.period_selector.years) if revision.period_selector.years else revision.period_selector.year_from
        for revision in modelo.revisions.values()
    ]
    return min(year for year in firsts if year is not None)


def _earliest_periods(modelo: ModeloDefinition) -> tuple[str, ...]:
    """Return the period tokens the earliest authored edition declares for its first year."""
    year = _earliest_authored_year(modelo)
    return tuple(
        sorted(
            {
                str(period)
                for revision in modelo.revisions.values()
                if revision.period_selector.includes_year(year)
                for period in revision.period_selector.periods_for_year(year)
            }
        )
    )


def _inception_disagreement(modelo: ModeloDefinition) -> str | None:
    """Return why a modelo's inception statement contradicts its editions, if it does."""
    inception = modelo.inception
    earliest = _earliest_authored_year(modelo)
    if isinstance(inception, DeclaredInception) and earliest < inception.filing_year:
        return f"modelo {modelo.id} authors {earliest}, before its declared inception {inception.filing_year}"
    if isinstance(inception, UnauthoredBefore) and inception.earliest_authored != earliest:
        return (
            f"modelo {modelo.id} states earliest_authored={inception.earliest_authored}, "
            f"but its earliest edition authors {earliest}"
        )
    return None


def _live_modelos() -> tuple[ModeloDefinition, ...]:
    modelos, _catalogues = committed_registry_tree()
    return tuple(modelos)


def _starting_inside_the_envelope(support: SupportedFilingYearsCatalogue) -> tuple[ModeloDefinition, ...]:
    """Live modelos whose earliest edition leaves supported years before it."""
    return tuple(modelo for modelo in _live_modelos() if _earliest_authored_year(modelo) > support.floor)


def _declared_at_earliest_edition(modelo: ModeloDefinition) -> ModeloDefinition:
    return modelo.model_copy(
        update={
            "inception": DeclaredInception(
                filing_year=_earliest_authored_year(modelo),
                legal_refs=modelo.legal_refs[:1],
            )
        }
    )


def _unauthored_before_earliest_edition(modelo: ModeloDefinition) -> ModeloDefinition:
    return modelo.model_copy(
        update={
            "inception": UnauthoredBefore(
                earliest_authored=_earliest_authored_year(modelo),
                reason="synthetic unauthored-debt declaration at the earliest authored edition",
            )
        }
    )


def test_every_inception_statement_agrees_with_the_authored_editions() -> None:
    """No declared inception postdates an edition, and every debt statement names the earliest one."""
    disagreements = [finding for modelo in _live_modelos() if (finding := _inception_disagreement(modelo))]

    assert disagreements == []


def test_the_agreement_screen_detects_a_statement_that_disagrees() -> None:
    """Detector teeth: moving a statement off the earliest edition is reported, in both arms."""
    modelo = _live_modelos()[0]
    earliest = _earliest_authored_year(modelo)
    late_inception = modelo.model_copy(
        update={"inception": DeclaredInception(filing_year=earliest + 1, legal_refs=modelo.legal_refs[:1])}
    )
    stale_debt = modelo.model_copy(
        update={"inception": UnauthoredBefore(earliest_authored=earliest + 1, reason="stale synthetic statement")}
    )

    assert _inception_disagreement(_declared_at_earliest_edition(modelo)) is None
    assert _inception_disagreement(late_inception) is not None
    assert _inception_disagreement(stale_debt) is not None


def _gate_cases(support: SupportedFilingYearsCatalogue) -> tuple[ModeloDefinition, ...]:
    live = tuple(
        modelo
        for modelo in _live_modelos()
        if isinstance(modelo.inception, DeclaredInception) and modelo.inception.filing_year > support.floor
    )
    synthetic = tuple(_declared_at_earliest_edition(modelo) for modelo in _starting_inside_the_envelope(support))
    return live + synthetic


def _every_selector(
    modelo: ModeloDefinition, support: SupportedFilingYearsCatalogue, *, filing_year: int, period: str
) -> tuple[Callable[[], object], ...]:
    directory = ModeloRevisionDirectory.from_modelo(modelo, support=support)
    return (
        lambda: select_revision(modelo, filing_year=filing_year, period=period, support=support),
        lambda: select_revision(modelo, filing_year=filing_year, period=period, support=None),
        lambda: select_revision_for_year(modelo, filing_year=filing_year, support=support),
        lambda: select_revision_metadata(directory, filing_year=filing_year, period=period),
        lambda: select_revision_metadata_for_year(directory, filing_year=filing_year),
        lambda: select_authored_revision_metadata(directory, filing_year=filing_year, period=period),
    )


def test_a_year_before_a_declared_inception_is_refused_by_every_selector() -> None:
    """Inside the envelope, a pre-inception year is an absence refusal, not a projection."""
    support = committed_supported_filing_years()
    cases = _gate_cases(support)
    assert cases, "no live modelo starts after the support floor, so the gate has no coordinate to refuse"

    for modelo in cases:
        assert isinstance(modelo.inception, DeclaredInception)
        inception_year = modelo.inception.filing_year
        for period in _earliest_periods(modelo):
            answered = select_revision(modelo, filing_year=inception_year, period=period, support=support)
            assert answered.period_selector.includes_year(inception_year)
            for filing_year in range(support.floor, inception_year):
                for select in _every_selector(modelo, support, filing_year=filing_year, period=period):
                    with pytest.raises(NoRevisionForPeriodError) as excinfo:
                        select()
                    assert not isinstance(excinfo.value, FilingYearOutsideSupportEnvelopeError)
                    assert excinfo.value.modelo_id == str(modelo.id)
                    assert excinfo.value.filing_year == filing_year


def test_without_the_declaration_the_resolver_would_answer_the_pre_inception_year() -> None:
    """Detector teeth: the same modelo with no inception projects its earliest edition backwards."""
    support = committed_supported_filing_years()
    cases = _starting_inside_the_envelope(support)
    assert cases, "no live modelo starts after the support floor, so there is no backward projection to observe"

    for modelo in cases:
        undeclared = modelo.model_copy(update={"inception": None})
        earliest = _earliest_authored_year(modelo)
        for period in _earliest_periods(modelo):
            selected = select_revision(undeclared, filing_year=support.floor, period=period, support=support)
            resolution = revision_temporal_resolution(
                selected, filing_year=support.floor, period=period, support=support
            )
            assert resolution.authored_filing_year == earliest
            assert resolution.projection_direction is TemporalProjectionDirection.BACKWARD


def test_projection_still_serves_years_below_an_unauthored_debt_declaration() -> None:
    """The unauthored arm is informational: supported years before the earliest edition are projected onto it."""
    support = committed_supported_filing_years()
    live = tuple(
        modelo
        for modelo in _live_modelos()
        if isinstance(modelo.inception, UnauthoredBefore) and _earliest_authored_year(modelo) > support.floor
    )
    synthetic = tuple(_unauthored_before_earliest_edition(modelo) for modelo in _starting_inside_the_envelope(support))
    cases = live + synthetic
    assert cases, "no live modelo starts after the support floor, so no unauthored year needs projection"

    for modelo in cases:
        assert isinstance(modelo.inception, UnauthoredBefore)
        directory = ModeloRevisionDirectory.from_modelo(modelo, support=support)
        earliest = _earliest_authored_year(modelo)
        for period in _earliest_periods(modelo):
            for filing_year in range(support.floor, earliest):
                selected = select_revision(modelo, filing_year=filing_year, period=period, support=support)
                resolution = revision_temporal_resolution(
                    selected, filing_year=filing_year, period=period, support=support
                )
                assert resolution.projection_direction is TemporalProjectionDirection.BACKWARD
                assert resolution.authored_filing_year == earliest
                indexed = select_revision_metadata(directory, filing_year=filing_year, period=period)
                assert indexed.id == selected.id
