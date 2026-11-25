"""Focused tests for non-duplicating modelo parameter projections."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from itertools import pairwise
from types import SimpleNamespace

import pytest

from cadrumo.core.revision_review import RevisionReviewStatus
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.payloads import ScalarFactPayload
from cadrumo.domain.calculations.registry.facts.resolution import ScalarFactQuery
from cadrumo.domain.calculations.registry.facts.variants import FactSelector
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.calculations.registry.schema_formula import ParameterDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..compiler.fact_providers import FACT_PROVIDER_REGISTRATIONS
from ..compiler.modelo_projections import (
    MODELO_PARAMETER_PROJECTION_PROVIDER_ID,
    ModeloParameterFact,
    compile_modelo_parameter_projection_facts,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = filing_year_envelope().horizon
_DEFAULT_SOURCE = f"aeat-renta-{_YEAR}-manual-parte1"


def _parameter(
    parameter_id: str,
    value: str,
    *,
    valid_from: date,
    valid_to: date | None = None,
    source_ref: str = _DEFAULT_SOURCE,
    date_axis: str = "filing_period",
) -> ParameterDefinition:
    return ParameterDefinition.model_validate(
        {
            "id": parameter_id,
            "data_type": "money",
            "unit": "EUR",
            "legal_refs": ("ley-35-2006:art-81",),
            "source_refs": (source_ref,),
            "source_citations": ({"source_ref": source_ref, "required_text": ("deducción por maternidad",)},),
            "values": (
                {
                    "value": value,
                    "date_axis": date_axis,
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                },
            ),
        },
    )


def test_query_contract_names_exact_modelo_parameter_coordinates() -> None:
    query = ScalarFactQuery(
        fact_id=ModeloParameterFact.MATERNITY_ANNUAL_CAP,
        date_axis=DateAxis.FILING_PERIOD,
        effective_date=date(_YEAR, 12, 31),
        selectors=(
            FactSelector(name="modelo", value="100"),
            FactSelector(name="parameter_id", value="renta-maternidad-cap-anual"),
        ),
    )

    assert query.fact_id == "renta.maternity.annual-cap"
    assert {(selector.name, selector.value) for selector in query.selectors} == {
        ("modelo", "100"),
        ("parameter_id", "renta-maternidad-cap-anual"),
    }


def test_projection_provider_is_registered_without_claiming_modelo_file_ownership() -> None:
    registration = next(
        item for item in FACT_PROVIDER_REGISTRATIONS if item.provider_id == MODELO_PARAMETER_PROJECTION_PROVIDER_ID
    )

    assert registration.owned_directories == ()
    assert registration.project_modelos is compile_modelo_parameter_projection_facts


def test_projection_preserves_scalar_temporal_and_provenance_contracts() -> None:
    modelos = (_modelo_100(), _modelo_347())
    facts = {fact.fact_id: fact for fact in compile_modelo_parameter_projection_facts(modelos)}
    variant = facts[ModeloParameterFact.MATERNITY_ANNUAL_CAP].variants[0]

    assert isinstance(variant.payload, ScalarFactPayload)
    assert variant.payload.value == Decimal("1200")
    assert variant.payload.unit == "EUR"
    assert variant.valid_from == date(_YEAR, 1, 1)
    assert variant.valid_to == date(_YEAR, 12, 31)
    assert variant.legal_refs == ("ley-35-2006:art-81",)
    assert variant.source_refs == (_DEFAULT_SOURCE,)
    assert variant.source_citations
    assert variant.ownership.value == "generated"


def test_identical_parameter_copies_across_revisions_project_once() -> None:
    facts = compile_modelo_parameter_projection_facts((_modelo_100(), _modelo_347()))
    threshold = next(fact for fact in facts if fact.fact_id == ModeloParameterFact.M347_COUNTERPARTY_ANNUAL_THRESHOLD)

    assert len(threshold.variants) == 1
    assert isinstance(threshold.variants[0].payload, ScalarFactPayload)
    assert threshold.variants[0].payload.value == Decimal("3005.06")


def test_an_unchanged_row_restated_with_per_edition_evidence_splits_at_edition_boundaries() -> None:
    """Each edition keeps its own evidence, and the slices cover exactly the row's window.

    A value the law leaves unchanged is authored once, open from its first
    year, and each later edition restates it with that edition's own manual.
    Projecting those statements as one variant per statement would give two
    variants one identity; the projection instead slices the row at each
    edition whose provenance differs.
    """
    row_start = date(_YEAR - 5, 1, 1)
    editions = {
        _edition_id(year, year): _revision(
            year,
            year,
            (
                _parameter(
                    "renta-maternidad-mensual",
                    "100",
                    valid_from=row_start,
                    source_ref=f"aeat-renta-{year}-manual-parte1",
                ),
            ),
        )
        for year in range(row_start.year, row_start.year + 3)
    }
    newest = _revision(_YEAR, None, _modelo_100_parameters(exclude="renta-maternidad-mensual"))
    modelo_100 = _modelo("100", {**editions, newest.id: newest})

    facts = {fact.fact_id: fact for fact in compile_modelo_parameter_projection_facts((modelo_100, _modelo_347()))}
    variants = facts[ModeloParameterFact.MATERNITY_MONTHLY_DEDUCTION].variants

    assert [variant.source_refs for variant in variants] == [
        (f"aeat-renta-{year}-manual-parte1",) for year in range(row_start.year, row_start.year + 3)
    ]
    assert variants[0].valid_from == row_start
    for earlier, later in pairwise(variants):
        assert earlier.valid_to is not None
        assert later.valid_from is not None
        assert (later.valid_from - earlier.valid_to).days == 1
    assert variants[-1].valid_to is None
    assert len({variant.variant_id for variant in variants}) == len(variants)


def test_a_non_filing_period_row_restated_with_different_evidence_is_refused() -> None:
    """Only filing-period rows share the edition window's coordinates, so only they may be sliced."""
    row_start = date(_YEAR - 5, 1, 1)
    editions = {
        _edition_id(year, year): _revision(
            year,
            year,
            (
                _parameter(
                    "renta-maternidad-mensual",
                    "100",
                    valid_from=row_start,
                    source_ref=f"aeat-renta-{year}-manual-parte1",
                    date_axis="devengo_date",
                ),
            ),
        )
        for year in range(row_start.year, row_start.year + 2)
    }
    newest = _revision(_YEAR, None, _modelo_100_parameters(exclude="renta-maternidad-mensual"))
    modelo_100 = _modelo("100", {**editions, newest.id: newest})

    with pytest.raises(RegistryValidationError, match="only a filing-period row can be split"):
        compile_modelo_parameter_projection_facts((modelo_100, _modelo_347()))


