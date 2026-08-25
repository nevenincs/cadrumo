"""Validation tests for the development-only record-design semantic map."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.core import (
    FilingProducerKey,
    M303ProrrataActivityProjectionField,
    M303ProrrataActivityProjectionRef,
    validated_casilla_id,
)
from cadrumo.domain.calculations.registry.schema import (
    CasillaFieldKind,
    ExportComputedKey,
    ExportDraftAttribute,
)

from ..pipeline._semantic_map import SemanticMap, SemanticMapEntry

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _anchor() -> dict[str, object]:
    return {
        "sheet": "Registro tipo 1",
        "source_row": 14,
        "source_cell": "A14",
        "ordinal": 3,
        "record_identity": "registro-tipo-1",
    }


def _entry_payload(kind: str, **semantic_payload: object) -> dict[str, object]:
    return {
        "anchor": _anchor(),
        "export_field_id": "registro-tipo-1.declarante-nif",
        "kind": kind,
        "legal_refs": ("liva-art-164",),
        "source_refs": ("aeat-dr-303-2026",),
        **semantic_payload,
    }


def _projection_ref() -> M303ProrrataActivityProjectionRef:
    return M303ProrrataActivityProjectionRef(
        projection_kind="m303_prorrata_activity",
        slot=1,
        field=M303ProrrataActivityProjectionField.CNAE,
        casilla_id=validated_casilla_id("500", surface="test"),
    )


@pytest.mark.parametrize(
    ("kind", "semantic_payload", "expected_name", "expected_value"),
    [
        ("casilla", {"casilla_id": "casilla.03"}, "casilla_id", "casilla.03"),
        ("binding", {"binding": "declarante.nif"}, "binding", "declarante.nif"),
        ("literal", {"literal": "T"}, "literal", "T"),
        (
            "header",
            {"producer_key": FilingProducerKey.PRESENTER_TAX_ID},
            "producer_key",
            FilingProducerKey.PRESENTER_TAX_ID,
        ),
        ("projection", {"projection_ref": _projection_ref()}, "projection_ref", _projection_ref()),
        (
            "draft",
            {"draft_attribute": ExportDraftAttribute.FILING_YEAR},
            "draft_attribute",
            ExportDraftAttribute.FILING_YEAR,
        ),
        (
            "computed",
            {"computed_key": ExportComputedKey.ENVELOPE_CLOSING_TAG},
            "computed_key",
            ExportComputedKey.ENVELOPE_CLOSING_TAG,
        ),
        ("filler", {}, None, None),
        ("checksum", {}, None, None),
    ],
)
def test_semantic_entry_accepts_only_the_registry_meaning_for_each_field_kind(
    kind: str,
    semantic_payload: dict[str, object],
    expected_name: str | None,
    expected_value: object | None,
) -> None:
    """Every production export kind maps to its one permitted semantic payload."""
    entry = SemanticMapEntry.model_validate(_entry_payload(kind, **semantic_payload))

    assert entry.kind is CasillaFieldKind(kind)
    if expected_name is not None:
        assert getattr(entry, expected_name) == expected_value
    else:
        assert entry.casilla_id is None
        assert entry.binding is None
        assert entry.literal is None
        assert entry.producer_key is None
        assert entry.projection_ref is None
        assert entry.draft_attribute is None
        assert entry.computed_key is None


def test_semantic_map_retains_a_complete_workbook_anchor_and_canonical_grounding() -> None:
    """A per-design map retains semantic identity without importing coordinates."""
    semantic_map = SemanticMap.model_validate(
        {
            "modelo": "303",
            "design_epoch": "2026",
            "source_ref": "aeat-dr-303-2026",
            "source_sha256": "a" * 64,
            "records": (
                {
                    "sheet": "Registro tipo 1",
                    "record_identity": "registro-tipo-1",
                    "export_record_id": "registro-tipo-1",
                    "record_type": "declaracion",
                },
            ),
            "entries": (_entry_payload("casilla", casilla_id="casilla.03"),),
        },
    )

    entry = semantic_map.entries[0]
    assert semantic_map.modelo == "303"
    assert semantic_map.design_epoch == "2026"
    assert semantic_map.source_ref == "aeat-dr-303-2026"
    assert semantic_map.source_sha256 == "a" * 64
    assert semantic_map.records[0].export_record_id == "registro-tipo-1"
    assert semantic_map.records[0].record_type == "declaracion"
    assert entry.anchor.sheet == "Registro tipo 1"
    assert entry.anchor.source_row == 14
    assert entry.anchor.source_cell == "A14"
    assert entry.anchor.ordinal == "3"
    assert entry.anchor.record_identity == "registro-tipo-1"
    assert entry.export_field_id == "registro-tipo-1.declarante-nif"
    assert entry.legal_refs == ("liva-art-164",)
    assert entry.source_refs == ("aeat-dr-303-2026",)


def test_semantic_map_supports_exact_pdf_anchors_without_a_workbook_cell() -> None:
    """PDF parser output remains exactly addressable without inventing a cell."""
    payload = _entry_payload("filler")
    payload["anchor"] = {**_anchor(), "source_cell": None}

    entry = SemanticMapEntry.model_validate(payload)

    assert entry.anchor.source_row == 14
    assert entry.anchor.source_cell is None
    assert entry.anchor.ordinal == "3"
    assert entry.anchor.record_identity == "registro-tipo-1"


@pytest.mark.parametrize("identity_key", ("source_ref", "source_sha256"))
def test_semantic_map_refuses_design_epoch_only_identity(identity_key: str) -> None:
    """A source-pinned map cannot fall back to the design epoch alone."""
    payload = {
        "modelo": "303",
        "design_epoch": "2026",
        "source_ref": "aeat-dr-303-2026",
        "source_sha256": "a" * 64,
        "records": (
            {
                "sheet": "Registro tipo 1",
                "record_identity": "registro-tipo-1",
                "export_record_id": "registro-tipo-1",
                "record_type": "declaracion",
            },
        ),
        "entries": (_entry_payload("casilla", casilla_id="casilla.03"),),
    }
    del payload[identity_key]

    with pytest.raises(ValidationError, match=identity_key):
        SemanticMap.model_validate(payload)


@pytest.mark.parametrize(
    ("kind", "semantic_payload", "message"),
    [
        ("casilla", {}, "only casilla_id; declared none"),
        ("binding", {"binding": "declarante.nif", "casilla_id": "casilla.03"}, "only binding"),
        ("projection", {}, "only projection_ref; declared none"),
        ("projection", {"projection_ref": _projection_ref(), "casilla_id": "casilla.03"}, "only projection_ref"),
        ("filler", {"literal": " "}, "must not declare semantic payloads"),
        ("checksum", {"computed_key": ExportComputedKey.ENVELOPE_CLOSING_TAG}, "must not declare semantic payloads"),
    ],
)
def test_semantic_map_rejects_missing_or_conflicting_kind_semantics(
    kind: str,
    semantic_payload: dict[str, object],
    message: str,
) -> None:
    """A map cannot silently mix registry meanings for one official slot."""
    with pytest.raises(ValidationError, match=message):
        SemanticMapEntry.model_validate(_entry_payload(kind, **semantic_payload))


def test_semantic_map_rejects_parser_coordinates_and_renderer_shape() -> None:
    """Coordinates and export formatting remain parser-owned, never semantic-map data."""
    with pytest.raises(ValidationError, match="offset"):
        SemanticMapEntry.model_validate(
            _entry_payload(
                "casilla",
                casilla_id="casilla.03",
                offset=17,
            ),
        )


def test_semantic_map_compiles_a_raw_projection_ref_through_the_canonical_compiler() -> None:
    """A raw mapping is COMPILED here, not refused, and never stored raw.

    This entry is embedded in the export provenance manifest, which is written
    as JSON and read back by design, and from JSON a reference can only arrive
    as a mapping. Demanding an already-typed model made that read-back
    impossible. The invariant boundaries actually need is "every reference was
    produced by the one canonical compiler", which compiling here satisfies for
    TOML and JSON through a single path.

    Pinned as the pair that makes it a real guarantee rather than a widening:
    a well-formed mapping arrives typed, and a malformed one still refuses.
    """
    entry = SemanticMapEntry.model_validate(
        _entry_payload(
            "projection",
            projection_ref={
                "projection_kind": "m303_prorrata_activity",
                "slot": 1,
                "field": "cnae",
                "casilla_id": "500",
            },
        ),
    )

    assert isinstance(entry.projection_ref, M303ProrrataActivityProjectionRef)
    assert entry.projection_ref.field is M303ProrrataActivityProjectionField.CNAE
    assert entry.projection_ref.casilla_id == validated_casilla_id("500")


def test_semantic_map_still_refuses_a_malformed_projection_ref() -> None:
    """The compiler is what makes the mapping path safe, so it must still bite."""
    with pytest.raises(ValidationError):
        SemanticMapEntry.model_validate(
            _entry_payload(
                "projection",
                projection_ref={
                    "projection_kind": "m303_prorrata_activity",
                    "slot": 1,
                    "field": "not_a_projection_field",
                    "casilla_id": "500",
                },
            ),
        )


@pytest.mark.parametrize(
    ("legacy_inference_axis", "value"),
    (
        ("label", "Actividad principal"),
        ("description", "Actividad prorrata"),
        ("offset", 17),
        ("section", "prorrata"),
        ("numeric", 500),
        ("neighbour", "next-field"),
    ),
)
def test_semantic_map_refuses_legacy_projection_inference_axes(
    legacy_inference_axis: str,
    value: object,
) -> None:
    """Official geometry remains evidence; it cannot select projection meaning."""
    with pytest.raises(ValidationError, match="extra_forbidden"):
        SemanticMapEntry.model_validate(
            _entry_payload(
                "projection",
                projection_ref=_projection_ref(),
                **{legacy_inference_axis: value},
            ),
        )


@pytest.mark.parametrize(
    ("kind", "payload", "deleted"),
    (
        ("header", {"producer_key": "presenter.tax_id"}, "producer_key"),
        ("header", {"header_key": "presenter_nif"}, "header_key"),
        ("draft", {"draft_attribute": "modelo"}, "modelo"),
        ("computed", {"computed_key": "record_checksum"}, "record_checksum"),
    ),
)
def test_semantic_map_rejects_deleted_selector_tokens(
    kind: str,
    payload: dict[str, object],
    deleted: str,
) -> None:
    with pytest.raises(ValidationError, match=deleted):
        SemanticMapEntry.model_validate(_entry_payload(kind, **payload))
