"""Compile the explicit, target-evidence-reviewed M200/2024 S14/S15 cohort.

The 119-row blocker screen remains diagnostic-only.  This compiler admits only
the disjoint 116-member authority cohort recorded beside it; it never consumes
a sibling declaration or proposal payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import rtoml

from cadrumo.core.hashing import sha256_hex
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.loader import load_catalogue_file
from cadrumo.domain.calculations.registry.schema_references import governed_period_span

from .m200_2024_blocker_adjudication import (
    BLOCKER_STATUSES,
    MANUAL_SOURCE_REF,
    MANUAL_SOURCE_SHA256,
    TARGET_SOURCE_REF,
    TARGET_SOURCE_SHA256,
    build_worklist,
)
from .m200_2024_template_adjudications import (
    CompiledM200Same2024TemplateAuthority,
    compile_m200_2024_same_template_authority,
)
from .m200_restored_semantic_audit import RestoredSemanticAudit, audit_bundled_restorations

ADJUDICATION_PATH = Path(__file__).with_suffix(".toml")
TARGET_WINDOW = (date(2024, 1, 1), date(2024, 12, 31))
S12_CONFLICT_RECEIPT = frozenset({"02239", "01603", "02412"})
S12_MEMBERS = frozenset({"00942", *S12_CONFLICT_RECEIPT})
S13_EXPECTED_COUNT = 36
S14_S15_EXPECTED_COUNT = 116


@dataclass(frozen=True, slots=True)
class Adjudication:
    """One reviewed blocker casilla, bound to the official label it was adjudicated against."""

    casilla_id: str
    export_field_id: str
    source_cohort: str
    official_label_sha256: str
    manual_pages: tuple[int, ...]
    section: tuple[str, ...]
    semantic_role: str | None
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompiledM200BlockerAuthority:
    """The reviewed blocker adjudications with the review that admitted them."""

    reviewed_by: str
    reviewed_at: str
    adjudications: tuple[Adjudication, ...]


def compile_m200_2024_blocker_authority(
    path: Path = ADJUDICATION_PATH,
    *,
    audits: tuple[RestoredSemanticAudit, ...] | None = None,
    worklist: dict[str, object] | None = None,
    same_template_authority: CompiledM200Same2024TemplateAuthority | None = None,
) -> CompiledM200BlockerAuthority:
    """Compile the closed S14/S15 declarations from target-only evidence."""
    raw = rtoml.loads(path.read_text(encoding="utf-8"))
    _require_header(raw)
    rows = tuple(_parse_row(row) for row in raw.get("adjudications", ()))
    _require_partition(rows, audits=audits, same_template_authority=same_template_authority)
    target_worklist = {
        str(row["casilla_id"]): row
        for row in (build_worklist(audits=audits) if worklist is None else worklist)["member"]
    }
    _require_target_evidence(rows, target_worklist)
    _require_legal_coverage(rows)
    _require_canonical_map(rows)
    return CompiledM200BlockerAuthority(
        reviewed_by=str(raw["reviewed_by"]),
        reviewed_at=str(raw["reviewed_at"]),
        adjudications=tuple(sorted(rows, key=lambda item: item.export_field_id)),
    )


def render_canonical_declaration(authority: CompiledM200BlockerAuthority, casilla_id: str) -> str:
    """Render the only permitted canonical bytes for one S14/S15 member."""
    matches = tuple(row for row in authority.adjudications if row.casilla_id == casilla_id)
    if len(matches) != 1:
        raise RegistryValidationError(f"M200/2024 blocker authority has no unique declaration for {casilla_id!r}")
    row = matches[0]
    lines = [
        "[[revisions.2024.casillas]]",
        f"id = {_literal(row.casilla_id)}",
        f"number = {_literal(row.casilla_id)}",
        "data_type = 'money'",
    ]
    if row.semantic_role is not None:
        lines.append(f"semantic_role = {_literal(row.semantic_role)}")
    lines.extend(
        (
            "required = false",
            "input_kind = 'manual'",
            f"section = {_array(row.section)}",
            f"legal_refs = {_array(row.legal_refs)}",
            f"source_refs = {_array((TARGET_SOURCE_REF, MANUAL_SOURCE_REF))}",
            "",
        )
    )
    return "\n".join(lines)


def verify_canonical_declarations(
    authority: CompiledM200BlockerAuthority, *, casillas_root: Path | None = None
) -> None:
    """Refuse unless every adjudicated casilla matches its declared canonical record."""
    root = (
        bundled_path("registry", "aeat", "modelos", "200", "revisions", "2024", "casillas")
        if casillas_root is None
        else casillas_root
    )
    for row in authority.adjudications:
        path = root / f"c{row.casilla_id}.toml"
        if not path.is_file() or path.read_text(encoding="utf-8") != render_canonical_declaration(
            authority, row.casilla_id
        ):
            raise RegistryValidationError(f"M200/2024 blocker declaration {row.casilla_id!r} is not compiler-identical")


def promoted_candidate_ids(
    authority: CompiledM200BlockerAuthority, *, casillas_root: Path | None = None
) -> frozenset[str]:
    """Return candidates only after a fresh equal receipt and byte check."""
    if authority != compile_m200_2024_blocker_authority():
        raise RegistryValidationError("M200/2024 blocker compiler receipt/provenance drifted")
    verify_canonical_declarations(authority, casillas_root=casillas_root)
    return frozenset(row.casilla_id for row in authority.adjudications)


def _require_header(raw: dict[str, object]) -> None:
    expected = {
        "schema_version": 1,
        "modelo": "200",
        "revision": "2024",
        "source_ref": TARGET_SOURCE_REF,
        "source_sha256": TARGET_SOURCE_SHA256,
        "manual_source_ref": MANUAL_SOURCE_REF,
        "manual_source_sha256": MANUAL_SOURCE_SHA256,
        "review_status": "agent_reviewed",
    }
    if any(raw.get(key) != value for key, value in expected.items()):
        raise RegistryValidationError("M200/2024 blocker adjudication header is not target-authoritative")
    if not isinstance(raw.get("reviewed_at"), str) or not isinstance(raw.get("reviewed_by"), str):
        raise RegistryValidationError("M200/2024 blocker adjudication lacks reviewer provenance")


def _parse_row(raw: object) -> Adjudication:
    if not isinstance(raw, dict):
        raise RegistryValidationError("M200/2024 blocker adjudication entry is malformed")
    try:
        row = Adjudication(
            casilla_id=str(raw["casilla_id"]),
            export_field_id=str(raw["export_field_id"]),
            source_cohort=str(raw["source_cohort"]),
            official_label_sha256=str(raw["official_label_sha256"]),
            manual_pages=tuple(int(page) for page in raw["manual_pages"]),
            section=tuple(str(item) for item in raw["section"]),
            semantic_role=None if raw.get("semantic_role") is None else str(raw["semantic_role"]),
            legal_refs=tuple(str(item) for item in raw["legal_refs"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RegistryValidationError("M200/2024 blocker adjudication entry is malformed") from exc
    if row.source_cohort not in BLOCKER_STATUSES or not row.manual_pages or not row.section or not row.legal_refs:
        raise RegistryValidationError("M200/2024 blocker adjudication omits target authority")
    return row


def _require_partition(
    rows: tuple[Adjudication, ...],
    *,
    audits: tuple[RestoredSemanticAudit, ...] | None = None,
    same_template_authority: CompiledM200Same2024TemplateAuthority | None = None,
) -> None:
    ids = frozenset(row.casilla_id for row in rows)
    if len(ids) != len(rows) or len(rows) != S14_S15_EXPECTED_COUNT or ids & S12_MEMBERS:
        raise RegistryValidationError("M200/2024 S14/S15 adjudication membership is not closed and disjoint")
    s12 = (
        compile_m200_2024_same_template_authority(audits=audits)
        if same_template_authority is None
        else same_template_authority
    )
    # This validates the receipt membership here.  Canonical byte verification
    # is performed once by the invocation-owned promotions snapshot that
    # supplies this receipt, avoiding a second full compiler replay.
    if frozenset(item.casilla_id for item in s12.adjudications) != S12_MEMBERS:
        raise RegistryValidationError("M200/2024 S12 receipt is not exact")
    audit_rows = audit_bundled_restorations() if audits is None else audits
    # The S12 template receipt also settles the one candidate that the older
    # diagnostic classifies as cross-revision-unique; S13 therefore owns the
    # remaining 36 unique proposals, not a second overlapping receipt.
    unique = frozenset(
        row.casilla_id
        for row in audit_rows
        if row.cross_revision_status == "unique_non_authoritative" and row.casilla_id not in S12_MEMBERS
    )
    blockers = frozenset(row.casilla_id for row in audit_rows if row.cross_revision_status in BLOCKER_STATUSES)
    if (
        len(unique) != S13_EXPECTED_COUNT
        or len(audit_rows) != len(S12_MEMBERS | unique | ids)
        or blockers != ids | S12_CONFLICT_RECEIPT
    ):
        raise RegistryValidationError("M200/2024 S12/S13/S14/S15 partition is not exhaustive")


def _require_target_evidence(rows: tuple[Adjudication, ...], worklist: dict[str, object]) -> None:
    if set(worklist) != {row.casilla_id for row in rows} | S12_CONFLICT_RECEIPT:
        raise RegistryValidationError("M200/2024 blocker diagnostic membership drifted")
    for row in rows:
        target = worklist.get(row.casilla_id)
        if target is None or target["source_cohort"] != row.source_cohort:
            raise RegistryValidationError(f"M200/2024 blocker {row.casilla_id!r} has drifted cohort evidence")
        if target["export_field_id"] != row.export_field_id:
            raise RegistryValidationError(f"M200/2024 blocker {row.casilla_id!r} has drifted target anchor")
        if sha256_hex(str(target["official_description"]).encode("utf-8")) != row.official_label_sha256:
            raise RegistryValidationError(f"M200/2024 blocker {row.casilla_id!r} official label drifted")
        manual = target["manual_locator"]
        if (
            tuple(manual["pages"]) != row.manual_pages
            or manual["source_ref"] != MANUAL_SOURCE_REF
            or manual["sha256"] != MANUAL_SOURCE_SHA256
        ):
            raise RegistryValidationError(f"M200/2024 blocker {row.casilla_id!r} manual evidence drifted")


def _require_canonical_map(rows: tuple[Adjudication, ...]) -> None:
    from ..pipeline._semantic_map_loader import load_semantic_map

    semantic_map = load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / "2024")
    entries = {str(entry.export_field_id): entry for entry in semantic_map.entries}
    for row in rows:
        entry = entries.get(row.export_field_id)
        # The pre-adjudication map retained numeric TOML spellings.  Its typed
        # owner is a CasillaId, so compare the canonical five-digit identity;
        # declaration bytes themselves always carry that canonical spelling.
        owner = None if entry is None or entry.casilla_id is None else str(entry.casilla_id).zfill(5)
        if entry is None or owner != row.casilla_id or tuple(entry.legal_refs) != row.legal_refs:
            raise RegistryValidationError(f"M200/2024 blocker {row.casilla_id!r} map authority drifted")


def _require_legal_coverage(rows: tuple[Adjudication, ...]) -> None:
    legal = {
        key: value
        for part in (load_catalogue_file(path) for path in bundled_path("registry", "aeat", "legal").glob("*.toml"))
        for key, value in part.legal.items()
    }
    for row in rows:
        for ref in row.legal_refs:
            provision = legal.get(ref)
            if provision is None or str(provision.id) != ref:
                raise RegistryValidationError(f"M200/2024 blocker {row.casilla_id!r} has unresolved legal authority")
            start, end = governed_period_span(provision)
            if start > TARGET_WINDOW[0] or (end is not None and end < TARGET_WINDOW[1]):
                raise RegistryValidationError(f"M200/2024 blocker {row.casilla_id!r} legal authority misses 2024")


def _literal(value: str) -> str:
    if "'" in value:
        raise RegistryValidationError("M200/2024 blocker declaration cannot render an apostrophe")
    return f"'{value}'"


def _array(values: tuple[str, ...]) -> str:
    return "[\n" + "".join(f"    {_literal(value)},\n" for value in values) + "]"
