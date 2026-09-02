"""Target-first reconciliation census for every planned M200/2024 casilla and anchor."""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import rtoml

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.loader import load_catalogue_file, load_modelo_directory
from cadrumo.domain.calculations.registry.schema_references import governed_period_span

from ..pipeline._record_design_ir import intermediate_anchor_key, load_record_design_intermediate
from ..pipeline._semantic_map import semantic_anchor_key
from ..pipeline._semantic_map_loader import load_semantic_map
from .m200_restored_semantic_audit import SemanticPayload, _candidate_payloads, _payload, _template

TARGET_SOURCE_REF = "aeat-dr-200-2024"
TARGET_SOURCE_SHA256 = "ed4df89a451abc2184bc60a1d13ff53a3d38e9a6201698fb635cf0b8ee455218"
SIBLING_SOURCE_REF = "aeat-dr-200-2025"
TARGET_VALID_FROM = date(2024, 1, 1)
TARGET_VALID_TO = date(2024, 12, 31)
SIBLING_VALID_FROM = date(2025, 1, 1)


@dataclass(frozen=True, slots=True)
class M200TargetAnchorDisposition:
    """One exact target-design anchor and its non-lossy semantic-map disposition."""

    export_field_id: str
    anchor: tuple[object, ...]
    semantic_kind: str
    declared_map_owner: str | None
    printed_number: str | None
    resolved_owner_proposal_non_authoritative: str | None
    owner_state: str
    printed_identity_state: str
    official_description: str
    template: str
    aeat_type: str
    length: int
    source_refs: tuple[str, ...]
    legal_evidence_state: str
    applicable_legal_refs: tuple[str, ...]
    inapplicable_legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class M200ReconciliationRow:
    """Declaration or proposal evidence kept separate from exact anchor ownership."""

    casilla_id: str
    origin: str
    source_ref_state: str
    mechanical_source_refs_proposal: tuple[str, ...] | None
    identity_review_required: bool
    export_reachability: str
    declared_export_refs: tuple[str, ...]
    export_reciprocity: str
    fields: tuple[M200TargetAnchorDisposition, ...]
    proposed_fields_non_authoritative: tuple[M200TargetAnchorDisposition, ...]
    normalized_official_descriptions: tuple[str, ...]
    same_2024_template_state: str
    cross_revision_status: str
    cross_revision_proposal_non_authoritative: SemanticPayload | None
    legal_evidence_state: str
    applicable_legal_refs: tuple[str, ...]
    inapplicable_legal_refs: tuple[str, ...]
    declaration_payload: SemanticPayload | None
    candidate_payload_non_authoritative: SemanticPayload | None


@dataclass(frozen=True, slots=True)
class M200ReconciliationCensus:
    """Source-bound, complete reconciliation of declarations and target anchors."""

    source_ref: str
    source_sha256: str
    semantic_map_source_ref: str
    semantic_map_source_sha256: str
    revision_valid_from: date
    revision_valid_to: date
    rows: tuple[M200ReconciliationRow, ...]
    anchors: tuple[M200TargetAnchorDisposition, ...]


