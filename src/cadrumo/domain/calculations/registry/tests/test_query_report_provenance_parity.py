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

from collections.abc import Mapping

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.schema_input_kind import InputKind

from .....core import CasillaId, validated_casilla_id
from ..query_reports import CasillaGroundingReport, ModeloCasillaDetailReport, ModeloCasillaRow

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CASILLA: CasillaId = validated_casilla_id("01", surface="_CASILLA")

#: Casilla identity and grounding both projections must describe identically.
_SHARED_GROUNDING_FIELDS = (
    "casilla_id",
    "number",
    "label",
    "section",
    "data_type",
    "input_kind",
    "required",
    "binding",
    "legal_refs",
    "source_refs",
    "help_text",
)

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


def _pattern_failures(error: ValidationError, field: str) -> list[Mapping[str, object]]:
    """Return the pattern-mismatch entries this error raised for *field*."""
    return [entry for entry in error.errors() if entry["type"] == "string_pattern_mismatch" and field in entry["loc"]]


def test_both_projections_accept_the_same_valid_grounding() -> None:
    """POSITIVE CONTROL: a well-formed reference pair survives both projections.

    This passes under mutation (the loose ``tuple[str, ...]`` annotation also
    accepts valid references), so it is not proof that the fix landed. Its job
    is to remove the opposite ambiguity: without it, an annotation that
    rejected *everything* would satisfy the refusal tests below identically to
    one that rejects the right thing.

    Scope note: ``LegalRefId`` / ``SourceRefId`` are SHAPE contracts with no
    existence check. A well-formed but nonexistent reference
    (``totally-made-up:art-999``) is accepted here by design; closing that is a
    separate concern from the shape parity these tests pin.
    """
    row = _row()
    detail = _detail()

    assert row.legal_refs == (_VALID_LEGAL_REF,)
    assert row.source_refs == (_VALID_SOURCE_REF,)
    assert detail.legal_refs == row.legal_refs
    assert detail.source_refs == row.source_refs


def test_list_row_refuses_the_legal_ref_the_detail_report_refuses() -> None:
    """DISCRIMINATING: the list row rejects a legal ref on the pattern constraint.

    Fails when ``ModeloCasillaRow.legal_refs`` is the loose ``tuple[str, ...]``:
    the bad value is then accepted and no error is raised at all. The assertion
    cites the constraint this fix adds (``string_pattern_mismatch`` located on
    ``legal_refs``) rather than merely observing that *some* error occurred, so
    a sibling constraint firing elsewhere cannot satisfy it.
    """
    with pytest.raises(ValidationError) as detail_error:
        _detail(legal_refs=(_INVALID_LEGAL_REF,))

    with pytest.raises(ValidationError) as row_error:
        _row(legal_refs=(_INVALID_LEGAL_REF,))

    assert _pattern_failures(detail_error.value, "legal_refs")
    assert _pattern_failures(row_error.value, "legal_refs")


def test_list_row_refuses_the_source_ref_the_detail_report_refuses() -> None:
    """DISCRIMINATING: the list row rejects a source ref on the pattern constraint.

    Fails when ``ModeloCasillaRow.source_refs`` is the loose ``tuple[str, ...]``.
    Cites ``string_pattern_mismatch`` on ``source_refs`` for the same reason as
    the legal-ref case above.
    """
    with pytest.raises(ValidationError) as detail_error:
        _detail(source_refs=(_INVALID_SOURCE_REF,))

    with pytest.raises(ValidationError) as row_error:
        _row(source_refs=(_INVALID_SOURCE_REF,))

    assert _pattern_failures(detail_error.value, "source_refs")
    assert _pattern_failures(row_error.value, "source_refs")


@pytest.mark.parametrize("field", ("legal_refs", "source_refs"))
def test_list_and_detail_declare_one_grounding_annotation(field: str) -> None:
    """SUPPORTING: the two projections agree on the reference annotation.

    This is an anti-drift guard, not proof: it also passes if BOTH sides are
    relaxed back to ``tuple[str, ...]`` together. The proof that each side is
    actually constrained lives in the two refusal tests above, which assert
    the absolute behaviour rather than the relative agreement.
    """
    row_annotation = ModeloCasillaRow.model_fields[field].annotation
    detail_annotation = ModeloCasillaDetailReport.model_fields[field].annotation

    assert row_annotation == detail_annotation


@pytest.mark.parametrize("report_model", (ModeloCasillaRow, ModeloCasillaDetailReport))
def test_both_projections_derive_from_one_grounding_model(report_model: type) -> None:
    """DISCRIMINATING: each projection derives from the shared grounding model.

    Fails when either projection re-declares the casilla's identity and
    grounding independently (the pre-fix shape). Unlike the annotation
    equality above, this cannot be satisfied by two separate declarations
    that merely happen to agree.
    """
    assert issubclass(report_model, CasillaGroundingReport)


@pytest.mark.parametrize("field", _SHARED_GROUNDING_FIELDS)
def test_grounding_fields_are_declared_only_on_the_shared_model(field: str) -> None:
    """DISCRIMINATING: the shared grounding fields live on the shared model.

    Fails when a projection shadows a shared field with its own declaration,
    which is how the two views would drift apart again while each still
    validates its own inputs.
    """
    assert field in CasillaGroundingReport.model_fields
    assert field not in vars(ModeloCasillaRow).get("__annotations__", {})
    assert field not in vars(ModeloCasillaDetailReport).get("__annotations__", {})
