"""Source-pinned review worklist for Modelo 200 target identity evidence."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import rtoml

from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_form_layouts import FormPlacementKind
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..compiler.authority import compiled_bundled_authority
from ..conformance.modelo_200_echoes import MODELO_200_ECHO_CELLS
from ..maintenance_support import (
    coverage_assessment_floor,
    coverage_assessment_horizon,
    revision_selection_coordinates,
)
from ..pipeline.record_design_intermediate import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    load_record_design_intermediate,
)
from ..pipeline.semantic_map import SemanticMap, SemanticMapEntry, load_semantic_map_for_revision, semantic_anchor_key
from ..pipeline.semantic_map_validation import resolve_semantic_map_casilla_tokens
from .casilla_id_grammar import classify_casilla_id
from .m200_record_design_support import record_design_field_index, record_design_source

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority

__all__ = [
    "M200MapOwnerIdentityDisposition",
    "M200OrphanDisposition",
    "M200PrintedIdentityDiagnostic",
    "M200PrintedIdentityState",
    "M200SharedOwner",
    "M200SharedOwnerCell",
    "M200TargetIdentityWorklist",
    "M200UnnumberedDesignRow",
    "M200UnnumberedDesignRowDisposition",
    "classify_m200_target_identities",
    "load_bundled_m200_target_identity_worklists",
    "main",
    "render_m200_target_identity_worklists_toml",
    "unnumbered_design_row_disposition",
]


_MODELO = "200"
_PRINTED_NUMBER = re.compile(r"\[([0-9]+)\]")
_BRACKETED_LABEL = re.compile(r"\[([^\[\]]*)\]")


class M200MapOwnerIdentityDisposition(StrEnum):
    """A source-anchor-only classification for a noncanonical map owner."""

    SEGMENT_QUALIFIED_PROPOSAL = "segment_qualified_proposal"


class M200OrphanDisposition(StrEnum):
    """A closed disposition for a declaration that has no target map owner.

    The layout dispositions record that the revision's own form layout declares
    the casilla unplaced or an application working figure.
    """

    UNMAPPED_DECLARATION = "unmapped_declaration"
    DECLARED_UNPLACED = "declared_unplaced"
    DECLARED_WORKING_FIGURE = "declared_working_figure"


class M200UnnumberedDesignRowDisposition(StrEnum):
    """Why a design row that prints no box number still has a proven map owner."""

    SEGMENT_IDENTITY_OF_UNNUMBERED_ROW = "segment_identity_of_unnumbered_row"


class M200PrintedIdentityState(StrEnum):
    """How an official printed number relates to the already-authored map owner."""

    MATCHES_MAP_OWNER = "matches_map_owner"
    MATCHES_IDENTITY_PROPOSAL = "matches_identity_proposal"
    MISSING_OFFICIAL_PRINTED_IDENTITY = "missing_official_printed_identity"
    CONFLICTS_WITH_MAP_OWNER = "conflicts_with_map_owner"


@dataclass(frozen=True, slots=True)
class M200MapOwnerIdentity:
    """One noncanonical casilla map owner; never a declaration or map mutation."""

    export_field_id: str
    anchor: tuple[object, ...]
    declared_map_owner: str
    disposition: M200MapOwnerIdentityDisposition
    proposed_target_identity_non_authoritative: str
    proposed_identity_origin: str
    printed_number: str
    printed_identity_state: M200PrintedIdentityState
    source_ref: str
    source_sha256: str


@dataclass(frozen=True, slots=True)
class M200OrphanedDeclaration:
    """One declared target casilla omitted by every target semantic-map owner."""

    casilla_id: str
    disposition: M200OrphanDisposition
    source_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class M200PrintedIdentityDiagnostic:
    """A printed-number discrepancy that deliberately does not change map ownership."""

    export_field_id: str
    anchor: tuple[object, ...]
    declared_map_owner: str
    printed_number: str | None
    state: M200PrintedIdentityState
    source_ref: str
    source_sha256: str


@dataclass(frozen=True, slots=True)
class M200UnnumberedDesignRow:
    """A design row with no printed box number, owned by its edition's own segment identity.

    The design cannot prove a box number it does not print, so such a row is
    never a printed-identity match; it is admitted only when its owner is a
    declared casilla of the row's own segment, in a non-numeric tail grammar,
    placed on the form with no box number either.
    """

    export_field_id: str
    anchor: tuple[object, ...]
    declared_map_owner: str
    disposition: M200UnnumberedDesignRowDisposition
    source_ref: str
    source_sha256: str


@dataclass(frozen=True, slots=True)
class M200SharedOwnerCell:
    """One design cell that writes a casilla also written by another cell."""

    export_field_id: str
    sheet: str
    source_row: int
    description: str


@dataclass(frozen=True, slots=True)
class M200SharedOwner:
    """A casilla whose single value is written into two or more unrelated cells.

    A matching printed number does not prove a shared concept, because the
    design reuses box numbers across sheets. Only a cell listed as a declared
    echo repeats another cell's amount, so every other cell is counted here
    until its concept is adjudicated against the revision's own design.
    """

    casilla_id: str
    cells: tuple[M200SharedOwnerCell, ...]


@dataclass(frozen=True, slots=True)
class M200TargetIdentityWorklist:
    """Complete, target-source-bound identity evidence with no authority mutation path."""

    revision: str
    source_ref: str
    source_sha256: str
    semantic_map_source_ref: str
    semantic_map_source_sha256: str
    map_owner_mismatches: tuple[M200MapOwnerIdentity, ...]
    orphaned_declarations: tuple[M200OrphanedDeclaration, ...]
    printed_identity_diagnostics: tuple[M200PrintedIdentityDiagnostic, ...]
    unnumbered_design_rows: tuple[M200UnnumberedDesignRow, ...]
    shared_owners: tuple[M200SharedOwner, ...]


def classify_m200_target_identities(
    target_map: SemanticMap,
    target_design: RecordDesignIntermediate,
    *,
    revision_id: str,
    target_declarations: Mapping[CasillaId, CasillaDefinition],
    target_candidate_ids: frozenset[CasillaId],
    declared_placements: Mapping[CasillaId, FormPlacementKind] | None = None,
    unnumbered_on_form_ids: frozenset[CasillaId] = frozenset(),
) -> M200TargetIdentityWorklist:
    """Classify target map-owner identity drift without changing ownership.

    A numeric owner token is resolved by the pipeline's own left-padding
    resolver, so an owner it resolves is credited as mapped and is never a
    finding.  The design proves only the physical source anchor and its
    printed box number; a segment-qualified declaration-like token is retained
    as a non-authoritative proposal, never rewritten into the semantic map or
    promoted into a canonical declaration.
    """
    _require_target_source_identity(target_map, target_design)
    target_fields = _complete_target_field_index(target_map, target_design)
    declared_ids = frozenset(target_declarations)
    known_ids = declared_ids | target_candidate_ids
    source_ref = str(target_design.source.source_ref)
    source_sha256 = target_design.source.source_sha256
    mismatches: list[M200MapOwnerIdentity] = []
    diagnostics: list[M200PrintedIdentityDiagnostic] = []
    unnumbered_rows: list[M200UnnumberedDesignRow] = []
    map_owner_ids: set[CasillaId] = set()
    cells_by_owner: dict[CasillaId, list[M200SharedOwnerCell]] = {}

    for entry in target_map.entries:
        field = target_fields[semantic_anchor_key(entry.anchor)]
        mismatch, diagnostic, map_owner = _target_identity_entry_findings(
            entry,
            target_map=target_map,
            field=field,
            known_ids=known_ids,
            declared_ids=declared_ids,
            source_ref=source_ref,
            source_sha256=source_sha256,
        )
        if map_owner is not None:
            map_owner_ids.add(map_owner)
            cells_by_owner.setdefault(map_owner, []).append(
                M200SharedOwnerCell(
                    export_field_id=str(entry.export_field_id),
                    sheet=field.record_identity,
                    source_row=field.source_row,
                    description=field.normalized_description,
                )
            )
        unnumbered = (
            None
            if diagnostic is None or mismatch is not None
            else unnumbered_design_row_disposition(
                field,
                diagnostic,
                declared_ids=declared_ids,
                unnumbered_on_form_ids=unnumbered_on_form_ids,
            )
        )
        if diagnostic is not None and unnumbered is not None:
            unnumbered_rows.append(
                M200UnnumberedDesignRow(
                    export_field_id=diagnostic.export_field_id,
                    anchor=diagnostic.anchor,
                    declared_map_owner=diagnostic.declared_map_owner,
                    disposition=unnumbered,
                    source_ref=diagnostic.source_ref,
                    source_sha256=diagnostic.source_sha256,
                )
            )
        elif diagnostic is not None:
            diagnostics.append(diagnostic)
        if mismatch is not None:
            mismatches.append(mismatch)

    placements = {} if declared_placements is None else declared_placements
    orphaned = tuple(
        M200OrphanedDeclaration(
            casilla_id=str(casilla_id),
            disposition=_orphan_disposition(placements.get(casilla_id)),
            source_refs=tuple(declaration.source_refs),
        )
        for casilla_id, declaration in sorted(target_declarations.items())
        if casilla_id not in map_owner_ids
    )
    return M200TargetIdentityWorklist(
        revision=revision_id,
        source_ref=source_ref,
        source_sha256=source_sha256,
        semantic_map_source_ref=target_map.source_ref,
        semantic_map_source_sha256=target_map.source_sha256,
        map_owner_mismatches=tuple(sorted(mismatches, key=lambda item: item.export_field_id)),
        orphaned_declarations=orphaned,
        printed_identity_diagnostics=tuple(sorted(diagnostics, key=lambda item: item.export_field_id)),
        unnumbered_design_rows=tuple(sorted(unnumbered_rows, key=lambda item: item.export_field_id)),
        shared_owners=_shared_owners(cells_by_owner),
    )


def unnumbered_design_row_disposition(
    field: RecordDesignIntermediateField,
    diagnostic: M200PrintedIdentityDiagnostic,
    *,
    declared_ids: frozenset[CasillaId],
    unnumbered_on_form_ids: frozenset[CasillaId],
) -> M200UnnumberedDesignRowDisposition | None:
    """Admit a missing printed identity only where the design itself prints no number at all.

    Every condition is read from the inputs, never from a list of rows: the
    row's own description carries no bracketed box number, its resolved owner
    is a declared casilla qualified by the row's own segment with a non-numeric
    tail, and the form places that casilla with no box number. A bracketed
    label the row does print must be exactly that tail, so a design that prints
    a non-numeric label names the owner itself. A row the design numbers, a
    label that names another identity, or an owner in the numeric grammar
    stays a diagnostic.
    """
    if diagnostic.state is not M200PrintedIdentityState.MISSING_OFFICIAL_PRINTED_IDENTITY:
        return None
    if _PRINTED_NUMBER.search(field.normalized_description):
        return None
    owner = diagnostic.declared_map_owner
    if owner not in declared_ids or owner not in unnumbered_on_form_ids:
        return None
    segment, separator, tail = owner.partition(":")
    if not separator or segment != field.record_identity or classify_casilla_id(owner) != "page_qualified":
        return None
    if classify_casilla_id(tail) == "numeric":
        return None
    labels = _BRACKETED_LABEL.findall(field.normalized_description)
    if labels and labels != [tail]:
        return None
    return M200UnnumberedDesignRowDisposition.SEGMENT_IDENTITY_OF_UNNUMBERED_ROW


def _shared_owners(cells_by_owner: Mapping[CasillaId, list[M200SharedOwnerCell]]) -> tuple[M200SharedOwner, ...]:
    """Return the owners with more than one cell left once declared echoes are set aside."""
    found: list[M200SharedOwner] = []
    for casilla_id, cells in sorted(cells_by_owner.items()):
        own_cells = tuple(cell for cell in cells if (cell.sheet, str(casilla_id)) not in MODELO_200_ECHO_CELLS)
        if len(own_cells) > 1:
            found.append(M200SharedOwner(casilla_id=str(casilla_id), cells=own_cells))
    return tuple(found)


def _orphan_disposition(placement: FormPlacementKind | None) -> M200OrphanDisposition:
    if placement is FormPlacementKind.UNPLACED:
        return M200OrphanDisposition.DECLARED_UNPLACED
    if placement is FormPlacementKind.WORKING_FIGURE:
        return M200OrphanDisposition.DECLARED_WORKING_FIGURE
    return M200OrphanDisposition.UNMAPPED_DECLARATION


def _target_identity_entry_findings(
    entry: SemanticMapEntry,
    *,
    target_map: SemanticMap,
    field: RecordDesignIntermediateField,
    known_ids: frozenset[CasillaId],
    declared_ids: frozenset[CasillaId],
    source_ref: str,
    source_sha256: str,
) -> tuple[M200MapOwnerIdentity | None, M200PrintedIdentityDiagnostic | None, CasillaId | None]:
    kind = _semantic_kind(entry)
    if kind != CasillaFieldKind.CASILLA.value:
        if entry.casilla_id is not None:
            raise ValueError(f"non-casilla map entry {entry.export_field_id!r} declares casilla ownership")
        return None, None, None
    if entry.casilla_id is None:
        raise ValueError(f"casilla map entry {entry.export_field_id!r} omits its owner")
    printed = printed_target_number(field)
    resolved = _resolve_owner(entry, target_map, known_ids)
    if resolved is not None:
        printed_state = printed_identity_state(printed, resolved, proposal=None)
        diagnostic = None
        if printed_state is not M200PrintedIdentityState.MATCHES_MAP_OWNER:
            diagnostic = M200PrintedIdentityDiagnostic(
                export_field_id=str(entry.export_field_id),
                anchor=semantic_anchor_key(entry.anchor),
                declared_map_owner=resolved,
                printed_number=printed,
                state=printed_state,
                source_ref=source_ref,
                source_sha256=source_sha256,
            )
        return None, diagnostic, resolved

    owner = str(entry.casilla_id)
    disposition, proposed = classify_noncanonical_map_owner(entry, target_map, field=field, known_ids=known_ids)
    printed_state = printed_identity_state(printed, owner, proposal=proposed)
    if printed is None or printed_state is not M200PrintedIdentityState.MATCHES_IDENTITY_PROPOSAL:
        raise ValueError(f"target anchor {entry.export_field_id!r} does not prove its proposed map-owner identity")
    mismatch = M200MapOwnerIdentity(
        export_field_id=str(entry.export_field_id),
        anchor=semantic_anchor_key(entry.anchor),
        declared_map_owner=owner,
        disposition=disposition,
        proposed_target_identity_non_authoritative=proposed,
        proposed_identity_origin=("declared" if proposed in declared_ids else "candidate_non_authoritative"),
        printed_number=printed,
        printed_identity_state=printed_state,
        source_ref=source_ref,
        source_sha256=source_sha256,
    )
    return mismatch, None, None


def _resolve_owner(
    entry: SemanticMapEntry,
    target_map: SemanticMap,
    casilla_ids: frozenset[CasillaId],
) -> CasillaId | None:
    """Return the owner the canonical resolver settles on, or None when it refuses."""
    try:
        resolved = resolve_semantic_map_casilla_tokens(
            target_map.model_copy(update={"entries": (entry,)}),
            casilla_ids=casilla_ids,
        )
    except RegistryValidationError:
        return None
    return resolved.entries[0].casilla_id


def render_m200_target_identity_worklists_toml(worklists: tuple[M200TargetIdentityWorklist, ...]) -> str:
    """Render deterministic source-anchor identity evidence, one table per revision, without an apply path."""
    for worklist in worklists:
        _require_worklist_source_identity(worklist)
    return rtoml.dumps(
        {
            "schema_version": 1,
            "authority_status": "proposal_only",
            "modelo": _MODELO,
            "revision_worklist": [
                {
                    "revision": worklist.revision,
                    "source_ref": worklist.source_ref,
                    "source_sha256": worklist.source_sha256,
                    "semantic_map_source_ref": worklist.semantic_map_source_ref,
                    "semantic_map_source_sha256": worklist.semantic_map_source_sha256,
                    "counts": {
                        "map_owner_mismatches": len(worklist.map_owner_mismatches),
                        "orphaned_declarations": len(worklist.orphaned_declarations),
                        "printed_identity_diagnostics": len(worklist.printed_identity_diagnostics),
                        "unnumbered_design_rows": len(worklist.unnumbered_design_rows),
                        "shared_owners": len(worklist.shared_owners),
                        "shared_owner_cells": sum(len(row.cells) for row in worklist.shared_owners),
                    },
                    "map_owner_mismatch": [_serialise(row) for row in worklist.map_owner_mismatches],
                    "orphaned_declaration": [_serialise(row) for row in worklist.orphaned_declarations],
                    "printed_identity_diagnostic": [_serialise(row) for row in worklist.printed_identity_diagnostics],
                    "unnumbered_design_row": [_serialise(row) for row in worklist.unnumbered_design_rows],
                    "shared_owner": [_serialise(row) for row in worklist.shared_owners],
                }
                for worklist in worklists
            ],
        },
        pretty=True,
    )


def main(argv: list[str] | None = None) -> int:
    """Emit the complete proposal-only target identity worklists as TOML to stdout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    worklists = load_bundled_m200_target_identity_worklists()
    sys.stdout.write(render_m200_target_identity_worklists_toml(worklists))
    return 0


