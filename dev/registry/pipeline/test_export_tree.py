"""Real filesystem and loader proofs for generated export-tree rendering."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import ModuleType
from typing import TypedDict, get_args, override

import pytest
import rtoml

from cadrumo.core.directory_scan import (
    scan_directory,
)
from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.core.filing_projection_ref import (
    M303ProrrataActivityProjectionField,
    M303ProrrataActivityProjectionRef,
)
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import (
    RegistryError,
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.schema_base import CorpusTier, RegistrySourceKind
from cadrumo.domain.calculations.registry.schema_exports import ProjectionEndpointDeclaration, RecordDiscriminator
from cadrumo.domain.calculations.registry.static_inspection import (
    StaticGeneratedArtifactInspection,
    StaticGeneratedArtifactSource,
)

from ..author_family_identities import derive_projection_endpoint_id
from ..compiler.loader import load_modelo_directory
from . import _export_tree
from ._export_tree import ExportTreeTransportProfile, render_complete_export_tree
from .export_fragment_provenance import (
    EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    ExportFragmentTarget,
    _write_canonical_manifest_atomically,
    emit_export_fragment_provenance_manifest,
    export_fragment_provenance_manifest_json_bytes,
    load_export_fragment_provenance_manifest,
    verify_export_fragment_provenance_manifest,
)
from .joined_record_design import JoinedRecordDesign, JoinedRecordDesignField, join_record_design_semantics
from .record_design_intermediate import (
    RecordDesignIntermediate,
    RecordDesignWorkbookFormat,
)
from .render_profile import (
    RenderProfile,
    RenderProfileAnchor,
    RenderProfileDesignIdentity,
    RenderProfileSourceEvidence,
    ReviewedPolicyDecision,
    SingletonNumericRule,
    Width17MembershipRule,
)
from .semantic_map import SemanticMap

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_toml_serialization_refusal_never_carries_the_offending_value() -> None:
    """``_render_toml_bytes``'s ``rtoml.dumps`` refusal must never echo a payload value.

    ``rtoml.dumps`` raises ``TomlSerializationError`` (a ``ValueError``
    subclass) whose sole ``args[0]`` bakes the offending value's own ``repr``
    into the message, with no structured field that omits it -- measured:
    ``rtoml.dumps({"bad": object()})`` produces a string naming the object's
    default ``repr`` verbatim. Reproduced here with a payload carrying a
    short, easy-to-miss string alongside an unserializable object whose
    ``repr`` embeds that same string, proving the raw exception would carry
    it before pinning that the registry's own message never does.
    """
    probe_value = "nif-Z-taxpayer-value"

    class _Unserializable:
        @override
        def __repr__(self) -> str:
            return f"<unserializable probe_value={probe_value}>"

    with pytest.raises(ValueError) as raw_excinfo:
        rtoml.dumps({"bad": _Unserializable()}, pretty=True, none_value=None)
    assert probe_value in str(raw_excinfo.value), "premise: rtoml's own error must actually carry the value"

    with pytest.raises(RegistryValidationError) as excinfo:
        _export_tree._render_toml_bytes("generated/example.toml", {"bad": _Unserializable()})

    message = str(excinfo.value)
    assert probe_value not in message
    assert "unserializable" not in message
    assert "cannot serialize generated export TOML" in message
    assert "generated/example.toml" in message


def _intermediate(
    *,
    first_record_declared_total: int | None = 4,
    first_field_offset: int = 1,
    second_field_offset: int = 3,
    second_field_aeat_type: str = "A",
    numeric_content: str | None = "2 enteros y 2 decimales",
) -> RecordDesignIntermediate:
    return RecordDesignIntermediate.model_validate(
        {
            "source": {
                "source_ref": "aeat-dr-130-2019-v12",
                "source_sha256": "58f731b0c72eff7fd23484000c74e73e0ac803a5167065176d78cac8712f5fe7",
                "workbook_format": RecordDesignWorkbookFormat.XLSX,
                "design_epoch": "2019",
            },
            "sheets": (
                {
                    "sheet": "Registro tipo 1",
                    "record_identity": "registro-tipo-1",
                    "declared_total": first_record_declared_total,
                    "fields": (
                        {
                            "sheet": "Registro tipo 1",
                            "record_identity": "registro-tipo-1",
                            "source_row": 14,
                            "source_cell": "A14",
                            "ordinal": "1",
                            "offset": first_field_offset,
                            "length": 2,
                            "aeat_type": "An",
                            "normalized_description": "Apertura",
                            "validation": "OBLIGATORIO",
                            "content": 'Constante "<T"',
                        },
                        {
                            "sheet": "Registro tipo 1",
                            "record_identity": "registro-tipo-1",
                            "source_row": 15,
                            "source_cell": "A15",
                            "ordinal": "2",
                            "offset": second_field_offset,
                            "length": 2,
                            "aeat_type": second_field_aeat_type,
                            "normalized_description": "Periodo",
                            "validation": "OBLIGATORIO",
                        },
                    ),
                },
                {
                    "sheet": "Registro tipo 2",
                    "record_identity": "registro-tipo-2",
                    "declared_total": 5,
                    "fields": (
                        {
                            "sheet": "Registro tipo 2",
                            "record_identity": "registro-tipo-2",
                            "source_row": 20,
                            "source_cell": "A20",
                            "ordinal": "1",
                            "offset": 1,
                            "length": 1,
                            "aeat_type": "Num",
                            "normalized_description": "Tipo",
                            "content": 'Constante "2"',
                        },
                        {
                            "sheet": "Registro tipo 2",
                            "record_identity": "registro-tipo-2",
                            "source_row": 21,
                            "source_cell": "A21",
                            "ordinal": "2",
                            "offset": 2,
                            "length": 4,
                            "aeat_type": "Num",
                            "normalized_description": "Importe",
                            "content": numeric_content,
                        },
                    ),
                },
            ),
        },
    )


def _semantic_map() -> SemanticMap:
    return SemanticMap.model_validate(
        {
            "modelo": "130",
            "design_epoch": "2019",
            "source_ref": "aeat-dr-130-2019-v12",
            "source_sha256": "58f731b0c72eff7fd23484000c74e73e0ac803a5167065176d78cac8712f5fe7",
            "records": (
                {
                    "sheet": "Registro tipo 1",
                    "record_identity": "registro-tipo-1",
                    "export_record_id": "generated-registro-tipo-1",
                    "record_type": "cabecera",
                },
                {
                    "sheet": "Registro tipo 2",
                    "record_identity": "registro-tipo-2",
                    "export_record_id": "generated-registro-tipo-2",
                    "record_type": "detalle",
                },
            ),
            "entries": (
                _entry("Registro tipo 1", "registro-tipo-1", 14, 1, "generated.open", "literal", literal="<T"),
                _entry(
                    "Registro tipo 1",
                    "registro-tipo-1",
                    15,
                    2,
                    "generated.period",
                    "header",
                    producer_key=FilingProducerKey.PRESENTER_TAX_ID,
                ),
                _entry("Registro tipo 2", "registro-tipo-2", 20, 1, "generated.type", "literal", literal="2"),
                _entry(
                    "Registro tipo 2",
                    "registro-tipo-2",
                    21,
                    2,
                    "generated.amount",
                    "header",
                    producer_key=FilingProducerKey.FILING_RESULT_DISPOSITION,
                ),
            ),
        },
    )


def _entry(
    sheet: str,
    record_identity: str,
    row: int,
    ordinal: int,
    field_id: str,
    kind: str,
    **semantic_value: str,
) -> dict[str, object]:
    return {
        "anchor": {
            "sheet": sheet,
            "source_row": row,
            "source_cell": f"A{row}",
            "ordinal": str(ordinal),
            "record_identity": record_identity,
        },
        "export_field_id": field_id,
        "kind": kind,
        "legal_refs": ("rd-439-2007:art-110",),
        "source_refs": ("aeat-dr-130-2019-v12",),
        **semantic_value,
    }


def _profile() -> ExportTreeTransportProfile:
    return ExportTreeTransportProfile(
        modelo="130",
        design_epoch="2019",
        source_ref="aeat-dr-130-2019-v12",
        source_sha256="58f731b0c72eff7fd23484000c74e73e0ac803a5167065176d78cac8712f5fe7",
        layout_id="generated-modelo-130-fichero",
        format="fixed_width",
        encoding=ExportEncoding.ISO_8859_1,
        line_ending="crlf",
        serializer_convention="rtoml-pretty-v1",
    )


def _wire_profile() -> RenderProfile:
    identity = RenderProfileDesignIdentity(
        modelo="130",
        design_epoch="2019",
        source_ref="aeat-dr-130-2019-v12",
        source_sha256="58f731b0c72eff7fd23484000c74e73e0ac803a5167065176d78cac8712f5fe7",
    )
    return RenderProfile(
        schema_version=1,
        design_identity=identity,
        fragment_ids=(),
        width_17_rules=(),
        singleton_rules=(),
    )


def _wire_evidence() -> RenderProfileSourceEvidence:
    return RenderProfileSourceEvidence(
        design_identity=_wire_profile().design_identity,
        entries=(),
    )


def _blank_integer_profile() -> RenderProfile:
    anchor = RenderProfileAnchor(
        sheet="Registro tipo 2",
        source_row=21,
        source_cell="A21",
        ordinal="2",
        record_identity="registro-tipo-2",
    )
    return _wire_profile().model_copy(
        update={
            "fragment_ids": ("blank-integer",),
            "singleton_rules": (
                SingletonNumericRule(
                    rule_kind="singleton_numeric",
                    anchor=anchor,
                    aeat_type="Num",
                    semantic_kind="integer",
                    value_policy=ExportValuePolicy.UNSIGNED_INTEGER,
                    integer_digits=4,
                    decimal_digits=0,
                    sign_policy="unsigned",
                    allowed_values=(),
                    evidence=ReviewedPolicyDecision(
                        authority_kind="reviewed_policy",
                        decision_id="synthetic-blank-integer-proof",
                        governed_anchor=anchor,
                        decision_statement="This exact synthetic blank field is an unsigned integer.",
                        justification="The test exercises exact-anchor profile integration without inference.",
                    ),
                ),
            ),
        },
    )


def _joined(
    snapshot,
    *,
    numeric_content: str | None = "2 enteros y 2 decimales",
    second_field_aeat_type: str = "A",
):
    return join_record_design_semantics(
        _semantic_map(),
        _intermediate(numeric_content=numeric_content, second_field_aeat_type=second_field_aeat_type),
        snapshot,
    )


def _synthetic_static_inspection() -> StaticGeneratedArtifactInspection:
    """Return the narrow, non-filing source authority for parser-derivation bites."""
    source_ref = "aeat-dr-130-2019-v12"
    return StaticGeneratedArtifactInspection(
        modelo_id="130",
        revision_id="2019",
        revision_source_refs=(source_ref,),
        sources={
            source_ref: StaticGeneratedArtifactSource(
                id=source_ref,
                kind=RegistrySourceKind.RECORD_DESIGN,
                corpus_path="aeat_official/disenos_registro/modelo_130/files/synthetic.xlsx",
                sha256="58f731b0c72eff7fd23484000c74e73e0ac803a5167065176d78cac8712f5fe7",
                bytes=1,
                applies_from=None,
                applies_to=None,
                record_design_epoch="2019",
                corpus_tier=CorpusTier.FULL_CONSOLIDATED,
            ),
        },
        legal_ref_ids=frozenset(("rd-439-2007:art-110",)),
        casilla_ids=frozenset(),
        binding_ids=frozenset(),
        projection_endpoints=(),
    )


def _oversized_authorities(snapshot, *, field_count: int = 245) -> tuple[SemanticMap, JoinedRecordDesign]:
    fields = tuple(
        {
            "sheet": "Oversized record",
            "record_identity": "oversized-record",
            "source_row": 14 + index,
            "source_cell": f"A{14 + index}",
            "ordinal": str(index + 1),
            "offset": index + 1,
            "length": 1,
            "aeat_type": "An",
            "normalized_description": f"Reviewed filler {index + 1}",
        }
        for index in range(field_count)
    )
    intermediate = RecordDesignIntermediate.model_validate(
        {
            "source": {
                "source_ref": "aeat-dr-130-2019-v12",
                "source_sha256": "58f731b0c72eff7fd23484000c74e73e0ac803a5167065176d78cac8712f5fe7",
                "workbook_format": RecordDesignWorkbookFormat.XLSX,
                "design_epoch": "2019",
            },
            "sheets": (
                {
                    "sheet": "Oversized record",
                    "record_identity": "oversized-record",
                    "declared_total": field_count,
                    "fields": fields,
                },
                {
                    "sheet": "Trailing record",
                    "record_identity": "trailing-record",
                    "declared_total": 1,
                    "fields": (
                        {
                            "sheet": "Trailing record",
                            "record_identity": "trailing-record",
                            "source_row": 14,
                            "source_cell": "A14",
                            "ordinal": "1",
                            "offset": 1,
                            "length": 1,
                            "aeat_type": "An",
                            "normalized_description": "Reviewed trailing filler",
                        },
                    ),
                },
            ),
        },
    )
    semantic_map = SemanticMap.model_validate(
        {
            "modelo": "130",
            "design_epoch": "2019",
            "source_ref": "aeat-dr-130-2019-v12",
            "source_sha256": "58f731b0c72eff7fd23484000c74e73e0ac803a5167065176d78cac8712f5fe7",
            "records": (
                {
                    "sheet": "Oversized record",
                    "record_identity": "oversized-record",
                    "export_record_id": "generated-oversized-record",
                    "record_type": "detalle",
                },
                {
                    "sheet": "Trailing record",
                    "record_identity": "trailing-record",
                    "export_record_id": "generated-trailing-record",
                    "record_type": "pie",
                },
            ),
            "entries": (
                *(
                    _entry(
                        "Oversized record",
                        "oversized-record",
                        14 + index,
                        index + 1,
                        f"generated.oversized.field-{index + 1:03d}",
                        "filler",
                    )
                    for index in range(field_count)
                ),
                _entry(
                    "Trailing record",
                    "trailing-record",
                    14,
                    1,
                    "generated.trailing.field",
                    "filler",
                ),
            ),
        },
    )
    return semantic_map, join_record_design_semantics(semantic_map, intermediate, snapshot)


def _write_modelo_shell(modelo_dir: Path) -> Path:
    revision_dir = modelo_dir / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    (modelo_dir / "manifest.toml").write_text(
        """
