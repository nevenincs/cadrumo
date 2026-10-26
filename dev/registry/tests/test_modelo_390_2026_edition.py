"""Modelo 390 ejercicio 2026 follows the form Orden HAC/27/2026 approves, at applicability grade.

The Orden replaces the modelo 390 form from ejercicio 2026 and adds one box,
[112], the pago a cuenta on fuel supplies deducted in the year, which the form's
own caption subtracts from the result of the liquidation. AEAT has not
published the matching diseno de registro, so the edition carries no generated
export layout and claims no filing grade; the previous edition is unchanged.
"""

from __future__ import annotations

from datetime import date
from functools import cache

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.errors import RegistryFailureCondition, RegistryValidationError
from cadrumo.domain.calculations.registry.schema import (
    FormulaDefinition,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
)
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection
from cadrumo.domain.calculations.registry.temporal import revision_temporal_resolution, select_revision

from ..compiler.authority import compiled_bundled_authority
from ..conformance.registry_schema_support import committed_modelo
from .authored_edition_support import legal_text_match

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NEW_BOX = "iva.anual.pago-cuenta-carburantes-deposito-fiscal"
_RESULT = "iva.anual.resultado-liquidacion"
_FORM = "boe-modelo-390-2026-form"
_DAYS = {"treinta": 30, "treinta y un": 31}


@cache
def _modelo() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return committed_modelo("390")


@cache
def _first_year() -> int:
    """The ejercicio the replaced form first governs, read from the Orden's final provision."""
    pattern = r"modelo 390, correspondiente al ejercicio (\d{4})"
    return int(legal_text_match("orden-hac-27-2026:disposicion-final-unica", pattern).group(1))


def _selected(year: int) -> ModeloRevision:
    modelo, catalogues = _modelo()
    return select_revision(modelo, filing_year=year, period="0A", support=catalogues.supported_filing_years)


def _references(expression: object) -> set[str]:
    found: set[str] = set()
    casilla = getattr(expression, "casilla_id", None)
    if casilla is not None:
        found.add(str(casilla))
    for arg in getattr(expression, "args", ()) or ():
        found |= _references(arg)
    return found


def _result_formula(revision: ModeloRevision) -> FormulaDefinition:
    (formula,) = (formula for formula in revision.formulas if str(formula.target_casilla_id) == _RESULT)
    return formula


def test_the_first_year_of_the_new_form_is_authored_at_applicability_grade() -> None:
    _, catalogues = _modelo()
    year = _first_year()
    revision = _selected(year)
    resolution = revision_temporal_resolution(
        revision, filing_year=year, period="0A", support=catalogues.supported_filing_years
    )

    assert resolution.projection_direction is TemporalProjectionDirection.AUTHORED
    assert revision.authority_grade is RegistryAuthorityGrade.APPLICABILITY
    assert revision.export_layouts == ()
    assert _selected(year - 1).authority_grade is RegistryAuthorityGrade.FILING
    assert _selected(year - 1).export_layouts


def test_box_112_is_new_on_the_form_and_enters_the_result() -> None:
    year = _first_year()
    current, previous = _selected(year), _selected(year - 1)

    (box,) = (casilla for casilla in current.casillas if str(casilla.id) == _NEW_BOX)
    assert box.number == "112"
    assert _FORM in box.source_refs
    assert _NEW_BOX not in {str(casilla.id) for casilla in previous.casillas}

    current_formula = _result_formula(current)
    assert _NEW_BOX in _references(current_formula.expression)
    assert _NEW_BOX not in _references(_result_formula(previous).expression)
    assert _FORM in {str(source) for source in current_formula.source_refs}


def test_the_window_follows_the_statutory_plazo_of_the_following_january() -> None:
    year = _first_year()
    words = legal_text_match(
        "orden-eha-3111-2009:art-8", r"en los ([a-z ]+?) primeros dias naturales del mes de enero siguiente"
    ).group(1)
    (window,) = _selected(year).deadline_windows
    assert window.filing_year == year
    assert (window.opens_on, window.closes_on) == (date(year + 1, 1, 1), date(year + 1, 1, _DAYS[words]))


def test_filing_grade_is_refused_for_the_new_form_and_kept_for_the_previous_year() -> None:
    authority = compiled_bundled_authority()
    year = _first_year()
    applicability = authority.snapshot("390", filing_year=year, period="0A", grade=RegistryAuthorityGrade.APPLICABILITY)
    assert str(applicability.revision.id) == str(_selected(year).id)
    with pytest.raises(RegistryValidationError) as refusal:
        authority.snapshot("390", filing_year=year, period="0A", grade=RegistryAuthorityGrade.FILING)
    failure = refusal.value.registry_failure
    assert failure is not None
    assert failure.condition is RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT
    assert authority.snapshot("390", filing_year=year - 1, period="0A").revision.authority_grade is (
        RegistryAuthorityGrade.FILING
    )
