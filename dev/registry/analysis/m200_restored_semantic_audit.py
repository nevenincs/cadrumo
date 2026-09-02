"""Audit restored M200/2024 casilla meaning against current structural peers.

Only same-revision declarations attached to an exact normalized-description
template may authorize a repair.  A later revision can explain a finding but
cannot by itself supply 2024 meaning.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import rtoml

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.loader import load_catalogue_file, load_modelo_directory
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..pipeline._record_design_ir import intermediate_anchor_key, load_record_design_intermediate
from ..pipeline._semantic_map import semantic_anchor_key
from ..pipeline._semantic_map_loader import load_semantic_map

_RESTORED_MARKER = "Semantic payload reviewed from pinned repository commit"
_QUALIFIED_RESTORATION = "DP200018:00588"
_REVISION_ROOT = Path("src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024")


class AuditDisposition(StrEnum):
    """Closed audit outcomes."""

    CONFIRMED = "confirmed"
    REPAIRABLE = "repairable"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class SemanticPayload:
    """Meaning-bearing declaration fields audited as one indivisible value."""

    section: tuple[str, ...]
    semantic_role: str | None
    data_type: str
    required: bool
    input_kind: str
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RestoredSemanticAudit:
    """One restored casilla and its deterministic peer verdict."""

    casilla_id: str
    export_field_id: str
    official_description: str
    template: str
    path: str
    disposition: AuditDisposition
    reason: str
    current: SemanticPayload
    proposed: SemanticPayload | None = None


def audit_bundled_restorations() -> tuple[RestoredSemanticAudit, ...]:
    """Audit every restoration marker plus the reviewed DP200018 identity."""
    registry_root = bundled_path("registry", "aeat")
    modelo = load_modelo_directory(registry_root / "modelos" / "200")
    revision = modelo.revisions["2024"]
    catalogues = load_catalogue_file(registry_root / "legal" / "is.toml")
    design = load_record_design_intermediate(
        bundled_path(),
        catalogues.sources,
        source_ref="aeat-dr-200-2024",
        filing_year=2024,
        design_epoch="2024",
    )
    semantic_map = load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / "2024")
    declarations = {str(item.id): item for item in revision.casillas}
    restored_paths = _restored_paths(bundled_path().parents[2])
    rows: list[tuple[str, str, str, CasillaDefinition]] = []
    fields = {intermediate_anchor_key(field): field for sheet in design.sheets for field in sheet.fields}
    for entry in semantic_map.entries:
        if entry.casilla_id is None:
            continue
        declaration = _resolve_declaration(str(entry.casilla_id), declarations)
        if declaration is None:
            continue
        field = fields[semantic_anchor_key(entry.anchor)]
        rows.append(
            (
                str(entry.export_field_id),
                field.normalized_description,
                _template(field.normalized_description),
                declaration,
            )
        )

    restored_ids = set(restored_paths) | {_QUALIFIED_RESTORATION}
    peer_payloads: dict[str, set[SemanticPayload]] = defaultdict(set)
    for _export_id, _description, template, declaration in rows:
        if str(declaration.id) not in restored_ids:
            peer_payloads[template].add(_payload(declaration))

    audits: list[RestoredSemanticAudit] = []
    for export_id, description, template, declaration in rows:
        declaration_id = str(declaration.id)
        if declaration_id not in restored_ids:
            continue
        path = restored_paths.get(declaration_id, _REVISION_ROOT / "casillas" / "cDP200018+00588.toml")
        peers = peer_payloads.get(template, set())
        current = _payload(declaration)
        contradiction = _direct_contradiction(description, current)
        if len(peers) == 1:
            proposed = next(iter(peers))
            disposition = AuditDisposition.CONFIRMED if proposed == current else AuditDisposition.REPAIRABLE
            reason = contradiction or "unique same-revision official-description template peer"
        elif peers:
            proposed = None
            disposition = AuditDisposition.UNRESOLVED
            reason = contradiction or f"same-revision template has {len(peers)} conflicting semantic payloads"
        else:
            proposed = None
            disposition = AuditDisposition.UNRESOLVED
            reason = contradiction or "no non-restored same-revision official-description template peer"
        audits.append(
            RestoredSemanticAudit(
                casilla_id=declaration_id,
                export_field_id=export_id,
                official_description=description,
                template=template,
                path=path.as_posix(),
                disposition=disposition,
                reason=reason,
                current=current,
                proposed=proposed,
            )
        )
    return tuple(sorted(audits, key=lambda item: item.export_field_id))


def render_review_toml(audits: tuple[RestoredSemanticAudit, ...]) -> str:
    """Render the complete deterministic worklist."""
    rows = []
    for audit in audits:
        row = {
            "casilla_id": audit.casilla_id,
            "export_field_id": audit.export_field_id,
            "official_description": audit.official_description,
            "template": audit.template,
            "path": audit.path,
            "disposition": audit.disposition.value,
            "reason": audit.reason,
            "current": _payload_dict(audit.current),
        }
        if audit.proposed is not None:
            row["proposed"] = _payload_dict(audit.proposed)
        rows.append(row)
    return rtoml.dumps({"schema_version": 1, "audit": rows}, pretty=True)


def render_apply_patch(audits: tuple[RestoredSemanticAudit, ...]) -> str:
    """Emit only uniquely proved repairs; unresolved rows remain untouched."""
    repairs = tuple(item for item in audits if item.disposition is AuditDisposition.REPAIRABLE)
    if not repairs:
        raise ValueError("cannot emit semantic patch because no restoration has a uniquely proved repair")
    lines = ["*** Begin Patch"]
    for audit in repairs:
        assert audit.proposed is not None  # noqa: S101 - disposition invariant
        lines.extend(_patch_hunk(audit))
    lines.append("*** End Patch")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Run the bundled audit, review renderer, or fail-closed patch renderer."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-toml", action="store_true")
    parser.add_argument("--emit-patch", action="store_true")
    args = parser.parse_args(argv)
    audits = audit_bundled_restorations()
    if args.review_toml:
        sys.stdout.write(render_review_toml(audits))
        return 0
    if args.emit_patch:
        try:
            sys.stdout.write(render_apply_patch(audits))
        except ValueError as exc:
            sys.stderr.write(f"refused: {exc}\n")
            return 1
        return 0
    counts = {item.value: sum(row.disposition is item for row in audits) for item in AuditDisposition}
    print(f"total={len(audits)}")
    for disposition in AuditDisposition:
        print(f"{disposition.value}={counts[disposition.value]}")
    for item in audits:
        if item.disposition is not AuditDisposition.CONFIRMED:
            print(f"{item.disposition.value}[{item.casilla_id}]={item.reason}")
    return 0


def _restored_paths(workspace_root: Path) -> dict[str, Path]:
    root = workspace_root / _REVISION_ROOT / "casillas"
    result: dict[str, Path] = {}
    for path in root.glob("*.toml"):
        text = path.read_text(encoding="utf-8")
        if _RESTORED_MARKER not in text:
            continue
        document = rtoml.loads(text)
        for declaration in document["revisions"]["2024"]["casillas"]:
            result[str(declaration["id"])] = path.relative_to(workspace_root)
    return result


def _resolve_declaration(token: str, declarations: dict[str, CasillaDefinition]) -> CasillaDefinition | None:
    exact = declarations.get(token)
    if exact is not None:
        return exact
    if not token.isdecimal():
        return None
    matches = tuple(
        declaration
        for identifier, declaration in declarations.items()
        if identifier.isdecimal() and identifier.lstrip("0") == token.lstrip("0")
    )
    return matches[0] if len(matches) == 1 else None


def _template(description: str) -> str:
    without_box = re.sub(r"\[[0-9]{5}\]", "[#]", description)
    return re.sub(r"\b20[0-9]{2}\b", "{year}", without_box)


def _direct_contradiction(description: str, payload: SemanticPayload) -> str | None:
    normalized = description.casefold()
    role = (payload.semantic_role or "").casefold()
    section = " ".join(payload.section).casefold()
    if "otras deducciones relativas a programas de apoyo" in normalized and "innovacion_tecnologica" in role:
        return "official exceptional-public-interest description contradicts restored innovation semantic role"
    if "reserva de nivelaci" in normalized and ("capitalizacion" in role or "capitalizacion" in section):
        return "official nivelacion description contradicts restored capitalizacion semantic payload"
    return None


def _payload(declaration: CasillaDefinition) -> SemanticPayload:
    return SemanticPayload(
        section=tuple(declaration.section),
        semantic_role=declaration.semantic_role,
        data_type=str(declaration.data_type),
        required=declaration.required,
        input_kind=str(declaration.input_kind),
        legal_refs=tuple(declaration.legal_refs),
        source_refs=tuple(declaration.source_refs),
    )


def _payload_dict(payload: SemanticPayload) -> dict[str, object]:
    return {
        "section": list(payload.section),
        "semantic_role": payload.semantic_role or "",
        "data_type": payload.data_type,
        "required": payload.required,
        "input_kind": payload.input_kind,
        "legal_refs": list(payload.legal_refs),
        "source_refs": list(payload.source_refs),
    }


def _patch_hunk(audit: RestoredSemanticAudit) -> tuple[str, ...]:
    current = audit.current
    proposed = audit.proposed
    if proposed is None:
        raise ValueError("repairable audit has no proposed payload")

    def quote(value: str) -> str:
        return json.dumps(value, ensure_ascii=False)

    def array(values: tuple[str, ...]) -> str:
        return "[" + ", ".join(quote(value) for value in values) + "]"

    old = _payload_lines(current, quote=quote, array=array)
    new = _payload_lines(proposed, quote=quote, array=array)
    return (f"*** Update File: {audit.path}", "@@", *(f"-{line}" for line in old), *(f"+{line}" for line in new))


def _payload_lines(
    payload: SemanticPayload,
    *,
    quote: Callable[[str], str],
    array: Callable[[tuple[str, ...]], str],
) -> tuple[str, ...]:
    return (
        f"section = {array(payload.section)}",
        f"semantic_role = {quote(payload.semantic_role or '')}",
        f"data_type = {quote(payload.data_type)}",
        f"required = {str(payload.required).lower()}",
        f"input_kind = {quote(payload.input_kind)}",
        f"legal_refs = {array(payload.legal_refs)}",
        f"source_refs = {array(payload.source_refs)}",
    )


if __name__ == "__main__":
    raise SystemExit(main())
