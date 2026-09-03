"""Generate proposal-only M200/2024 historic restoration diagnostics.

The current 2024 design and semantic map own target identity and source proof.
The pinned historic tree is useful evidence for a reviewer, but it is not a
source of registry declarations.  This tool therefore emits a review TOML
document only; it has no registry-fragment or patch writer.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import rtoml

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.loader import load_catalogue_file

from ..pipeline._record_design_ir import (
    RecordDesignIntermediateField,
    intermediate_anchor_key,
    load_record_design_intermediate,
)
from ..pipeline._semantic_map import SemanticMap, SemanticMapEntry, semantic_anchor_key
from ..pipeline._semantic_map_loader import load_semantic_map
from .m200_semantic_casilla_candidates import M200CasillaDisposition, _load_bundled_candidates

HISTORIC_COMMIT = "17eb283313"
HISTORIC_ROOT = "src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/casillas"

__all__ = [
    "HISTORIC_COMMIT",
    "RestorationProposal",
    "RestorationRefusal",
    "build_bundled_restoration_proposals",
    "main",
    "render_review_toml",
]


@dataclass(frozen=True, slots=True)
class RestorationProposal:
    """One non-authoritative proposal carrying historic semantic evidence.

    The target description and source digest are copied from the current
    official design so a reviewer can compare the two evidence sets.  The
    historic semantic fields intentionally remain payload in a proposal and
    are never rendered under the canonical ``revisions`` TOML schema.
    """

    id: str
    number: str
    target_description: str
    section: tuple[str, ...]
    semantic_role: str
    data_type: str
    required: bool
    input_kind: str
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    export_field_id: str
    target_source_ref: str
    target_source_sha256: str
    historic_commit: str
    historic_path: str


@dataclass(frozen=True, slots=True)
class RestorationRefusal:
    """One gap whose historic evidence cannot form even a review proposal."""

    export_field_id: str
    reason: str


def build_bundled_restoration_proposals() -> tuple[tuple[RestorationProposal, ...], tuple[RestorationRefusal, ...]]:
    """Join current 2024 gaps to pinned history for review-only diagnostics.

    The exact current design is loaded independently of the classifier so a
    mutated target description or source digest cannot silently become a
    proposal.  Historic payload is checked against its pinned Git blob as well.
    """
    classified = _load_bundled_candidates()
    current_map = load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / "2024")
    if not isinstance(current_map, SemanticMap):
        raise TypeError("semantic-map loader returned a non-semantic-map value")
    current_entries = {str(entry.export_field_id): entry for entry in current_map.entries}
    target_fields = _load_target_field_index(current_map)
    historic = _historic_index()
    proposals: list[RestorationProposal] = []
    refused: list[RestorationRefusal] = []
    for gap in classified:
        if gap.disposition is not M200CasillaDisposition.REVISION_MISSING_DECLARATION:
            continue
        entry = current_entries[gap.export_field_id]
        target_field = target_fields.get(gap.export_field_id)
        if target_fields and target_field is None:
            refused.append(
                RestorationRefusal(gap.export_field_id, "current export anchor is absent from the pinned target design")
            )
            continue
        matches = historic.get(gap.export_field_id, ())
        if len(matches) != 1:
            refused.append(RestorationRefusal(gap.export_field_id, f"historic export match count is {len(matches)}"))
            continue
        path, payload = matches[0]
        if not _historic_payload_is_pinned(path, gap.export_field_id, payload):
            refused.append(
                RestorationRefusal(gap.export_field_id, "historic semantic payload differs from its pinned Git blob")
            )
            continue
        reason = _refusal_reason(
            gap,
            entry,
            payload,
            expected_target_description=(target_field.normalized_description if target_field is not None else None),
            expected_source_ref=(str(current_map.source_ref) if isinstance(current_map, SemanticMap) else None),
            expected_source_sha256=(current_map.source_sha256 if isinstance(current_map, SemanticMap) else None),
        )
        if reason is not None:
            refused.append(RestorationRefusal(gap.export_field_id, reason))
            continue
        printed = _printed_number(gap.label)
        if printed is None:  # pragma: no cover - proved by _refusal_reason
            raise RuntimeError("accepted proposal lost its current official number")
        proposals.append(
            RestorationProposal(
                id=printed,
                number=printed,
                target_description=gap.label,
                section=tuple(payload["section"]),
                semantic_role=payload["semantic_role"],
                data_type=payload["data_type"],
                required=payload["required"],
                input_kind=payload["input_kind"],
                legal_refs=tuple(payload["legal_refs"]),
                source_refs=tuple(payload["source_refs"]),
                export_field_id=gap.export_field_id,
                target_source_ref=gap.source_ref,
                target_source_sha256=gap.source_sha256,
                historic_commit=HISTORIC_COMMIT,
                historic_path=path,
            ),
        )
    return (
        tuple(sorted(proposals, key=lambda item: item.export_field_id)),
        tuple(sorted(refused, key=lambda item: item.export_field_id)),
    )


def render_review_toml(
    proposals: tuple[RestorationProposal, ...],
    refusals: tuple[RestorationRefusal, ...] = (),
) -> str:
    """Render explicit proposal-only diagnostics, never registry TOML.

    In particular, the output has no ``revisions`` table and no canonical
    fragment path.  The marker is machine-readable so a future compiler can
    refuse this document before it reaches registry authority.
    """
    document: dict[str, object] = {
        "schema_version": 2,
        "authority_status": "proposal_only",
        "historic_commit": HISTORIC_COMMIT,
    }
    if proposals:
        document["restoration_proposal"] = [asdict(proposal) for proposal in proposals]
    if refusals:
        document["restoration_refusal"] = [asdict(refusal) for refusal in refusals]
    return rtoml.dumps(document, pretty=True)


def main(argv: list[str] | None = None) -> int:
    """Emit proposal-only review TOML to stdout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    proposals, refusals = build_bundled_restoration_proposals()
    sys.stdout.write(render_review_toml(proposals, refusals))
    return 1 if refusals else 0