def load_bundled_m200_target_identity_worklists() -> tuple[M200TargetIdentityWorklist, ...]:
    """Load one worklist per Modelo 200 revision the registry's supported envelope selects."""
    authority = compiled_bundled_authority()
    modelo = authority.modelo(_MODELO)
    horizon = coverage_assessment_horizon(authority.catalogues)
    floor = coverage_assessment_floor(authority.catalogues)
    selected = tuple(
        revision
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.valid_from)
        if revision_selection_coordinates(revision, assessment_horizon=horizon, assessment_floor=floor)
    )
    source_root = bundled_path()
    worklists = (_load_revision_worklist(authority, revision, source_root) for revision in selected)
    return tuple(worklist for worklist in worklists if worklist is not None)


def _load_revision_worklist(
    authority: ValidatedRegistryAuthority,
    revision: ModeloRevision,
    source_root: Path,
) -> M200TargetIdentityWorklist | None:
    """Screen one revision, or return None when it has no authored semantic map to screen."""
    sources = authority.catalogues.sources
    target_source = record_design_source(revision.source_refs, sources)
    target_epoch = sources[target_source].record_design_epoch
    if target_epoch is None:
        raise ValueError("M200 target record-design source must declare an epoch")
    epoch_directory = Path(__file__).parents[1] / "mappings" / f"modelo_{_MODELO}" / target_epoch
    if not epoch_directory.is_dir():
        return None
    target_design = load_record_design_intermediate(
        source_root,
        sources,
        source_ref=target_source,
        filing_year=revision.valid_from.year,
        design_epoch=target_epoch,
    )
    semantic_map = load_semantic_map_for_revision(epoch_directory, revision.id)
    return classify_m200_target_identities(
        semantic_map,
        target_design,
        revision_id=str(revision.id),
        target_declarations={declaration.id: declaration for declaration in revision.casillas},
        target_candidate_ids=frozenset(),
        declared_placements={
            placement.casilla_id: placement.kind for layout in revision.form_layouts for placement in layout.placements
        },
        unnumbered_on_form_ids=frozenset(
            placement.casilla_id
            for layout in revision.form_layouts
            for placement in layout.placements
            if placement.kind is FormPlacementKind.ON_FORM and placement.box_number is None
        ),
    )


