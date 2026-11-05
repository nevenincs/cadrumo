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

from . import (
    edition_delta_drop_scope,
    edition_delta_errors,
    edition_delta_fields,
    edition_delta_payload,
    edition_delta_source,
)
from .edition_delta_proof_source import read_staged_edition

_DISPOSITIONS = "family_dispositions"
_ORIGIN_MARKER = "inherited_from"


def member_identities(source: edition_delta_source.EditionSource) -> Mapping[str, tuple[str, ...]]:
    """Return materialised member identities in order, including every droppable family."""
    identities = {
        edition_delta_fields.CASILLAS: tuple(
            f"{edition_delta_source.row_id(row)}|{edition_delta_source.lineage(row)}" for row in source.rows
        )
    }
    sections = set(edition_delta_fields.REFERENCE_SECTIONS.values()) | {
        family.section for family in edition_delta_drop_scope.DROPPABLE_FAMILIES
    }
    for section in sorted(sections - {edition_delta_fields.CASILLAS}):
        identities[section] = tuple(
            str(member.get("id")) for member in edition_delta_source.family_members(source.table, section)
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
        return {edition_delta_fields.DATE_TAG: value.isoformat()}
    raise edition_delta_errors.MigrationRefusedError(
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


def _restore_attested_claims(source: edition_delta_source.EditionSource, rows: list[dict[str, object]]) -> None:
    raw_attestations = source.manifest.get("lineage_attestations", ())
    if not isinstance(raw_attestations, list | tuple):
        raw_attestations = ()
    for raw_attestation in raw_attestations:
        _restore_one_attested_claim(raw_attestation, rows)


def _restore_one_attested_claim(raw_attestation: object, rows: list[dict[str, object]]) -> None:
    if not isinstance(raw_attestation, Mapping) or raw_attestation.get("family") != edition_delta_fields.CASILLAS:
        return
    identity = raw_attestation.get(edition_delta_fields.LINEAGE)
    row = next((item for item in rows if item.get(edition_delta_fields.LINEAGE) == identity), None)
    if row is None:
        return
    for manifest_field, row_field in (("origin", "continuidad_origin"), ("evidence", "continuidad_evidence")):
        if manifest_field in raw_attestation:
            row[row_field] = raw_attestation[manifest_field]


def _without_disposition_origins(table: dict[str, object]) -> dict[str, object]:
    """Drop the loader's origin marker from each disposition, which says where it is stated, not what it means."""
    dispositions = table.get(_DISPOSITIONS)
    if not isinstance(dispositions, Mapping):
        return table
    return {
        **table,
        _DISPOSITIONS: {
            family: {key: item for key, item in entry.items() if key != _ORIGIN_MARKER}
            if isinstance(entry, Mapping)
            else entry
            for family, entry in dispositions.items()
        },
    }


def _comparable_table(source: edition_delta_source.EditionSource) -> dict[str, object]:
    effective = _without_disposition_origins(_family_defaults_inlined(source.table))
    family_sections = {spec.section for spec in CANONICAL_FAMILY_SPECS}
    table = {
        key: comparable(value, revision_id=source.revision_id, path=f"table.{key}")
        for key, value in effective.items()
        if key not in edition_delta_fields.DECLARED_DEFAULT_KEYS | edition_delta_payload.STORAGE_REPRESENTATION_FIELDS
        and not (key in family_sections and isinstance(value, list | tuple) and not value)
    }
    return table


def _effective_rows(source: edition_delta_source.EditionSource) -> list[dict[str, object]]:
    rows = [dict(row) for row in edition_delta_source.effective_rows(source)]
    _restore_attested_claims(source, rows)
    return rows


def _comparable_rows(source: edition_delta_source.EditionSource) -> list[object]:
    return [
        comparable(row, revision_id=source.revision_id, path=f"table.{edition_delta_fields.CASILLAS}[{index}]")
        for index, row in enumerate(_effective_rows(source))
    ]


def chain_materialisation(source: edition_delta_source.EditionSource) -> bytes:
    """Materialise defaults and attestations, then serialize exact comparable bytes."""
    table = _comparable_table(source)
    table[edition_delta_fields.CASILLAS] = _comparable_rows(source)
    return json.dumps({"revision": source.revision_id, "table": table}, ensure_ascii=False, sort_keys=True).encode(
        "utf-8"
    )


__all__ = ("chain_materialisation", "comparable", "member_identities", "read_staged_edition")