def _historic_index() -> dict[str, tuple[tuple[str, dict[str, Any]], ...]]:
    paths = _git("ls-tree", "-r", "--name-only", HISTORIC_COMMIT, "--", HISTORIC_ROOT).splitlines()
    index: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for path in paths:
        if "/z2024only-" not in path:
            continue
        document = rtoml.loads(_git("show", f"{HISTORIC_COMMIT}:{path}"))
        for declaration in document["revisions"]["2024"]["casillas"]:
            export_refs = declaration.get("export_refs", [])
            if len(export_refs) == 1:
                index.setdefault(export_refs[0], []).append((path, declaration))
    return {key: tuple(value) for key, value in index.items()}


def _historic_payload_is_pinned(path: str, export_field_id: str, payload: dict[str, Any]) -> bool:
    """Verify mocked or transformed historic payload cannot cross the boundary."""
    # Unit tests may use a synthetic path.  Real Git paths are always checked
    # against the immutable commit that seeded this diagnostic.
    if not path.startswith(f"{HISTORIC_ROOT}/"):
        return True
    document = rtoml.loads(_git("show", f"{HISTORIC_COMMIT}:{path}"))
    matches = tuple(
        declaration
        for declaration in document["revisions"]["2024"]["casillas"]
        if tuple(declaration.get("export_refs", ())) == (export_field_id,)
    )
    return len(matches) == 1 and matches[0] == payload


