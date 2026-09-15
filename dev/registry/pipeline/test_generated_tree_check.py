"""Real-filesystem regression proof for generated export check mode."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, TypedDict

import pytest

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.hashing import hash_file
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding, ExportJustification, ExportPadding
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDataType,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)

from . import _tree_check
from ._export_tree import ExportTreeTransportProfile
from ._generated_tree_test_support import (
    ISOLATED_TREE,
    isolated_authorities,
    isolated_authority,
    isolated_export_root,
    isolated_render_profile,
    render_isolated_export,
    stage_isolated_validation_context,
)
from ._tree_check import (
    GeneratedExportTreeCheckContext,
    check_generated_export_tree,
)
from .export_fragment_provenance import (
    EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    export_fragment_provenance_manifest_json_bytes,
    load_export_fragment_provenance_manifest,
    normalised_loader_semantics,
)
from .joined_record_design import JoinedRecordDesign
from .semantic_map import SemanticMap

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _tree_hashes(root: Path) -> dict[str, str]:
    """Observe existing target bytes using the production hashing utility."""
    return {
        path.relative_to(root).as_posix(): hash_file(path)[0]
        for path in scan_directory(root, recursive=True, select=DirectoryEntryKind.FILES)
    }


def _check_inputs(tmp_path: Path) -> tuple[GeneratedExportTreeCheckContext, JoinedRecordDesign, SemanticMap, Path]:
    """Build a rendered published target and a separate export-free candidate authority on disk.

    The continuity witness is an input to candidate validation only, so the
    published side stages just its registry and renders its export.
    """
    target_registry_root = isolated_authority(ISOLATED_TREE, tmp_path / "published")
    joined, semantic_map, _rendered, target_export_root = render_isolated_export(target_registry_root)
    candidate_root = tmp_path / "candidate"
    context = GeneratedExportTreeCheckContext(
        validation=stage_isolated_validation_context(candidate_root),
        temporary_root=candidate_root,
        target_registry_root=target_registry_root,
        target_export_root=target_export_root,
    )
    return context, joined, semantic_map, target_export_root


#: Substring of the registry's filing-grade review refusal. ``check_generated_export_tree``
#: selects a filing-grade snapshot partway through, so an unreviewed target revision raises
#: the same exception type these cases expect, before the comparison under test runs.
_REVIEW_GATE_REFUSAL = "filing-grade snapshot requires a reviewed revision"


def _require_the_defect_was_reached(refusal: BaseException, defect: str) -> None:
    """Refuse a pass earned by the review gate rather than by the injected defect."""
    assert _REVIEW_GATE_REFUSAL not in str(refusal), (
        f"defect {defect!r} was not detected on its own terms: the check refused on the "
        f"registry's filing-grade review gate before reaching the comparison this case "
        f"exercises, so a green result here would prove nothing about the injected drift"
    )


def _rendered_record_fragments(export_root: Path) -> list[Path]:
    """The record fragments the renderer wrote, in file order, so each tamper targets a real file."""
    return sorted(
        path
        for path in export_root.iterdir()
        if path.suffix == ".toml" and path.name != EXPORT_FRAGMENT_PROVENANCE_FILENAME
    )


def _transport_profile() -> ExportTreeTransportProfile:
    """The isolated tree's own transport profile, derived from its real joined design."""
    _joined, _map, transport, _render_profile, _evidence = isolated_authorities(ISOLATED_TREE)
    return transport


def test_check_regenerates_in_isolation_and_preserves_published_hashes(tmp_path: Path) -> None:
    """A real candidate must match every current target member without target mutation."""
    context, joined, semantic_map, target_export_root = _check_inputs(tmp_path)
    render_profile, render_evidence = isolated_render_profile()
    before = _tree_hashes(context.target_registry_root)

    checked = check_generated_export_tree(
        context=context,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=_transport_profile(),
        render_profile=render_profile,
        render_profile_source_evidence=render_evidence,
    )

    assert _tree_hashes(context.target_registry_root) == before
    assert checked.candidate.snapshot.revision.export_layouts == (checked.candidate.layout,)
    assert checked.published_manifest == checked.candidate.provenance_manifest
    assert normalised_loader_semantics(checked.published_layout) == normalised_loader_semantics(
        checked.candidate.layout,
    )
    assert _tree_hashes(isolated_export_root(context.validation.registry_root)) == _tree_hashes(target_export_root)


