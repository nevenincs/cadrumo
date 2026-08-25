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
    populate this family. That closed-union fact holds unconditionally, but
    the STRONGER claim a not_applicable reason would otherwise imply -- that
    a repeating-row need this modelo actually has is already served by some
    other mechanism -- is not unconditional, so this script declares ONLY
    where that is an OBSERVED, POSITIVE fact of the candidate revision's own
    ``export_layouts``: at least one authored ``ExportRecordDefinition``
    already declares ``repeat == "binding_rows"``.

    An earlier draft of this script also auto-declared whenever every
    authored record left ``repeat`` unset, reading that as "no repeating
    record structure at all". A primary-source check against modelo 347's
    own bundled AEAT record-design corpus
    (``corpus/aeat_official/disenos_registro/modelo_347``) falsified that for
    the concrete case it was about to fire on: the official design declares
    a "REGISTRO DE TIPO 2" (repeating per third party / per property), and
    the revision's authored ``export_layouts`` simply had not modeled that
    record YET -- absence of an authored repeat was proof of an unfinished
    layout, not proof of a flat one. That branch is deliberately NOT
    implemented: a revision whose export_layouts shows no ``binding_rows``
    record is left BLOCKED -- reported as ``held``, never declared.
    Declaring it would assert an unverified prediction about a mechanism
    nobody has authored yet, which is exactly the kind of exception this
    script must not grant.

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

    python -m dev.registry.analysis.transcribe_structural_family_dispositions [--apply] [--json OUT.json]

Default is a dry run: prints what would be written (and what is held back for
lack of evidence), writes nothing. ``--apply`` performs the writes, then
reloads the whole registry tree through the same production loader and proves
every intended declaration now reads back as the exact reason/refs this
script wrote.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from cadrumo.core import Modelo
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
    ModeloRevision,
)
from cadrumo.domain.calculations.registry.loader import load_registry_tree

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


@dataclass(frozen=True)
class HeldCandidate:
    """A blocked, structurally-eligible cell this script deliberately does NOT declare.

    Only ``projection_endpoints`` ever produces these: the closed-union
    discriminator holds for every non-303 modelo, but this script requires
    per-revision OBSERVED evidence of which mechanism actually serves the
    modelo's repeating rows before it will write a declaration, and a
    revision with no ``export_layouts`` yet carries none.
    """

    modelo: str
    revision: str
    family: str
    reason: str


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


def projection_endpoints_evidence(revision: ModeloRevision) -> str | None:
    """Classify the OBSERVED evidence this revision's own export_layouts carry.

    Returns ``"binding_rows"`` when at least one authored
    ``ExportRecordDefinition`` already declares ``repeat == "binding_rows"``
    -- a positive, unambiguous fact: this modelo's repeating rows, if it has
    any, are demonstrably served by that mechanism today. Returns ``None``
    for everything else, INCLUDING a revision whose export_layouts is
    non-empty but declares no ``binding_rows`` record: absence of an
    authored repeat is not proof of a flat record design, only proof that
    nobody has authored the repeating record (yet, or ever) -- see the
    module docstring's modelo-347 counter-example. ``None`` always means
    "hold", never "declare".
    """
    if not revision.export_layouts:
        return None
    repeats = {record.repeat for layout in revision.export_layouts for record in layout.records}
    if "binding_rows" in repeats:
        return "binding_rows"
    return None


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
        "populated by construction. This revision's own export_layouts already demonstrate the "
        "mechanism that serves its repeating rows: at least one authored ExportRecordDefinition "
        'declares repeat == "binding_rows", materializing repeating rows from binding values '
        "rather than from a projection_endpoints declaration."
    )


def _held_reason_projection_endpoints(modelo: ModeloDefinition, revision: ModeloRevision) -> str:
    if not revision.export_layouts:
        observed = f"revision {revision.id!r} declares no export_layouts yet"
    else:
        observed = (
            f"revision {revision.id!r} declares export_layouts, but no authored "
            'ExportRecordDefinition in them declares repeat == "binding_rows" -- an absent '
            "repeat is not proof the modelo's official record design has no repeating detail "
            "rows, only proof that this layout has not (yet) authored one"
        )
    return (
        f"Modelo {modelo.id} is not modelo 303, so FilingProjectionRef's closed m303_* union "
        "still means projection_endpoints itself cannot be populated for this modelo. But "
        f"{observed}, so there is no observed evidence of which mechanism -- if any -- actually "
        "serves this revision's repeating rows. Declaring not_applicable here would assert an "
        "unverified prediction rather than a fact this revision's own declarations establish; "
        "held pending the export_layouts authoring that resolves it."
    )