[modelo]
id = "130"
tax_domain = "irpf"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["rd-439-2007:art-110"]
source_refs = ["aeat-dr-130-2019-v12"]
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "revision.toml").write_text(
        """
[revisions."2025"]
authority_grade = "applicability"
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["rd-439-2007:art-110"]
source_refs = ["aeat-dr-130-2019-v12"]
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    return revision_dir


_VALIDATION_MANIFEST = """\
[modelo]
id = "130"
tax_domain = "irpf"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["rd-439-2007:art-110", "orden-eha-672-2007:art-1"]
source_refs = ["aeat-dr-130-2019-v12", "aeat-modelo-130-instructions"]
"""

_VALIDATION_REVISION = """\
[revisions."2025"]
authority_grade = "applicability"
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["rd-439-2007:art-110", "orden-eha-672-2007:art-1"]
source_refs = ["aeat-dr-130-2019-v12", "aeat-modelo-130-instructions"]
orden_aplicabilidad = ["orden-eha-672-2007:art-1"]
"""

_VALIDATION_APPLICATION_LINKS = """\
[[revisions."2025".application_links]]
id = "generated-export-link"
surface = "export"
consumer = "cli.app"
requires_snapshot = true
legal_refs = ["rd-439-2007:art-110"]
source_refs = ["aeat-dr-130-2019-v12"]

[[revisions."2025".application_links]]
id = "generated-filing-link"
surface = "filing"
consumer = "cli.app"
requires_snapshot = true
legal_refs = ["rd-439-2007:art-110"]
source_refs = ["aeat-modelo-130-instructions"]
"""

_VALIDATION_CASILLAS = """\
[[revisions."2025".casillas]]
id = "01"
number = "01"
section = ["generated"]
data_type = "integer"
legal_refs = ["rd-439-2007:art-110"]
source_refs = ["aeat-dr-130-2019-v12"]
"""

_VALIDATION_WORKBOOK_PARITY = """\
[[revisions."2025".workbook_parity_refs]]
id = "generated-workbook-parity"
workbook_source = "aeat-dr-130-2019-v12"
fixture_id = "generated-tree-validation"
formula_coverage = "record_design_layout"
runner_required = false
tolerance = "0.00"
legal_refs = ["rd-439-2007:art-110"]
source_refs = ["aeat-dr-130-2019-v12"]
"""


def test_renderer_writes_stable_complete_tree_that_real_directory_loader_merges(
    m130_inspection_snapshot, tmp_path
) -> None:
    """The output is fresh canonical TOML that the real loader compiles by its fragment rules."""
    revision_dir = _write_modelo_shell(tmp_path / "modelos" / "130")
    first = render_complete_export_tree(
        revision_dir / "export",
        revision_id="2025",
        joined=_joined(m130_inspection_snapshot),
        semantic_map=_semantic_map(),
        transport_profile=_profile(),
        render_profile=_wire_profile(),
        render_profile_source_evidence=_wire_evidence(),
    )
    duplicate_revision_dir = _write_modelo_shell(tmp_path / "comparison" / "modelos" / "130")
    second = render_complete_export_tree(
        duplicate_revision_dir / "export",
        revision_id="2025",
        joined=_joined(m130_inspection_snapshot),
        semantic_map=_semantic_map(),
        transport_profile=_profile(),
        render_profile=_wire_profile(),
        render_profile_source_evidence=_wire_evidence(),
    )

    assert first.output_files == (
        "0000-export-layout.toml",
        "0001-record-generated-registro-tipo-1.toml",
        "0002-record-generated-registro-tipo-2.toml",
    )
    assert first.field_derivations[-1].derivation_code == "numeric-decimal-v1"
    assert first.layout == second.layout
    assert {
        path.relative_to(revision_dir / "export").as_posix(): path.read_bytes()
        for path in scan_directory(revision_dir / "export")
    } == {
        path.relative_to(duplicate_revision_dir / "export").as_posix(): path.read_bytes()
        for path in scan_directory(duplicate_revision_dir / "export")
    }

    loaded = load_modelo_directory(tmp_path / "modelos" / "130")
    layout = loaded.revisions["2025"].export_layouts[0]
    manifest_path = revision_dir / "export" / EXPORT_FRAGMENT_PROVENANCE_FILENAME
    assert manifest_path.is_file()
    assert manifest_path.name not in first.output_files
    assert load_export_fragment_provenance_manifest(manifest_path.read_bytes()) == first.provenance_manifest
    assert (
        verify_export_fragment_provenance_manifest(
            export_root=revision_dir / "export",
            joined=_joined(m130_inspection_snapshot),
            semantic_map=_semantic_map(),
            target=ExportFragmentTarget(modelo="130", revision_id="2025", design_epoch="2019"),
            loaded_layout=layout,
            field_derivations=first.field_derivations,
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )
        == first.provenance_manifest
    )
    assert layout == first.layout


def test_real_loader_accepts_only_generator_owned_export_provenance(m130_inspection_snapshot, tmp_path) -> None:
    """The generated JSON sidecar is structural evidence, not a TOML fragment."""
    revision_dir = _write_modelo_shell(tmp_path / "modelos" / "130")
    render_complete_export_tree(
        revision_dir / "export",
        revision_id="2025",
        joined=_joined(m130_inspection_snapshot),
        semantic_map=_semantic_map(),
        transport_profile=_profile(),
        render_profile=_wire_profile(),
        render_profile_source_evidence=_wire_evidence(),
    )

    loaded = load_modelo_directory(tmp_path / "modelos" / "130")
    assert loaded.revisions["2025"].export_layouts

    unexpected = revision_dir / "export" / "unexpected.json"
    unexpected.write_text("{}\n", encoding="utf-8", newline="\n")
    with pytest.raises(RegistryError, match="unrecognized revision fragment file"):
        load_modelo_directory(tmp_path / "modelos" / "130")


@pytest.mark.parametrize("required", [False, True])
def test_renderer_carries_semantic_projection_occurrence_authority_into_generated_record(
    m130_inspection_snapshot,
    tmp_path,
    required: bool,
) -> None:
    semantic_map = _semantic_map()
    projection_entry = semantic_map.entries[-1].model_copy(
        update={
            "kind": CasillaFieldKind.PROJECTION,
            "producer_key": None,
            "projection_ref": M303ProrrataActivityProjectionRef(
                projection_kind="m303_prorrata_activity",
                slot=1,
                field=M303ProrrataActivityProjectionField.CNAE,
                casilla_id="500",
            ),
        },
    )
    records = tuple(
        record.model_copy(update={"repeat": "projection_rows", "required": required}) if index == 1 else record
        for index, record in enumerate(semantic_map.records)
    )
    semantic_map = semantic_map.model_copy(
        update={"records": records, "entries": (*semantic_map.entries[:-1], projection_entry)},
    )
    assert projection_entry.projection_ref is not None
    projection_endpoints = (
        ProjectionEndpointDeclaration(
            id=derive_projection_endpoint_id(
                {"projection_ref": projection_entry.projection_ref.model_dump(mode="json")}
            ),
            projection_ref=projection_entry.projection_ref,
            legal_refs=("rd-439-2007:art-110",),
            source_refs=("aeat-dr-130-2019-v12",),
        ),
    )
    inspection = m130_inspection_snapshot.model_copy(update={"projection_endpoints": projection_endpoints})
    joined = join_record_design_semantics(semantic_map, _intermediate(), inspection)

    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id="2025",
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=_profile(),
        render_profile=_wire_profile(),
        render_profile_source_evidence=_wire_evidence(),
    )

    assert rendered.layout.records[1].repeat == "projection_rows"
    assert rendered.layout.records[1].required is required


def test_renderer_carries_semantic_record_discriminator_into_generated_record(
    m130_inspection_snapshot,
    tmp_path,
) -> None:
    semantic_map = _semantic_map()
    records = tuple(
        record.model_copy(update={"discriminator": RecordDiscriminator(offset=3, length=1, requires="blank")})
        if index == 1
        else record
        for index, record in enumerate(semantic_map.records)
    )
    semantic_map = semantic_map.model_copy(update={"records": records})
    joined = join_record_design_semantics(semantic_map, _intermediate(), m130_inspection_snapshot)

    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id="2025",
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=_profile(),
        render_profile=_wire_profile(),
        render_profile_source_evidence=_wire_evidence(),
    )

    assert rendered.layout.records[1].discriminator == RecordDiscriminator(offset=3, length=1, requires="blank")


def test_renderer_manifest_refuses_file_tampering_derivation_drift_and_partial_field_evidence(
    m130_inspection_snapshot,
    tmp_path,
) -> None:
    """Only the fresh full renderer result can attest its real generated tree."""
    revision_dir = _write_modelo_shell(tmp_path / "modelos" / "130")
    rendered = render_complete_export_tree(
        revision_dir / "export",
        revision_id="2025",
        joined=_joined(m130_inspection_snapshot),
        semantic_map=_semantic_map(),
        transport_profile=_profile(),
        render_profile=_wire_profile(),
        render_profile_source_evidence=_wire_evidence(),
    )
    layout = load_modelo_directory(tmp_path / "modelos" / "130").revisions["2025"].export_layouts[0]
    export_root = revision_dir / "export"
    manifest_path = revision_dir / "export" / EXPORT_FRAGMENT_PROVENANCE_FILENAME
    original_fragment = export_root / "0001-record-generated-registro-tipo-1.toml"
    original_bytes = original_fragment.read_bytes()

    original_fragment.write_bytes(original_bytes + b"# tampered\n")
    with pytest.raises(RegistryValidationError, match="output-file digests"):
        verify_export_fragment_provenance_manifest(
            export_root=export_root,
            joined=_joined(m130_inspection_snapshot),
            semantic_map=_semantic_map(),
            target=ExportFragmentTarget(modelo="130", revision_id="2025", design_epoch="2019"),
            loaded_layout=layout,
            field_derivations=rendered.field_derivations,
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )
    original_fragment.write_bytes(original_bytes)

    manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
    authority_tampered_manifest = manifest.model_copy(update={"source_sha256": "b" * 64})
    manifest_path.write_bytes(export_fragment_provenance_manifest_json_bytes(authority_tampered_manifest))
    with pytest.raises(RegistryValidationError, match="current generation authorities"):
        verify_export_fragment_provenance_manifest(
            export_root=export_root,
            joined=_joined(m130_inspection_snapshot),
            semantic_map=_semantic_map(),
            target=ExportFragmentTarget(modelo="130", revision_id="2025", design_epoch="2019"),
            loaded_layout=layout,
            field_derivations=rendered.field_derivations,
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    drifted_derivation = manifest.field_derivations[0].model_copy(update={"derivation_code": "filler-v1"})
    drifted_manifest = manifest.model_copy(
        update={"field_derivations": (drifted_derivation, *manifest.field_derivations[1:])},
    )
    manifest_path.write_bytes(export_fragment_provenance_manifest_json_bytes(drifted_manifest))
    with pytest.raises(RegistryValidationError, match="field derivations do not match"):
        verify_export_fragment_provenance_manifest(
            export_root=export_root,
            joined=_joined(m130_inspection_snapshot),
            semantic_map=_semantic_map(),
            target=ExportFragmentTarget(modelo="130", revision_id="2025", design_epoch="2019"),
            loaded_layout=layout,
            field_derivations=rendered.field_derivations,
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    partial_manifest = manifest.model_copy(update={"field_derivations": manifest.field_derivations[:-1]})
    manifest_path.write_bytes(export_fragment_provenance_manifest_json_bytes(partial_manifest))
    with pytest.raises(RegistryValidationError, match="do not cover exactly"):
        verify_export_fragment_provenance_manifest(
            export_root=export_root,
            joined=_joined(m130_inspection_snapshot),
            semantic_map=_semantic_map(),
            target=ExportFragmentTarget(modelo="130", revision_id="2025", design_epoch="2019"),
            loaded_layout=layout,
            field_derivations=rendered.field_derivations,
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )


def test_generated_export_target_refuses_a_link_even_though_the_name_and_kind_look_right(
    m130_inspection_snapshot,
    tmp_path,
) -> None:
    """The renderer must not write through a link masquerading as the export target.

    The module docstring promises a tree written "without opening a shipped
    fragment directory or deriving any output fact from one." A link named
    ``export`` that resolves elsewhere is exactly how that isolation would be
    defeated silently: `.exists()` and `.is_dir()` both admit it, so only the
    dedicated link check stands between this call and writing through it.
    """
    real_elsewhere = tmp_path / "real_elsewhere"
    real_elsewhere.mkdir()
    link_target = tmp_path / "export"
    link_target.symlink_to(real_elsewhere, target_is_directory=True)

    with pytest.raises(RegistryValidationError, match="must not be a link"):
        render_complete_export_tree(
            link_target,
            revision_id="2025",
            joined=_joined(m130_inspection_snapshot),
            semantic_map=_semantic_map(),
            transport_profile=_profile(),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )
    assert not any(real_elsewhere.iterdir())


def test_generated_export_target_accepts_a_real_preexisting_empty_directory(
    m130_inspection_snapshot,
    tmp_path,
) -> None:
    """Sibling-blindness check: a genuine empty directory is not mistaken for a link.

    Same name, same "already exists as a directory" shape as the refused link
    above, but no reparse point involved. The link guard must not fire here,
    and the render must proceed and populate the real directory in place.
    """
    real_target = tmp_path / "export"
    real_target.mkdir()

    rendered = render_complete_export_tree(
        real_target,
        revision_id="2025",
        joined=_joined(m130_inspection_snapshot),
        semantic_map=_semantic_map(),
        transport_profile=_profile(),
        render_profile=_wire_profile(),
        render_profile_source_evidence=_wire_evidence(),
    )

    assert rendered.output_files
    assert all((real_target / relative_path).is_file() for relative_path in rendered.output_files)


def test_direct_manifest_emission_and_real_loader_verification(m130_inspection_snapshot, tmp_path) -> None:
    """The public provenance-manifest emitter and verifier operate on a real fresh tree only."""
    revision_dir = _write_modelo_shell(tmp_path / "modelos" / "130")
    semantic_map = _semantic_map()
    joined = _joined(m130_inspection_snapshot)
    rendered = render_complete_export_tree(
        revision_dir / "export",
        revision_id="2025",
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=_profile(),
        render_profile=_wire_profile(),
        render_profile_source_evidence=_wire_evidence(),
    )
    layout = load_modelo_directory(tmp_path / "modelos" / "130").revisions["2025"].export_layouts[0]
    manifest_path = revision_dir / "export" / EXPORT_FRAGMENT_PROVENANCE_FILENAME
    manifest_path.unlink()

    emitted = emit_export_fragment_provenance_manifest(
        joined=joined,
        semantic_map=semantic_map,
        target=ExportFragmentTarget(modelo="130", revision_id="2025", design_epoch="2019"),
        loaded_layout=layout,
        export_root=revision_dir / "export",
        field_derivations=rendered.field_derivations,
        render_profile=_wire_profile(),
        render_profile_source_evidence=_wire_evidence(),
    )

    assert load_export_fragment_provenance_manifest(manifest_path.read_bytes()) == emitted
    assert (
        verify_export_fragment_provenance_manifest(
            export_root=revision_dir / "export",
            joined=joined,
            semantic_map=semantic_map,
            target=ExportFragmentTarget(modelo="130", revision_id="2025", design_epoch="2019"),
            loaded_layout=layout,
            field_derivations=rendered.field_derivations,
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )
        == emitted
    )


def test_manifest_writer_refuses_a_target_that_already_exists(tmp_path) -> None:
    """Pin the refusal this writer delegates to its publish-once primitive.

    The development-owned primitive publishes with :func:`os.link`, which fails
    with :exc:`FileExistsError` in one uninterruptible step rather than
    overwriting. This test pins this boundary's registry-error translation.

    The first write is the positive control -- without it a refusal that fired
    unconditionally, or a writer that never wrote at all, would pass too.
    """
    target = tmp_path / EXPORT_FRAGMENT_PROVENANCE_FILENAME

    _write_canonical_manifest_atomically(target, b'{"first": true}')
    assert target.read_bytes() == b'{"first": true}'

    with pytest.raises(RegistryValidationError, match="already exists"):
        _write_canonical_manifest_atomically(target, b'{"second": true}')

    assert target.read_bytes() == b'{"first": true}', "the refused write must not have replaced the target"
    assert scan_directory(tmp_path) == (target,), "the refused write must not leave its staging tempfile behind"


def test_renderer_refuses_mismatched_map_without_emitting_a_manifest(m130_inspection_snapshot, tmp_path) -> None:
    """Manifest emission never leaves a partial sibling attestation when map authority drifts."""
    revision_dir = _write_modelo_shell(tmp_path / "modelos" / "130")
    semantic_map = _semantic_map()
    mismatched_map = semantic_map.model_copy(
        update={
            "entries": (
                semantic_map.entries[0].model_copy(update={"literal": "XX"}),
                *semantic_map.entries[1:],
            ),
        },
    )

    with pytest.raises(RegistryValidationError, match="joined fields do not attest"):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id="2025",
            joined=_joined(m130_inspection_snapshot),
            semantic_map=mismatched_map,
            transport_profile=_profile(),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    with pytest.raises(RegistryValidationError, match="semantic-map SHA-256 does not match joined official source"):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id="2025",
            joined=_joined(m130_inspection_snapshot),
            semantic_map=semantic_map.model_copy(update={"source_sha256": "b" * 64}),
            transport_profile=_profile(),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    assert not (revision_dir / "export" / EXPORT_FRAGMENT_PROVENANCE_FILENAME).exists()


def test_renderer_refuses_semantic_map_source_and_incomplete_entries_without_emitting_a_manifest(
    m130_inspection_snapshot,
    tmp_path,
) -> None:
    """The remaining two semantic-map attestation comparisons must each refuse on their own
    terms rather than inherit coverage from the coarse whole-map and SHA-256 siblings pinned
    above: a source-ref drift on the map argument, and an entries set that no longer bijects
    the compiled map once the joined design itself carries a duplicated field."""
    revision_dir = _write_modelo_shell(tmp_path / "modelos" / "130")
    semantic_map = _semantic_map()

    with pytest.raises(RegistryValidationError, match=r"semantic-map source .+ does not match joined source"):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id="2025",
            joined=_joined(m130_inspection_snapshot),
            semantic_map=semantic_map.model_copy(update={"source_ref": "aeat-dr-130-2019-v13"}),
            transport_profile=_profile(),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    # The coarse whole-map equality check above intercepts every semantic_map
    # argument that merely differs from what the join used, so the
    # entries-completeness comparison can only be reached by keeping that
    # argument identical to the join's own authored map and instead corrupting
    # the JOINED design: one already-joined field duplicated so its flattened
    # entry set no longer bijects the compiled map's entries.
    joined = _joined(m130_inspection_snapshot)
    joined_with_duplicated_field = joined.model_copy(update={"fields": (*joined.fields, joined.fields[0])})

    with pytest.raises(
        RegistryValidationError,
        match="joined fields do not attest the supplied complete semantic map",
    ):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id="2025",
            joined=joined_with_duplicated_field,
            semantic_map=semantic_map,
            transport_profile=_profile(),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    assert not (revision_dir / "export" / EXPORT_FRAGMENT_PROVENANCE_FILENAME).exists()


def test_renderer_tolerates_reordered_joined_fields_without_tripping_the_entries_gate(
    m130_inspection_snapshot,
    tmp_path,
) -> None:
    """Sibling-blindness for the entries-completeness gate above: it compares the joined
    fields' entries as a SET against the compiled map's entries, so reordering those fields
    without dropping or duplicating any of them must still render cleanly. A gate that fired
    on any change to field order, rather than genuine incompleteness, would not have proven
    the completeness comparison the prior test exercises."""
    joined = _joined(m130_inspection_snapshot)
    reordered_fields = (joined.fields[1], joined.fields[0], *joined.fields[2:])
    reordered_joined = joined.model_copy(update={"fields": reordered_fields})

    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id="2025",
        joined=reordered_joined,
        semantic_map=_semantic_map(),
        transport_profile=_profile(),
        render_profile=_wire_profile(),
        render_profile_source_evidence=_wire_evidence(),
    )

    assert rendered.output_files


def test_renderer_refuses_incomplete_joined_records_without_emitting_a_manifest(
    m130_inspection_snapshot,
    tmp_path,
) -> None:
    """The records-completeness comparison is the fifth attestation raise and, unlike the
    entries duplication above, a literal duplicated record collides with the renderer's own
    duplicate-output-id refusal before this comparison is ever reached (proven: duplicating
    ``joined.records[0]`` raises "generated export tree has duplicate record id", not this
    comparison's message, because a shared ``semantic_record`` always shares its rendered
    export_record_id). Dropping a record from the joined design instead -- so the joined set
    is a proper subset of the compiled map's records, with no id collision -- reaches the
    comparison this raise site actually guards."""
    revision_dir = _write_modelo_shell(tmp_path / "modelos" / "130")
    joined = _joined(m130_inspection_snapshot)
    joined_missing_a_record = joined.model_copy(update={"records": joined.records[:1]})

    with pytest.raises(
        RegistryValidationError,
        match="joined records do not attest the supplied complete semantic map",
    ):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id="2025",
            joined=joined_missing_a_record,
            semantic_map=_semantic_map(),
            transport_profile=_profile(),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    assert not (revision_dir / "export" / EXPORT_FRAGMENT_PROVENANCE_FILENAME).exists()


def test_renderer_tolerates_reordered_joined_records_without_tripping_the_records_gate(
    m130_inspection_snapshot,
    tmp_path,
) -> None:
    """Sibling-blindness for the records-completeness gate above: it compares joined records
    as a SET against the compiled map's records, so reordering them without dropping or
    duplicating any must still render cleanly."""
    joined = _joined(m130_inspection_snapshot)
    reordered_records = (joined.records[1], joined.records[0])
    reordered_joined = joined.model_copy(update={"records": reordered_records})

    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id="2025",
        joined=reordered_joined,
        semantic_map=_semantic_map(),
        transport_profile=_profile(),
        render_profile=_wire_profile(),
        render_profile_source_evidence=_wire_evidence(),
    )

    assert rendered.output_files


def test_renderer_refuses_transport_profile_identity_axes_without_emitting_a_manifest(
    m130_inspection_snapshot,
    tmp_path,
) -> None:
    """The transport profile's modelo, design-epoch, source-ref, and serializer-convention
    comparisons must each refuse on their own terms: the sibling SHA-256 comparison already
    pinned in ``test_renderer_refuses_mismatched_map_without_emitting_a_manifest`` proves only
    that one axis, and two differently-named parametrize labels that both mutate the SHA-256
    field would leave these other four axes silently undriven."""
    revision_dir = _write_modelo_shell(tmp_path / "modelos" / "130")
    profile = _profile()

    with pytest.raises(RegistryValidationError, match="export tree transport profile modelo"):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id="2025",
            joined=_joined(m130_inspection_snapshot),
            semantic_map=_semantic_map(),
            transport_profile=profile.model_copy(update={"modelo": "184"}),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    with pytest.raises(RegistryValidationError, match="export tree transport profile design epoch"):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id="2025",
            joined=_joined(m130_inspection_snapshot),
            semantic_map=_semantic_map(),
            transport_profile=profile.model_copy(update={"design_epoch": "2020"}),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    with pytest.raises(RegistryValidationError, match="export tree transport profile source "):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id="2025",
            joined=_joined(m130_inspection_snapshot),
            semantic_map=_semantic_map(),
            transport_profile=profile.model_copy(update={"source_ref": "aeat-dr-130-2019-v13"}),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    with pytest.raises(RegistryValidationError, match="export tree transport profile serializer"):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id="2025",
            joined=_joined(m130_inspection_snapshot),
            semantic_map=_semantic_map(),
            transport_profile=profile.model_copy(update={"serializer_convention": "unsupported-convention"}),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    assert not (revision_dir / "export" / EXPORT_FRAGMENT_PROVENANCE_FILENAME).exists()


def test_renderer_tolerates_transport_profile_line_ending_drift(m130_inspection_snapshot, tmp_path) -> None:
    """Sibling-blindness for the transport-profile identity gate above: it compares five
    named axes (modelo, design epoch, source ref, source digest, serializer convention), not
    the profile as a whole, so a drifted line_ending -- not one of those axes -- must reach a
    normal render rather than tripping any of the four gates just pinned."""
    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id="2025",
        joined=_joined(m130_inspection_snapshot),
        semantic_map=_semantic_map(),
        transport_profile=_profile().model_copy(update={"line_ending": "lf"}),
        render_profile=_wire_profile(),
        render_profile_source_evidence=_wire_evidence(),
    )

    assert rendered.output_files


def test_renderer_refuses_uncovered_blank_numeric_anchor_without_emitting_a_partial_fragment(
    m130_inspection_snapshot,
    tmp_path,
) -> None:
    """A blank numeric field needs its exact reviewed profile rule before output."""
    target = tmp_path / "export"

    with pytest.raises(RegistryValidationError, match="must cover exactly the eligible blank numeric fields"):
        render_complete_export_tree(
            target,
            revision_id="2025",
            joined=_joined(m130_inspection_snapshot, numeric_content=None),
            semantic_map=_semantic_map(),
            transport_profile=_profile(),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    assert not target.exists()


def test_renderer_resolves_one_blank_numeric_field_only_through_its_exact_profile_anchor(
    m130_inspection_snapshot,
    tmp_path,
) -> None:
    revision_dir = _write_modelo_shell(tmp_path / "modelos" / "130")
    joined = _joined(m130_inspection_snapshot, numeric_content=None)
    profile = _blank_integer_profile()

    rendered = render_complete_export_tree(
        revision_dir / "export",
        revision_id="2025",
        joined=joined,
        semantic_map=_semantic_map(),
        transport_profile=_profile(),
        render_profile=profile,
        render_profile_source_evidence=_wire_evidence(),
    )
    loaded = load_modelo_directory(tmp_path / "modelos" / "130").revisions["2025"].export_layouts[0]
    derived = rendered.field_derivations[-1]

    assert loaded == rendered.layout
    assert derived.derivation_code == "render-profile-singleton-v1"
    assert derived.field.value_policy == "unsigned-integer"
    assert derived.field.data_type == "integer"
    assert derived.field.length == 4
    assert rendered.provenance_manifest.render_profile_sha256 != "0" * 64


class _IntermediateKwargs(TypedDict, total=False):
    first_record_declared_total: int | None
    first_field_offset: int
    second_field_offset: int
    numeric_content: str | None


@pytest.mark.parametrize(
    ("intermediate_kwargs", "error"),
    (
        ({"first_record_declared_total": None}, "no declared total"),
        ({"first_field_offset": 2}, "expected offset 1, got 2"),
        ({"second_field_offset": 4, "first_record_declared_total": 5}, "has a gap"),
        ({"second_field_offset": 2, "first_record_declared_total": 3}, "has an overlap"),
        ({"first_record_declared_total": 5}, "declares total 5, but parsed fields end at 4"),
    ),
)
def test_renderer_refuses_missing_or_noncontiguous_official_record_geometry(
    m130_inspection_snapshot,
    tmp_path,
    intermediate_kwargs: _IntermediateKwargs,
    error: str,
) -> None:
    """No inferred total, first position, gap, overlap, or terminal extent may be emitted."""
    target = tmp_path / "export"
    joined = join_record_design_semantics(
        _semantic_map(),
        _intermediate(**intermediate_kwargs),
        m130_inspection_snapshot,
    )

    with pytest.raises(RegistryValidationError, match=error):
        render_complete_export_tree(
            target,
            revision_id="2025",
            joined=joined,
            semantic_map=_semantic_map(),
            transport_profile=_profile(),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    assert not target.exists()


def test_renderer_refuses_unstructured_quoted_numeric_prose(m130_inspection_snapshot, tmp_path) -> None:
    """Quoted digits form an enum only under the reviewed comma-delimited source grammar."""
    target = tmp_path / "export"
    joined = _joined(
        m130_inspection_snapshot,
        # Four digits each, matching the slot the fixture declares. The values
        # were five digits wide, so the slot-width refusal fired first and this
        # case never reached the ambiguity it is about -- both refusals are
        # correct, but only one is this test's subject.
        numeric_content='"0000" only if the taxpayer elects "0050"',
    )

    with pytest.raises(RegistryValidationError, match="ambiguous content"):
        render_complete_export_tree(
            target,
            revision_id="2025",
            joined=joined,
            semantic_map=_semantic_map(),
            transport_profile=_profile(),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    assert not target.exists()


def test_note_governed_numeric_enumeration_retains_the_period_specific_closed_domain() -> None:
    """The official Nota 8/9 form adds ``0`` without opening the enum.

    The annotation is the mutation: without the paired notes the two printed
    values remain the complete closed enum; with the pair, ``0`` is a required
    period-reserved wire token in addition to the printed Yes/No values.
    """
    annotated = (
        _joined(
            _synthetic_static_inspection(),
            numeric_content='"0001" SI, "0002" NO. Nota 8. Nota 9',
        )
        .records[1]
        .fields[1]
    )
    unannotated = (
        _joined(
            _synthetic_static_inspection(),
            numeric_content='"0001" SI, "0002" NO',
        )
        .records[1]
        .fields[1]
    )
    incomplete_note_pair = (
        _joined(
            _synthetic_static_inspection(),
            numeric_content='"0001" SI, "0002" NO. Nota 8',
        )
        .records[1]
        .fields[1]
    )

    annotated_derivation = _export_tree._numeric_derivation(
        annotated,
        export_record_id="generated-record-type-2",
    )
    unannotated_derivation = _export_tree._numeric_derivation(
        unannotated,
        export_record_id="generated-record-type-2",
    )
    incomplete_note_pair_derivation = _export_tree._numeric_derivation(
        incomplete_note_pair,
        export_record_id="generated-record-type-2",
    )

    assert annotated_derivation.field.value_policy is ExportValuePolicy.ENUMERATED_DIGITS
    assert annotated_derivation.field.allowed_values == ("0", "1", "2")
    assert annotated_derivation.derivation_code == "numeric-enumeration-v1"
    assert unannotated_derivation.field.value_policy is ExportValuePolicy.ENUMERATED_DIGITS
    assert unannotated_derivation.field.allowed_values == ("1", "2")
    assert incomplete_note_pair_derivation.field.allowed_values == ("1", "2")


def test_renderer_refuses_profile_hash_drift_literal_extent_and_nonempty_target(
    m130_inspection_snapshot, tmp_path
) -> None:
    """The renderer rejects unsafe authority mismatches and never overwrites a prior output."""
    joined = _joined(m130_inspection_snapshot)
    with pytest.raises(RegistryValidationError, match="SHA-256"):
        render_complete_export_tree(
            tmp_path / "export",
            revision_id="2025",
            joined=joined,
            semantic_map=_semantic_map(),
            transport_profile=_profile().model_copy(update={"source_sha256": "b" * 64}),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    literal_map = _semantic_map().model_copy(
        update={
            "entries": (
                _semantic_map().entries[0].model_copy(update={"literal": "TOO LONG"}),
                *_semantic_map().entries[1:],
            ),
        },
    )
    intermediate = _intermediate()
    first_sheet = intermediate.sheets[0]
    oversized_literal = first_sheet.fields[0].model_copy(update={"content": 'Constante "TOO LONG"'})
    intermediate = intermediate.model_copy(
        update={
            "sheets": (
                first_sheet.model_copy(update={"fields": (oversized_literal, *first_sheet.fields[1:])}),
                *intermediate.sheets[1:],
            ),
        },
    )
    with pytest.raises(RegistryValidationError, match="encoded bytes"):
        render_complete_export_tree(
            tmp_path / "second" / "export",
            revision_id="2025",
            joined=join_record_design_semantics(literal_map, intermediate, m130_inspection_snapshot),
            semantic_map=literal_map,
            transport_profile=_profile(),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )
    assert not (tmp_path / "second" / "export").exists()

    occupied = tmp_path / "occupied" / "export"
    occupied.mkdir(parents=True)
    (occupied / "foreign.toml").write_text("value = 1\n", encoding="utf-8")
    with pytest.raises(RegistryValidationError, match="not empty"):
        render_complete_export_tree(
            occupied,
            revision_id="2025",
            joined=joined,
            semantic_map=_semantic_map(),
            transport_profile=_profile(),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )


@pytest.mark.parametrize(
    "official_content",
    (
        None,
        'Constante "<T" o "ZZ"',
        'Constante "<T". o "ZZ"',
        'Constante "E". o "S". rentas.',
        'Constante "E". rentas.\no "S".',
        'Constante "<T',
    ),
)
def test_renderer_refuses_missing_or_ambiguous_official_literal_without_output(
    m130_inspection_snapshot,
    tmp_path,
    official_content: str | None,
) -> None:
    """Literal meaning never substitutes for absent or ambiguous official constant bytes."""
    intermediate = _intermediate()
    first_sheet = intermediate.sheets[0]
    first_field = first_sheet.fields[0].model_copy(update={"content": official_content})
    intermediate = intermediate.model_copy(
        update={
            "sheets": (
                first_sheet.model_copy(update={"fields": (first_field, *first_sheet.fields[1:])}),
                *intermediate.sheets[1:],
            ),
        },
    )
    semantic_map = _semantic_map()
    target = tmp_path / "export"

    with pytest.raises(RegistryValidationError, match="official constant"):
        render_complete_export_tree(
            target,
            revision_id="2025",
            joined=join_record_design_semantics(semantic_map, intermediate, m130_inspection_snapshot),
            semantic_map=semantic_map,
            transport_profile=_profile(),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    assert not target.exists()


def test_labelled_official_literal_accepts_the_m184_sentence_stop_but_not_an_alternative() -> None:
    """M184 2025 prints the constant before a merged explanatory sentence."""
    labelled = _export_tree._OFFICIAL_LABELLED_LITERAL_RE.fullmatch(
        'Constante "E". rentas. Declaración anual.',
    )

    assert labelled is not None
    assert labelled.group("literal") == "E"
    assert _export_tree._OFFICIAL_ALTERNATIVE_LITERALS_RE.fullmatch('Constante "E". o "S". rentas.') is not None
    assert _export_tree._OFFICIAL_ALTERNATIVE_LITERALS_RE.fullmatch('Constante "E". rentas.\no "S".') is not None


def test_labelled_official_literal_accepts_m296_field_enumeration_after_the_constant() -> None:
    """M296's later quoted 1/2 values describe another field, not tipo-hoja."""
    official_content = (
        "Constante «F» ANEXO «VALORES NEGOCIABLES. RELACIÓN DE PAGO A CONTRIBUYENTES» "
        'Sólo para claves de percepción "1" ó "2" (posiciones 100-101 del tipo de registro 2).'
    )
    folded = official_content.translate(_export_tree._OFFICIAL_QUOTE_FOLD)

    assert _export_tree._OFFICIAL_ALTERNATIVE_LITERALS_RE.fullmatch(folded) is None
    labelled = _export_tree._OFFICIAL_LABELLED_LITERAL_RE.fullmatch(folded)
    assert labelled is not None
    assert labelled.group("literal") == "F"


def test_renderer_refuses_wrong_same_width_literal_without_output(m130_inspection_snapshot, tmp_path) -> None:
    """A reviewed literal with the right width still cannot override different official bytes."""
    semantic_map = _semantic_map().model_copy(
        update={
            "entries": (
                _semantic_map().entries[0].model_copy(update={"literal": "ZZ"}),
                *_semantic_map().entries[1:],
            ),
        },
    )
    target = tmp_path / "export"

    with pytest.raises(RegistryValidationError, match="byte-for-byte"):
        render_complete_export_tree(
            target,
            revision_id="2025",
            joined=join_record_design_semantics(semantic_map, _intermediate(), m130_inspection_snapshot),
            semantic_map=semantic_map,
            transport_profile=_profile(),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    assert not target.exists()


def test_renderer_partitions_oversized_record_deterministically_and_loader_merges_exactly(
    m130_inspection_snapshot,
    tmp_path,
) -> None:
    """A real-shaped 245-field record stays reviewable and roundtrips exactly once in source order."""
    semantic_map, joined = _oversized_authorities(m130_inspection_snapshot)
    first_revision = _write_modelo_shell(tmp_path / "first" / "modelos" / "130")
    second_revision = _write_modelo_shell(tmp_path / "second" / "modelos" / "130")
    first = render_complete_export_tree(
        first_revision / "export",
        revision_id="2025",
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=_profile(),
        render_profile=_wire_profile(),
        render_profile_source_evidence=_wire_evidence(),
    )
    second = render_complete_export_tree(
        second_revision / "export",
        revision_id="2025",
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=_profile(),
        render_profile=_wire_profile(),
        render_profile_source_evidence=_wire_evidence(),
    )
    compact_map, compact_joined = _oversized_authorities(m130_inspection_snapshot, field_count=20)
    compact_revision = _write_modelo_shell(tmp_path / "compact" / "modelos" / "130")
    compact = render_complete_export_tree(
        compact_revision / "export",
        revision_id="2025",
        joined=compact_joined,
        semantic_map=compact_map,
        transport_profile=_profile(),
        render_profile=_wire_profile(),
        render_profile_source_evidence=_wire_evidence(),
    )

    oversized_parts = tuple(
        path for path in first.output_files if path.endswith("-record-generated-oversized-record.toml")
    )
    compact_parts = tuple(
        path for path in compact.output_files if path.endswith("-record-generated-oversized-record.toml")
    )
    assert len(oversized_parts) > 1
    # Each part takes its own administrative prefix, numbered consecutively from 0001,
    # because the loader admits exactly one fragment per prefix.
    assert oversized_parts == tuple(
        f"{prefix:04d}-record-generated-oversized-record.toml" for prefix in range(1, len(oversized_parts) + 1)
    )
    assert len(oversized_parts) > len(compact_parts)
    assert compact_parts[0] == oversized_parts[0]
    # The trailing record follows the oversized record's last part rather than colliding
    # with it, so its prefix moves as the partition count grows.
    assert first.output_files[-1] == f"{len(oversized_parts) + 1:04d}-record-generated-trailing-record.toml"
    assert compact.output_files[-1] == f"{len(compact_parts) + 1:04d}-record-generated-trailing-record.toml"
    assert first.output_files[-1] != compact.output_files[-1]
    assert first.output_files == second.output_files
    assert len(set(first.output_files)) == len(first.output_files)
    assert [path.split("-", 1)[0] for path in first.output_files] == sorted(
        path.split("-", 1)[0] for path in first.output_files
    )
    assert {path.name: path.read_bytes() for path in scan_directory(first_revision / "export")} == {
        path.name: path.read_bytes() for path in scan_directory(second_revision / "export")
    }
    for relative_path in first.output_files:
        lines = (first_revision / "export" / relative_path).read_text(encoding="utf-8").splitlines()
        assert len(lines) < 1_400
        assert max(map(len, lines), default=0) < 520

    loaded_layout = load_modelo_directory(tmp_path / "first" / "modelos" / "130").revisions["2025"].export_layouts[0]
    assert loaded_layout == first.layout
    emitted_ids = tuple(str(field.id) for field in loaded_layout.records[0].fields)
    assert emitted_ids == tuple(f"generated.oversized.field-{index:03d}" for index in range(1, 246))
    assert len(emitted_ids) == len(set(emitted_ids)) == 245


def test_renderer_refuses_a_fragment_prefix_that_overflows_its_padded_width() -> None:
    """An overflowed prefix is refused at render rather than emitted as an unreadable name.

    Reaching this by rendering would need ten thousand fragments, so the naming
    function is exercised directly. The last in-width prefix must still render, or
    the guard would be refusing legitimate output one short of the boundary.
    """
    width = _export_tree._FRAGMENT_PREFIX_DIGITS
    last_in_width = 10**width - 1

    assert (
        _export_tree._record_relative_path(last_in_width, "generated-record")
        == f"{last_in_width}-record-generated-record.toml"
    )

    with pytest.raises(RegistryValidationError, match="overflows"):
        _export_tree._record_relative_path(last_in_width + 1, "generated-record")


def _code_only_source(module: ModuleType) -> str:
    """Return a module's source with comments and string literals removed.

    Uses the tokeniser rather than a regex so an apostrophe or a `#` inside a
    string cannot desynchronise the scan.
    """
    import io
    import tokenize

    text = inspect.getsource(module)
    kept: list[str] = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type in {tokenize.COMMENT, tokenize.STRING}:
            continue
        kept.append(token.string)
    return " ".join(kept)


def test_renderer_module_has_no_old_tree_or_approximate_admission_surface() -> None:
    """The renderer must fail closed instead of importing an older output as guidance."""
    module = ast.parse(inspect.getsource(_export_tree))
    referenced_names = {node.id for node in ast.walk(module) if isinstance(node, ast.Name)}
    imported_modules = {
        node.module for node in ast.walk(module) if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name for node in ast.walk(module) if isinstance(node, ast.Import) for alias in node.names
    )
    # Scanned with COMMENTS AND DOCSTRINGS STRIPPED. The forbidden tokens name a
    # surface the renderer must not have, not a word it must not say: the module
    # explains in a comment why it refuses "a fuzzy match", and a raw substring
    # scan read that explanation as the defect it warns against. Stripping prose
    # keeps the tokens meaningful -- an actual `shutil` import or `read_text`
    # call is still caught, because those survive tokenisation as code.
    source = _code_only_source(_export_tree).casefold()

    assert "resolve_export_layout" not in referenced_names
    assert "bundled_authority" not in referenced_names
    assert "cadrumo.domain.calculations.registry.export" not in imported_modules
    for forbidden in (
        "fallback",
        "fuzzy",
        "legacy",
        "copytree",
        "shutil",
        "rglob",
        ".extracted",
        "read_text",
    ):
        assert forbidden not in source


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        # The two spellings AEAT actually ships for one closed value set.
        ("1 - Sí  2 - No", ("1", "2")),
        ("1 -Sí, 2 -No", ("1", "2")),
        ("3 -Mensual, 6 -Trimestral, 12 -Anual", ("3", "6", "12")),
        # A RANGE states an interval, not a set. Reading "01-12" as two members
        # would emit an enumeration of {1, 12} and silently refuse every month
        # between them, so the separator refuses a digit on its right.
        ("01-12", ()),
        ("Periodos 01-12 del ejercicio", ()),
        # A single dash-labelled value is not enough to call it an enumeration;
        # the caller requires more than one member before taking this reading.
        ("1 - Sí", ("1",)),
    ],
)
def test_dash_numeric_enumeration_reads_labels_and_refuses_ranges(
    content: str,
    expected: tuple[str, ...],
) -> None:
    """The dash-enumeration reader admits AEAT's label spellings, never a range."""
    values = tuple(match.group("value") for match in _export_tree._DASH_NUMERIC_ENUMERATION_TOKEN_RE.finditer(content))

    assert values == expected