def _require_target_source_identity(target_map: SemanticMap, target_design: RecordDesignIntermediate) -> None:
    if (
        target_map.source_ref != target_design.source.source_ref
        or target_map.source_sha256 != target_design.source.source_sha256
    ):
        raise ValueError("M200 target source identity drifted")


def _require_worklist_source_identity(worklist: M200TargetIdentityWorklist) -> None:
    if (
        worklist.semantic_map_source_ref != worklist.source_ref
        or worklist.semantic_map_source_sha256 != worklist.source_sha256
    ):
        raise ValueError("M200 target identity worklist source identity drifted")


def _complete_target_field_index(
    target_map: SemanticMap,
    target_design: RecordDesignIntermediate,
) -> dict[tuple[object, ...], RecordDesignIntermediateField]:
    fields = tuple(field for sheet in target_design.sheets for field in sheet.fields)
    target_fields = record_design_field_index(target_design)
    map_keys = tuple(semantic_anchor_key(entry.anchor) for entry in target_map.entries)
    if len(target_fields) != len(fields):
        raise ValueError("M200 target design has ambiguous source anchors")
    if len(set(map_keys)) != len(map_keys) or set(map_keys) != set(target_fields):
        raise ValueError("M200 target semantic map omits, duplicates, or drifts from a source anchor")
    return target_fields


