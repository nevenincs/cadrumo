"""Target-first reconciliation census for every planned M200/2024 casilla and anchor."""

from __future__ import annotations

import argparse
import json
import re
import secrets
import shutil
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path

import rtoml

from cadrumo.core.atomic_write import atomic_write_text
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.fsync import fsync_parent_dir
from cadrumo.core.locks import exclusive_file_lock
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.legal import verify_legal_catalogue
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

_CASILLA_TABLE = re.compile(r'^\[\[revisions\."2024"\.casillas\]\]\s*$')
_ID_LINE = re.compile(r'^\s*id\s*=\s*"(?P<id>[^"]+)"\s*$')
_SOURCE_REFS_LINE = re.compile(r"^(?P<prefix>\s*source_refs\s*=\s*)(?P<value>.*?)(?P<ending>\r?\n)?$")
_REBIND_JOURNAL = ".m200-2024-source-rebind.journal.json"
_REBIND_STAGE_PREFIX = ".m200-2024-source-rebind-stage-"
_REBIND_BACKUP_PREFIX = ".m200-2024-source-rebind-backup-"


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
    legal_refs: tuple[str, ...]
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
    legal_refs: tuple[str, ...]
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


@dataclass(frozen=True, slots=True)
class M200LegalWorklistItem:
    """One declaration or semantic-map legal-evidence result for the pinned target."""

    evidence_home: str
    subject_id: str
    source_ref: str
    source_sha256: str
    legal_refs: tuple[str, ...]
    applicable_legal_refs: tuple[str, ...]
    unknown_legal_refs: tuple[str, ...]
    out_of_window_legal_refs: tuple[str, ...]
    state: str


@dataclass(frozen=True, slots=True)
class M200LegalWorklist:
    """Complete, source-SHA-bound legal worklist for Modelo 200/2024 authority."""

    source_ref: str
    source_sha256: str
    revision_valid_from: date
    revision_valid_to: date
    items: tuple[M200LegalWorklistItem, ...]

    @property
    def missing_provenance_count(self) -> int:
        """Count carriers with no legal reference at all."""
        return sum(item.state == "missing_provenance" for item in self.items)

    @property
    def unknown_reference_count(self) -> int:
        """Count carriers whose catalogue key cannot resolve."""
        return sum(bool(item.unknown_legal_refs) for item in self.items)

    @property
    def out_of_window_count(self) -> int:
        """Count carriers whose known authority misses the target period."""
        return sum(bool(item.out_of_window_legal_refs) for item in self.items)


@dataclass(frozen=True, slots=True)
class M200SourceRebind:
    """One exact-map-owned 2025-to-2024 declaration-source replacement."""

    casilla_id: str
    expected_source_refs: tuple[str, ...]
    target_source_refs: tuple[str, ...]
    non_source_payload_sha256: str


@dataclass(frozen=True, slots=True)
class M200SourceRebindPlan:
    """Complete source-SHA-bound mutation plan for the 2024 declaration tree."""

    source_ref: str
    source_sha256: str
    semantic_map_source_ref: str
    semantic_map_source_sha256: str
    rebinds: tuple[M200SourceRebind, ...]
    verified_current_design_ids: tuple[str, ...]
    refused_orphan_ids: tuple[str, ...]
    expected_current_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class M200SourceRebindApplication:
    """The deterministic result of validating, previewing, or applying a plan."""

    planned_rebind_count: int
    changed_paths: tuple[Path, ...]
    dry_run: bool


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
    current_declarations = {str(item.id): item for item in revision.casillas}
    _require_reviewed_candidate_promotions(frozenset(declaration_ids) & candidate_ids)
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
        is_candidate = identifier in candidates and identifier not in current
        payload = candidates[identifier] if is_candidate else current[identifier]
        fields = tuple(sorted(exact_ownership.get(identifier, ()), key=lambda item: item.export_field_id))
        proposed_fields = tuple(sorted(proposed_ownership.get(identifier, ()), key=lambda item: item.export_field_id))
        if is_candidate:
            source_state, source_proposal = "candidate_non_authoritative", None
        elif not fields:
            source_state, source_proposal = "unmapped_no_rebind", None
        else:
            source_state, source_proposal = _source_ref_state(payload)
        identity_review_required = any(field.printed_identity_state != "matches_declared_owner" for field in fields)
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
                legal_refs=tuple(payload.legal_refs),
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


