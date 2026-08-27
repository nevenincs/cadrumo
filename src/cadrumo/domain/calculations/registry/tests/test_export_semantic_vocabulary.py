"""Strict schema proofs for canonical export semantic selectors."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....core import (
    FilingProducerKey,
    M303ProrrataActivityProjectionField,
    M303ProrrataActivityProjectionRef,
)
from ...export_field_kind import CasillaFieldKind
from ..export_semantics import (
    ExportComputedKey,
    ExportDraftAttribute,
    ExportSemanticPayloadAxis,
    export_semantic_payload_axis,
)
from ..schema_exports import ExportFieldDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _field_payload(kind: str, **semantic_payload: object) -> dict[str, object]:
    return {
        "id": "semantic-selector-proof",
        "offset": 1,
        "length": 4,
        "kind": kind,
        "data_type": "text",
        "required": False,
        "padding": "right_space",
        "justification": "left",
        "signed": False,
        "legal_refs": ("ley-58-2003:art-98",),
        "source_refs": ("aeat-dr-303-2025",),
        **semantic_payload,
    }


@pytest.mark.parametrize(
    ("kind", "payload", "axis"),
    (
        ("header", {"producer_key": FilingProducerKey.PRESENTER_TAX_ID}, ExportSemanticPayloadAxis.PRODUCER_KEY),
        ("draft", {"draft_attribute": ExportDraftAttribute.FILING_YEAR}, ExportSemanticPayloadAxis.DRAFT_ATTRIBUTE),
        ("computed", {"computed_key": ExportComputedKey.ENVELOPE_CLOSING_TAG}, ExportSemanticPayloadAxis.COMPUTED_KEY),
        (
            "projection",
            {
                "projection_ref": M303ProrrataActivityProjectionRef(
                    projection_kind="m303_prorrata_activity",
                    slot=1,
                    field=M303ProrrataActivityProjectionField.CNAE,
                    casilla_id="c500",
                ),
            },
            ExportSemanticPayloadAxis.PROJECTION_REF,
        ),
    ),
)
def test_strict_schema_accepts_only_enum_members_from_the_canonical_vocabulary(
    kind: str,
    payload: dict[str, object],
    axis: ExportSemanticPayloadAxis,
) -> None:
    field = ExportFieldDefinition.model_validate(_field_payload(kind, **payload))

    assert export_semantic_payload_axis(field.kind) is axis
    if axis is ExportSemanticPayloadAxis.PRODUCER_KEY:
        assert field.producer_key is FilingProducerKey.PRESENTER_TAX_ID
    elif axis is ExportSemanticPayloadAxis.DRAFT_ATTRIBUTE:
        assert field.draft_attribute is ExportDraftAttribute.FILING_YEAR
    elif axis is ExportSemanticPayloadAxis.COMPUTED_KEY:
        assert field.computed_key is ExportComputedKey.ENVELOPE_CLOSING_TAG
    else:
        assert isinstance(field.projection_ref, M303ProrrataActivityProjectionRef)


@pytest.mark.parametrize(
    ("kind", "payload", "deleted"),
    (
        ("header", {"producer_key": "presenter.tax_id"}, "producer_key"),
        ("header", {"header_key": "presenter_nif"}, "header_key"),
        ("draft", {"draft_attribute": "modelo"}, "modelo"),
        ("draft", {"draft_attribute": "period"}, "period"),
        ("computed", {"computed_key": "record_checksum"}, "record_checksum"),
    ),
)
def test_deleted_or_unproduced_tokens_fail_strict_schema_load(
    kind: str,
    payload: dict[str, object],
    deleted: str,
) -> None:
    with pytest.raises(ValidationError, match=deleted):
        ExportFieldDefinition.model_validate(_field_payload(kind, **payload))


def test_export_field_requires_exactly_the_payload_axis_matching_its_kind() -> None:
    with pytest.raises(ValidationError, match="must declare only producer_key"):
        ExportFieldDefinition.model_validate(
            _field_payload(
                "header",
                producer_key=FilingProducerKey.PRESENTER_TAX_ID,
                draft_attribute=ExportDraftAttribute.FILING_YEAR,
            ),
        )
    with pytest.raises(ValidationError, match="must not declare semantic payloads"):
        ExportFieldDefinition.model_validate(
            _field_payload("filler", producer_key=FilingProducerKey.PRESENTER_TAX_ID),
        )


def test_payload_axis_table_is_total_over_every_field_kind() -> None:
    assert {kind: export_semantic_payload_axis(kind) for kind in CasillaFieldKind} == {
        CasillaFieldKind.LITERAL: ExportSemanticPayloadAxis.LITERAL,
        CasillaFieldKind.CASILLA: ExportSemanticPayloadAxis.CASILLA_ID,
        CasillaFieldKind.BINDING: ExportSemanticPayloadAxis.BINDING,
        CasillaFieldKind.COMPUTED: ExportSemanticPayloadAxis.COMPUTED_KEY,
        CasillaFieldKind.DRAFT: ExportSemanticPayloadAxis.DRAFT_ATTRIBUTE,
        CasillaFieldKind.FILLER: None,
        CasillaFieldKind.HEADER: ExportSemanticPayloadAxis.PRODUCER_KEY,
        CasillaFieldKind.PROJECTION: ExportSemanticPayloadAxis.PROJECTION_REF,
        CasillaFieldKind.CHECKSUM: None,
    }
