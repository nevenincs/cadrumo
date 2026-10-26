"""Collapse keyed declaration families for any modelo candidate.

Each keyed family an edition states is rewritten as the storage delta the
loader applies against the edition's family baseline, and the candidate is
accepted only when every edition hydrates exactly as the source did. Four rules
decide what the delta holds:

- **The baseline is the one the authored tree names.** A named predecessor,
  then a family storage baseline, decide it as the loader does. A casilla
  storage baseline the author declared alone is a decision about casillas and
  leaves the families as authored; only an edition that declared no ancestry at
  all takes the baseline the casilla pass has just planned for it.
- **A per-edition sequence is stated, not overridden.** An export layout's
  records transcribe one official record design. A layout whose records differ
  from its baseline stays stated whole in the edition rather than folded into
  an override that removes the baseline's records and re-adds them; an existing
  override of that kind is turned back into the stated layout.
- **A period is never removed twice.** The loader withholds a period-scoped
  member the edition does not file on every edge, so no removal is written for
  one, and an existing removal of one is dropped as redundant.
- **Order is restored with the fewest positions.** The members already in the
  target order are left in place and every other one is moved once, so the
  family's positions are the minimal set for the loader's sequential moves, not
  a greedy set appended to positions already declared.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Final

import tomlkit

from cadrumo.core.toml import render_toml
from cadrumo.domain.calculations.registry.keyed_families import (
    KeyedFamilySpec,
    family_source_default_fields,
)

__all__ = [
    "STATED_WHOLE_SEQUENCES",
    "restates_stated_whole_sequence",
]

_REPRESENTATION_FIELDS = {
    "inherited_from",
    "casillas",
    "predecessor",
    "casilla_source_refs",
    "casilla_storage_baseline",
    "casilla_overrides",
    "casilla_removals",
    "casilla_positions",
    "lineage_attestations",
    "family_storage_baseline",
    "family_overrides",
    "family_removals",
    "family_positions",
    "cleared_families",
    "scoped_families",
    "restated_families",
    # An edition-level ``<family>_source_refs`` only defaults its members'
    # ``source_refs``; the hydrated members carry the resolved references, so
    # lifting a shared run into the default changes representation, not meaning.
    *(field for _section, field in family_source_default_fields(include_casillas=True)),
}

#: Per family, the member sequence each edition states for itself. An export
#: layout's records are one official record design transcribed; an edition
#: whose records differ states its layout, because an override could only
#: remove the baseline's records and re-add every record of its own.
STATED_WHOLE_SEQUENCES: Final[Mapping[str, str]] = MappingProxyType({"export_layouts": "records"})

_FRAGMENT_NAME: Final = "0001-declarations.toml"


def restates_stated_whole_sequence(section: str, operation: Mapping[str, object]) -> bool:
    """Whether a family override rewrites a sequence its family states whole per edition."""
    sequence = STATED_WHOLE_SEQUENCES.get(section)
    return sequence is not None and _contains_whole_sequence(_operation_paths(operation), sequence)


def _operation_paths(operation: Mapping[str, object]) -> list[str]:
    paths: list[str] = []
    _extend_mapping_paths(paths, operation.get("fields"))
    _extend_value_paths(paths, operation.get("removed_fields"))
    for key in ("sequence_additions", "sequence_removals", "sequence_order"):
        _extend_mapping_paths(paths, operation.get(key))
    return paths


def _extend_mapping_paths(paths: list[str], value: object) -> None:
    if isinstance(value, Mapping):
        paths.extend(str(path) for path in value)


def _extend_value_paths(paths: list[str], value: object) -> None:
    if isinstance(value, list | tuple):
        paths.extend(str(path) for path in value)


def _contains_whole_sequence(paths: Sequence[str], sequence: str) -> bool:
    return any(path == sequence or path.startswith(f"{sequence}.") for path in paths)


def _digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _effective(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _effective(item) for key, item in value.items() if key not in _REPRESENTATION_FIELDS}
    if isinstance(value, list | tuple):
        return [_effective(item) for item in value]
    return value


def _plain(value: object) -> object:
    """A materialised value as plain dicts and lists, the shapes TOML writers accept."""
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    return value


def _payload_field_count(value: object) -> int:
    if isinstance(value, Mapping):
        return sum(_payload_field_count(item) for item in value.values())
    if isinstance(value, list | tuple):
        return sum(_payload_field_count(item) for item in value)
    return 1


def _remove_members(
    revision_dir: Path,
    revision_id: str,
    family: str,
    keep: set[str],
    identity: str,
    *,
    singleton: bool,
) -> None:
    section_dir = revision_dir / family
    if not section_dir.is_dir():
        return
    if singleton and not keep:
        _remove_singleton_section(section_dir)
        return
    for path in sorted(section_dir.glob("*.toml")):
        _rewrite_family_fragment(path, revision_id, family, keep, identity)
    _remove_empty_section(section_dir)


def _remove_singleton_section(section_dir: Path) -> None:
    for path in section_dir.glob("*.toml"):
        path.unlink()
    section_dir.rmdir()


def _rewrite_family_fragment(path: Path, revision_id: str, family: str, keep: set[str], identity: str) -> None:
    document = tomlkit.parse(path.read_text(encoding="utf-8"))
    members = document["revisions"][revision_id][family]
    retained = [member for member in members if str(member.get(identity)) in keep]
    if not retained:
        path.unlink()
        return
    members.clear()
    members.extend(retained)
    path.write_text(tomlkit.dumps(document), encoding="utf-8", newline="\n")


def _remove_empty_section(section_dir: Path) -> None:
    if section_dir.is_dir() and not any(section_dir.iterdir()):
        section_dir.rmdir()


def _state_members(revision_dir: Path, revision_id: str, family: str, members: Sequence[Mapping[str, object]]) -> None:
    """State ``members`` in the family's fragment, appending to the one already authored."""
    section_dir = revision_dir / family
    fragments = sorted(section_dir.glob("*.toml")) if section_dir.is_dir() else []
    if not fragments:
        section_dir.mkdir(exist_ok=True)
        (section_dir / _FRAGMENT_NAME).write_text(
            render_toml({"revisions": {revision_id: {family: [_plain(member) for member in members]}}}),
            encoding="utf-8",
            newline="\n",
        )
        return
    path = fragments[0]
    document = tomlkit.parse(path.read_text(encoding="utf-8"))
    stated = document["revisions"][revision_id][family]
    for member in members:
        stated.append(tomlkit.item(_plain(member)))
    path.write_text(tomlkit.dumps(document), encoding="utf-8", newline="\n")


