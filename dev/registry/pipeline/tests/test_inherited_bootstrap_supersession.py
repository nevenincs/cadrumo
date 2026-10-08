"""An inherited manual export layout can be superseded in one revision only."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryLoadError, RegistryValidationError

from ...compiler.authority import compiled_bundled_authority
from ...compiler.loader import load_modelo_directory
from .. import cli as tree_cli
from .._tree_publication import publish_validated_generated_export_tree
from .._tree_validation import GeneratedExportTreeValidationContext
from ..bootstrap_supersession import (
    bootstrap_layout_supersession_fingerprint,
    bootstrap_manual_source_revision_root,
    validate_bootstrap_manual_export_layout_supersession,
)
from ..bootstrap_targets import GeneratedExportBootstrapTarget
from ..candidate_staging import stage_generated_export_candidate
from ..cli import (
    GeneratedTreeInvocation,
    PreparedGeneratedTreeInvocation,
    check_prepared_invocation,
    prepare_generated_tree_invocation,
)
from ..export_fragment_provenance import ExportFragmentTarget
from ..export_tree_models import RenderedExportTree
from ..export_tree_serialization import render_toml_bytes
from ..tree_publication_contracts import (
    GeneratedExportSupersession,
    GeneratedExportTreePublicationContext,
    GeneratedExportTreeTargetStateReceipt,
)
from ..tree_publication_supersession import _install_generated_form_companion, _retarget_reviewed_constructs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CASES = (
    (
        "131",
        "2026-3t-4t",
        "2026",
        "modelo-131-fichero-boe",
        1,
        "aeat-dr-131-2026-late",
        "b394370ae16d303a3ed7e192ca34ba1ff49dbbbea49e4d2bbe220085cc53600f",
    ),
    (
        "189",
        "2024",
        "2023",
        "modelo-189-fichero-2023",
        0,
        "aeat-dr-189-2023",
        "c493f8d9d927f28211336324cbe17ab7bae7b256d3c563273e01a76834757d6a",
    ),
    (
        "189",
        "2025",
        "2023",
        "modelo-189-fichero-2023",
        0,
        "aeat-dr-189-2023",
        "c493f8d9d927f28211336324cbe17ab7bae7b256d3c563273e01a76834757d6a",
    ),
)


def _prepublication_registry(root: Path, *, modelo: str, ancestor: str, revisions: tuple[str, ...]) -> Path:
    """Build a scratch manual ancestor before its generated publication.

    The live corpus now publishes these layouts. Reconstruct the admission
    state explicitly while keeping the exact typed layout, source pins and
    storage deltas that the supersession contract operates on.
    """
    registry_root = root / "registry" / "aeat"
    for catalogue in bundled_path("registry", "aeat").iterdir():
        if catalogue.is_dir() and catalogue.name != "modelos":
            shutil.copytree(catalogue, registry_root / catalogue.name)
    source_modelo_root = bundled_path("registry", "aeat", "modelos", modelo)
    loaded = load_modelo_directory(source_modelo_root)
    modelo_root = registry_root / "modelos" / modelo
    shutil.copytree(source_modelo_root, modelo_root)
    for revision_root in (modelo_root / "revisions").iterdir():
        export = revision_root / "export"
        assert export.resolve().is_relative_to(registry_root.resolve())
        if export.exists():
            shutil.rmtree(export)
    manual_root = modelo_root / "revisions" / ancestor / "export_layouts"
    manual_root.mkdir(exist_ok=True)
    assert not tuple(manual_root.iterdir()), "the scratch ancestor must have one explicit manual source"
    layout = loaded.revisions[ancestor].export_layouts[0]
    # The manual predecessor existed before source-derived full envelopes were
    # published. A child replaces source_refs when it inherits this body layout;
    # an early generated wrapper must not be transplanted into that old state.
    payload = {
        "revisions": {
            ancestor: {
                "export_layouts": [layout.model_dump(mode="json", exclude_none=True, exclude={"filing_envelope"})]
            }
        }
    }
    (manual_root / "0001-layout.toml").write_bytes(render_toml_bytes("0001-layout.toml", payload))
    return registry_root


def test_inherited_generated_form_companion_uses_canonical_local_filename(tmp_path: Path) -> None:
    """A detached validation filename must not enter the thin published child."""
    source_modelo_root = bundled_path("registry", "aeat", "modelos", "131")
    source_fragment = source_modelo_root / "revisions" / "2026-3t-4t" / "form_layouts" / "0001-form-layout.toml"
    assert source_fragment.is_file()
    candidate_root = tmp_path / "candidate" / "registry" / "aeat"
    candidate_form_root = candidate_root / "modelos" / "131" / "revisions" / "2026-3t-4t" / "form_layouts"
    candidate_form_root.mkdir(parents=True)
    (candidate_form_root / "0001-complete-edition.toml").write_bytes(source_fragment.read_bytes())
    staged_revision_root = tmp_path / "staged-child"
    staged_form_root = staged_revision_root / "form_layouts"
    staged_form_root.mkdir(parents=True)
    (staged_form_root / "0001-form-layout.toml").write_text("stale generated companion", encoding="utf-8")
    context = GeneratedExportTreePublicationContext(
        validation=GeneratedExportTreeValidationContext(
            registry_root=candidate_root,
            source_root=bundled_path(),
            target=ExportFragmentTarget(modelo="131", revision_id="2026-3t-4t", design_epoch="2026-late"),
            filing_year=2026,
            period="3T",
        ),
        temporary_root=tmp_path,
        target_root=tmp_path / "live-registry",
        target_export_root=staged_revision_root / "export",
    )

    _install_generated_form_companion(
        context=context,
        staged_revision_root=staged_revision_root,
        source_modelo_root=source_modelo_root,
        revision_id="2026-3t-4t",
    )

    assert [path.name for path in staged_form_root.iterdir()] == ["0001-form-layout.toml"]
    assert (staged_form_root / "0001-form-layout.toml").read_bytes() == source_fragment.read_bytes()


@pytest.mark.parametrize("modelo,revision,ancestor,layout_id,references,source_ref,source_sha256", _CASES)
def test_reviewed_inherited_manual_layout_has_unique_source_pinned_ancestor(
    tmp_path: Path,
    modelo: str,
    revision: str,
    ancestor: str,
    layout_id: str,
    references: int,
    source_ref: str,
    source_sha256: str,
) -> None:
    registry_root = _prepublication_registry(tmp_path, modelo=modelo, ancestor=ancestor, revisions=(revision,))
    modelo_root = registry_root / "modelos" / modelo
    loaded = load_modelo_directory(modelo_root)
    manual_root, manual_revision = bootstrap_manual_source_revision_root(modelo_root, loaded, revision=revision)
    assert manual_revision == ancestor
    assert manual_root == modelo_root / "revisions" / ancestor
    assert not (modelo_root / "revisions" / revision / "export_layouts").exists()
    assert tuple(str(layout.id) for layout in loaded.revisions[revision].export_layouts) == (layout_id,)
    source_fingerprint = bootstrap_layout_supersession_fingerprint(manual_root)
    assert validate_bootstrap_manual_export_layout_supersession(
        modelo_root,
        revision=revision,
        superseded_layout_id=layout_id,
        expected_references=references,
        generated_layout_id=layout_id,
        source_ref=source_ref,
        source_sha256=source_sha256,
        manual_source_sha256=source_fingerprint,
        manual_origin_revision=ancestor,
    ) == bootstrap_layout_supersession_fingerprint(modelo_root / "revisions" / revision)


def test_inherited_layout_refuses_missing_or_wrong_source_pins_and_identity(tmp_path: Path) -> None:
    registry_root = _prepublication_registry(tmp_path, modelo="131", ancestor="2026", revisions=("2026-3t-4t",))
    modelo_root = registry_root / "modelos" / "131"

    def guard(
        *,
        manual_origin_revision: str | None = "2026",
        source_ref: str | None = None,
        source_sha256: str | None = None,
        superseded_layout_id: str = "modelo-131-fichero-boe",
        expected_references: int = 1,
        generated_layout_id: str | None = None,
    ) -> str:
        return validate_bootstrap_manual_export_layout_supersession(
            modelo_root,
            revision="2026-3t-4t",
            superseded_layout_id=superseded_layout_id,
            expected_references=expected_references,
            generated_layout_id=generated_layout_id,
            source_ref=source_ref,
            source_sha256=source_sha256,
            manual_origin_revision=manual_origin_revision,
        )

    with pytest.raises(ValueError, match="requires an exact source"):
        guard()
    with pytest.raises(ValueError, match="requires an exact manual origin"):
        guard(
            manual_origin_revision=None,
            source_ref="aeat-dr-131-2026-late",
            source_sha256=_CASES[0][-1],
        )
    with pytest.raises(ValueError, match="manual origin is"):
        guard(
            manual_origin_revision="2025",
            source_ref="aeat-dr-131-2026-late",
            source_sha256=_CASES[0][-1],
        )
    with pytest.raises(ValueError, match="does not cite source"):
        guard(source_ref="aeat-dr-131-2025", source_sha256="0" * 64)
    with pytest.raises(ValueError, match="digest changed"):
        guard(source_ref="aeat-dr-131-2026-late", source_sha256="0" * 64)
    with pytest.raises(
        (RegistryLoadError, ValueError), match=r"expected exactly manual layout|contains no .*fragments"
    ):
        guard(
            superseded_layout_id="wrong",
            source_ref="aeat-dr-131-2026-late",
            source_sha256=_CASES[0][-1],
        )
    with pytest.raises(ValueError, match="expected 2 construct reference"):
        guard(
            expected_references=2,
            source_ref="aeat-dr-131-2026-late",
            source_sha256=_CASES[0][-1],
        )
    with pytest.raises(ValueError, match="stable layout id"):
        guard(
            generated_layout_id="different-layout",
            source_ref="aeat-dr-131-2026-late",
            source_sha256=_CASES[0][-1],
        )


def test_inherited_layout_refuses_changed_or_missing_ancestor(tmp_path: Path) -> None:
    registry_root = _prepublication_registry(tmp_path, modelo="131", ancestor="2026", revisions=("2026-3t-4t",))
    copied_root = registry_root / "modelos" / "131"
    ancestor = copied_root / "revisions" / "2026"
    pinned = bootstrap_layout_supersession_fingerprint(ancestor)
    fragment = next((ancestor / "export_layouts").glob("*.toml"))
    fragment.write_bytes(fragment.read_bytes() + b"\n# changed after review\n")
    with pytest.raises(ValueError, match="ancestor changed"):
        validate_bootstrap_manual_export_layout_supersession(
            copied_root,
            revision="2026-3t-4t",
            superseded_layout_id="modelo-131-fichero-boe",
            expected_references=1,
            source_ref="aeat-dr-131-2026-late",
            source_sha256=_CASES[0][-1],
            manual_source_sha256=pinned,
            manual_origin_revision="2026",
        )
    fragment.unlink()
    fragment.parent.rmdir()
    with pytest.raises(RegistryLoadError, match=r"family override selector.*missing"):
        validate_bootstrap_manual_export_layout_supersession(
            copied_root,
            revision="2026-3t-4t",
            superseded_layout_id="modelo-131-fichero-boe",
            expected_references=1,
            source_ref="aeat-dr-131-2026-late",
            source_sha256=_CASES[0][-1],
            manual_origin_revision="2026",
        )


@pytest.mark.parametrize("modelo,revision,ancestor,layout_id,references,source_ref,source_sha256", _CASES)
def test_reviewed_candidate_detaches_only_target_and_keeps_ancestor_intact(
    tmp_path: Path,
    modelo: str,
    revision: str,
    ancestor: str,
    layout_id: str,
    references: int,
    source_ref: str,
    source_sha256: str,
) -> None:
    registry_root = _prepublication_registry(
        tmp_path / "source", modelo=modelo, ancestor=ancestor, revisions=(revision,)
    )
    ancestor_root = registry_root / "modelos" / modelo / "revisions" / ancestor
    ancestor_before = bootstrap_layout_supersession_fingerprint(ancestor_root)
    target = GeneratedExportBootstrapTarget(
        modelo=modelo,
        revision=revision,
        source_ref=source_ref,
        source_sha256=source_sha256,
        layout_id=layout_id,
        line_ending="none",
        supersedes_layout_id=layout_id,
        superseded_construct_references=references,
        manual_origin_revision=ancestor,
    )
    staged = stage_generated_export_candidate(
        registry_root,
        tmp_path / "candidate",
        modelo=modelo,
        revision=revision,
        supporting_modelos=(),
        bootstrap_target=target,
    )
    assert list((staged / "revisions").iterdir()) == [staged / "revisions" / revision]
    assert not (staged / "revisions" / revision / "export_layouts").exists()
    assert load_modelo_directory(staged).revisions[revision].export_layouts == ()
    assert bootstrap_layout_supersession_fingerprint(ancestor_root) == ancestor_before


def test_inherited_construct_cannot_change_layout_id_without_a_local_keyed_delta(tmp_path: Path) -> None:
    source_revision = bundled_path("registry", "aeat", "modelos", "131", "revisions", "2026-3t-4t")
    staged_revision = tmp_path / "2026-3t-4t"
    shutil.copytree(source_revision, staged_revision)
    before = bootstrap_layout_supersession_fingerprint(staged_revision)
    reviewed = GeneratedExportSupersession(
        superseded_layout_id="modelo-131-fichero-boe",
        generated_layout_id="different-layout",
        expected_construct_references=1,
        source_state_sha256=before,
    )
    with pytest.raises(RegistryValidationError, match="inherited construct without a keyed local delta"):
        _retarget_reviewed_constructs(staged_revision, revision_id="2026-3t-4t", supersession=reviewed)
    assert bootstrap_layout_supersession_fingerprint(staged_revision) == before

    stable = GeneratedExportSupersession(
        superseded_layout_id="modelo-131-fichero-boe",
        generated_layout_id="modelo-131-fichero-boe",
        expected_construct_references=1,
        source_state_sha256=before,
    )
    _retarget_reviewed_constructs(staged_revision, revision_id="2026-3t-4t", supersession=stable)
    assert bootstrap_layout_supersession_fingerprint(staged_revision) == before


@pytest.fixture(scope="module")
def inherited_publication_candidate(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[PreparedGeneratedTreeInvocation, RenderedExportTree]:
    """Prepare one real, source-complete late-131 candidate for both cutover outcomes."""
    registry_root = _prepublication_registry(
        tmp_path_factory.mktemp("manual-131"), modelo="131", ancestor="2026", revisions=("2026-3t-4t",)
    )
    invocation = GeneratedTreeInvocation("131", "2026-3t-4t", "aeat-dr-131-2026-late", 2026, "3T")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            tree_cli,
            "bundled_path",
            lambda *parts: registry_root if parts == ("registry", "aeat") else bundled_path(*parts),
        )
        # Live bootstrap enrollment is retired at publication. This fixture
        # reconstructs the reviewed prepublication target explicitly.
        target = GeneratedExportBootstrapTarget(
            modelo="131",
            revision="2026-3t-4t",
            source_ref="aeat-dr-131-2026-late",
            source_sha256=_CASES[0][-1],
            layout_id="modelo-131-fichero-boe",
            line_ending="none",
            supersedes_layout_id="modelo-131-fichero-boe",
            superseded_construct_references=1,
            manual_origin_revision="2026",
        )
        patch.setattr(tree_cli, "generated_export_bootstrap_target", lambda **_kwargs: target)
        prepared = prepare_generated_tree_invocation(
            invocation, tmp_path_factory.mktemp("inherited-131") / "prepared", authority=compiled_bundled_authority()
        )
    result, rendered, _ = check_prepared_invocation(prepared)
    assert result == "publishable_absence"
    return prepared, rendered


@pytest.mark.parametrize("fail_validation", [False, True], ids=["accepted", "rollback"])
def test_inherited_publication_keeps_thin_child_and_rolls_back_on_refusal(
    tmp_path: Path,
    inherited_publication_candidate: tuple[PreparedGeneratedTreeInvocation, RenderedExportTree],
    fail_validation: bool,
) -> None:
    """The actual publisher retains keyed delta storage through success and rollback."""
    prepared, rendered = inherited_publication_candidate
    supersession = prepared.supersession
    assert supersession is not None
    source_modelo_root = prepared.target_root / "modelos" / "131"
    target_root = tmp_path / "registry" / "aeat"
    for catalogue in prepared.target_root.iterdir():
        if catalogue.is_dir() and catalogue.name != "modelos":
            shutil.copytree(catalogue, target_root / catalogue.name)
    target_modelo_root = target_root / "modelos" / "131"
    target_modelo_root.parent.mkdir(parents=True)
    shutil.copytree(source_modelo_root, target_modelo_root)
    child_root = target_modelo_root / "revisions" / "2026-3t-4t"
    old_digest = bootstrap_layout_supersession_fingerprint(child_root)
    ancestor_root = child_root.parent / "2026"
    ancestor_digest = bootstrap_layout_supersession_fingerprint(ancestor_root)
    revision_bytes = (child_root / "revision.toml").read_bytes()
    target_export_root = child_root / "export"
    assert not (child_root / "constructs").exists()

    def validate_live() -> None:
        if fail_validation:
            raise RegistryValidationError("forced full live validation refusal")
        loaded = load_modelo_directory(target_modelo_root)
        revision = loaded.revisions["2026-3t-4t"]
        assert len(revision.export_layouts) == 1
        assert str(revision.export_layouts[0].id) == supersession.generated_layout_id

    context = GeneratedExportTreePublicationContext(
        validation=prepared.validation,
        temporary_root=prepared.candidate_root.parents[2],
        target_root=target_root,
        target_export_root=target_export_root,
        expected_target_state=GeneratedExportTreeTargetStateReceipt.observe(
            target_export_root,
            supersession_source_sha256=supersession.source_state_sha256,
        ),
        supersession=supersession,
        final_live_validator=validate_live,
    )

    def publish() -> None:
        publish_validated_generated_export_tree(
            context=context,
            joined=prepared.inputs.joined,
            semantic_map=prepared.inputs.semantic_map,
            rendered=rendered,
            render_profile=prepared.inputs.render_profile,
            render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
        )

    if fail_validation:
        with pytest.raises(RegistryValidationError, match="previous revision was restored"):
            publish()
        assert bootstrap_layout_supersession_fingerprint(child_root) == old_digest
        assert not target_export_root.exists()
    else:
        publish()
        assert bootstrap_layout_supersession_fingerprint(child_root) != old_digest
        assert target_export_root.is_dir()
    assert bootstrap_layout_supersession_fingerprint(ancestor_root) == ancestor_digest
    assert not (child_root / "export_layouts").exists()
    assert not (child_root / "constructs").exists()
    assert (child_root / "revision.toml").read_bytes() == revision_bytes
