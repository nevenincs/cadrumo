"""Render a fully materialised edition as exact, representation-blind proof bytes."""

from __future__ import annotations

import datetime
import json
from collections.abc import Mapping

from cadrumo.domain.calculations.registry.keyed_families import (
    CANONICAL_FAMILY_SPECS,
    family_source_default_fields,
    inline_family_source_default,
)

from . import edition_delta_drop_scope as _edition_delta_drop_scope
from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_fields as _edition_delta_fields
from . import edition_delta_payload as _edition_delta_payload
from . import edition_delta_source as _edition_delta_source
from .edition_delta_proof_source import read_staged_edition


def member_identities(source: _edition_delta_source._EditionSource) -> Mapping[str, tuple[str, ...]]:
    """Return materialised member identities in order, including every droppable family."""
    identities = {
        _edition_delta_fields._CASILLAS: tuple(
            f"{_edition_delta_source._row_id(row)}|{_edition_delta_source._lineage(row)}" for row in source.rows
        )
    }
    sections = set(_edition_delta_fields._REFERENCE_SECTIONS.values()) | {
        family.section for family in _edition_delta_drop_scope._DROPPABLE_FAMILIES
    }
    for section in sorted(sections - {_edition_delta_fields._CASILLAS}):
        identities[section] = tuple(
            str(member.get("id")) for member in _edition_delta_source._family_members(source.table, section)
        )
    return identities


def comparable(value: object, *, revision_id: str, path: str) -> object:
    """Render one exact JSON-comparable value or refuse the unsupported type."""
    if value is None or isinstance(value, str | bool | int | float):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): comparable(item, revision_id=revision_id, path=f"{path}.{key}") for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [comparable(item, revision_id=revision_id, path=f"{path}[{index}]") for index, item in enumerate(value)]
    if type(value) is datetime.date:
        return {_edition_delta_fields._DATE_TAG: value.isoformat()}
    raise _edition_delta_errors.MigrationRefusedError(
        f"edition {revision_id!r}: the value at {path} is a {type(value).__name__}, which the chain proof cannot "
        "compare; the proof is byte identity and refuses a type it has no exact rendering for",
    )


def _family_defaults_inlined(table: Mapping[str, object]) -> dict[str, object]:
    result = dict(table)
    for section, default_key in family_source_default_fields():
        raw_members = table.get(section)
        if not isinstance(raw_members, list | tuple):
            continue
        result[section] = [
            inline_family_source_default(raw_member, table, default_key)
            if isinstance(raw_member, Mapping)
            else raw_member
            for raw_member in raw_members
        ]
    return result


def _restore_attested_claims(source: _edition_delta_source._EditionSource, rows: list[dict[str, object]]) -> None:
    raw_attestations = source.manifest.get("lineage_attestations", ())
    if not isinstance(raw_attestations, list | tuple):
        raw_attestations = ()
    for raw_attestation in raw_attestations:
        _restore_one_attested_claim(raw_attestation, rows)


def _restore_one_attested_claim(raw_attestation: object, rows: list[dict[str, object]]) -> None:
    if not isinstance(raw_attestation, Mapping) or raw_attestation.get("family") != _edition_delta_fields._CASILLAS:
        return
    identity = raw_attestation.get(_edition_delta_fields._LINEAGE)
    row = next((item for item in rows if item.get(_edition_delta_fields._LINEAGE) == identity), None)
    if row is None:
        return
    for manifest_field, row_field in (("origin", "continuidad_origin"), ("evidence", "continuidad_evidence")):
        if manifest_field in raw_attestation:
            row[row_field] = raw_attestation[manifest_field]


def _comparable_table(source: _edition_delta_source._EditionSource) -> dict[str, object]:
    effective = _family_defaults_inlined(source.table)
    family_sections = {spec.section for spec in CANONICAL_FAMILY_SPECS}
    table = {
        key: comparable(value, revision_id=source.revision_id, path=f"table.{key}")
        for key, value in effective.items()
        if key
        not in _edition_delta_fields._DECLARED_DEFAULT_KEYS | _edition_delta_payload._STORAGE_REPRESENTATION_FIELDS
        and not (key in family_sections and isinstance(value, list | tuple) and not value)
    }
    return table


def _effective_rows(source: _edition_delta_source._EditionSource) -> list[dict[str, object]]:
    rows = [dict(row) for row in _edition_delta_source._effective_rows(source)]
    _restore_attested_claims(source, rows)
    return rows


def _comparable_rows(source: _edition_delta_source._EditionSource) -> list[object]:
    return [
        comparable(row, revision_id=source.revision_id, path=f"table.{_edition_delta_fields._CASILLAS}[{index}]")
        for index, row in enumerate(_effective_rows(source))
    ]


def chain_materialisation(source: _edition_delta_source._EditionSource) -> bytes:
    """Materialise defaults and attestations, then serialize exact comparable bytes."""
    table = _comparable_table(source)
    table[_edition_delta_fields._CASILLAS] = _comparable_rows(source)
    return json.dumps({"revision": source.revision_id, "table": table}, ensure_ascii=False, sort_keys=True).encode(
        "utf-8"
    )


__all__ = ("chain_materialisation", "comparable", "member_identities", "read_staged_edition")