def test_bare_record_tag_is_recognised_without_a_constante_label() -> None:
    """A record's own identifier is readable even when printed unlabelled.

    Modelo 353 prints `</T35301000>` with neither the `Constante` label nor
    quotes its own opening tag carries; Modelo 322 prints BOTH ends bare. The
    pattern keys on the tag's SHAPE, so admitting them cannot turn an arbitrary
    unlabelled cell into a mandated literal.
    """
    matcher = _export_tree._OFFICIAL_BARE_RECORD_TAG_RE

    assert matcher.fullmatch("</T35301000>") is not None
    assert matcher.fullmatch("<T32201000>") is not None
    assert matcher.fullmatch("</T303DID>") is not None
    assert matcher.fullmatch("blanco o 'C' (compl.)") is None
    assert matcher.fullmatch("BLANCOS") is None
    assert matcher.fullmatch("15 enteros + 2 decimales") is None


def test_width_17_sign_policies_cover_every_declared_policy() -> None:
    """The signed/unsigned pair must be the whole policy set the model admits.

    ``_profile_width_17_derivation`` coerces ``sign_policy`` to a boolean, and that
    boolean picks ``data_type`` (money vs decimal), ``signed``, and whether the
    rule's scale is emitted at all. A policy admitted by the model but unknown to
    that coercion therefore renders as an unsigned decimal with a scale -- wrong in
    all three -- and nothing refuses, because the comparison simply evaluates
    false. Adding a policy must break here rather than in a filed amount.
    """
    declared = set(get_args(Width17MembershipRule.model_fields["sign_policy"].annotation))
    handled = {_export_tree._WIDTH_17_SIGNED_POLICY, _export_tree._WIDTH_17_UNSIGNED_POLICY}
    assert handled == declared, (
        f"width-17 sign policies handled by the derivation {sorted(handled)} do not match the "
        f"declared set {sorted(declared)}; an unhandled policy renders as unsigned decimal"
    )


