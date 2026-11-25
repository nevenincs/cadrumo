"""Keep the Modelo 100 calculation-completeness manifests covering the 0564 operands.

The 0564 formula reads every comunidad's official deduction boxes, so each of those
boxes enters the edition's calculation closure and must be listed in its
calculation-completeness manifest. The oldest edition lists them in a second
manifest fragment. A later edition inherits its manifest through one family
override whose removals and order are positions in the inherited list, so adding
entries to an earlier edition moves them: this module rewrites the ``casillas``
part of each later override so the edition's own list is what it was plus the
boxes its closure now needs, and leaves every other part of the override as it is.

An edition whose manifest already covers its closure and whose override still
applies is left untouched, so the module never rewrites a hand-authored override
without a reason.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.record_design_coverage import calculation_closure_casilla_ids
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.keyed_family_storage_delta import patch_family_sequences
from .autonomic_deduction_sum_dictionary import AutonomicSumExtractionError

__all__ = ["manifest_files"]

_FAMILY_LINE: Final = 'family = "completeness_manifest"'
_SEQUENCE_KEYS: Final = ("sequence_additions", "sequence_removals", "sequence_order")
_FRAGMENT: Final = "0002-deducciones-autonomicas-suma.toml"
_BARE_KEY: Final = re.compile(r"^[A-Za-z0-9_-]+$")

type Entry = dict[str, str]
type Patch = dict[str, dict[str, list[object]]]


def _key(entry: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(name), str(value)) for name, value in entry.items()))


def _entry(revision: ModeloRevision, casilla_id: str) -> Entry:
    casilla = next(casilla for casilla in revision.casillas if str(casilla.id) == casilla_id)
    entry = {"casilla_id": casilla_id, "number": casilla.number}
    if casilla.segmento is not None:
        entry["segmento"] = casilla.segmento
    return entry


def _missing(revision: ModeloRevision, listed: Sequence[Mapping[str, object]]) -> list[Entry]:
    """Closure casillas the list omits, in the edition's declaration order."""
    closure = calculation_closure_casilla_ids(revision, "100")
    present = {str(entry["casilla_id"]) for entry in listed}
    return [
        _entry(revision, str(casilla.id))
        for casilla in revision.casillas
        if casilla.id in closure and not casilla.internal_only and str(casilla.id) not in present
    ]


def _indices(context: str, values: Sequence[object]) -> tuple[int, ...]:
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        raise AutonomicSumExtractionError(f"{context}: a manifest removal or order is not a list of positions")
    return tuple(value for value in values if isinstance(value, int))


def _apply(context: str, inherited: Sequence[Mapping[str, object]], patch: Patch) -> list[Entry]:
    order = patch["sequence_order"].get("casillas")
    patched = patch_family_sequences(
        context,
        {"casillas": list(inherited)},
        {"casillas": tuple(patch["sequence_additions"].get("casillas", ()))},
        {"casillas": _indices(context, patch["sequence_removals"].get("casillas", []))},
        {} if order is None else {"casillas": _indices(context, order)},
    )
    if not isinstance(patched, Mapping):
        raise AutonomicSumExtractionError(f"{context}: the manifest patch did not yield a table")
    return [{str(name): str(value) for name, value in entry.items()} for entry in patched["casillas"]]


def _absent(entries: Sequence[Mapping[str, object]], keys: set[tuple[tuple[str, str], ...]]) -> list[int]:
    return [index for index, entry in enumerate(entries) if _key(entry) not in keys]


def _derive(inherited: Sequence[Mapping[str, object]], desired: Sequence[Entry]) -> dict[str, list[object]]:
    """The removals, additions and order that turn ``inherited`` into ``desired``."""
    removed = set(_absent(inherited, {_key(entry) for entry in desired}))
    added = [desired[index] for index in _absent(desired, {_key(entry) for entry in inherited})]
    patched = [_key(entry) for index, entry in enumerate(inherited) if index not in removed]
    patched += [_key(entry) for entry in added]
    return {
        "sequence_additions": list[object](added),
        "sequence_removals": list[object](sorted(removed)),
        "sequence_order": list[object](patched.index(_key(entry)) for entry in desired),
    }