#: The refusal each injected defect must produce. Pairs that share a message
#: do so because production catches them in one comparison; the two manifest
#: authority cases are held apart by the field they disagree on.
_DEFECT_REFUSAL = {
    "semantic-map": "joined fields do not attest the supplied semantic map",
    "source": "transport profile SHA-256 does not match joined official source",
    "transport-profile": "transport profile SHA-256 does not match joined official source",
    "render-profile": "render_profile_sha256",
    "output-byte": "output-file digests do not match generated tree",
    "manifest-authority": "source_sha256",
    "manifest-schema": "manifest violates the current contract",
    "missing-output": "output-file digests do not match generated tree",
    "extra-output": "cannot load through the directory authority",
    "obsolete-sibling": "refuses obsolete sibling provenance manifest",
    "obsolete-direct-modelo": "refuses obsolete direct registry path",
}


@pytest.mark.parametrize(
    "defect",
    (
        "semantic-map",
        "source",
        "transport-profile",
        "render-profile",
        "output-byte",
        "manifest-authority",
        "manifest-schema",
        "missing-output",
        "extra-output",
        "obsolete-sibling",
        "obsolete-direct-modelo",
    ),
)
def test_check_refuses_drift_without_changing_published_hashes(tmp_path: Path, defect: str) -> None:
    """Every authority or membership defect fails while target bytes remain exactly as supplied."""
    context, joined, semantic_map, target_export_root = _check_inputs(tmp_path)
    profile = _transport_profile()
    render_profile, render_evidence = isolated_render_profile()
    if defect == "semantic-map":
        semantic_map = semantic_map.model_copy(
            update={
                "entries": (
                    semantic_map.entries[0].model_copy(update={"literal": "XX"}),
                    *semantic_map.entries[1:],
                ),
            },
        )
    elif defect == "source":
        joined = joined.model_copy(
            update={"source": joined.source.model_copy(update={"source_sha256": "b" * 64})},
        )
    elif defect == "transport-profile":
        profile = profile.model_copy(update={"source_sha256": "b" * 64})
    elif defect == "render-profile":
        render_profile = render_profile.model_copy(update={"fragment_ids": ("digest-drift",)})
    elif defect == "output-byte":
        output = _rendered_record_fragments(target_export_root)[0]
        output.write_bytes(output.read_bytes() + b"# drift\n")
    elif defect == "manifest-authority":
        manifest_path = target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME
        manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
        manifest_path.write_bytes(
            export_fragment_provenance_manifest_json_bytes(
                manifest.model_copy(update={"source_sha256": "b" * 64}),
            ),
        )
    elif defect == "manifest-schema":
        manifest_path = target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME
        manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
        manifest_path.write_bytes(
            export_fragment_provenance_manifest_json_bytes(
                manifest.model_copy(update={"generator_schema_version": 1}),
            ),
        )
    elif defect == "missing-output":
        _rendered_record_fragments(target_export_root)[-1].unlink()
    elif defect == "extra-output":
        (target_export_root / "0003-unreviewed.toml").write_text("unreviewed = true\n", encoding="utf-8")
    elif defect == "obsolete-sibling":
        (target_export_root.parent / "export.provenance.json").write_text("{}\n", encoding="utf-8")
    elif defect == "obsolete-direct-modelo":
        # The direct file names the target's own modelo: the obsolete-path check
        # refuses it for that modelo specifically, not as foreign registry content.
        (context.target_registry_root / "modelos" / f"{ISOLATED_TREE.modelo}.toml").write_text(
            f'[modelo]\nid = "{ISOLATED_TREE.modelo}"\n',
            encoding="utf-8",
        )
    else:
        raise AssertionError(f"unknown test defect: {defect}")
    before = _tree_hashes(context.target_registry_root)

    # Each defect must refuse with its own message: an earlier, unrelated check
    # raising the same exception type would otherwise pass the case without the
    # injected defect ever being reached.
    with pytest.raises(RegistryValidationError, match=_DEFECT_REFUSAL[defect]) as refusal:
        check_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            transport_profile=profile,
            render_profile=render_profile,
            render_profile_source_evidence=render_evidence,
        )

    _require_the_defect_was_reached(refusal.value, defect)
    assert _tree_hashes(context.target_registry_root) == before


def test_check_refuses_candidate_reuse_without_changing_published_hashes(tmp_path: Path) -> None:
    """A prior candidate output cannot become a check input or a silent green path."""
    context, joined, semantic_map, _target_export_root = _check_inputs(tmp_path)
    render_profile, render_evidence = isolated_render_profile()
    isolated_export_root(context.validation.registry_root).mkdir()
    before = _tree_hashes(context.target_registry_root)

    with pytest.raises(RegistryValidationError, match="must be absent before fresh rendering"):
        check_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            transport_profile=_transport_profile(),
            render_profile=render_profile,
            render_profile_source_evidence=render_evidence,
        )

    assert _tree_hashes(context.target_registry_root) == before


