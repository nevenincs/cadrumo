"""Casilla 0515, the mínimo por ascendientes, from stored ascendant rows through the real resolver.

The expected figures are the statute's own: LIRPF art. 59.1 grants 1.150 euros for an
ascendant of 65 or more (or with a disability), art. 59.2 adds 1.400 euros from 75,
art. 61 norma 4ª grants a flat 1.150 euros for an ascendant who dies in the period,
and art. 61 norma 1ª shares the amount equally among the descendants entitled. They
are written here from the law rather than read back from the registry, so a wrong
registry figure fails the test.

Every supported year is enumerated from the registry's support envelope. A row whose
share depends on a fact it does not state withholds the casilla: the binding is
reported unresolved and a ``household_row_fact_unstated`` note names the leaf.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.user_profile.values import create_user_profile_record

from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.formula_expression import evaluate_expression
from ....domain.calculations.registry.formula_runtime_ops import UnresolvedFormulaDependencyError, apply_rounding
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_edition
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context,
    published_snapshot,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ...aggregation.source_mesh import CalculationSourceResolution
from ...operator_actions.models import PreconditionVerdict
from ..calculation_notes import note_fact_text
from ..profile_binding import resolve_profile_sourced_bindings
from ..profile_derived_facts import ProfileBindingResolutionError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_BUCKET = "0de41ce4-0000-4000-8000-000000000515"
_T0 = datetime(1980, 8, 5, 10, 0, tzinfo=UTC)
_BINDING = "renta-profile-minimo-ascendientes-estatal"
_CASILLA = "0515"
_GROUP = "renta_family.ascendiente"

# LIRPF art. 59.1, art. 59.2 and art. 61 norma 4ª.
_BASE = Decimal("1150")
_OVER_75 = Decimal("1400")
_DEATH = Decimal("1150")


def _snapshot(year: int) -> RegistrySnapshot:
    return published_snapshot("100", filing_year=year, period="0A")


def _born(year: int, age: int) -> date:
    """A birth date that gives ``age`` full years at 31 December of ``year``."""
    return date(year - age, 6, 1)


def _record(*rows: dict[str, str]) -> UserProfileRecord:
    facts = [UserProfileFact(path="renta_family.ascendientes_count", value=str(len(rows)))]
    for index, row in enumerate(rows):
        facts.extend(UserProfileFact(path=f"{_GROUP}.{index}.{leaf}", value=value) for leaf, value in row.items())
    return create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=tuple(facts),
        created_at=_T0,
        updated_at=_T0,
        context=leased_profile_create_context(),
    )


def _resolve(year: int, record: UserProfileRecord, operation: PinnedAuthorityOperation) -> CalculationSourceResolution:
    return resolve_profile_sourced_bindings(
        _snapshot(year), bucket_id=_BUCKET, profile_record=record, operation=operation
    )


def _casilla_0515(year: int, resolution: CalculationSourceResolution) -> Decimal | None:
    """Evaluate the edition's 0515 formula over the resolved bindings, or ``None`` when it cannot settle."""
    snapshot = _snapshot(year)
    (formula,) = (formula for formula in snapshot.revision.formulas if formula.target_casilla_id == _CASILLA)
    try:
        value = evaluate_expression(
            formula.expression,
            values={},
            binding_values=resolution.binding_values,
            parameters={parameter.id: parameter for parameter in snapshot.revision.parameters},
            date_context={"filing_period": date(year, 12, 31)},
            relation_values={},
            unresolved_relation_ids=frozenset(),
            unresolved_casilla_ids=set(),
            operand_refs=[],
            operand_casilla_refs=[],
            operand_values=[],
            unresolved_binding_ids=frozenset(resolution.unresolved_binding_ids),
            filing_year=snapshot.filing_year,
        )
    except UnresolvedFormulaDependencyError:
        return None
    return apply_rounding(value, formula.rounding)


# The leaves the art. 59/61 share turns on; the row's identity leaves are another gate's notes.
_DECIDING_LEAVES = frozenset(
    {
        "birth_date",
        "convivientes",
        "convivencia_mitad_periodo",
        "rentas_anuales",
        "declaracion_propia",
        "discapacidad",
        "incapacidad_judicial",
    }
)