@dataclass(slots=True)
class _Override:
    """The completeness-manifest override lines of one revision manifest."""

    path: Path
    lines: list[str]
    positions: dict[str, int]
    patch: Patch

    @classmethod
    def read(cls, path: Path) -> _Override:
        lines = path.read_text(encoding="utf-8").split("\n")
        start = lines.index(_FAMILY_LINE)
        positions: dict[str, int] = {}
        patch: Patch = {key: {} for key in _SEQUENCE_KEYS}
        for index in range(start + 1, len(lines)):
            line = lines[index]
            if not line.strip() or line.startswith("[["):
                break
            name = line.split("=", 1)[0].strip()
            if name in _SEQUENCE_KEYS:
                positions[name] = index
                patch[name] = dict(tomllib.loads(line)[name])
        return cls(path, lines, positions, patch)

    def rewritten(self, casillas: Mapping[str, list[object]]) -> str:
        lines = list(self.lines)
        anchor = max(self.positions.values(), default=self.lines.index(_FAMILY_LINE) + 2)
        insert_at = anchor + 1
        for name in _SEQUENCE_KEYS:
            table = {**self.patch[name]}
            table.pop("casillas", None)
            if casillas[name]:
                table = {"casillas": casillas[name], **table}
            rendered = f"{name} = {_render(table)}" if table else None
            if name in self.positions:
                lines[self.positions[name]] = rendered if rendered is not None else "\0"
            elif rendered is not None:
                lines.insert(insert_at, rendered)
                insert_at += 1
        return "\n".join(line for line in lines if line != "\0")


def _render(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, Mapping):
        items = ", ".join(
            f"{name if _BARE_KEY.match(str(name)) else _render(str(name))} = {_render(item)}"
            for name, item in value.items()
        )
        return "{ " + items + " }"
    if isinstance(value, list | tuple):
        return "[" + ", ".join(_render(item) for item in value) + "]"
    raise AutonomicSumExtractionError(f"cannot render manifest value {value!r}")


def _base_entries(path: Path, revision_id: str) -> list[Entry]:
    if not path.exists():
        return []
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    manifest = data["revisions"][revision_id]["completeness_manifest"]
    return [dict(entry) for entry in manifest.get("casillas", ())]


def _fragment_text(revision_id: str, entries: Sequence[Entry]) -> str:
    lines = [
        "# The official deduction boxes the casilla 0564 formula sums enter the calculation closure. Written by",
        "# `python -m dev.registry.authoring.autonomic_deduction_sum`; do not edit.",
    ]
    for entry in entries:
        lines += ["", f'[[revisions."{revision_id}".completeness_manifest.casillas]]']
        lines += [f"{name} = {_render(value)}" for name, value in entry.items()]
    return "\n".join(lines) + "\n"


def manifest_files(revisions: Sequence[ModeloRevision], revision_dir: Mapping[str, Path]) -> dict[Path, str]:
    """The manifest files whose text must change so each edition covers its closure.

    An empty text means the file must not exist.
    """
    oldest, later = revisions[0], revisions[1:]
    manifest_dir = revision_dir[str(oldest.id)] / "completeness_manifest"
    fragment = manifest_dir / _FRAGMENT
    authored = _base_entries(manifest_dir / "0001-declarations.toml", str(oldest.id))
    extra = _missing(oldest, authored)
    desired = authored + extra
    files: dict[Path, str] = {}
    fragment_text = _fragment_text(str(oldest.id), extra) if extra else ""
    if fragment_text != (fragment.read_text(encoding="utf-8") if fragment.exists() else ""):
        files[fragment] = fragment_text
    # The first later override was authored either against the list with the fragment
    # (after a previous write) or against the hand-authored list alone (before one).
    inherited = [authored + _base_entries(fragment, str(oldest.id)), authored]
    for revision in later:
        manifest = revision_dir[str(revision.id)] / "revision.toml"
        override = _Override.read(manifest)
        edition = _first_applying(str(manifest), inherited, override.patch)
        wanted = edition + _missing(revision, edition)
        if _applied(str(manifest), desired, override.patch) != wanted:
            files[manifest] = override.rewritten(_derive(desired, wanted))
        inherited, desired = [edition], wanted
    return files


def _applied(context: str, inherited: Sequence[Mapping[str, object]], patch: Patch) -> list[Entry] | None:
    try:
        return _apply(context, inherited, patch)
    except RegistryLoadError:
        return None


def _first_applying(context: str, candidates: Sequence[Sequence[Mapping[str, object]]], patch: Patch) -> list[Entry]:
    for inherited in candidates:
        if (edition := _applied(context, inherited, patch)) is not None:
            return edition
    raise AutonomicSumExtractionError(f"{context}: the manifest override applies to no inherited list; restore it")
