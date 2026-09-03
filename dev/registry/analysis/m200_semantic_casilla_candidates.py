"""Fail-closed review candidates for unresolved Modelo 200 semantic tokens.

This analysis does not author registry declarations.  It compares two pinned
official designs and their reviewed semantic maps, and reports only identities
proved by their complete exact parser anchor.
"""

from __future__ import annotations

import argparse
import os
import re
import tempfile
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

import rtoml

from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.loader import load_catalogue_file, load_modelo_directory

from ..pipeline._record_design_ir import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    intermediate_anchor_key,
    load_record_design_intermediate,
)
from ..pipeline._semantic_map import SemanticMap, SemanticMapEntry, semantic_anchor_key
from ..pipeline._semantic_map_loader import load_semantic_map

__all__ = [
    "M200CasillaCandidate",
    "M200CasillaDisposition",
    "M200MapOwnerIdentityDisposition",
    "M200OrphanDisposition",
    "M200PrintedIdentityDiagnostic",
    "M200PrintedIdentityState",
    "M200TargetIdentityWorklist",
    "classify_m200_casilla_candidates",
    "classify_m200_target_identities",
    "load_bundled_m200_target_identity_worklist",
    "main",
    "render_m200_casilla_candidates_toml",
    "render_m200_target_identity_worklist_toml",
]


TARGET_SOURCE_REF = "aeat-dr-200-2024"
TARGET_SOURCE_SHA256 = "ed4df89a451abc2184bc60a1d13ff53a3d38e9a6201698fb635cf0b8ee455218"


class M200CasillaDisposition(StrEnum):
    """Review outcomes that make no legal or registry-schema inference."""

    EXISTING_IDENTITY = "existing_identity"
    SEGMENT_QUALIFIED_IDENTITY = "segment_qualified_identity"
    REVISION_MISSING_DECLARATION = "revision_missing_declaration"
    NON_CASILLA = "non_casilla"
    UNRESOLVED = "unresolved"


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


@dataclass(frozen=True, slots=True)
class M200CasillaCandidate:
    """One source-pinned review row; never a registry declaration."""

    export_field_id: str
    authored_token: str
    disposition: M200CasillaDisposition
    reason: str
    source_ref: str
    source_sha256: str
    sibling_source_ref: str
    sibling_source_sha256: str
    sheet: str
    record_identity: str
    source_row: int
    source_cell: str | None
    ordinal: str | None
    offset: int
    length: int
    aeat_type: str
    label: str
    proposed_casilla_id: str | None = None
    proposed_kind: str | None = None
    registry_data_type: None = None
    legal_refs: None = None


def classify_m200_casilla_candidates(
    target_map: SemanticMap,
    target_design: RecordDesignIntermediate,
    *,
    target_casilla_ids: frozenset[CasillaId],
    sibling_map: SemanticMap,
    sibling_design: RecordDesignIntermediate,
    sibling_casilla_ids: frozenset[CasillaId],
    target_ids_by_number: Mapping[str, tuple[CasillaId, ...]] | None = None,
) -> tuple[M200CasillaCandidate, ...]:
    """Classify unresolved target tokens using exact official sibling evidence.

    Numeric tokens having a unique target-revision zero-padding resolution are
    already handled by the semantic compiler and therefore omitted here.
    """
    target_fields = _field_index(target_design)
    sibling_fields = _field_index(sibling_design)
    sibling_entries = {semantic_anchor_key(entry.anchor): entry for entry in sibling_map.entries}
    candidates: list[M200CasillaCandidate] = []
    for entry in target_map.entries:
        token = entry.casilla_id
        if token is None or token in target_casilla_ids or _unique_left_pad(token, target_casilla_ids) is not None:
            continue
        key = semantic_anchor_key(entry.anchor)
        field = target_fields[key]
        sibling_field = sibling_fields.get(key)
        sibling_entry = sibling_entries.get(key)
        disposition, reason, proposed_id, proposed_kind = _classify_sibling(
            field,
            sibling_field,
            sibling_entry,
            authored_token=token,
            target_ids_by_number=target_ids_by_number or {},
        )
        candidates.append(
            M200CasillaCandidate(
                export_field_id=str(entry.export_field_id),
                authored_token=str(token),
                disposition=disposition,
                reason=reason,
                source_ref=str(target_design.source.source_ref),
                source_sha256=target_design.source.source_sha256,
                sibling_source_ref=str(sibling_design.source.source_ref),
                sibling_source_sha256=sibling_design.source.source_sha256,
                sheet=field.sheet,
                record_identity=field.record_identity,
                source_row=field.source_row,
                source_cell=field.source_cell,
                ordinal=field.ordinal,
                offset=field.offset,
                length=field.length,
                aeat_type=field.aeat_type,
                label=field.normalized_description,
                proposed_casilla_id=proposed_id,
                proposed_kind=proposed_kind,
            ),
        )
    return tuple(
        sorted(candidates, key=lambda row: (row.sheet, row.source_row, row.ordinal or "", row.export_field_id))
    )


