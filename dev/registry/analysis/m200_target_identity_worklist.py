"""Source-pinned review worklist for Modelo 200 target identity evidence."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass
from enum import StrEnum
from pathlib import Path

import rtoml

from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..compiler.loader import load_catalogue_file, load_modelo_directory
from ..pipeline.record_design_intermediate import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    load_record_design_intermediate,
)
from ..pipeline.semantic_map import SemanticMap, SemanticMapEntry, load_semantic_map, semantic_anchor_key
from .m200_record_design_support import record_design_field_index, record_design_source

__all__ = [
    "M200MapOwnerIdentityDisposition",
    "M200OrphanDisposition",
    "M200PrintedIdentityDiagnostic",
    "M200PrintedIdentityState",
    "M200TargetIdentityWorklist",
    "classify_m200_target_identities",
    "load_bundled_m200_target_identity_worklist",
    "main",
    "render_m200_target_identity_worklist_toml",
]


TARGET_SOURCE_REF = "aeat-dr-200-2024"
TARGET_SOURCE_SHA256 = "ed4df89a451abc2184bc60a1d13ff53a3d38e9a6201698fb635cf0b8ee455218"


class M200MapOwnerIdentityDisposition(StrEnum):
    """A source-anchor-only classification for a noncanonical map owner."""

    ZERO_PADDING_PROPOSAL = "zero_padding_proposal"
    SEGMENT_QUALIFIED_PROPOSAL = "segment_qualified_proposal"


class M200OrphanDisposition(StrEnum):
    """A closed disposition for a declaration that has no target map owner."""

    UNMAPPED_DECLARATION = "unmapped_declaration"


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
class M200TargetIdentityWorklist:
    """Complete, target-source-bound identity evidence with no authority mutation path."""

    source_ref: str
    source_sha256: str
    semantic_map_source_ref: str
    semantic_map_source_sha256: str
    map_owner_mismatches: tuple[M200MapOwnerIdentity, ...]
    orphaned_declarations: tuple[M200OrphanedDeclaration, ...]
    printed_identity_diagnostics: tuple[M200PrintedIdentityDiagnostic, ...]


def classify_m200_target_identities(
    target_map: SemanticMap,
    target_design: RecordDesignIntermediate,
    *,
    target_declarations: Mapping[CasillaId, CasillaDefinition],
    target_candidate_ids: frozenset[CasillaId],
) -> M200TargetIdentityWorklist:
    """Classify target map-owner identity drift without changing ownership.

    The 2024 design proves only the physical source anchor and its printed box
    number.  A padded or segment-qualified declaration-like token is retained
    as a non-authoritative proposal, never rewritten into the semantic map or
    promoted into a canonical declaration.
    """
    _require_target_source_identity(target_map, target_design)
    target_fields = _complete_target_field_index(target_map, target_design)
    declared_ids = frozenset(target_declarations)
    known_ids = declared_ids | target_candidate_ids
    mismatches: list[M200MapOwnerIdentity] = []
    diagnostics: list[M200PrintedIdentityDiagnostic] = []
    map_owner_ids: set[CasillaId] = set()

    for entry in target_map.entries:
        field = target_fields[semantic_anchor_key(entry.anchor)]
        mismatch, diagnostic, map_owner = _target_identity_entry_findings(
            entry,
            field=field,
            known_ids=known_ids,
            declared_ids=declared_ids,
        )
        if map_owner is not None:
            map_owner_ids.add(map_owner)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
        if mismatch is not None:
            mismatches.append(mismatch)

    orphaned = tuple(
        M200OrphanedDeclaration(
            casilla_id=str(casilla_id),
            disposition=M200OrphanDisposition.UNMAPPED_DECLARATION,
            source_refs=tuple(declaration.source_refs),
        )
        for casilla_id, declaration in sorted(target_declarations.items())
        if casilla_id not in map_owner_ids
    )
    return M200TargetIdentityWorklist(
        source_ref=TARGET_SOURCE_REF,
        source_sha256=TARGET_SOURCE_SHA256,
        semantic_map_source_ref=target_map.source_ref,
        semantic_map_source_sha256=target_map.source_sha256,
        map_owner_mismatches=tuple(sorted(mismatches, key=lambda item: item.export_field_id)),
        orphaned_declarations=orphaned,
        printed_identity_diagnostics=tuple(sorted(diagnostics, key=lambda item: item.export_field_id)),
    )


def _target_identity_entry_findings(
    entry: SemanticMapEntry,
    *,
    field: RecordDesignIntermediateField,
    known_ids: frozenset[CasillaId],
    declared_ids: frozenset[CasillaId],
) -> tuple[M200MapOwnerIdentity | None, M200PrintedIdentityDiagnostic | None, CasillaId | None]:
    kind = _semantic_kind(entry)
    owner = entry.casilla_id
    if kind != CasillaFieldKind.CASILLA.value:
        if owner is not None:
            raise ValueError(f"non-casilla map entry {entry.export_field_id!r} declares casilla ownership")
        return None, None, None
    if owner is None:
        raise ValueError(f"casilla map entry {entry.export_field_id!r} omits its owner")
    owner = str(owner)
    printed = _printed_target_number(field)
    if owner in known_ids:
        printed_state = _printed_identity_state(printed, owner, proposal=None)
        diagnostic = None
        if printed_state is not M200PrintedIdentityState.MATCHES_MAP_OWNER:
            diagnostic = M200PrintedIdentityDiagnostic(
                export_field_id=str(entry.export_field_id),
                anchor=semantic_anchor_key(entry.anchor),
                declared_map_owner=owner,
                printed_number=printed,
                state=printed_state,
                source_ref=TARGET_SOURCE_REF,
                source_sha256=TARGET_SOURCE_SHA256,
            )
        return None, diagnostic, owner

    disposition, proposed = _classify_noncanonical_map_owner(owner, field=field, known_ids=known_ids)
    printed_state = _printed_identity_state(printed, owner, proposal=proposed)
    if printed_state is not M200PrintedIdentityState.MATCHES_IDENTITY_PROPOSAL:
        raise ValueError(f"target anchor {entry.export_field_id!r} does not prove its proposed map-owner identity")
    # MATCHES_IDENTITY_PROPOSAL is only reachable when `printed` is not None:
    # `_printed_identity_state` returns MISSING_OFFICIAL_PRINTED_IDENTITY otherwise.
    if printed is None:
        raise ValueError("identity proposal requires an official printed identity")
    mismatch = M200MapOwnerIdentity(
        export_field_id=str(entry.export_field_id),
        anchor=semantic_anchor_key(entry.anchor),
        declared_map_owner=owner,
        disposition=disposition,
        proposed_target_identity_non_authoritative=proposed,
        proposed_identity_origin=("declared" if proposed in declared_ids else "candidate_non_authoritative"),
        printed_number=printed,
        printed_identity_state=printed_state,
        source_ref=TARGET_SOURCE_REF,
        source_sha256=TARGET_SOURCE_SHA256,
    )
    return mismatch, None, None


def render_m200_target_identity_worklist_toml(worklist: M200TargetIdentityWorklist) -> str:
    """Render deterministic source-anchor identity evidence without an apply path."""
    _require_worklist_source_identity(worklist)
    return rtoml.dumps(
        {
            "schema_version": 1,
            "authority_status": "proposal_only",
            "modelo": "200",
            "revision": "2024",
            "source_ref": worklist.source_ref,
            "source_sha256": worklist.source_sha256,
            "semantic_map_source_ref": worklist.semantic_map_source_ref,
            "semantic_map_source_sha256": worklist.semantic_map_source_sha256,
            "counts": {
                "map_owner_mismatches": len(worklist.map_owner_mismatches),
                "orphaned_declarations": len(worklist.orphaned_declarations),
                "printed_identity_diagnostics": len(worklist.printed_identity_diagnostics),
            },
            "map_owner_mismatch": [_serialise(row) for row in worklist.map_owner_mismatches],
            "orphaned_declaration": [_serialise(row) for row in worklist.orphaned_declarations],
            "printed_identity_diagnostic": [_serialise(row) for row in worklist.printed_identity_diagnostics],
        },
        pretty=True,
    )


def main(argv: list[str] | None = None) -> int:
    """Emit the complete proposal-only target identity worklist as TOML to stdout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    worklist = load_bundled_m200_target_identity_worklist()
    sys.stdout.write(render_m200_target_identity_worklist_toml(worklist))
    return 0


