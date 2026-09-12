"""Shared exclusions for isolated generated-export candidate authority.

Candidates must contain the authored revision authority and no pre-existing
export authority. The registry loader accepts both the current ``export/``
fragment directory and the superseded ``export_layouts/`` form, so excluding
only one lets a legacy tree participate in validation of its replacement.
"""

from __future__ import annotations

import shutil
import tomllib
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

import rtoml

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import DeclaredPredecessor

from ..compiler.edition_materialisation import MaterialisedEdition, materialise_edition
from ..compiler.loader import load_modelo_directory
from ._export_tree import _render_toml_bytes

__all__ = [
    "GeneratedExportBootstrapTarget",
    "generated_export_bootstrap_target",
    "ignore_export_authority_directories",
    "retarget_bootstrap_construct_export_layout",
    "stage_continuity_metadata",
    "stage_generated_export_candidate",
    "stage_supplementary_orden_authority",
]


_EXPORT_AUTHORITY_DIRECTORY_NAMES: Final[frozenset[str]] = frozenset({"export", "export_layouts"})
_BOOTSTRAP_TARGETS_PATH: Final[Path] = Path(__file__).with_name("generated_export_bootstrap_targets.toml")
_CONTINUITY_SECTIONS: Final[tuple[str, ...]] = ("casillas", "casilla_continuidad_evolutions")
_PREDECESSOR_DECLARATION: Final = "predecessor"
_CASILLA_SECTION: Final = "casillas"
_COMPLETE_CASILLA_FRAGMENT: Final = "complete-edition.toml"


@dataclass(frozen=True, slots=True)
class GeneratedExportBootstrapTarget:
    """One reviewed transport and supersession declaration for an unpublished tree."""

    modelo: str
    revision: str
    source_ref: str
    source_sha256: str
    layout_id: str
    line_ending: Literal["crlf", "lf", "none"]
    supersedes_layout_id: str | None
    superseded_construct_references: int


