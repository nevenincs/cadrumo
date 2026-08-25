"""Exact-anchor canonical-home closure for the five reviewed Modelo 303 epochs.

The semantic maps are the reviewed declaration of canonical homes; this test
does not classify a second time.  It joins every hash-pinned source field to
that declaration through the existing exact-anchor join, then checks the
public official-casilla classifier agrees for the canonical casilla homes.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest

from cadrumo.core import EstadoCasillaOficial
from cadrumo.domain.calculations.registry.schema import CasillaFieldKind
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection
from cadrumo.domain.calculations.registry.export import clasificar_casillas_oficiales
from cadrumo.domain.calculations.registry.loader import load_registry_tree
from cadrumo.domain.calculations.registry.temporal import select_revision

from ..analysis.m303_semantic_census import census_m303_semantic_map, resolve_semantic_home
from ..pipeline._record_design_ir import RecordDesignIntermediate, load_record_design_intermediate
from ..pipeline._semantic_map import SemanticMap
from ..pipeline._semantic_map_join import JoinedRecordDesign, JoinedRecordDesignField, join_record_design_semantics
from ..pipeline._semantic_map_loader import load_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "303"
_SOURCE_ROOT = Path("src/cadrumo/_data")
_REGISTRY_ROOT = _SOURCE_ROOT / "registry" / "aeat"
_MAPPING_ROOT = Path("dev/registry/mappings/modelo_303")
_OFFICIAL_LITERAL = re.compile(
    r'^\s*constante\s+"(?P<literal>[^"]*)"(?:\.\s*nota\s+\d+)?\s*$',
    re.IGNORECASE,
)
_CANONICAL_BOX_46 = "iva.resultado-regimen-general"


@dataclass(frozen=True, slots=True)
class _Epoch:
    name: str
    filing_year: int
    period: str
    revision_id: str
    expected_anchor_count: int


_EPOCHS = (
    _Epoch("2023", 2023, "4T", "2023", 406),
    _Epoch("2024-early", 2024, "2T", "2024-hasta-08-y-2t", 406),
    _Epoch("2024-late", 2024, "4T", "2024-desde-09-y-3t", 426),
    _Epoch("2025", 2025, "4T", "2025", 429),
    _Epoch("2026", 2026, "4T", "2026-y-siguientes", 430),
)
_EPOCH_BY_NAME = {epoch.name: epoch for epoch in _EPOCHS}


@dataclass(frozen=True, slots=True)
class _EpochAuthorities:
    epoch: _Epoch
    revision: object
    inspection: RegistryRevisionInspection
    intermediate: RecordDesignIntermediate
    semantic_map: SemanticMap
    joined: JoinedRecordDesign


@cache
def _compiled_modelo():
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    return next(modelo for modelo in modelos if str(modelo.id) == _MODELO), catalogues


@cache
def _authorities(epoch_name: str) -> _EpochAuthorities:
    epoch = _EPOCH_BY_NAME[epoch_name]
    modelo, catalogues = _compiled_modelo()
    revision = select_revision(modelo, filing_year=epoch.filing_year, period=epoch.period)
    assert str(revision.id) == epoch.revision_id
    inspection = RegistryRevisionInspection.from_revision(
        modelo=modelo,
        revision=revision,
        source_root=_SOURCE_ROOT,
        sources=catalogues.sources,
        legal_ref_ids=frozenset(catalogues.legal),
    )
    semantic_map = load_semantic_map(_MAPPING_ROOT / epoch.name)
    intermediate = load_record_design_intermediate(
        inspection.source_root,
        inspection.sources,
        source_ref=str(semantic_map.source_ref),
        filing_year=epoch.filing_year,
        design_epoch=epoch.name,
    )
    return _EpochAuthorities(
        epoch=epoch,
        revision=revision,
        inspection=inspection,
        intermediate=intermediate,
        semantic_map=semantic_map,
        joined=join_record_design_semantics(semantic_map, intermediate, inspection),
    )


def _source_anchor(field) -> tuple[str, int, str | None, str | None, str]:
    return (
        str(field.sheet),
        int(field.source_row),
        field.source_cell,
        field.ordinal,
        str(field.record_identity),
    )


def _semantic_anchor(anchor) -> tuple[str, int, str | None, str | None, str]:
    return (
        str(anchor.sheet),
        int(anchor.source_row),
        anchor.source_cell,
        anchor.ordinal,
        str(anchor.record_identity),
    )


def _joined_fields(authorities: _EpochAuthorities) -> tuple[JoinedRecordDesignField, ...]:
    return tuple(field for record in authorities.joined.records for field in record.fields)


def _source_and_map_anchor_counts(authorities: _EpochAuthorities) -> tuple[Counter, Counter]:
    parser_envelope = authorities.intermediate.variable_envelopes
    semantic_envelope = authorities.semantic_map.variable_envelopes
    assert len(parser_envelope) == len(semantic_envelope) == 1
    source_anchors = [
        *(_source_anchor(field) for sheet in authorities.intermediate.sheets for field in sheet.fields),
        *(_source_anchor(field) for field in parser_envelope[0].prefix_fields),
    ]
    map_anchors = [
        *(_semantic_anchor(entry.anchor) for entry in authorities.semantic_map.entries),
        *(_semantic_anchor(field.anchor) for field in semantic_envelope[0].prefix_fields),
    ]
    return Counter(source_anchors), Counter(map_anchors)


def _is_reserved(field) -> bool:
    return "reservado para la aeat" in field.normalized_description.casefold()


def _source_fact_errors(fields: tuple[JoinedRecordDesignField, ...]) -> tuple[str, ...]:
    """Return exact source literals or AEAT reserves assigned to the wrong home."""
    errors: list[str] = []
    for joined_field in fields:
        field = joined_field.parser_field
        entry = joined_field.semantic_entry
        anchor = f"{field.record_identity}/{field.ordinal}@{field.source_row}"
        if _is_reserved(field):
            if entry.kind is not CasillaFieldKind.FILLER:
                errors.append(f"{anchor}: AEAT reserve is not a filler")
            continue
        if entry.kind is CasillaFieldKind.FILLER:
            errors.append(f"{anchor}: filler has no AEAT reserve")
            continue
        if entry.kind is not CasillaFieldKind.LITERAL:
            continue
        if field.content == "En blanco":
            if entry.literal != "":
                errors.append(f"{anchor}: blank marker is not the exact empty literal")
            continue
        match = _OFFICIAL_LITERAL.fullmatch(field.content or "")
        if match is None or entry.literal != match.group("literal"):
            errors.append(f"{anchor}: literal does not retain exact official constant bytes")
    return tuple(errors)


@pytest.mark.parametrize("epoch_name", tuple(epoch.name for epoch in _EPOCHS))
def test_every_hash_pinned_m303_anchor_has_one_canonical_home(epoch_name: str) -> None:
    """All parser fields, including DP30300, retain multiplicity and exact identity."""
    authorities = _authorities(epoch_name)
    census = census_m303_semantic_map(
        authorities.intermediate,
        authorities.semantic_map,
        design_epoch=authorities.epoch.name,
    )
    source_counts, map_counts = _source_and_map_anchor_counts(authorities)

    assert census.total_anchor_count == authorities.epoch.expected_anchor_count
    assert source_counts == map_counts
    assert all(count == 1 for count in source_counts.values())
    assert len(source_counts) == authorities.epoch.expected_anchor_count


@pytest.mark.parametrize("epoch_name", tuple(epoch.name for epoch in _EPOCHS))
def test_canonical_casilla_homes_are_addressed_without_number_reverse_lookup(epoch_name: str) -> None:
    """Map CasillaIds, never box metadata, choose the public classifier's owner."""
    authorities = _authorities(epoch_name)
    statuses = clasificar_casillas_oficiales(authorities.revision)

    for joined_field in _joined_fields(authorities):
        casilla_id = joined_field.semantic_entry.casilla_id
        if casilla_id is None:
            continue
        assert casilla_id in authorities.inspection.casilla_ids
        assert statuses[casilla_id] is EstadoCasillaOficial.ADDRESSED