@pytest.mark.parametrize(
    ("aeat_type", "expected_code"),
    [
        ("A", "text-a-v1"),
        ("Alfabético", "text-a-v1"),
        ("Alfabetico", "text-a-v1"),
        ("An", "text-an-v1"),
        ("Alfanumérico", "text-an-v1"),
        ("Alfanumerico", "text-an-v1"),
    ],
)
def test_every_spelling_of_a_text_naturaleza_reaches_its_own_derivation_code(
    m130_inspection_snapshot,
    tmp_path,
    aeat_type: str,
    expected_code: str,
) -> None:
    """A naturaleza must derive from what it names, not from which vocabulary named it.

    AEAT states the same two text naturalezas in two vocabularies: a workbook
    prints the abbreviation, and a PDF design prints the word the shipped parser
    canonicalises to ``Alfabético``/``Alfanumérico``. Both spellings of
    *alfabético* have to reach the alphabetic derivation. Keying the choice on
    the abbreviation alone silently records every PDF-sourced alphabetic field as
    the ALPHANUMERIC derivation, and nothing refuses, because the folded word is
    simply not the abbreviation.
    """
    revision_dir = _write_modelo_shell(tmp_path / "modelos" / "130")
    rendered = render_complete_export_tree(
        revision_dir / "export",
        revision_id="2025",
        joined=_joined(m130_inspection_snapshot, second_field_aeat_type=aeat_type),
        semantic_map=_semantic_map(),
        transport_profile=_profile(),
        render_profile=_wire_profile(),
        render_profile_source_evidence=_wire_evidence(),
    )

    codes = {str(derivation.field.id): derivation.derivation_code for derivation in rendered.field_derivations}
    text_field = next(field_id for field_id in codes if codes[field_id] in {"text-a-v1", "text-an-v1"})
    assert codes[text_field] == expected_code


