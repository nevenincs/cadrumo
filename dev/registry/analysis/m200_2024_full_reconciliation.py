"""Target-first reconciliation census for every planned M200/2024 casilla."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import rtoml

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.loader import load_catalogue_file, load_modelo_directory
from cadrumo.domain.calculations.registry.schema_references import governed_period_span

from ..pipeline._record_design_ir import intermediate_anchor_key, load_record_design_intermediate
from ..pipeline._semantic_map import semantic_anchor_key
from ..pipeline._semantic_map_loader import load_semantic_map
from .m200_restored_semantic_audit import (
    SemanticPayload,
    _candidate_payloads,
    _payload,
    _template,
)


@dataclass(frozen=True, slots=True)
class M200FieldOwnership:
    """One exact current official field owned by a planned casilla."""

    export_field_id: str
    anchor: tuple[object, ...]
    official_description: str
    template: str
    aeat_type: str
    length: int


@dataclass(frozen=True, slots=True)
class M200ReconciliationRow:
    """Physical, source, semantic, and legal evidence for one planned casilla."""

    casilla_id: str
    origin: str
    source_ref_state: str
    mechanical_source_refs_proposal: tuple[str, ...] | None
    export_reachability: str
    fields: tuple[M200FieldOwnership, ...]
    normalized_official_descriptions: tuple[str, ...]
    same_2024_template_state: str
    cross_revision_status: str
    cross_revision_proposal_non_authoritative: SemanticPayload | None
    applicable_legal_refs: tuple[str, ...]
    inapplicable_legal_refs: tuple[str, ...]
    payload: SemanticPayload


def reconcile_bundled_m200_2024() -> tuple[M200ReconciliationRow, ...]:
    """Build the complete source-SHA-bound planned-revision reconciliation."""
    registry_root = bundled_path("registry", "aeat")
    modelo = load_modelo_directory(registry_root / "modelos" / "200")
    revision = modelo.revisions["2024"]
    sibling = modelo.revisions["2025-y-siguientes"]
    parts = tuple(load_catalogue_file(path) for path in (registry_root / "legal").glob("*.toml"))
    sources = {key: value for part in parts for key, value in part.sources.items()}
    legal = {key: value for part in parts for key, value in part.legal.items()}
    target_design = load_record_design_intermediate(
        bundled_path(), sources, source_ref="aeat-dr-200-2024", filing_year=2024, design_epoch="2024"
    )
    target_map = load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / "2024")
    candidates = _candidate_payloads()
    candidate_ids = frozenset(candidates)
    current = {str(item.id): _payload(item) for item in revision.casillas if str(item.id) not in candidate_ids}
    planned = {**current, **{identifier: payload for identifier, (_path, payload) in candidates.items()}}

    target_fields = {intermediate_anchor_key(field): field for sheet in target_design.sheets for field in sheet.fields}
    ownership: dict[str, list[M200FieldOwnership]] = defaultdict(list)
    for entry in target_map.entries:
        if entry.casilla_id is None:
            continue
        anchor = semantic_anchor_key(entry.anchor)
        field = target_fields[anchor]
        printed = _printed(field.normalized_description)
        if printed is None:
            continue
        qualified = f"{field.record_identity}:{printed}"
        owner = qualified if qualified in planned else printed if printed in planned else None
        if owner is None:
            continue
        ownership[owner].append(
            M200FieldOwnership(
                export_field_id=str(entry.export_field_id),
                anchor=anchor,
                official_description=field.normalized_description,
                template=_template(field.normalized_description),
                aeat_type=field.aeat_type,
                length=field.length,
            )
        )

    template_payloads: dict[str, set[SemanticPayload]] = defaultdict(set)
    for identifier, fields in ownership.items():
        for field in fields:
            template_payloads[field.template].add(planned[identifier])

    cross_index = _cross_revision_index(
        sibling=sibling,
        sources=sources,
        legal=legal,
        valid_from=revision.valid_from,
        valid_to=revision.valid_to,
    )
    rows: list[M200ReconciliationRow] = []
    for identifier, payload in planned.items():
        fields = tuple(sorted(ownership.get(identifier, ()), key=lambda item: item.export_field_id))
        source_state, source_proposal = _source_ref_state(payload, mapped=bool(fields))
        applicable, inapplicable = _legal_partition(payload.legal_refs, legal, revision.valid_from, revision.valid_to)
        same_year = _same_year_state(payload, fields, template_payloads)
        cross_payloads = {
            proposal
            for field in fields
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
                origin="restoration_candidate" if identifier in candidate_ids else "current_declaration",
                source_ref_state=source_state,
                mechanical_source_refs_proposal=source_proposal,
                export_reachability="mapped_current_2024" if fields else "unmapped_calculation_only",
                fields=fields,
                normalized_official_descriptions=tuple(field.official_description for field in fields),
                same_2024_template_state=same_year,
                cross_revision_status=cross_status,
                cross_revision_proposal_non_authoritative=(
                    next(iter(cross_payloads)) if len(cross_payloads) == 1 else None
                ),
                applicable_legal_refs=applicable,
                inapplicable_legal_refs=inapplicable,
                payload=payload,
            )
        )
    return tuple(sorted(rows, key=lambda item: item.casilla_id))


def render_reconciliation_toml(rows: tuple[M200ReconciliationRow, ...]) -> str:
    """Render deterministic report rows bound to the official 2024 source SHA."""
    source = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml")).sources["aeat-dr-200-2024"]
    return rtoml.dumps(
        {
            "schema_version": 1,
            "modelo": "200",
            "revision": "2024",
            "source_ref": str(source.id),
            "source_sha256": source.sha256,
            "row": [_serialise(row) for row in rows],
        },
        pretty=True,
    )


def main(argv: list[str] | None = None) -> int:
    """Print counts or the full deterministic TOML report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toml", action="store_true")
    args = parser.parse_args(argv)
    rows = reconcile_bundled_m200_2024()
    if args.toml:
        sys.stdout.write(render_reconciliation_toml(rows))
        return 0
    print(f"total={len(rows)}")
    print(f"current={sum(row.origin == 'current_declaration' for row in rows)}")
    print(f"candidates={sum(row.origin == 'restoration_candidate' for row in rows)}")
    for state in ("current_design", "mechanical_rebind", "missing_current_design_source", "unmapped_no_rebind"):
        print(f"source_{state}={sum(row.source_ref_state == state for row in rows)}")
    print(f"mapped={sum(bool(row.fields) for row in rows)}")
    print(f"unmapped={sum(not row.fields for row in rows)}")
    print(f"legal_inapplicable={sum(bool(row.inapplicable_legal_refs) for row in rows)}")
    return 0


