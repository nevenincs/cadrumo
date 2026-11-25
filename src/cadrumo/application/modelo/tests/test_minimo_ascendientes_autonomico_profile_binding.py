"""Casilla 0516, the autonomic mínimo por ascendientes, from stored rows through the real resolver.

LIRPF art. 56.3 computes the autonomic mínimo from the art. 59 amounts as the
comunidad of residence raised or lowered them under Ley 22/2009 art. 46.1.a), and
from the state amounts where it set none. The expected figures are read here from
the official text, not from the registry: each edition's Manual práctico de Renta
(parte 1, cap. 14) prints, for every comunidad that approved its own mínimos, a
section with its "Mínimo por ascendientes", and a comunidad without such a section
applies the state figures of LIRPF art. 59, written below from the statute. A wrong
registry row therefore fails the test.

Every supported year is enumerated from the registry's support envelope; a year
without its own edition reads the manual of the edition it is projected from.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from importlib.resources import files

import pytest

from cadrumo.domain.user_profile.values import create_user_profile_record

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
from ..profile_binding import resolve_profile_sourced_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_BUCKET = "0de41ce4-0000-4000-8000-000000000516"
_T0 = datetime(1980, 8, 5, 10, 0, tzinfo=UTC)
_BINDING = "renta-profile-minimo-ascendientes-autonomico"
_STATE_BINDING = "renta-profile-minimo-ascendientes-estatal"
_CASILLA = "0516"
_GROUP = "renta_family.ascendiente"

# LIRPF art. 59.1 and 59.2, the figures a comunidad without its own applies.
_STATE_BASE = Decimal("1150")
_STATE_OVER_75 = Decimal("1400")

# The heading each comunidad's section opens with in the manual, when it has one.
_MANUAL_HEADINGS = {
    "madrid": "Comunidad de Madrid:",
    "andalucia": "Comunidad Autónoma de Andalucía:",
    "aragon": "Comunidad Autónoma de Aragón:",
}
_SECTION_END = re.compile(
    r"^(?:(?:Comunidad|Comunitat)[^\n]*: Import|Cuadro comparativo|Ejemplos prácticos)", re.MULTILINE
)
_AMOUNT = r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)"
_BASE_TEXT = re.compile(_AMOUNT + r" euros anuales")
_OVER_75_TEXT = re.compile(r"Más " + _AMOUNT + r" euros anuales por cada ascendiente mayor de 75")


def _euros(text: str) -> Decimal:
    return Decimal(text.replace(".", "").replace(",", "."))


def _snapshot(year: int) -> RegistrySnapshot:
    return published_snapshot("100", filing_year=year, period="0A")


def _manual_amounts(year: int, ccaa: str) -> tuple[Decimal, Decimal]:
    """The art. 59.1 cuantía and 59.2 increment the edition's manual prints for ``ccaa``."""
    edition = _snapshot(year).authored_filing_year or year
    manual = (
        files("cadrumo")
        .joinpath("_data", "corpus", "manuals", "renta", str(edition), "part1", "source.pdf.extracted.md")
        .read_text(encoding="utf-8")
    )
    heading = re.search(rf"^{re.escape(_MANUAL_HEADINGS[ccaa])}", manual, re.MULTILINE)
    if heading is None:
        return _STATE_BASE, _STATE_OVER_75
    end = _SECTION_END.search(manual, heading.end())
    section = manual[heading.end() : end.start() if end is not None else len(manual)]
    _, found, ascendientes = section.partition("Mínimo por ascendientes")
    if not found:
        return _STATE_BASE, _STATE_OVER_75
    base = _BASE_TEXT.search(ascendientes)
    over_75 = _OVER_75_TEXT.search(ascendientes)
    assert base is not None and over_75 is not None, (edition, ccaa)
    return _euros(base.group(1)), _euros(over_75.group(1))


def _born(year: int, age: int) -> date:
    """A birth date that gives ``age`` full years at 31 December of ``year``."""
    return date(year - age, 6, 1)


def _record(ccaa: str | None, *rows: dict[str, str]) -> UserProfileRecord:
    facts = [UserProfileFact(path="renta_family.ascendientes_count", value=str(len(rows)))]
    if ccaa is not None:
        facts.append(UserProfileFact(path="tax_residence.ccaa", value=ccaa))
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


