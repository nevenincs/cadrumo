"""Real filesystem and loader proofs for generated export-tree rendering."""

from __future__ import annotations

import ast
import inspect
from dataclasses import replace
from pathlib import Path
from typing import Final, TypedDict

import pytest

from cadrumo.core import (
    FilingProducerKey,
    M303ProrrataActivityProjectionField,
    M303ProrrataActivityProjectionRef,
)
from cadrumo.core.directory_scan import (
    scan_directory,
)
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import (
    RegistryError,
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.loader import load_modelo_directory
from cadrumo.domain.calculations.registry.schema_exports import ProjectionEndpointDeclaration

from ..pipeline import _export_tree
from ..pipeline._export_tree import ExportTreeTransportProfile, RenderedExportTree, render_complete_export_tree
from ..pipeline._provenance_manifest import (
    EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    ExportFragmentTarget,
    _write_canonical_manifest_atomically,
    emit_export_fragment_provenance_manifest,
    export_fragment_provenance_manifest_json_bytes,
    load_export_fragment_provenance_manifest,
    verify_export_fragment_provenance_manifest,
)
from ..pipeline._record_design_ir import RecordDesignIntermediate, RecordDesignWorkbookFormat
from ..pipeline._render_profile import (
    RenderProfile,
    RenderProfileAnchor,
    RenderProfileDesignIdentity,
    RenderProfileSourceEvidence,
    ReviewedPolicyDecision,
    SingletonNumericRule,
)
from ..pipeline._semantic_map import SemanticMap
from ..pipeline._semantic_map_join import JoinedRecordDesign, join_record_design_semantics
from ..pipeline._tree_validation import (
    GeneratedExportTreeValidationContext,
    validate_generated_export_tree,
)
from .test_generated_export_trees import (
    _authorities as _enrolled_authorities,
)
from .test_generated_export_trees import (
    _GeneratedTree,
    _isolated_authority,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _intermediate(
    *,
    first_record_declared_total: int | None = 4,
    first_field_offset: int = 1,
    second_field_offset: int = 3,
    numeric_content: str | None = "2 enteros y 2 decimales",
) -> RecordDesignIntermediate:
    return RecordDesignIntermediate.model_validate(
        {
            "source": {
                "source_ref": "aeat-dr-130-2019-v12",
                "source_sha256": "5d370a9dd13124dbfa596ee903d7a4f3e8801c4d153aa922e1f445790e181e4f",
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
                            "aeat_type": "A",
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
            "source_sha256": "5d370a9dd13124dbfa596ee903d7a4f3e8801c4d153aa922e1f445790e181e4f",
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
        source_sha256="5d370a9dd13124dbfa596ee903d7a4f3e8801c4d153aa922e1f445790e181e4f",
        layout_id="generated-modelo-130-fichero",
        format="fixed_width",
        encoding=ExportEncoding.LATIN_1,
        line_ending="crlf",
        serializer_convention="rtoml-pretty-v1",
    )


def _wire_profile() -> RenderProfile:
    identity = RenderProfileDesignIdentity(
        modelo="130",
        design_epoch="2019",
        source_ref="aeat-dr-130-2019-v12",
        source_sha256="5d370a9dd13124dbfa596ee903d7a4f3e8801c4d153aa922e1f445790e181e4f",
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


def _joined(snapshot, *, numeric_content: str | None = "2 enteros y 2 decimales"):
    return join_record_design_semantics(_semantic_map(), _intermediate(numeric_content=numeric_content), snapshot)


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
                "source_sha256": "5d370a9dd13124dbfa596ee903d7a4f3e8801c4d153aa922e1f445790e181e4f",
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
            "source_sha256": "5d370a9dd13124dbfa596ee903d7a4f3e8801c4d153aa922e1f445790e181e4f",
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


def _real_authorities(tree: _GeneratedTree):
    """Return the real (joined, semantic map, transport, render profile, evidence).

    A thin adapter over the enrolled drift gate's own `_authorities`, so this
    fixture and that gate cannot disagree about how a generated tree is built.
    """
    semantic_map, render_profile, joined, evidence, transport = _enrolled_authorities(tree)
    return joined, semantic_map, transport, render_profile, evidence


#: The enrolled generated tree this fixture materialises in isolation.
#:
#: It used to hand-assemble a synthetic modelo/revision and render a two-sheet
#: toy layout into it. The export-completeness gate reads the REAL design named
#: by the revision's `source_refs`, so that layout covered 3 of the 41 positions
#: modelo 130's diseño requires and validation refused -- correctly. No synthetic
#: layout can satisfy that gate against a real design, and no bundled design is
#: small enough to be covered by a toy.
#:
#: Modelo 184 is used instead because it is ENROLLED in the generated-tree drift
#: gate, so its real diseño and real semantic map are already proven to render a
#: complete, valid tree. It also carries NO supporting modelo and exactly ONE
#: revision, so the isolated candidate needs no staged neighbour -- modelo 202,
#: the first choice, folds in modelo 200 and the candidate root must contain
#: exactly the target modelo.
#:
#: It no longer carries exactly one revision: the split at Orden HAC/1430/2025's
#: boundary gave it `2015-2024` and `2025-y-siguientes`, so the isolation does
#: prune a sibling now. The tree named here is the later half, which is the one
#: the 2025 design and its `2025` epoch belong to.
_ISOLATED_TREE: Final[_GeneratedTree] = _GeneratedTree(
    "184", "2025-y-siguientes", "aeat-dr-184-2025", "2025", 2025, "0A"
)


def _isolated_render_profile():
    """The REAL render profile for the isolated tree, and its source evidence.

    Validation checks the profile's design identity against the tree's, so the
    synthetic wire profile cannot be passed alongside a real generated tree.
    """
    _joined, _map, _transport, render_profile, evidence = _real_authorities(_ISOLATED_TREE)
    return render_profile, evidence


def _write_isolated_generated_authority_tree(
    tmp_path: Path,
    snapshot=None,
) -> tuple[GeneratedExportTreeValidationContext, JoinedRecordDesign, SemanticMap, RenderedExportTree, Path]:
    """Materialise the target's real NON-export authority plus a freshly rendered export.

    The export directory is never copied: it is written solely through the
    export-tree renderer, so generated-tree validation cannot pass by loading an
    older fragment tree. Everything else comes from the shipped registry through
    the same two helpers the enrolled drift gate uses, so this fixture cannot
    drift from what a real generated tree looks like.

    ``snapshot`` is accepted and ignored: callers pass a revision inspection that
    the real authorities now supersede.
    """
    registry_root = _isolated_authority(_ISOLATED_TREE, tmp_path / "candidate")
    joined, semantic_map, transport, render_profile, render_evidence = _real_authorities(_ISOLATED_TREE)

    export_root = registry_root / "modelos" / _ISOLATED_TREE.modelo / "revisions" / _ISOLATED_TREE.revision / "export"
    assert not export_root.exists(), "the authority fixture must not copy legacy export fragments"
    rendered = render_complete_export_tree(
        export_root,
        revision_id=_ISOLATED_TREE.revision,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=transport,
        render_profile=render_profile,
        render_profile_source_evidence=render_evidence,
    )
    context = GeneratedExportTreeValidationContext(
        registry_root=registry_root,
        source_root=bundled_path(),
        target=ExportFragmentTarget(
            modelo=_ISOLATED_TREE.modelo,
            revision_id=_ISOLATED_TREE.revision,
            design_epoch=_ISOLATED_TREE.epoch,
        ),
        filing_year=_ISOLATED_TREE.filing_year,
        period=_ISOLATED_TREE.period,
    )
    return context, joined, semantic_map, rendered, export_root


def test_generated_tree_validation_requires_real_loader_and_authority_selection(
    m130_inspection_snapshot, tmp_path
) -> None:
    """A fresh target must compile, attest, and select through the production authority."""
    context, joined, semantic_map, rendered, _export_root = _write_isolated_generated_authority_tree(
        tmp_path,
        m130_inspection_snapshot,
    )

    validated = validate_generated_export_tree(
        context=context,
        joined=joined,
        semantic_map=semantic_map,
        rendered=rendered,
        render_profile=_isolated_render_profile()[0],
        render_profile_source_evidence=_isolated_render_profile()[1],
    )

    assert validated.target == context.target
    assert validated.layout == rendered.layout
    assert validated.provenance_manifest == rendered.provenance_manifest
    assert validated.snapshot.modelo.id == _ISOLATED_TREE.modelo
    assert validated.snapshot.revision.id == _ISOLATED_TREE.revision
    assert validated.snapshot.revision.export_layouts == (rendered.layout,)


def test_generated_tree_validation_refuses_partial_or_non_generated_export_siblings(
    m130_inspection_snapshot, tmp_path
) -> None:
    """Missing output and a legacy-style sibling both refuse before any publication path exists."""
    context, joined, semantic_map, rendered, export_root = _write_isolated_generated_authority_tree(
        tmp_path,
        m130_inspection_snapshot,
    )
    (export_root / rendered.output_files[-1]).unlink()

    with pytest.raises(RegistryValidationError, match="exactly the current rendered outputs"):
        validate_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_isolated_render_profile()[0],
            render_profile_source_evidence=_isolated_render_profile()[1],
        )

    context, joined, semantic_map, rendered, export_root = _write_isolated_generated_authority_tree(
        tmp_path / "sibling",
        m130_inspection_snapshot,
    )
    (export_root / "0003-unreviewed-layout.toml").write_text(
        """
[revisions."2025"]
[[revisions."2025".export_layouts]]
id = "unreviewed-layout"
format = "fixed_width"
source_refs = ["aeat-dr-130-2019-v12"]
legal_refs = ["rd-439-2007:art-110"]
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(RegistryValidationError, match="exactly the current rendered outputs"):
        validate_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_isolated_render_profile()[0],
            render_profile_source_evidence=_isolated_render_profile()[1],
        )


def test_generated_tree_validation_refuses_direct_revision_legacy_and_loader_breakage(
    m130_inspection_snapshot, tmp_path
) -> None:
    """No single-file modelo, direct revision fallback, or malformed output reaches authority selection."""
    context, joined, semantic_map, rendered, _export_root = _write_isolated_generated_authority_tree(
        tmp_path,
        m130_inspection_snapshot,
    )
    (context.registry_root / "modelos" / "200.toml").write_text("[modelo]\nid = '200'\n", encoding="utf-8")

    with pytest.raises(RegistryValidationError, match="generated registry modelos root must contain exactly"):
        validate_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    context, joined, semantic_map, rendered, export_root = _write_isolated_generated_authority_tree(
        tmp_path / "malformed",
        m130_inspection_snapshot,
    )
    (export_root / rendered.output_files[0]).write_text("[revisions\n", encoding="utf-8")

    with pytest.raises(RegistryError):
        validate_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )


def test_generated_tree_validation_refuses_stale_sibling_provenance(m130_inspection_snapshot, tmp_path) -> None:
    """The former outside-export attestation path cannot survive the hard cutover."""
    context, joined, semantic_map, rendered, export_root = _write_isolated_generated_authority_tree(
        tmp_path,
        m130_inspection_snapshot,
    )
    (export_root.parent / "export.provenance.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(RegistryValidationError, match="stale sibling export provenance"):
        validate_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_isolated_render_profile()[0],
            render_profile_source_evidence=_isolated_render_profile()[1],
        )


def test_generated_tree_validation_refuses_wrong_period_and_provenance_drift(
    m130_inspection_snapshot, tmp_path
) -> None:
    """The exact target must apply to its filing context and retain current authority evidence."""
    context, joined, semantic_map, rendered, _export_root = _write_isolated_generated_authority_tree(
        tmp_path,
        m130_inspection_snapshot,
    )

    with pytest.raises(RegistryError, match="no revision for year"):
        validate_generated_export_tree(
            context=replace(context, period="1T"),
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_isolated_render_profile()[0],
            render_profile_source_evidence=_isolated_render_profile()[1],
        )

    with pytest.raises(RegistryValidationError, match="'303'"):
        validate_generated_export_tree(
            context=replace(
                context,
                target=context.target.model_copy(update={"modelo": "303"}),
            ),
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_isolated_render_profile()[0],
            render_profile_source_evidence=_isolated_render_profile()[1],
        )

    with pytest.raises(RegistryValidationError, match="'2026'"):
        validate_generated_export_tree(
            context=replace(
                context,
                target=context.target.model_copy(update={"revision_id": "2026"}),
            ),
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_isolated_render_profile()[0],
            render_profile_source_evidence=_isolated_render_profile()[1],
        )

    manifest_path = (
        context.registry_root
        / "modelos"
        / _ISOLATED_TREE.modelo
        / "revisions"
        / _ISOLATED_TREE.revision
        / "export"
        / EXPORT_FRAGMENT_PROVENANCE_FILENAME
    )
    manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
    manifest_path.write_bytes(
        export_fragment_provenance_manifest_json_bytes(manifest.model_copy(update={"source_sha256": "b" * 64})),
    )
    with pytest.raises(RegistryValidationError, match="current generation authorities"):
        validate_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_isolated_render_profile()[0],
            render_profile_source_evidence=_isolated_render_profile()[1],
        )


def test_generated_tree_validation_module_has_no_legacy_loader_surface() -> None:
    """The generated-tree validation boundary must not reintroduce legacy reader or fallback APIs."""
    # The module was renamed and rehomed in the authoring-tree deconflation:
    # `dev/registry/_generated_tree_validation.py` is now
    # `dev/registry/pipeline/_tree_validation.py`. The import was left behind, so
    # this case died on ImportError rather than proving anything about the
    # boundary it guards.
    from ..pipeline import _tree_validation

    module = ast.parse(inspect.getsource(_tree_validation))
    referenced_names = {node.id for node in ast.walk(module) if isinstance(node, ast.Name)}
    attribute_names = {node.attr for node in ast.walk(module) if isinstance(node, ast.Attribute)}
    forbidden = {
        "bundled_authority",
        "load_modelo_file",
        "load_modelo_path",
        "resolve_export_layout",
        "copytree",
    }

    assert not forbidden.intersection(referenced_names)
    assert not forbidden.intersection(attribute_names)


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
    """Pin the refusal this writer delegates to the core publish-once tier.

    ``atomic_write_publish_once_bytes`` publishes with :func:`os.link`, which
    fails with :exc:`FileExistsError` in one uninterruptible step rather than
    overwriting. This test pins the refusal at THIS boundary anyway, because the
    writer translates that failure into a registry error and a delegation that
    dropped the translation would still be a defect here. Nothing else asserted
    it: the emit-level test must ``unlink()`` the manifest before it can call
    emit at all, so the behaviour was exercised by necessity and would have
    survived its own deletion in green.

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


@pytest.mark.parametrize("official_content", (None, 'Constante "<T" o "ZZ"'))
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


def _code_only_source(module: object) -> str:
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

    assert "cadrumo.domain.calculations.registry.record_spec" not in imported_modules
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
