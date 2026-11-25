"""Shared builders for the export tree tests."""

from __future__ import annotations

from pathlib import Path

from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.schema_base import CorpusTier, RegistrySourceKind
from cadrumo.domain.calculations.registry.static_inspection import (
    RegistryRevisionInspection,
    StaticGeneratedArtifactInspection,
    StaticGeneratedArtifactSource,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope, open_ended_revision

from ..export_tree_models import ExportTreeTransportProfile
from ..joined_record_design import JoinedRecordDesign, join_record_design_semantics
from ..record_design_intermediate import (
    RecordDesignIntermediate,
    RecordDesignWorkbookFormat,
)
from ..render_profile_evidence import RenderProfileSourceEvidence, ReviewedPolicyDecision
from ..render_profile_model import RenderProfile
from ..render_profile_model_base import RenderProfileAnchor, RenderProfileDesignIdentity
from ..render_profile_rules import SingletonNumericRule
from ..semantic_map import SemanticMap
from .generated_tree_test_support import bundled_revision_inspection

_M130_OPEN_ENDED = open_ended_revision("130")
#: The record-design epoch the synthetic modelo 130 design stands in for: the one the real modelo 130 authors.
DESIGN_EPOCH = str(_M130_OPEN_ENDED.valid_from.year)
#: The single synthetic revision a staged shell modelo carries, named for the exercise it covers.
SHELL_EXERCISE = filing_year_envelope().horizon
SHELL_REVISION = str(SHELL_EXERCISE)


def export_tree_intermediate(
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
                "design_epoch": DESIGN_EPOCH,
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


def export_tree_semantic_map() -> SemanticMap:
    return SemanticMap.model_validate(
        {
            "modelo": "130",
            "design_epoch": DESIGN_EPOCH,
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


def export_tree_profile() -> ExportTreeTransportProfile:
    return ExportTreeTransportProfile(
        modelo="130",
        design_epoch=DESIGN_EPOCH,
        source_ref="aeat-dr-130-2019-v12",
        source_sha256="58f731b0c72eff7fd23484000c74e73e0ac803a5167065176d78cac8712f5fe7",
        layout_id="generated-modelo-130-fichero",
        format="fixed_width",
        encoding=ExportEncoding.ISO_8859_1,
        line_ending="crlf",
        serializer_convention="rtoml-pretty-v1",
    )


def wire_profile() -> RenderProfile:
    identity = RenderProfileDesignIdentity(
        modelo="130",
        design_epoch=DESIGN_EPOCH,
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


def wire_evidence() -> RenderProfileSourceEvidence:
    return RenderProfileSourceEvidence(
        design_identity=wire_profile().design_identity,
        entries=(),
    )


def blank_integer_profile() -> RenderProfile:
    anchor = RenderProfileAnchor(
        sheet="Registro tipo 2",
        source_row=21,
        source_cell="A21",
        ordinal="2",
        record_identity="registro-tipo-2",
    )
    return wire_profile().model_copy(
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


def m130_inspection() -> RegistryRevisionInspection:
    """The real modelo 130 revision authority the synthetic 130 design joins against.

    It declares no projection endpoint, so a synthetic semantic map joins against
    it without a projection bijection to satisfy.
    """
    return bundled_revision_inspection("130", str(_M130_OPEN_ENDED.id))


def export_tree_joined(
    snapshot,
    *,
    numeric_content: str | None = "2 enteros y 2 decimales",
    second_field_aeat_type: str = "A",
) -> JoinedRecordDesign:
    return join_record_design_semantics(
        export_tree_semantic_map(),
        export_tree_intermediate(numeric_content=numeric_content, second_field_aeat_type=second_field_aeat_type),
        snapshot,
    )


def synthetic_static_inspection() -> StaticGeneratedArtifactInspection:
    """Return the narrow, non-filing source authority for parser-derivation bites."""
    source_ref = "aeat-dr-130-2019-v12"
    return StaticGeneratedArtifactInspection(
        modelo_id="130",
        revision_id=DESIGN_EPOCH,
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
                record_design_epoch=DESIGN_EPOCH,
                corpus_tier=CorpusTier.FULL_CONSOLIDATED,
            ),
        },
        legal_ref_ids=frozenset(("rd-439-2007:art-110",)),
        casilla_ids=frozenset(),
        binding_ids=frozenset(),
        projection_endpoints=(),
    )


def oversized_authorities(snapshot, *, field_count: int = 245) -> tuple[SemanticMap, JoinedRecordDesign]:
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
                "design_epoch": DESIGN_EPOCH,
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
            "design_epoch": DESIGN_EPOCH,
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


def write_modelo_shell(modelo_dir: Path) -> Path:
    revision_dir = modelo_dir / "revisions" / SHELL_REVISION
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
        f"""
[revisions."{SHELL_REVISION}"]
authority_grade = "applicability"
valid_from = {SHELL_EXERCISE}-01-01
period_selector = {{ years = [{SHELL_EXERCISE}], periods = ["0A"] }}
legal_refs = ["rd-439-2007:art-110"]
source_refs = ["aeat-dr-130-2019-v12"]
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    return revision_dir
