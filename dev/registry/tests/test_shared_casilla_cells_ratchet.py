"""No export layout binds one bare casilla id to cells on more than one record without a declared reason.

Each cell reads its value by casilla id, so a bare id bound on two record sheets
writes one figure into both. The registry declares the legitimate repeats in
three places: a ``segmento`` on the casilla, a split value policy within one
record, and the Modelo 200 echo cells that repeat another sheet's amount.
:func:`unadjudicated_shared_owners` already honours the first two; this gate
removes the declared echoes and refuses whatever still spans several records.

The surviving population is pinned in ``shared_casilla_cells_baseline.toml`` by
modelo, revision, casilla id and the sorted record-qualified cell ids. It is a
shrink-only ratchet: a new entry fails, and an entry that no longer occurs must
be deleted rather than left as a spare slot.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest

from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.export_shared_owner import (
    canonical_export_layout,
    unadjudicated_shared_owners,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportLayoutDefinition
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..compiler.authority import compiled_bundled_authority
from ..conformance.modelo_200_echoes import MODELO_200_ECHO_CELLS
from ..pipeline.export_fragment_provenance import load_export_fragment_provenance_manifest
from ..pipeline.rename_set_static_repair import REVIEWED_RENAME_SETS
from ..pipeline.render_check import revision_render_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BASELINE = Path(__file__).with_name("shared_casilla_cells_baseline.toml")
_ECHO_CELLS: Mapping[str, frozenset[tuple[str, str]]] = {"200": MODELO_200_ECHO_CELLS}
_PROVENANCE = "_generation.provenance.json"


@dataclass(frozen=True, slots=True, order=True)
class SharedCasillaCells:
    """One bare casilla id whose undeclared cells span more than one record."""

    modelo: str
    revision: str
    casilla_id: str
    cells: tuple[str, ...]


def cross_record_shared_owners(
    modelo: str,
    revision: str,
    layout: ExportLayoutDefinition,
    casillas: Iterable[CasillaDefinition],
    *,
    field_sheets: Mapping[str, str],
    echo_cells: frozenset[tuple[str, str]],
) -> tuple[SharedCasillaCells, ...]:
    """Return every unadjudicated owner whose non-echo cells sit on more than one record."""
    records = {
        str(field.id): str(record.id)
        for record in layout.records
        for field in record.fields
        if field.kind is CasillaFieldKind.CASILLA
    }
    found: list[SharedCasillaCells] = []
    for owner in unadjudicated_shared_owners(layout, casillas):
        own = [
            cell
            for cell in owner.target_cells
            if (field_sheets.get(str(cell.id), ""), str(owner.casilla_id)) not in echo_cells
        ]
        if len({records[str(cell.id)] for cell in own}) > 1:
            cells = tuple(sorted(f"{records[str(cell.id)]}/{cell.id}" for cell in own))
            found.append(SharedCasillaCells(modelo, revision, str(owner.casilla_id), cells))
    return tuple(found)


def _field_sheets(modelo: str, revision: str) -> dict[str, str]:
    """Map each generated field to the design sheet the record design prints it on."""
    manifest = bundled_path("registry", "aeat", "modelos", modelo, "revisions", revision, "export", _PROVENANCE)
    if not manifest.is_file():
        return {}
    receipt = load_export_fragment_provenance_manifest(manifest.read_bytes())
    inputs = revision_render_inputs(
        compiled_bundled_authority(), modelo=modelo, revision=revision, source_ref=str(receipt.source_ref)
    )
    return {
        str(field.semantic_entry.export_field_id): (field.parser_field.sheet or "").strip().upper()
        for field in inputs.joined.fields
    }


@cache
def bundled_shared_owners() -> frozenset[SharedCasillaCells]:
    """Scan every revision's canonical export layout in the compiled authority."""
    found: set[SharedCasillaCells] = set()
    for modelo in compiled_bundled_authority().modelos:
        modelo_id = str(modelo.id)
        echoes = _ECHO_CELLS.get(modelo_id, frozenset())
        for revision in modelo.revisions.values():
            layout = canonical_export_layout(revision.export_layouts)
            if layout is None:
                continue
            sheets = _field_sheets(modelo_id, str(revision.id)) if echoes else {}
            found.update(
                cross_record_shared_owners(
                    modelo_id, str(revision.id), layout, revision.casillas, field_sheets=sheets, echo_cells=echoes
                )
            )
    return frozenset(found)


def _baseline() -> frozenset[SharedCasillaCells]:
    entries = tomllib.loads(_BASELINE.read_text(encoding="utf-8")).get("entries", [])
    return frozenset(
        SharedCasillaCells(entry["modelo"], entry["revision"], entry["casilla_id"], tuple(entry["cells"]))
        for entry in entries
    )


def test_no_new_bare_casilla_spans_several_records() -> None:
    new = sorted(bundled_shared_owners() - _baseline())
    assert not new, "bare casilla ids newly bound on several records:\n" + "\n".join(map(str, new[:40]))