def _casilla(year: int, casilla_id: str, resolution: CalculationSourceResolution) -> Decimal | None:
    """Evaluate the edition's formula for ``casilla_id``, or ``None`` when it cannot settle."""
    snapshot = _snapshot(year)
    (formula,) = (formula for formula in snapshot.revision.formulas if formula.target_casilla_id == casilla_id)
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


def _mother_over_75(year: int) -> dict[str, str]:
    """The asalariada-familia ascendant: 78 at year end, living with the filer alone, below the ceilings."""
    return {
        "birth_date": _born(year, 78).isoformat(),
        "convivientes": "1",
        "convivencia_mitad_periodo": "true",
        "rentas_anuales": "7200.00",
        "declaracion_propia": "false",
    }


@pytest.mark.parametrize("ccaa", sorted(_MANUAL_HEADINGS))
@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_an_ascendant_over_75_reaches_casilla_0516_at_the_comunidad_amounts_in_every_supported_year(
    year: int, ccaa: str, authority_operation: PinnedAuthorityOperation
) -> None:
    base, over_75 = _manual_amounts(year, ccaa)

    resolution = _resolve(year, _record(ccaa, _mother_over_75(year)), authority_operation)

    expected = base + over_75
    assert resolution.binding_values[_BINDING] == expected
    assert _BINDING not in resolution.unresolved_binding_ids
    assert _casilla(year, _CASILLA, resolution) == expected
    assert resolution.binding_values[_STATE_BINDING] == _STATE_BASE + _STATE_OVER_75


def test_the_manuals_give_madrid_its_own_amount_and_aragon_the_state_one_in_the_newest_edition() -> None:
    """The oracle itself distinguishes the two cases, so the test above covers both."""
    year = newest_authored_edition("100")

    assert _manual_amounts(year, "madrid") != (_STATE_BASE, _STATE_OVER_75)
    assert _manual_amounts(year, "aragon") == (_STATE_BASE, _STATE_OVER_75)


def test_the_comunidad_amount_is_shared_and_aged_as_the_state_one(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    year = newest_authored_edition("100")
    base, _ = _manual_amounts(year, "madrid")
    under_75 = {
        "birth_date": _born(year, 70).isoformat(),
        "convivientes": "2",
        "convivencia_mitad_periodo": "true",
        "rentas_anuales": "5000.00",
        "declaracion_propia": "false",
    }
    dead_in_period = {
        "birth_date": _born(year, 85).isoformat(),
        "fallecimiento": date(year, 9, 30).isoformat(),
        "convivientes": "1",
        "convivencia_mitad_periodo": "true",
        "rentas_anuales": "1000.00",
    }

    resolution = _resolve(year, _record("madrid", under_75, dead_in_period), authority_operation)

    # Art. 61 norma 4ª: the death cuantía is not an art. 59 amount, so it stays the state one.
    assert resolution.binding_values[_BINDING] == base / 2 + _STATE_BASE


def test_a_filer_with_no_entitled_ascendant_has_a_zero_autonomic_minimum_without_a_comunidad(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    year = newest_authored_edition("100")

    resolution = _resolve(year, _record(None), authority_operation)

    assert resolution.binding_values[_BINDING] == Decimal("0")
    assert _casilla(year, _CASILLA, resolution) == Decimal("0")


def test_an_entitled_ascendant_without_a_stated_comunidad_withholds_only_casilla_0516(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    year = newest_authored_edition("100")

    resolution = _resolve(year, _record(None, _mother_over_75(year)), authority_operation)

    assert _BINDING not in resolution.binding_values
    assert _BINDING in resolution.unresolved_binding_ids
    assert _casilla(year, _CASILLA, resolution) is None
    assert resolution.binding_values[_STATE_BINDING] == _STATE_BASE + _STATE_OVER_75


def test_an_unstated_row_fact_withholds_both_parts(authority_operation: PinnedAuthorityOperation) -> None:
    year = newest_authored_edition("100")
    row = _mother_over_75(year)
    del row["convivientes"]

    resolution = _resolve(year, _record("madrid", row), authority_operation)

    assert {_BINDING, _STATE_BINDING} <= set(resolution.unresolved_binding_ids)
    assert _casilla(year, _CASILLA, resolution) is None
