"""Canonical TOML serialization and reviewable export-tree fragment rendering."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final, Literal, cast

import rtoml

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import RevisionId
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition

SERIALIZER_CONVENTION: Final[Literal["rtoml-pretty-v1"]] = "rtoml-pretty-v1"

_SAFE_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"^[^/\\\x00-\x1f]+$")

_SLUG_RE: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")

_MAX_FRAGMENT_LINES: Final[int] = 1_399

_MAX_FRAGMENT_LINE_CHARS: Final[int] = 519

#: Zero-padded width this renderer gives an administrative fragment prefix. It is the

#: single place the width is stated: the same value formats the prefix and checks that

#: the formatting did not overflow, so the guard cannot drift from the format it guards.

_FRAGMENT_PREFIX_DIGITS: Final[int] = 4


def render_tree_files(
    *,
    revision_id: RevisionId,
    layout: ExportLayoutDefinition,
) -> tuple[tuple[str, bytes], ...]:
    """Build the ordered metadata and reviewable record-fragment payloads."""
    layout_payload = layout.model_dump(mode="json", exclude_none=True)
    records = tuple(layout_payload.pop("records"))
    metadata_payload = {"revisions": {str(revision_id): {"export_layouts": [layout_payload]}}}
    metadata_bytes = render_toml_bytes("0000-export-layout.toml", metadata_payload)
    _require_reviewable_fragment("0000-export-layout.toml", metadata_bytes)
    rendered_files = [("0000-export-layout.toml", metadata_bytes)]
    planned_paths = {"0000-export-layout.toml"}
    # One prefix per emitted fragment, not per record. A partitioned record occupies
    # several consecutive prefixes: the loader admits one fragment per administrative
    # prefix, and merges records in prefix order, so the prefix sequence is what makes
    # field order survive the round trip.
    prefix = 0
    for record in records:
        record_id = record.get("id")
        if not isinstance(record_id, str):
            raise RegistryValidationError("validated generated export record has no string id")
        record_parts = _render_record_parts(revision_id=revision_id, layout_id=layout.id, record=record)
        for fragment_bytes in record_parts:
            prefix += 1
            relative_path = _record_relative_path(prefix, record_id)
            if relative_path in planned_paths:
                raise RegistryValidationError(f"generated export path collision at {relative_path!r}")
            planned_paths.add(relative_path)
            rendered_files.append((relative_path, fragment_bytes))
    return tuple(rendered_files)


def _render_record_parts(
    *,
    revision_id: RevisionId,
    layout_id: object,
    record: Mapping[str, object],
) -> tuple[bytes, ...]:
    fields = _require_record_fields(record)
    record_without_fields = {key: value for key, value in record.items() if key != "fields"}
    rendered_parts: list[bytes] = []
    current_fields: list[Mapping[str, object]] = []
    for field in fields:
        current_fields, completed_part = _append_reviewable_record_field(
            revision_id=revision_id,
            layout_id=layout_id,
            record_without_fields=record_without_fields,
            current_fields=current_fields,
            field=field,
        )
        if completed_part is not None:
            rendered_parts.append(completed_part)
    rendered_parts.append(
        _render_record_fragment(
            revision_id=revision_id,
            layout_id=layout_id,
            record={**record_without_fields, "fields": current_fields},
        ),
    )
    return tuple(rendered_parts)


def _require_record_fields(record: Mapping[str, object]) -> list[Mapping[str, object]]:
    """Require a nonempty validated record field table and preserve its order."""
    raw_fields = record.get("fields")
    if not isinstance(raw_fields, list) or not raw_fields:
        raise RegistryValidationError(f"validated generated export record {record.get('id')!r} has no fields")
    fields: list[Mapping[str, object]] = []
    for field in cast(list[object], raw_fields):
        if not isinstance(field, Mapping):
            raise RegistryValidationError(
                f"validated generated export record {record.get('id')!r} contains a non-table field",
            )
        fields.append(cast(Mapping[str, object], field))
    return fields


def _append_reviewable_record_field(
    *,
    revision_id: RevisionId,
    layout_id: object,
    record_without_fields: Mapping[str, object],
    current_fields: list[Mapping[str, object]],
    field: Mapping[str, object],
) -> tuple[list[Mapping[str, object]], bytes | None]:
    """Append one field or close the current reviewable record fragment."""
    candidate_fields: list[Mapping[str, object]] = [*current_fields, field]
    candidate = _render_record_fragment(
        revision_id=revision_id,
        layout_id=layout_id,
        record={**record_without_fields, "fields": candidate_fields},
    )
    if _is_reviewable_fragment(candidate):
        return candidate_fields, None
    if not current_fields:
        _raise_field_exceeds_reviewability(field)
    completed_part = _render_record_fragment(
        revision_id=revision_id,
        layout_id=layout_id,
        record={**record_without_fields, "fields": current_fields},
    )
    next_fields = [field]
    candidate = _render_record_fragment(
        revision_id=revision_id,
        layout_id=layout_id,
        record={**record_without_fields, "fields": next_fields},
    )
    if not _is_reviewable_fragment(candidate):
        _raise_field_exceeds_reviewability(field)
    return next_fields, completed_part


def _raise_field_exceeds_reviewability(field: Mapping[str, object]) -> None:
    field_id = field.get("id")
    raise RegistryValidationError(
        f"generated export field {field_id!r} cannot fit the repository TOML reviewability baseline",
    )


def _render_record_fragment(
    *,
    revision_id: RevisionId,
    layout_id: object,
    record: Mapping[str, object],
) -> bytes:
    return render_toml_bytes(
        str(record.get("id", "record")),
        {
            "revisions": {
                str(revision_id): {
                    "export_layouts": [
                        {
                            "id": layout_id,
                            "records": [record],
                        },
                    ],
                },
            },
        },
    )


def render_toml_bytes(relative_path: str, payload: Mapping[str, object]) -> bytes:
    """Serialize one TOML payload with stable ordering and safe refusal details."""
    try:
        rendered = rtoml.dumps(_order_toml_values_before_tables(payload), pretty=True, none_value=None)
    except (TypeError, ValueError) as exc:
        # rtoml raises TomlSerializationError (a ValueError subclass) whose sole
        # ``args[0]`` bakes the offending value's own ``repr`` into the message,
        # with no structured field that omits it -- measured:
        # ``rtoml.dumps({"bad": Foo()})`` produces "<Foo object at 0x...> (Foo)
        # is not serializable to TOML". Unlike ``json.dumps``'s purely
        # positional "Object of type X is not JSON serializable", there is no
        # accessor here that separates the offending value from the message, so
        # this refusal names only the exception's type, never its rendered text.
        raise RegistryValidationError(
            f"cannot serialize generated export TOML {relative_path!r}: {type(exc).__name__} refused the payload",
        ) from exc
    return rendered.encode("utf-8")


def _order_toml_values_before_tables(value: object) -> object:
    """Recursively order scalars before TOML tables and arrays of tables.

    The generated M303 declaration introduces a nested prefix-field table.
    ``rtoml`` correctly requires every scalar in that declaration to be
    emitted before the nested table, so preserve values while presenting its
    serializer a valid TOML order.
    """
    if isinstance(value, Mapping):
        # Partitioned in ONE pass: the shape test was evaluated twice per item,
        # once to reject it from the scalars and again to admit it to the
        # tables, and this recursion reaches every node of every generated
        # tree -- 8.9M calls for one modelo.
        values: list[tuple[str, object]] = []
        tables: list[tuple[str, object]] = []
        for key, item in value.items():
            ordered = _order_toml_values_before_tables(item)
            (tables if _toml_table_like(ordered) else values).append((str(key), ordered))
        return dict((*values, *tables))
    if isinstance(value, list):
        return [_order_toml_values_before_tables(item) for item in value]
    if isinstance(value, tuple):
        return [_order_toml_values_before_tables(item) for item in value]
    return value


def _toml_table_like(value: object) -> bool:
    """Return whether TOML must emit ``value`` as a table-shaped value."""
    if isinstance(value, Mapping):
        return True
    return isinstance(value, list) and any(isinstance(item, Mapping) for item in value)


def _is_reviewable_fragment(payload: bytes) -> bool:
    lines = payload.decode("utf-8").splitlines()
    return (
        len(lines) <= _MAX_FRAGMENT_LINES and max((len(line) for line in lines), default=0) <= _MAX_FRAGMENT_LINE_CHARS
    )


def _require_reviewable_fragment(relative_path: str, payload: bytes) -> None:
    if not _is_reviewable_fragment(payload):
        raise RegistryValidationError(
            f"generated export TOML {relative_path!r} exceeds the repository reviewability baseline",
        )


def _record_relative_path(prefix: int, record_id: object) -> str:
    """Return the fragment filename for one rendered record part.

    The administrative prefix carries the whole ordering, so the filename states no
    second one: a partitioned record appears as consecutive prefixes sharing a slug.
    """
    raw_record_id = str(record_id)
    require_safe_identifier(raw_record_id, subject="export record id")
    slug = _SLUG_RE.sub("-", raw_record_id.casefold()).strip("-")
    if not slug:
        raise RegistryValidationError(f"export record id {raw_record_id!r} cannot form a stable output slug")
    rendered_prefix = f"{prefix:0{_FRAGMENT_PREFIX_DIGITS}d}"
    if len(rendered_prefix) != _FRAGMENT_PREFIX_DIGITS:
        raise RegistryValidationError(
            f"generated export record {raw_record_id!r} needs fragment prefix {prefix}, which overflows the "
            f"{_FRAGMENT_PREFIX_DIGITS}-digit prefix width; an overflowed prefix does not sort late, it stops "
            "being a readable fragment name",
        )
    return f"{rendered_prefix}-record-{slug}.toml"


def require_safe_identifier(value: str, *, subject: str) -> None:
    """Refuse identifiers unsafe for generated export paths."""
    if not value or value in {".", ".."} or ".." in value or _SAFE_IDENTIFIER_RE.fullmatch(value) is None:
        raise RegistryValidationError(f"{subject} is unsafe for generated export output: {value!r}")
