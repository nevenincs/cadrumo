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

Second rule: the modelo-anchored edition-year collapse. The rule above keys
on the *whole revision id*, so an identifier such as
``modelo-232-2016.page_01.144-158.vinculada-1-nif``, declared by revision
``2016-2017``, is out of its reach: ``2016`` is not ``2016-2017``. The
edition-year collapse closes exactly that gap, and nothing wider. An identifier
qualifies when all three hold:

* it opens with ``modelo-<N>`` where ``<N>`` is the modelo's OWN number,
  followed by an identifier separator. The modelo number is the anchor, and it
  is why a legal-norm year can never fire: ``ley-35-2006`` and
  ``rd-1624-1992`` carry a year in the same shape but do not open with this
  modelo's ``modelo-<N>`` prefix;
* the segment immediately after that separator is a whole, separator-bounded
  segment; and
* that segment is a year one of this modelo's own editions keys on.

``modelo-<N><sep><year><rest>`` then collapses to ``modelo-<N><rest>``, so
``modelo-232-2016.page_01.x`` becomes ``modelo-232.page_01.x`` and
``modelo-232-2016-portal`` becomes ``modelo-232-portal``.

The year set. An edition keys on its ``valid_from`` year and on every filing
year its ``period_selector`` admits, both read from its ``revision.toml``
manifest rather than from its directory name -- the name is a label and the two
disagree in the corpus: modelo 720's ``2013-y-siguientes`` declares
``valid_from = 2012``, and its identifiers spell ``modelo-720-2013.*``.
Admission is decided by :meth:`PeriodSelector.includes_year` itself rather than
by a copy of it. An open-ended selector admits unboundedly many years, so it is
enumerated to a horizon that is a declaration rather than the clock: the last
filing year the registry's ``supported_filing_years`` promise names, widened by
any later bound this modelo's own editions declare. A rule whose result changes
on New Year's Eve would not be auditable.

Identity gate. A qualifying identifier is collapsed only when the collapse
loses nothing. Every declaration that would map to one collapsed identifier --
the year-keyed ones and any edition already declaring the bare collapsed id --
is compared as raw TOML row text with its ``id`` line normalised to a sentinel
and its edition's shared source references lifted out, and the collapse is
written only when every one of those bodies is byte-identical. A refusal is a
finding, not a failure: it says the two editions state genuinely different
things under a name the collapse would have made one.

Reference lifting. Two editions routinely state the same row and ground it in
their own diseno -- ``source_refs = ["aeat-dr-232-2016"]`` against
``["aeat-dr-232-2018"]`` -- which is restatement of a fact the edition already
carries, not a difference between the rows. So the comparison lifts each side's
edition default first, exactly as the casilla family lifts
``casilla_source_refs``: a member whose references EQUAL the default states
none, and a member that opens with the default keeps only the tail, as
``additional_source_refs``. The default is the edition's manifest
``binding_source_refs`` / ``formula_source_refs`` where one is declared.

Where none is declared yet, the default is bootstrapped from the corpus, under
a deliberately narrow test: the reference must be stated by EVERY row of that
edition's family AND by NO row of any sibling edition's, exactly one such
reference must survive, and the modelo must have more than one edition
declaring the family -- with a single edition there is no counterpart to prove
and every shared reference is edition-scoped vacuously. ``--apply`` writes the
bootstrapped default onto the edition's manifest and drops it from the members
in the same run, because the two are one change: a member may only stop stating
a reference the manifest now states. A manifest already declaring a different
default is refused rather than overwritten.

The manifest write is gated on the typed model: ``--apply`` refuses while
:class:`ModeloRevision` declares no ``binding_source_refs`` /
``formula_source_refs`` field, since writing a key the loader refuses would
produce an unloadable manifest. The gate is read off the live model, so it
opens by itself when the field lands.

A collapsed identifier is also refused when it would collide with another
declaration in the same revision's combined primary-id namespace.

