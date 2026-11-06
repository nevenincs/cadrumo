"""Digest stamps: what a family's outputs were produced from, and whether that still holds.

A stamp records, per input group, the digest of every input file's content as
the repository records it (line endings normalised by ``.gitattributes``), the
published authority's database digest, the family's declaration digest and the
sha256 of every output. Status compares those records with the files as they
stand now: modification times never enter.

A family whose outputs are committed in place keeps its stamp in the
development cache, which is per-checkout, ignored and relocatable, because a
source directory holds no ignored stamp beside its tracked outputs. A family
whose outputs are generated keeps its stamp inside its output root, so removing
the outputs removes the stamp with them.
"""

from __future__ import annotations

import enum
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.hashing import sha256_file

from ..cache_root import dev_cache_dir
from ..source_tree import normalised_contents, repository_files
from .location import WINDOW_INDEX, output_directory
from .registry import FixtureFamily

STAMP_FORMAT: Final[str] = "cadrumo-fixture-projection-stamp-v1"
STAMP_CACHE: Final[str] = "fixture-projections"
AUTHORITY_GROUP: Final[str] = "authority"

#: Per input group, each member's content digest.
InputRecord = dict[str, dict[str, str]]


class FixtureState(enum.StrEnum):
    """Where a family's outputs stand against their inputs."""

    FRESH = "fresh"
    STALE = "stale"
    UNSTAMPED = "unstamped"
    MISSING = "missing"
    CHECK_ONLY = "check-only"


@dataclass(frozen=True, slots=True)
class FamilyStatus:
    """A family's state and, when it is not fresh, what made it so."""

    name: str
    state: FixtureState
    reasons: tuple[str, ...] = ()


class InputDigests:
    """Content digests of repository files, each read at most once per instance."""

    def __init__(self, root: Path) -> None:
        """Read files below ``root``, the repository whose ignore and attribute rules apply."""
        self._root = root
        self._groups: dict[tuple[str, ...], dict[str, str]] = {}

    def group(self, paths: Sequence[str]) -> dict[str, str]:
        """Return each repository file under ``paths`` with the digest of its normalised content.

        Raises:
            FileNotFoundError: When a path in ``paths`` does not exist.
        """
        key = tuple(paths)
        cached = self._groups.get(key)
        if cached is None:
            files = repository_files(self._root, under=paths, must_exist=True)
            cached = {
                relative: hashlib.sha256(content).hexdigest()
                for relative, content in normalised_contents(self._root, files)
            }
            self._groups[key] = cached
        return cached


def declaration_digest(family: FixtureFamily) -> str:
    """Name the family's declaration, so a changed command, input or output set is a changed producer."""
    return hashlib.sha256(json.dumps(asdict(family), sort_keys=True).encode()).hexdigest()


def family_inputs(family: FixtureFamily, digests: InputDigests, authority: Mapping[str, str]) -> InputRecord:
    """Every input digest of ``family``, by group, with the authority identity as its own group."""
    record = {group.label: digests.group(group.paths) for group in family.inputs}
    record[AUTHORITY_GROUP] = dict(authority)
    return record


def input_digest(inputs: InputRecord) -> str:
    """Fold every group's member digests into one digest."""
    digest = hashlib.sha256()
    for label in sorted(inputs):
        for member, value in sorted(inputs[label].items()):
            digest.update(f"{label}\0{member}\0{value}\n".encode())
    return digest.hexdigest()


def output_paths(family: FixtureFamily, root: Path) -> tuple[Path, ...]:
    """Every file under the family's output root that its output patterns name, sorted.

    The family's stamp and the window index beside the outputs are records of them, never outputs.
    """
    if family.output_root is None:
        return ()
    output_root = output_directory(family.output_root, root)
    records = {output_root / _stamp_name(family), output_root / WINDOW_INDEX}
    found = {
        path
        for pattern in family.outputs
        for path in output_root.glob(pattern)
        if path.is_file() and path not in records
    }
    return tuple(sorted(found))


def output_digests(family: FixtureFamily, root: Path) -> dict[str, str]:
    """The sha256 of every output, keyed by its path relative to the output root."""
    if family.output_root is None:
        return {}
    output_root = output_directory(family.output_root, root)
    return {path.relative_to(output_root).as_posix(): sha256_file(path) for path in output_paths(family, root)}


def _stamp_name(family: FixtureFamily) -> str:
    return f".{family.name}.fixture-stamp.json"


def stamp_path(family: FixtureFamily, root: Path, *, cache_directory: Path | None = None) -> Path:
    """Where ``family``'s stamp lives: the development cache when committed, else beside the outputs."""
    if family.committed or family.output_root is None:
        directory = cache_directory if cache_directory is not None else dev_cache_dir(STAMP_CACHE)
        return directory / f"{family.name}.json"
    return output_directory(family.output_root, root) / _stamp_name(family)


def write_stamp(family: FixtureFamily, root: Path, inputs: InputRecord, *, cache_directory: Path | None = None) -> Path:
    """Record that the family's outputs on disk now were produced from ``inputs``."""
    document = {
        "format": STAMP_FORMAT,
        "family": family.name,
        "producer_version": declaration_digest(family),
        "input_digest": input_digest(inputs),
        "inputs": inputs,
        "outputs": output_digests(family, root),
    }
    path = stamp_path(family, root, cache_directory=cache_directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(path.name + ".partial")
    staged.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    staged.replace(path)
    return path


def _changed_members(label: str, recorded: Mapping[str, str], current: Mapping[str, str]) -> list[str]:
    changes = [
        f"{label}: {member} changed"
        for member in sorted(recorded.keys() & current.keys())
        if recorded[member] != current[member]
    ]
    changes += [f"{label}: {member} added" for member in sorted(current.keys() - recorded.keys())]
    changes += [f"{label}: {member} removed" for member in sorted(recorded.keys() - current.keys())]
    return changes


def family_status(
    family: FixtureFamily, root: Path, inputs: InputRecord, *, cache_directory: Path | None = None
) -> FamilyStatus:
    """Compare the family's stamp with ``inputs`` and the outputs on disk."""
    if family.producer is None:
        return FamilyStatus(family.name, FixtureState.CHECK_ONLY)
    path = stamp_path(family, root, cache_directory=cache_directory)
    outputs = output_digests(family, root)
    if not outputs:
        return FamilyStatus(family.name, FixtureState.MISSING, ("no outputs",))
    # Outputs with no usable stamp exist but are of unknown provenance: not
    # missing, and not fresh until a seed produces or adopts them.
    try:
        stamp = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return FamilyStatus(family.name, FixtureState.UNSTAMPED, ("no stamp",))
    except (OSError, ValueError) as exc:
        return FamilyStatus(family.name, FixtureState.UNSTAMPED, (f"unreadable stamp: {type(exc).__name__}",))
    if not isinstance(stamp, dict) or stamp.get("format") != STAMP_FORMAT or stamp.get("family") != family.name:
        return FamilyStatus(family.name, FixtureState.UNSTAMPED, ("stamp of another format or family",))
    reasons: list[str] = []
    if stamp.get("producer_version") != declaration_digest(family):
        reasons.append("declaration changed")
    recorded_inputs = stamp.get("inputs", {})
    for label in sorted(recorded_inputs.keys() | inputs.keys()):
        reasons += _changed_members(label, recorded_inputs.get(label, {}), inputs.get(label, {}))
    reasons += _changed_members("output", stamp.get("outputs", {}), outputs)
    if reasons:
        return FamilyStatus(family.name, FixtureState.STALE, tuple(reasons))
    return FamilyStatus(family.name, FixtureState.FRESH)