def _cross_revision_index(*, sibling: object, sources: dict, legal: dict, valid_from, valid_to) -> dict:
    design = load_record_design_intermediate(
        bundled_path(), sources, source_ref="aeat-dr-200-2025", filing_year=2025, design_epoch="2025"
    )
    semantic_map = load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / "2025")
    fields = {intermediate_anchor_key(field): field for sheet in design.sheets for field in sheet.fields}
    declarations = {str(item.id): item for item in sibling.casillas}
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


def _source_ref_state(payload: SemanticPayload, *, mapped: bool) -> tuple[str, tuple[str, ...] | None]:
    if not mapped:
        return "unmapped_no_rebind", None
    if "aeat-dr-200-2024" in payload.source_refs:
        return "current_design", None
    if "aeat-dr-200-2025" in payload.source_refs:
        proposal = tuple("aeat-dr-200-2024" if ref == "aeat-dr-200-2025" else ref for ref in payload.source_refs)
        return "mechanical_rebind", proposal
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
            applicable if start <= valid_from and (valid_to is None or end is None or end >= valid_to) else inapplicable
        )
        target.append(ref)
    return tuple(applicable), tuple(inapplicable)


def _same_year_state(payload, fields, templates):
    if not fields:
        return "unmapped_no_template_adjudication"
    peers = {candidate for field in fields for candidate in templates[field.template] if candidate != payload}
    if not peers:
        return "no_distinct_peer"
    return "unique_consistent_peer" if len(peers) == 1 else "conflicting_peers"


def _printed(description: str) -> str | None:
    import re

    matches = re.findall(r"\[([0-9]{5})\]", description)
    return matches[0] if len(matches) == 1 else None


def _serialise(row: M200ReconciliationRow) -> dict:
    value = asdict(row)
    if value["mechanical_source_refs_proposal"] is None:
        value.pop("mechanical_source_refs_proposal")
    if value["cross_revision_proposal_non_authoritative"] is None:
        value.pop("cross_revision_proposal_non_authoritative")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
