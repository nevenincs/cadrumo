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
    "classify_m200_casilla_candidates",
    "main",
    "render_m200_casilla_candidates_toml",
]


class M200CasillaDisposition(StrEnum):
    """Review outcomes that make no legal or registry-schema inference."""

    EXISTING_IDENTITY = "existing_identity"
    SEGMENT_QUALIFIED_IDENTITY = "segment_qualified_identity"
    REVISION_MISSING_DECLARATION = "revision_missing_declaration"
    NON_CASILLA = "non_casilla"
    UNRESOLVED = "unresolved"


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


def main(argv: list[str] | None = None) -> int:
    """Classify the bundled M200 designs and optionally manage a review file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="explicit path for deterministic review TOML")
    parser.add_argument("--check", action="store_true", help="compare --output without writing")
    args = parser.parse_args(argv)
    if args.check and args.output is None:
        parser.error("--check requires --output")

    candidates = _load_bundled_candidates()
    counts = Counter(candidate.disposition.value for candidate in candidates)
    print(f"total={len(candidates)}")
    for disposition in M200CasillaDisposition:
        print(f"{disposition.value}={counts[disposition.value]}")
    unresolved_reasons = Counter(
        candidate.reason for candidate in candidates if candidate.disposition is M200CasillaDisposition.UNRESOLVED
    )
    for reason, count in sorted(unresolved_reasons.items()):
        print(f"unresolved[{reason}]={count}")

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