def test_a_blank_run_naturaleza_the_semantic_map_calls_value_bearing_is_refused(
    m130_inspection_snapshot,
    tmp_path,
) -> None:
    """``Blancos`` states no text representation, so deriving one is a guess.

    A blank run is a fill, and the semantic map already routes a declared filler
    to its own derivation before any naturaleza is read. Reaching this branch
    means the design says "blanks" while the map says the field carries a value:
    the two disagree, and the honest answer is a refusal naming the field, not a
    text derivation invented for it.
    """
    revision_dir = _write_modelo_shell(tmp_path / "modelos" / "130")

    with pytest.raises(RegistryValidationError, match="blank-run naturaleza"):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id="2025",
            joined=_joined(m130_inspection_snapshot, second_field_aeat_type="Blancos"),
            semantic_map=_semantic_map(),
            transport_profile=_profile(),
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )


def _joined_fields_by_aeat_type(modelo: str) -> dict[str, JoinedRecordDesignField]:
    """Return one real joined field per official type token, from the live join.

    Deliberately taken from the real record design rather than assembled here: a
    hand-built stand-in would prove the helper's `if`, not that the official type
    column actually reaches it.
    """
    from .test_generated_export_trees import _GENERATED_TREES, _authorities

    tree = next(item for item in _GENERATED_TREES if item.modelo == modelo)
    _map, _profile, joined, _evidence, _transport = _authorities(tree)
    found: dict[str, JoinedRecordDesignField] = {}
    for field in joined.fields:
        found.setdefault(field.parser_field.aeat_type, field)
    return found


