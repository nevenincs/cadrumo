"""Audit restored M200/2024 casilla meaning against current structural peers.

Only same-revision declarations attached to an exact normalized-description
template may authorize a repair.  A later revision can explain a finding but
cannot by itself supply 2024 meaning.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path

import rtoml

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.loader import load_catalogue_file, load_modelo_directory
from cadrumo.domain.calculations.registry.schema_references import LegalReference, governed_period_span
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..pipeline._record_design_ir import intermediate_anchor_key, load_record_design_intermediate
from ..pipeline._semantic_map import semantic_anchor_key
from ..pipeline._semantic_map_loader import load_semantic_map

_QUALIFIED_RESTORATION = "DP200018:00588"
_REVISION_ROOT = Path("src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024")
_RESTORATION_COMMITS = ("c930a14cf9", "075ed0294b", "9a3e6f05bb", "0be4f4cd2f")


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
    source_ref: str
    source_sha256: str
    disposition: AuditDisposition
    reason: str
    current: SemanticPayload
    proposed: SemanticPayload | None = None
    cross_revision_status: str = "no_applicable_match"
    cross_revision_evidence_count: int = 0
    cross_revision_proposed: SemanticPayload | None = None


def audit_bundled_restorations(
    *,
    canonical_restoration_root: Path | None = None,
) -> tuple[RestoredSemanticAudit, ...]:
    """Audit the pinned pre-canonical candidate set against current peers."""
    if canonical_restoration_root is not None and any(canonical_restoration_root.iterdir()):
        raise ValueError("pre-canonical audit root must be empty")
    registry_root = bundled_path("registry", "aeat")
    modelo = load_modelo_directory(registry_root / "modelos" / "200")
    revision = modelo.revisions["2024"]
    catalogue_parts = tuple(load_catalogue_file(path) for path in (registry_root / "legal").glob("*.toml"))
    sources = {key: value for part in catalogue_parts for key, value in part.sources.items()}
    legal = {key: value for part in catalogue_parts for key, value in part.legal.items()}
    design = load_record_design_intermediate(
        bundled_path(),
        sources,
        source_ref="aeat-dr-200-2024",
        filing_year=2024,
        design_epoch="2024",
    )
    semantic_map = load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / "2024")
    declarations = {str(item.id): item for item in revision.casillas}
    candidates = _candidate_payloads()
    candidate_ids = frozenset(candidates)
    fields = {intermediate_anchor_key(field): field for sheet in design.sheets for field in sheet.fields}

    candidate_rows: list[tuple[str, str, str, str, Path, SemanticPayload, tuple[object, ...], str, int]] = []
    for entry in semantic_map.entries:
        if entry.casilla_id is None:
            continue
        field = fields[semantic_anchor_key(entry.anchor)]
        printed = _printed_number(field.normalized_description)
        if printed is None:
            continue
        qualified = f"{field.record_identity}:{printed}"
        candidate_id = qualified if qualified in candidates else printed
        candidate = candidates.get(candidate_id)
        if candidate is not None:
            path, payload = candidate
            candidate_rows.append(
                (
                    str(entry.export_field_id),
                    field.normalized_description,
                    _template(field.normalized_description),
                    candidate_id,
                    path,
                    payload,
                    semantic_anchor_key(entry.anchor),
                    field.aeat_type,
                    field.length,
                )
            )

    peer_payloads: dict[str, set[SemanticPayload]] = defaultdict(set)
    for entry in semantic_map.entries:
        if entry.casilla_id is None:
            continue
        declaration = _resolve_declaration(str(entry.casilla_id), declarations)
        if declaration is None or str(declaration.id) in candidate_ids:
            continue
        field = fields[semantic_anchor_key(entry.anchor)]
        peer_payloads[_template(field.normalized_description)].add(_payload(declaration))

    sibling = modelo.revisions["2025-y-siguientes"]
    sibling_design = load_record_design_intermediate(
        bundled_path(), sources, source_ref="aeat-dr-200-2025", filing_year=2025, design_epoch="2025"
    )
    sibling_map = load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / "2025")
    sibling_fields = {
        intermediate_anchor_key(field): field for sheet in sibling_design.sheets for field in sheet.fields
    }
    sibling_declarations = {str(item.id): item for item in sibling.casillas}
    cross_index: dict[tuple[str, str, int], list[tuple[tuple[object, ...], SemanticPayload]]] = defaultdict(list)
    for entry in sibling_map.entries:
        declaration = sibling_declarations.get(str(entry.casilla_id))
        if declaration is None or not _legal_refs_cover_2024(
            declaration, legal, revision.valid_from, revision.valid_to
        ):
            continue
        anchor = semantic_anchor_key(entry.anchor)
        field = sibling_fields[anchor]
        cross_index[(_template(field.normalized_description), field.aeat_type, field.length)].append(
            (anchor, _payload(declaration))
        )

    audits: list[RestoredSemanticAudit] = []
    for export_id, description, template, declaration_id, path, current, anchor, aeat_type, length in candidate_rows:
        peers = peer_payloads.get(template, set())
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
        cross_payloads = {
            payload
            for sibling_anchor, payload in cross_index.get((template, aeat_type, length), ())
            if sibling_anchor != anchor
        }
        cross_count = len(cross_payloads)
        cross_status = (
            "unique_non_authoritative"
            if cross_count == 1
            else "conflicting_non_authoritative"
            if cross_count > 1
            else "no_applicable_match"
        )
        audits.append(
            RestoredSemanticAudit(
                casilla_id=declaration_id,
                export_field_id=export_id,
                official_description=description,
                template=template,
                path=path.as_posix(),
                source_ref=str(design.source.source_ref),
                source_sha256=design.source.source_sha256,
                disposition=disposition,
                reason=reason,
                current=current,
                proposed=proposed,
                cross_revision_status=cross_status,
                cross_revision_evidence_count=cross_count,
                cross_revision_proposed=next(iter(cross_payloads)) if cross_count == 1 else None,
            )
        )
    if len(audits) != 156:
        raise ValueError(f"current 2024 map/design must join all 156 pinned candidates, found {len(audits)}")
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
            "source_ref": audit.source_ref,
            "source_sha256": audit.source_sha256,
            "disposition": audit.disposition.value,
            "reason": audit.reason,
            "cross_revision_status": audit.cross_revision_status,
            "cross_revision_evidence_count": audit.cross_revision_evidence_count,
            "current": _payload_dict(audit.current),
        }
        if audit.proposed is not None:
            row["proposed"] = _payload_dict(audit.proposed)
        if audit.cross_revision_proposed is not None:
            row["cross_revision_proposed_non_authoritative"] = _payload_dict(audit.cross_revision_proposed)
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
    cross_statuses = ("unique_non_authoritative", "conflicting_non_authoritative", "no_applicable_match")
    for status in cross_statuses:
        print(f"cross_revision_{status}={sum(item.cross_revision_status == status for item in audits)}")
    for item in audits:
        if item.disposition is not AuditDisposition.CONFIRMED:
            print(f"{item.disposition.value}[{item.casilla_id}]={item.reason}")
    return 0


def _candidate_payloads() -> dict[str, tuple[Path, SemanticPayload]]:
    """Load candidate payloads from the four pinned pre-canonical reviews."""
    result: dict[str, tuple[Path, SemanticPayload]] = {}
    for commit in _RESTORATION_COMMITS:
        paths = _git(
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            "--diff-filter=A",
            commit,
            "--",
            (_REVISION_ROOT / "casillas").as_posix(),
        ).splitlines()
        archive = _git_bytes("archive", "--format=tar", commit, "--", *paths)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as stream:
            documents = {
                member.name: rtoml.loads(stream.extractfile(member).read().decode("utf-8"))
                for member in stream.getmembers()
                if member.isfile() and member.name in paths
            }
        for raw_path in paths:
            document = documents[raw_path]
            for raw in document["revisions"]["2024"]["casillas"]:
                candidate_id = str(raw["id"])
                if candidate_id in result:
                    raise ValueError(f"duplicate restoration candidate id {candidate_id!r}")
                result[candidate_id] = (Path(raw_path), _raw_payload(raw))
    if len(result) != 156:
        raise ValueError(f"pinned restoration reviews must yield 156 candidates, found {len(result)}")
    return result


def _git(*args: str) -> str:
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git executable is required to read pinned restoration candidates")
    return subprocess.run(  # noqa: S603 - fixed executable and internally constructed arguments
        [executable, *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout


def _git_bytes(*args: str) -> bytes:
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git executable is required to read pinned restoration candidates")
    return subprocess.run(  # noqa: S603 - fixed executable and internally constructed arguments
        [executable, *args],
        check=True,
        capture_output=True,
    ).stdout


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


def _printed_number(description: str) -> str | None:
    matches = re.findall(r"\[([0-9]{5})\]", description)
    return matches[0] if len(matches) == 1 else None


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


def _legal_refs_cover_2024(
    declaration: CasillaDefinition,
    legal: Mapping[object, LegalReference],
    valid_from: date,
    valid_to: date | None,
) -> bool:
    for reference_id in declaration.legal_refs:
        reference = legal.get(reference_id)
        if reference is None:
            return False
        span_from, span_to = governed_period_span(reference)
        if span_from > valid_from:
            return False
        if valid_to is not None and span_to is not None and span_to < valid_to:
            return False
    return True


def _raw_payload(raw: dict[str, object]) -> SemanticPayload:
    return SemanticPayload(
        section=tuple(str(item) for item in raw["section"]),
        semantic_role=str(raw["semantic_role"]) if raw.get("semantic_role") is not None else None,
        data_type=str(raw["data_type"]),
        required=bool(raw["required"]),
        input_kind=str(raw["input_kind"]),
        legal_refs=tuple(str(item) for item in raw["legal_refs"]),
        source_refs=tuple(str(item) for item in raw["source_refs"]),
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
