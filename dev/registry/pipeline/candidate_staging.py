"""Shared exclusions for isolated generated-export candidate authority.

Candidates must contain the authored revision authority and no pre-existing
export authority. The registry loader accepts both the current ``export/``
fragment directory and the superseded ``export_layouts/`` form, so excluding
only one lets a legacy tree participate in validation of its replacement.
"""

from __future__ import annotations

import shutil
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

import rtoml

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.toml import parse_toml
from cadrumo.domain.calculations.registry.revision_contracts import DeclaredPredecessor

from ..compiler.edition_materialisation import MaterialisedEdition, materialise_edition
from ..compiler.loader import load_modelo_directory
from ..compiler.loader_grammar import REVISION_SECTION_FIELDS
from ._export_tree import render_toml_bytes

__all__ = [
    "GeneratedExportBootstrapTarget",
    "drop_cross_edition_evolutions",
    "generated_export_bootstrap_target",
    "ignore_export_authority_directories",
    "retarget_bootstrap_construct_export_layout",
    "stage_continuity_metadata",
    "stage_generated_export_candidate",
    "stage_supplementary_orden_authority",
    "write_complete_edition",
]


_EXPORT_AUTHORITY_DIRECTORY_NAMES: Final[frozenset[str]] = frozenset({"export", "export_layouts"})
_BOOTSTRAP_TARGETS_PATH: Final[Path] = Path(__file__).with_name("generated_export_bootstrap_targets.toml")
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
_EXPORT_AUTHORITY_MEMBERS: Final[frozenset[str]] = frozenset({"export", "export_layouts"})
_SOURCE_NATIVE_SECTIONS: Final[frozenset[str]] = frozenset({"casillas", "casilla_continuidad_evolutions"})


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
    payload = parse_toml(_BOOTSTRAP_TARGETS_PATH.read_text("utf-8"))
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
    reads_another_edition = any(
        isinstance(item.predecessor, DeclaredPredecessor)
        or item.casilla_storage_baseline is not None
        or item.family_storage_baseline is not None
        for item in definition.revisions.values()
    )
    for sibling_id in siblings:
        if reads_another_edition:
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
    if edition_requires_detachment(edition):
        write_complete_edition(staged_modelo_root / "revisions" / revision, edition)
    drop_cross_edition_evolutions(staged_modelo_root / "revisions" / revision)
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
    rows = edition.table.get(_CASILLA_SECTION, ())
    if not isinstance(rows, list | tuple) or not all(isinstance(row, Mapping) for row in rows):
        raise ValueError(f"edition {edition.modelo_id}/{edition.revision_id} resolved no casilla rows")
    staged_rows = [dict(row) for row in rows]
    (revision_root / "revision.toml").write_bytes(
        render_toml_bytes("revision.toml", {"revisions": {edition.revision_id: revision_table}}),
    )
    _write_complete_edition_section(revision_root, edition, _CASILLA_SECTION, staged_rows)
    for member, value in edition.table.items():
        if member in _EXPORT_AUTHORITY_MEMBERS or member == _CASILLA_SECTION:
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


def drop_cross_edition_evolutions(revision_root: Path) -> None:
    """Remove continuity evolutions from an isolated edition whose sibling endpoints were pruned."""
    evolutions = revision_root / "casilla_continuidad_evolutions"
    if evolutions.is_dir():
        shutil.rmtree(evolutions)


def edition_requires_detachment(edition: MaterialisedEdition) -> bool:
    """Whether an isolated edition must be written complete because it reaches pruned siblings."""
    return bool(_DETACHMENT_DECLARATIONS.intersection(edition.table))