@pytest.mark.unit
def test_an_unsigned_official_type_derives_an_unsigned_slot() -> None:
    """`Num` is numerico SIN signo, and it must still render without refusal."""
    from ._export_tree import _derive_sign_from_official_type

    unsigned = _joined_fields_by_aeat_type("390")["Num"]

    assert _derive_sign_from_official_type(unsigned) is False


@pytest.mark.unit
def test_a_signed_official_type_derives_a_signed_slot() -> None:
    """`N` is numerico CON signo, and its representation is now grounded.

    AEAT's "Disenos de registro" manual states the convention for every design:
    numeric fields are right-aligned and zero-filled SIN SIGNOS, and only
    NEGATIVE amounts are preceded by the character ``N``. So a signed slot
    reserves no byte -- the marker displaces the leading digit when the value is
    negative -- and the derivation reads that grounding rather than refusing, as
    it once did before the representation was grounded.
    """
    from ._export_tree import _derive_sign_from_official_type

    signed = _joined_fields_by_aeat_type("390")["N"]

    assert _derive_sign_from_official_type(signed) is True


def test_requirement_reading_sets_aside_sentence_punctuation_but_not_a_qualifier() -> None:
    """Prove the punctuation repair lands and each wording is read as what it states.

    The defect was an exact-match comparison: ``OBLIGATORIO.`` fell through to
    ``False``, so twelve stated requirements in modelo 390 shipped as no
    requirement, defeated by a full stop. Sentence punctuation is now set
    aside.

    ``Obligatorio PI`` is unconditional: PI names the value list in modelo
    303's Nota 1, not a condition. ``OBLIGATORIO (persona fisica)`` is not
    unconditional; it is read as a requirement for natural persons only. A
    wording nobody has adjudicated is neither, and stays unclaimed.
    """
    from ._export_tree import _is_required, _qualified_requirement

    assert _is_required(None) is False
    assert _is_required("Obligatorio") is True
    assert _is_required("OBLIGATORIO") is True
    assert _is_required("  obligatorio  ") is True
    assert _is_required("OBLIGATORIO.") is True
    assert _is_required("Obligatorio PI") is True

    for qualified in ("OBLIGATORIO (persona fisica)", "Obligatorio si procede"):
        assert _is_required(qualified) is False

    assert _qualified_requirement("OBLIGATORIO (persona fisica)") == "natural_person"
    assert _qualified_requirement("Obligatorio (persona física).") == "natural_person"
    assert _qualified_requirement("Obligatorio si procede") is None
    assert _qualified_requirement("OBLIGATORIO") is None