Generated export trees. ``--apply`` refuses outright when a published
``revisions/*/export/`` tree quotes an id the collapse renames. Such a tree is
generator-owned and must never be hand-edited, and the deadlock it creates is
total: the registry authority will not compile while a published tree names a
binding the source no longer declares, and the generator cannot republish the
tree without a compiling authority. So the rename and the republish have to
land in one change, planned by the export lane, and
``--export-republish-acknowledged`` is the caller's statement that they do. The
condition is read from the trees themselves rather than from a hand-kept
roster: the ``DEFERRED_MODELOS`` list below was such a roster, it named only
modelo 390, and modelos 232 and 353 carried the identical hazard without
appearing on it. Quote style is not part of the test, because generated
fragments spell a binding reference in single quotes where authored fragments
use double.

Scope. The collapse runs only for modelos named explicitly with ``--modelo``,
because it is an auditable per-modelo operation whose refusal list a reader is
expected to read before applying.

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
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_MODELOS_ROOT = REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"
MAPPINGS_ROOT = REPO_ROOT / "dev" / "registry" / "mappings"

sys.path.insert(0, str(REPO_ROOT / "src"))

from cadrumo.domain.calculations.registry.identifier_lineage import (  # noqa: E402
    EDITION_PLACEHOLDER,
    identifier_lineage,
)
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector  # noqa: E402

from .analysis.edition_delta_status import supported_filing_years  # noqa: E402

EXCLUDED_MODELOS: frozenset[str] = frozenset({"185", "222", "347"})

# Measured and reported, but never written by --apply: their generated export
# tree copies a renamed binding id, and registry verify refuses a renamed
# source map beside a not-yet-regenerated tree (see module docstring).
DEFERRED_MODELOS: frozenset[str] = frozenset({"390"})

# Mirrors identifier_lineage._IDENTIFIER_SEPARATORS; kept in sync by
# _check_separator_set_matches_identifier_lineage below.
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
# dev.registry.compiler._loader_revision_fragments.
_MERGE_BY_ID_DIRS: frozenset[str] = frozenset({"export_layouts", "constructs"})


@dataclass(frozen=True)
class DeclaredId:
    """One declared ``id`` found under a revision's family directory (e.g. ``formulas/``)."""

    modelo: str
    revision_id: str
    family: str
    identifier: str
    source_file: Path


@dataclass
class ModeloMeasurement:
    """Per-modelo embedding counts and the resolved old-id to new-id rename map."""

    modelo: str
    formula_embedded: int = 0
    formula_total: int = 0
    binding_embedded: int = 0
    binding_total: int = 0
    renames: dict[str, str] = field(default_factory=dict)
    ambiguous: list[str] = field(default_factory=list)


def iter_modelo_dirs() -> list[Path]:
    """Return every in-scope modelo directory, excluding :data:`EXCLUDED_MODELOS`."""
    return sorted(p for p in REGISTRY_MODELOS_ROOT.iterdir() if p.is_dir() and p.name not in EXCLUDED_MODELOS)


def iter_revision_dirs(modelo_dir: Path) -> list[Path]:
    """Return a modelo's revision directories, sorted by directory name."""
    revisions_dir = modelo_dir / "revisions"
    if not revisions_dir.is_dir():
        return []
    return sorted(p for p in revisions_dir.iterdir() if p.is_dir())


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def declared_ids_for_dir(modelo: str, revision_dir: Path, revision_id: str, dirname: str) -> list[DeclaredId]:
    """Return every declared ``id`` for one revision's ``dirname`` family, across its fragment files."""
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

    Raises :class:`AmbiguousRenameError` when the revision id occurs as more than
    one whole segment, since the rewrite would then have to choose which
    occurrence to collapse against which adjacent separator.
    """
    lineage = identifier_lineage(identifier, revision_id)
    if lineage == identifier:
        return None
    occurrences = lineage.count(EDITION_PLACEHOLDER)
    if occurrences > 1:
        raise AmbiguousRenameError(identifier, revision_id, occurrences)
    idx = lineage.index(EDITION_PLACEHOLDER)
    prefix = identifier[:idx]
    suffix = identifier[idx + len(revision_id) :]
    # Sanity: the lineage function must have replaced exactly this span.
    if prefix != lineage[:idx] or suffix != lineage[idx + len(EDITION_PLACEHOLDER) :]:
        raise RenameSpanMismatchError(identifier, revision_id, lineage)
    if prefix and prefix[-1] in _IDENTIFIER_SEPARATORS:
        return prefix[:-1] + suffix
    if suffix and suffix[0] in _IDENTIFIER_SEPARATORS:
        return prefix + suffix[1:]
    return prefix + suffix


class AmbiguousRenameError(Exception):
    """The revision id occurs as more than one whole segment in the identifier."""

    def __init__(self, identifier: str, revision_id: str, occurrences: int) -> None:
        """Record the identifier, the declaring revision id, and how many segments matched."""
        super().__init__(
            f"identifier {identifier!r} embeds revision {revision_id!r} as {occurrences} separate segments; "
            "refusing to guess which separator to collapse"
        )
        self.identifier = identifier
        self.revision_id = revision_id


class RenameSpanMismatchError(Exception):
    """:func:`identifier_lineage` replaced a span that does not match the identifier/lineage prefix and suffix."""

    def __init__(self, identifier: str, revision_id: str, lineage: str) -> None:
        """Record the identifier, the declaring revision id, and the lineage it produced."""
        super().__init__(
            f"identifier {identifier!r} and its lineage {lineage!r} against revision {revision_id!r} disagree "
            "outside the placeholder span; identifier_lineage's boundary rule may have changed"
        )


def measure(modelos: tuple[str, ...] = ()) -> tuple[dict[str, ModeloMeasurement], list[str]]:
    """Parse every in-scope declaration and return per-modelo measurements plus hard failures.

    ``modelos`` narrows the scan to the named modelos; empty means the whole
    in-scope corpus.
    """
    measurements: dict[str, ModeloMeasurement] = {}
    failures: list[str] = []

    for modelo_dir in iter_modelo_dirs():
        modelo = modelo_dir.name
        if modelos and modelo not in modelos:
            continue
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
                        except AmbiguousRenameError as exc:
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


def _check_separator_set_matches_identifier_lineage() -> None:
    """Self-check: our local separator copy agrees with the module's own boundary test."""
    probe = "modelo-131-2024-total"
    for sep in _IDENTIFIER_SEPARATORS:
        candidate = f"modelo-131{sep}2024{sep}total"
        lineage = identifier_lineage(candidate, "2024")
        expected = f"modelo-131{sep}{EDITION_PLACEHOLDER}{sep}total"
        if lineage != expected:
            raise RenameSpanMismatchError(candidate, "2024", lineage)
    if identifier_lineage(probe, "2024") == probe:
        raise RenameSpanMismatchError(probe, "2024", probe)


# ---------------------------------------------------------------------------
# The modelo-anchored edition-year collapse (see the module docstring).
# ---------------------------------------------------------------------------

_MANIFEST_NAME = "revision.toml"

#: Replaces the ``id`` line before two declaration bodies are compared, so the
#: comparison asks "is everything else identical" rather than "do these two
#: rows carry the same name", which they never do before the collapse.
_ID_SENTINEL = 'id = "<collapsed>"'

#: The manifest key each renamed family lifts its shared ``source_refs`` into,
#: mirroring ``casilla_source_refs`` for the casilla family.
_FAMILY_DEFAULT_KEY: dict[str, str] = {"bindings": "binding_source_refs", "formulas": "formula_source_refs"}

_ARRAY_TABLE_HEADER = re.compile(
    r"""^\[\[revisions\.(?:"(?P<dq>[^"]*)"|'(?P<sq>[^']*)'|(?P<bare>[^.\]]+))\.(?P<family>[A-Za-z_]+)\]\]\s*$"""
)
_ID_LINE = re.compile(r"""^\s*id\s*=\s*"(?P<value>[^"]*)"\s*$""")
_SOURCE_REFS_LINE = re.compile(r"""^\s*source_refs\s*=\s*\[(?P<items>[^\]]*)\]\s*$""")
_QUOTED_ITEM = re.compile(r'"([^"]*)"')


def _quoted_items(text: str) -> tuple[str, ...]:
    """Return the double-quoted items of a one-line TOML array."""
    return tuple(str(item) for item in _QUOTED_ITEM.findall(text))


class GeneratedExportTreeStaleError(Exception):
    """The collapse would strand a generated export tree that quotes a renamed id."""

    def __init__(self, modelo: str, revisions: tuple[str, ...]) -> None:
        """Record the modelo and the revisions whose generated trees quote a renamed id."""
        super().__init__(
            f"modelo {modelo} ships generated export trees that quote ids this collapse renames "
            f"({', '.join(revisions)}). Those trees are generator-owned, cannot be hand-edited, and the "
            "registry authority refuses to compile while a published tree names a binding the source no "
            "longer declares -- which also blocks the generator, since publishing a tree needs a compiling "
            "authority. So the rename and the republish must land together, planned by the export lane. "
            "Pass --export-republish-acknowledged only as part of a change that republishes them."
        )
        self.modelo = modelo
        self.revisions = revisions


class FamilyDefaultUnsupportedError(Exception):
    """Lifting was planned, but the typed revision model carries no family-default field yet."""

    def __init__(self, missing: tuple[str, ...]) -> None:
        """Record the manifest keys the shipped :class:`ModeloRevision` does not declare."""
        super().__init__(
            f"the collapse plan lifts shared source references into {', '.join(missing)}, which "
            "ModeloRevision does not declare; writing them now would produce a manifest the loader "
            "refuses. Land the schema field first, then re-run --apply."
        )
        self.missing = missing


def _missing_family_default_fields() -> tuple[str, ...]:
    """Return the family-default manifest keys the shipped revision model does NOT declare.

    Read off the live model rather than asserted, so this gate opens by itself
    the moment the typed field lands and can never claim support the loader
    does not have.
    """
    from cadrumo.domain.calculations.registry.schema import ModeloRevision

    declared = set(ModeloRevision.model_fields)
    return tuple(sorted(key for key in _FAMILY_DEFAULT_KEY.values() if key not in declared))


@dataclass(frozen=True)
class Declaration:
    """One declared row of a renamed family, with the raw TOML text that states it."""

    revision_id: str
    family: str
    identifier: str
    lines: tuple[str, ...]
    source_file: Path

    @property
    def source_refs(self) -> tuple[str, ...] | None:
        """The row's stated ``source_refs``, or ``None`` when it states none on one line.

        A multi-line array is deliberately reported as absent rather than
        parsed: lifting rewrites the statement textually, and a spelling this
        function cannot reproduce exactly must not be rewritten at all.
        """
        for line in self.lines:
            match = _SOURCE_REFS_LINE.match(line)
            if match is not None:
                return _quoted_items(match.group("items"))
        return None

    def lifted(self, default: tuple[str, ...]) -> str:
        """Return the body with ``default`` lifted out of its ``source_refs``.

        Mirrors the casilla rule exactly: a row whose references EQUAL the
        edition default states none; a row that opens with the default keeps
        only the tail, as ``additional_source_refs``; anything else is
        irreducible and is kept whole.
        """
        if not default:
            return "\n".join(self.lines)
        rendered: list[str] = []
        for line in self.lines:
            match = _SOURCE_REFS_LINE.match(line)
            if match is None:
                rendered.append(line)
                continue
            items = _quoted_items(match.group("items"))
            if items == default:
                continue
            if items[: len(default)] == default:
                tail = ", ".join(f'"{item}"' for item in items[len(default) :])
                rendered.append(f"additional_source_refs = [{tail}]")
                continue
            rendered.append(line)
        return "\n".join(rendered)


@dataclass
class CollapsePlan:
    """One modelo's edition-year collapse: what it would rewrite and what it refuses."""

    modelo: str
    valid_from_years: dict[str, str] = field(default_factory=dict)
    year_set: tuple[str, ...] = ()
    renames: dict[str, str] = field(default_factory=dict)
    refusals: list[str] = field(default_factory=list)
    #: ``(family, revision_id) -> refs`` this run would write into a manifest.
    manifest_writes: dict[tuple[str, str], tuple[str, ...]] = field(default_factory=dict)
    #: Every effective family default, declared or bootstrapped, used for lifting.
    family_defaults: dict[tuple[str, str], tuple[str, ...]] = field(default_factory=dict)
    #: Revisions whose generated export tree quotes an id this plan renames.
    stranded_export_trees: tuple[str, ...] = ()

    @property
    def collapsed_count(self) -> int:
        """How many declared identifiers the plan would rewrite."""
        return len(self.renames)


def _revision_table(revision_dir: Path) -> dict[str, Any]:
    """Return one edition's ``revision.toml`` table, or an empty mapping."""
    manifest = revision_dir / _MANIFEST_NAME
    if not manifest.is_file():
        return {}
    table = _load_toml(manifest).get("revisions", {}).get(revision_dir.name)
    return table if isinstance(table, dict) else {}


def valid_from_years(modelo_dir: Path) -> dict[str, str]:
    """Return each edition's ``valid_from`` year, read from its ``revision.toml`` manifest.

    The manifest is the declaration; the directory name is a label that may or
    may not agree with it -- modelo 720's ``2013-y-siguientes`` declares
    ``valid_from = 2012-01-01`` -- so the year is never taken from the name.
    """
    years: dict[str, str] = {}
    for revision_dir in iter_revision_dirs(modelo_dir):
        valid_from = _revision_table(revision_dir).get("valid_from")
        if isinstance(valid_from, date):
            years[revision_dir.name] = f"{valid_from.year:04d}"
        elif isinstance(valid_from, str) and len(valid_from) >= 4 and valid_from[:4].isdigit():
            years[revision_dir.name] = valid_from[:4]
    return years


def _selector(revision_dir: Path) -> PeriodSelector | None:
    """Return an edition's typed ``period_selector``, built through the domain model itself.

    The registry models validate in strict mode, where a TOML array is a
    ``list`` and a declared ``tuple`` field refuses it, so the sequences are
    retyped before validation. ``None`` means the edition declares no selector,
    or declares one this tool could not type -- a state the caller reports
    rather than absorbs, because a silently unread selector would quietly
    narrow the year set.
    """
    declared = _revision_table(revision_dir).get("period_selector")
    if not isinstance(declared, dict):
        return None
    retyped = {key: tuple(value) if isinstance(value, list) else value for key, value in declared.items()}
    try:
        return PeriodSelector.model_validate(retyped)
    except ValueError:
        return None


def unreadable_selectors(modelo_dir: Path) -> tuple[str, ...]:
    """Return the editions that declare a ``period_selector`` this tool could not type."""
    return tuple(
        revision_dir.name
        for revision_dir in iter_revision_dirs(modelo_dir)
        if isinstance(_revision_table(revision_dir).get("period_selector"), dict) and _selector(revision_dir) is None
    )


def _year_horizon(modelos_root: Path, modelo_dir: Path) -> int | None:
    """Return the last filing year an open-ended selector is enumerated to.

    An open-ended ``period_selector`` (``year_from`` with no ``year_to``) admits
    unboundedly many years, so the set has to stop somewhere, and the stopping
    point must be a DECLARATION rather than the clock -- a rule whose result
    changes on New Year's Eve is not auditable. The horizon is the latest year
    the registry itself names: the product's promised filing years, widened by
    any bound this modelo's own editions declare beyond them.
    """
    candidates: list[int] = list(supported_filing_years(modelos_root.parent))
    for revision_dir in iter_revision_dirs(modelo_dir):
        selector = _selector(revision_dir)
        if selector is not None:
            candidates.extend(selector.years)
            candidates.extend(bound for bound in (selector.year_from, selector.year_to) if bound is not None)
        valid_from = _revision_table(revision_dir).get("valid_from")
        if isinstance(valid_from, date):
            candidates.append(valid_from.year)
    return max(candidates) if candidates else None


def edition_year_set(modelo_dir: Path, modelos_root: Path = REGISTRY_MODELOS_ROOT) -> frozenset[str]:
    """Return every year this modelo's own editions key on.

    Two sources, both declared: each edition's ``valid_from`` year, and every
    filing year its ``period_selector`` admits, decided by the domain model's
    own :meth:`PeriodSelector.includes_year` rather than by a copy of it. The
    second source is what reaches an identifier keyed on a year inside the
    edition's span rather than on its first -- modelo 720 spells
    ``modelo-720-2013.*`` under an edition whose ``valid_from`` is 2012.
    """
    years: set[str] = set(valid_from_years(modelo_dir).values())
    horizon = _year_horizon(modelos_root, modelo_dir)
    for revision_dir in iter_revision_dirs(modelo_dir):
        selector = _selector(revision_dir)
        if selector is None:
            continue
        if selector.years:
            years.update(f"{year:04d}" for year in selector.years)
            continue
        if selector.year_from is None:
            continue
        last = selector.year_to if selector.year_to is not None else horizon
        if last is None:
            continue
        years.update(f"{year:04d}" for year in range(selector.year_from, last + 1) if selector.includes_year(year))
    return frozenset(years)


def collapse_edition_year(identifier: str, modelo: str, years: frozenset[str]) -> str | None:
    """Return ``identifier`` with a leading ``modelo-<N><sep><year>`` year segment removed, or ``None``.

    Anchored on this modelo's own number, so a year sitting anywhere else in the
    identifier -- a legal norm's year, a referenced casilla's year -- cannot
    fire.
    """
    prefix = f"modelo-{modelo}"
    if not identifier.startswith(prefix):
        return None
    rest = identifier[len(prefix) :]
    if not rest or rest[0] not in _IDENTIFIER_SEPARATORS:
        return None
    tail = rest[1:]
    end = len(tail)
    for position, character in enumerate(tail):
        if character in _IDENTIFIER_SEPARATORS:
            end = position
            break
    if tail[:end] not in years:
        return None
    return prefix + tail[end:]


def declarations_in_file(path: Path, family: str) -> list[Declaration]:
    """Return every row of ``family`` declared in one fragment, with its raw body text.

    Read as text rather than through :mod:`tomllib` because the identity gate
    compares what the two editions WROTE. A parsed-and-reserialised comparison
    would silently equate two rows that differ in comment, key order or inline
    table spelling, and those differences are exactly the kind a reviewer of a
    merge wants to see.
    """
    found: list[Declaration] = []
    state: dict[str, str | None] = {"revision": None, "family": None}
    lines: list[str] = []

    def flush() -> None:
        revision = state["revision"]
        if revision is None or state["family"] != family:
            return
        identifier: str | None = None
        normalised: list[str] = []
        for line in lines:
            match = _ID_LINE.match(line)
            if match is not None and identifier is None:
                identifier = str(match.group("value"))
                normalised.append(_ID_SENTINEL)
                continue
            normalised.append(line)
        if identifier is None:
            return
        # A trailing run of blank and comment lines introduces whatever comes
        # NEXT in the fragment -- a section banner above the following rows --
        # rather than stating anything about this row, and one edition carrying
        # such a banner would otherwise make two identical rows compare
        # different. Dropping it narrows the comparison to the row's own
        # statement; no body is ever rewritten from this text.
        while normalised and (not normalised[-1].strip() or normalised[-1].lstrip().startswith("#")):
            normalised.pop()
        found.append(
            Declaration(
                revision_id=revision,
                family=family,
                identifier=identifier,
                lines=tuple(normalised),
                source_file=path,
            )
        )

    for line in path.read_text(encoding="utf-8").splitlines():
        header = _ARRAY_TABLE_HEADER.match(line)
        if header is not None:
            flush()
            state["revision"] = header.group("dq") or header.group("sq") or header.group("bare")
            state["family"] = header.group("family")
            lines = []
            continue
        if state["revision"] is not None:
            lines.append(line)
    flush()
    return found


def modelo_declarations(modelo_dir: Path) -> list[Declaration]:
    """Return every formula and binding row this modelo's editions declare."""
    found: list[Declaration] = []
    for revision_dir in iter_revision_dirs(modelo_dir):
        for family in _RENAMED_FAMILIES:
            family_dir = revision_dir / family
            if not family_dir.is_dir():
                continue
            for toml_path in sorted(family_dir.glob("*.toml")):
                found.extend(
                    declaration
                    for declaration in declarations_in_file(toml_path, family)
                    if declaration.revision_id == revision_dir.name
                )
    return found


def declared_family_default(modelo_dir: Path, revision_id: str, family: str) -> tuple[str, ...] | None:
    """Return the family's shared ``source_refs`` this edition's manifest already declares."""
    declared = _revision_table(modelo_dir / "revisions" / revision_id).get(_FAMILY_DEFAULT_KEY[family])
    if isinstance(declared, list) and all(isinstance(item, str) for item in declared):
        return tuple(str(item) for item in declared)
    return None


def bootstrap_family_default(declarations: Sequence[Declaration], revision_id: str) -> tuple[str, ...] | None:
    """Return the edition-scoped reference an edition's rows all restate, or ``None``.

    Edition-scoped means both halves, and the second is what keeps this honest:
    the reference is stated by EVERY row of this edition's family, and by NO row
    of any sibling edition's. A reference satisfying only the first half is
    shared vocabulary rather than an edition's own design citation, and lifting
    it would assert an edition boundary the corpus never drew. Exactly one such
    reference must survive; two would make the lift ambiguous.
    """
    mine = [declaration for declaration in declarations if declaration.revision_id == revision_id]
    if not mine:
        return None
    refs_by_row = [declaration.source_refs for declaration in mine]
    if any(refs is None for refs in refs_by_row):
        return None
    common = set(refs_by_row[0] or ())
    for refs in refs_by_row[1:]:
        common &= set(refs or ())
    elsewhere = {
        ref
        for declaration in declarations
        if declaration.revision_id != revision_id
        for ref in (declaration.source_refs or ())
    }
    candidates = sorted(common - elsewhere)
    return (candidates[0],) if len(candidates) == 1 else None


def _namespace_by_revision(modelo: str, modelo_dir: Path) -> dict[str, dict[str, str]]:
    """Return each revision's combined primary-id namespace as ``id -> owning family``."""
    namespace: dict[str, dict[str, str]] = {}
    for revision_dir in iter_revision_dirs(modelo_dir):
        revision_id = revision_dir.name
        owners: dict[str, str] = {}
        for _kind, dirname in _RECORD_ID_DIRS:
            for declared in declared_ids_for_dir(modelo, revision_dir, revision_id, dirname):
                owners.setdefault(declared.identifier, dirname)
        namespace[revision_id] = owners
    return namespace


def _resolve_family_defaults(
    modelo_dir: Path,
    declarations: Sequence[Declaration],
    plan: CollapsePlan,
) -> tuple[dict[tuple[str, str], tuple[str, ...]], dict[tuple[str, str], tuple[str, ...]], set[str]]:
    """Resolve each ``(family, edition)`` default; return effective, bootstrapped, and conflicted sets."""
    effective: dict[tuple[str, str], tuple[str, ...]] = {}
    bootstrapped: dict[tuple[str, str], tuple[str, ...]] = {}
    conflicted: set[str] = set()
    for family in _RENAMED_FAMILIES:
        family_rows = [declaration for declaration in declarations if declaration.family == family]
        revisions = sorted({declaration.revision_id for declaration in family_rows})
        for revision_id in revisions:
            declared = declared_family_default(modelo_dir, revision_id, family)
            candidate = bootstrap_family_default(family_rows, revision_id)
            if declared is not None:
                effective[(family, revision_id)] = declared
                if candidate is not None and candidate != declared:
                    plan.refusals.append(
                        f"{plan.modelo} {family} {revision_id}: manifest declares "
                        f"{_FAMILY_DEFAULT_KEY[family]}={list(declared)} but its rows restate "
                        f"{list(candidate)}; refusing to lift against a conflicting default"
                    )
                    conflicted.add(revision_id)
                continue
            # A bootstrapped lift is inferred rather than declared, so it is
            # taken only where it earns its risk: proving two editions state the
            # same thing. With one edition there is no counterpart to compare
            # against, every shared reference is "edition-scoped" vacuously, and
            # lifting would rewrite the corpus for no identity gain.
            if candidate is not None and len(revisions) > 1:
                effective[(family, revision_id)] = candidate
                bootstrapped[(family, revision_id)] = candidate
    return effective, bootstrapped, conflicted


def plan_edition_year_collapse(modelo: str, modelos_root: Path = REGISTRY_MODELOS_ROOT) -> CollapsePlan:
    """Decide, for one modelo, which year-keyed identifiers collapse and which are refused."""
    modelo_dir = modelos_root / modelo
    plan = CollapsePlan(modelo=modelo)
    if not modelo_dir.is_dir():
        plan.refusals.append(f"{modelo}: no such modelo directory under {modelos_root}")
        return plan
    plan.valid_from_years = valid_from_years(modelo_dir)
    for revision_id in unreadable_selectors(modelo_dir):
        plan.refusals.append(
            f"{modelo} {revision_id}: period_selector could not be typed, so its filing years are "
            "not in the year set; the collapse may be narrower than the editions declare"
        )
    years = edition_year_set(modelo_dir, modelos_root)
    plan.year_set = tuple(sorted(years))
    if not years:
        plan.refusals.append(f"{modelo}: no edition declares a year; nothing anchors a collapse")
        return plan

    declarations = modelo_declarations(modelo_dir)
    effective, bootstrapped, conflicted = _resolve_family_defaults(modelo_dir, declarations, plan)
    plan.family_defaults = dict(effective)

    groups: dict[tuple[str, str], list[Declaration]] = defaultdict(list)
    keyed: dict[tuple[str, str], list[Declaration]] = defaultdict(list)
    for declaration in declarations:
        collapsed = collapse_edition_year(declaration.identifier, modelo, years)
        key = (declaration.family, collapsed if collapsed is not None else declaration.identifier)
        groups[key].append(declaration)
        if collapsed is not None:
            keyed[key].append(declaration)

    namespace = _namespace_by_revision(modelo, modelo_dir)

    for key in sorted(keyed):
        family, collapsed_id = key
        members = groups[key]
        blocked = sorted({member.revision_id for member in members} & conflicted)
        if blocked:
            plan.refusals.append(
                f"{modelo} {family} {collapsed_id}: edition {', '.join(blocked)} has a conflicting "
                f"{_FAMILY_DEFAULT_KEY[family]}, so its references cannot be lifted"
            )
            continue
        bodies = {member.lifted(effective.get((family, member.revision_id), ())) for member in members}
        if len(bodies) > 1:
            spellings = ", ".join(sorted({member.identifier for member in members}))
            plan.refusals.append(
                f"{modelo} {family} {collapsed_id}: declarations differ after the collapse ({spellings})"
            )
            continue
        collision = next(
            (
                f"{member.revision_id}:{namespace[member.revision_id][collapsed_id]}"
                for member in keyed[key]
                if namespace.get(member.revision_id, {}).get(collapsed_id) not in (None, family)
            ),
            None,
        )
        if collision is not None:
            plan.refusals.append(f"{modelo} {family} {collapsed_id}: collapsed id already owned in {collision}")
            continue
        for member in members:
            lift_key = (family, member.revision_id)
            if lift_key in bootstrapped:
                plan.manifest_writes[lift_key] = bootstrapped[lift_key]
        for member in keyed[key]:
            plan.renames[member.identifier] = collapsed_id
    plan.stranded_export_trees = stranded_export_trees(plan, modelos_root)
    return plan


def stranded_export_trees(plan: CollapsePlan, modelos_root: Path = REGISTRY_MODELOS_ROOT) -> tuple[str, ...]:
    """Return the revisions whose generated export tree quotes an id this plan renames.

    Read from the generated tree itself rather than from a list of modelos kept
    by hand: the module docstring's ``DEFERRED_MODELOS`` roster was exactly such
    a list, it named only modelo 390, and modelos 232 and 353 shipped the same
    hazard without being on it. A tree that quotes no renamed id is not
    stranded, so a modelo carrying an export tree it does not touch still
    applies.

    The quote style is deliberately not part of the test. Generated fragments
    spell a binding reference in single quotes where authored fragments use
    double, and a match that assumed either would miss the whole population.
    """
    modelo_dir = modelos_root / plan.modelo
    found: list[str] = []
    for export_dir in sorted(modelo_dir.glob("revisions/*/export")):
        revision_id = export_dir.parent.name
        for path in sorted(export_dir.rglob("*")):
            if not path.is_file() or path.suffix not in {".toml", ".json"}:
                continue
            text = path.read_text(encoding="utf-8")
            if any(old_id in text for old_id in plan.renames):
                found.append(revision_id)
                break
    return tuple(found)