def _unstated_leaves(resolution: CalculationSourceResolution) -> set[str]:
    leaves: set[str] = set()
    for diagnostic in resolution.diagnostics:
        if diagnostic.reason != "household_row_fact_unstated" or diagnostic.fact is None:
            continue
        values = dict(diagnostic.fact.values)
        if values.get("group") == _GROUP and values.get("leaf") in _DECIDING_LEAVES:
            leaves.add(str(values["leaf"]))
    return leaves


def _unstated_rows(resolution: CalculationSourceResolution, leaf: str) -> tuple[str, ...]:
    """The 0-based stored positions the note for ``leaf`` names, which the edit door takes as its index."""
    (rows,) = (
        diagnostic.fact.row_refs
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "household_row_fact_unstated"
        and diagnostic.fact is not None
        and diagnostic.fact.row_refs
        and dict(diagnostic.fact.values).get("leaf") == leaf
    )
    return rows


@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_one_ascendant_over_65_and_one_over_75_reach_casilla_0515_in_every_supported_year(
    year: int, authority_operation: PinnedAuthorityOperation
) -> None:
    record = _record(
        {
            "birth_date": _born(year, 70).isoformat(),
            "convivientes": "1",
            "convivencia_mitad_periodo": "true",
            "rentas_anuales": "5000.00",
            "declaracion_propia": "false",
        },
        {
            "birth_date": _born(year, 80).isoformat(),
            "convivientes": "2",
            "convivencia_mitad_periodo": "true",
            "rentas_anuales": "7999.99",
            "declaracion_propia": "false",
        },
    )

    resolution = _resolve(year, record, authority_operation)

    expected = _BASE + (_BASE + _OVER_75) / 2
    assert resolution.binding_values[_BINDING] == expected
    assert _BINDING not in resolution.unresolved_binding_ids
    assert not _unstated_leaves(resolution)
    assert _casilla_0515(year, resolution) == expected


def test_a_filer_with_no_ascendant_has_a_zero_minimum(authority_operation: PinnedAuthorityOperation) -> None:
    year = newest_authored_edition("100")
    resolution = _resolve(year, _record(), authority_operation)

    assert resolution.binding_values[_BINDING] == Decimal("0")
    assert _casilla_0515(year, resolution) == Decimal("0")


