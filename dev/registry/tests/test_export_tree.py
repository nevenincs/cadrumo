"""Real filesystem and loader proofs for generated export-tree rendering."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry import RegistryValidationError, bundled_authority
from cadrumo.domain.calculations.registry._loader import load_modelo_directory

from .. import _export_tree
from .._export_tree import ExportRenderProfile, render_complete_export_tree
from .._provenance_manifest import (
    EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    ExportFragmentTarget,
    emit_export_fragment_provenance_manifest,
    export_fragment_provenance_manifest_json_bytes,
    load_export_fragment_provenance_manifest,
    verify_export_fragment_provenance_manifest,
)
from .._record_design_ir import RecordDesignIntermediate, RecordDesignWorkbookFormat
from .._semantic_map import SemanticMap
from .._semantic_map_join import join_record_design_semantics

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture
def _m200_snapshot():
    return bundled_authority().snapshot("200", filing_year=2025, period="0A")


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
                "source_ref": "aeat-dr-200-2025",
                "source_sha256": "a4506d24b7973a745d1225d59147078e03f14a30791a229d852b37f757442505",
                "workbook_format": RecordDesignWorkbookFormat.XLSX,
                "design_epoch": "2025",
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
                            "ordinal": 1,
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
                            "ordinal": 2,
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
                            "ordinal": 1,
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
                            "ordinal": 2,
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
            "modelo": "200",
            "design_epoch": "2025",
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
                    header_key="period_code",
                ),
                _entry("Registro tipo 2", "registro-tipo-2", 20, 1, "generated.type", "literal", literal="2"),
                _entry(
                    "Registro tipo 2",
                    "registro-tipo-2",
                    21,
                    2,
                    "generated.amount",
                    "header",
                    header_key="amount",
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
            "ordinal": ordinal,
            "record_identity": record_identity,
        },
        "export_field_id": field_id,
        "kind": kind,
        "legal_refs": ("ley-27-2014:art-40",),
        "source_refs": ("aeat-dr-200-2025",),
        **semantic_value,
    }


def _profile() -> ExportRenderProfile:
    return ExportRenderProfile(
        modelo="200",
        design_epoch="2025",
        source_ref="aeat-dr-200-2025",
        source_sha256="a4506d24b7973a745d1225d59147078e03f14a30791a229d852b37f757442505",
        layout_id="generated-modelo-200-fichero",
        format="fixed_width",
        encoding="latin-1",
        line_ending="crlf",
        serializer_convention="rtoml-pretty-v1",
    )


def _joined(snapshot, *, numeric_content: str | None = "2 enteros y 2 decimales"):
    return join_record_design_semantics(_semantic_map(), _intermediate(numeric_content=numeric_content), snapshot)


def _write_modelo_shell(modelo_dir: Path) -> Path:
    revision_dir = modelo_dir / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    (modelo_dir / "manifest.toml").write_text(
        """