def reconcile_bundled_m200_2024() -> M200ReconciliationCensus:
    """Build the complete source-SHA-bound planned-revision reconciliation."""
    registry_root = bundled_path("registry", "aeat")
    modelo = load_modelo_directory(registry_root / "modelos" / "200")
    revision = modelo.revisions["2024"]
    sibling = modelo.revisions["2025-y-siguientes"]
    parts = tuple(load_catalogue_file(path) for path in sorted((registry_root / "legal").glob("*.toml")))
    sources = _merge_unique_catalogue(parts, attribute="sources")
    legal = _merge_unique_catalogue(parts, attribute="legal")
    _require_partition(revision, sibling)
    source = sources.get(TARGET_SOURCE_REF)
    if source is None:
        raise RegistryValidationError(f"missing target record-design source {TARGET_SOURCE_REF!r}")
    _require_exact_source_identity("source catalogue", str(source.id), source.sha256)

    target_design = load_record_design_intermediate(
        bundled_path(), sources, source_ref=TARGET_SOURCE_REF, filing_year=2024, design_epoch="2024"
    )
    target_map = load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / "2024")
    _require_exact_source_identity(
        "record-design intermediate", str(target_design.source.source_ref), target_design.source.source_sha256
    )
    _require_exact_source_identity("semantic map", target_map.source_ref, target_map.source_sha256)
    _require_entry_source_refs(target_map.entries)

    candidate_documents = _candidate_payloads()
    candidate_ids = frozenset(candidate_documents)
    declaration_ids = tuple(str(item.id) for item in revision.casillas)
    _require_unique_identifiers(declaration_ids, label="current declaration")
    _require_disjoint_ids(frozenset(declaration_ids), candidate_ids)
    current_declarations = {str(item.id): item for item in revision.casillas}
    current = {identifier: _payload(item) for identifier, item in current_declarations.items()}
    candidates = {identifier: payload for identifier, (_path, payload) in candidate_documents.items()}
    planned_ids = frozenset((*current, *candidates))

    design_fields = tuple(field for sheet in target_design.sheets for field in sheet.fields)
    design_keys = tuple(intermediate_anchor_key(field) for field in design_fields)
    map_keys = tuple(semantic_anchor_key(entry.anchor) for entry in target_map.entries)
    export_ids = tuple(str(entry.export_field_id) for entry in target_map.entries)
    _require_anchor_bijection(design_keys=design_keys, map_keys=map_keys, export_ids=export_ids)
    target_fields = dict(zip(design_keys, design_fields, strict=True))

    anchors = tuple(
        _classify_anchor(
            entry,
            target_fields[semantic_anchor_key(entry.anchor)],
            planned_ids=planned_ids,
            legal=legal,
            valid_from=revision.valid_from,
            valid_to=revision.valid_to,
        )
        for entry in target_map.entries
    )
    exact_ownership: dict[str, list[M200TargetAnchorDisposition]] = defaultdict(list)
    proposed_ownership: dict[str, list[M200TargetAnchorDisposition]] = defaultdict(list)
    for anchor in anchors:
        if anchor.owner_state == "exact_planned_owner":
            if anchor.declared_map_owner is None:
                raise RegistryValidationError("exact target owner disposition omitted its declared owner")
            exact_ownership[anchor.declared_map_owner].append(anchor)
        elif anchor.resolved_owner_proposal_non_authoritative is not None:
            proposed_ownership[anchor.resolved_owner_proposal_non_authoritative].append(anchor)

    template_payloads = _trusted_template_payloads(exact_ownership, current)

    cross_index = _cross_revision_index(
        sibling=sibling,
        sources=sources,
        legal=legal,
        valid_from=revision.valid_from,
        valid_to=revision.valid_to,
    )
    rows: list[M200ReconciliationRow] = []
    for identifier in sorted(planned_ids):
        is_candidate = identifier in candidates
        payload = candidates[identifier] if is_candidate else current[identifier]
        fields = tuple(sorted(exact_ownership.get(identifier, ()), key=lambda item: item.export_field_id))
        proposed_fields = tuple(
            sorted(proposed_ownership.get(identifier, ()), key=lambda item: item.export_field_id)
        )
        if is_candidate:
            source_state, source_proposal = "candidate_non_authoritative", None
        elif not fields:
            source_state, source_proposal = "unmapped_no_rebind", None
        else:
            source_state, source_proposal = _source_ref_state(payload)
        identity_review_required = any(
            field.printed_identity_state != "matches_declared_owner" for field in fields
        )
        applicable, inapplicable, legal_state = _legal_evidence(
            payload.legal_refs, legal, revision.valid_from, revision.valid_to
        )
        declared_export_refs = tuple(current_declarations[identifier].export_refs) if not is_candidate else ()
        generated_refs = tuple(field.export_field_id for field in fields)
        reciprocity = (
            "proposal_only"
            if is_candidate
            else "unmapped_no_reciprocity"
            if not fields
            else "complete"
            if declared_export_refs == generated_refs
            else "generator_pending"
        )
        evidence_fields = (*fields, *proposed_fields)
        cross_payloads = {
            proposal
            for field in evidence_fields
            for sibling_anchor, proposal in cross_index.get((field.template, field.aeat_type, field.length), ())
            if sibling_anchor != field.anchor
        }
        cross_status = (
            "unique_non_authoritative"
            if len(cross_payloads) == 1
            else "conflicting_non_authoritative"
            if len(cross_payloads) > 1
            else "no_applicable_match"
        )
        rows.append(
            M200ReconciliationRow(
                casilla_id=identifier,
                origin="restoration_candidate" if is_candidate else "current_declaration",
                source_ref_state=source_state,
                mechanical_source_refs_proposal=source_proposal,
                identity_review_required=identity_review_required,
                export_reachability=(
                    "mapped_exact_owner"
                    if fields
                    else "identity_mismatch_proposal"
                    if proposed_fields
                    else "unmapped_calculation_only"
                ),
                declared_export_refs=declared_export_refs,
                export_reciprocity=reciprocity,
                fields=fields,
                proposed_fields_non_authoritative=proposed_fields,
                normalized_official_descriptions=tuple(field.official_description for field in evidence_fields),
                same_2024_template_state=_same_year_state(payload, evidence_fields, template_payloads),
                cross_revision_status=cross_status,
                cross_revision_proposal_non_authoritative=(
                    next(iter(cross_payloads)) if len(cross_payloads) == 1 else None
                ),
                legal_evidence_state=legal_state,
                applicable_legal_refs=applicable,
                inapplicable_legal_refs=inapplicable,
                declaration_payload=None if is_candidate else payload,
                candidate_payload_non_authoritative=payload if is_candidate else None,
            )
        )
    return M200ReconciliationCensus(
        source_ref=TARGET_SOURCE_REF,
        source_sha256=TARGET_SOURCE_SHA256,
        semantic_map_source_ref=target_map.source_ref,
        semantic_map_source_sha256=target_map.source_sha256,
        revision_valid_from=revision.valid_from,
        revision_valid_to=revision.valid_to,
        rows=tuple(rows),
        anchors=tuple(sorted(anchors, key=lambda item: item.export_field_id)),
    )