def compute_dispositions(
    modelos: tuple[ModeloDefinition, ...],
) -> tuple[tuple[Disposition, ...], tuple[HeldCandidate, ...]]:
    """Re-derive every grounded not_applicable candidate, and every held one, live from the tree."""
    out: list[Disposition] = []
    held: list[HeldCandidate] = []
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
                evidence = projection_endpoints_evidence(revision)
                if evidence is None:
                    held.append(
                        HeldCandidate(
                            modelo=modelo.id,
                            revision=revision.id,
                            family=PROJECTION_ENDPOINTS_FAMILY,
                            reason=_held_reason_projection_endpoints(modelo, revision),
                        ),
                    )
                else:
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
    held.sort(key=lambda h: (h.modelo, h.revision))
    return tuple(out), tuple(held)


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
    """Reload the whole tree and prove every intended declaration reads back exactly.

    MUST run in a fresh process, never called a second time in the same
    process as the pre-write load. ``load_registry_tree`` memoizes on
    ``lru_cache(maxsize=32)`` keyed by ``(root, fingerprints)``
    (``_loader.py`` ``_load_registry_tree_cached``), and this worktree's
    backing share has been observed to serve a coarse-grained mtime that
    does not always change within the same process's write-then-reread
    window -- a same-process reload can silently return the PRE-WRITE cached
    tuple, which reads as every disposition missing. ``main()`` never calls
    this directly; it shells out to ``--verify-against`` in a new
    interpreter, whose ``lru_cache`` starts cold.
    """
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


def _dispositions_from_json(payload: object) -> tuple[Disposition, ...]:
    records = payload["dispositions"] if isinstance(payload, dict) else payload
    return tuple(
        Disposition(
            modelo=record["modelo"],
            revision=record["revision"],
            family=record["family"],
            reason=record["reason"],
            legal_refs=tuple(record["legal_refs"]),
            source_refs=tuple(record["source_refs"]),
        )
        for record in records
    )


def _run_verify_against(path: Path) -> int:
    """Load a dispositions JSON file and prove it against a FRESH tree load.

    The entry point ``--apply`` shells out to, in a new interpreter, so
    ``prove`` never shares an ``lru_cache`` with the pre-write load in the
    parent process (see ``prove``'s docstring).
    """
    dispositions = _dispositions_from_json(json.loads(path.read_text(encoding="utf-8")))
    mismatches = prove(dispositions)
    if mismatches:
        print(f"{len(mismatches)} disposition(s) FAILED the reload-and-read-back proof:")
        for mismatch in mismatches:
            print(f"  {mismatch}")
        return 1
    print(f"All {len(dispositions)} disposition(s) verified by a fresh reload.")
    return 0


def main() -> int:
    """Run the transcriber: dry-run by default, ``--apply`` to write and prove."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write and prove (default: dry run, writes nothing)")
    parser.add_argument("--json", type=Path, default=None, help="Write the candidate report as JSON to this path")
    parser.add_argument(
        "--verify-against",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,  # internal: re-invoked as a fresh subprocess by --apply
    )
    args = parser.parse_args()

    if args.verify_against is not None:
        return _run_verify_against(args.verify_against)

    modelos, _catalogues = load_registry_tree(REGISTRY_ROOT)
    dispositions, held = compute_dispositions(modelos)

    by_family: dict[str, int] = {}
    for disposition in dispositions:
        by_family[disposition.family] = by_family.get(disposition.family, 0) + 1
    revisions_touched = len({(d.modelo, d.revision) for d in dispositions})

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"=== structural family disposition transcription ({mode}) ===")
    print(f"total candidates: {len(dispositions)} across {revisions_touched} revision(s)")
    for family in _FAMILY_WRITE_ORDER:
        print(f"  {family}: {by_family.get(family, 0)}")
    print(f"held (blocked, structurally eligible, but no observed evidence yet): {len(held)}")
    for item in held:
        print(f"    HOLD {item.modelo}/{item.revision}/{item.family}")

    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "dispositions": [asdict(d) for d in dispositions],
                    "held": [asdict(h) for h in held],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
            newline="\n",
        )
        print(f"Wrote candidate report to {args.json}")

    if not args.apply:
        return 0

    apply_dispositions(dispositions)

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as handle:
        json.dump([asdict(d) for d in dispositions], handle, ensure_ascii=False)
        verify_payload_path = Path(handle.name)
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, this module re-invoked through sys.executable
            [
                sys.executable,
                "-m",
                "dev.registry_authoring.transcribe_structural_family_dispositions",
                "--verify-against",
                str(verify_payload_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        verify_payload_path.unlink(missing_ok=True)

    print(f"\n--- fresh-process verification ({len(dispositions)} disposition(s)) ---")
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
