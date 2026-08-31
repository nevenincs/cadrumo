"""Real-binary contract tests for the Modelo 303 DP30300 static declaration."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.resources._boundary import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_revision_inspection
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.loader import load_registry_tree
from cadrumo.domain.calculations.registry.schema_exports import FilingEnvelopeCloserDerivation

from ..pipeline._record_design_ir import (
    RecordDesignIntermediateField,
    RecordDesignIntermediateRelativeSuffixMarker,
    RecordDesignIntermediateSource,
    RecordDesignIntermediateVariableEnvelope,
    load_record_design_intermediate,
)
from ..pipeline._semantic_map import (
    EnvelopePrefixField,
    EnvelopeTotalAnchor,
    FilingEnvelopePrefixRole,
    SemanticMapAnchor,
    VariableEnvelopeSemantic,
)
from ..pipeline._variable_envelope import (
    FilingEnvelopeProvenance,
    compile_filing_envelope_definition,
    validate_variable_envelope,
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


#: Modelo 303 prints the shared grammar in its thirteen-row spelling: every
#: role except the composed opening tag, which is the ALTERNATIVE spelling of
#: the six rows this design prints separately.
_M303_PREFIX_ROLES: tuple[FilingEnvelopePrefixRole, ...] = tuple(
    role for role in FilingEnvelopePrefixRole if role is not FilingEnvelopePrefixRole.COMPOSED_OPENING_TAG
)


def _semantic_for(
    envelope: RecordDesignIntermediateVariableEnvelope,
    *,
    source_ref: str,
    source_sha256: str,
) -> VariableEnvelopeSemantic:
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
    return VariableEnvelopeSemantic(
        source_ref=source_ref,
        source_sha256=source_sha256,
        record_identity="DP30300",
        prefix_fields=tuple(
            EnvelopePrefixField(role=role, anchor=_anchor(field))
            for role, field in zip(_M303_PREFIX_ROLES, envelope.prefix_fields, strict=True)
        ),
        body_anchor=body,
        body_record_ids=_BODY_RECORD_IDS,
        closer_anchor=closer,
        total_anchor=EnvelopeTotalAnchor(
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
    declaration = compile_filing_envelope_definition(
        semantic,
        envelope,
        modelo="303",
        source=intermediate.source,
        body_record_ids=_BODY_RECORD_IDS,
    )

    assert inspection.revision_id == expected_revision_id
    assert len(envelope.prefix_fields) == 13
    assert tuple(field.role for field in declaration.prefix_fields) == _M303_PREFIX_ROLES
    assert sum(field.length for field in declaration.prefix_fields) == 328
    assert declaration.prefix_extent == 328
    assert declaration.body_record_ids == _BODY_RECORD_IDS

    provenance = FilingEnvelopeProvenance(
        schema_version=2,
        revision_id="2023",
        layout_id="generated-modelo-303-2023-fichero",
        semantic_sha256="a" * 64,
        envelope=declaration,
        envelope_sha256=content_hash_hex(declaration.model_dump(mode="json")),
    )
    encoded_provenance = provenance.model_dump(mode="json")

    assert FilingEnvelopeProvenance.model_validate_json(provenance.model_dump_json()) == provenance
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
        validate_variable_envelope(
            semantic,
            envelope,
            modelo="303",
            source=intermediate.source,
            body_record_ids=tuple(reversed(_BODY_RECORD_IDS)),
        )
    with pytest.raises(RegistryValidationError, match="body records must match"):
        validate_variable_envelope(
            _semantic_for(
                envelope,
                source_ref=str(intermediate.source.source_ref),
                source_sha256=intermediate.source.source_sha256,
            ),
            envelope,
            modelo="303",
            source=intermediate.source,
            body_record_ids=tuple(reversed(_BODY_RECORD_IDS)),
        )


def test_static_generator_has_no_instance_carrier_vocabulary() -> None:
    """DP30300 compilation retains grammar only; application owns filing bytes."""
    source = Path("dev/registry/pipeline/_variable_envelope.py").read_text(encoding="utf-8")

    forbidden = {
        "M303EnvelopeGenerationInput",
        "M303EnvelopeBodyMember",
        "M303EnvelopeBytes",
        "render_variable_envelope_bytes",
        "m303_envelope_body_casilla_coordinates",
    }
    assert all(name not in source for name in forbidden)


#: One bundled design per distinct official envelope spelling, with the roles
#: that design PRINTS. Not a Modelo 303 fixture list: the point of these rows is
#: that six modelos reach one compiler with no per-modelo code, so a seventh is
#: a row here rather than a branch in `_variable_envelope.py`.
_CROSS_MODELO_ENVELOPES = (
    ("308", "aeat-dr-308-2019", "2019", 2019, "M30800", 13),
    ("322", "aeat-dr-322-2024-2025", "2024", 2025, "DR32200", 13),
    ("353", "aeat-dr-353-2021-2025", "2021", 2025, "35300", 13),
    ("151", "aeat-dr-151-2023", "2023", 2023, "M15100", 13),
    ("202", "aeat-dr-202-2025", "2025", 2025, "dr M202 (0)", 13),
    ("200", "aeat-dr-200-2025", "2025", 2025, "DP200000", 8),
)

#: Modelo 200's eight-row spelling: the six opening-tag components fused into
#: one composed identifier, then the same `<AUX>` block every design carries.
_COMPOSED_PREFIX_ROLES: tuple[FilingEnvelopePrefixRole, ...] = (
    FilingEnvelopePrefixRole.COMPOSED_OPENING_TAG,
    FilingEnvelopePrefixRole.AUX_OPENING_TAG,
    FilingEnvelopePrefixRole.PRE_PROGRAM_FILLER,
    FilingEnvelopePrefixRole.PROGRAM_IDENTIFIER,
    FilingEnvelopePrefixRole.BETWEEN_IDENTITIES_FILLER,
    FilingEnvelopePrefixRole.DEVELOPER_TAX_ID,
    FilingEnvelopePrefixRole.POST_DEVELOPER_FILLER,
    FilingEnvelopePrefixRole.AUX_CLOSING_TAG,
)


def _bundled_intermediate(source_ref: str, *, design_epoch: str, filing_year: int):
    """Load one real design through the catalogue, without a filing snapshot."""
    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return load_record_design_intermediate(
        bundled_path(),
        catalogues.sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=design_epoch,
    )


def _semantic_for_roles(
    envelope: RecordDesignIntermediateVariableEnvelope,
    roles: tuple[FilingEnvelopePrefixRole, ...],
    *,
    source: RecordDesignIntermediateSource,
) -> VariableEnvelopeSemantic:
    closing = envelope.closing
    assert isinstance(closing, RecordDesignIntermediateRelativeSuffixMarker)
    return VariableEnvelopeSemantic(
        source_ref=str(source.source_ref),
        source_sha256=source.source_sha256,
        record_identity=envelope.record_identity,
        prefix_fields=tuple(
            EnvelopePrefixField(role=role, anchor=_anchor(field))
            for role, field in zip(roles, envelope.prefix_fields, strict=True)
        ),
        body_anchor=SemanticMapAnchor(
            sheet=envelope.sheet,
            source_row=envelope.body_source_row,
            source_cell=envelope.body_source_cell,
            ordinal=envelope.body_ordinal,
            record_identity=envelope.record_identity,
        ),
        body_record_ids=_BODY_RECORD_IDS,
        closer_anchor=SemanticMapAnchor(
            sheet=envelope.sheet,
            source_row=closing.source_row,
            source_cell=closing.source_cell,
            ordinal=closing.ordinal,
            record_identity=envelope.record_identity,
        ),
        total_anchor=EnvelopeTotalAnchor(
            source_row=envelope.total_source_row,
            source_cell=envelope.total_source_cell,
            label=envelope.total_label,
            length=envelope.total_length,
        ),
    )


@pytest.mark.parametrize(
    ("modelo", "source_ref", "design_epoch", "filing_year", "record_identity", "prefix_count"),
    _CROSS_MODELO_ENVELOPES,
)
def test_one_compiler_declares_every_modelo_sharing_the_official_envelope_grammar(
    modelo: str,
    source_ref: str,
    design_epoch: str,
    filing_year: int,
    record_identity: str,
    prefix_count: int,
) -> None:
    """Six modelos, two official spellings, one compiler and no modelo branch."""
    intermediate = _bundled_intermediate(source_ref, design_epoch=design_epoch, filing_year=filing_year)
    envelope = intermediate.variable_envelopes[0]
    roles = _COMPOSED_PREFIX_ROLES if prefix_count == len(_COMPOSED_PREFIX_ROLES) else _M303_PREFIX_ROLES

    declaration = compile_filing_envelope_definition(
        _semantic_for_roles(envelope, roles, source=intermediate.source),
        envelope,
        modelo=modelo,
        source=intermediate.source,
        body_record_ids=_BODY_RECORD_IDS,
    )

    assert declaration.record_identity == record_identity
    assert len(declaration.prefix_fields) == prefix_count
    assert declaration.prefix_extent == 328
    assert sum(field.length for field in declaration.prefix_fields) == 328
    assert declaration.closer_derivation is FilingEnvelopeCloserDerivation.RELATIVE_CLOSER_V1


def test_the_compiler_refuses_a_design_whose_official_closer_names_another_modelo() -> None:
    """The shared grammar is proved per design, not assumed from the role list.

    Modelo 309's bundled source is the live case: its closer content cell reads
    ``"</3090AAAAPP0000>"`` while the row's own description reads
    ``</T3090+Ejercicio+periodo+0000>``, so AEAT dropped the ``T``. Compiling it
    would emit a closer no AEAT reader accepts, which is why this refuses rather
    than tolerating a near-match. A declared, sourced correction is the route
    that opens it, not a widened pattern here.
    """
    intermediate = _bundled_intermediate("aeat-dr-309-2023", design_epoch="2023", filing_year=2023)
    envelope = intermediate.variable_envelopes[0]

    with pytest.raises(RegistryValidationError, match="is not the official"):
        compile_filing_envelope_definition(
            _semantic_for_roles(envelope, _M303_PREFIX_ROLES, source=intermediate.source),
            envelope,
            modelo="309",
            source=intermediate.source,
            body_record_ids=_BODY_RECORD_IDS,
        )