def test_an_ascendant_who_dies_in_the_period_takes_the_flat_cuantia(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    year = newest_authored_edition("100")
    record = _record(
        {
            "birth_date": _born(year, 85).isoformat(),
            "fallecimiento": date(year, 9, 30).isoformat(),
            "convivientes": "1",
            # Art. 61 norma 5ª counts the half period up to the death.
            "convivencia_mitad_periodo": "true",
            "rentas_anuales": "1000.00",
        },
        {
            "birth_date": _born(year, 90).isoformat(),
            "fallecimiento": date(year - 1, 9, 30).isoformat(),
        },
    )

    resolution = _resolve(year, record, authority_operation)

    assert resolution.binding_values[_BINDING] == _DEATH


def test_a_stated_disqualifying_fact_makes_the_missing_ones_irrelevant(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    year = newest_authored_edition("100")
    record = _record(
        {"birth_date": _born(year, 70).isoformat(), "rentas_anuales": "8000.01"},
        {
            "birth_date": _born(year, 50).isoformat(),
            "discapacidad": "0",
            "incapacidad_judicial": "false",
            "convivientes": "1",
        },
        {"birth_date": _born(year, 70).isoformat(), "convivientes": "0"},
        {
            "birth_date": _born(year, 70).isoformat(),
            "convivientes": "1",
            "rentas_anuales": "1800.01",
            "declaracion_propia": "true",
        },
    )

    resolution = _resolve(year, record, authority_operation)

    assert resolution.binding_values[_BINDING] == Decimal("0")
    assert not _unstated_leaves(resolution)


def test_an_ascendant_under_65_with_a_disability_is_entitled(authority_operation: PinnedAuthorityOperation) -> None:
    year = newest_authored_edition("100")
    record = _record(
        {
            "birth_date": _born(year, 50).isoformat(),
            "discapacidad": "33",
            "convivientes": "1",
            "convivencia_mitad_periodo": "true",
            "rentas_anuales": "0",
        }
    )

    resolution = _resolve(year, record, authority_operation)

    assert resolution.binding_values[_BINDING] == _BASE


_COMPLETE = {
    "convivientes": "1",
    "convivencia_mitad_periodo": "true",
    "rentas_anuales": "5000.00",
    "declaracion_propia": "false",
}


@pytest.mark.parametrize(
    ("age", "omitted", "stated", "leaf"),
    [
        (70, "convivientes", {}, "convivientes"),
        (70, "convivencia_mitad_periodo", {}, "convivencia_mitad_periodo"),
        (70, "rentas_anuales", {}, "rentas_anuales"),
        (50, None, {"incapacidad_judicial": "false"}, "discapacidad"),
        (50, None, {"discapacidad": "0"}, "incapacidad_judicial"),
    ],
)
def test_each_unstated_deciding_fact_withholds_casilla_0515(
    age: int, omitted: str | None, stated: dict[str, str], leaf: str, authority_operation: PinnedAuthorityOperation
) -> None:
    year = newest_authored_edition("100")
    row = {"birth_date": _born(year, age).isoformat(), **_COMPLETE, **stated}
    if omitted is not None:
        del row[omitted]
    complete = {"birth_date": _born(year, 80).isoformat(), **_COMPLETE}

    resolution = _resolve(year, _record(complete, row), authority_operation)

    assert _BINDING not in resolution.binding_values
    assert _BINDING in resolution.unresolved_binding_ids
    assert _unstated_leaves(resolution) == {leaf}
    assert _unstated_rows(resolution, leaf) == ("1",)
    assert _casilla_0515(year, resolution) is None
    _assert_every_note_reads_in_words(resolution)


def _assert_every_note_reads_in_words(resolution: CalculationSourceResolution) -> None:
    """Every note renders in each language and names the missing fact by its words."""
    facts = [
        diagnostic.fact
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "household_row_fact_unstated" and diagnostic.fact is not None
    ]
    assert facts
    for fact in facts:
        leaf = dict(fact.values)["leaf"]
        for language in SUPPORTED_OUTPUT_LANGUAGES:
            words = tr(f"application.modelo.calc_diagnostic_words.household_leaf.{leaf}", locale=language)
            assert words in note_fact_text(fact, locale=language), (language, leaf)


def test_an_unstated_own_return_withholds_only_above_the_norma_2_figure(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    year = newest_authored_edition("100")
    stated = {"birth_date": _born(year, 70).isoformat(), "convivientes": "1", "convivencia_mitad_periodo": "true"}
    below = {**stated, "rentas_anuales": "1800.00"}
    above = {**stated, "rentas_anuales": "1800.01"}

    assert _resolve(year, _record(below), authority_operation).binding_values[_BINDING] == _BASE
    withheld = _resolve(year, _record(above), authority_operation)
    assert _BINDING in withheld.unresolved_binding_ids
    assert _unstated_leaves(withheld) == {"declaracion_propia"}


def test_a_stored_value_the_row_refuses_opens_the_edit_of_that_row(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    year = newest_authored_edition("100")
    stated = {"birth_date": _born(year, 70).isoformat(), "convivientes": "1", "rentas_anuales": "1800.00"}
    refused = {**stated, "convivientes": "uno"}

    with pytest.raises(ProfileBindingResolutionError) as raised:
        _resolve(year, _record(stated, refused), authority_operation)

    verdict = raised.value.terminal_precondition_verdict
    assert isinstance(verdict, PreconditionVerdict)
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.profile.ascendiente.edit"
    assert {binding.argument_name: binding.value for binding in verdict.argument_bindings} == {
        "index": 1,
        "ascendiente": None,
    }
    assert verdict.missing_argument_names == ("ascendiente",)
    assert dict(verdict.evidence[0].values)["leaf"] == "convivientes"