def _modelo_100_parameters(*, exclude: str = "") -> tuple[ParameterDefinition, ...]:
    return tuple(
        parameter
        for parameter in _modelo_100().revisions[_edition_id(_YEAR, None)].parameters
        if parameter.id != exclude
    )


def _modelo_100() -> ModeloDefinition:
    start, end = date(_YEAR, 1, 1), date(_YEAR, 12, 31)
    parameters = (
        _parameter("renta-maternidad-mensual", "100", valid_from=start, valid_to=end),
        _parameter("renta-maternidad-cap-anual", "1200", valid_from=start, valid_to=end),
        _parameter("renta-maternidad-alta-posterior-incremento", "150", valid_from=start, valid_to=end),
    )
    newest = _revision(_YEAR, None, parameters)
    return _modelo("100", {newest.id: newest})


def _modelo_347() -> ModeloDefinition:
    parameter = _parameter("modelo-347-tercero-anual-threshold-eur", "3005.06", valid_from=date(_YEAR - 18, 1, 1))
    closed = _revision(_YEAR - 15, _YEAR - 1, (parameter,))
    newest = _revision(_YEAR, None, (parameter,))
    return _modelo("347", {closed.id: closed, newest.id: newest})


def _edition_id(first: int, last: int | None) -> str:
    """Spell an edition id the way the authored tree does: a first year, then a closing year or an open tail."""
    return f"{first}-{'y-siguientes' if last is None else last}"


def _revision(first: int, last: int | None, parameters: tuple[ParameterDefinition, ...]) -> SimpleNamespace:
    """One stand-in edition, carrying the window the projection orders editions by.

    Stated rather than omitted because the projection picks the newest edition
    by ``valid_from`` and only carries an end forward when it is that edition's
    own.
    """
    return SimpleNamespace(
        id=_edition_id(first, last),
        parameters=parameters,
        review_status=RevisionReviewStatus.AUTOMATION_REVIEWED,
        valid_from=date(first, 1, 1),
        valid_to=None if last is None else date(last, 12, 31),
    )


def _modelo_payload(modelo_id: str, revisions: dict[str, object]) -> object:
    return SimpleNamespace(id=modelo_id, revisions=revisions)


def _modelo(modelo_id: str, revisions: dict[str, object]) -> ModeloDefinition:
    from typing import cast

    return cast("ModeloDefinition", _modelo_payload(modelo_id, revisions))


def test_a_registry_without_a_projected_modelo_omits_that_fact_and_keeps_the_rest() -> None:
    """A partial registry cannot carry a fact projected from a modelo it lacks.

    Refusing the whole compilation instead made a partial registry impossible to
    validate: the isolated candidate a generated tree is checked against holds
    one modelo by design, and these two targets pull a transitive closure of
    nineteen, so satisfying the demand would have put nearly the entire registry
    into every candidate and left the isolation meaning nothing.
    """
    facts = compile_modelo_parameter_projection_facts((_modelo_347(),))

    projected = {fact.fact_id for fact in facts}
    assert ModeloParameterFact.M347_COUNTERPARTY_ANNUAL_THRESHOLD in projected


def test_an_omitted_projection_is_absent_rather_than_defaulted() -> None:
    """Nothing stands in for the missing modelo's facts.

    An omitted projection publishes NO variant, so a caller asking for it fails
    at resolution, where the boundary knows what the value was for. A default or
    a zero here would be the silent under-declaration this registry refuses.
    """
    facts = compile_modelo_parameter_projection_facts((_modelo_347(),))

    projected = {fact.fact_id for fact in facts}
    assert ModeloParameterFact.MATERNITY_MONTHLY_DEDUCTION not in projected
    assert not any(fact.variants == () for fact in facts), "an empty fact is a stand-in, not an omission"


def test_a_complete_registry_still_projects_every_target() -> None:
    """The omission must not weaken the whole registry, which contains both targets."""
    facts = compile_modelo_parameter_projection_facts((_modelo_100(), _modelo_347()))

    projected = {fact.fact_id for fact in facts}
    assert ModeloParameterFact.M347_COUNTERPARTY_ANNUAL_THRESHOLD in projected
    assert ModeloParameterFact.MATERNITY_MONTHLY_DEDUCTION in projected