def render_reconciliation_toml(census: M200ReconciliationCensus) -> str:
    """Render a deterministic report only for the exact frozen target source."""
    _require_exact_source_identity("reconciliation census", census.source_ref, census.source_sha256)
    _require_exact_source_identity(
        "reconciliation semantic map", census.semantic_map_source_ref, census.semantic_map_source_sha256
    )
    if (census.revision_valid_from, census.revision_valid_to) != (TARGET_VALID_FROM, TARGET_VALID_TO):
        raise RegistryValidationError("reconciliation census carries a drifted Modelo 200/2024 partition")
    return rtoml.dumps(
        _toml_order(
            {
                "schema_version": 2,
                "modelo": "200",
                "revision": "2024",
                "source_ref": census.source_ref,
                "source_sha256": census.source_sha256,
                "semantic_map_source_ref": census.semantic_map_source_ref,
                "semantic_map_source_sha256": census.semantic_map_source_sha256,
                "revision_valid_from": census.revision_valid_from.isoformat(),
                "revision_valid_to": census.revision_valid_to.isoformat(),
                "row": [_serialise(row) for row in census.rows],
                "anchor": [asdict(anchor) for anchor in census.anchors],
            }
        ),
        pretty=True,
    )


def main(argv: list[str] | None = None) -> int:
    """Print counts or the full deterministic TOML report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toml", action="store_true")
    args = parser.parse_args(argv)
    census = reconcile_bundled_m200_2024()
    if args.toml:
        sys.stdout.write(render_reconciliation_toml(census))
        return 0
    rows = census.rows
    anchors = census.anchors
    print(f"total={len(rows)}")
    print(f"current={sum(row.origin == 'current_declaration' for row in rows)}")
    print(f"candidates={sum(row.origin == 'restoration_candidate' for row in rows)}")
    print(f"target_anchors={len(anchors)}")
    for state in (
        "exact_planned_owner",
        "zero_padding_mismatch_refused",
        "qualified_identity_mismatch_refused",
        "unknown_map_owner_refused",
        "non_casilla",
    ):
        print(f"anchor_{state}={sum(anchor.owner_state == state for anchor in anchors)}")
    for state in (
        "current_design",
        "mechanical_rebind",
        "mixed_design_sources",
        "missing_current_design_source",
        "unmapped_no_rebind",
        "candidate_non_authoritative",
    ):
        print(f"source_{state}={sum(row.source_ref_state == state for row in rows)}")
    current_rows = tuple(row for row in rows if row.origin == "current_declaration")
    eligible_states = {"current_design", "mechanical_rebind"}
    print(f"current_rebind_eligible={sum(row.source_ref_state in eligible_states for row in current_rows)}")
    print(f"current_rebind_withheld={sum(row.source_ref_state not in eligible_states for row in current_rows)}")
    print(f"current_exact_map_owned={sum(bool(row.fields) for row in current_rows)}")
    print(f"current_orphan={sum(not row.fields for row in current_rows)}")
    print(f"current_identity_review_required={sum(row.identity_review_required for row in current_rows)}")
    print(
        "anchor_identity_mismatches="
        f"{sum(anchor.owner_state not in {'exact_planned_owner', 'non_casilla'} for anchor in anchors)}"
    )
    print(f"declaration_legal_gaps={sum(row.legal_evidence_state != 'applicable' for row in rows)}")
    print(f"map_legal_gaps={sum(anchor.legal_evidence_state != 'applicable' for anchor in anchors)}")
    return 0


def _classify_anchor(entry, field, *, planned_ids, legal, valid_from, valid_to) -> M200TargetAnchorDisposition:
    declared_owner = None if entry.casilla_id is None else str(entry.casilla_id)
    printed = _printed(field.normalized_description)
    resolved: str | None = None
    if declared_owner is None:
        owner_state = "non_casilla"
    elif declared_owner in planned_ids:
        owner_state = "exact_planned_owner"
    else:
        padded = declared_owner.zfill(5)
        qualified = f"{field.record_identity}:{padded}"
        if padded in planned_ids:
            owner_state = "zero_padding_mismatch_refused"
            resolved = padded
        elif qualified in planned_ids:
            owner_state = "qualified_identity_mismatch_refused"
            resolved = qualified
        else:
            owner_state = "unknown_map_owner_refused"
    if declared_owner is None:
        printed_state = "not_applicable"
    elif printed is None:
        printed_state = "missing_official_printed_identity"
    elif printed == declared_owner or (":" in declared_owner and printed == declared_owner.rsplit(":", 1)[1]):
        printed_state = "matches_declared_owner"
    elif resolved is not None and (printed == resolved or printed == resolved.rsplit(":", 1)[-1]):
        printed_state = "matches_identity_proposal"
    else:
        printed_state = "conflicts_with_declared_owner"
    applicable, inapplicable, legal_state = _legal_evidence(entry.legal_refs, legal, valid_from, valid_to)
    return M200TargetAnchorDisposition(
        export_field_id=str(entry.export_field_id),
        anchor=semantic_anchor_key(entry.anchor),
        semantic_kind=str(entry.kind.value),
        declared_map_owner=declared_owner,
        printed_number=printed,
        resolved_owner_proposal_non_authoritative=resolved,
        owner_state=owner_state,
        printed_identity_state=printed_state,
        official_description=field.normalized_description,
        template=_template(field.normalized_description),
        aeat_type=field.aeat_type,
        length=field.length,
        source_refs=tuple(entry.source_refs),
        legal_evidence_state=legal_state,
        applicable_legal_refs=applicable,
        inapplicable_legal_refs=inapplicable,
    )


def _cross_revision_index(*, sibling, sources, legal, valid_from, valid_to) -> dict:
    design = load_record_design_intermediate(
        bundled_path(), sources, source_ref=SIBLING_SOURCE_REF, filing_year=2025, design_epoch="2025"
    )
    semantic_map = load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / "2025")
    if str(design.source.source_ref) != SIBLING_SOURCE_REF or semantic_map.source_ref != SIBLING_SOURCE_REF:
        raise RegistryValidationError("Modelo 200 sibling proposal evidence carries a drifted source reference")
    if design.source.source_sha256 != semantic_map.source_sha256:
        raise RegistryValidationError("Modelo 200 sibling design and semantic map SHA-256 differ")
    fields = {intermediate_anchor_key(field): field for sheet in design.sheets for field in sheet.fields}
    declarations = {str(item.id): item for item in sibling.casillas}
    _require_unique_identifiers(tuple(str(item.id) for item in sibling.casillas), label="sibling declaration")
    index = defaultdict(list)
    for entry in semantic_map.entries:
        declaration = declarations.get(str(entry.casilla_id))
        if declaration is None:
            continue
        _applicable, inapplicable = _legal_partition(declaration.legal_refs, legal, valid_from, valid_to)
        if inapplicable:
            continue
        anchor = semantic_anchor_key(entry.anchor)
        field = fields[anchor]
        index[(_template(field.normalized_description), field.aeat_type, field.length)].append(
            (anchor, _payload(declaration))
        )
    return index


def _source_ref_state(payload: SemanticPayload) -> tuple[str, tuple[str, ...] | None]:
    refs = payload.source_refs
    if TARGET_SOURCE_REF in refs and SIBLING_SOURCE_REF in refs:
        return "mixed_design_sources", None
    if TARGET_SOURCE_REF in refs:
        return "current_design", None
    if SIBLING_SOURCE_REF in refs:
        return "mechanical_rebind", tuple(TARGET_SOURCE_REF if ref == SIBLING_SOURCE_REF else ref for ref in refs)
    return "missing_current_design_source", None


def _legal_partition(refs, legal, valid_from, valid_to):
    applicable, inapplicable = [], []
    for ref in refs:
        authority = legal.get(ref)
        if authority is None:
            inapplicable.append(ref)
            continue
        start, end = governed_period_span(authority)
        target = (
            applicable
            if start <= valid_from and (valid_to is None or end is None or end >= valid_to)
            else inapplicable
        )
        target.append(ref)
    return tuple(applicable), tuple(inapplicable)


def _legal_evidence(refs, legal, valid_from, valid_to):
    """Partition refs and distinguish absent proof from applicable authority."""
    applicable, inapplicable = _legal_partition(refs, legal, valid_from, valid_to)
    state = (
        "missing_legal_provenance"
        if not refs
        else "unresolved_or_inapplicable"
        if inapplicable
        else "applicable"
    )
    return applicable, inapplicable, state


def _same_year_state(payload, fields, templates):
    if not fields:
        return "unmapped_no_template_adjudication"
    peers = {candidate for field in fields for candidate in templates[field.template] if candidate != payload}
    if not peers:
        return "no_distinct_peer"
    return "unique_consistent_peer" if len(peers) == 1 else "conflicting_peers"


def _trusted_template_payloads(exact_ownership, current):
    """Build peer evidence exclusively from current, identity-clean declarations."""
    template_payloads: dict[str, set[SemanticPayload]] = defaultdict(set)
    for identifier, fields in exact_ownership.items():
        if identifier not in current:
            continue
        for field in fields:
            if field.printed_identity_state == "matches_declared_owner":
                template_payloads[field.template].add(current[identifier])
    return template_payloads


def _merge_unique_catalogue(parts: Iterable[object], *, attribute: str) -> dict:
    merged: dict = {}
    for part in parts:
        for identifier, value in getattr(part, attribute).items():
            if identifier in merged:
                raise RegistryValidationError(f"duplicate {attribute} catalogue id {identifier!r}")
            merged[identifier] = value
    return merged


def _require_partition(revision, sibling) -> None:
    if str(revision.id) != "2024" or (revision.valid_from, revision.valid_to) != (
        TARGET_VALID_FROM,
        TARGET_VALID_TO,
    ):
        raise RegistryValidationError("Modelo 200/2024 revision partition drifted from calendar year 2024")
    sibling_partition = (str(sibling.id), sibling.valid_from, sibling.valid_to)
    if sibling_partition != ("2025-y-siguientes", SIBLING_VALID_FROM, None):
        raise RegistryValidationError("Modelo 200 sibling partition drifted from 2025-y-siguientes")
    if TARGET_SOURCE_REF not in tuple(map(str, revision.source_refs)):
        raise RegistryValidationError("Modelo 200/2024 revision is not bound to its exact record-design source")
    if SIBLING_SOURCE_REF not in tuple(map(str, sibling.source_refs)):
        raise RegistryValidationError("Modelo 200 sibling revision is not bound to its exact record-design source")


def _require_exact_source_identity(label: str, source_ref: str, source_sha256: str) -> None:
    if (source_ref, source_sha256) != (TARGET_SOURCE_REF, TARGET_SOURCE_SHA256):
        raise RegistryValidationError(
            f"{label} source identity drifted: expected {TARGET_SOURCE_REF}@{TARGET_SOURCE_SHA256}, "
            f"found {source_ref}@{source_sha256}"
        )


def _require_entry_source_refs(entries: Iterable[object]) -> None:
    contaminated = tuple(
        str(entry.export_field_id) for entry in entries if tuple(entry.source_refs) != (TARGET_SOURCE_REF,)
    )
    if contaminated:
        raise RegistryValidationError(
            "Modelo 200/2024 semantic-map entries carry non-target source refs: " + ", ".join(contaminated[:10])
        )


def _require_unique_identifiers(identifiers: tuple[str, ...], *, label: str) -> None:
    duplicates = sorted(identifier for identifier, count in Counter(identifiers).items() if count > 1)
    if duplicates:
        raise RegistryValidationError(f"duplicate {label} ids: {duplicates!r}")


def _require_disjoint_ids(current_ids: frozenset[str], candidate_ids: frozenset[str]) -> None:
    collisions = sorted(current_ids & candidate_ids)
    if collisions:
        raise RegistryValidationError(f"current declarations collide with non-authoritative candidates: {collisions!r}")


def _require_anchor_bijection(*, design_keys, map_keys, export_ids) -> None:
    _require_unique_identifiers(tuple(map(repr, design_keys)), label="target-design anchor")
    _require_unique_identifiers(tuple(map(repr, map_keys)), label="semantic-map anchor")
    _require_unique_identifiers(tuple(export_ids), label="semantic-map export field")
    design_set = set(design_keys)
    map_set = set(map_keys)
    if design_set != map_set:
        missing = sorted(map(repr, design_set - map_set))
        extra = sorted(map(repr, map_set - design_set))
        raise RegistryValidationError(
            f"target design and semantic map are not bijective; missing={missing[:5]!r}, extra={extra[:5]!r}"
        )


def _printed(description: str) -> str | None:
    import re

    matches = re.findall(r"\[([0-9]{5})\]", description)
    return matches[0] if len(matches) == 1 else None


def _serialise(row: M200ReconciliationRow) -> dict:
    value = asdict(row)
    for optional in (
        "mechanical_source_refs_proposal",
        "cross_revision_proposal_non_authoritative",
        "declaration_payload",
        "candidate_payload_non_authoritative",
    ):
        if value[optional] is None:
            value.pop(optional)
    return value


def _toml_order(value):
    if isinstance(value, Mapping):
        items = tuple((key, _toml_order(item)) for key, item in value.items())
        scalars = tuple((key, item) for key, item in items if not _table_like(item))
        tables = tuple((key, item) for key, item in items if _table_like(item))
        return dict((*scalars, *tables))
    if isinstance(value, (list, tuple)):
        return [_toml_order(item) for item in value]
    return value


def _table_like(value):
    return isinstance(value, Mapping) or (isinstance(value, list) and any(isinstance(item, Mapping) for item in value))


if __name__ == "__main__":
    raise SystemExit(main())
