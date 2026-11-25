"""A reviewed rename set admits exactly its typed refusal, its pinned members and nothing broader."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal

import pytest
import typer

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryLoadError, RegistryValidationError
from cadrumo.domain.calculations.registry.tests.authored_editions import revision_covering

from ...compiler.authority import compiled_bundled_authority
from ...compiler.loader import load_modelo_directory
from ...compiler.revision_export_projection import (
    UndeclaredExportTargetError,
    undeclared_export_refusal,
    undeclared_export_targets,
)
from ...form_layout.generator import generate_revision_layout
from ...form_layout.serialization import form_layout_fragment_path, render_form_layout_toml
from .. import cli
from ..candidate_source_chain import stage_source_chain
from ..export_fragment_provenance import load_export_fragment_provenance_manifest
from ..rename_set_static_repair import (
    REVIEWED_RENAME_SETS,
    reviewed_rename_set,
    validate_rename_refusal,
    validated_rename_repair_source,
)
from .generated_tree_test_support import ISOLATED_TREE

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SET = REVIEWED_RENAME_SETS[0]
_FIRST = _SET.members[0]
_RENAMED = tuple(sorted(_SET.renamed_casilla_ids))


def _targets(modelo: str, casilla_ids: tuple[str, ...], revision: str = "edition") -> UndeclaredExportTargetError:
    return UndeclaredExportTargetError(Path("registry") / "modelos" / modelo, revision, casilla_ids)


def test_typed_refusal_carries_its_identities_and_stays_a_load_error() -> None:
    targets = _targets(_SET.modelo, _RENAMED)
    refusal = undeclared_export_refusal(targets)

    assert type(refusal) is RegistryLoadError
    assert not isinstance(refusal, RegistryValidationError)
    assert undeclared_export_targets(refusal) is targets
    assert (targets.modelo_id, targets.revision_id, targets.casilla_ids) == (_SET.modelo, "edition", _RENAMED)
    assert all(casilla_id in str(refusal) for casilla_id in _RENAMED)


def test_any_other_load_refusal_carries_no_stale_export_identities() -> None:
    unrelated = RegistryLoadError("an unrelated malformed table")
    unrelated.__cause__ = ValueError("a different cause")

    assert undeclared_export_targets(RegistryLoadError("an unrelated malformed table")) is None
    assert undeclared_export_targets(unrelated) is None


def test_the_projection_module_loads_after_the_error_code_catalogue() -> None:
    """A CadrumoError subclass defined in dev/ is refused once the catalogue has loaded, so none may stand there."""
    loaded = subprocess.run(
        [
            sys.executable,
            "-c",
            "from cadrumo.core.errors.error_codes import declared_error_codes_by_qualname as codes; codes(); "
            "import dev.registry.compiler.revision_export_projection",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert loaded.returncode == 0, loaded.stderr[-2000:]


def test_the_reviewed_member_and_manifest_select_its_set() -> None:
    assert reviewed_rename_set(_SET.modelo, _FIRST.source_ref, _FIRST.manifest_sha256) is _SET


@pytest.mark.parametrize(
    ("modelo", "source_ref", "manifest"),
    [
        pytest.param(_SET.modelo, _FIRST.source_ref, "0" * 64, id="stale-manifest"),
        pytest.param(_SET.modelo, _FIRST.source_ref, None, id="no-manifest"),
        pytest.param(_SET.modelo, "aeat-dr-unreviewed", _FIRST.manifest_sha256, id="unreviewed-target"),
        pytest.param("303", _FIRST.source_ref, _FIRST.manifest_sha256, id="other-modelo"),
    ],
)
def test_an_unreviewed_target_or_manifest_refuses(modelo: str, source_ref: str, manifest: str | None) -> None:
    with pytest.raises(RegistryValidationError, match="exact reviewed rename-set member"):
        reviewed_rename_set(modelo, source_ref, manifest)


def test_exactly_the_renamed_ids_are_admitted() -> None:
    validate_rename_refusal(_SET, _targets(_SET.modelo, _RENAMED))


@pytest.mark.parametrize(
    "refusal",
    [
        pytest.param(_targets(_SET.modelo, (*_RENAMED, "00999")), id="extra-unknown-id"),
        pytest.param(_targets(_SET.modelo, _RENAMED[:-1]), id="missing-id"),
        pytest.param(_targets(_SET.modelo, (*_RENAMED, _RENAMED[0])), id="duplicate-id"),
        pytest.param(_targets("303", _RENAMED), id="other-modelo"),
    ],
)
def test_any_other_unknown_id_set_refuses(refusal: UndeclaredExportTargetError) -> None:
    with pytest.raises(RegistryValidationError, match="beyond the reviewed rename"):
        validate_rename_refusal(_SET, refusal)


def test_a_committed_tree_whose_manifest_moved_refuses_before_any_overlay(tmp_path: Path) -> None:
    """Once a member is republished, its pin is stale and the live tree no longer matches it."""
    modelo_root = bundled_path("registry", "aeat", "modelos", _SET.modelo)
    live = {path.parent.parent.name for path in modelo_root.glob("revisions/*/export/_generation.provenance.json")}
    assert live, "the reviewed modelo must carry committed exports"
    with pytest.raises(RegistryValidationError, match="manifest differs from the reviewed digest"):
        validated_rename_repair_source(
            refusal=_targets(_SET.modelo, _RENAMED),
            modelo=_SET.modelo,
            revision=sorted(live)[0],
            source_ref=_FIRST.source_ref,
            filing_year=1,
            period="0A",
            expected_manifest_sha256=_FIRST.manifest_sha256,
            overlay_parent=tmp_path / "overlay",
        )
    assert not (tmp_path / "overlay").exists()


def _invocation() -> cli.GeneratedTreeInvocation:
    return cli.GeneratedTreeInvocation(_SET.modelo, "edition", _FIRST.source_ref, 1, "0A", _FIRST.manifest_sha256)


_Action = Literal["check", "publish", "republish"]


def _route(
    monkeypatch: pytest.MonkeyPatch,
    compile_refusal: Exception,
    action: _Action,
    routed: list[UndeclaredExportTargetError],
) -> None:
    """Drive the real lifecycle runner with a compiler that refuses; record what reaches the set repair."""

    def refuse() -> object:
        raise compile_refusal

    def record(_invocation: cli.GeneratedTreeInvocation, refusal: UndeclaredExportTargetError, _root: Path) -> None:
        routed.append(refusal)

    monkeypatch.setattr(cli, "compiled_bundled_authority", refuse)
    monkeypatch.setattr(cli, "recover_interrupted_supersession_bundle", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "republish_rename_set", record)
    cli.run(_invocation(), action=action)


def test_only_the_typed_refusal_routes_a_republish_to_the_rename_set(monkeypatch: pytest.MonkeyPatch) -> None:
    targets = _targets(_SET.modelo, _RENAMED)
    routed: list[UndeclaredExportTargetError] = []

    _route(monkeypatch, undeclared_export_refusal(targets), "republish", routed)

    assert routed == [targets]


@pytest.mark.parametrize("action", ["check", "publish"])
def test_the_typed_refusal_outside_republication_still_refuses(
    monkeypatch: pytest.MonkeyPatch, action: _Action
) -> None:
    routed: list[UndeclaredExportTargetError] = []
    with pytest.raises(typer.Exit):
        _route(monkeypatch, undeclared_export_refusal(_targets(_SET.modelo, _RENAMED)), action, routed)
    assert routed == []


def test_a_different_load_refusal_still_raises_without_repair(monkeypatch: pytest.MonkeyPatch) -> None:
    routed: list[UndeclaredExportTargetError] = []
    with pytest.raises(typer.Exit):
        _route(monkeypatch, RegistryLoadError("an unrelated malformed table"), "republish", routed)
    assert routed == []


def _published_revision(modelo: str, source_ref: str) -> str:
    revisions = [
        manifest.parent.parent.name
        for manifest in bundled_path("registry", "aeat", "modelos", modelo).glob(
            "revisions/*/export/_generation.provenance.json"
        )
        if str(load_export_fragment_provenance_manifest(manifest.read_bytes()).source_ref) == source_ref
    ]
    assert len(revisions) == 1, (modelo, source_ref, revisions)
    return revisions[0]


def test_each_republished_member_carries_the_form_owners_own_bytes() -> None:
    """The set installed each member's form; the form owner regenerating it now yields the same bytes."""
    modelo_root = bundled_path("registry", "aeat", "modelos", _SET.modelo)
    definition = load_modelo_directory(modelo_root)
    sources = {str(key): value for key, value in compiled_bundled_authority().catalogues.sources.items()}
    for member in _SET.members:
        revision = _published_revision(_SET.modelo, member.source_ref)
        generated = generate_revision_layout(
            _SET.modelo, definition.revisions[revision], sources=sources, data_root=bundled_path()
        )
        assert generated.layout is not None, generated.failure
        committed = form_layout_fragment_path(modelo_root / "revisions" / revision).read_bytes()
        assert committed == render_form_layout_toml(revision, generated.layout).encode("utf-8")


