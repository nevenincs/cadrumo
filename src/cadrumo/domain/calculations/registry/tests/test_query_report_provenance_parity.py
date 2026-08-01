"""Cross-projection provenance parity for registry casilla query reports.

The casilla *list* row and the casilla *detail* report describe the same
casilla's legal grounding. Operator JSON is projected from both, so a legal or
source reference shape one projection refuses must not pass through the other:
otherwise a list response can carry provenance that the detail response would
reject, and the grounding contract differs by which verb the operator ran.

These tests pin the shared annotation and the refusal behaviour on real
pydantic validation, with no fixtures or doubles.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .. import CasillaId, validated_casilla_id
from .._query_reports import ModeloCasillaDetailReport, ModeloCasillaRow
from .._schema import InputKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CASILLA: CasillaId = validated_casilla_id("01", surface="_CASILLA")

_VALID_LEGAL_REF = "ley-35-2006:art-27"
_VALID_SOURCE_REF = "aeat-manual-renta-2024"

#: The audit's literal probe values: free prose carrying spaces, which the
#: canonical ``LegalRefId``/``SourceRefId`` patterns refuse.
_INVALID_LEGAL_REF = "NOT VALID REF"
_INVALID_SOURCE_REF = "NOT VALID SOURCE"


def _row(
    *,
    legal_refs: tuple[str, ...] = (_VALID_LEGAL_REF,),
    source_refs: tuple[str, ...] = (_VALID_SOURCE_REF,),
) -> ModeloCasillaRow:
    return ModeloCasillaRow(
        casilla_id=_CASILLA,
        number="01",
        label="Rendimientos íntegros",
        section=("actividades",),
        data_type="decimal",
        input_kind=InputKind.MANUAL,
        required=True,
        formula=None,
        binding=None,
        form_number=None,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def _detail(
    *,
    legal_refs: tuple[str, ...] = (_VALID_LEGAL_REF,),
    source_refs: tuple[str, ...] = (_VALID_SOURCE_REF,),
) -> ModeloCasillaDetailReport:
    return ModeloCasillaDetailReport(
        code="130",
        revision="2019-y-siguientes",
        filing_year=2024,
        period="1T",
        casilla_id=_CASILLA,
        number="01",
        label="Rendimientos íntegros",
        section=("actividades",),
        data_type="decimal",
        input_kind=InputKind.MANUAL,
        required=True,
        legal_refs=legal_refs,
        source_refs=source_refs,
        binding=None,
        formula_id=None,
        formula_expression=None,
    )


def test_both_projections_accept_the_same_valid_grounding() -> None:
    """A well-formed reference pair survives both projections unchanged."""
    row = _row()
    detail = _detail()

    assert row.legal_refs == (_VALID_LEGAL_REF,)
    assert row.source_refs == (_VALID_SOURCE_REF,)
    assert detail.legal_refs == row.legal_refs
    assert detail.source_refs == row.source_refs


def test_list_row_refuses_the_legal_ref_the_detail_report_refuses() -> None:
    """The list row must not admit a legal ref the detail report rejects."""
    with pytest.raises(ValidationError) as detail_error:
        _detail(legal_refs=(_INVALID_LEGAL_REF,))

    with pytest.raises(ValidationError) as row_error:
        _row(legal_refs=(_INVALID_LEGAL_REF,))

    assert "legal_refs" in str(detail_error.value)
    assert "legal_refs" in str(row_error.value)


def test_list_row_refuses_the_source_ref_the_detail_report_refuses() -> None:
    """The list row must not admit a source ref the detail report rejects."""
    with pytest.raises(ValidationError) as detail_error:
        _detail(source_refs=(_INVALID_SOURCE_REF,))

    with pytest.raises(ValidationError) as row_error:
        _row(source_refs=(_INVALID_SOURCE_REF,))

    assert "source_refs" in str(detail_error.value)
    assert "source_refs" in str(row_error.value)


@pytest.mark.parametrize("field", ("legal_refs", "source_refs"))
def test_list_and_detail_declare_one_grounding_annotation(field: str) -> None:
    """Pin the annotations equal so the two projections cannot drift apart.

    Without this the reference constraint can be relaxed on one projection
    while every behavioural test that only exercises the other stays green.
    """
    row_annotation = ModeloCasillaRow.model_fields[field].annotation
    detail_annotation = ModeloCasillaDetailReport.model_fields[field].annotation

    assert row_annotation == detail_annotation
