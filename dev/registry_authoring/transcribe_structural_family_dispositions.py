"""One-shot transcriber: ground three structural not_applicable family dispositions.

``build_revision_coverage_manifest``
(:mod:`cadrumo.domain.calculations.registry._schema_family_coverage`) reads an
empty schema family as ``BLOCKED_PENDING_EVIDENCE`` unless the revision
declares a ``family_dispositions`` entry carrying a reason, ``legal_refs`` and
``source_refs``. Three of the nineteen enrolled families carry a discriminator
provable from the loaded registry tree alone, with no per-revision legal
research required:

``casilla_continuidad_evolutions``
    ``CasillaContinuidadEvolutionDefinition`` requires ``from_revision !=
    to_revision`` -- it declares a transition between two revisions of the
    same modelo, and every evolution already declared anywhere in this
    registry is authored on the revision it lands on (its ``to_revision``).
    A revision with no strictly-earlier sibling revision of the same modelo
    cannot be the landing point of a within-modelo transition, so its own
    family is empty by construction, not by omission.

``relations``
    ``validate_informative_class_invariant``
    (:mod:`cadrumo.domain.calculations.registry._validate_revision_rules`)
    hard-refuses a non-empty ``relations`` family on any revision of a
    ``calculation_class == "informative"`` modelo. The declaration states a
    registry-enforced truth.

``projection_endpoints``
    ``FilingProjectionRef`` (:mod:`cadrumo.core`) is a closed discriminated
    union of seven ``m303_*`` members only; ``ProjectionEndpointDeclaration
    .projection_ref`` accepts nothing else, so no modelo but 303 can ever
    populate this family. Every other modelo's repeating detail rows, if it
    has any, are served instead by the independent
    ``ExportRecordDefinition.repeat == "binding_rows"`` mechanism.

``export_layouts`` is NEVER a candidate here: ``_validate_export_exemption.py``
refuses a layout-less revision unconditionally and consults no disposition --
declaring it not_applicable would satisfy this coverage row while leaving the
real gate red. The other fifteen families are untouched by this script; a
prior pass checked several of them (notably ``verification_expectations``) and
found their apparent discriminators falsified by populated counter-examples.

Every declared reason cites the structural fact it rests on. Every
``legal_refs``/``source_refs`` pair is the revision's OWN already-declared
grounding, copied verbatim -- never invented, never empty (both fields are
``Field(min_length=1)`` on ``ModeloRevision``, so the source tuple always has
at least one entry).

Usage::

    python -m dev.registry_authoring.transcribe_structural_family_dispositions [--apply] [--json OUT.json]

Default is a dry run: prints what would be written, writes nothing.
``--apply`` performs the writes, then reloads the whole registry tree through
the same production loader and proves every intended declaration now reads
back as the exact reason/refs this script wrote.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from cadrumo.core import Modelo
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import ModeloDefinition, ModeloRevision, load_registry_tree

REGISTRY_ROOT = bundled_path("registry", "aeat")
MODELOS_ROOT = REGISTRY_ROOT / "modelos"

CASILLA_CONTINUIDAD_FAMILY = "casilla_continuidad_evolutions"
RELATIONS_FAMILY = "relations"
PROJECTION_ENDPOINTS_FAMILY = "projection_endpoints"

#: Fixed write order inside one revision.toml -- stable across runs so a
#: re-run's diff (if any) is never a reordering.
_FAMILY_WRITE_ORDER = (CASILLA_CONTINUIDAD_FAMILY, PROJECTION_ENDPOINTS_FAMILY, RELATIONS_FAMILY)


@dataclass(frozen=True)
class Disposition:
    """One grounded not_applicable declaration this script intends to write."""

    modelo: str
    revision: str
    family: str
    reason: str
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


def is_blocked(revision: ModeloRevision, family: str) -> bool:
    """Mirror the coverage projection's blocked test without a private import.

    A family reads ``BLOCKED_PENDING_EVIDENCE`` in
    ``build_revision_coverage_manifest`` exactly when it is empty AND carries
    no ``family_dispositions`` entry; this is that same test, computed from
    the public revision surface alone so this script never imports the
    private coverage module.
    """
    return not getattr(revision, family) and family not in revision.family_dispositions


def has_no_earlier_sibling(modelo: ModeloDefinition, revision: ModeloRevision) -> bool:
    """Return whether no other revision of ``modelo`` has a strictly-earlier ``valid_from``."""
    return not any(
        other.id != revision.id and other.valid_from < revision.valid_from for other in modelo.revisions.values()
    )


def _reason_continuidad(modelo: ModeloDefinition, revision: ModeloRevision) -> str:
    return (
        "CasillaContinuidadEvolutionDefinition requires from_revision != to_revision -- it "
        "declares a transition between two revisions of the same modelo, and every evolution "
        "already declared anywhere in this registry is authored on the revision it lands on "
        f"(its to_revision). Revision {revision.id!r} of modelo {modelo.id} has no strictly-earlier "
        f"sibling revision of this modelo (valid_from {revision.valid_from.isoformat()} precedes "
        "every other declared revision), so it cannot be the landing point of any within-modelo "
        "continuity transition; the casilla_continuidad_evolutions family is empty by "
        "construction, not by omission."
    )


def _reason_relations(modelo: ModeloDefinition) -> str:
    return (
        f'Modelo {modelo.id} declares calculation_class = "informative". '
        "validate_informative_class_invariant hard-refuses any revision of an informative-class "
        "modelo that declares a non-empty relations family -- cross-model relations feed a "
        "filing-grade calculation this modelo does not perform. The relations family cannot be "
        "populated for this modelo by registry construction."
    )


def _reason_projection_endpoints(modelo: ModeloDefinition) -> str:
    return (
        "FilingProjectionRef (cadrumo.core) is a closed discriminated union of exactly seven "
        "projection_kind members, all prefixed m303_ and used exclusively by modelo 303's "
        "engine-computed IVA facts; ProjectionEndpointDeclaration.projection_ref accepts only "
        f"that union, so no declaration naming modelo {modelo.id}'s own casillas can validate. "
        f"Modelo {modelo.id} is not modelo 303, so the projection_endpoints family cannot be "
        "populated by construction. Any repeating detail rows this modelo's export requires are "
        'addressed instead by the independent ExportRecordDefinition.repeat == "binding_rows" '
        "mechanism, which materializes repeating rows from binding values rather than from a "
        "projection_endpoints declaration."
    )


def compute_dispositions(modelos: tuple[ModeloDefinition, ...]) -> tuple[Disposition, ...]:
    """Re-derive every grounded not_applicable candidate live from the loaded tree."""
    out: list[Disposition] = []
    for modelo in modelos:
        is_informative = modelo.calculation_class == "informative"
        is_m303 = Modelo(modelo.id) == Modelo.M303
        for revision in modelo.revisions.values():
            legal_refs = tuple(str(ref) for ref in revision.legal_refs)
            source_refs = tuple(str(ref) for ref in revision.source_refs)
            if is_blocked(revision, CASILLA_CONTINUIDAD_FAMILY) and has_no_earlier_sibling(modelo, revision):
                out.append(
                    Disposition(
                        modelo=modelo.id,
                        revision=revision.id,
                        family=CASILLA_CONTINUIDAD_FAMILY,
                        reason=_reason_continuidad(modelo, revision),
                        legal_refs=legal_refs,
                        source_refs=source_refs,
                    ),
                )
            if is_blocked(revision, RELATIONS_FAMILY) and is_informative:
                out.append(
                    Disposition(
                        modelo=modelo.id,
                        revision=revision.id,
                        family=RELATIONS_FAMILY,
                        reason=_reason_relations(modelo),
                        legal_refs=legal_refs,
                        source_refs=source_refs,
                    ),
                )
            if is_blocked(revision, PROJECTION_ENDPOINTS_FAMILY) and not is_m303:
                out.append(
                    Disposition(
                        modelo=modelo.id,
                        revision=revision.id,
                        family=PROJECTION_ENDPOINTS_FAMILY,
                        reason=_reason_projection_endpoints(modelo),
                        legal_refs=legal_refs,
                        source_refs=source_refs,
                    ),
                )
    out.sort(key=lambda d: (d.modelo, d.revision, _FAMILY_WRITE_ORDER.index(d.family)))
    return tuple(out)


def _quote(value: str) -> str:
    """Render ``value`` as a TOML basic string literal.

    JSON and TOML basic-string escaping agree on every character these
    values ever carry (quotes, backslashes, and literal UTF-8 prose); using
    ``json.dumps`` avoids hand-rolling a second escaper for the same rules.
    """
    return json.dumps(value, ensure_ascii=False)


def render_block(revision_id: str, disposition: Disposition) -> str:
    """Render one ``[revisions."<rid>".family_dispositions.<family>]`` table."""
    lines = [f'[revisions."{revision_id}".family_dispositions.{disposition.family}]']
    lines.append(f"reason = {_quote(disposition.reason)}")
    lines.append("legal_refs = [")
    lines.extend(f"    {_quote(ref)}," for ref in disposition.legal_refs)
    lines.append("]")
    lines.append("source_refs = [")
    lines.extend(f"    {_quote(ref)}," for ref in disposition.source_refs)
    lines.append("]")
    return "\n".join(lines)


def _revision_toml_path(modelo: str, revision: str) -> Path:
    path = MODELOS_ROOT / modelo / "revisions" / revision / "revision.toml"
    if not path.is_file():
        raise AssertionError(f"{path}: expected a directory-mode revision manifest; none found")
    return path


def _apply_group(path: Path, revision_id: str, dispositions: tuple[Disposition, ...]) -> None:
    """Append every disposition's block to ``path``, matching the corpus's own hand-authored spacing.

    The twelve existing hand-authored ``family_dispositions`` blocks in this
    corpus all follow the same layout: two blank lines separate the last
    manifest scalar from the first block, one blank line separates
    subsequent blocks. Reproduced exactly so a diff against those files reads
    as more of the same pattern, not a new one.
    """
    text = path.read_text(encoding="utf-8").rstrip("\n")
    already_has_family_dispositions = "family_dispositions" in text
    blocks = [render_block(revision_id, disposition) for disposition in dispositions]
    separator = "\n\n" if already_has_family_dispositions else "\n\n\n"
    new_text = text + separator + "\n\n".join(blocks) + "\n"
    path.write_text(new_text, encoding="utf-8", newline="\n")


def apply_dispositions(dispositions: tuple[Disposition, ...]) -> None:
    """Group by (modelo, revision) and write one ``revision.toml`` append per group."""
    grouped: dict[tuple[str, str], list[Disposition]] = {}
    for disposition in dispositions:
        grouped.setdefault((disposition.modelo, disposition.revision), []).append(disposition)
    for (modelo, revision), group in grouped.items():
        ordered = tuple(sorted(group, key=lambda d: _FAMILY_WRITE_ORDER.index(d.family)))
        _apply_group(_revision_toml_path(modelo, revision), revision, ordered)


def prove(dispositions: tuple[Disposition, ...]) -> list[str]:
    """Reload the whole tree and prove every intended declaration reads back exactly."""
    modelos, _catalogues = load_registry_tree(REGISTRY_ROOT)
    by_id = {modelo.id: modelo for modelo in modelos}
    mismatches: list[str] = []
    for disposition in dispositions:
        label = f"{disposition.modelo}/{disposition.revision}/{disposition.family}"
        modelo = by_id.get(disposition.modelo)
        if modelo is None:
            mismatches.append(f"{label}: modelo missing after reload")
            continue
        revision = modelo.revisions.get(disposition.revision)
        if revision is None:
            mismatches.append(f"{label}: revision missing after reload")
            continue
        if getattr(revision, disposition.family):
            mismatches.append(f"{label}: family is populated after reload, not empty")
            continue
        declared = revision.family_dispositions.get(disposition.family)
        if declared is None:
            mismatches.append(f"{label}: no family_dispositions entry after reload")
            continue
        if declared.reason != disposition.reason:
            mismatches.append(f"{label}: reason mismatch")
        if tuple(str(ref) for ref in declared.legal_refs) != disposition.legal_refs:
            mismatches.append(f"{label}: legal_refs mismatch")
        if tuple(str(ref) for ref in declared.source_refs) != disposition.source_refs:
            mismatches.append(f"{label}: source_refs mismatch")
    return mismatches


def main() -> int:
    """Run the transcriber: dry-run by default, ``--apply`` to write and prove."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write and prove (default: dry run, writes nothing)")
    parser.add_argument("--json", type=Path, default=None, help="Write the candidate report as JSON to this path")
    args = parser.parse_args()

    modelos, _catalogues = load_registry_tree(REGISTRY_ROOT)
    dispositions = compute_dispositions(modelos)

    by_family: dict[str, int] = {}
    for disposition in dispositions:
        by_family[disposition.family] = by_family.get(disposition.family, 0) + 1
    revisions_touched = len({(d.modelo, d.revision) for d in dispositions})

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"=== structural family disposition transcription ({mode}) ===")
    print(f"total candidates: {len(dispositions)} across {revisions_touched} revision(s)")
    for family in _FAMILY_WRITE_ORDER:
        print(f"  {family}: {by_family.get(family, 0)}")

    if args.json:
        args.json.write_text(
            json.dumps([asdict(d) for d in dispositions], indent=2, ensure_ascii=False),
            encoding="utf-8",
            newline="\n",
        )
        print(f"Wrote candidate report to {args.json}")

    if not args.apply:
        return 0

    apply_dispositions(dispositions)
    mismatches = prove(dispositions)
    if mismatches:
        print(f"\n{len(mismatches)} disposition(s) FAILED the reload-and-read-back proof:")
        for mismatch in mismatches:
            print(f"  {mismatch}")
        return 1
    print(f"\nAll {len(dispositions)} disposition(s) verified by reload.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