def _lift_file(path: Path, default: tuple[str, ...]) -> str:
    """Return one fragment's text with ``default`` lifted out of every row's ``source_refs``."""
    rendered: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _SOURCE_REFS_LINE.match(line)
        if match is None:
            rendered.append(line)
            continue
        items = _quoted_items(match.group("items"))
        if items == default:
            continue
        if items[: len(default)] == default:
            tail = ", ".join(f'"{item}"' for item in items[len(default) :])
            rendered.append(f"additional_source_refs = [{tail}]")
            continue
        rendered.append(line)
    return "\n".join(rendered) + "\n"


def _write_manifest_default(modelo_dir: Path, revision_id: str, family: str, refs: tuple[str, ...]) -> Path:
    """Declare a family's shared ``source_refs`` once on the edition's manifest."""
    manifest = modelo_dir / "revisions" / revision_id / _MANIFEST_NAME
    key = _FAMILY_DEFAULT_KEY[family]
    joined = ", ".join('"' + ref + '"' for ref in refs)
    rendered = f"{key} = [{joined}]"
    header = re.compile(rf"""^\[revisions\.(?:"{re.escape(revision_id)}"|{re.escape(revision_id)})\]\s*$""")
    lines = manifest.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if header.match(line):
            lines.insert(index + 1, rendered)
            break
    else:
        raise RuntimeError(f"{manifest}: no [revisions.{revision_id}] table to declare {key} on")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def apply_collapse(
    plan: CollapsePlan,
    modelos_root: Path = REGISTRY_MODELOS_ROOT,
    mappings_root: Path = MAPPINGS_ROOT,
    *,
    export_republish_acknowledged: bool = False,
) -> list[Path]:
    """Lift the shared references, write the manifest defaults, and rewrite every collapsed id.

    One run, because the three are one change: a member drops a reference only
    because the manifest now states it, and leaves the tree valid only if both
    land together.

    Raises:
        GeneratedExportTreeStaleError: When a published generated export tree
            quotes an id this plan renames and the caller has not acknowledged
            that the same change republishes it.
        FamilyDefaultUnsupportedError: When a lift is planned but the typed
            revision model declares no field to carry it.
    """
    if not plan.renames:
        return []
    if plan.stranded_export_trees and not export_republish_acknowledged:
        raise GeneratedExportTreeStaleError(plan.modelo, plan.stranded_export_trees)
    if plan.manifest_writes:
        missing = _missing_family_default_fields()
        if missing:
            raise FamilyDefaultUnsupportedError(missing)
    modelo_dir = modelos_root / plan.modelo
    mapping_dir = mappings_root / f"modelo_{plan.modelo}"
    touched: list[Path] = []

    for (family, revision_id), refs in sorted(plan.manifest_writes.items()):
        family_dir = modelo_dir / "revisions" / revision_id / family
        for path in sorted(family_dir.glob("*.toml")):
            lifted = _lift_file(path, refs)
            if lifted != path.read_text(encoding="utf-8"):
                path.write_text(lifted, encoding="utf-8")
                touched.append(path)
        touched.append(_write_manifest_default(modelo_dir, revision_id, family, refs))

    ordered = sorted(plan.renames.items(), key=lambda pair: len(pair[0]), reverse=True)
    candidates: list[Path] = [
        path
        for path in modelo_dir.rglob("*.toml")
        if not any(part == "export" for part in path.relative_to(modelo_dir).parts)
    ]
    if mapping_dir.is_dir():
        candidates.extend(sorted(mapping_dir.rglob("*.toml")))
    for path in candidates:
        original = path.read_text(encoding="utf-8")
        updated = original
        for old_id, new_id in ordered:
            # Both quote styles: the authored corpus spells a reference in
            # double quotes and the semantic maps may spell it in either, so
            # matching one style silently leaves the other behind.
            updated = updated.replace(f'"{old_id}"', f'"{new_id}"').replace(f"'{old_id}'", f"'{new_id}'")
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            if path not in touched:
                touched.append(path)
    return touched


