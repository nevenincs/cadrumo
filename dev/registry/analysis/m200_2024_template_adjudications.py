"""Compile the closed, target-only M200/2024 template-adjudication cohort.

This is an authority compiler, not a candidate resolver.  It admits only the
explicitly listed same-2024 repairs after the frozen worklist has classified
them as repairable, checks each target label against the pinned design, and
rejects both a stale legal reference and any attempt to expand the cohort.
Cross-revision proposals deliberately never enter this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import rtoml

from cadrumo.core.hashing import content_hash_hex, sha256_hex
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.loader import load_catalogue_file
from cadrumo.domain.calculations.registry.schema_references import governed_period_span

from ..pipeline._semantic_map_loader import load_semantic_map
from .m200_restored_semantic_audit import AuditDisposition, RestoredSemanticAudit, audit_bundled_restorations

TARGET_SOURCE_REF = "aeat-dr-200-2024"
TARGET_SOURCE_SHA256 = "ed4df89a451abc2184bc60a1d13ff53a3d38e9a6201698fb635cf0b8ee455218"
MANUAL_SOURCE_REF = "aeat-modelo-200-manual-2024"
MANUAL_SOURCE_SHA256 = "ad02f914246632dcd7ab30f3e7280daf3501be6ee3938237e2ebfe7328ff8179"
TARGET_WINDOW = (date(2024, 1, 1), date(2024, 12, 31))
ADJUDICATION_PATH = Path(__file__).parents[1] / "analysis" / "m200_2024_same_template_adjudications.toml"
_CLOSED_MEMBERSHIP = frozenset({"00942", "02239", "01603", "02412"})


@dataclass(frozen=True, slots=True)
class M200Same2024TemplateAdjudication:
    """One explicitly reviewed, same-target-year declaration authority."""

    casilla_id: str
    export_field_id: str
    official_label_sha256: str
    manual_pages: tuple[int, ...]
    section: tuple[str, ...]
    semantic_role: str
    legal_refs: tuple[str, ...]
    semantic_payload_sha256: str


@dataclass(frozen=True, slots=True)
class CompiledM200Same2024TemplateAuthority:
    """Target-year semantic authority ready for a canonical casilla declaration."""

    source_ref: str
    source_sha256: str
    manual_source_ref: str
    manual_source_sha256: str
    review_status: str
    reviewed_at: str
    reviewed_by: str
    adjudications: tuple[M200Same2024TemplateAdjudication, ...]


def compile_m200_2024_same_template_authority(
    path: Path = ADJUDICATION_PATH,
    *,
    audits: tuple[RestoredSemanticAudit, ...] | None = None,
) -> CompiledM200Same2024TemplateAuthority:
    """Compile only the four target-evidence-complete same-2024 repairs."""
    raw = rtoml.loads(path.read_text(encoding="utf-8"))
    _require_header(raw)
    entries = tuple(_parse_entry(value) for value in raw.get("adjudications", ()))
    if {entry.casilla_id for entry in entries} != _CLOSED_MEMBERSHIP or len(entries) != len(_CLOSED_MEMBERSHIP):
        raise RegistryValidationError("M200/2024 same-template adjudication membership is not closed")
    audit_by_id = {row.casilla_id: row for row in (audit_bundled_restorations() if audits is None else audits)}
    for entry in entries:
        _require_target_audit(entry, audit_by_id.get(entry.casilla_id))
    _require_legal_coverage(entries)
    _require_canonical_map_entries(entries)
    return CompiledM200Same2024TemplateAuthority(
        source_ref=TARGET_SOURCE_REF,
        source_sha256=TARGET_SOURCE_SHA256,
        manual_source_ref=MANUAL_SOURCE_REF,
        manual_source_sha256=MANUAL_SOURCE_SHA256,
        review_status=str(raw["review_status"]),
        reviewed_at=str(raw["reviewed_at"]),
        reviewed_by=str(raw["reviewed_by"]),
        adjudications=tuple(sorted(entries, key=lambda item: item.export_field_id)),
    )


def render_canonical_declaration(authority: CompiledM200Same2024TemplateAuthority, casilla_id: str) -> str:
    """Render one canonical declaration without copying a historic payload."""
    matches = tuple(item for item in authority.adjudications if item.casilla_id == casilla_id)
    if len(matches) != 1:
        raise RegistryValidationError(f"M200/2024 same-template authority has no unique declaration for {casilla_id!r}")
    item = matches[0]
    return "\n".join(
        (
            "[[revisions.2024.casillas]]",
            f"id = {_toml_literal(item.casilla_id)}",
            f"number = {_toml_literal(item.casilla_id)}",
            "data_type = 'money'",
            f"semantic_role = {_toml_literal(item.semantic_role)}",
            "required = false",
            "input_kind = 'manual'",
            f"section = {_toml_array(item.section)}",
            f"legal_refs = {_toml_array(item.legal_refs)}",
            f"source_refs = {_toml_array((authority.source_ref, authority.manual_source_ref))}",
            "",
        )
    )


def verify_canonical_declarations(authority: CompiledM200Same2024TemplateAuthority) -> None:
    """Require committed declarations to be exactly the reviewed compiler output."""
    root = bundled_path("registry", "aeat", "modelos", "200", "revisions", "2024", "casillas")
    for entry in authority.adjudications:
        path = root / f"c{entry.casilla_id}.toml"
        if not path.is_file() or path.read_text(encoding="utf-8") != render_canonical_declaration(
            authority, entry.casilla_id
        ):
            raise RegistryValidationError(
                f"M200/2024 same-template declaration {entry.casilla_id!r} is not compiler-identical"
            )


def promoted_candidate_ids(authority: CompiledM200Same2024TemplateAuthority) -> frozenset[str]:
    """Return only reviewed candidates whose exact compiler bytes are live."""
    verify_canonical_declarations(authority)
    return frozenset(entry.casilla_id for entry in authority.adjudications)


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
        raise RegistryValidationError("M200/2024 same-template adjudication header is not target-authoritative")
    if not isinstance(raw.get("reviewed_at"), str) or not isinstance(raw.get("reviewed_by"), str):
        raise RegistryValidationError("M200/2024 same-template adjudication lacks reviewer provenance")


def _toml_literal(value: str) -> str:
    if "'" in value:
        raise RegistryValidationError("M200/2024 same-template declaration cannot render an apostrophe")
    return f"'{value}'"


def _toml_array(values: tuple[str, ...]) -> str:
    return "[\n" + "".join(f"    {_toml_literal(value)},\n" for value in values) + "]"


def _semantic_payload_digest(entry: M200Same2024TemplateAdjudication) -> str:
    return content_hash_hex(
        {
            "section": entry.section,
            "semantic_role": entry.semantic_role,
            "data_type": "money",
            "required": False,
            "input_kind": "manual",
            "legal_refs": entry.legal_refs,
            "source_refs": (TARGET_SOURCE_REF, MANUAL_SOURCE_REF),
        }
    )


def _require_canonical_map_entries(entries: tuple[M200Same2024TemplateAdjudication, ...]) -> None:
    semantic_map = load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / "2024")
    if (semantic_map.source_ref, semantic_map.source_sha256) != (TARGET_SOURCE_REF, TARGET_SOURCE_SHA256):
        raise RegistryValidationError("M200/2024 same-template semantic map source drifted")
    by_export_id = {str(entry.export_field_id): entry for entry in semantic_map.entries}
    for adjudication in entries:
        map_entry = by_export_id.get(adjudication.export_field_id)
        if map_entry is None or str(map_entry.casilla_id) != adjudication.casilla_id:
            raise RegistryValidationError(
                f"M200/2024 same-template adjudication {adjudication.casilla_id!r} lacks its canonical map owner"
            )
        if tuple(map_entry.legal_refs) != adjudication.legal_refs:
            raise RegistryValidationError(
                f"M200/2024 same-template adjudication {adjudication.casilla_id!r} map legal authority drifted"
            )


def _parse_entry(raw: object) -> M200Same2024TemplateAdjudication:
    if not isinstance(raw, dict):
        raise RegistryValidationError("M200/2024 same-template adjudication entry is malformed")
    try:
        value = M200Same2024TemplateAdjudication(
            casilla_id=str(raw["casilla_id"]),
            export_field_id=str(raw["export_field_id"]),
            official_label_sha256=str(raw["official_label_sha256"]),
            manual_pages=tuple(int(page) for page in raw["manual_pages"]),
            section=tuple(str(part) for part in raw["section"]),
            semantic_role=str(raw["semantic_role"]),
            legal_refs=tuple(str(reference) for reference in raw["legal_refs"]),
            semantic_payload_sha256=str(raw["semantic_payload_sha256"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RegistryValidationError("M200/2024 same-template adjudication entry is malformed") from exc
    if not value.manual_pages or not value.section or not value.semantic_role or not value.legal_refs:
        raise RegistryValidationError("M200/2024 same-template adjudication omits required reviewed authority")
    if value.semantic_payload_sha256 != _semantic_payload_digest(value):
        raise RegistryValidationError("M200/2024 same-template adjudication semantic payload drifted")
    return value


def _require_target_audit(entry: M200Same2024TemplateAdjudication, audit: RestoredSemanticAudit | None) -> None:
    if audit is None or audit.disposition is not AuditDisposition.REPAIRABLE or audit.proposed is None:
        raise RegistryValidationError(
            f"M200/2024 adjudication {entry.casilla_id!r} is not a repairable same-year template"
        )
    if (audit.source_ref, audit.source_sha256) != (TARGET_SOURCE_REF, TARGET_SOURCE_SHA256):
        raise RegistryValidationError(f"M200/2024 adjudication {entry.casilla_id!r} target source drifted")
    if audit.export_field_id != entry.export_field_id:
        raise RegistryValidationError(f"M200/2024 adjudication {entry.casilla_id!r} target anchor drifted")
    if sha256_hex(audit.official_description.encode("utf-8")) != entry.official_label_sha256:
        raise RegistryValidationError(f"M200/2024 adjudication {entry.casilla_id!r} official label drifted")
    proposed = audit.proposed
    if (proposed.section, proposed.semantic_role, proposed.legal_refs) != (
        entry.section,
        entry.semantic_role,
        entry.legal_refs,
    ):
        raise RegistryValidationError(
            f"M200/2024 adjudication {entry.casilla_id!r} no longer agrees with its exact peer"
        )


def _require_legal_coverage(entries: tuple[M200Same2024TemplateAdjudication, ...]) -> None:
    legal = {
        key: value
        for part in (
            load_catalogue_file(path) for path in sorted(bundled_path("registry", "aeat", "legal").glob("*.toml"))
        )
        for key, value in part.legal.items()
    }
    for entry in entries:
        for reference in entry.legal_refs:
            provision = legal.get(reference)
            if provision is None or str(provision.id) != reference:
                raise RegistryValidationError(
                    f"M200/2024 adjudication {entry.casilla_id!r} has unresolved legal authority"
                )
            start, end = governed_period_span(provision)
            if start > TARGET_WINDOW[0] or (end is not None and end < TARGET_WINDOW[1]):
                raise RegistryValidationError(
                    f"M200/2024 adjudication {entry.casilla_id!r} legal authority misses 2024"
                )
