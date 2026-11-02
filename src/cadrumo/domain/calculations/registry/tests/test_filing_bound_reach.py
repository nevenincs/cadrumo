"""Which bindings and casillas reach an exported box, derived on a revision built by hand.

Each expectation is read off the hand-built graph below, not off the function
under test: box 01 and box 04 are the only boxes carrying ``export_refs``, and
every edge into them is declared here. A box an XML dictionary emits is
exported too, though it carries no ``export_refs``.
"""

from __future__ import annotations

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from ..errors import RegistryValidationError
from ..filing_bound_reach import filing_bound_reach, filing_bound_reach_digest, official_export_casilla_ids
from ..schema import FormulaDefinition, ModeloRevision
from ..schema_exports import ExportLayoutDefinition
from ..schema_formula import FormulaExpression
from ..schema_input_kind import InputKind
from ._referential_integrity_support import (
    REFERENCE_LEGAL_ID,
    REFERENCE_SOURCE_ID,
    minimal_revision,
    minimal_source_ref,
    segmented_casilla,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DIRECT = validated_casilla_id("01")
_FED = validated_casilla_id("02")
_INTERNAL = validated_casilla_id("03")
_TOTAL = validated_casilla_id("04")
_UNEXPORTED = validated_casilla_id("05")
_VERIFIED_ONLY = validated_casilla_id("06")


def _bound(casilla_id: CasillaId, binding: str, *, alternates: tuple[str, ...] = (), exported: bool = False):
    update: dict[str, object] = {"input_kind": InputKind.BOUND, "binding": binding, "alternate_bindings": alternates}
    if exported:
        update["export_refs"] = (f"test.field.{casilla_id}",)
    return segmented_casilla(casilla_id, str(casilla_id), None).model_copy(update=update)


def _computed(casilla_id: CasillaId, formula: str, *, exported: bool = False, internal_only: bool = False):
    update: dict[str, object] = {"input_kind": InputKind.COMPUTED, "formula": formula, "internal_only": internal_only}
    if exported:
        update["export_refs"] = (f"test.field.{casilla_id}",)
    return segmented_casilla(casilla_id, str(casilla_id), None).model_copy(update=update)


def _formula(formula_id: str, target: CasillaId, expression: FormulaExpression) -> FormulaDefinition:
    return FormulaDefinition(
        id=formula_id,
        target_casilla_id=target,
        expression=expression,
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )


def _revision(grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING) -> ModeloRevision:
    """Box 01 exported and bound directly; box 02 feeds internal box 03, which with an operand feeds exported box 04.

    Box 05 is bound but exported nowhere and read by no formula; box 06 is read
    by a formula only for a box that is itself not exported.
    """
    casillas = (
        _bound(_DIRECT, "b-direct", exported=True),
        _bound(_FED, "b-primary", alternates=("b-alternate",)),
        _computed(_INTERNAL, "f-internal", internal_only=True),
        _computed(_TOTAL, "f-total", exported=True),
        _bound(_UNEXPORTED, "b-unexported"),
        _computed(_VERIFIED_ONLY, "f-unexported"),
    )
    formulas = (
        _formula("f-internal", _INTERNAL, FormulaExpression(casilla_id=_FED)),
        _formula(
            "f-total",
            _TOTAL,
            FormulaExpression(
                op="add", args=(FormulaExpression(casilla_id=_INTERNAL), FormulaExpression(binding="b-operand"))
            ),
        ),
        _formula("f-unexported", _VERIFIED_ONLY, FormulaExpression(binding="b-working-only")),
    )
    return minimal_revision(casillas=casillas, formulas=formulas).model_copy(update={"authority_grade": grade})


def _reach(revision: ModeloRevision):
    return filing_bound_reach(revision, exported=official_export_casilla_ids(revision))


def test_a_binding_bound_to_an_exported_box_reaches_that_box() -> None:
    assert _reach(_revision()).binding_reach("b-direct") == (_DIRECT,)


def test_a_primary_and_an_alternate_binding_reach_through_an_internal_box() -> None:
    reach = _reach(_revision())

    assert reach.binding_reach("b-primary") == (_TOTAL,)
    assert reach.binding_reach("b-alternate") == (_TOTAL,)
    assert reach.casilla_reach(_INTERNAL) == (_TOTAL,)
    assert reach.casilla_reach(_FED) == (_TOTAL,)


def test_a_formula_operand_reaches_the_exported_box_its_formula_feeds() -> None:
    assert _reach(_revision()).binding_reach("b-operand") == (_TOTAL,)


def test_an_exported_box_reaches_itself() -> None:
    reach = _reach(_revision())

    assert reach.casilla_reach(_DIRECT) == (_DIRECT,)
    assert reach.casilla_reach(_TOTAL) == (_TOTAL,)


def test_a_figure_that_reaches_no_exported_box_is_not_filing_bound() -> None:
    reach = _reach(_revision())

    assert reach.binding_reach("b-unexported") == ()
    assert reach.binding_reach("b-working-only") == ()
    assert reach.casilla_reach(_UNEXPORTED) == ()
    assert reach.casilla_reach(_VERIFIED_ONLY) == ()
    assert set(reach.bindings) == {"b-direct", "b-primary", "b-alternate", "b-operand"}


@pytest.mark.parametrize(
    "grade", [grade for grade in RegistryAuthorityGrade if grade is not RegistryAuthorityGrade.FILING]
)
def test_nothing_of_a_revision_below_the_filing_rung_is_filing_bound(grade: RegistryAuthorityGrade) -> None:
    reach = _reach(_revision(grade))

    assert dict(reach.bindings) == {}
    assert dict(reach.casillas) == {}


def test_the_digest_moves_when_the_filing_bound_set_does() -> None:
    filing = filing_bound_reach_digest(_reach(_revision()))
    unexported_total = _revision().model_copy(
        update={
            "casillas": tuple(
                casilla.model_copy(update={"export_refs": ()}) if casilla.id == _TOTAL else casilla
                for casilla in _revision().casillas
            )
        }
    )

    assert filing == filing_bound_reach_digest(_reach(_revision()))
    assert filing != filing_bound_reach_digest(_reach(unexported_total))


_DICTIONARY_SOURCE = minimal_source_ref().model_copy(update={"kind": "dictionary"})


def _with_dictionary_layout(revision: ModeloRevision) -> ModeloRevision:
    layout = ExportLayoutDefinition(
        id="test-xml-dictionary",
        format="xml_dictionary",
        dictionary_source_ref=_DICTIONARY_SOURCE.id,
        source_refs=(_DICTIONARY_SOURCE.id,),
        legal_refs=(REFERENCE_LEGAL_ID,),
        aux_idioma="E",
    )
    return revision.model_copy(update={"export_layouts": (layout,)})


def test_a_box_an_xml_dictionary_emits_is_exported_without_export_refs() -> None:
    """Box 05 reaches no box with ``export_refs``; the dictionary naming it makes its binding filing-bound."""
    revision = _with_dictionary_layout(_revision())
    payload = b"UNEXPORTED=[/Declaracion/Unexported][N][05][Box 05]"
    exported = official_export_casilla_ids(
        revision, sources={_DICTIONARY_SOURCE.id: _DICTIONARY_SOURCE}, source_payloads={_DICTIONARY_SOURCE.id: payload}
    )
    reach = filing_bound_reach(revision, exported=exported)

    assert exported == {_DIRECT, _TOTAL, _UNEXPORTED}
    assert reach.binding_reach("b-unexported") == (_UNEXPORTED,)
    assert reach.binding_reach("b-working-only") == ()


def test_an_xml_dictionary_without_its_published_bytes_refuses_rather_than_exporting_nothing() -> None:
    revision = _with_dictionary_layout(_revision())

    with pytest.raises(RegistryValidationError, match="published sources"):
        official_export_casilla_ids(revision)