def load_bundled_m200_target_identity_worklist() -> M200TargetIdentityWorklist:
    """Load the complete 2024 target-only map-owner and orphan worklist."""
    source_root = bundled_path()
    registry_root = bundled_path("registry", "aeat")
    modelo = load_modelo_directory(registry_root / "modelos" / "200")
    target = modelo.revisions["2024"]
    catalogues = load_catalogue_file(registry_root / "legal" / "is.toml")
    target_source = record_design_source(target.source_refs, catalogues.sources)
    target_epoch = catalogues.sources[target_source].record_design_epoch
    if target_epoch is None:
        raise ValueError("M200 target record-design source must declare an epoch")
    target_design = load_record_design_intermediate(
        source_root,
        catalogues.sources,
        source_ref=target_source,
        filing_year=target.valid_from.year,
        design_epoch=target_epoch,
    )
    return classify_m200_target_identities(
        load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / target_epoch),
        target_design,
        target_declarations={declaration.id: declaration for declaration in target.casillas},
        target_candidate_ids=frozenset(),
    )


def _require_target_source_identity(target_map: SemanticMap, target_design: RecordDesignIntermediate) -> None:
    if (
        str(target_design.source.source_ref) != TARGET_SOURCE_REF
        or target_design.source.source_sha256 != TARGET_SOURCE_SHA256
        or target_map.source_ref != TARGET_SOURCE_REF
        or target_map.source_sha256 != TARGET_SOURCE_SHA256
    ):
        raise ValueError("M200 target source identity drifted")


