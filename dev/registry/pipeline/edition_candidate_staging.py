"""Stage complete editions and continuity witnesses for isolated candidates."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from cadrumo.core.toml import parse_toml
from cadrumo.domain.calculations.registry.revision_contracts import DeclaredPredecessor
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..compiler.edition_materialisation import MaterialisedEdition, materialise_edition
from ..compiler.export_fragment_grammar import EXPORT_SECTION_DIRECTORY_NAMES
from ..compiler.loader import load_modelo_directory
from ..compiler.loader_grammar import REVISION_SECTION_FIELDS
from .export_tree_serialization import render_toml_bytes

__all__ = [
    "drop_cross_edition_evolutions",
    "edition_requires_detachment",
    "stage_continuity_metadata",
    "write_complete_edition",
]

_CONTINUITY_SECTIONS: Final[tuple[str, ...]] = ("casillas", "casilla_continuidad_evolutions")
_PREDECESSOR_DECLARATION: Final = "predecessor"
_DETACHMENT_DECLARATIONS: Final[frozenset[str]] = frozenset(
    {_PREDECESSOR_DECLARATION, "casilla_storage_baseline", "family_storage_baseline"}
)
_RESOLVED_STORAGE_DECLARATIONS: Final[frozenset[str]] = frozenset(
    {
        _PREDECESSOR_DECLARATION,
        "reviewed_against",
        "casilla_storage_baseline",
        "casilla_overrides",
        "casilla_removals",
        "casilla_positions",
        "family_storage_baseline",
        "cleared_families",
        "scoped_families",
        "family_overrides",
        "family_removals",
        "family_positions",
        "restated_families",
    }
)
_CASILLA_SECTION: Final = "casillas"
_COMPLETE_EDITION_FRAGMENT: Final = "complete-edition.toml"
_SOURCE_NATIVE_SECTIONS: Final[frozenset[str]] = frozenset({"casillas", "casilla_continuidad_evolutions"})


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
    predecessor or a storage baseline, every sibling states its own rows and is
    copied as it stands. Once any edition names one, a sibling's own files may be
    only the rows it changed or stored against another edition, and the target
    it may read through is the one revision a witness must not hold. Every
    sibling is then staged as the complete edition the loader resolves for it,
    carrying no predecessor or storage declaration, so each loads on its own
    and none depends on a chain the witness cannot supply.
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
    reads_another_edition = _revisions_read_another_edition(definition)
    for sibling_id in siblings:
        _stage_sibling(
            source_modelo_root,
            metadata_modelo_root,
            revision=sibling_id,
            reads_another_edition=reads_another_edition,
        )
    return metadata_modelo_root


def _revisions_read_another_edition(definition: ModeloDefinition) -> bool:
    return any(
        isinstance(item.predecessor, DeclaredPredecessor)
        or item.casilla_storage_baseline is not None
        or item.family_storage_baseline is not None
        for item in definition.revisions.values()
    )


def _stage_sibling(
    source_modelo_root: Path,
    metadata_modelo_root: Path,
    *,
    revision: str,
    reads_another_edition: bool,
) -> None:
    if reads_another_edition:
        _stage_complete_sibling(source_modelo_root, metadata_modelo_root, revision=revision)
    else:
        _copy_sibling_sections(source_modelo_root, metadata_modelo_root, revision=revision)


def _copy_sibling_sections(source_modelo_root: Path, metadata_modelo_root: Path, *, revision: str) -> None:
    source_revision_root = source_modelo_root / "revisions" / revision
    target_revision_root = metadata_modelo_root / "revisions" / revision
    target_revision_root.mkdir(parents=True)
    shutil.copy2(source_revision_root / "revision.toml", target_revision_root / "revision.toml")
    for member in _CONTINUITY_SECTIONS:
        source_member = source_revision_root / member
        if source_member.is_dir():
            shutil.copytree(source_member, target_revision_root / member)


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
    manifest = parse_toml((source_modelo_root / "revisions" / revision / "revision.toml").read_text("utf-8"))
    manifest_members = frozenset(manifest.get("revisions", {}).get(revision, {}))
    manifest_table = {
        key: value
        for key, value in edition.table.items()
        if key in manifest_members and key not in _RESOLVED_STORAGE_DECLARATIONS
    }
    revisions_root = metadata_modelo_root / "revisions" / revision
    revisions_root.mkdir(parents=True, exist_ok=True)
    (revisions_root / "revision.toml").write_bytes(
        render_toml_bytes("revision.toml", {"revisions": {revision: manifest_table}}),
    )
    for section in _CONTINUITY_SECTIONS:
        value = edition.table.get(section)
        if value is None:
            continue
        section_root = revisions_root / section
        section_root.mkdir()
        (section_root / "complete-edition.toml").write_bytes(
            render_toml_bytes(
                f"{section}/complete-edition.toml",
                {"revisions": {revision: {section: value}}},
            ),
        )


def write_complete_edition(revision_root: Path, edition: MaterialisedEdition) -> None:
    """Rewrite a staged delta edition's own directory as the complete edition it stands for.

    The directory stays a fragment tree: the loader accepts no other revision
    layout, and the export tree a generated candidate renders into it, or a
    published edition already carries, stays where the loader resolves it.
    Export authority members are never rewritten. ``revision.toml`` keeps its
    own members as resolved, which
    drops the predecessor and any review claim the full copy does not carry, and
    the casilla section becomes one fragment holding every resolved row in the
    loader's order.

    A section the target inherited rather than restated is staged too, because
    the candidate names no predecessor and the chain those rows came from is
    pruned with its siblings. Modelo 390's later editions restate three of their
    ten application links and none of their filing schedules, so the candidate
    loaded a revision whose constructs referenced ids it no longer carried and
    validation refused them as unknown. A section already staged with exactly
    the rows the loader resolved is left untouched, so a target that restates
    its whole edition still stages as the plain copy it always was.
    """
    manifest = parse_toml((revision_root / "revision.toml").read_text("utf-8"))
    manifest_members = frozenset(manifest.get("revisions", {}).get(edition.revision_id, {}))
    revision_table = {
        key: value
        for key, value in edition.table.items()
        if key in manifest_members and key not in _RESOLVED_STORAGE_DECLARATIONS
    }
    staged_rows = _complete_casilla_rows(edition)
    (revision_root / "revision.toml").write_bytes(
        render_toml_bytes("revision.toml", {"revisions": {edition.revision_id: revision_table}}),
    )
    _write_complete_edition_section(revision_root, edition, _CASILLA_SECTION, staged_rows)
    _write_remaining_complete_sections(revision_root, edition)


def _complete_casilla_rows(edition: MaterialisedEdition) -> list[dict[str, object]]:
    rows = edition.table.get(_CASILLA_SECTION, ())
    if not isinstance(rows, list | tuple) or not all(isinstance(row, Mapping) for row in rows):
        raise ValueError(f"edition {edition.modelo_id}/{edition.revision_id} resolved no casilla rows")
    return [dict(row) for row in rows]


def _write_remaining_complete_sections(revision_root: Path, edition: MaterialisedEdition) -> None:
    for member, value in edition.table.items():
        if member in EXPORT_SECTION_DIRECTORY_NAMES or member == _CASILLA_SECTION:
            continue
        if member not in REVISION_SECTION_FIELDS:
            continue
        if _staged_section_rows(revision_root / member, edition.revision_id, member) == value:
            continue
        _write_complete_edition_section(revision_root, edition, member, value)


def _staged_section_rows(section_root: Path, revision_id: str, member: str) -> object:
    """Return what the staged fragments already declare for one section.

    ``None`` for an absent section, so a member present nowhere in the candidate
    can never compare equal to the rows the loader resolved for it.
    """
    if not section_root.is_dir():
        return None
    staged: list[object] = []
    for fragment in sorted(section_root.glob("*.toml")):
        payload = parse_toml(fragment.read_text("utf-8"))
        declared = payload.get("revisions", {}).get(revision_id, {}).get(member)
        if isinstance(declared, list):
            staged.extend(declared)
        elif declared is not None:
            return None
    return staged


def _write_complete_edition_section(
    revision_root: Path,
    edition: MaterialisedEdition,
    member: str,
    value: object,
) -> None:
    """Replace one staged section with the single fragment its edition resolves to."""
    member_root = revision_root / member
    if member_root.exists():
        shutil.rmtree(member_root)
    member_root.mkdir()
    # The loader names source-native and administrative sections by different
    # conventions and refuses a fragment spelled the other way, so the complete
    # fragment is spelled the way its own section requires.
    fragment_name = (
        _COMPLETE_EDITION_FRAGMENT if member in _SOURCE_NATIVE_SECTIONS else f"0001-{_COMPLETE_EDITION_FRAGMENT}"
    )
    (member_root / fragment_name).write_bytes(
        render_toml_bytes(
            f"{member}/{fragment_name}",
            {"revisions": {edition.revision_id: {member: value}}},
        ),
    )


def drop_cross_edition_evolutions(revision_root: Path) -> None:
    """Remove continuity evolutions from an isolated edition whose sibling endpoints were pruned."""
    evolutions = revision_root / "casilla_continuidad_evolutions"
    if evolutions.is_dir():
        shutil.rmtree(evolutions)


def edition_requires_detachment(edition: MaterialisedEdition) -> bool:
    """Whether an isolated edition must be written complete because it reaches pruned siblings.

    The inheritance edge is read from ``inherits_from``, never from the table: a
    materialised table carries no named predecessor by construction, so a test
    against its keys answered "no" for every delta edition and staged it thin --
    the staged tree then kept a ``predecessor`` pointing at a sibling the
    isolation had just pruned. The storage baselines are still read from the
    table, where they remain declared.
    """
    if edition.inherits_from is not None:
        return True
    return bool(_DETACHMENT_DECLARATIONS.intersection(edition.table))