def _two_edition_modelo(tmp_path: Path) -> tuple[Path, str, str]:
    """Copy the isolated fixture's modelo, naming its target and a second exported edition."""
    source = bundled_path("registry", "aeat", "modelos", ISOLATED_TREE.modelo)
    sibling = revision_covering(ISOLATED_TREE.modelo, ISOLATED_TREE.filing_year - 1)
    root = tmp_path / "modelos" / ISOLATED_TREE.modelo
    shutil.copytree(source, root)
    return root, ISOLATED_TREE.revision, str(sibling.id)


def _plant_undeclared_export_target(revision_root: Path) -> None:
    """Rebind one exported casilla cell to an id the edition does not declare, as a rename leaves it."""
    for fragment in sorted((revision_root / "export").glob("*-record-*.toml")):
        text = fragment.read_bytes()
        marker = b'casilla_id = "'
        if marker in text:
            start = text.index(marker) + len(marker)
            end = text.index(b'"', start)
            fragment.write_bytes(text[:start] + b"99999" + text[end:])
            return
    pytest.fail("the sibling export binds no casilla cell to plant into")


def test_source_chain_staging_from_the_live_root_meets_a_stale_sibling_export(tmp_path: Path) -> None:
    """Staging one member loads the whole modelo, so a sibling's stale export refuses with the typed error."""
    modelo_root, target, sibling = _two_edition_modelo(tmp_path / "live")
    _plant_undeclared_export_target(modelo_root / "revisions" / sibling)

    with pytest.raises(RegistryLoadError) as refused:
        stage_source_chain(modelo_root, tmp_path / "staged", revision=target, include_target_export=False)

    targets = undeclared_export_targets(refused.value)
    assert targets is not None
    assert targets.revision_id == sibling
    assert targets.casilla_ids == ("99999",)


def test_source_chain_staging_from_an_overlay_without_the_stale_export_succeeds(tmp_path: Path) -> None:
    """The repair stages members from an overlay whose stale exports were removed, which loads."""
    modelo_root, target, sibling = _two_edition_modelo(tmp_path / "overlay")
    _plant_undeclared_export_target(modelo_root / "revisions" / sibling)
    shutil.rmtree(modelo_root / "revisions" / sibling / "export")

    staged = stage_source_chain(modelo_root, tmp_path / "staged", revision=target, include_target_export=False)

    assert (staged / "revisions" / target).is_dir()
