"""Strip the declaring edition's key out of formula and binding identifiers.

A formula or binding identifier may embed the revision id of the edition that
declares it, as in ``modelo-131-2024-pago-fraccionado-sin-datos-base``. Once an
inherited casilla's formula and binding references resolve against the
successor edition's own declarations by lineage
(:mod:`cadrumo.domain.calculations.registry.identifier_lineage`), an
identifier that still embeds its own edition key is not its own lineage, so
matching it against itself needs a placeholder substitution on every lookup.
This tool removes the embedded key instead, so the identifier becomes its own
lineage and the substitution is never needed.

Scope. Only formula and binding identifiers are renamed, and only where they
embed their *declaring* edition's own revision id as a whole segment -- the
same test :func:`identifier_lineage` uses. An identifier such as
``modelo-232-2016.page_01.144-158.vinculada-1-nif``, declared by revision
``2016-2017``, does not qualify: ``2016`` is not the revision id
``2016-2017``, so the function already treats it as its own lineage and this
tool leaves it untouched.

Rename rule. The new id is the old id with the matched revision-id segment
removed, together with one adjacent identifier separator (preferring the
separator immediately before the match, falling back to the one immediately
after when the match sits at the very start of the identifier). This mirrors
:data:`~cadrumo.domain.calculations.registry.identifier_lineage._IDENTIFIER_SEPARATORS`
without importing the private module constant; a self-test at import time
keeps the two in agreement.

Reference sites. Every exact quoted occurrence of a renamed id anywhere under
the modelo's registry tree and, for the same modelo number, under its
``dev/registry/mappings`` semantic map is rewritten in the same pass:
declarations, casilla ``formula``/``binding``/``alternate_bindings`` fields,
formula-to-formula and formula-to-binding cross-references, hand-authored
``export_layouts`` field bindings, and semantic-map ``binding = "..."``
entries. Generated ``revisions/*/export/`` trees are read-only source for the
measurement pass (to report which trees would need republishing) and are
never rewritten by this tool.

Exclusions. Modelos 185, 222 and 347 (both editions) are never rewritten, nor
is ``dev/registry/mappings/modelo_347``: their generated trees cannot be
republished by this campaign.

Deferred modelos. A modelo whose generated ``export/`` tree copies a renamed
binding id into its field or provenance records (currently only modelo 390,
across its 2022-2025 revisions) is measured and reported, but never rewritten
by ``--apply``: ``registry verify`` refuses a renamed source map sitting
beside a not-yet-regenerated tree (confirmed empirically -- exactly one
"unknown binding" failure per renamed reference), so this modelo's rename and
its export republish must land in the same change. Until the export lane
republishes those trees, this tool leaves modelo 390 untouched.

Modes. ``--measure`` (the default) parses every in-scope declaration, reports
the embedding counts, checks the renamed ids for collisions within a
revision's combined primary-id namespace, and lists the generated export
trees a later republish must touch; it writes nothing. ``--apply`` performs
the rewrite in place after the same safety checks pass.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_MODELOS_ROOT = REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"
MAPPINGS_ROOT = REPO_ROOT / "dev" / "registry" / "mappings"

sys.path.insert(0, str(REPO_ROOT / "src"))

from cadrumo.domain.calculations.registry.identifier_lineage import (  # noqa: E402
    EDITION_PLACEHOLDER,
    identifier_lineage,
)

EXCLUDED_MODELOS: frozenset[str] = frozenset({"185", "222", "347"})

# Measured and reported, but never written by --apply: their generated export
# tree copies a renamed binding id, and registry verify refuses a renamed
# source map beside a not-yet-regenerated tree (see module docstring).
DEFERRED_MODELOS: frozenset[str] = frozenset({"390"})

# Mirrors identifier_lineage._IDENTIFIER_SEPARATORS; kept in sync by
# test_separator_set_matches_identifier_lineage below.
_IDENTIFIER_SEPARATORS = "-._:"

# (family, directory name) pairs that declare an ``id`` primary key sharing
# one combined namespace per revision; mirrors
# cadrumo.domain.calculations.registry.validate_revision_identity._RECORD_ID_KINDS.
_RECORD_ID_DIRS: tuple[tuple[str, str], ...] = (
    ("casilla", "casillas"),
    ("formula", "formulas"),
    ("binding", "bindings"),
    ("relation", "relations"),
    ("parameter", "parameters"),
    ("export layout", "export_layouts"),
    ("extraction profile", "extraction_profiles"),
    ("cross-reference", "live_cross_references"),
    ("workbook parity reference", "workbook_parity_refs"),
    ("verification expectation", "verification_expectations"),
    ("application link", "application_links"),
    ("deadline window", "deadline_windows"),
    ("filing schedule", "filing_schedules"),
    ("construct", "constructs"),
    ("dependency classification", "dependency_classifications"),
)

_RENAMED_FAMILIES: tuple[str, ...] = ("formulas", "bindings")

# Families the loader merges by id across fragment files rather than simply
# concatenating; mirrors _REVISION_SPECIAL_MERGE_FIELDS in
# cadrumo.domain.calculations.registry._loader_revision_fragments.
_MERGE_BY_ID_DIRS: frozenset[str] = frozenset({"export_layouts", "constructs"})


@dataclass(frozen=True)
class DeclaredId:
    modelo: str
    revision_id: str
    family: str
    identifier: str
    source_file: Path


@dataclass
class ModeloMeasurement:
    modelo: str
    formula_embedded: int = 0
    formula_total: int = 0
    binding_embedded: int = 0
    binding_total: int = 0
    renames: dict[str, str] = field(default_factory=dict)
    ambiguous: list[str] = field(default_factory=list)


def iter_modelo_dirs() -> list[Path]:
    return sorted(
        p for p in REGISTRY_MODELOS_ROOT.iterdir() if p.is_dir() and p.name not in EXCLUDED_MODELOS
    )


def iter_revision_dirs(modelo_dir: Path) -> list[Path]:
    revisions_dir = modelo_dir / "revisions"
    if not revisions_dir.is_dir():
        return []
    return sorted(p for p in revisions_dir.iterdir() if p.is_dir())


def _load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def declared_ids_for_dir(modelo: str, revision_dir: Path, revision_id: str, dirname: str) -> list[DeclaredId]:
    target_dir = revision_dir / dirname
    if not target_dir.is_dir():
        return []
    family = dirname
    out: list[DeclaredId] = []
    for toml_path in sorted(target_dir.glob("*.toml")):
        data = _load_toml(toml_path)
        revisions = data.get("revisions")
        if not isinstance(revisions, dict):
            continue
        revision_table = revisions.get(revision_id)
        if not isinstance(revision_table, dict):
            continue
        entries = revision_table.get(dirname)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                out.append(
                    DeclaredId(
                        modelo=modelo,
                        revision_id=revision_id,
                        family=family,
                        identifier=entry["id"],
                        source_file=toml_path,
                    )
                )
    return out


def strip_edition_key(identifier: str, revision_id: str) -> str | None:
    """Return ``identifier`` with its declaring edition's key removed, or ``None`` if it does not embed it.

    Raises :class:`AmbiguousRename` when the revision id occurs as more than
    one whole segment, since the rewrite would then have to choose which
    occurrence to collapse against which adjacent separator.
    """
    lineage = identifier_lineage(identifier, revision_id)
    if lineage == identifier:
        return None
    occurrences = lineage.count(EDITION_PLACEHOLDER)
    if occurrences > 1:
        raise AmbiguousRename(identifier, revision_id, occurrences)
    idx = lineage.index(EDITION_PLACEHOLDER)
    prefix = identifier[:idx]
    suffix = identifier[idx + len(revision_id) :]
    # Sanity: the lineage function replaced exactly this span.
    assert prefix == lineage[:idx]
    assert suffix == lineage[idx + len(EDITION_PLACEHOLDER) :]
    if prefix and prefix[-1] in _IDENTIFIER_SEPARATORS:
        return prefix[:-1] + suffix
    if suffix and suffix[0] in _IDENTIFIER_SEPARATORS:
        return prefix + suffix[1:]
    return prefix + suffix


class AmbiguousRename(Exception):
    def __init__(self, identifier: str, revision_id: str, occurrences: int) -> None:
        super().__init__(
            f"identifier {identifier!r} embeds revision {revision_id!r} as {occurrences} separate segments; "
            "refusing to guess which separator to collapse"
        )
        self.identifier = identifier
        self.revision_id = revision_id


def measure() -> tuple[dict[str, ModeloMeasurement], list[str]]:
    """Parse every in-scope declaration and return per-modelo measurements plus hard failures."""
    measurements: dict[str, ModeloMeasurement] = {}
    failures: list[str] = []

    for modelo_dir in iter_modelo_dirs():
        modelo = modelo_dir.name
        measurement = ModeloMeasurement(modelo=modelo)
        measurements[modelo] = measurement

        # Collect every declared id in every kind, per revision, to check the
        # combined primary-id namespace after renaming.
        ids_by_revision: dict[str, dict[str, list[DeclaredId]]] = defaultdict(lambda: defaultdict(list))

        for revision_dir in iter_revision_dirs(modelo_dir):
            revision_id = revision_dir.name
            for _kind, dirname in _RECORD_ID_DIRS:
                for declared in declared_ids_for_dir(modelo, revision_dir, revision_id, dirname):
                    ids_by_revision[revision_id][dirname].append(declared)

        for revision_id, by_dirname in ids_by_revision.items():
            # Build the post-rename combined namespace for this revision.
            owners_after_rename: dict[str, list[str]] = defaultdict(list)
            local_renames: dict[str, str] = {}

            for _kind, dirname in _RECORD_ID_DIRS:
                declared_entries = by_dirname.get(dirname, ())
                if dirname in _MERGE_BY_ID_DIRS:
                    # These families merge same-id fragments across files into
                    # one declaration before validation; repeats of the same
                    # id here are fragmentation, not a namespace collision.
                    seen_ids: set[str] = set()
                    deduped: list[DeclaredId] = []
                    for declared in declared_entries:
                        if declared.identifier not in seen_ids:
                            seen_ids.add(declared.identifier)
                            deduped.append(declared)
                    declared_entries = deduped
                for declared in declared_entries:
                    if dirname in _RENAMED_FAMILIES:
                        try:
                            new_id = strip_edition_key(declared.identifier, revision_id)
                        except AmbiguousRename as exc:
                            failures.append(f"{modelo} {revision_id}: {exc}")
                            new_id = None
                        if dirname == "formulas":
                            measurement.formula_total += 1
                        else:
                            measurement.binding_total += 1
                        if new_id is not None:
                            if dirname == "formulas":
                                measurement.formula_embedded += 1
                            else:
                                measurement.binding_embedded += 1
                            local_renames[declared.identifier] = new_id
                            measurement.renames[declared.identifier] = new_id
                            owners_after_rename[new_id].append(f"{dirname}:{declared.identifier}")
                        else:
                            owners_after_rename[declared.identifier].append(f"{dirname}:{declared.identifier}")
                    else:
                        owners_after_rename[declared.identifier].append(f"{dirname}:{declared.identifier}")

            for identifier, owners in owners_after_rename.items():
                if len(owners) > 1:
                    failures.append(
                        f"{modelo} {revision_id}: post-rename collision on {identifier!r} shared by {owners}"
                    )

    return measurements, failures


def find_reference_occurrences(modelo: str, old_id: str) -> list[Path]:
    """Return files under the modelo's source tree and matching mapping tree that quote ``old_id``."""
    needle = f'"{old_id}"'
    hits: list[Path] = []
    modelo_dir = REGISTRY_MODELOS_ROOT / modelo
    for path in modelo_dir.rglob("*.toml"):
        # Exclude any path with a literal "export" directory segment (generated tree).
        if any(part == "export" for part in path.relative_to(modelo_dir).parts):
            continue
        text = path.read_text(encoding="utf-8")
        if needle in text:
            hits.append(path)
    mapping_dir = MAPPINGS_ROOT / f"modelo_{modelo}"
    if mapping_dir.is_dir():
        for path in mapping_dir.rglob("*.toml"):
            text = path.read_text(encoding="utf-8")
            if needle in text:
                hits.append(path)
    return hits