@pytest.mark.parametrize("epoch_name", tuple(epoch.name for epoch in _EPOCHS))
def test_box_46_reaches_its_canonical_owner_through_the_map_and_generated_layout(epoch_name: str) -> None:
    """Box metadata stays diagnostic; its canonical id is the export identity."""
    authorities = _authorities(epoch_name)
    matches = tuple(
        field for field in _joined_fields(authorities) if str(field.semantic_entry.casilla_id) == _CANONICAL_BOX_46
    )
    assert len(matches) == 1
    assert "[46]" in matches[0].parser_field.normalized_description

    canonical = next(casilla for casilla in authorities.revision.casillas if str(casilla.id) == _CANONICAL_BOX_46)
    assert canonical.form_number == "46"
    assert canonical.number != "46"
    assert clasificar_casillas_oficiales(authorities.revision)[canonical.id] is EstadoCasillaOficial.ADDRESSED


@pytest.mark.parametrize("epoch_name", tuple(epoch.name for epoch in _EPOCHS))
def test_constants_and_reserves_keep_their_source_grounded_homes(epoch_name: str) -> None:
    """Constants stay literals or their printed numbered casilla; reserves stay fillers."""
    assert not _source_fact_errors(_joined_fields(_authorities(epoch_name)))


def test_two_110_anchor_coordinates_cannot_collapse_or_select_by_a_single_number() -> None:
    """The row-110 and ordinal-110 DP30302 facts are separate exact anchors."""
    authorities = _authorities("2025")
    fields = _joined_fields(authorities)
    source_row_110 = next(
        field
        for field in fields
        if field.parser_field.record_identity == "DP30302"
        and field.parser_field.source_row == 110
        and field.parser_field.source_cell == "A110"
    )
    ordinal_110 = next(
        field
        for field in fields
        if field.parser_field.record_identity == "DP30302" and field.parser_field.ordinal == "110"
    )

    assert _source_anchor(source_row_110.parser_field) != _source_anchor(ordinal_110.parser_field)
    assert resolve_semantic_home(source_row_110.semantic_entry) != resolve_semantic_home(ordinal_110.semantic_entry)

    duplicate_anchor = source_row_110.semantic_entry.model_copy(update={"anchor": ordinal_110.semantic_entry.anchor})
    mutated_entries = tuple(
        duplicate_anchor if entry == source_row_110.semantic_entry else entry
        for entry in authorities.semantic_map.entries
    )
    mutated_map = authorities.semantic_map.model_copy(update={"entries": mutated_entries})
    with pytest.raises(ValueError, match="assigns an anchor more than once"):
        census_m303_semantic_map(authorities.intermediate, mutated_map, design_epoch=authorities.epoch.name)


def test_a_reserved_anchor_mutation_is_detected_as_filler_misuse() -> None:
    """A non-filler home cannot silently replace an AEAT reserve."""
    authorities = _authorities("2025")
    reserved = next(field for field in _joined_fields(authorities) if _is_reserved(field.parser_field))
    mutated = reserved.semantic_entry.model_copy(update={"kind": CasillaFieldKind.LITERAL, "literal": ""})
    mutated_field = reserved.model_copy(update={"semantic_entry": mutated})

    assert _source_fact_errors((mutated_field,)) == (
        f"{reserved.parser_field.record_identity}/{reserved.parser_field.ordinal}@"
        f"{reserved.parser_field.source_row}: AEAT reserve is not a filler",
    )
