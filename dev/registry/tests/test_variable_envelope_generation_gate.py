"""Real-source gate for variable-envelope retention and generation refusal."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_revision_inspection
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.loader import load_catalogue_file

from ..pipeline._export_tree import ExportTreeTransportProfile, RenderedExportTree, render_complete_export_tree
from ..pipeline._record_design_ir import load_record_design_intermediate
from ..pipeline._render_profile import (
    RenderProfileSourceEvidence,
    load_render_profile,
    load_render_profile_source_evidence,
)
from ..pipeline._semantic_map import SemanticMap
from ..pipeline._semantic_map_join import join_record_design_semantics
from ..pipeline._semantic_map_loader import load_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _real_render_profile(modelo: str, design_epoch: str, source_ref: str, catalogues) -> tuple:
    """Return the authored render profile and its official-source evidence.

    Generation refuses a profile that does not cover exactly the design's
    eligible blank numeric fields, so these gates cannot stand up a placeholder
    profile to reach a later refusal. Evidence is read out of the hash-verified
    design binary only when the profile actually claims a cell; a profile whose
    every rule is reviewed policy claims none, and the resolver refuses an empty
    claim set.
    """
    profile = load_render_profile(Path("dev/registry/render_profiles") / f"modelo_{modelo}" / design_epoch)
    claims_official = any(
        rule.evidence.authority_kind != "reviewed_policy"
        for rule in (*profile.singleton_rules, *profile.width_17_rules)
    )
    evidence = (
        load_render_profile_source_evidence(bundled_path() / catalogues.sources[source_ref].corpus_path, profile)
        if claims_official
        else RenderProfileSourceEvidence(design_identity=profile.design_identity, entries=())
    )
    return profile, evidence


def _authored_envelope_contract(modelo: str, design_epoch: str, body_record_id: str) -> dict[str, object]:
    """Return the reviewed variable-envelope contract, bound to one body record.

    The join refuses a design whose parser owns a variable envelope unless the
    semantic map carries exactly one reviewed contract for it, so these gates
    cannot build a map without one. The contract is taken from the authored
    mapping rather than invented here: its prefix roles are semantic judgements
    about what the design PRINTS, which no fixture can derive from the parser.

    Only ``body_record_ids`` is rebound. These gates focus the intermediate down
    to a single sheet so the refusal under test is reached quickly, and the
    validator derives the expected body records from the sheets actually
    present, so the authored list of every page would not match the focused
    intermediate.
    """
    authored = load_semantic_map(Path("dev/registry/mappings") / f"modelo_{modelo}" / design_epoch)
    contract = authored.variable_envelopes[0].model_copy(update={"body_record_ids": (body_record_id,)})
    return contract.model_dump(mode="python")


def test_static_generator_exposes_no_filing_instance_channels() -> None:
    """The generator carries grammar only; application owns a filing instance."""
    assert {
        "product_software_identity",
        "m303_envelope_input",
        "filing_period",
        "casilla_values",
        "body_members",
        "payload",
        "payload_sha256",
        "total_length",
    }.isdisjoint(inspect.signature(render_complete_export_tree).parameters)
    assert "variable_envelope_contract" not in RenderedExportTree.model_fields


def test_real_m200_variable_envelope_is_composed_rather_than_truncated(tmp_path: Path) -> None:
    """The parsed DP200000 composition survives the join AND reaches the output.

    Generation used to REFUSE a design carrying a variable envelope, and this
    gate asserted that refusal. It now composes one through the reviewed
    contract -- which is why modelos 151 and 202, both envelope-bearing, are
    generated trees. The concern the refusal stood in for is unchanged and is
    what is pinned here: the wrapper must not vanish, and must not be flattened
    into one more fixed record.

    Driven with the AUTHORED mapping and render profile against the whole
    parsed design. A design whose parser owns an envelope must now carry a
    reviewed contract for it and declare its revision's projection endpoints,
    so a focused synthetic map cannot reach generation at all -- and the
    authored artefacts are the better witness, being what generation consumes.
    """
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml"))
    inspection = bundled_revision_inspection("200", filing_year=2025, period="0A")
    parsed = load_record_design_intermediate(
        source_root,
        catalogues.sources,
        source_ref="aeat-dr-200-2025",
        filing_year=2025,
        design_epoch="2025",
    )
    semantic_map = load_semantic_map(Path("dev/registry/mappings") / "modelo_200" / "2025")
    render_profile, evidence = _real_render_profile("200", "2025", "aeat-dr-200-2025", catalogues)

    joined = join_record_design_semantics(semantic_map, parsed, inspection)

    assert joined.variable_envelopes == parsed.variable_envelopes
    assert joined.variable_envelopes[0].record_identity == "DP200000"

    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=inspection.revision_id,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=ExportTreeTransportProfile(
            modelo="200",
            design_epoch="2025",
            source_ref="aeat-dr-200-2025",
            source_sha256=parsed.source.source_sha256,
            layout_id="m200-envelope-gate",
            format="fixed_width",
            encoding=ExportEncoding.LATIN_1,
            line_ending="crlf",
            serializer_convention="rtoml-pretty-v1",
        ),
        render_profile=render_profile,
        render_profile_source_evidence=evidence,
    )

    contract = rendered.provenance_manifest.variable_envelope_contract
    assert contract is not None, "the composition disappeared between join and output"
    assert contract.envelope.record_identity == "DP200000"

    layout_record_ids = tuple(record.id for record in rendered.layout.records)
    assert contract.envelope.body_record_ids == layout_record_ids, (
        "the envelope must wrap exactly the fixed body records the layout emits, in order"
    )
    assert "DP200000" not in layout_record_ids, (
        "the wrapper was flattened into a fixed record, which is the truncation this gate exists for"
    )


def test_real_m220_composite_envelope_refuses_the_join_without_a_reviewed_contract() -> None:
    """The six typed closing rows cannot be truncated into a fixed M220 record.

    Modelo 220 has no authored mapping, so what protects it today is the join
    itself: a parser envelope with no reviewed semantic contract refuses, and
    the design cannot be generated into a fixed tree by omission. That refusal
    IS the protection this gate was written for, expressed in the mechanism
    that now carries it.

    When modelo 220's mapping is authored, this becomes the composed-rather-
    than-truncated assertion its m200 sibling makes, and the refusal below will
    fail loudly rather than passing vacuously -- which is what forces the
    upgrade instead of leaving a stale gate behind.
    """
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml"))
    inspection = bundled_revision_inspection("220", filing_year=2025, period="0A")
    parsed = load_record_design_intermediate(
        source_root,
        catalogues.sources,
        source_ref="aeat-dr-220-2025",
        filing_year=2025,
        design_epoch="2025",
    )

    assert parsed.variable_envelopes[0].record_identity == "T220000000"

    real_sheet = parsed.sheets[0]
    real_field = real_sheet.fields[0]
    # Focused to one sheet and one field so the exact-bijection check, which
    # runs first, is satisfied and the envelope refusal is what this reaches.
    focused = parsed.model_copy(
        update={
            "sheets": (
                real_sheet.model_copy(
                    update={
                        "declared_total": real_field.offset + real_field.length - 1,
                        "fields": (real_field,),
                    },
                ),
            ),
        },
    )
    semantic_map = SemanticMap.model_validate(
        {
            "modelo": "220",
            "design_epoch": "2025",
            "source_ref": parsed.source.source_ref,
            "source_sha256": parsed.source.source_sha256,
            "records": (
                {
                    "sheet": real_sheet.sheet,
                    "record_identity": real_sheet.record_identity,
                    "export_record_id": "m220-envelope-gate-record",
                    "record_type": "declaracion",
                },
            ),
            "entries": (
                {
                    "anchor": {
                        "sheet": real_field.sheet,
                        "source_row": real_field.source_row,
                        "source_cell": real_field.source_cell,
                        "ordinal": real_field.ordinal,
                        "record_identity": real_field.record_identity,
                    },
                    "export_field_id": "m220-envelope-gate-field",
                    "kind": "filler",
                    "legal_refs": ("ley-27-2014:art-40",),
                    "source_refs": ("aeat-dr-220-2025",),
                },
            ),
        },
    )

    with pytest.raises(RegistryValidationError, match="requires exactly one reviewed variable-envelope"):
        join_record_design_semantics(semantic_map, focused, inspection)
