"""Mechanical receipts for lossless registry source transformations.

This module deliberately knows nothing about the registry compiler.  A caller
supplies the selected source closure and the already-loaded definitions; this
module records exact source bytes and compares their complete JSON projections.
Receipts therefore contain registry definitions only, never runtime filing or
taxpayer data.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, cast

from cadrumo.core.hashing import canonical_json_bytes, content_hash_hex, hash_file

JsonObject = dict[str, Any]


class JsonDumpable(Protocol):
    """The narrow Pydantic-compatible surface needed by a proof snapshot."""

    def model_dump(self, *, mode: str, exclude_defaults: bool, exclude_none: bool) -> JsonObject:
        """Return the full JSON projection without exclusions."""
        ...


@dataclass(frozen=True, slots=True)
class SourceFileFingerprint:
    """The exact bytes and relative identity of one closure member."""

    relative_path: str
    sha256: str
    byte_count: int


@dataclass(frozen=True, slots=True)
class SourceClosureFingerprint:
    """A path-sensitive digest over a complete selected source closure."""

    files: tuple[SourceFileFingerprint, ...]
    sha256: str

    def to_dict(self) -> JsonObject:
        """Return the canonical-JSON-compatible receipt payload."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DefinitionSnapshot:
    """One complete definition meaning and its stable digest."""

    definition: JsonObject
    locale_fields: JsonObject
    representation_metadata: JsonObject
    sha256: str

    def to_dict(self) -> JsonObject:
        """Return the canonical-JSON-compatible receipt payload."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TransformationProof:
    """Before/after snapshots and their first semantic divergence."""

    before: DefinitionSnapshot
    after: DefinitionSnapshot
    is_equivalent: bool
    first_mismatch: str | None

    def to_dict(self) -> JsonObject:
        """Return the canonical-JSON-compatible receipt payload."""
        return asdict(self)


def fingerprint_source_closure(root: Path, relative_paths: Iterable[str | Path]) -> SourceClosureFingerprint:
    """Fingerprint every explicitly selected regular file by path and raw bytes.

    Paths are sorted and canonicalised to POSIX spelling.  The aggregate digest
    consequently changes for an addition, deletion, rename, or byte edit.
    """
    resolved_root = root.resolve(strict=True)
    fingerprints: list[SourceFileFingerprint] = []
    seen: set[str] = set()
    for supplied in relative_paths:
        relative = PurePosixPath(Path(supplied).as_posix())
        if relative.is_absolute() or ".." in relative.parts or relative == PurePosixPath("."):
            raise ValueError(f"source closure path must be a relative file path: {supplied}")
        spelling = relative.as_posix()
        if spelling in seen:
            raise ValueError(f"source closure contains duplicate path {spelling!r}")
        seen.add(spelling)
        path = (resolved_root / Path(*relative.parts)).resolve(strict=True)
        if not path.is_relative_to(resolved_root) or not path.is_file():
            raise ValueError(f"source closure path is not a regular file below root: {spelling}")
        digest, byte_count = hash_file(path)
        fingerprints.append(SourceFileFingerprint(spelling, digest, byte_count))
    fingerprints.sort(key=lambda item: item.relative_path)
    files = tuple(fingerprints)
    payload = [asdict(item) for item in files]
    return SourceClosureFingerprint(files=files, sha256=content_hash_hex(payload))


def fingerprint_source_tree(root: Path) -> SourceClosureFingerprint:
    """Fingerprint a fresh recursive enumeration of every file below ``root``."""
    resolved_root = root.resolve(strict=True)
    paths: list[Path] = []
    for candidate in resolved_root.rglob("*"):
        if candidate.is_symlink():
            raise ValueError(f"source closure contains symbolic link: {candidate}")
        if candidate.is_file():
            paths.append(candidate.relative_to(resolved_root))
    return fingerprint_source_closure(resolved_root, paths)


def snapshot_definition(
    definition: JsonDumpable | Mapping[str, Any],
    *,
    locale_fields: Mapping[str, Any],
    representation_metadata: Mapping[str, Any] | None = None,
) -> DefinitionSnapshot:
    """Snapshot every dumped definition field plus caller-supplied locale data.

    No schema field, default, or null is excluded.  Representation-only facts
    (for example source file counts) must be passed explicitly by the caller;
    the proof never guesses them or silently removes definition fields.
    """
    if isinstance(definition, Mapping):
        dumped = cast(JsonObject, _json_projection(cast(Mapping[str, object], definition)))
    else:
        dumped = definition.model_dump(mode="json", exclude_defaults=False, exclude_none=False)
    if not isinstance(dumped, dict) or any(not isinstance(key, str) for key in dumped):
        raise TypeError("definition model_dump must return a string-keyed object")
    locales = dict(locale_fields)
    metadata = {} if representation_metadata is None else dict(representation_metadata)
    payload = {"definition": dumped, "locale_fields": locales, "representation_metadata": metadata}
    digest = content_hash_hex(payload)
    return DefinitionSnapshot(dumped, locales, metadata, digest)


def prove_transformation(before: DefinitionSnapshot, after: DefinitionSnapshot) -> TransformationProof:
    """Compare two complete snapshots and report the first canonical path that differs."""
    before_payload = _snapshot_payload(before)
    after_payload = _snapshot_payload(after)
    mismatch = _first_mismatch(before_payload, after_payload)
    return TransformationProof(before, after, mismatch is None, mismatch)


def write_transformation_receipt(path: Path, proof: TransformationProof) -> None:
    """Write a deterministic JSON proof receipt."""
    path.write_bytes(canonical_json_bytes(proof.to_dict()) + b"\n")


def _snapshot_payload(snapshot: DefinitionSnapshot) -> JsonObject:
    return {
        "definition": snapshot.definition,
        "locale_fields": snapshot.locale_fields,
        "representation_metadata": snapshot.representation_metadata,
    }


def _json_projection(value: object) -> object:
    """Project raw TOML values without conflating temporal scalars with strings."""
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        if any(not isinstance(key, str) for key in mapping):
            raise TypeError("raw definition mappings must have string keys")
        return {cast(str, key): _json_projection(child) for key, child in mapping.items()}
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        return [_json_projection(child) for child in sequence]
    if isinstance(value, datetime):
        return {"$toml_type": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"$toml_type": "date", "value": value.isoformat()}
    if isinstance(value, time):
        return {"$toml_type": "time", "value": value.isoformat()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"raw definition contains unsupported value type {type(value).__name__}")


def _first_mismatch(before: object, after: object, path: str = "$") -> str | None:
    if type(before) is not type(after):
        return path
    if isinstance(before, dict):
        before_mapping = cast(dict[str, object], before)
        after_mapping = cast(dict[str, object], after)
        for key in sorted(before_mapping.keys() | after_mapping.keys()):
            child = f"{path}.{key}"
            if key not in before_mapping or key not in after_mapping:
                return child
            mismatch = _first_mismatch(before_mapping[key], after_mapping[key], child)
            if mismatch is not None:
                return mismatch
        return None
    if isinstance(before, (list, tuple)):
        before_sequence = cast(list[object] | tuple[object, ...], before)
        after_sequence = cast(list[object] | tuple[object, ...], after)
        common = min(len(before_sequence), len(after_sequence))
        for index in range(common):
            mismatch = _first_mismatch(before_sequence[index], after_sequence[index], f"{path}[{index}]")
            if mismatch is not None:
                return mismatch
        return None if len(before_sequence) == len(after_sequence) else f"{path}[{common}]"
    return None if before == after else path


__all__ = [
    "DefinitionSnapshot",
    "JsonDumpable",
    "SourceClosureFingerprint",
    "SourceFileFingerprint",
    "TransformationProof",
    "fingerprint_source_closure",
    "fingerprint_source_tree",
    "prove_transformation",
    "snapshot_definition",
    "write_transformation_receipt",
]
