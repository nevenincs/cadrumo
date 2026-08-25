"""Strict persisted-fragment loader for reviewed semantic-map authority.

Semantic-map fragments are meaning-only authored inputs.  This loader owns
their on-disk TOML contract and compiles them in filename order into the
canonical :class:`SemanticMap` schema.  It never reads an export layout or
uses a neighbouring generated tree as an oracle.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

from cadrumo.core import FilingProducerKey, compile_filing_projection_ref, freeze_toml, read_toml
from cadrumo.core.directory_scan import iter_directory
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_semantics import ExportComputedKey, ExportDraftAttribute
from cadrumo.domain.calculations.registry.ids import (
    ModeloId,
    SourceRefId,
)

from ._semantic_map import SemanticMap, SemanticMapEntry, SemanticMapRecord, VariableEnvelopeSemantic

__all__ = [
    "SEMANTIC_MAP_FRAGMENT_SCHEMA_VERSION",
    "SemanticMapFragment",
    "load_semantic_map",
]


SEMANTIC_MAP_FRAGMENT_SCHEMA_VERSION: Final[int] = 1
_FRAGMENT_FILENAME = re.compile(r"^[0-9]{4}-(?P<fragment_id>[a-z0-9][a-z0-9-]*)$")
_RAW_ENTRIES_ADAPTER = TypeAdapter(tuple[dict[str, object], ...], config=ConfigDict(strict=True))


class _StrictModel(BaseModel):
    """Frozen authored boundary with unknown keys forbidden."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SemanticMapFragment(_StrictModel):
    """One reviewable fragment of one exact source-pinned semantic map."""

    schema_version: Literal[1]
    fragment_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    modelo: ModeloId
    design_epoch: str = Field(min_length=1)
    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: tuple[SemanticMapRecord, ...] = ()
    entries: tuple[SemanticMapEntry, ...] = ()
    variable_envelopes: tuple[VariableEnvelopeSemantic, ...] = ()

    @model_validator(mode="after")
    def _require_authored_meaning(self) -> SemanticMapFragment:
        if not self.records and not self.entries and not self.variable_envelopes:
            raise ValueError("semantic-map fragments must contain records, entries, or variable envelopes")
        return self


def load_semantic_map(fragment_directory: Path) -> SemanticMap:
    """Compile one strict semantic map from regular TOML fragments.

    Fragment order is the lexical filename order.  Filesystem enumeration
    order therefore cannot affect the compiled map, while every duplicate
    semantic identity is refused instead of merged or overwritten.
    """
    paths = _semantic_map_fragment_paths(fragment_directory)
    fragments = tuple(_load_fragment(path) for path in paths)
    return _compile_fragments(fragments)


def _semantic_map_fragment_paths(fragment_directory: Path) -> tuple[Path, ...]:
    if not fragment_directory.is_dir() or fragment_directory.is_symlink() or fragment_directory.is_junction():
        raise RegistryValidationError(
            f"semantic-map path must be a real directory: {fragment_directory}",
        )
    try:
        paths = tuple(sorted(iter_directory(fragment_directory, require_root=True), key=lambda path: path.name))
    except OSError as exc:
        raise RegistryValidationError(
            f"cannot inspect semantic-map directory: {fragment_directory}",
        ) from exc
    if not paths:
        raise RegistryValidationError(
            f"semantic-map directory contains no TOML fragments: {fragment_directory}",
        )
    invalid = tuple(
        path.name
        for path in paths
        if path.suffix.casefold() != ".toml" or path.is_symlink() or path.is_junction() or not path.is_file()
    )
    if invalid:
        raise RegistryValidationError(
            f"semantic-map directory accepts only regular TOML fragments; refusing entries: {invalid!r}",
        )
    return paths