def find_generated_export_impact(modelo: str, old_id: str) -> list[Path]:
    """Return generated export-tree files (records, provenance) that quote ``old_id``."""
    modelo_dir = REGISTRY_MODELOS_ROOT / modelo
    needle = old_id
    hits: list[Path] = []
    for export_dir in modelo_dir.glob("revisions/*/export"):
        for path in export_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in {".toml", ".json"}:
                continue
            text = path.read_text(encoding="utf-8")
            if needle in text:
                hits.append(path)
    return hits


def apply_renames(measurements: dict[str, ModeloMeasurement]) -> dict[str, int]:
    """Rewrite every quoted occurrence of each renamed id in place. Returns per-modelo file counts."""
    files_touched: dict[str, int] = {}
    for modelo, measurement in measurements.items():
        if not measurement.renames:
            continue
        if modelo in DEFERRED_MODELOS:
            continue
        touched: set[Path] = set()
        # Sort by descending length so a longer id is replaced before any id
        # that happens to be one of its substrings gets a chance to match.
        ordered = sorted(measurement.renames.items(), key=lambda pair: len(pair[0]), reverse=True)
        modelo_dir = REGISTRY_MODELOS_ROOT / modelo
        mapping_dir = MAPPINGS_ROOT / f"modelo_{modelo}"
        candidate_files: list[Path] = []
        for path in modelo_dir.rglob("*.toml"):
            if any(part == "export" for part in path.relative_to(modelo_dir).parts):
                continue
            candidate_files.append(path)
        if mapping_dir.is_dir():
            candidate_files.extend(mapping_dir.rglob("*.toml"))

        for path in candidate_files:
            original = path.read_text(encoding="utf-8")
            updated = original
            for old_id, new_id in ordered:
                updated = updated.replace(f'"{old_id}"', f'"{new_id}"')
            if updated != original:
                path.write_text(updated, encoding="utf-8")
                touched.add(path)
        files_touched[modelo] = len(touched)
    return files_touched


