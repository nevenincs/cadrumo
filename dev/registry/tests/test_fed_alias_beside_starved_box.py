"""Modelo 390's rate-specific recargo boxes are owned by their typed rows.

The former fed-alias/starved-box shape has been resolved: the aggregate
``general``, ``reducido`` and ``super-reducido`` casillas no longer own export fields,
and the numbered ``tipo-*.cuota`` casillas carry the export references and
layout ownership. Keep that repaired relationship observable so a later
revision cannot silently route the filed bytes back through an aggregate alias.
"""

from __future__ import annotations

import re
from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..compiler.authority import compile_validated_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BOX_NUMBER = re.compile(r"^\d+[A-Za-z]?$")
_MODELO_ID = "390"
_RATE_QUOTA_PREFIX = "iva.anual.repercutido.recargo.tipo-"
_AGGREGATE_IDS = frozenset(
    {
        "iva.anual.repercutido.recargo.general",
        "iva.anual.repercutido.recargo.reducido",
        "iva.anual.repercutido.recargo.super-reducido",
    }
)
_REVISIONS_WITH_RATE_QUOTA_EXPORTS = frozenset({"2022", "2023", "2024", "2025"})


@cache
def _authority() -> ValidatedRegistryAuthority:
    return compile_validated_authority(bundled_path("registry", "aeat"), bundled_path())


def _is_box_number(number: str | None) -> bool:
    return bool(_BOX_NUMBER.fullmatch((number or "").strip()))


def _owned_casilla_ids(revision: ModeloRevision) -> frozenset[str]:
    owned: set[str] = set()
    for layout in revision.export_layouts:
        for record in layout.records:
            for field in record.fields:
                if field.casilla_id is not None:
                    owned.add(str(field.casilla_id))
    return frozenset(owned)


def _published_revisions() -> tuple[tuple[str, ModeloRevision], ...]:
    modelo = _authority().modelo(_MODELO_ID)
    return tuple(
        (str(revision_id), revision) for revision_id, revision in modelo.revisions.items() if revision.export_layouts
    )


def _rate_quota_rows() -> tuple[tuple[str, CasillaDefinition, frozenset[str]], ...]:
    rows: list[tuple[str, CasillaDefinition, frozenset[str]]] = []
    for revision_id, revision in _published_revisions():
        owned = _owned_casilla_ids(revision)
        rows.extend(
            (revision_id, casilla, owned)
            for casilla in revision.casillas
            if str(casilla.id).startswith(_RATE_QUOTA_PREFIX) and str(casilla.id).endswith(".cuota")
        )
    return tuple(rows)


def _aggregate_rows() -> tuple[tuple[str, CasillaDefinition, frozenset[str]], ...]:
    rows: list[tuple[str, CasillaDefinition, frozenset[str]]] = []
    for revision_id, revision in _published_revisions():
        owned = _owned_casilla_ids(revision)
        rows.extend((revision_id, casilla, owned) for casilla in revision.casillas if str(casilla.id) in _AGGREGATE_IDS)
    return tuple(rows)


def test_numbered_rate_specific_recargo_rows_own_their_export_fields() -> None:
    rows = _rate_quota_rows()
    assert rows, "no rate-specific Modelo 390 recargo quota rows were inspected"
    assert {revision_id for revision_id, _, _ in rows} >= _REVISIONS_WITH_RATE_QUOTA_EXPORTS

    nonnumeric = [
        (revision_id, str(casilla.id), casilla.number)
        for revision_id, casilla, _ in rows
        if not _is_box_number(casilla.number)
    ]
    assert not nonnumeric, f"rate-specific quota rows lost their numeric box membership: {nonnumeric}"

    missing = [
        (revision_id, str(casilla.id), casilla.number)
        for revision_id, casilla, owned in rows
        if not casilla.export_refs or str(casilla.id) not in owned
    ]
    assert not missing, f"rate-specific quota rows have no owned export bytes: {missing}"


def test_aggregate_recargo_aliases_do_not_own_the_rate_specific_bytes() -> None:
    rows = _aggregate_rows()
    assert rows, "no aggregate Modelo 390 recargo rows were inspected"
    aliases_by_revision = {
        revision_id: {str(casilla.id) for row_revision, casilla, _ in rows if row_revision == revision_id}
        for revision_id in _REVISIONS_WITH_RATE_QUOTA_EXPORTS
    }
    missing = {
        revision_id: sorted(_AGGREGATE_IDS - aliases)
        for revision_id, aliases in aliases_by_revision.items()
        if _AGGREGATE_IDS - aliases
    }
    assert not missing, f"published revisions are missing aggregate recargo aliases: {missing}"

    misplaced = [
        (revision_id, str(casilla.id), casilla.number)
        for revision_id, casilla, owned in rows
        if _is_box_number(casilla.number) or casilla.export_refs or str(casilla.id) in owned
    ]
    assert not misplaced, f"aggregate recargo aliases unexpectedly claim exported box bytes: {misplaced}"