def _table(value: Mapping[str, object]) -> object:
    table = tomlkit.inline_table()
    for key, item in value.items():
        table[key] = item
    return table


def _authored_member_order(revision_dir: Path, revision_id: str, family: str, identity: str) -> list[str]:
    """Return identities physically stated in one family directory, in the order the loader reads them."""
    identities: list[str] = []
    for path in sorted((revision_dir / family).glob("*.toml")):
        document = tomlkit.parse(path.read_text(encoding="utf-8"))
        value = document["revisions"][revision_id][family]
        members = (value,) if isinstance(value, Mapping) else value
        identities.extend(str(member[identity]) for member in members)
    return identities


def _restated_sections(revision: Mapping[str, object]) -> set[str]:
    """Return the keyed families one edition restates in full rather than inherits."""
    declared = revision.get("restated_families") or ()
    if not isinstance(declared, list | tuple):
        return set()
    return {str(entry["family"]) for entry in declared if isinstance(entry, Mapping) and "family" in entry}


def _drop_restatement(revision: MutableMapping[str, object], section: str) -> None:
    """Remove one family's restatement, and the declaration once it restates nothing."""
    declared = revision["restated_families"]
    if not isinstance(declared, list):
        raise RuntimeError(f"restated_families is not an array while lifting {section!r}")
    retained = [entry for entry in declared if not (isinstance(entry, Mapping) and entry.get("family") == section)]
    if retained:
        declared.clear()
        declared.extend(retained)
    else:
        del revision["restated_families"]


def _family_baseline(authored: Mapping[str, object], planned: Mapping[str, object]) -> str | None:
    """The edition a revision's keyed families are stored against, or ``None`` when they stay as authored.

    The authored tree decides, in the loader's order: a named predecessor, then
    a family storage baseline. A casilla storage baseline declared alone is the
    author's decision about casillas, and the families stay as authored. Only an
    edition that declared no ancestry at all takes the one the casilla pass has
    just planned for it.
    """
    for key in ("predecessor", "family_storage_baseline"):
        value = authored.get(key)
        if isinstance(value, str):
            return value
    if isinstance(authored.get("casilla_storage_baseline"), str):
        return None
    for key in ("predecessor", "family_storage_baseline", "casilla_storage_baseline"):
        value = planned.get(key)
        if isinstance(value, str):
            return value
    return None


def _family_members(table: Mapping[str, object], spec: KeyedFamilySpec) -> tuple[Mapping[str, object], ...]:
    raw = table.get(spec.section)
    candidates: tuple[object, ...] = (raw,) if spec.singleton else tuple(raw) if isinstance(raw, list | tuple) else ()
    members: list[Mapping[str, object]] = []
    for item in candidates:
        if isinstance(item, Mapping):
            members.append({str(key): value for key, value in item.items()})
    return tuple(members)


def _selector_id(operation: object) -> str | None:
    selector = operation.get("selector") if isinstance(operation, Mapping) else None
    member = selector.get("id") if isinstance(selector, Mapping) else None
    return None if member is None else str(member)


def _replace_operations(operations: list[object], retained: Sequence[object]) -> bool:
    """Keep only ``retained`` in ``operations``; return whether anything was dropped."""
    if len(retained) == len(operations):
        return False
    kept = list(retained)
    operations.clear()
    operations.extend(kept)
    return True