def build_m200_2024_legal_worklist(census: M200ReconciliationCensus) -> M200LegalWorklist:
    """Classify every target declaration and map citation without legal inference.

    The exact 2024 record-design identity is deliberately retained on every
    row.  A later model design, a legal provision under a different catalogue
    key, or a provision whose governed period misses 2024 can therefore never
    become a quiet substitute while preparing the catalogue worklist.
    """
    _require_exact_source_identity("legal worklist census", census.source_ref, census.source_sha256)
    _require_exact_source_identity(
        "legal worklist semantic map", census.semantic_map_source_ref, census.semantic_map_source_sha256
    )
    if (census.revision_valid_from, census.revision_valid_to) != (TARGET_VALID_FROM, TARGET_VALID_TO):
        raise RegistryValidationError("legal worklist carries a drifted Modelo 200/2024 partition")

    registry_root = bundled_path("registry", "aeat")
    modelo = load_modelo_directory(registry_root / "modelos" / "200")
    revision = modelo.revisions["2024"]
    _require_partition(revision, modelo.revisions["2025-y-siguientes"])
    parts = tuple(load_catalogue_file(path) for path in sorted((registry_root / "legal").glob("*.toml")))
    legal = _merge_unique_catalogue(parts, attribute="legal")
    items = tuple(
        _legal_worklist_item(
            evidence_home=evidence_home,
            subject_id=subject_id,
            legal_refs=legal_refs,
            legal=legal,
            source_ref=census.source_ref,
            source_sha256=census.source_sha256,
            valid_from=census.revision_valid_from,
            valid_to=census.revision_valid_to,
        )
        for evidence_home, subject_id, legal_refs in (
            *(
                ("revision", subject_id, legal_refs)
                for subject_id, legal_refs in _m200_2024_revision_legal_carriers(registry_root)
            ),
            *( ("declaration", row.casilla_id, row.legal_refs) for row in census.rows),
            *( ("semantic_map", anchor.export_field_id, anchor.legal_refs) for anchor in census.anchors),
        )
    )
    _verify_m200_2024_worklist_legal_authority(items, legal)
    return M200LegalWorklist(
        source_ref=census.source_ref,
        source_sha256=census.source_sha256,
        revision_valid_from=census.revision_valid_from,
        revision_valid_to=census.revision_valid_to,
        items=items,
    )


def _verify_m200_2024_worklist_legal_authority(
    items: Iterable[M200LegalWorklistItem], legal: Mapping[str, object]
) -> None:
    """Require every known worklist citation to be reviewed and corpus-grounded."""
    referenced = {
        ref: legal[ref]
        for item in items
        for ref in item.legal_refs
        if ref in legal
    }
    verify_legal_catalogue(referenced, source_root=bundled_path())


def _require_closed_m200_2024_legal_worklist(
    census: M200ReconciliationCensus, *, worklist: M200LegalWorklist | None = None
) -> M200LegalWorklist:
    """Build and admit only closed Modelo 200/2024 legal authority for CLI work."""
    admitted = build_m200_2024_legal_worklist(census) if worklist is None else worklist
    require_closed_m200_2024_legal_worklist(admitted)
    return admitted


