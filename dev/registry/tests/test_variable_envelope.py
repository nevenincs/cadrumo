"""Real-binary contract tests for the Modelo 303 DP30300 static declaration."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_exports import FilingEnvelopeCloserDerivation, FilingEnvelopePrefixRole
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

from ..compiler.authority import compiled_bundled_authority
from ..compiler.authority_state import source_root_for
from ..compiler.loader import load_modelo_directory, load_shared_catalogues
from ..pipeline.joined_record_design import join_record_design_semantics
from ..pipeline.record_design_intermediate import (
    RecordDesignIntermediateField,
    RecordDesignIntermediateRelativeSuffixMarker,
    RecordDesignIntermediateSource,
    RecordDesignIntermediateVariableEnvelope,
    load_record_design_intermediate,
)
from ..pipeline.semantic_map import (
    EnvelopePrefixField,
    EnvelopeTotalAnchor,
    SemanticMapAnchor,
    VariableEnvelopeSemantic,
    load_semantic_map,
)
from ..pipeline.variable_envelope import (
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


#: These are the thirteen roles present in Modelo 303's reviewed source order.
#: Other shared-grammar roles are omitted by this design; Modelo 200's one-row
#: opening identifier is the alternative spelling of the six opening rows.
_M303_PREFIX_ROLES: tuple[FilingEnvelopePrefixRole, ...] = (
    FilingEnvelopePrefixRole.OPENING_TAG,
    FilingEnvelopePrefixRole.MODELO,
    FilingEnvelopePrefixRole.DISCRIMINANT,
    FilingEnvelopePrefixRole.FILING_YEAR,
    FilingEnvelopePrefixRole.PERIOD,
    FilingEnvelopePrefixRole.RECORD_TYPE,
    FilingEnvelopePrefixRole.AUX_OPENING_TAG,
    FilingEnvelopePrefixRole.PRE_PROGRAM_FILLER,
    FilingEnvelopePrefixRole.PROGRAM_IDENTIFIER,
    FilingEnvelopePrefixRole.BETWEEN_IDENTITIES_FILLER,
    FilingEnvelopePrefixRole.DEVELOPER_TAX_ID,
    FilingEnvelopePrefixRole.POST_DEVELOPER_FILLER,
    FilingEnvelopePrefixRole.AUX_CLOSING_TAG,
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
        ordinal=str(envelope.body_ordinal),
        record_identity=envelope.record_identity,
    )
    closer = SemanticMapAnchor(
        sheet=envelope.sheet,
        source_row=closing.source_row,
        source_cell=closing.source_cell,
        ordinal=str(closing.ordinal),
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
    authority = compiled_bundled_authority()
    inspection = authority.inspect_revision("303", filing_year=filing_year, period=period)
    source_root = source_root_for(authority)
    intermediate = load_record_design_intermediate(
        source_root,
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
    authority = compiled_bundled_authority()
    inspection = authority.inspect_revision("303", filing_year=2026, period="4T")
    source_root = source_root_for(authority)
    intermediate = load_record_design_intermediate(
        source_root,
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
    source = Path("dev/registry/pipeline/variable_envelope.py").read_text(encoding="utf-8")

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
#: a row here rather than a branch in `variable_envelope.py`.
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
    catalogues = load_shared_catalogues(bundled_path("registry", "aeat"))
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
            ordinal=str(envelope.body_ordinal),
            record_identity=envelope.record_identity,
        ),
        body_record_ids=_BODY_RECORD_IDS,
        closer_anchor=SemanticMapAnchor(
            sheet=envelope.sheet,
            source_row=closing.source_row,
            source_cell=closing.source_cell,
            ordinal=str(closing.ordinal),
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

    Modelo 309's unadjudicated 2016 source is the live case: its closer content reads
    ``"</3090AAAAPP0000>"`` while the row's own description reads
    ``</T3090+Ejercicio+periodo+0000>``. The selected 2018 and 2023 sources
    have their own exact adjudications; this source has none and still refuses.
    """
    intermediate = _bundled_intermediate("aeat-dr-309-2016", design_epoch="2016", filing_year=2016)
    envelope = intermediate.variable_envelopes[0]

    with pytest.raises(RegistryValidationError, match="is not the official"):
        compile_filing_envelope_definition(
            _semantic_for_roles(envelope, _M303_PREFIX_ROLES, source=intermediate.source),
            envelope,
            modelo="309",
            source=intermediate.source,
            body_record_ids=_BODY_RECORD_IDS,
        )


_M309_SELECTED_DESIGNS = (
    ("2018", "2018-2022", 2018, 65, "7f46a0301f27345c19530a6a12acfa976ab5b60a67e563afa68277c12f2b07a8"),
    ("2023", "2023-y-siguientes", 2023, 68, "a84c6347a87ac4c4db8610010e100cb8632518a9d20e54e79ffbc713d770beb5"),
)