def test_a_resolved_entry_is_deleted_from_the_baseline() -> None:
    stale = sorted(_baseline() - bundled_shared_owners())
    assert not stale, "baseline entries that no longer occur; delete them:\n" + "\n".join(map(str, stale[:40]))


def _published_revision(modelo: str, source_ref: str) -> str:
    revisions = [
        manifest.parent.parent.name
        for manifest in bundled_path("registry", "aeat", "modelos", modelo).glob(f"revisions/*/export/{_PROVENANCE}")
        if str(load_export_fragment_provenance_manifest(manifest.read_bytes()).source_ref) == source_ref
    ]
    assert len(revisions) == 1, (modelo, source_ref, revisions)
    return revisions[0]


def test_the_reviewed_renames_are_not_admitted_debt() -> None:
    """A reviewed rename made its boxes sheet-scoped; the baseline must not keep their old shared ids."""
    baseline = _baseline()
    for reviewed in REVIEWED_RENAME_SETS:
        revisions = {_published_revision(reviewed.modelo, member.source_ref) for member in reviewed.members}
        admitted = [
            entry
            for entry in baseline
            if entry.modelo == reviewed.modelo
            and entry.revision in revisions
            and entry.casilla_id in reviewed.renamed_casilla_ids
        ]
        assert not admitted, admitted


def _rebound(layout: ExportLayoutDefinition, field_id: str, casilla_id: CasillaId) -> ExportLayoutDefinition:
    return layout.model_copy(
        update={
            "records": tuple(
                record.model_copy(
                    update={
                        "fields": tuple(
                            field.model_copy(update={"casilla_id": casilla_id}) if str(field.id) == field_id else field
                            for field in record.fields
                        )
                    }
                )
                for record in layout.records
            )
        }
    )


@dataclass(frozen=True, slots=True)
class _PlantedPair:
    modelo: str
    revision: ModeloRevision
    layout: ExportLayoutDefinition
    first_record: str
    anchor: ExportFieldDefinition
    second_record: str
    target: ExportFieldDefinition


def _planted_pair() -> _PlantedPair:
    """Pick a bare-id cell on one record and any casilla cell on another record of a real layout."""
    for modelo in sorted(compiled_bundled_authority().modelos, key=lambda item: str(item.id)):
        for revision in sorted(modelo.revisions.values(), key=lambda item: str(item.id)):
            layout = canonical_export_layout(revision.export_layouts)
            if layout is None or len(layout.records) < 2 or not any(c.segmento for c in revision.casillas):
                continue
            declared = {str(casilla.id): casilla for casilla in revision.casillas}
            already = {str(owner.casilla_id) for owner in unadjudicated_shared_owners(layout, revision.casillas)}
            first, second = layout.records[0], layout.records[1]
            anchors = [
                field
                for field in first.fields
                if field.kind is CasillaFieldKind.CASILLA
                and field.casilla_id is not None
                and str(field.casilla_id) not in already
                and (casilla := declared.get(str(field.casilla_id))) is not None
                and casilla.segmento is None
            ]
            targets = [field for field in second.fields if field.kind is CasillaFieldKind.CASILLA]
            if anchors and targets:
                return _PlantedPair(
                    str(modelo.id), revision, layout, str(first.id), anchors[0], str(second.id), targets[0]
                )
    pytest.fail("no multi-record export layout of a segmented modelo to plant a defect in")


def test_the_gate_detects_a_bare_id_planted_on_a_second_record() -> None:
    """Bind one record's cell to a bare id another record already writes: exactly that owner appears."""
    pair = _planted_pair()
    assert pair.anchor.casilla_id is not None
    revision = str(pair.revision.id)
    clean = cross_record_shared_owners(
        pair.modelo, revision, pair.layout, pair.revision.casillas, field_sheets={}, echo_cells=frozenset()
    )
    planted = cross_record_shared_owners(
        pair.modelo,
        revision,
        _rebound(pair.layout, str(pair.target.id), pair.anchor.casilla_id),
        pair.revision.casillas,
        field_sheets={},
        echo_cells=frozenset(),
    )

    added = set(planted) - set(clean)
    assert [entry.casilla_id for entry in added] == [str(pair.anchor.casilla_id)]
    (entry,) = added
    assert f"{pair.first_record}/{pair.anchor.id}" in entry.cells
    assert f"{pair.second_record}/{pair.target.id}" in entry.cells


def test_a_declared_echo_cell_is_not_a_shared_owner() -> None:
    """The same planted pair passes once the second cell is declared an echo on its sheet."""
    pair = _planted_pair()
    assert pair.anchor.casilla_id is not None
    planted = _rebound(pair.layout, str(pair.target.id), pair.anchor.casilla_id)

    found = cross_record_shared_owners(
        pair.modelo,
        str(pair.revision.id),
        planted,
        pair.revision.casillas,
        field_sheets={str(pair.target.id): "ECHO-SHEET"},
        echo_cells=frozenset({("ECHO-SHEET", str(pair.anchor.casilla_id))}),
    )

    assert str(pair.anchor.casilla_id) not in {entry.casilla_id for entry in found}