def main(argv: list[str] | None = None) -> int:
    """Run the measurement pass and, with ``--apply``, the rewrite; return the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Rewrite files in place; default is measure-only.")
    parser.add_argument("--json", action="store_true", help="Emit the measurement report as JSON.")
    parser.add_argument(
        "--modelo",
        action="append",
        default=[],
        help="Restrict both rules to this modelo; repeatable. Required by the edition-year collapse.",
    )
    parser.add_argument("--report", type=Path, default=None, help="Write the JSON summary to this path.")
    parser.add_argument(
        "--export-republish-acknowledged",
        action="store_true",
        help="Apply even though a generated export tree quotes a renamed id; only within a change that republishes it.",
    )
    args = parser.parse_args(argv)

    selected = tuple(args.modelo)

    _check_separator_set_matches_identifier_lineage()

    measurements, failures = measure(selected)

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

    # The edition-year collapse is per-modelo and auditable by design, so it
    # runs only for modelos named explicitly. Its refusals do NOT gate the
    # whole-revision rule below: a refused identifier is a finding about two
    # editions that genuinely differ, not a defect in the corpus.
    collapse_plans = [plan_edition_year_collapse(modelo) for modelo in selected]
    report["edition_year_collapse"] = {
        plan.modelo: {
            "valid_from_years": plan.valid_from_years,
            "year_set": list(plan.year_set),
            "collapsed_count": plan.collapsed_count,
            "collapsed": dict(sorted(plan.renames.items())),
            "refused": plan.refusals,
            "stranded_export_trees": list(plan.stranded_export_trees),
            "family_defaults": {
                f"{family}/{revision}": list(refs) for (family, revision), refs in sorted(plan.family_defaults.items())
            },
            "manifest_writes": {
                f"{family}/{revision}": list(refs) for (family, revision), refs in sorted(plan.manifest_writes.items())
            },
        }
        for plan in collapse_plans
    }

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
            for trees in sorted(generated_tree_impact.values(), key=lambda group: group[0]):
                for tree in trees:
                    print(f"  {tree}")
        else:
            print("No generated export tree quotes a renamed id.")
        for plan in collapse_plans:
            print(f"Edition-year collapse {plan.modelo}: years {', '.join(plan.year_set) or 'none'}")
            for (family, revision), refs in sorted(plan.manifest_writes.items()):
                print(f"  would lift {family} {revision} -> {_FAMILY_DEFAULT_KEY[family]} = {list(refs)}")
            for revision in plan.stranded_export_trees:
                print(f"  STRANDS generated export tree {plan.modelo}/{revision}; republish must land in this change")
            print(f"  collapsed {plan.collapsed_count} identifiers, refused {len(plan.refusals)}")
            for refusal in plan.refusals:
                print(f"    REFUSED {refusal}")

    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if failures:
        print("Refusing to apply: unresolved collisions or ambiguous renames reported above.", file=sys.stderr)
        return 1

    if args.apply:
        for plan in collapse_plans:
            try:
                touched = apply_collapse(plan, export_republish_acknowledged=args.export_republish_acknowledged)
            except (FamilyDefaultUnsupportedError, GeneratedExportTreeStaleError) as exc:
                print(f"Refusing to apply {plan.modelo}: {exc}", file=sys.stderr)
                return 1
            print(
                f"Edition-year collapse {plan.modelo}: "
                f"{plan.collapsed_count} identifiers collapsed, {len(touched)} files touched"
            )
        files_touched = apply_renames(measurements)
        total_files = sum(files_touched.values())
        print(f"Applied renames across {total_files} files in {len(files_touched)} modelos.")
        for modelo, count in sorted(files_touched.items()):
            renamed = len(measurements[modelo].renames)
            print(f"  {modelo}: {renamed} identifiers renamed, {count} files touched")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