def _test_separator_set_matches_identifier_lineage() -> None:
    """Self-check: our local separator copy agrees with the module's own boundary test."""
    probe = "modelo-131-2024-total"
    for sep in _IDENTIFIER_SEPARATORS:
        candidate = f"modelo-131{sep}2024{sep}total"
        lineage = identifier_lineage(candidate, "2024")
        assert lineage == f"modelo-131{sep}{EDITION_PLACEHOLDER}{sep}total", (sep, lineage)
    assert identifier_lineage(probe, "2024") != probe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Rewrite files in place; default is measure-only.")
    parser.add_argument("--json", action="store_true", help="Emit the measurement report as JSON.")
    args = parser.parse_args(argv)

    _test_separator_set_matches_identifier_lineage()

    measurements, failures = measure()

    total_formula_embedded = sum(m.formula_embedded for m in measurements.values())
    total_binding_embedded = sum(m.binding_embedded for m in measurements.values())

    report = {
        "modelos_scanned": len(measurements),
        "excluded_modelos": sorted(EXCLUDED_MODELOS),
        "formula_ids_embedding_edition_key_total": total_formula_embedded,
        "binding_ids_embedding_edition_key_total": total_binding_embedded,
        "per_modelo": {
            modelo: {
                "formula_embedded": m.formula_embedded,
                "formula_total": m.formula_total,
                "binding_embedded": m.binding_embedded,
                "binding_total": m.binding_total,
                "renamed_count": len(m.renames),
            }
            for modelo, m in sorted(measurements.items())
            if m.formula_embedded or m.binding_embedded
        },
        "collision_failures": failures,
    }

    generated_tree_impact: dict[str, list[str]] = {}
    for modelo, measurement in measurements.items():
        for old_id in measurement.renames:
            hits = find_generated_export_impact(modelo, old_id)
            if hits:
                for hit in hits:
                    rel = hit.relative_to(REGISTRY_MODELOS_ROOT)
                    revision = rel.parts[2] if len(rel.parts) > 2 else "?"
                    generated_tree_impact.setdefault(modelo, [])
                    label = f"{modelo}/{revision}"
                    if label not in generated_tree_impact[modelo]:
                        generated_tree_impact[modelo].append(label)
    report["generated_export_trees_needing_republish"] = generated_tree_impact

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Modelos scanned: {report['modelos_scanned']} (excluded: {report['excluded_modelos']})")
        print(f"Formula ids embedding edition key: {total_formula_embedded}")
        print(f"Binding ids embedding edition key: {total_binding_embedded}")
        print("Per modelo (only modelos with at least one embedded id):")
        for modelo, counts in report["per_modelo"].items():
            deferred_note = " [DEFERRED: not applied, see module docstring]" if modelo in DEFERRED_MODELOS else ""
            print(
                f"  {modelo}: formulas {counts['formula_embedded']}/{counts['formula_total']}, "
                f"bindings {counts['binding_embedded']}/{counts['binding_total']}, "
                f"renamed {counts['renamed_count']}{deferred_note}"
            )
        if failures:
            print("COLLISION / AMBIGUITY FAILURES:")
            for failure in failures:
                print(f"  {failure}")
        else:
            print("No collisions detected in the combined per-revision primary-id namespace.")
        if generated_tree_impact:
            print("Generated export trees needing republish once source renames land:")
            for modelo, trees in sorted(generated_tree_impact.items()):
                for tree in trees:
                    print(f"  {tree}")
        else:
            print("No generated export tree quotes a renamed id.")

    if failures:
        print("Refusing to apply: unresolved collisions or ambiguous renames reported above.", file=sys.stderr)
        return 1

    if args.apply:
        files_touched = apply_renames(measurements)
        total_files = sum(files_touched.values())
        print(f"Applied renames across {total_files} files in {len(files_touched)} modelos.")
        for modelo, count in sorted(files_touched.items()):
            renamed = len(measurements[modelo].renames)
            print(f"  {modelo}: {renamed} identifiers renamed, {count} files touched")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