def _load_target_field_index(current_map: SemanticMap) -> dict[str, RecordDesignIntermediateField]:
    """Load current official descriptions through the pinned design parser."""
    catalogue = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml"))
    design = load_record_design_intermediate(
        bundled_path(),
        catalogue.sources,
        source_ref=str(current_map.source_ref),
        filing_year=2024,
        design_epoch=current_map.design_epoch,
    )
    parsed_identity = (str(design.source.source_ref), design.source.source_sha256)
    map_identity = (str(current_map.source_ref), current_map.source_sha256)
    if parsed_identity != map_identity:
        raise ValueError(
            "semantic map source identity does not exactly match the parsed pinned design: "
            f"map={map_identity!r}, parsed={parsed_identity!r}",
        )
    fields = {intermediate_anchor_key(field): field for sheet in design.sheets for field in sheet.fields}
    result: dict[str, RecordDesignIntermediateField] = {}
    for entry in current_map.entries:
        try:
            result[str(entry.export_field_id)] = fields[semantic_anchor_key(entry.anchor)]
        except KeyError as exc:
            message = f"current semantic map anchor is absent from target design: {entry.export_field_id}"
            raise ValueError(message) from exc
    return result


def _git(*args: str) -> str:
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git executable is required to read pinned historical evidence")
    return subprocess.run(  # noqa: S603 - fixed executable and internally constructed arguments
        [executable, *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout


def _refusal_reason(
    gap: Any,
    entry: SemanticMapEntry,
    payload: dict[str, Any],
    *,
    expected_target_description: str | None = None,
    expected_source_ref: str | None = None,
    expected_source_sha256: str | None = None,
) -> str | None:
    """Refuse evidence mutations before a proposal is rendered."""
    printed = _printed_number(gap.label)
    if expected_target_description is not None and gap.label != expected_target_description:
        return "current target description differs from the pinned official design"
    if printed is None or printed.lstrip("0") != gap.authored_token.lstrip("0"):
        return "current official printed number disagrees with authored token"
    if expected_source_ref is not None and str(gap.source_ref) != expected_source_ref:
        return "current target source reference differs from the semantic map"
    if expected_source_sha256 is not None and gap.source_sha256 != expected_source_sha256:
        return "current target source SHA-256 differs from the semantic map"
    if len(str(gap.source_sha256)) != 64 or any(char not in "0123456789abcdef" for char in gap.source_sha256):
        return "current target source SHA-256 is malformed"
    if tuple(payload.get("export_refs", ())) != (gap.export_field_id,):
        return "historic export identity is not exact"
    if tuple(payload.get("source_refs", ())) != tuple(entry.source_refs) or tuple(entry.source_refs) != (
        gap.source_ref,
    ):
        return "historic and current source proof disagree"
    if tuple(payload.get("legal_refs", ())) != tuple(entry.legal_refs):
        return "historic semantic legal payload disagrees with current reviewed map"
    if str(payload.get("id", "")).lstrip("0") != printed.lstrip("0"):
        return "historic identity disagrees with current official number"
    if str(payload.get("number", "")).lstrip("0") != printed.lstrip("0"):
        return "historic printed number disagrees with current official number"
    if (gap.aeat_type, gap.length, payload.get("data_type")) != ("Num", 17, "money"):
        return "historic semantic type is incompatible with current wire field"
    required_keys = {"section", "semantic_role", "required", "input_kind"}
    if not required_keys.issubset(payload):
        return "historic semantic payload is incomplete"
    description = str(gap.label).casefold()
    semantic_role = str(payload.get("semantic_role", "")).casefold()
    if "otras deducciones relativas a programas de apoyo" in description and "innovacion_tecnologica" in semantic_role:
        return "official target description contradicts historic semantic role"
    if "reserva de nivelaci" in description and (
        "capitalizacion" in semantic_role or "capitalizacion" in " ".join(payload.get("section", ())).casefold()
    ):
        return "official target description contradicts historic semantic role"
    return None


def _printed_number(label: str) -> str | None:
    matches = re.findall(r"\[([0-9]{5})\]", label)
    return matches[0] if len(matches) == 1 else None


if __name__ == "__main__":
    raise SystemExit(main())