@pytest.mark.parametrize(("epoch", "revision", "filing_year", "field_count", "source_sha256"), _M309_SELECTED_DESIGNS)
def test_m309_selected_source_maps_join_every_body_field_and_compile_only_the_reviewed_closer(
    epoch: str,
    revision: str,
    filing_year: int,
    field_count: int,
    source_sha256: str,
) -> None:
    """Each current map joins its own hash-verified source and selected revision."""
    root = bundled_path("registry", "aeat")
    catalogues = load_shared_catalogues(root)
    modelo = load_modelo_directory(root / "modelos" / "309")
    inspection = RegistryRevisionInspection.from_revision(
        modelo=modelo,
        revision=modelo.revisions[revision],
        source_root=bundled_path(),
        sources=catalogues.sources,
        legal_ref_ids=frozenset(catalogues.legal),
    )
    intermediate = _bundled_intermediate(f"aeat-dr-309-{epoch}", design_epoch=epoch, filing_year=filing_year)
    semantic_map = load_semantic_map(Path(__file__).resolve().parents[1] / "mappings" / "modelo_309" / epoch)
    joined = join_record_design_semantics(semantic_map, intermediate, inspection)

    assert joined.source.source_sha256 == source_sha256
    assert len(joined.records) == 1
    assert len(joined.fields) == field_count
    assert tuple(field.parser_field.ordinal for field in joined.fields) == tuple(
        str(ordinal) for ordinal in range(1, field_count + 1)
    )
    assert tuple(record.semantic_record.export_record_id for record in joined.records) == ("modelo-309-page-01",)
    contract = joined.variable_envelope_contract
    assert contract is not None
    declaration = compile_filing_envelope_definition(
        contract.semantic,
        contract.parser_envelope,
        modelo="309",
        source=joined.source,
        body_record_ids=("modelo-309-page-01",),
    )
    assert declaration.record_identity == "M30900"
    assert declaration.closer_derivation is FilingEnvelopeCloserDerivation.RELATIVE_CLOSER_V1


@pytest.mark.parametrize(
    ("epoch", "_revision", "filing_year", "_field_count", "_source_sha256"), _M309_SELECTED_DESIGNS
)
@pytest.mark.parametrize(
    ("mutation", "error"),
    (
        ("source_sha256", "source digest changed"),
        ("source_ref", "is not the official"),
        ("wrong_modelo", "is not the official"),
        ("source_row", "no longer matches its exact printed row"),
        ("description", "no longer matches its exact printed row"),
        ("validation", "no longer matches its exact printed row"),
        ("lexeme", "no longer matches its exact printed row"),
        ("width", "does not match its exact 18-byte source anchor"),
    ),
)
def test_m309_missing_t_adjudication_refuses_changed_source_or_printed_row(
    epoch: str,
    _revision: str,
    filing_year: int,
    _field_count: int,
    _source_sha256: str,
    mutation: str,
    error: str,
) -> None:
    intermediate = _bundled_intermediate(f"aeat-dr-309-{epoch}", design_epoch=epoch, filing_year=filing_year)
    envelope = intermediate.variable_envelopes[0]
    semantic = _semantic_for_roles(envelope, _M303_PREFIX_ROLES, source=intermediate.source)
    source = intermediate.source
    closing = envelope.closing
    modelo = "309"
    assert isinstance(closing, RecordDesignIntermediateRelativeSuffixMarker)

    if mutation == "source_sha256":
        source = source.model_copy(update={"source_sha256": "0" * 64})
        semantic = semantic.model_copy(update={"source_sha256": source.source_sha256})
    elif mutation == "source_ref":
        source = source.model_copy(update={"source_ref": "aeat-dr-309-2016"})
        semantic = semantic.model_copy(update={"source_ref": source.source_ref})
    elif mutation == "wrong_modelo":
        # Keep the selected source pin and alter the prefix in memory so the
        # closer guard, rather than the earlier prefix guard, proves isolation.
        prefix_fields = list(envelope.prefix_fields)
        prefix_fields[1] = prefix_fields[1].model_copy(update={"content": '"310"'})
        envelope = envelope.model_copy(update={"prefix_fields": tuple(prefix_fields)})
        modelo = "310"
    elif mutation == "source_row":
        closing = closing.model_copy(update={"source_row": 21})
        semantic = semantic.model_copy(
            update={"closer_anchor": semantic.closer_anchor.model_copy(update={"source_row": 21})}
        )
    elif mutation == "description":
        closing = closing.model_copy(update={"normalized_description": "Constante. </3090+Ejercicio+periodo+0000>"})
    elif mutation == "validation":
        closing = closing.model_copy(update={"validation": "another statement"})
    elif mutation == "lexeme":
        closing = closing.model_copy(update={"content": '"</3100AAAAPP0000>"'})
    else:
        assert mutation == "width"
        closing = closing.model_copy(update={"length": 17})
    envelope = envelope.model_copy(update={"closing": closing})

    with pytest.raises(RegistryValidationError, match=error):
        compile_filing_envelope_definition(
            semantic,
            envelope,
            modelo=modelo,
            source=source,
            body_record_ids=_BODY_RECORD_IDS,
        )
