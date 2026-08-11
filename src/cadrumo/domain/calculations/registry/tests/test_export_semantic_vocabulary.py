"""Strict schema proofs for canonical export semantic selectors."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..._export_field_kind import CasillaFieldKind
from .. import (
    ExportComputedKey,
    ExportDraftAttribute,
    ExportFieldDefinition,
    ExportHeaderKey,
    ExportSemanticPayloadAxis,
    export_semantic_payload_axis,
)

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
        ("header", {"header_key": "program_version"}, ExportSemanticPayloadAxis.HEADER_KEY),
        ("draft", {"draft_attribute": "filing_year"}, ExportSemanticPayloadAxis.DRAFT_ATTRIBUTE),
        ("computed", {"computed_key": "envelope_closing_tag"}, ExportSemanticPayloadAxis.COMPUTED_KEY),
    ),
)
def test_strict_schema_hydrates_each_selector_from_the_canonical_vocabulary(
    kind: str,
    payload: dict[str, object],
    axis: ExportSemanticPayloadAxis,
) -> None:
    field = ExportFieldDefinition.model_validate(_field_payload(kind, **payload))

    assert export_semantic_payload_axis(field.kind) is axis
    if axis is ExportSemanticPayloadAxis.HEADER_KEY:
        assert field.header_key is ExportHeaderKey.PROGRAM_VERSION
    elif axis is ExportSemanticPayloadAxis.DRAFT_ATTRIBUTE:
        assert field.draft_attribute is ExportDraftAttribute.FILING_YEAR
    else:
        assert field.computed_key is ExportComputedKey.ENVELOPE_CLOSING_TAG


@pytest.mark.parametrize(
    ("kind", "payload", "deleted"),
    (
        ("header", {"header_key": "presenter_nif"}, "presenter_nif"),
        ("header", {"header_key": "presenter_tax_id"}, "presenter_tax_id"),
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
    with pytest.raises(ValidationError, match="must declare only header_key"):
        ExportFieldDefinition.model_validate(
            _field_payload(
                "header",
                header_key="program_version",
                draft_attribute="filing_year",
            ),
        )
    with pytest.raises(ValidationError, match="must not declare semantic payloads"):
        ExportFieldDefinition.model_validate(_field_payload("filler", header_key="program_version"))


def test_payload_axis_table_is_total_over_every_field_kind() -> None:
    assert {kind: export_semantic_payload_axis(kind) for kind in CasillaFieldKind} == {
        CasillaFieldKind.LITERAL: ExportSemanticPayloadAxis.LITERAL,
        CasillaFieldKind.CASILLA: ExportSemanticPayloadAxis.CASILLA_ID,
        CasillaFieldKind.BINDING: ExportSemanticPayloadAxis.BINDING,
        CasillaFieldKind.COMPUTED: ExportSemanticPayloadAxis.COMPUTED_KEY,
        CasillaFieldKind.DRAFT: ExportSemanticPayloadAxis.DRAFT_ATTRIBUTE,
        CasillaFieldKind.FILLER: None,
        CasillaFieldKind.HEADER: ExportSemanticPayloadAxis.HEADER_KEY,
        CasillaFieldKind.CHECKSUM: None,
    }