def generated_export_bootstrap_target(
    *,
    modelo: str,
    revision: str,
    source_ref: str,
    source_sha256: str,
) -> GeneratedExportBootstrapTarget | None:
    """Return the uniquely matching reviewed bootstrap declaration, if one exists."""
    payload = tomllib.loads(_BOOTSTRAP_TARGETS_PATH.read_text("utf-8"))
    matches = [
        row
        for row in payload.get("targets", [])
        if row.get("modelo") == modelo
        and row.get("revision") == revision
        and row.get("source_ref") == source_ref
        and row.get("source_sha256") == source_sha256
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError(f"multiple generated-export bootstrap targets match {modelo}/{revision}/{source_ref}")
    row = matches[0]
    line_ending = row.get("line_ending")
    if line_ending not in {"crlf", "lf", "none"}:
        raise ValueError("reviewed generated-export bootstrap target has invalid line ending")
    supersedes_layout_id = row.get("supersedes_layout_id")
    superseded_construct_references = row.get("superseded_construct_references", 0)
    if supersedes_layout_id is not None and (not isinstance(supersedes_layout_id, str) or not supersedes_layout_id):
        raise ValueError("reviewed generated-export bootstrap target has invalid superseded layout id")
    if not isinstance(superseded_construct_references, int) or superseded_construct_references < 0:
        raise ValueError("reviewed generated-export bootstrap target has invalid superseded construct-reference count")
    if (supersedes_layout_id is None) != (superseded_construct_references == 0):
        raise ValueError("reviewed generated-export bootstrap target must pair its superseded layout and references")
    return GeneratedExportBootstrapTarget(
        modelo=str(row["modelo"]),
        revision=str(row["revision"]),
        source_ref=str(row["source_ref"]),
        source_sha256=str(row["source_sha256"]),
        layout_id=str(row["layout_id"]),
        line_ending=line_ending,
        supersedes_layout_id=supersedes_layout_id,
        superseded_construct_references=superseded_construct_references,
    )


def ignore_export_authority_directories(_directory: str, names: Collection[str]) -> set[str]:
    """Return every loader-recognized export-authority directory in ``names``."""
    return set(_EXPORT_AUTHORITY_DIRECTORY_NAMES.intersection(names))


def stage_supplementary_orden_authority(
    source_root: Path,
    candidate_root: Path,
    *,
    modelos: Collection[str],
) -> None:
    """Copy supplementary Orden authority required by the staged modelo closure."""
    if "303" in modelos:
        shutil.copytree(source_root / "m303_orden_anual", candidate_root / "m303_orden_anual")


def stage_continuity_metadata(
    source_modelo_root: Path,
    staging_root: Path,
    *,
    revision: str,
) -> Path | None:
    """Stage every sibling revision's facts as the witness the target validates against.

    Candidate validation isolates the target revision on purpose, so any check
    that reasons across a modelo's revisions needs those revisions supplied
    separately. Strict continuity needs the target's predecessor chain; the
    semantic-role singleton check needs every sibling, because a role declared
    once per revision is a singleton only in a tree that holds one revision.
    Staging all siblings answers both. A modelo with a single revision has no
    siblings to stage, and there a singleton genuinely is one.

    Which edition a sibling inherits from is the ``predecessor`` it declares,
    and the loader alone follows that chain; continuity evolution records play
    no part in choosing what is staged. In a modelo where no edition names a
    predecessor, every sibling states its own rows and is copied as it stands.
    Once any edition names one, a sibling's own files may be only the rows it
    changed, and the target it may inherit through is the one revision a
    witness must not hold. Every sibling is then staged as the complete edition
    the loader resolves for it, carrying no predecessor declaration, so each
    loads on its own and none depends on a chain the witness cannot supply.
    """
    definition = load_modelo_directory(source_modelo_root)
    if revision not in definition.revisions:
        raise ValueError(f"modelo {definition.id} declares no revision {revision!r}")

    siblings = sorted(str(item) for item in definition.revisions if str(item) != revision)
    if not siblings:
        return None
    metadata_modelo_root = staging_root / "continuity-metadata" / str(definition.id)
    metadata_modelo_root.mkdir(parents=True)
    shutil.copy2(source_modelo_root / "manifest.toml", metadata_modelo_root / "manifest.toml")
    names_a_predecessor = any(
        isinstance(item.predecessor, DeclaredPredecessor) for item in definition.revisions.values()
    )
    for sibling_id in siblings:
        if names_a_predecessor:
            _stage_complete_sibling(source_modelo_root, metadata_modelo_root, revision=sibling_id)
            continue
        source_revision_root = source_modelo_root / "revisions" / sibling_id
        target_revision_root = metadata_modelo_root / "revisions" / sibling_id
        target_revision_root.mkdir(parents=True)
        shutil.copy2(source_revision_root / "revision.toml", target_revision_root / "revision.toml")
        for member in _CONTINUITY_SECTIONS:
            source_member = source_revision_root / member
            if source_member.is_dir():
                shutil.copytree(source_member, target_revision_root / member)
    return metadata_modelo_root


def _stage_complete_sibling(source_modelo_root: Path, metadata_modelo_root: Path, *, revision: str) -> None:
    """Write one sibling as the complete edition it stands for, naming no predecessor.

    The witness carries a sibling's manifest facts and its continuity sections
    and nothing else, whether or not the sibling inherits; the resolved edition
    is cut back to exactly those members so the two staging forms hold the same
    families. A declared root's explicit no-predecessor is dropped with any
    named predecessor, because a witness mixing declared roots with editions
    that no longer name one would read as a forest with several key-less roots.
    """
    edition = materialise_edition(source_modelo_root, revision)
    manifest = tomllib.loads((source_modelo_root / "revisions" / revision / "revision.toml").read_text("utf-8"))
    manifest_members = frozenset(manifest.get("revisions", {}).get(revision, {}))
    manifest_table = {
        key: value
        for key, value in edition.table.items()
        if key in manifest_members and key != _PREDECESSOR_DECLARATION
    }
    revisions_root = metadata_modelo_root / "revisions" / revision
    revisions_root.mkdir(parents=True, exist_ok=True)
    (revisions_root / "revision.toml").write_bytes(
        _render_toml_bytes("revision.toml", {"revisions": {revision: manifest_table}}),
    )
    for section in _CONTINUITY_SECTIONS:
        value = edition.table.get(section)
        if value is None:
            continue
        section_root = revisions_root / section
        section_root.mkdir()
        (section_root / "complete-edition.toml").write_bytes(
            _render_toml_bytes(
                f"{section}/complete-edition.toml",
                {"revisions": {revision: {section: value}}},
            ),
        )


#: Authority directories resolved BY NAME at registry load, beside `legal` and
#: the modelo trees. Read from the shipped tree rather than hardcoded, so a
#: provider directory introduced by another change is staged without this module
#: being edited to notice it.
def _fact_provider_directories() -> frozenset[str]:
    root = bundled_path("registry", "aeat")
    skip = {"legal", "modelos", "user_profile", "m303_orden_anual"}
    return frozenset(entry.name for entry in root.iterdir() if entry.is_dir() and entry.name not in skip)


_FACT_PROVIDER_DIRECTORIES = _fact_provider_directories()


def stage_generated_export_candidate(
    source_root: Path,
    candidate_root: Path,
    *,
    modelo: str,
    revision: str,
    supporting_modelos: Collection[str],
    bootstrap_target: GeneratedExportBootstrapTarget | None = None,
) -> Path:
    """Stage one revision's complete non-export authority through a single boundary.

    The candidate holds the target as its modelo's only edition. An edition
    naming a predecessor states only the rows it changed, and pruning its
    siblings deletes the chain the rest come from, so such a target is staged as
    the complete edition the loader resolves for it, naming no predecessor. An
    edition whose named predecessor is absent is refused by that resolution.
    """
    if bootstrap_target is not None and (bootstrap_target.modelo, bootstrap_target.revision) != (modelo, revision):
        raise ValueError(
            f"bootstrap target {bootstrap_target.modelo}/{bootstrap_target.revision} cannot stage {modelo}/{revision}",
        )
    source_modelo_root = source_root / "modelos" / modelo
    edition = materialise_edition(source_modelo_root, revision)
    shutil.copytree(source_root / "legal", candidate_root / "legal")
    # The governed-fact provider directories are part of the authority a
    # candidate must validate against, not optional decoration: the registry
    # load resolves them by name, so a candidate root without them fails to
    # fingerprint rather than validating a narrower tree. Staged whole, like
    # `legal`, and staged by iteration so a directory added later is carried
    # without this list being the thing that remembered to mention it.
    for provider_directory in sorted(_FACT_PROVIDER_DIRECTORIES):
        source_provider = source_root / provider_directory
        if source_provider.is_dir():
            shutil.copytree(source_provider, candidate_root / provider_directory)
    stage_supplementary_orden_authority(
        source_root,
        candidate_root,
        modelos={modelo, *supporting_modelos},
    )
    staged_modelo_root = candidate_root / "modelos" / modelo
    shutil.copytree(
        source_modelo_root,
        staged_modelo_root,
        ignore=ignore_export_authority_directories,
    )
    for sibling in (staged_modelo_root / "revisions").iterdir():
        if sibling.name != revision:
            shutil.rmtree(sibling)
    if edition.inherits_from is not None:
        _write_complete_candidate_edition(staged_modelo_root / "revisions" / revision, edition)
    if bootstrap_target is not None and bootstrap_target.supersedes_layout_id is not None:
        retarget_bootstrap_construct_export_layout(
            staged_modelo_root,
            revision=revision,
            superseded_layout_id=bootstrap_target.supersedes_layout_id,
            generated_layout_id=bootstrap_target.layout_id,
            expected_references=bootstrap_target.superseded_construct_references,
        )
    for supporting_modelo in supporting_modelos:
        shutil.copytree(
            source_root / "modelos" / supporting_modelo,
            candidate_root / "modelos" / supporting_modelo,
        )
    return staged_modelo_root


def _write_complete_candidate_edition(revision_root: Path, edition: MaterialisedEdition) -> None:
    """Rewrite a staged delta edition's own directory as the complete edition it stands for.

    The directory stays a fragment tree because the generated layout is
    rendered into it. ``revision.toml`` keeps its own members as resolved, which
    drops the predecessor and any review claim the full copy does not carry, and
    the casilla section becomes one fragment holding every resolved row in the
    loader's order.
    """
    manifest = tomllib.loads((revision_root / "revision.toml").read_text("utf-8"))
    manifest_members = frozenset(manifest.get("revisions", {}).get(edition.revision_id, {}))
    revision_table = {key: value for key, value in edition.table.items() if key in manifest_members}
    rows = edition.table.get(_CASILLA_SECTION, ())
    if not isinstance(rows, list | tuple) or not all(isinstance(row, Mapping) for row in rows):
        raise ValueError(f"edition {edition.modelo_id}/{edition.revision_id} resolved no casilla rows")
    staged_rows = [dict(row) for row in rows]
    (revision_root / "revision.toml").write_bytes(
        _render_toml_bytes("revision.toml", {"revisions": {edition.revision_id: revision_table}}),
    )
    casillas_root = revision_root / _CASILLA_SECTION
    shutil.rmtree(casillas_root)
    casillas_root.mkdir()
    (casillas_root / _COMPLETE_CASILLA_FRAGMENT).write_bytes(
        _render_toml_bytes(
            f"{_CASILLA_SECTION}/{_COMPLETE_CASILLA_FRAGMENT}",
            {"revisions": {edition.revision_id: {_CASILLA_SECTION: staged_rows}}},
        ),
    )


def retarget_bootstrap_construct_export_layout(
    staged_modelo_root: Path,
    *,
    revision: str,
    superseded_layout_id: str,
    generated_layout_id: str,
    expected_references: int,
) -> None:
    """Retarget the explicitly pinned construct members in an isolated candidate."""
    replacements = 0
    updates: list[tuple[Path, dict[str, object]]] = []
    construct_root = staged_modelo_root / "revisions" / revision / "constructs"
    for path in sorted(construct_root.glob("*.toml")):
        payload = rtoml.load(path)
        revision_payload = payload.get("revisions", {}).get(revision, {})
        constructs = revision_payload.get("constructs", [])
        changed = False
        for construct in constructs:
            layout_ids = construct.get("export_layouts", [])
            occurrences = layout_ids.count(superseded_layout_id)
            if occurrences:
                construct["export_layouts"] = [
                    generated_layout_id if layout_id == superseded_layout_id else layout_id for layout_id in layout_ids
                ]
                replacements += occurrences
                changed = True
        if changed:
            updates.append((path, payload))
    if replacements != expected_references:
        raise ValueError(
            f"bootstrap superseded layout {superseded_layout_id!r} expected {expected_references} "
            f"construct reference(s), found {replacements}",
        )
    for path, payload in updates:
        path.write_text(rtoml.dumps(payload, pretty=True), encoding="utf-8", newline="")
