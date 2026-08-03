"""Shared-grounding parity for the modelo bindings list and preview payloads.

``bindings list`` and ``bindings resolve`` (preview) project the *same*
binding. Per `binding-values-carry-provenance` both must carry the binding's
``legal_refs`` / ``source_refs`` and typed source identity. Before the shared
:class:`BindingGroundingPayload` existed, each row declared that grounding
independently, so a constraint relaxed on one surface left the other silently
covered and operator list JSON could carry provenance the preview JSON refused.

The proof here is structural: the two rows must *derive* their grounding from
one model rather than happen to agree today.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._modelo_bindings_payloads import (
    BindingGroundingPayload,
    BindingListRowPayload,
    BindingPreviewRowPayload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: Identity and provenance both surfaces must describe identically.
_SHARED_GROUNDING_FIELDS = (
    "binding_id",
    "source",
    "readiness",
    "typed_enum",
    "legal_refs",
    "source_refs",
    "relation_inputs",
    "encoded_options",
)

_VALID_LEGAL_REF = "ley-35-2006:art-27"
_VALID_SOURCE_REF = "aeat-manual-renta-2024"
_INVALID_LEGAL_REF = "NOT VALID REF"


def _list_row(**overrides: object) -> BindingListRowPayload:
    return BindingListRowPayload.model_validate(
        {
            "modelo": "130",
            "revision": "2019-y-siguientes",
            "filing_year": 2024,
            "period": "1T",
            "binding_id": "ledger-ingresos",
            "source": "ledger_aggregation",
            "readiness": "ready",
            "typed_enum": None,
            "input_channel": "decimal",
            "borrador_capable": False,
            "legal_refs": (_VALID_LEGAL_REF,),
            "source_refs": (_VALID_SOURCE_REF,),
            **overrides,
        },
    )


def _preview_row(**overrides: object) -> BindingPreviewRowPayload:
    return BindingPreviewRowPayload.model_validate(
        {
            "binding_id": "ledger-ingresos",
            "source": "ledger_aggregation",
            "readiness": "ready",
            "typed_enum": None,
            "override": None,
            "legal_refs": (_VALID_LEGAL_REF,),
            "source_refs": (_VALID_SOURCE_REF,),
            **overrides,
        },
    )


@pytest.mark.parametrize("row_model", (BindingListRowPayload, BindingPreviewRowPayload))
def test_both_rows_derive_grounding_from_one_model(row_model: type) -> None:
    """DISCRIMINATING: each row derives from the shared grounding payload.

    Fails when either row re-declares the grounding fields independently
    (the pre-fix shape). This is the assertion that cannot be satisfied by
    two definitions that merely agree today, which is the drift this fix
    exists to prevent.
    """
    assert issubclass(row_model, BindingGroundingPayload)


@pytest.mark.parametrize("field", _SHARED_GROUNDING_FIELDS)
def test_grounding_fields_are_declared_only_on_the_shared_model(field: str) -> None:
    """DISCRIMINATING: the grounding fields live on the shared base.

    Fails when a row shadows a shared field with its own declaration, which
    is how the two surfaces would drift apart again while both still
    validate their own inputs.
    """
    assert field in BindingGroundingPayload.model_fields
    assert field not in vars(BindingListRowPayload).get("__annotations__", {})
    assert field not in vars(BindingPreviewRowPayload).get("__annotations__", {})


@pytest.mark.parametrize("field", _SHARED_GROUNDING_FIELDS)
def test_both_rows_expose_the_same_grounding_constraint(field: str) -> None:
    """SUPPORTING: the two rows agree on each shared field's constraint.

    Passes under mutation, because the pre-fix independent declarations were
    already identical -- that equality is exactly why the duplication was
    invisible. Kept as a regression readout of the contract itself.
    """
    list_field = BindingListRowPayload.model_fields[field]
    preview_field = BindingPreviewRowPayload.model_fields[field]

    assert list_field.annotation == preview_field.annotation
    assert list_field.metadata == preview_field.metadata


def test_both_rows_accept_well_formed_grounding() -> None:
    """POSITIVE CONTROL: valid grounding is accepted and carried through.

    Without this, the refusal tests below are ambiguous: a field annotated
    with a type that rejected *everything* would satisfy them identically to
    one that rejects the right thing. This proves the constraint discriminates
    rather than merely refusing.
    """
    for factory in (_list_row, _preview_row):
        row = factory()
        assert row.legal_refs == (_VALID_LEGAL_REF,)
        assert row.source_refs == (_VALID_SOURCE_REF,)


def test_both_rows_reject_a_malformed_legal_ref() -> None:
    """SUPPORTING: a bad legal ref is refused on both surfaces.

    Passes under mutation (both rows already carried ``LegalRefId``). It
    records the provenance contract the shared model now owns. The assertion
    names the constraint that fired (``string_pattern_mismatch`` on
    ``legal_refs``) so an unrelated refusal cannot read as proof.
    """
    for factory in (_list_row, _preview_row):
        with pytest.raises(ValidationError) as error:
            factory(legal_refs=(_INVALID_LEGAL_REF,))
        assert any(
            entry["type"] == "string_pattern_mismatch" and "legal_refs" in entry["loc"]
            for entry in error.value.errors()
        )


@pytest.mark.parametrize("field", ("legal_refs", "source_refs"))
def test_both_rows_require_non_empty_grounding(field: str) -> None:
    """SUPPORTING: empty provenance tuples are refused on both surfaces.

    Passes under mutation; documents that the shared model preserves the
    ``min_length=1`` grounding requirement. Asserts the specific ``too_short``
    constraint on the named field rather than a bare ``ValidationError``: a
    refusal raised for some unrelated reason would otherwise read as proof
    that the grounding requirement is enforced.
    """
    for factory in (_list_row, _preview_row):
        with pytest.raises(ValidationError) as error:
            factory(**{field: ()})
        assert any(
            entry["type"] == "too_short" and field in entry["loc"] for entry in error.value.errors()
        )