def render_m200_casilla_candidates_toml(candidates: tuple[M200CasillaCandidate, ...]) -> str:
    """Render deterministic review evidence, excluding absent optional values."""
    rows = [
        {
            key: value.value if isinstance(value, StrEnum) else value
            for key, value in asdict(candidate).items()
            if value is not None
        }
        for candidate in candidates
    ]
    return rtoml.dumps({"schema_version": 1, "candidate": rows}, pretty=True)


def classify_m200_target_identities(
    target_map: SemanticMap,
    target_design: RecordDesignIntermediate,
    *,
    target_declarations: Mapping[CasillaId, object],
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
        kind = _semantic_kind(entry)
        owner = entry.casilla_id
        if kind != CasillaFieldKind.CASILLA.value:
            if owner is not None:
                raise ValueError(f"non-casilla map entry {entry.export_field_id!r} declares casilla ownership")
            continue
        if owner is None:
            raise ValueError(f"casilla map entry {entry.export_field_id!r} omits its owner")
        owner = str(owner)
        printed = _printed_number(field)
        if owner in known_ids:
            map_owner_ids.add(owner)
            printed_state = _printed_identity_state(printed, owner, proposal=None)
            if printed_state is not M200PrintedIdentityState.MATCHES_MAP_OWNER:
                diagnostics.append(
                    M200PrintedIdentityDiagnostic(
                        export_field_id=str(entry.export_field_id),
                        anchor=semantic_anchor_key(entry.anchor),
                        declared_map_owner=owner,
                        printed_number=printed,
                        state=printed_state,
                        source_ref=TARGET_SOURCE_REF,
                        source_sha256=TARGET_SOURCE_SHA256,
                    ),
                )
            continue

        disposition, proposed = _classify_noncanonical_map_owner(
            owner,
            field=field,
            known_ids=known_ids,
        )
        printed_state = _printed_identity_state(printed, owner, proposal=proposed)
        if printed_state is not M200PrintedIdentityState.MATCHES_IDENTITY_PROPOSAL:
            raise ValueError(
                f"target anchor {entry.export_field_id!r} does not prove its proposed map-owner identity",
            )
        mismatches.append(
            M200MapOwnerIdentity(
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
            ),
        )

    orphaned = tuple(
        M200OrphanedDeclaration(
            casilla_id=str(casilla_id),
            disposition=M200OrphanDisposition.UNMAPPED_DECLARATION,
            source_refs=tuple(getattr(declaration, "source_refs")),
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


def render_m200_target_identity_worklist_toml(worklist: M200TargetIdentityWorklist) -> str:
    """Render deterministic source-anchor identity evidence without an apply path."""
    _require_worklist_source_identity(worklist)
    return rtoml.dumps(
        {
            "schema_version": 1,
            "modelo": "200",
            "revision": "2024",
            "source_ref": worklist.source_ref,
            "source_sha256": worklist.source_sha256,
            "semantic_map_source_ref": worklist.semantic_map_source_ref,
            "semantic_map_source_sha256": worklist.semantic_map_source_sha256,
            "map_owner_mismatch": [_serialise(row) for row in worklist.map_owner_mismatches],
            "orphaned_declaration": [_serialise(row) for row in worklist.orphaned_declarations],
            "printed_identity_diagnostic": [_serialise(row) for row in worklist.printed_identity_diagnostics],
        },
        pretty=True,
    )


def main(argv: list[str] | None = None) -> int:
    """Classify the bundled M200 designs and optionally manage a review file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="explicit path for deterministic review TOML")
    parser.add_argument("--check", action="store_true", help="compare --output without writing")
    args = parser.parse_args(argv)
    if args.check and args.output is None:
        parser.error("--check requires --output")

    candidates = _load_bundled_candidates()
    worklist = load_bundled_m200_target_identity_worklist()
    counts = Counter(candidate.disposition.value for candidate in candidates)
    print(f"total={len(candidates)}")
    for disposition in M200CasillaDisposition:
        print(f"{disposition.value}={counts[disposition.value]}")
    unresolved_reasons = Counter(
        candidate.reason for candidate in candidates if candidate.disposition is M200CasillaDisposition.UNRESOLVED
    )
    for reason, count in sorted(unresolved_reasons.items()):
        print(f"unresolved[{reason}]={count}")
    print(f"map_owner_mismatches={len(worklist.map_owner_mismatches)}")
    for disposition in M200MapOwnerIdentityDisposition:
        print(
            f"map_owner_{disposition.value}="
            f"{sum(row.disposition is disposition for row in worklist.map_owner_mismatches)}",
        )
    print(f"orphaned_declarations={len(worklist.orphaned_declarations)}")
    print(f"printed_identity_diagnostics={len(worklist.printed_identity_diagnostics)}")

    rendered = render_m200_casilla_candidates_toml(candidates)
    if args.output is None:
        return 0
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != rendered:
            print(f"stale={args.output}")
            return 1
        print(f"current={args.output}")
        return 0
    _atomic_write(args.output, rendered)
    print(f"wrote={args.output}")
    return 0


def _load_bundled_candidates() -> tuple[M200CasillaCandidate, ...]:
    source_root = bundled_path()
    registry_root = bundled_path("registry", "aeat")
    modelo = load_modelo_directory(registry_root / "modelos" / "200")
    catalogues = load_catalogue_file(registry_root / "legal" / "is.toml")
    target = modelo.revisions["2024"]
    sibling = modelo.revisions["2025-y-siguientes"]
    target_source = _record_design_source(target.source_refs, catalogues.sources)
    sibling_source = _record_design_source(sibling.source_refs, catalogues.sources)
    target_epoch = catalogues.sources[target_source].record_design_epoch
    sibling_epoch = catalogues.sources[sibling_source].record_design_epoch
    if target_epoch is None or sibling_epoch is None:
        raise ValueError("M200 record-design sources must declare epochs")
    target_design = load_record_design_intermediate(
        source_root,
        catalogues.sources,
        source_ref=target_source,
        filing_year=target.valid_from.year,
        design_epoch=target_epoch,
    )
    sibling_design = load_record_design_intermediate(
        source_root,
        catalogues.sources,
        source_ref=sibling_source,
        filing_year=sibling.valid_from.year,
        design_epoch=sibling_epoch,
    )
    ids_by_number: dict[str, list[CasillaId]] = {}
    for declaration in target.casillas:
        ids_by_number.setdefault(declaration.number, []).append(declaration.id)
    return classify_m200_casilla_candidates(
        load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / target_epoch),
        target_design,
        target_casilla_ids=frozenset(declaration.id for declaration in target.casillas),
        sibling_map=load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / sibling_epoch),
        sibling_design=sibling_design,
        sibling_casilla_ids=frozenset(declaration.id for declaration in sibling.casillas),
        target_ids_by_number={number: tuple(ids) for number, ids in ids_by_number.items()},
    )


def load_bundled_m200_target_identity_worklist() -> M200TargetIdentityWorklist:
    """Load the complete 2024 target-only map-owner and orphan worklist."""
    from .m200_restored_semantic_audit import _candidate_payloads

    source_root = bundled_path()
    registry_root = bundled_path("registry", "aeat")
    modelo = load_modelo_directory(registry_root / "modelos" / "200")
    target = modelo.revisions["2024"]
    catalogues = load_catalogue_file(registry_root / "legal" / "is.toml")
    target_source = _record_design_source(target.source_refs, catalogues.sources)
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
        target_candidate_ids=frozenset(_candidate_payloads()),
    )


def _record_design_source(source_refs: tuple[str, ...], sources: Mapping[str, object]) -> str:
    matches = tuple(
        source_ref for source_ref in source_refs if getattr(sources.get(source_ref), "kind", None) == "record_design"
    )
    if len(matches) != 1:
        raise ValueError(f"M200 revision must have exactly one record-design source, found {matches!r}")
    return str(matches[0])


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(text)
    os.replace(temporary, path)


def _field_index(design: RecordDesignIntermediate) -> dict[tuple[object, ...], RecordDesignIntermediateField]:
    return {intermediate_anchor_key(field): field for sheet in design.sheets for field in sheet.fields}


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
    target_fields = _field_index(target_design)
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


def _serialise(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {key: _serialise(item) for key, item in asdict(value).items()}
    if isinstance(value, tuple):
        return [_serialise(item) for item in value]
    return value


def _classify_sibling(
    target_field: RecordDesignIntermediateField,
    sibling_field: RecordDesignIntermediateField | None,
    sibling_entry: SemanticMapEntry | None,
    *,
    authored_token: CasillaId,
    target_ids_by_number: Mapping[str, tuple[CasillaId, ...]],
) -> tuple[M200CasillaDisposition, str, str | None, str | None]:
    printed_number = _printed_number(target_field)
    if printed_number is None or printed_number.lstrip("0") != authored_token.lstrip("0"):
        return (
            M200CasillaDisposition.UNRESOLVED,
            "current official printed number disagrees with authored token",
            None,
            None,
        )
    target_ids = tuple(
        identifier
        for number, identifiers in target_ids_by_number.items()
        if number.lstrip("0") == printed_number.lstrip("0")
        for identifier in identifiers
    )
    unqualified = tuple(identifier for identifier in target_ids if ":" not in identifier)
    qualified = tuple(identifier for identifier in target_ids if ":" in identifier)
    if qualified:
        return (
            M200CasillaDisposition.SEGMENT_QUALIFIED_IDENTITY,
            "official number has segment-qualified target identities; ownership cannot be inferred",
            str(qualified[0]) if len(qualified) == 1 else None,
            None,
        )
    if len(unqualified) == 1:
        return (
            M200CasillaDisposition.EXISTING_IDENTITY,
            "current official printed identity exists in the target revision",
            str(unqualified[0]),
            None,
        )
    if len(unqualified) > 1:
        return M200CasillaDisposition.UNRESOLVED, "current official printed identity is ambiguous", None, None
    return (
        M200CasillaDisposition.REVISION_MISSING_DECLARATION,
        "current official printed identity is absent from the target revision",
        printed_number,
        None,
    )


def _unique_left_pad(token: CasillaId, casilla_ids: frozenset[CasillaId]) -> CasillaId | None:
    if not token.isdecimal():
        return None
    candidates = tuple(
        candidate
        for candidate in casilla_ids
        if candidate.isdecimal()
        and len(candidate) > len(token)
        and candidate.endswith(token)
        and set(candidate[: -len(token)]) == {"0"}
    )
    return candidates[0] if len(candidates) == 1 else None


def _printed_number(field: RecordDesignIntermediateField) -> str | None:
    matches = re.findall(r"\[([0-9]{1,5})\]", field.normalized_description)
    return matches[0] if len(matches) == 1 and field.aeat_type == "Num" else None


if __name__ == "__main__":
    raise SystemExit(main())
