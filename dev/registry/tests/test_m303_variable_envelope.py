"""Real-binary contract tests for the Modelo 303 DP30300 composition authority."""

from __future__ import annotations

import pytest

from cadrumo.core import M303ProductSoftwareEvidence, M303ProductSoftwareIdentity, Period
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import RegistryValidationError, load_catalogue_file

from .._m303_variable_envelope import (
    M303EnvelopeBodyMember,
    render_m303_variable_envelope_bytes,
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
    ("aeat-dr-303-2023", 2023, "2023"),
    ("aeat-dr-303-2024-early", 2024, "2024-early"),
    ("aeat-dr-303-2024-late", 2024, "2024-late"),
    ("aeat-dr-303-2025", 2025, "2025"),
    ("aeat-dr-303-2026", 2026, "2026"),
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


def _product_identity() -> M303ProductSoftwareIdentity:
    return M303ProductSoftwareIdentity(
        program_identifier="C303",
        developer_tax_id="Y0000001S",
        evidence=(
            M303ProductSoftwareEvidence(
                reference="aeat-software-registration:c303",
                digest="a" * 64,
            ),
        ),
    )


@pytest.mark.parametrize(("source_ref", "filing_year", "design_epoch"), _MODELO_303_DESIGNS)
def test_real_m303_binaries_render_the_typed_envelope_without_a_legacy_layout(
    source_ref: str,
    filing_year: int,
    design_epoch: str,
) -> None:
    """All five hash-pinned DP30300 sources yield one measured byte composition."""
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "iva.toml"))
    intermediate = load_record_design_intermediate(
        source_root,
        catalogues.sources,
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
    body_members = (
        M303EnvelopeBodyMember(record_id="m303-page-1", payload=b"PAGE-ONE\r\n"),
        M303EnvelopeBodyMember(record_id="m303-page-2", payload=b"PAGE-TWO\r\n"),
    )

    rendered = render_m303_variable_envelope_bytes(
        semantic,
        envelope,
        source=intermediate.source,
        product_software_identity=_product_identity(),
        filing_period=Period.from_year_and_code(filing_year, "4T"),
        body_members=body_members,
    )

    assert len(envelope.prefix_fields) == 13
    assert len(rendered.prefix) == 328
    assert rendered.prefix[92:96] == b"C303"
    assert rendered.prefix[100:109] == b"Y0000001S"
    assert rendered.closer == f"</T3030{filing_year:04d}4T0000>".encode("ascii")
    assert rendered.payload[328 : 328 + len(body_members[0].payload)] == body_members[0].payload
    assert (
        rendered.total_length == len(rendered.payload) == 328 + sum(len(member.payload) for member in body_members) + 18
    )


def test_m303_envelope_refuses_source_drift_and_reordered_body_members() -> None:
    """Product identity cannot make a drifted source or reordered body silently render."""
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "iva.toml"))
    intermediate = load_record_design_intermediate(
        source_root,
        catalogues.sources,
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
    members = (
        M303EnvelopeBodyMember(record_id="m303-page-2", payload=b"PAGE-TWO\r\n"),
        M303EnvelopeBodyMember(record_id="m303-page-1", payload=b"PAGE-ONE\r\n"),
    )

    with pytest.raises(RegistryValidationError, match="not pinned to the exact parser source"):
        render_m303_variable_envelope_bytes(
            semantic,
            envelope,
            source=intermediate.source,
            product_software_identity=_product_identity(),
            filing_period=Period.from_year_and_code(2026, "4T"),
            body_members=members,
        )

    with pytest.raises(RegistryValidationError, match="body records must match"):
        render_m303_variable_envelope_bytes(
            _semantic_for(
                envelope,
                source_ref=str(intermediate.source.source_ref),
                source_sha256=intermediate.source.source_sha256,
            ),
            envelope,
            source=intermediate.source,
            product_software_identity=_product_identity(),
            filing_period=Period.from_year_and_code(2026, "4T"),
            body_members=members,
        )

    with pytest.raises(RegistryValidationError, match="monthly or quarterly"):
        render_m303_variable_envelope_bytes(
            _semantic_for(
                envelope,
                source_ref=str(intermediate.source.source_ref),
                source_sha256=intermediate.source.source_sha256,
            ),
            envelope,
            source=intermediate.source,
            product_software_identity=_product_identity(),
            filing_period=Period.from_year_and_code(2026, "0A"),
            body_members=(
                M303EnvelopeBodyMember(record_id="m303-page-1", payload=b"PAGE-ONE\r\n"),
                M303EnvelopeBodyMember(record_id="m303-page-2", payload=b"PAGE-TWO\r\n"),
            ),
        )