def _m200_2024_revision_legal_carriers(registry_root: Path) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Extract every legal-reference carrier from the target revision declaration.

    ``orden_aplicabilidad`` is a legal-reference carrier despite using a
    distinct schema key.  Recursing the actual TOML keeps future nested family
    dispositions visible instead of assuming the top-level ``legal_refs`` list
    is the entire worklist.
    """
    document = rtoml.loads(
        (registry_root / "modelos" / "200" / "revisions" / "2024" / "revision.toml").read_text(encoding="utf-8")
    )
    revision = document["revisions"]["2024"]
    carriers: list[tuple[str, tuple[str, ...]]] = []

    def visit(value: object, path: tuple[str, ...]) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                child_path = (*path, str(key))
                if key in {"legal_refs", "orden_aplicabilidad"}:
                    if not isinstance(child, list) or not all(isinstance(ref, str) for ref in child):
                        raise RegistryValidationError(
                            f"Modelo 200/2024 revision legal carrier {'.'.join(child_path)!r} is malformed"
                        )
                    carriers.append((".".join(child_path), tuple(child)))
                else:
                    visit(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, (*path, str(index)))

    visit(revision, ())
    return tuple(carriers)


def _legal_worklist_item(
    *,
    evidence_home: str,
    subject_id: str,
    legal_refs: tuple[str, ...],
    legal: Mapping[str, object],
    source_ref: str,
    source_sha256: str,
    valid_from: date,
    valid_to: date,
) -> M200LegalWorklistItem:
    applicable, unknown, out_of_window = _legal_worklist_partition(legal_refs, legal, valid_from, valid_to)
    state = (
        "missing_provenance"
        if not legal_refs
        else "unresolved"
        if unknown or out_of_window
        else "applicable"
    )
    return M200LegalWorklistItem(
        evidence_home=evidence_home,
        subject_id=subject_id,
        source_ref=source_ref,
        source_sha256=source_sha256,
        legal_refs=legal_refs,
        applicable_legal_refs=applicable,
        unknown_legal_refs=unknown,
        out_of_window_legal_refs=out_of_window,
        state=state,
    )


def require_closed_m200_2024_legal_worklist(worklist: M200LegalWorklist) -> None:
    """Refuse catalogue authoring or semantic admission while any evidence is open."""
    _require_exact_source_identity("legal worklist", worklist.source_ref, worklist.source_sha256)
    if (worklist.revision_valid_from, worklist.revision_valid_to) != (TARGET_VALID_FROM, TARGET_VALID_TO):
        raise RegistryValidationError("legal worklist carries a drifted Modelo 200/2024 partition")
    unresolved = tuple(item for item in worklist.items if item.state != "applicable")
    if unresolved:
        sample = ", ".join(f"{item.evidence_home}:{item.subject_id}" for item in unresolved[:5])
        raise RegistryValidationError(
            "Modelo 200/2024 legal worklist is unresolved: "
            f"missing={worklist.missing_provenance_count}, "
            f"unknown={worklist.unknown_reference_count}, "
            f"out_of_window={worklist.out_of_window_count}; {sample}"
        )


def build_m200_source_rebind_plan(census: M200ReconciliationCensus) -> M200SourceRebindPlan:
    """Derive the complete, target-map-owned declaration-source rebind plan.

    This deliberately consumes the census rather than walking source files by
    number.  The census has already proved the target design/map bijection and
    exact map ownership, so a declaration is eligible only when it owns one or
    more exact target anchors and its sole design substitution is the pinned
    2025 record-design reference.  An already-target-design declaration is
    excluded only when the closed target compiler replays its exact receipt and
    canonical bytes.  The two declarations without target anchors remain
    explicit refusals instead of becoming a catch-all source rewrite.
    """
    _require_exact_source_identity("source rebind census", census.source_ref, census.source_sha256)
    _require_exact_source_identity(
        "source rebind semantic map", census.semantic_map_source_ref, census.semantic_map_source_sha256
    )
    if (census.revision_valid_from, census.revision_valid_to) != (TARGET_VALID_FROM, TARGET_VALID_TO):
        raise RegistryValidationError("source rebind census carries a drifted Modelo 200/2024 partition")

    current = tuple(row for row in census.rows if row.origin == "current_declaration")
    candidates = tuple(row for row in census.rows if row.origin == "restoration_candidate")
    _require_unique_identifiers(tuple(row.casilla_id for row in current), label="source rebind current declaration")
    from .m200_2024_template_adjudications import (
        compile_m200_2024_same_template_authority,
        promoted_candidate_ids,
    )

    compiler_authority = compile_m200_2024_same_template_authority()
    receipted_current_ids = promoted_candidate_ids(compiler_authority)
    rebinds: list[M200SourceRebind] = []
    verified_current_design_ids: list[str] = []
    orphans: list[str] = []
    for row in current:
        payload = row.declaration_payload
        if payload is None:
            raise RegistryValidationError(f"current declaration {row.casilla_id!r} omitted its source payload")
        if row.source_ref_state == "mechanical_rebind":
            if not row.fields or row.mechanical_source_refs_proposal is None:
                raise RegistryValidationError(
                    f"source rebind candidate {row.casilla_id!r} lacks exact target-map ownership or a replacement",
                )
            rebinds.append(
                M200SourceRebind(
                    casilla_id=row.casilla_id,
                    expected_source_refs=tuple(payload.source_refs),
                    target_source_refs=tuple(row.mechanical_source_refs_proposal),
                    non_source_payload_sha256="",
                )
            )
        elif row.source_ref_state == "current_design":
            if not row.fields:
                raise RegistryValidationError(
                    f"source rebind current-design declaration {row.casilla_id!r} lacks exact target-map ownership"
                )
            if row.casilla_id not in receipted_current_ids:
                raise RegistryValidationError(
                    f"source rebind plan refuses unreceipted current-design declaration {row.casilla_id!r}"
                )
            verified_current_design_ids.append(row.casilla_id)
        elif row.source_ref_state == "unmapped_no_rebind":
            if row.fields:
                raise RegistryValidationError(
                    f"source rebind orphan {row.casilla_id!r} unexpectedly owns a target anchor"
                )
            orphans.append(row.casilla_id)
        else:
            raise RegistryValidationError(
                "source rebind plan refuses unexpected declaration state "
                f"{row.source_ref_state!r} for {row.casilla_id!r}",
            )

    planned = tuple(sorted(rebinds, key=lambda item: item.casilla_id))
    verified_current_design = tuple(sorted(verified_current_design_ids))
    _require_unique_identifiers(tuple(item.casilla_id for item in planned), label="source rebind output")
    for item in planned:
        _require_rebind_source_refs(item)
    if (
        len(planned) != 3171
        or len(verified_current_design) != 4
        or len(orphans) != 2
        or len(candidates) != 152
        or len(census.rows) != 3329
    ):
        raise RegistryValidationError(
            "Modelo 200 source rebind population drifted: "
            "expected 3171 rebinds, 4 verified current-design declarations, 2 refused orphans, "
            f"152 remaining candidates, and 3329 rows; found {len(planned)}, {len(verified_current_design)}, "
            f"{len(orphans)}, {len(candidates)}, and {len(census.rows)}",
        )
    if frozenset(verified_current_design) != receipted_current_ids:
        raise RegistryValidationError("source rebind current-design declarations drifted from compiler receipt")
    canonical_records = _read_m200_2024_casilla_records(bundled_path("registry", "aeat"))
    if set(canonical_records) != {row.casilla_id for row in current}:
        raise RegistryValidationError("source rebind canonical declaration anchors drifted while planning")
    planned = tuple(
        M200SourceRebind(
            casilla_id=item.casilla_id,
            expected_source_refs=item.expected_source_refs,
            target_source_refs=item.target_source_refs,
            non_source_payload_sha256=canonical_records[item.casilla_id].non_source_payload_sha256,
        )
        for item in planned
    )
    return M200SourceRebindPlan(
        source_ref=census.source_ref,
        source_sha256=census.source_sha256,
        semantic_map_source_ref=census.semantic_map_source_ref,
        semantic_map_source_sha256=census.semantic_map_source_sha256,
        rebinds=planned,
        verified_current_design_ids=verified_current_design,
        refused_orphan_ids=tuple(sorted(orphans)),
        expected_current_ids=tuple(sorted(row.casilla_id for row in current)),
    )


def build_bundled_m200_source_rebind_plan() -> M200SourceRebindPlan:
    """Build the only supported source rebind plan from live pinned authority."""
    return build_m200_source_rebind_plan(reconcile_bundled_m200_2024())


def apply_m200_source_rebind_plan(
    plan: M200SourceRebindPlan,
    *,
    registry_root: Path,
    dry_run: bool = False,
) -> M200SourceRebindApplication:
    """Preflight then atomically replace only planned ``source_refs`` lines.

    ``registry_root`` may be an isolated temporary registry tree for review and
    detector tests, or the canonical bundled registry root for the explicit CLI
    apply path.  Every anchor, input source tuple, output tuple, and complete
    declaration population is checked before the first atomic file replace.
    Thus a stale, duplicated, or partly-applied tree refuses before it can
    receive an additional rebind.  Unrelated TOML bytes are carried through
    unchanged rather than being parsed and reserialised.
    """
    _require_rebind_plan_identity(plan)
    _require_unique_identifiers(tuple(item.casilla_id for item in plan.rebinds), label="source rebind output")
    if len(plan.rebinds) != 3171 or len(plan.verified_current_design_ids) != 4 or len(plan.refused_orphan_ids) != 2:
        raise RegistryValidationError("source rebind plan does not carry the complete 3171/4/2 population")
    partitions = (
        {item.casilla_id for item in plan.rebinds},
        set(plan.verified_current_design_ids),
        set(plan.refused_orphan_ids),
    )
    if any(left & right for index, left in enumerate(partitions) for right in partitions[index + 1 :]):
        raise RegistryValidationError("source rebind plan overlaps its declaration partitions")
    if set().union(*partitions) != set(plan.expected_current_ids):
        raise RegistryValidationError("source rebind plan does not cover the complete current declaration population")
    for item in plan.rebinds:
        _require_rebind_source_refs(item)

    registry_root = registry_root.resolve()
    with exclusive_file_lock(registry_root / ".m200-2024-source-rebind.lock"):
        _recover_m200_source_rebind(plan, registry_root)
        return _apply_preflighted_m200_source_rebind(plan, registry_root=registry_root, dry_run=dry_run)


def _apply_preflighted_m200_source_rebind(
    plan: M200SourceRebindPlan, *, registry_root: Path, dry_run: bool
) -> M200SourceRebindApplication:
    records = _read_m200_2024_casilla_records(registry_root)
    expected_ids = set(plan.expected_current_ids)
    actual_ids = set(records)
    if actual_ids != expected_ids:
        missing = sorted(expected_ids - actual_ids)
        extra = sorted(actual_ids - expected_ids)
        raise RegistryValidationError(
            f"source rebind declaration anchors drifted: missing={missing[:5]!r}, extra={extra[:5]!r}"
        )
    _require_verified_current_design(
        plan,
        registry_root / "modelos" / "200" / "revisions" / "2024" / "casillas",
    )

    replacements: dict[Path, dict[int, str]] = defaultdict(dict)
    for item in plan.rebinds:
        record = records[item.casilla_id]
        if record.source_refs != item.expected_source_refs:
            raise RegistryValidationError(
                f"source rebind input drifted or is partially applied for {item.casilla_id!r}: "
                f"expected {item.expected_source_refs!r}, found {record.source_refs!r}",
            )
        if record.non_source_payload_sha256 != item.non_source_payload_sha256:
            raise RegistryValidationError(f"source rebind non-source payload drifted for {item.casilla_id!r}")
        replacement = _render_source_refs_line(record.source_line, item.target_source_refs)
        if record.source_line_index in replacements[record.path]:
            raise RegistryValidationError(f"duplicate source rebind output line for {item.casilla_id!r}")
        replacements[record.path][record.source_line_index] = replacement

    rendered: dict[Path, str] = {}
    for path, line_replacements in replacements.items():
        original = records_by_path(records, path)
        lines = original.splitlines(keepends=True)
        for line_index, replacement in line_replacements.items():
            lines[line_index] = replacement
        candidate = "".join(lines)
        _require_non_source_payload_unchanged(original, candidate)
        rendered[path] = candidate

    changed_paths = tuple(sorted(rendered))
    if not dry_run:
        _publish_m200_source_rebind_transaction(registry_root, rendered, plan)
    return M200SourceRebindApplication(
        planned_rebind_count=len(plan.rebinds),
        changed_paths=changed_paths,
        dry_run=dry_run,
    )


def _publish_m200_source_rebind_transaction(
    registry_root: Path, rendered: Mapping[Path, str], plan: M200SourceRebindPlan
) -> None:
    """Stage a whole casilla tree, then cut it over with journaled directory moves."""
    casillas_root = registry_root / "modelos" / "200" / "revisions" / "2024" / "casillas"
    revision_root = casillas_root.parent
    token = secrets.token_hex(8)
    stage = revision_root / f"{_REBIND_STAGE_PREFIX}{token}"
    backup = revision_root / f"{_REBIND_BACKUP_PREFIX}{token}"
    journal_path = revision_root / _REBIND_JOURNAL
    journal = {"schema_version": 1, "state": "intent", "stage": stage.name, "backup": backup.name}
    _write_rebind_journal(journal_path, journal)
    try:
        shutil.copytree(casillas_root, stage)
        for path, text in rendered.items():
            atomic_write_text(stage / path.relative_to(casillas_root), text, encoding="utf-8")
        _require_rebound_tree(plan, stage)
        _replace_rebind_tree(casillas_root, backup)
        journal["state"] = "backup_staged"
        _write_rebind_journal(journal_path, journal)
        _replace_rebind_tree(stage, casillas_root)
        journal["state"] = "candidate_live"
        _write_rebind_journal(journal_path, journal)
        _require_rebound_tree(plan, casillas_root)
    except BaseException:
        _restore_rebind_backup(casillas_root, backup)
        _remove_rebind_tree(stage, revision_root)
        if casillas_root.exists():
            _delete_rebind_journal(journal_path)
        raise
    _remove_rebind_tree(backup, revision_root)
    _delete_rebind_journal(journal_path)


def _read_m200_2024_casilla_records_for_root(casillas_root: Path) -> dict[str, _M200CasillaSourceRecord]:
    """Read a staged casilla tree using the same parser as a registry root."""
    return _read_m200_2024_casilla_records_at(casillas_root)


def _recover_m200_source_rebind(plan: M200SourceRebindPlan, registry_root: Path) -> None:
    revision_root = registry_root / "modelos" / "200" / "revisions" / "2024"
    journal_path = revision_root / _REBIND_JOURNAL
    if not journal_path.exists():
        return
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        if (
            set(journal) != {"schema_version", "state", "stage", "backup"}
            or journal["schema_version"] != 1
            or not isinstance(journal["state"], str)
            or journal["state"] not in {"intent", "backup_staged", "candidate_live"}
        ):
            raise ValueError("invalid schema")
        stage = _rebind_transaction_child(revision_root, journal["stage"], _REBIND_STAGE_PREFIX)
        backup = _rebind_transaction_child(revision_root, journal["backup"], _REBIND_BACKUP_PREFIX)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise RegistryValidationError(f"invalid source rebind recovery journal: {journal_path}") from exc
    casillas_root = revision_root / "casillas"
    state = journal["state"]
    if state == "candidate_live" and casillas_root.exists() and backup.exists():
        try:
            _require_rebound_tree(plan, casillas_root)
        except RegistryValidationError:
            _restore_rebind_backup(casillas_root, backup)
        else:
            _remove_rebind_tree(backup, revision_root)
        _remove_rebind_tree(stage, revision_root)
        _delete_rebind_journal(journal_path)
        return
    if state in {"intent", "backup_staged"} and backup.exists():
        _restore_rebind_backup(casillas_root, backup)
    elif state != "intent" and not casillas_root.exists():
        raise RegistryValidationError(f"source rebind journal cannot recover missing canonical tree: {journal_path}")
    _remove_rebind_tree(stage, revision_root)
    _delete_rebind_journal(journal_path)


def _require_rebound_tree(plan: M200SourceRebindPlan, casillas_root: Path) -> None:
    _require_verified_current_design(plan, casillas_root)
    records = _read_m200_2024_casilla_records_for_root(casillas_root)
    if set(records) != set(plan.expected_current_ids):
        raise RegistryValidationError("staged source rebind tree changed its declaration anchors")
    for item in plan.rebinds:
        record = records[item.casilla_id]
        if (
            record.source_refs != item.target_source_refs
            or record.non_source_payload_sha256 != item.non_source_payload_sha256
        ):
            raise RegistryValidationError(f"staged source rebind tree drifted for {item.casilla_id!r}")


def _require_verified_current_design(plan: M200SourceRebindPlan, casillas_root: Path) -> None:
    """Bind every excluded current row to the compiler receipt and exact bytes."""
    from .m200_2024_template_adjudications import (
        compile_m200_2024_same_template_authority,
        promoted_candidate_ids,
    )

    authority = compile_m200_2024_same_template_authority()
    verified = promoted_candidate_ids(authority, casillas_root=casillas_root)
    if verified != frozenset(plan.verified_current_design_ids):
        raise RegistryValidationError(
            "source rebind verified current-design declarations drifted from compiler receipt"
        )


def _replace_rebind_tree(source: Path, destination: Path) -> None:
    import os

    os.replace(source, destination)
    fsync_parent_dir(destination)


def _restore_rebind_backup(casillas_root: Path, backup: Path) -> None:
    if not backup.exists():
        return
    if casillas_root.exists():
        discarded = casillas_root.parent / f"{_REBIND_STAGE_PREFIX}discard-{secrets.token_hex(8)}"
        _replace_rebind_tree(casillas_root, discarded)
        _remove_rebind_tree(discarded, casillas_root.parent)
    _replace_rebind_tree(backup, casillas_root)


def _write_rebind_journal(path: Path, journal: Mapping[str, object]) -> None:
    atomic_write_text(path, json.dumps(journal, sort_keys=True) + "\n", encoding="utf-8")


def _delete_rebind_journal(path: Path) -> None:
    path.unlink(missing_ok=True)
    fsync_parent_dir(path)


def _rebind_transaction_child(root: Path, name: object, prefix: str) -> Path:
    if not isinstance(name, str) or not name.startswith(prefix) or Path(name).name != name:
        raise RegistryValidationError("source rebind journal carries an unsafe transaction path")
    return root / name


def _remove_rebind_tree(path: Path, root: Path) -> None:
    if not path.exists():
        return
    if path.parent.resolve() != root.resolve() or not path.name.startswith(
        (_REBIND_STAGE_PREFIX, _REBIND_BACKUP_PREFIX)
    ):
        raise RegistryValidationError(f"unsafe source rebind transaction cleanup target: {path}")
    shutil.rmtree(path)
    fsync_parent_dir(path)


@dataclass(frozen=True, slots=True)
class _M200CasillaSourceRecord:
    """The one direct ``source_refs`` line owned by one source declaration."""

    casilla_id: str
    path: Path
    document: str
    source_line_index: int
    source_line: str
    source_refs: tuple[str, ...]
    non_source_payload_sha256: str


def _require_rebind_plan_identity(plan: M200SourceRebindPlan) -> None:
    _require_exact_source_identity("source rebind plan", plan.source_ref, plan.source_sha256)
    _require_exact_source_identity(
        "source rebind plan semantic map", plan.semantic_map_source_ref, plan.semantic_map_source_sha256
    )


def _require_rebind_source_refs(rebind: M200SourceRebind) -> None:
    if SIBLING_SOURCE_REF not in rebind.expected_source_refs or TARGET_SOURCE_REF in rebind.expected_source_refs:
        raise RegistryValidationError(
            f"source rebind input is not an exact 2025-only design binding: {rebind.casilla_id!r}"
        )
    if TARGET_SOURCE_REF not in rebind.target_source_refs or SIBLING_SOURCE_REF in rebind.target_source_refs:
        raise RegistryValidationError(
            f"source rebind output is not an exact 2024 design binding: {rebind.casilla_id!r}"
        )
    if len(set(rebind.target_source_refs)) != len(rebind.target_source_refs):
        raise RegistryValidationError(f"source rebind output duplicates a source reference: {rebind.casilla_id!r}")
    expected_other = tuple(ref for ref in rebind.expected_source_refs if ref != SIBLING_SOURCE_REF)
    target_other = tuple(ref for ref in rebind.target_source_refs if ref != TARGET_SOURCE_REF)
    if expected_other != target_other:
        raise RegistryValidationError(
            f"source rebind output alters non-design source references: {rebind.casilla_id!r}"
        )


def _read_m200_2024_casilla_records(registry_root: Path) -> dict[str, _M200CasillaSourceRecord]:
    casillas_root = registry_root / "modelos" / "200" / "revisions" / "2024" / "casillas"
    return _read_m200_2024_casilla_records_at(casillas_root)


def _read_m200_2024_casilla_records_at(casillas_root: Path) -> dict[str, _M200CasillaSourceRecord]:
    if not casillas_root.is_dir():
        raise RegistryValidationError(f"source rebind found no Modelo 200/2024 casilla root: {casillas_root}")
    records: dict[str, _M200CasillaSourceRecord] = {}
    for path in scan_directory(casillas_root, pattern="*.toml"):
        document = path.read_text(encoding="utf-8")
        lines = document.splitlines(keepends=True)
        starts = tuple(index for index, line in enumerate(lines) if _CASILLA_TABLE.match(line.strip()))
        for position, start in enumerate(starts):
            end = starts[position + 1] if position + 1 < len(starts) else len(lines)
            body_end = next((index for index in range(start + 1, end) if lines[index].lstrip().startswith("[")), end)
            ids = tuple(match.group("id") for line in lines[start:body_end] if (match := _ID_LINE.match(line.strip())))
            if len(ids) != 1:
                raise RegistryValidationError(f"{path}: expected one direct casilla id, found {ids!r}")
            source_lines = tuple(
                index for index in range(start, body_end) if _SOURCE_REFS_LINE.match(lines[index]) is not None
            )
            if len(source_lines) != 1:
                raise RegistryValidationError(
                    f"{path}: casilla {ids[0]!r} has {len(source_lines)} direct source_refs anchors; expected one",
                )
            source_line_index = source_lines[0]
            source_refs = _parse_source_refs(path, lines[source_line_index])
            record = _M200CasillaSourceRecord(
                casilla_id=ids[0],
                path=path,
                document=document,
                source_line_index=source_line_index,
                source_line=lines[source_line_index],
                source_refs=source_refs,
                non_source_payload_sha256=_non_source_payload_sha256(lines, start, end, source_line_index),
            )
            if record.casilla_id in records:
                raise RegistryValidationError(
                    f"duplicate source rebind declaration anchor {record.casilla_id!r}: "
                    f"{records[record.casilla_id].path}, {path}",
                )
            records[record.casilla_id] = record
    return records


def _parse_source_refs(path: Path, line: str) -> tuple[str, ...]:
    match = _SOURCE_REFS_LINE.match(line)
    if match is None:  # pragma: no cover - caller selected this line through the same expression
        raise RegistryValidationError(f"{path}: source_refs line lost its anchor")
    try:
        value = rtoml.loads(f"source_refs = {match.group('value')}")["source_refs"]
    except rtoml.TomlParsingError as exc:
        raise RegistryValidationError(f"{path}: cannot parse direct source_refs anchor") from exc
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RegistryValidationError(f"{path}: direct source_refs anchor is not a string array")
    if len(set(value)) != len(value):
        raise RegistryValidationError(f"{path}: direct source_refs anchor duplicates a source reference")
    return tuple(value)


def _render_source_refs_line(original: str, refs: tuple[str, ...]) -> str:
    match = _SOURCE_REFS_LINE.match(original)
    if match is None:  # pragma: no cover - caller holds a validated source line
        raise RegistryValidationError("source rebind lost the direct source_refs anchor")
    if len(set(refs)) != len(refs):
        raise RegistryValidationError("source rebind produced duplicate source references")
    ending = match.group("ending") or ""
    return match.group("prefix") + "[" + ", ".join(f'"{item}"' for item in refs) + "]" + ending


def _non_source_payload_sha256(lines: list[str], start: int, end: int, source_line_index: int) -> str:
    """Digest exact declaration bytes after excluding only its direct source line."""
    payload = "".join(line for index, line in enumerate(lines[start:end], start=start) if index != source_line_index)
    return sha256(payload.encode("utf-8")).hexdigest()


def records_by_path(records: Mapping[str, _M200CasillaSourceRecord], path: Path) -> str:
    """Return the preflight document for ``path`` and reject a split view."""
    documents = {record.document for record in records.values() if record.path == path}
    if len(documents) != 1:
        raise RegistryValidationError(f"source rebind preflight has no unique document for {path}")
    return next(iter(documents))


def _require_non_source_payload_unchanged(before: str, after: str) -> None:
    """Prove a text edit changed only direct declaration ``source_refs`` lines."""
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    if len(before_lines) != len(after_lines):
        raise RegistryValidationError("source rebind altered TOML line structure")
    for before_line, after_line in zip(before_lines, after_lines, strict=True):
        before_is_source = _SOURCE_REFS_LINE.match(before_line) is not None
        after_is_source = _SOURCE_REFS_LINE.match(after_line) is not None
        if before_is_source != after_is_source:
            raise RegistryValidationError("source rebind altered a non-source TOML payload anchor")
        if not before_is_source and before_line != after_line:
            raise RegistryValidationError("source rebind altered non-source TOML payload bytes")


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
    parser.add_argument(
        "--apply-source-rebinds",
        action="store_true",
        help="preflight and atomically apply the exact target-map-owned declaration source rebind plan",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and report --apply-source-rebinds without changing TOML",
    )
    parser.add_argument(
        "--registry-root",
        type=Path,
        default=bundled_path("registry", "aeat"),
        help="registry root (default: canonical bundle; use an isolated temporary root for review)",
    )
    args = parser.parse_args(argv)
    if args.dry_run and not args.apply_source_rebinds:
        parser.error("--dry-run requires --apply-source-rebinds")
    census = reconcile_bundled_m200_2024()
    legal_worklist = _require_closed_m200_2024_legal_worklist(census)
    if args.toml:
        if args.apply_source_rebinds:
            parser.error("--toml cannot be combined with --apply-source-rebinds")
        sys.stdout.write(render_reconciliation_toml(census))
        return 0
    if args.apply_source_rebinds:
        plan = build_m200_source_rebind_plan(census)
        result = apply_m200_source_rebind_plan(plan, registry_root=args.registry_root, dry_run=args.dry_run)
        print(f"eligible={result.planned_rebind_count}")
        print(f"refused_orphans={len(plan.refused_orphan_ids)}")
        print(f"changed_files={len(result.changed_paths)}")
        print(f"dry_run={str(result.dry_run).lower()}")
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
    print(f"legal_worklist_items={len(legal_worklist.items)}")
    print(f"legal_worklist_missing_provenance={legal_worklist.missing_provenance_count}")
    print(f"legal_worklist_unknown_references={legal_worklist.unknown_reference_count}")
    print(f"legal_worklist_out_of_window={legal_worklist.out_of_window_count}")
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
        legal_refs=tuple(entry.legal_refs),
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
        if not _legal_refs_support_proposal(declaration.legal_refs, legal, valid_from, valid_to):
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
            applicable if start <= valid_from and (valid_to is None or end is None or end >= valid_to) else inapplicable
        )
        target.append(ref)
    return tuple(applicable), tuple(inapplicable)


def _legal_worklist_partition(refs, legal: Mapping[str, object], valid_from: date, valid_to: date):
    """Separate absent catalogue keys from known provisions outside 2024.

    Checking the catalogue object's embedded id matters: a dictionary key can
    otherwise make a different provision appear to resolve merely because it
    shares the requested reference key in an in-memory test or a faulty loader.
    """
    applicable, unknown, out_of_window = [], [], []
    for ref in refs:
        authority = legal.get(ref)
        if authority is None:
            unknown.append(ref)
            continue
        if str(getattr(authority, "id", "")) != ref:
            raise RegistryValidationError(
                f"legal catalogue provision mismatch for {ref!r}: found {getattr(authority, 'id', None)!r}"
            )
        start, end = governed_period_span(authority)
        if start <= valid_from and end is not None and end < valid_to:
            out_of_window.append(ref)
        elif start <= valid_from:
            applicable.append(ref)
        else:
            out_of_window.append(ref)
    return tuple(applicable), tuple(unknown), tuple(out_of_window)


def _legal_evidence(refs, legal, valid_from, valid_to):
    """Partition refs and distinguish absent proof from applicable authority."""
    applicable, inapplicable = _legal_partition(refs, legal, valid_from, valid_to)
    state = "missing_legal_provenance" if not refs else "unresolved_or_inapplicable" if inapplicable else "applicable"
    return applicable, inapplicable, state


def _legal_refs_support_proposal(refs, legal, valid_from, valid_to) -> bool:
    """Admit sibling proposals only when non-empty legal proof fully covers 2024."""
    return _legal_evidence(refs, legal, valid_from, valid_to)[2] == "applicable"


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


def _require_reviewed_candidate_promotions(collisions: frozenset[str]) -> None:
    """Allow collisions only when the reviewed target compiler proves live bytes."""
    if not collisions:
        return
    from .m200_2024_template_adjudications import (
        compile_m200_2024_same_template_authority,
        promoted_candidate_ids,
    )

    authority = compile_m200_2024_same_template_authority()
    if collisions != promoted_candidate_ids(authority):
        raise RegistryValidationError(
            "current declarations collide with non-authoritative candidates outside reviewed target adjudications: "
            f"{sorted(collisions)!r}"
        )


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
