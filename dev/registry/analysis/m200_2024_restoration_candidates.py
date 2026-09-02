"""Generate fail-closed M200/2024 casilla restoration candidates.

Current 2024 design/map evidence owns physical identity and export placement.
The pinned historical revision may contribute semantic payload only after an
exact export-field and source-proof match.  This tool never writes registry
files; its TOML is a review artefact.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from typing import Any

import rtoml

from cadrumo.core.resources.bundled_data import bundled_path

from ..pipeline._semantic_map import SemanticMapEntry
from ..pipeline._semantic_map_loader import load_semantic_map
from .m200_semantic_casilla_candidates import M200CasillaDisposition, _load_bundled_candidates

HISTORIC_COMMIT = "17eb283313"
HISTORIC_ROOT = "src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/casillas"
CANONICAL_CASILLA_ROOT = Path("src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/casillas")


@dataclass(frozen=True, slots=True)
class RestorationCandidate:
    """One current-owned declaration candidate with history-supplied meaning."""

    id: str
    number: str
    section: tuple[str, ...]
    semantic_role: str
    data_type: str
    required: bool
    input_kind: str
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    export_refs: tuple[str, ...]
    current_source_sha256: str
    historic_commit: str
    historic_path: str


@dataclass(frozen=True, slots=True)
class RestorationRefusal:
    """One gap that history cannot safely complete."""

    export_field_id: str
    reason: str


def build_bundled_restoration_candidates() -> tuple[tuple[RestorationCandidate, ...], tuple[RestorationRefusal, ...]]:
    """Join current 2024 gaps to the pinned historical payload by export id."""
    classified = _load_bundled_candidates()
    current_map = load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / "2024")
    current_entries = {str(entry.export_field_id): entry for entry in current_map.entries}
    historic = _historic_index()
    accepted: list[RestorationCandidate] = []
    refused: list[RestorationRefusal] = []
    for gap in classified:
        if gap.disposition is not M200CasillaDisposition.REVISION_MISSING_DECLARATION:
            continue
        entry = current_entries[gap.export_field_id]
        matches = historic.get(gap.export_field_id, ())
        if len(matches) != 1:
            refused.append(RestorationRefusal(gap.export_field_id, f"historic export match count is {len(matches)}"))
            continue
        path, payload = matches[0]
        reason = _refusal_reason(gap, entry, payload)
        if reason is not None:
            refused.append(RestorationRefusal(gap.export_field_id, reason))
            continue
        printed = _printed_number(gap.label)
        if printed is None:  # pragma: no cover - proved by _refusal_reason
            raise RuntimeError("accepted restoration lost its current official number")
        accepted.append(
            RestorationCandidate(
                id=printed,
                number=printed,
                section=tuple(payload["section"]),
                semantic_role=payload["semantic_role"],
                data_type=payload["data_type"],
                required=payload["required"],
                input_kind=payload["input_kind"],
                legal_refs=tuple(payload["legal_refs"]),
                source_refs=tuple(payload["source_refs"]),
                export_refs=(gap.export_field_id,),
                current_source_sha256=gap.source_sha256,
                historic_commit=HISTORIC_COMMIT,
                historic_path=path,
            ),
        )
    return (
        tuple(sorted(accepted, key=lambda item: item.export_refs[0])),
        tuple(sorted(refused, key=lambda item: item.export_field_id)),
    )


def render_review_toml(candidates: tuple[RestorationCandidate, ...]) -> str:
    """Render review-only TOML; provenance keys prevent registry ingestion."""
    return rtoml.dumps(
        {"schema_version": 1, "restoration_candidate": [asdict(candidate) for candidate in candidates]},
        pretty=True,
    )


def render_apply_patch(
    candidates: tuple[RestorationCandidate, ...],
    refusals: tuple[RestorationRefusal, ...],
    *,
    workspace_root: Path,
) -> str:
    """Render an all-or-nothing apply_patch document without writing files."""
    if refusals:
        raise ValueError(f"cannot emit registry patch with {len(refusals)} restoration refusals")
    targets = tuple((_canonical_relative_path(candidate), candidate) for candidate in candidates)
    duplicate_paths = tuple(
        sorted(path for path in {item[0] for item in targets} if sum(p == path for p, _ in targets) > 1)
    )
    if duplicate_paths:
        raise ValueError(f"duplicate canonical restoration paths: {duplicate_paths!r}")
    collisions = tuple(path for path, _candidate in targets if (workspace_root / path).exists())
    if collisions:
        raise ValueError(f"canonical restoration targets already exist: {collisions!r}")

    lines = ["*** Begin Patch"]
    for path, candidate in targets:
        lines.append(f"*** Add File: {path.as_posix()}")
        lines.extend(f"+{line}" for line in _render_registry_fragment(candidate).splitlines())
    lines.append("*** End Patch")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Report dry-run candidates and optionally write a review artefact."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write review TOML to this explicit non-registry path")
    parser.add_argument("--emit-patch", action="store_true", help="print an apply_patch document to stdout")
    args = parser.parse_args(argv)
    if args.emit_patch and args.output is not None:
        parser.error("--emit-patch cannot be combined with --output")
    accepted, refused = build_bundled_restoration_candidates()
    if args.emit_patch:
        try:
            sys.stdout.write(render_apply_patch(accepted, refused, workspace_root=bundled_path().parents[2]))
        except ValueError as exc:
            sys.stderr.write(f"refused: {exc}\n")
            return 1
        return 0
    print(f"accepted={len(accepted)}")
    print(f"refused={len(refused)}")
    for item in refused[:10]:
        print(f"refusal[{item.export_field_id}]={item.reason}")
    if args.output is not None:
        args.output.write_text(render_review_toml(accepted), encoding="utf-8", newline="\n")
        print(f"wrote={args.output}")
    return 1 if refused else 0


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


def _refusal_reason(gap: Any, entry: SemanticMapEntry, payload: dict[str, Any]) -> str | None:
    printed = _printed_number(gap.label)
    if printed is None or printed.lstrip("0") != gap.authored_token.lstrip("0"):
        return "current official printed number disagrees with authored token"
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
    return None


def _printed_number(label: str) -> str | None:
    matches = re.findall(r"\[([0-9]{5})\]", label)
    return matches[0] if len(matches) == 1 else None


def _canonical_relative_path(candidate: RestorationCandidate) -> Path:
    if not re.fullmatch(r"[0-9]{5}", candidate.id):
        raise ValueError(f"restoration candidate has non-canonical unqualified id {candidate.id!r}")
    return CANONICAL_CASILLA_ROOT / f"c{candidate.id}.toml"


def _render_registry_fragment(candidate: RestorationCandidate) -> str:
    """Render only registry-schema fields; review provenance stays outside."""
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    array = lambda values: "[" + ", ".join(quote(value) for value in values) + "]"
    return "\n".join(
        (
            "# Generated from the current M200/2024 semantic map and official aeat-dr-200-2024 design.",
            f"# Semantic payload reviewed from pinned repository commit {HISTORIC_COMMIT}.",
            "",
            '[[revisions."2024".casillas]]',
            f"id = {quote(candidate.id)}",
            f"number = {quote(candidate.number)}",
            f"section = {array(candidate.section)}",
            f"semantic_role = {quote(candidate.semantic_role)}",
            f"data_type = {quote(candidate.data_type)}",
            f"required = {str(candidate.required).lower()}",
            f"input_kind = {quote(candidate.input_kind)}",
            f"legal_refs = {array(candidate.legal_refs)}",
            f"source_refs = {array(candidate.source_refs)}",
            f"export_refs = {array(candidate.export_refs)}",
            "",
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
