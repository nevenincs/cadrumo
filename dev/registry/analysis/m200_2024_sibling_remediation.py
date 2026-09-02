"""Fail-closed, source-pinned remediation proposals for Modelo 200 (2024).

This is deliberately a development generator, not a registry writer.  It may
derive an in-memory declaration only when the 2024 official field is identical
to the 2025 sibling field and every inherited authority fact covers 2024.  A
caller must still route its output through the normal reviewed-fragment and
generated-tree publication flow.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path

from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.loader import load_catalogue_file, load_modelo_directory
from cadrumo.domain.calculations.registry.schema_references import governed_period_span
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..pipeline._record_design_ir import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    intermediate_anchor_key,
    load_record_design_intermediate,
)
from ..pipeline._semantic_map import SemanticMap, SemanticMapEntry, semantic_anchor_key
from ..pipeline._semantic_map_loader import load_semantic_map
from .m200_semantic_casilla_candidates import (
    M200CasillaDisposition,
    _record_design_source,
    classify_m200_casilla_candidates,
)

__all__ = [
    "M200RemediationDisposition",
    "M200RemediationProposal",
    "derive_m200_2024_sibling_remediation",
    "load_bundled_m200_2024_sibling_remediation",
    "main",
]


class M200RemediationDisposition(StrEnum):
    """The only outputs this generator is permitted to make."""

    DERIVE_DECLARATION = "derive_declaration"
    CORRECT_SEMANTIC_MAP = "correct_semantic_map"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class M200RemediationProposal:
    """One deterministic proposal or an explicit refusal reason.

    ``casilla`` and ``semantic_entry`` are in-memory typed objects on purpose:
    this tool cannot silently choose an authoritative fragment or publish one.
    """

    disposition: M200RemediationDisposition
    export_field_id: str
    reason: str
    casilla: CasillaDefinition | None = None
    semantic_entry: SemanticMapEntry | None = None


def derive_m200_2024_sibling_remediation(
    *,
    target_map: SemanticMap,
    target_design: RecordDesignIntermediate,
    target_casillas: tuple[CasillaDefinition, ...],
    target_valid_from: date,
    target_valid_to: date | None,
    sibling_map: SemanticMap,
    sibling_design: RecordDesignIntermediate,
    sibling_casillas: tuple[CasillaDefinition, ...],
    legal_catalogue: Mapping[str, object],
    source_catalogue: Mapping[str, object],
) -> tuple[M200RemediationProposal, ...]:
    """Propose only exact, independently 2024-valid sibling remediation.

    The checks intentionally exceed the initial classifier: equal parser
    anchors are not enough.  The complete parser field must be equal, the
    sibling semantic identity must be authoritative, all inherited legal and
    source evidence must cover the full 2024 revision, and a copied record
    design source is rebound to the exact pinned 2024 binary.
    """
    target_by_id = {item.id: item for item in target_casillas}
    sibling_by_id = {item.id: item for item in sibling_casillas}
    target_fields = _field_index(target_design)
    sibling_fields = _field_index(sibling_design)
    target_entries = {semantic_anchor_key(item.anchor): item for item in target_map.entries}
    sibling_entries = {semantic_anchor_key(item.anchor): item for item in sibling_map.entries}
    ids_by_number: dict[str, list[CasillaId]] = {}
    for casilla in target_casillas:
        ids_by_number.setdefault(casilla.number, []).append(casilla.id)
    candidates = classify_m200_casilla_candidates(
        target_map,
        target_design,
        target_casilla_ids=frozenset(target_by_id),
        sibling_map=sibling_map,
        sibling_design=sibling_design,
        sibling_casilla_ids=frozenset(sibling_by_id),
        target_ids_by_number={number: tuple(ids) for number, ids in ids_by_number.items()},
    )
    proposals: list[M200RemediationProposal] = []
    for candidate in candidates:
        if candidate.disposition not in {
            M200CasillaDisposition.REVISION_MISSING_DECLARATION,
            M200CasillaDisposition.NON_CASILLA,
            M200CasillaDisposition.SEGMENT_QUALIFIED_IDENTITY,
            M200CasillaDisposition.UNRESOLVED,
        }:
            continue
        key = (
            candidate.sheet,
            candidate.source_row,
            candidate.source_cell,
            candidate.ordinal,
            candidate.record_identity,
        )
        target_field = target_fields[key]
        sibling_field = sibling_fields.get(key)
        target_entry = target_entries[key]
        sibling_entry = sibling_entries.get(key)
        if candidate.disposition is M200CasillaDisposition.REVISION_MISSING_DECLARATION:
            sibling_id = sibling_entry.casilla_id if sibling_entry is not None else None
            sibling_casilla = sibling_by_id.get(sibling_id) if sibling_id is not None else None
            refusal = _shared_refusal(
                target_field,
                sibling_field,
                target_entry,
                sibling_entry,
                target_valid_from,
                target_valid_to,
                legal_catalogue,
                source_catalogue,
                target_design.source.source_ref,
                sibling_design.source.source_ref,
            )
            if sibling_casilla is None:
                refusal = refusal or "sibling declaration is not authoritative"
            elif sibling_id != target_entry.casilla_id:
                refusal = refusal or "sibling canonical casilla identity differs from the target semantic identity"
            else:
                rebound = _rebind_casilla_sources(
                    sibling_casilla,
                    target_design_source=str(target_design.source.source_ref),
                    sibling_design_source=str(sibling_design.source.source_ref),
                    valid_from=target_valid_from,
                    valid_to=target_valid_to,
                    legal_catalogue=legal_catalogue,
                    source_catalogue=source_catalogue,
                )
                if rebound is None:
                    refusal = refusal or "inherited declaration legal/source/type facts do not independently cover 2024"
            if refusal is None:
                proposals.append(
                    M200RemediationProposal(
                        M200RemediationDisposition.DERIVE_DECLARATION,
                        candidate.export_field_id,
                        "exact full field signature and 2024 authority coverage; record-design source rebound",
                        casilla=rebound,
                    )
                )
            else:
                proposals.append(
                    M200RemediationProposal(M200RemediationDisposition.UNRESOLVED, candidate.export_field_id, refusal)
                )
            continue
        if candidate.disposition is M200CasillaDisposition.NON_CASILLA:
            refusal = _shared_refusal(
                target_field,
                sibling_field,
                target_entry,
                sibling_entry,
                target_valid_from,
                target_valid_to,
                legal_catalogue,
                source_catalogue,
                target_design.source.source_ref,
                sibling_design.source.source_ref,
            )
            if sibling_entry is None or sibling_entry.kind is CasillaFieldKind.CASILLA:
                refusal = refusal or "sibling non-casilla semantic fact is absent"
            corrected = (
                None
                if sibling_entry is None
                else _rebind_semantic_entry(
                    sibling_entry,
                    target_entry=target_entry,
                    target_design_source=str(target_design.source.source_ref),
                    sibling_design_source=str(sibling_design.source.source_ref),
                    valid_from=target_valid_from,
                    valid_to=target_valid_to,
                    legal_catalogue=legal_catalogue,
                    source_catalogue=source_catalogue,
                )
            )
            if corrected is None:
                refusal = refusal or "inherited semantic-map legal/source facts do not independently cover 2024"
            if refusal is None:
                proposals.append(
                    M200RemediationProposal(
                        M200RemediationDisposition.CORRECT_SEMANTIC_MAP,
                        candidate.export_field_id,
                        "exact full field signature and 2024 authority coverage; semantic source rebound",
                        semantic_entry=corrected,
                    )
                )
            else:
                proposals.append(
                    M200RemediationProposal(M200RemediationDisposition.UNRESOLVED, candidate.export_field_id, refusal)
                )
            continue
        # The generator must not manufacture facts for 2024-only or segment
        # ownership cases.  They remain auditable, explicit work items.
        proposals.append(
            M200RemediationProposal(M200RemediationDisposition.UNRESOLVED, candidate.export_field_id, candidate.reason)
        )
    return tuple(sorted(proposals, key=lambda item: item.export_field_id))


def _field_index(design: RecordDesignIntermediate) -> dict[tuple[object, ...], RecordDesignIntermediateField]:
    return {intermediate_anchor_key(field): field for sheet in design.sheets for field in sheet.fields}


def _shared_refusal(
    target_field: RecordDesignIntermediateField,
    sibling_field: RecordDesignIntermediateField | None,
    target_entry: SemanticMapEntry,
    sibling_entry: SemanticMapEntry | None,
    valid_from: date,
    valid_to: date | None,
    legal_catalogue: Mapping[str, object],
    source_catalogue: Mapping[str, object],
    target_design_source: object,
    sibling_design_source: object,
) -> str | None:
    if sibling_field is None or sibling_entry is None:
        return "no exact sibling parser/semantic anchor"
    if intermediate_anchor_key(target_field) != intermediate_anchor_key(sibling_field):
        return "sibling parser anchor differs"
    if not _same_official_field_signature(target_field, sibling_field):
        return "sibling parser field signature differs"
    if not _refs_cover(
        sibling_entry.legal_refs, sibling_entry.source_refs, valid_from, valid_to, legal_catalogue, source_catalogue
    ):
        return "sibling semantic-map evidence does not cover 2024"
    if str(sibling_design_source) not in sibling_entry.source_refs:
        return "sibling semantic entry is not pinned to its official record-design source"
    if str(target_design_source) not in source_catalogue:
        return "target official record-design source is not catalogued"
    return None


def _rebind_casilla_sources(
    casilla: CasillaDefinition,
    *,
    target_design_source: str,
    sibling_design_source: str,
    valid_from: date,
    valid_to: date | None,
    legal_catalogue: Mapping[str, object],
    source_catalogue: Mapping[str, object],
) -> CasillaDefinition | None:
    if sibling_design_source not in casilla.source_refs:
        return None
    sources = tuple(target_design_source if item == sibling_design_source else item for item in casilla.source_refs)
    if target_design_source not in sources or len(set(sources)) != len(sources):
        return None
    if not _refs_cover(casilla.legal_refs, sources, valid_from, valid_to, legal_catalogue, source_catalogue):
        return None
    if casilla.constraints is not None and not _refs_cover(
        casilla.constraints.legal_refs,
        casilla.constraints.source_refs,
        valid_from,
        valid_to,
        legal_catalogue,
        source_catalogue,
    ):
        return None
    if any(
        not _refs_cover(alias.legal_refs, alias.source_refs, valid_from, valid_to, legal_catalogue, source_catalogue)
        for alias in casilla.aliases
    ):
        return None
    return casilla.model_copy(update={"source_refs": sources})


def _rebind_semantic_entry(
    entry: SemanticMapEntry,
    *,
    target_entry: SemanticMapEntry,
    target_design_source: str,
    sibling_design_source: str,
    valid_from: date,
    valid_to: date | None,
    legal_catalogue: Mapping[str, object],
    source_catalogue: Mapping[str, object],
) -> SemanticMapEntry | None:
    if sibling_design_source not in entry.source_refs:
        return None
    sources = tuple(target_design_source if item == sibling_design_source else item for item in entry.source_refs)
    if target_design_source not in sources or len(set(sources)) != len(sources):
        return None
    if not _refs_cover(entry.legal_refs, sources, valid_from, valid_to, legal_catalogue, source_catalogue):
        return None
    return entry.model_copy(
        update={"anchor": target_entry.anchor, "export_field_id": target_entry.export_field_id, "source_refs": sources}
    )


def _refs_cover(
    legal_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
    valid_from: date,
    valid_to: date | None,
    legal_catalogue: Mapping[str, object],
    source_catalogue: Mapping[str, object],
) -> bool:
    """Require full 2024 coverage; unknown or future-only evidence refuses."""
    for reference_id in legal_refs:
        reference = legal_catalogue.get(reference_id)
        if reference is None:
            return False
        begins, ends = governed_period_span(reference)  # type: ignore[arg-type]
        if begins > valid_from or (valid_to is not None and ends is not None and ends < valid_to):
            return False
    for reference_id in source_refs:
        source = source_catalogue.get(reference_id)
        if source is None:
            return False
        begins = getattr(source, "applies_from", None)
        ends = getattr(source, "applies_to", None)
        if begins is not None and begins > valid_from:
            return False
        if valid_to is not None and ends is not None and ends < valid_to:
            return False
    return True


def _same_official_field_signature(
    target: RecordDesignIntermediateField,
    sibling: RecordDesignIntermediateField,
) -> bool:
    """Compare every parser-owned field fact other than its source identity.

    The caller separately requires the complete anchor (sheet, row, cell,
    ordinal and record identity).  ``RecordDesignIntermediate`` itself embeds
    the different 2024/2025 source hashes at its root, so comparing models or
    any epoch-derived wrapper would make a genuine unchanged field look
    different merely because it was read from its own pinned official binary.
    """
    return (
        target.offset,
        target.length,
        target.aeat_type,
        target.normalized_description,
        target.validation,
        target.content,
    ) == (
        sibling.offset,
        sibling.length,
        sibling.aeat_type,
        sibling.normalized_description,
        sibling.validation,
        sibling.content,
    )


def load_bundled_m200_2024_sibling_remediation() -> tuple[M200RemediationProposal, ...]:
    """Run the proposal generator against the two pinned bundled M200 designs."""
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
    return derive_m200_2024_sibling_remediation(
        target_map=load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / target_epoch),
        target_design=target_design,
        target_casillas=target.casillas,
        target_valid_from=target.valid_from,
        target_valid_to=target.valid_to,
        sibling_map=load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / sibling_epoch),
        sibling_design=sibling_design,
        sibling_casillas=sibling.casillas,
        legal_catalogue=catalogues.legal,
        source_catalogue=catalogues.sources,
    )


def main() -> int:
    """Print proposal/refusal counts without mutating registry authority."""
    from collections import Counter

    proposals = load_bundled_m200_2024_sibling_remediation()
    counts = Counter(item.disposition.value for item in proposals)
    print(f"total={len(proposals)}")
    for disposition in M200RemediationDisposition:
        print(f"{disposition.value}={counts[disposition.value]}")
    for reason, count in sorted(
        Counter(item.reason for item in proposals if item.disposition is M200RemediationDisposition.UNRESOLVED).items()
    ):
        print(f"unresolved[{reason}]={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
