"""Real-binary contract tests for the Modelo 303 DP30300 static declaration."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core import content_hash_hex
from cadrumo.domain.calculations.registry import RegistryValidationError, bundled_revision_inspection

from .._m303_variable_envelope import (
    M303EnvelopeProvenance,
    compile_m303_filing_envelope_definition,
    validate_m303_variable_envelope,
)
from .._record_design_ir import (
    RecordDesignIntermediateField,
    RecordDesignIntermediateRelativeSuffixMarker,
    RecordDesignIntermediateVariableEnvelope,
    load_record_design_intermediate,
)
from .._semantic_map import (
    M303EnvelopePrefixField,
    M303EnvelopePrefixRole,
    M303EnvelopeTotalAnchor,
    M303VariableEnvelopeSemantic,
    SemanticMapAnchor,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MODELO_303_DESIGNS = (
    ("aeat-dr-303-2023", "2023", 2023, "4T", "2023"),
    ("aeat-dr-303-2024-early", "2024-hasta-08-y-2t", 2024, "2T", "2024-early"),
    ("aeat-dr-303-2024-late", "2024-desde-09-y-3t", 2024, "3T", "2024-late"),
    ("aeat-dr-303-2025", "2025", 2025, "4T", "2025"),
    ("aeat-dr-303-2026", "2026-y-siguientes", 2026, "4T", "2026"),
)
_BODY_RECORD_IDS = ("m303-page-1", "m303-page-2")


def _anchor(field: RecordDesignIntermediateField) -> SemanticMapAnchor:
    return SemanticMapAnchor(
        sheet=field.sheet,
        source_row=field.source_row,
        source_cell=field.source_cell,
        ordinal=field.ordinal,
        record_identity=field.record_identity,
    )


def _semantic_for(
    envelope: RecordDesignIntermediateVariableEnvelope,
    *,
    source_ref: str,
    source_sha256: str,
) -> M303VariableEnvelopeSemantic:
    """Adapt one real parser-owned envelope into its reviewed role contract."""
    closing = envelope.closing
    assert isinstance(closing, RecordDesignIntermediateRelativeSuffixMarker)
    body = SemanticMapAnchor(
        sheet=envelope.sheet,
        source_row=envelope.body_source_row,
        source_cell=envelope.body_source_cell,
        ordinal=envelope.body_ordinal,
        record_identity=envelope.record_identity,
    )
    closer = SemanticMapAnchor(
        sheet=envelope.sheet,
        source_row=closing.source_row,
        source_cell=closing.source_cell,
        ordinal=closing.ordinal,
        record_identity=envelope.record_identity,
    )
    return M303VariableEnvelopeSemantic(
        source_ref=source_ref,
        source_sha256=source_sha256,
        record_identity="DP30300",
        prefix_fields=tuple(
            M303EnvelopePrefixField(role=role, anchor=_anchor(field))
            for role, field in zip(M303EnvelopePrefixRole, envelope.prefix_fields, strict=True)
        ),
        body_anchor=body,
        body_record_ids=_BODY_RECORD_IDS,
        closer_anchor=closer,
        total_anchor=M303EnvelopeTotalAnchor(
            source_row=envelope.total_source_row,
            source_cell=envelope.total_source_cell,
            label=envelope.total_label,
            length=envelope.total_length,
        ),
    )


@pytest.mark.parametrize(
    ("source_ref", "expected_revision_id", "filing_year", "period", "design_epoch"),
    _MODELO_303_DESIGNS,
)
def test_real_m303_binaries_compile_the_typed_static_declaration_without_instance_inputs(
    source_ref: str,
    expected_revision_id: str,
    filing_year: int,
    period: str,
    design_epoch: str,
) -> None:
    """All five hash-pinned DP30300 sources yield one source-bound static grammar."""
    inspection = bundled_revision_inspection("303", filing_year=filing_year, period=period)
    intermediate = load_record_design_intermediate(
        inspection.source_root,
        inspection.sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=design_epoch,
    )
    envelope = intermediate.variable_envelopes[0]
    semantic = _semantic_for(
        envelope,
        source_ref=str(intermediate.source.source_ref),
        source_sha256=intermediate.source.source_sha256,
    )
    declaration = compile_m303_filing_envelope_definition(
        semantic,
        envelope,
        source=intermediate.source,
        body_record_ids=_BODY_RECORD_IDS,
    )

    assert inspection.revision_id == expected_revision_id
    assert len(envelope.prefix_fields) == 13
    assert tuple(field.role for field in declaration.prefix_fields) == tuple(M303EnvelopePrefixRole)
    assert sum(field.length for field in declaration.prefix_fields) == 328
    assert declaration.body_record_ids == _BODY_RECORD_IDS
    assert declaration.product_identity_requirement == "aeat-product-software-identity-v1"
    assert declaration.closer_derivation == "m303-relative-closer-v1"
    assert declaration.total_derivation == "m303-emitted-byte-total-v1"

    provenance = M303EnvelopeProvenance(
        schema_version=2,
        revision_id="2023",
        layout_id="generated-modelo-303-2023-fichero",
        semantic_sha256="a" * 64,
        envelope=declaration,
        envelope_sha256=content_hash_hex(declaration.model_dump(mode="json")),
    )
    encoded_provenance = provenance.model_dump(mode="json")

    assert M303EnvelopeProvenance.model_validate_json(provenance.model_dump_json()) == provenance
    assert set(encoded_provenance) == {
        "schema_version",
        "revision_id",
        "layout_id",
        "semantic_sha256",
        "envelope",
        "envelope_sha256",
    }
    assert not {"period", "payload", "payload_sha256", "total_length", "product_software_identity"} & set(
        encoded_provenance
    )


def test_m303_static_declaration_refuses_source_drift_and_reordered_body_definitions() -> None:
    """No later application authority can repair source or record-order drift."""
    inspection = bundled_revision_inspection("303", filing_year=2026, period="4T")
    intermediate = load_record_design_intermediate(
        inspection.source_root,
        inspection.sources,
        source_ref="aeat-dr-303-2026",
        filing_year=2026,
        design_epoch="2026",
    )
    envelope = intermediate.variable_envelopes[0]
    semantic = _semantic_for(
        envelope,
        source_ref=str(intermediate.source.source_ref),
        source_sha256="b" * 64,
    )
    with pytest.raises(RegistryValidationError, match="not pinned to the exact parser source"):
        validate_m303_variable_envelope(
            semantic,
            envelope,
            source=intermediate.source,
            body_record_ids=tuple(reversed(_BODY_RECORD_IDS)),
        )
    with pytest.raises(RegistryValidationError, match="body records must match"):
        validate_m303_variable_envelope(
            _semantic_for(
                envelope,
                source_ref=str(intermediate.source.source_ref),
                source_sha256=intermediate.source.source_sha256,
            ),
            envelope,
            source=intermediate.source,
            body_record_ids=tuple(reversed(_BODY_RECORD_IDS)),
        )


def test_static_generator_has_no_instance_carrier_vocabulary() -> None:
    """DP30300 compilation retains grammar only; application owns filing bytes."""
    source = Path("dev/registry/_m303_variable_envelope.py").read_text(encoding="utf-8")

    forbidden = {
        "M303EnvelopeGenerationInput",
        "M303EnvelopeBodyMember",
        "M303EnvelopeBytes",
        "render_m303_variable_envelope_bytes",
        "m303_envelope_body_casilla_coordinates",
    }
    assert all(name not in source for name in forbidden)