[modelo]
id = "200"
tax_domain = "is"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-27-2014:art-40"]
source_refs = ["aeat-dr-200-2025"]
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "revision.toml").write_text(
        """
[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-27-2014:art-40"]
source_refs = ["aeat-dr-200-2025"]
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    return revision_dir


def test_renderer_writes_stable_complete_tree_that_real_directory_loader_merges(_m200_snapshot, tmp_path) -> None:
    """The output is fresh canonical TOML that the real loader compiles by its fragment rules."""
    revision_dir = _write_modelo_shell(tmp_path / "modelos" / "200")
    first = render_complete_export_tree(
        revision_dir / "export",
        revision_id="2025",
        joined=_joined(_m200_snapshot),
        semantic_map=_semantic_map(),
        profile=_profile(),
    )
    duplicate_revision_dir = _write_modelo_shell(tmp_path / "comparison" / "modelos" / "200")
    second = render_complete_export_tree(
        duplicate_revision_dir / "export",
        revision_id="2025",
        joined=_joined(_m200_snapshot),
        semantic_map=_semantic_map(),
        profile=_profile(),
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
        for path in sorted((revision_dir / "export").iterdir())
    } == {
        path.relative_to(duplicate_revision_dir / "export").as_posix(): path.read_bytes()
        for path in sorted((duplicate_revision_dir / "export").iterdir())
    }

    loaded = load_modelo_directory(tmp_path / "modelos" / "200")
    layout = loaded.revisions["2025"].export_layouts[0]
    manifest_path = revision_dir / EXPORT_FRAGMENT_PROVENANCE_FILENAME
    assert manifest_path.is_file()
    assert manifest_path.name not in first.output_files
    assert load_export_fragment_provenance_manifest(manifest_path.read_bytes()) == first.provenance_manifest
    assert verify_export_fragment_provenance_manifest(
        export_root=revision_dir / "export",
        joined=_joined(_m200_snapshot),
        semantic_map=_semantic_map(),
        target=ExportFragmentTarget(modelo="200", revision_id="2025", design_epoch="2025"),
        loaded_layout=layout,
        field_derivations=first.field_derivations,
    ) == first.provenance_manifest
    assert tuple(record.id for record in layout.records) == (
        "generated-registro-tipo-1",
        "generated-registro-tipo-2",
    )
    assert tuple(
        (field.offset, field.length, field.data_type, field.decimals) for field in layout.records[1].fields
    ) == (
        (1, 1, "text", None),
        (2, 4, "decimal", 2),
    )


def test_renderer_manifest_refuses_file_tampering_derivation_drift_and_partial_field_evidence(
    _m200_snapshot,
    tmp_path,
) -> None:
    """Only the fresh full renderer result can attest its real generated tree."""
    revision_dir = _write_modelo_shell(tmp_path / "modelos" / "200")
    rendered = render_complete_export_tree(
        revision_dir / "export",
        revision_id="2025",
        joined=_joined(_m200_snapshot),
        semantic_map=_semantic_map(),
        profile=_profile(),
    )
    layout = load_modelo_directory(tmp_path / "modelos" / "200").revisions["2025"].export_layouts[0]
    export_root = revision_dir / "export"
    manifest_path = revision_dir / EXPORT_FRAGMENT_PROVENANCE_FILENAME
    original_fragment = export_root / "0001-record-generated-registro-tipo-1.toml"
    original_bytes = original_fragment.read_bytes()

    original_fragment.write_bytes(original_bytes + b"# tampered\n")
    with pytest.raises(RegistryValidationError, match="output-file digests"):
        verify_export_fragment_provenance_manifest(
            export_root=export_root,
            joined=_joined(_m200_snapshot),
            semantic_map=_semantic_map(),
            target=ExportFragmentTarget(modelo="200", revision_id="2025", design_epoch="2025"),
            loaded_layout=layout,
            field_derivations=rendered.field_derivations,
        )
    original_fragment.write_bytes(original_bytes)

    manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
    authority_tampered_manifest = manifest.model_copy(update={"source_sha256": "b" * 64})
    manifest_path.write_bytes(export_fragment_provenance_manifest_json_bytes(authority_tampered_manifest))
    with pytest.raises(RegistryValidationError, match="current generation authorities"):
        verify_export_fragment_provenance_manifest(
            export_root=export_root,
            joined=_joined(_m200_snapshot),
            semantic_map=_semantic_map(),
            target=ExportFragmentTarget(modelo="200", revision_id="2025", design_epoch="2025"),
            loaded_layout=layout,
            field_derivations=rendered.field_derivations,
        )

    drifted_derivation = manifest.field_derivations[0].model_copy(update={"derivation_code": "filler-v1"})
    drifted_manifest = manifest.model_copy(
        update={"field_derivations": (drifted_derivation, *manifest.field_derivations[1:])},
    )
    manifest_path.write_bytes(export_fragment_provenance_manifest_json_bytes(drifted_manifest))
    with pytest.raises(RegistryValidationError, match="field derivations do not match"):
        verify_export_fragment_provenance_manifest(
            export_root=export_root,
            joined=_joined(_m200_snapshot),
            semantic_map=_semantic_map(),
            target=ExportFragmentTarget(modelo="200", revision_id="2025", design_epoch="2025"),
            loaded_layout=layout,
            field_derivations=rendered.field_derivations,
        )

    partial_manifest = manifest.model_copy(update={"field_derivations": manifest.field_derivations[:-1]})
    manifest_path.write_bytes(export_fragment_provenance_manifest_json_bytes(partial_manifest))
    with pytest.raises(RegistryValidationError, match="do not cover exactly"):
        verify_export_fragment_provenance_manifest(
            export_root=export_root,
            joined=_joined(_m200_snapshot),
            semantic_map=_semantic_map(),
            target=ExportFragmentTarget(modelo="200", revision_id="2025", design_epoch="2025"),
            loaded_layout=layout,
            field_derivations=rendered.field_derivations,
        )


def test_direct_manifest_emission_and_real_loader_verification(_m200_snapshot, tmp_path) -> None:
    """The public S09 emitter and verifier operate on a real fresh tree only."""
    revision_dir = _write_modelo_shell(tmp_path / "modelos" / "200")
    semantic_map = _semantic_map()
    joined = _joined(_m200_snapshot)
    rendered = render_complete_export_tree(
        revision_dir / "export",
        revision_id="2025",
        joined=joined,
        semantic_map=semantic_map,
        profile=_profile(),
    )
    layout = load_modelo_directory(tmp_path / "modelos" / "200").revisions["2025"].export_layouts[0]
    manifest_path = revision_dir / EXPORT_FRAGMENT_PROVENANCE_FILENAME
    manifest_path.unlink()

    emitted = emit_export_fragment_provenance_manifest(
        joined=joined,
        semantic_map=semantic_map,
        target=ExportFragmentTarget(modelo="200", revision_id="2025", design_epoch="2025"),
        loaded_layout=layout,
        export_root=revision_dir / "export",
        field_derivations=rendered.field_derivations,
    )

    assert load_export_fragment_provenance_manifest(manifest_path.read_bytes()) == emitted
    assert verify_export_fragment_provenance_manifest(
        export_root=revision_dir / "export",
        joined=joined,
        semantic_map=semantic_map,
        target=ExportFragmentTarget(modelo="200", revision_id="2025", design_epoch="2025"),
        loaded_layout=layout,
        field_derivations=rendered.field_derivations,
    ) == emitted


def test_renderer_refuses_mismatched_map_without_emitting_a_manifest(_m200_snapshot, tmp_path) -> None:
    """S09 never leaves a partial sibling attestation when map authority drifts."""
    revision_dir = _write_modelo_shell(tmp_path / "modelos" / "200")
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
            joined=_joined(_m200_snapshot),
            semantic_map=mismatched_map,
            profile=_profile(),
        )

    assert not (revision_dir / EXPORT_FRAGMENT_PROVENANCE_FILENAME).exists()


def test_renderer_refuses_unmeasured_numeric_form_without_emitting_a_partial_fragment(_m200_snapshot, tmp_path) -> None:
    """A numeric type without its official form is insufficient to select wire semantics."""
    target = tmp_path / "export"

    with pytest.raises(RegistryValidationError, match="no unambiguous content form"):
        render_complete_export_tree(
            target,
            revision_id="2025",
            joined=_joined(_m200_snapshot, numeric_content=None),
            semantic_map=_semantic_map(),
            profile=_profile(),
        )

    assert target.is_dir()
    assert not tuple(target.iterdir())


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
    _m200_snapshot,
    tmp_path,
    intermediate_kwargs: dict[str, int | None],
    error: str,
) -> None:
    """No inferred total, first position, gap, overlap, or terminal extent may be emitted."""
    target = tmp_path / "export"
    joined = join_record_design_semantics(
        _semantic_map(),
        _intermediate(**intermediate_kwargs),
        _m200_snapshot,
    )

    with pytest.raises(RegistryValidationError, match=error):
        render_complete_export_tree(
            target,
            revision_id="2025",
            joined=joined,
            semantic_map=_semantic_map(),
            profile=_profile(),
        )

    assert target.is_dir()
    assert not tuple(target.iterdir())


def test_renderer_refuses_profile_hash_drift_literal_extent_and_nonempty_target(_m200_snapshot, tmp_path) -> None:
    """The renderer rejects unsafe authority mismatches and never overwrites a prior output."""
    joined = _joined(_m200_snapshot)
    with pytest.raises(RegistryValidationError, match="SHA-256"):
        render_complete_export_tree(
            tmp_path / "export",
            revision_id="2025",
            joined=joined,
            semantic_map=_semantic_map(),
            profile=_profile().model_copy(update={"source_sha256": "b" * 64}),
        )

    literal_map = _semantic_map().model_copy(
        update={
            "entries": (
                _semantic_map().entries[0].model_copy(update={"literal": "TOO LONG"}),
                *_semantic_map().entries[1:],
            ),
        },
    )
    with pytest.raises(RegistryValidationError, match="encoded bytes"):
        render_complete_export_tree(
            tmp_path / "second" / "export",
            revision_id="2025",
            joined=join_record_design_semantics(literal_map, _intermediate(), _m200_snapshot),
            semantic_map=literal_map,
            profile=_profile(),
        )

    occupied = tmp_path / "occupied" / "export"
    occupied.mkdir(parents=True)
    (occupied / "foreign.toml").write_text("value = 1\n", encoding="utf-8")
    with pytest.raises(RegistryValidationError, match="not empty"):
        render_complete_export_tree(
            occupied,
            revision_id="2025",
            joined=joined,
            semantic_map=_semantic_map(),
            profile=_profile(),
        )


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
    source = inspect.getsource(_export_tree).casefold()

    assert "resolve_export_layout" not in referenced_names
    assert "bundled_authority" not in referenced_names
    assert "cadrumo.domain.calculations.registry._export" not in imported_modules
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