def _require_worklist_source_identity(worklist: M200TargetIdentityWorklist) -> None:
    if (
        worklist.source_ref != TARGET_SOURCE_REF
        or worklist.source_sha256 != TARGET_SOURCE_SHA256
        or worklist.semantic_map_source_ref != TARGET_SOURCE_REF
        or worklist.semantic_map_source_sha256 != TARGET_SOURCE_SHA256
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


def _classify_noncanonical_map_owner(
    owner: str,
    *,
    field: RecordDesignIntermediateField,
    known_ids: frozenset[CasillaId],
) -> tuple[M200MapOwnerIdentityDisposition, str]:
    if not owner.isdecimal():
        raise ValueError(f"M200 casilla map owner {owner!r} is neither declared nor a numeric identity")
    padded = owner.zfill(5)
    candidates: list[tuple[M200MapOwnerIdentityDisposition, str]] = []
    if padded in known_ids:
        candidates.append((M200MapOwnerIdentityDisposition.ZERO_PADDING_PROPOSAL, padded))
    qualified = f"{field.record_identity}:{padded}"
    if qualified in known_ids:
        candidates.append((M200MapOwnerIdentityDisposition.SEGMENT_QUALIFIED_PROPOSAL, qualified))
    if len(candidates) != 1:
        raise ValueError(f"M200 casilla map owner {owner!r} has ambiguous or missing target identity")
    return candidates[0]


def _printed_identity_state(
    printed: str | None,
    owner: str,
    *,
    proposal: str | None,
) -> M200PrintedIdentityState:
    if printed is None:
        return M200PrintedIdentityState.MISSING_OFFICIAL_PRINTED_IDENTITY
    if printed == owner or (":" in owner and printed == owner.rsplit(":", 1)[-1]):
        return M200PrintedIdentityState.MATCHES_MAP_OWNER
    if proposal is not None and (printed == proposal or printed == proposal.rsplit(":", 1)[-1]):
        return M200PrintedIdentityState.MATCHES_IDENTITY_PROPOSAL
    return M200PrintedIdentityState.CONFLICTS_WITH_MAP_OWNER


def _printed_target_number(field: RecordDesignIntermediateField) -> str | None:
    """Return only the complete five-digit printed identity used by the 2024 census."""
    matches = [str(match) for match in re.findall(r"\[([0-9]{5})\]", field.normalized_description)]
    return matches[0] if len(matches) == 1 else None


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