def _load_fragment(path: Path) -> SemanticMapFragment:
    frozen = freeze_toml(
        read_toml(
            path,
            error_factory=lambda message: RegistryValidationError(message),
        ),
    )
    data: dict[str, object] = dict(frozen)
    try:
        raw_entries = _RAW_ENTRIES_ADAPTER.validate_python(data.get("entries", ()))
    except ValidationError as exc:
        raise RegistryValidationError(
            f"invalid semantic-map fragment {path.name!r}: entries must be an array of tables",
        ) from exc
    compiled_entries: list[object] = []
    for raw_entry in raw_entries:
        entry = dict(raw_entry)
        if "header_key" in entry:
            raise RegistryValidationError(
                f"invalid semantic-map fragment {path.name!r}: legacy header_key is not accepted; use producer_key",
            )
        raw_producer_key = entry.get("producer_key")
        if isinstance(raw_producer_key, str):
            try:
                entry["producer_key"] = FilingProducerKey(raw_producer_key)
            except ValueError as exc:
                raise RegistryValidationError(
                    f"invalid semantic-map fragment {path.name!r}: "
                    f"{raw_producer_key!r} is not a canonical producer_key",
                ) from exc
        raw_projection_ref = entry.get("projection_ref")
        if raw_projection_ref is not None:
            try:
                entry["projection_ref"] = compile_filing_projection_ref(raw_projection_ref)
            except (ValidationError, ValueError) as exc:
                raise RegistryValidationError(
                    f"invalid semantic-map fragment {path.name!r}: projection_ref is not canonical: {exc}",
                ) from exc
        for field_name, enum_type in (
            ("draft_attribute", ExportDraftAttribute),
            ("computed_key", ExportComputedKey),
        ):
            raw_value = entry.get(field_name)
            if isinstance(raw_value, str):
                try:
                    entry[field_name] = enum_type(raw_value)
                except ValueError as exc:
                    raise RegistryValidationError(
                        f"invalid semantic-map fragment {path.name!r}: {raw_value!r} is not a canonical {field_name}",
                    ) from exc
        compiled_entries.append(entry)
    data["entries"] = tuple(compiled_entries)
    try:
        fragment = SemanticMapFragment.model_validate(data)
    except ValidationError as exc:
        raise RegistryValidationError(
            f"invalid semantic-map fragment {path.name!r}: {exc}",
        ) from exc
    filename_match = _FRAGMENT_FILENAME.fullmatch(path.stem)
    if filename_match is None or filename_match.group("fragment_id") != fragment.fragment_id:
        raise RegistryValidationError(
            f"semantic-map fragment filename {path.name!r} must be NNNN-<fragment_id>.toml",
        )
    return fragment


def _compile_fragments(fragments: Iterable[SemanticMapFragment]) -> SemanticMap:
    ordered = tuple(fragments)
    if not ordered:
        raise RegistryValidationError("semantic map requires at least one fragment")

    duplicate_fragment_ids = _duplicates(fragment.fragment_id for fragment in ordered)
    if duplicate_fragment_ids:
        raise RegistryValidationError(
            f"semantic map contains duplicate fragment ids: {duplicate_fragment_ids!r}",
        )

    identity = (
        ordered[0].modelo,
        ordered[0].design_epoch,
        ordered[0].source_ref,
        ordered[0].source_sha256,
    )
    mismatched_fragments = tuple(
        fragment.fragment_id
        for fragment in ordered
        if (
            fragment.modelo,
            fragment.design_epoch,
            fragment.source_ref,
            fragment.source_sha256,
        )
        != identity
    )
    if mismatched_fragments:
        raise RegistryValidationError(
            f"semantic-map fragments have conflicting modelo/design/source identities: {mismatched_fragments!r}",
        )

    records = tuple(record for fragment in ordered for record in fragment.records)
    entries = tuple(entry for fragment in ordered for entry in fragment.entries)
    variable_envelopes = tuple(envelope for fragment in ordered for envelope in fragment.variable_envelopes)
    if not records or not entries:
        raise RegistryValidationError(
            "compiled semantic map requires at least one record and one entry",
        )
    _require_no_collisions(records, entries)
    return SemanticMap(
        modelo=ordered[0].modelo,
        design_epoch=ordered[0].design_epoch,
        source_ref=ordered[0].source_ref,
        source_sha256=ordered[0].source_sha256,
        records=tuple(
            sorted(
                records,
                key=lambda record: (
                    record.sheet,
                    record.record_identity,
                    str(record.export_record_id),
                ),
            ),
        ),
        entries=tuple(sorted(entries, key=_entry_key)),
        variable_envelopes=tuple(sorted(variable_envelopes, key=lambda envelope: envelope.record_identity)),
    )


def _require_no_collisions(
    records: tuple[SemanticMapRecord, ...],
    entries: tuple[SemanticMapEntry, ...],
) -> None:
    collisions = (
        (
            "exact record anchors",
            _duplicates((record.sheet, record.record_identity) for record in records),
        ),
        (
            "export record ids",
            _duplicates(str(record.export_record_id) for record in records),
        ),
        (
            "exact field anchors",
            _duplicates(
                (
                    entry.anchor.sheet,
                    entry.anchor.source_row,
                    entry.anchor.source_cell,
                    entry.anchor.ordinal,
                    entry.anchor.record_identity,
                )
                for entry in entries
            ),
        ),
        (
            "export field ids",
            _duplicates(str(entry.export_field_id) for entry in entries),
        ),
    )
    for subject, duplicates in collisions:
        if duplicates:
            raise RegistryValidationError(
                f"semantic-map fragments collide on {subject}: {duplicates!r}",
            )


def _duplicates[T](values: Iterable[T]) -> tuple[T, ...]:
    seen: set[T] = set()
    duplicates: set[T] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return tuple(sorted(duplicates, key=repr))


def _entry_key(entry: SemanticMapEntry) -> tuple[str, int, str, str, str, str]:
    return (
        entry.anchor.sheet,
        entry.anchor.source_row,
        entry.anchor.source_cell or "",
        entry.anchor.ordinal or "",
        entry.anchor.record_identity,
        str(entry.export_field_id),
    )