def _semantic_kind(entry: SemanticMapEntry) -> str:
    kind = getattr(entry.kind, "value", entry.kind)
    return str(kind)


def classify_noncanonical_map_owner(
    entry: SemanticMapEntry,
    target_map: SemanticMap,
    *,
    field: RecordDesignIntermediateField,
    known_ids: frozenset[CasillaId],
) -> tuple[M200MapOwnerIdentityDisposition, str]:
    """Propose the segment-qualified identity a token the canonical resolver refused may denote."""
    prefix = f"{field.record_identity}:"
    segment_ids = frozenset(str(item)[len(prefix) :] for item in known_ids if str(item).startswith(prefix))
    resolved = _resolve_owner(entry, target_map, segment_ids)
    if resolved is None:
        raise ValueError(f"M200 casilla map owner {entry.casilla_id!r} has ambiguous or missing target identity")
    return M200MapOwnerIdentityDisposition.SEGMENT_QUALIFIED_PROPOSAL, f"{prefix}{resolved}"


def _same_box_number(left: str, right: str) -> bool:
    """Compare two decimal box numbers modulo left-zero padding, as the design prints them."""
    return left.isdecimal() and right.isdecimal() and left.lstrip("0") == right.lstrip("0")


def printed_identity_state(
    printed: str | None,
    owner: str,
    *,
    proposal: str | None,
) -> M200PrintedIdentityState:
    """Classify a printed M200 identity against the owner and any proposed identity."""
    if printed is None:
        return M200PrintedIdentityState.MISSING_OFFICIAL_PRINTED_IDENTITY
    if printed == owner or _same_box_number(printed, owner.rsplit(":", 1)[-1]):
        return M200PrintedIdentityState.MATCHES_MAP_OWNER
    if proposal is not None and _same_box_number(printed, proposal.rsplit(":", 1)[-1]):
        return M200PrintedIdentityState.MATCHES_IDENTITY_PROPOSAL
    return M200PrintedIdentityState.CONFLICTS_WITH_MAP_OWNER


def printed_target_number(field: RecordDesignIntermediateField) -> str | None:
    """Return the single bracketed printed box number, whatever its digit count."""
    matches = _PRINTED_NUMBER.findall(field.normalized_description)
    return str(matches[0]) if len(matches) == 1 else None


def _serialise(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _serialise(item) for key, item in asdict(value).items()}
    if isinstance(value, tuple):
        return [_serialise(item) for item in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