def test_check_refuses_linked_candidate_ancestor_before_rendering(tmp_path: Path) -> None:
    """A directory link cannot redirect candidate rendering before the validation boundary."""
    context, joined, semantic_map, _target_export_root = _check_inputs(tmp_path)
    render_profile, render_evidence = isolated_render_profile()
    candidate_modelos_root = context.validation.registry_root / "modelos"
    redirected_modelos_root = tmp_path / "redirected-modelos"
    candidate_modelos_root.rename(redirected_modelos_root)
    candidate_modelos_root.symlink_to(redirected_modelos_root, target_is_directory=True)
    before = _tree_hashes(context.target_registry_root)
    # The export directory rendering would reach through the link.
    redirected_export_root = (
        redirected_modelos_root / ISOLATED_TREE.modelo / "revisions" / ISOLATED_TREE.revision / "export"
    )

    with pytest.raises(RegistryValidationError, match="candidate revision root must not be a link"):
        check_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            transport_profile=_transport_profile(),
            render_profile=render_profile,
            render_profile_source_evidence=render_evidence,
        )

    assert not redirected_export_root.exists()
    assert _tree_hashes(context.target_registry_root) == before


class _SharedExportFieldFields(TypedDict):
    """The export-field fields both repeat variants share, minus the kind pairing."""

    id: str
    offset: int
    length: int
    data_type: ExportFieldDataType
    required: bool
    padding: ExportPadding
    justification: ExportJustification
    signed: bool
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


def _layout_with_repeat(repeat: Literal["binding_rows", "projection_rows"] | None) -> ExportLayoutDefinition:
    """One real layout carrying ``repeat``, with the field shape that repeat admits.

    The record model enforces the pairing both ways -- a binding-rows record must
    carry binding fields, and a projection-rows record must not -- so the two
    layouts differ in field kind as well as in repeat. That is the real shape of
    the drift this guard exists to catch: a regeneration DROPS the repeat and
    renders a single-valued casilla where the published tree renders a row
    sequence, which is why the candidate here carries no repeat at all.
    """
    common: _SharedExportFieldFields = {
        "id": "declarado.importe",
        "offset": 1,
        "length": 10,
        "data_type": CasillaDataType.MONEY,
        "required": False,
        "padding": ExportPadding.LEFT_ZERO,
        "justification": ExportJustification.RIGHT,
        "signed": False,
        "legal_refs": ("ley-35-2006:art-test",),
        "source_refs": ("aeat-test-source-001",),
    }
    if repeat == "binding_rows":
        field = ExportFieldDefinition(kind=CasillaFieldKind.BINDING, binding="binding.rows", **common)
    else:
        field = ExportFieldDefinition(
            kind=CasillaFieldKind.CASILLA,
            casilla_id=validated_casilla_id("01", surface="repeat-guard fixture"),
            **common,
        )
    return ExportLayoutDefinition(
        id="layout",
        legal_refs=("ley-35-2006:art-test",),
        source_refs=("aeat-test-source-001",),
        records=(
            ExportRecordDefinition(
                id="declarado",
                record_type="declarado",
                order=1,
                encoding=ExportEncoding.ASCII,
                line_ending="none",
                repeat=repeat,
                fields=(field,),
            ),
        ),
    )


def test_repeat_guard_refuses_a_published_binding_rows_record_the_candidate_drops() -> None:
    """A published row sequence must not regenerate into single-valued fields.

    The guard runs before the loader-semantics and byte comparisons, so this is
    the only place the operator is told the candidate LOST a repeat rather than
    merely differing from what is committed. Byte drift invites regenerate-and-
    commit, which is exactly the action that ships the truncation.
    """
    published = _layout_with_repeat("binding_rows")
    candidate = _layout_with_repeat(None)

    with pytest.raises(RegistryValidationError, match="repeat='binding_rows'") as refusal:
        _tree_check._refuse_repeat_the_candidate_would_drop(published, candidate)

    assert "declarado" in str(refusal.value)


def test_repeat_guard_admits_a_candidate_that_keeps_the_published_repeat() -> None:
    """The guard fires on a LOST repeat, not on the repeat's presence."""
    published = _layout_with_repeat("binding_rows")
    candidate = _layout_with_repeat("binding_rows")

    _tree_check._refuse_repeat_the_candidate_would_drop(published, candidate)
