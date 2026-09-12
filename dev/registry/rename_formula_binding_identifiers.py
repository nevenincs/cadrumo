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

Fourth rule: the fixed-width span strip (``--strip-spans``, bindings only). A
binding id such as ``modelo-131.page1.109-112.actividad-1-epigrafe`` names a
slot AND the fixed-width address of that slot, and the address is already
stated -- typed, and the only copy anything reads -- by the row's own
``provider.offset`` and ``provider.length``. The id's copy is a restatement that
goes stale the moment a record design moves the field, which is exactly the
moment an identifier must not change, so the segment is removed and the id is
left naming a timeless slot.

The proof is per row. A separator-bounded ``<digits>-<digits>`` run is stripped
only when it EQUALS the member's own provider address, ``offset`` through
``offset + length - 1``. An id carrying a span-shaped run no provider declares
is refused and listed rather than guessed at: such a run may be a year range, a
legal-norm pair or a repetition group, and each would mean something different.
An id carrying no span-shaped run at all is simply untouched -- a dotted id is
not a candidate for stating a dot.

Refusal is per modelo. The post-strip image of each edition's whole authored
namespace is computed before anything is written, and two members of one edition
landing on one name withdraw the entire modelo with the pairs listed. A half
applied edition would be spelled under a rule no reader could reapply by hand.
References are rewritten in the same pass -- casilla ``binding`` and
``alternate_bindings``, formula operands, export field bindings, constructs,
``dependency_classifications`` ``binding_refs``, verification expectations, and
the ``dev/registry/mappings`` semantic maps -- and the generated-export-tree
guard fires where a published tree quotes a stripped id. Locale prose is
reported, never hand-edited. Modelo 714 is withheld entirely: its within-edition
collisions are repetition groups whose surviving names need the generator's
repetition index.

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
from collections.abc import Iterator, Mapping, Sequence, Set
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from types import UnionType
from typing import Annotated, Any, Protocol, Union, get_args, get_origin

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_MODELOS_ROOT = REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"
MAPPINGS_ROOT = REPO_ROOT / "dev" / "registry" / "mappings"

sys.path.insert(0, str(REPO_ROOT / "src"))

from cadrumo.domain.calculations.registry.identifier_lineage import (  # noqa: E402
    EDITION_PLACEHOLDER,
    identifier_lineage,
)
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector  # noqa: E402

# The edition-delta signal is imported lazily by the two rules that consult it.
# It reaches the whole registry domain, and the fourth rule below (the span
# strip) consults nothing but a member's own provider table, so a module-level
# import would make an independent rule unavailable whenever the domain's own
# import graph is mid-change.

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
    from .analysis.edition_delta_status import supported_filing_years

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


# ---------------------------------------------------------------------------
# Third rule: the family-wide edition-token collapse (every id-keyed family).
# ---------------------------------------------------------------------------

#: Casillas key on ``continuidad_id`` rather than on a token-bearing name, and
#: their ids are box numbers the official record design owns, so they never
#: enter this collapse even though ``CasillaDefinition`` declares an ``id``.
_COLLAPSE_EXCLUDED_FAMILIES: frozenset[str] = frozenset({"casillas"})

#: An export layout the generator writes, named from the modelo and the edition
#: it renders. Renaming one would rename the generator's own output under it, so
#: it is reported and skipped rather than collapsed.
_GENERATED_EXPORT_LAYOUT_ID = re.compile(r"^generated-modelo-.+-fichero$")

#: A four-digit year pair. An occurrence of a token inside such a range is an
#: offset or validity window carried by the box rather than the edition
#: restating itself, and the signal's tokeniser excludes it; the removal below
#: must exclude the same spans or it would cut a range in half.
_YEAR_RANGE_SPAN = re.compile(r"(?<![0-9])\d{4}-\d{4}(?![0-9])")


class FamilyWithoutIdentityError(Exception):
    """A named family's member model declares no ``id``, so it cannot be collapsed."""

    def __init__(self, family: str) -> None:
        """Record the family whose element model carries no identity field."""
        super().__init__(
            f"family {family!r} is not an id-keyed schema family; the collapse keys on a member's own id "
            f"and the enrolled families are {', '.join(id_keyed_families())}"
        )
        self.family = family


def id_keyed_families() -> tuple[str, ...]:
    """Return every ``SCHEMA_FAMILY`` collection whose member model declares an ``id``.

    Read off the shipped ``ModeloRevision`` rather than listed here, so a family
    added to the schema is collapsed without this tool being edited to notice
    it, and a family whose element model carries no ``id`` is refused rather
    than silently skipped.
    """
    import typing

    from cadrumo.domain.calculations.registry.schema import ModeloRevision
    from cadrumo.domain.calculations.registry.schema_base import SCHEMA_FAMILY

    found: list[str] = []
    for name, info in ModeloRevision.model_fields.items():
        if not any(marker is SCHEMA_FAMILY for marker in info.metadata) or name in _COLLAPSE_EXCLUDED_FAMILIES:
            continue
        (element, *_rest) = typing.get_args(info.annotation) or (None,)
        candidates = [element] if hasattr(element, "model_fields") else list(typing.get_args(element))
        if any("id" in getattr(candidate, "model_fields", {}) for candidate in candidates):
            found.append(name)
    return tuple(found)


def _bounded_token_spans(identifier: str, token: str) -> tuple[tuple[int, int], ...]:
    """Return the spans where ``token`` sits as a whole, separator-bounded segment run.

    Bounded on both sides by an identifier separator or by the end of the
    identifier, so ``2024`` does not match inside ``20240`` and a whole
    qualified edition id such as ``2024-desde-09-y-3t`` matches as one token.
    Spans lying inside a ``NNNN-NNNN`` range that is not the token itself are
    dropped: the signal's tokeniser does not count them, and cutting one in half
    would rewrite a validity window into nonsense.
    """
    ranged = [match.span() for match in _YEAR_RANGE_SPAN.finditer(identifier) if match.group() != token]
    spans: list[tuple[int, int]] = []
    start = identifier.find(token)
    while start != -1:
        end = start + len(token)
        before_ok = start == 0 or identifier[start - 1] in _IDENTIFIER_SEPARATORS
        after_ok = end == len(identifier) or identifier[end] in _IDENTIFIER_SEPARATORS
        # A range the occurrence CONTAINS is part of the token itself --
        # edition ``2009-2011-junio`` spelled whole inside an identifier --
        # and only a range the occurrence cuts across disqualifies it.
        inside_range = any(low < end and start < high and not (start <= low and high <= end) for low, high in ranged)
        if before_ok and after_ok and not inside_range:
            spans.append((start, end))
        start = identifier.find(token, start + 1)
    return tuple(spans)


def strip_identifier_token(identifier: str, token: str) -> str:
    """Return ``identifier`` with its single bounded ``token`` segment and one separator removed.

    The separator immediately before the token is preferred, falling back to the
    one immediately after when the token opens the identifier, which is the rule
    :func:`strip_edition_key` applies to the whole-revision case, so the two
    produce one spelling rather than two.

    Every bounded occurrence is removed, right to left. An identifier such as
    ``renta-2020-minimo-contribuyente-base-2020`` restates its edition twice and
    both statements are the same fact the containing directory already names, so
    removing one and keeping the other would leave the condition half met under
    a name no rule could explain. The result is uniquely determined, and a
    collapse that lands on an identifier the edition already owns is refused by
    the caller's collision gate rather than guessed at here.

    Raises:
        AmbiguousRenameError: When the token appears nowhere as a whole,
            separator-bounded segment run -- the tokeniser saw it as a bare
            substring, which is not a statement the edition made.
    """
    spans = _bounded_token_spans(identifier, token)
    if not spans:
        raise AmbiguousRenameError(identifier, token, 0)
    collapsed = identifier
    for start, end in reversed(spans):
        prefix, suffix = collapsed[:start], collapsed[end:]
        if prefix and prefix[-1] in _IDENTIFIER_SEPARATORS:
            collapsed = prefix[:-1] + suffix
        elif suffix and suffix[0] in _IDENTIFIER_SEPARATORS:
            collapsed = prefix + suffix[1:]
        else:
            collapsed = prefix + suffix
    return collapsed


@dataclass(frozen=True)
class MemberRename:
    """One member id the collapse would rewrite, with the token it carries."""

    modelo: str
    edition: str
    family: str
    old_id: str
    new_id: str
    token: str


@dataclass
class FamilyCollapsePlan:
    """One modelo's family-wide collapse: what it rewrites, skips and refuses."""

    modelo: str
    families: tuple[str, ...] = ()
    renames: list[MemberRename] = field(default_factory=list)
    collisions: list[str] = field(default_factory=list)
    refusals: list[str] = field(default_factory=list)
    generated_skipped: list[str] = field(default_factory=list)
    stranded_export_trees: tuple[str, ...] = ()

    @property
    def rename_map(self) -> dict[str, str]:
        """The accepted ``old id -> new id`` map, keyed by old id."""
        return {rename.old_id: rename.new_id for rename in self.renames}

    def withdraw(self, identifiers: Set[str]) -> None:
        """Drop every planned rename whose source id is in *identifiers*."""
        self.renames = [rename for rename in self.renames if rename.old_id not in identifiers]

    def per_family(self) -> dict[str, int]:
        """How many members the plan rewrites, per family."""
        counts: dict[str, int] = defaultdict(int)
        for rename in self.renames:
            counts[rename.family] += 1
        return dict(sorted(counts.items()))


def _filing_coordinate_scalars(annotation: object) -> Iterator[object]:
    """Yield the scalar types one field annotation can resolve to.

    ``Annotated`` wrappers and optional unions are transparent -- they qualify a
    type without changing what the field holds -- while a container is NOT
    descended into. ``tuple[PeriodCode, ...]`` is the set of periods a row
    COVERS, not the coordinate that identifies it, and reading it as identity
    would withhold a filing schedule whose id names no period at all.
    """
    yield annotation
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is Annotated:
        yield from _filing_coordinate_scalars(args[0])
    elif origin in {Union, UnionType}:
        for argument in args:
            yield from _filing_coordinate_scalars(argument)


def is_filing_coordinate_annotation(annotation: object) -> bool:
    """Whether a field's declared TYPE makes it a filing coordinate.

    Structural, not nominal: the question is whether the field holds a filing
    year or a filing period, which the shipped type answers. A field named
    ``anio_devengo`` typed ``FilingYear`` is a coordinate and a field named
    ``period_kind`` typed as a cadence enum is not, and neither answer depends
    on how the field happens to be spelled.
    """
    from cadrumo.core.filing_year import FilingYear
    from cadrumo.core.period import Period, RegistrySelectorPeriodCode
    from cadrumo.domain.calculations.registry.schema_scalars import PeriodCode

    aliases = (FilingYear, PeriodCode, RegistrySelectorPeriodCode)
    for candidate in _filing_coordinate_scalars(annotation):
        if any(candidate == alias for alias in aliases):
            return True
        if isinstance(candidate, type) and issubclass(candidate, Period):
            return True
    return False


def family_data_fields(family: str) -> tuple[str, ...]:
    """Return the typed filing-coordinate fields a family's member model declares.

    A member may state a year as its own datum -- ``DeadlineWindowDefinition``
    declares ``filing_year``, and modelo 763's ``modelo-763-2013-1t`` names the
    quarter of a filing year its multi-year edition covers. That year is what
    the row is ABOUT, not the edition restating itself, so the collapse must
    leave it alone; stripping it would merge four windows of one edition into
    one name and lose three filing years.

    A field earns the exemption by its declared TYPE -- the ``FilingYear`` alias,
    the ``Period`` model, or a registry period-code alias -- and never by its
    name. A name test asks whether the author happened to spell ``year`` or
    ``period`` into the field, which a Spanish-named ``ejercicio`` coordinate
    fails while an unrelated ``grace_period`` duration passes; the type is the
    thing the schema actually guarantees. Read off the shipped model, so a
    family that gains such a field is exempted without this tool being edited to
    notice it.
    """
    import typing

    from cadrumo.domain.calculations.registry.schema import ModeloRevision

    info = ModeloRevision.model_fields.get(family)
    if info is None:
        return ()
    (element, *_rest) = typing.get_args(info.annotation) or (None,)
    candidates = [element] if hasattr(element, "model_fields") else list(typing.get_args(element))
    found: set[str] = set()
    for candidate in candidates:
        fields = getattr(candidate, "model_fields", None)
        if not fields:
            continue
        hints = typing.get_type_hints(candidate, include_extras=True)
        found.update(name for name in fields if is_filing_coordinate_annotation(hints.get(name)))
    return tuple(sorted(found))


def data_keyed_families() -> tuple[str, ...]:
    """Return the families whose members are identified by a filing coordinate they state.

    ``DeadlineWindowDefinition`` declares ``filing_year`` and ``period``, so a
    window IS a ``(year, period)`` cell and its id spells that cell:
    ``modelo-763-2018-4t`` under the edition ``2018-4t`` names the fourth
    quarter of 2018, and the year is the datum whichever rule matches it --
    the edition id and the filing year coincide there precisely BECAUSE the
    edition is that one cell. Collapsing such an id merges distinct cells, so
    the whole family is withheld from the rename rather than protected member by
    member. Read off the model, so a family that gains a filing coordinate
    leaves the pass without this tool being edited to notice it.
    """
    return tuple(family for family in id_keyed_families() if family_data_fields(family))


def member_declared_years(member: Mapping[str, Any], family: str) -> frozenset[str]:
    """Return the four-digit years a member states in its own typed year fields."""
    years: set[str] = set()
    for name in family_data_fields(family):
        value = member.get(name)
        if isinstance(value, int):
            years.add(f"{value:04d}")
        elif isinstance(value, str) and len(value) == 4 and value.isdigit():
            years.add(value)
    return frozenset(years)


def planned_token(family: str, identifier: str, member: Mapping[str, Any], edition: str) -> str | None:
    """Return the edition token a member would lose, or ``None`` when it loses none.

    The token itself is the signal's own decision, imported rather than copied.
    The one thing added here is the datum exemption: a year the member states in
    its own typed year field is what the row is about, so it stays.
    """
    from .analysis.edition_delta_status import edition_token_in_identifier

    token = edition_token_in_identifier(identifier, edition)
    if token is None or token in member_declared_years(member, family):
        return None
    return token


def _is_generated_path(path: Path, root: Path) -> bool:
    """Whether a file sits inside a generator-owned ``export`` tree."""
    return any(part == "export" for part in path.relative_to(root).parts)


def edition_sections(revision_dir: Path, revision_id: str, families: Sequence[str]) -> dict[str, list[dict[str, Any]]]:
    """Merge every authored fragment below one edition into one member list per family.

    Mirrors the loader's own merge across fragment files and reads only the
    authored tree: a generator-owned ``export`` subtree is collected separately
    so its ids can be reported as skipped rather than silently renamed.
    """
    merged: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(revision_dir.rglob("*.toml")):
        if _is_generated_path(path, revision_dir):
            continue
        table = _load_toml(path).get("revisions", {}).get(revision_id)
        if not isinstance(table, dict):
            continue
        for family in families:
            declared = table.get(family)
            if isinstance(declared, list):
                merged[family].extend(entry for entry in declared if isinstance(entry, dict))
    return dict(merged)


def generated_layout_ids(revision_dir: Path, revision_id: str) -> list[str]:
    """Return the generator-owned export layout ids published under one edition."""
    found: list[str] = []
    for path in sorted(revision_dir.rglob("*.toml")):
        if not _is_generated_path(path, revision_dir):
            continue
        table = _load_toml(path).get("revisions", {}).get(revision_id)
        if not isinstance(table, dict):
            continue
        declared = table.get("export_layouts")
        for entry in declared if isinstance(declared, list) else ():
            if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                found.append(entry["id"])
    return found


def plan_family_collapse(
    modelo: str,
    families: Sequence[str] = (),
    modelos_root: Path = REGISTRY_MODELOS_ROOT,
) -> FamilyCollapsePlan:
    """Decide which of one modelo's id-keyed family members lose their edition token.

    The qualifying test is the signal's own ``edition_token_in_identifier``,
    imported rather than reimplemented so the screen that reports the condition
    and the tool that clears it can never disagree about what carries a token.
    A member whose id carries one is renamed to the token-free spelling; a member
    with a stable id is untouched, which is why modelo 131's parameters, mixing
    both shapes, come through half rewritten.

    Raises:
        FamilyWithoutIdentityError: When ``families`` names a family whose
            member model declares no ``id``.
    """
    from .analysis.edition_delta_status import edition_token_in_identifier

    enrolled = id_keyed_families()
    for family in families:
        if family not in enrolled:
            raise FamilyWithoutIdentityError(family)
    withheld = set(data_keyed_families())
    selected = tuple(family for family in (families or enrolled) if family not in withheld)
    plan = FamilyCollapsePlan(modelo=modelo, families=selected)
    for family in sorted(withheld.intersection(families or enrolled)):
        plan.refusals.append(
            f"{modelo} {family}: members are identified by the filing coordinate they state "
            f"({', '.join(family_data_fields(family))}), so no id in this family is a rename candidate"
        )
    modelo_dir = modelos_root / modelo
    if not modelo_dir.is_dir():
        plan.refusals.append(f"{modelo}: no such modelo directory under {modelos_root}")
        return plan

    inventory: dict[str, list[tuple[str, str]]] = {}
    for revision_dir in iter_revision_dirs(modelo_dir):
        edition = revision_dir.name
        sections = edition_sections(revision_dir, edition, selected)
        # The edition's whole authored namespace, so a collapse landing on an id
        # another family already owns is refused rather than quietly merged.
        owned: dict[str, str] = {}
        for family, members in edition_sections(revision_dir, edition, (*enrolled, "casillas")).items():
            for member in members:
                if isinstance(member.get("id"), str):
                    owned.setdefault(member["id"], family)
        for layout_id in generated_layout_ids(revision_dir, edition):
            owned.setdefault(layout_id, "export_layouts")
            entry = f"{modelo} {edition} export_layouts {layout_id}"
            # One generated layout is written across several fragment files, so
            # the id repeats; the skip list names the declaration, not its parts.
            if edition_token_in_identifier(layout_id, edition) is not None and entry not in plan.generated_skipped:
                plan.generated_skipped.append(entry)
        inventory[edition] = sorted((identifier, family) for identifier, family in owned.items())

        # A family the loader merges by id across fragment files states one
        # declaration in several places; a repeated id there is fragmentation,
        # not a second member, and reading it as one would report every
        # fragmented layout as colliding with itself.
        candidates: list[tuple[str, str, dict[str, Any]]] = []
        seen: set[tuple[str, str]] = set()
        for family in selected:
            for member in sections.get(family, ()):
                identifier = member.get("id")
                if not isinstance(identifier, str) or not identifier or (family, identifier) in seen:
                    continue
                seen.add((family, identifier))
                candidates.append((family, identifier, member))

        # Two members of one edition may collapse onto one name -- modelo 184's
        # 2019 and 2021 deadline windows under the edition 2019-2021 both become
        # ``modelo-184-0a``. Neither is more entitled to the surviving name than
        # the other, so BOTH are refused: picking the first read would make the
        # result depend on fragment order, and the year is carrying real meaning
        # wherever this happens.
        contenders: dict[str, list[str]] = defaultdict(list)
        for family, identifier, member in candidates:
            token = planned_token(family, identifier, member, edition)
            if token is None:
                continue
            try:
                contenders[strip_identifier_token(identifier, token)].append(f"{family}:{identifier}")
            except AmbiguousRenameError:
                continue

        for family, identifier, member in candidates:
            if family == "export_layouts" and _GENERATED_EXPORT_LAYOUT_ID.match(identifier):
                entry = f"{modelo} {edition} {family} {identifier}"
                if entry not in plan.generated_skipped:
                    plan.generated_skipped.append(entry)
                continue
            token = planned_token(family, identifier, member, edition)
            if token is None:
                continue
            try:
                new_id = strip_identifier_token(identifier, token)
            except AmbiguousRenameError as exc:
                plan.refusals.append(f"{modelo} {edition} {family} {identifier}: {exc}")
                continue
            if not new_id:
                plan.refusals.append(
                    f"{modelo} {edition} {family} {identifier}: the whole identifier is the edition token"
                )
                continue
            if new_id in owned:
                plan.collisions.append(
                    f"{modelo} {edition} {family}: {identifier} -> {new_id} already declared by "
                    f"{owned[new_id]} in the same edition"
                )
                continue
            if len(contenders.get(new_id, ())) > 1:
                plan.collisions.append(
                    f"{modelo} {edition} {family}: {identifier} -> {new_id} contested by "
                    f"{', '.join(sorted(contenders[new_id]))} in the same edition"
                )
                continue
            plan.renames.append(
                MemberRename(
                    modelo=modelo,
                    edition=edition,
                    family=family,
                    old_id=identifier,
                    new_id=new_id,
                    token=token,
                )
            )
    _refuse_post_image_collisions(plan, inventory)
    plan.stranded_export_trees = stranded_generated_trees(modelo_dir, plan.rename_map)
    return plan


class PostImageRefusablePlan(Protocol):
    """The surface :func:`_refuse_post_image_collisions` needs from a rename plan.

    Both the family collapse and the span strip produce a corpus-wide textual
    rewrite from a per-edition plan, so both are exposed to the same
    cross-edition post-image collision and both are screened by the same
    function rather than by two drifting copies of the projection.
    """

    modelo: str
    collisions: list[str]

    @property
    def rename_map(self) -> dict[str, str]:
        """The accepted ``old id -> new id`` map, keyed by old id."""
        ...

    def withdraw(self, identifiers: Set[str]) -> None:
        """Drop every planned rename whose source id is in *identifiers*."""
        ...


def _refuse_post_image_collisions(
    plan: PostImageRefusablePlan,
    inventory: Mapping[str, list[tuple[str, str]]],
) -> None:
    """Drop every rename that would leave two members of one edition sharing a name.

    The per-edition gate above cannot see this on its own, because the rewrite
    is TEXTUAL and corpus-wide while the plan is per-edition: modelo 210 spells
    ``modelo-210-procedure-2025`` and ``modelo-210-procedure-2026`` in BOTH its
    editions, each edition collapses the one that carries its own year, and the
    rewrite of either lands on the other edition's copy as well. Only the
    modelo's whole post-image shows it, so the map is projected over every
    edition's full id inventory and any name two members would then share
    withdraws every rename that produced it.
    """
    renames = plan.rename_map
    if not renames:
        return
    contested: dict[str, set[str]] = defaultdict(set)
    for edition, declared in inventory.items():
        after: dict[str, list[str]] = defaultdict(list)
        for identifier, family in declared:
            after[renames.get(identifier, identifier)].append(f"{family}:{identifier}")
        for collapsed, owners in after.items():
            if len(owners) > 1:
                plan.collisions.append(
                    f"{plan.modelo} {edition}: {collapsed} would be shared by {', '.join(sorted(owners))} "
                    "after the rewrite; every rename onto it is withdrawn"
                )
                contested[collapsed].update(
                    identifier for identifier, _family in declared if renames.get(identifier) == collapsed
                )
    plan.withdraw({identifier for group in contested.values() for identifier in group})


def stranded_generated_trees(modelo_dir: Path, renames: Mapping[str, str]) -> tuple[str, ...]:
    """Return the editions whose generated export tree quotes an id this plan renames."""
    found: list[str] = []
    for export_dir in sorted(modelo_dir.glob("revisions/*/export")):
        for path in sorted(export_dir.rglob("*")):
            if not path.is_file() or path.suffix not in {".toml", ".json"}:
                continue
            text = path.read_text(encoding="utf-8")
            if any(old_id in text for old_id in renames):
                found.append(export_dir.parent.name)
                break
    return tuple(found)


def rewritable_files(modelos_root: Path = REGISTRY_MODELOS_ROOT, mappings_root: Path = MAPPINGS_ROOT) -> list[Path]:
    """Every authored registry file a reference rewrite may touch.

    Corpus-wide rather than one modelo's subtree: a construct, dependency
    classification or cross-reference in another modelo may quote a renamed id,
    and a rewrite scoped to the declaring modelo would leave that reference
    dangling. Generator-owned ``export`` trees are excluded here and handled by
    the republish guard instead.
    """
    candidates = [path for path in modelos_root.rglob("*.toml") if not _is_generated_path(path, modelos_root)]
    if mappings_root.is_dir():
        candidates.extend(sorted(mappings_root.rglob("*.toml")))
    return sorted(candidates)


def code_reference_files(repo_root: Path = REPO_ROOT) -> list[Path]:
    """Non-test Python modules that may quote a registry identifier by literal.

    A registry id reaches beyond the TOML corpus: a projection or diagnostic
    module may name a parameter directly, and a rename that stops at the corpus
    boundary leaves such a module pointing at a declaration that no longer
    exists. Test modules are deliberately excluded -- they are owned by whoever
    is editing them, and a rename that rewrites another contributor's test under
    them is not this tool's call to make; the caller is handed the list instead.
    """
    found: list[Path] = []
    for root in (repo_root / "src" / "cadrumo", repo_root / "dev"):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            parts = path.relative_to(root).parts
            if "tests" in parts or "__pycache__" in parts or path.name.startswith("test_"):
                continue
            found.append(path)
    return found


LOCALES_ROOT = REPO_ROOT / "src" / "cadrumo" / "locales"


def locale_mentions(renames: Mapping[str, str], locales_root: Path = LOCALES_ROOT) -> dict[str, dict[str, int]]:
    """Return the locale catalogue cells that still name a renamed identifier.

    Reported rather than rewritten. A catalogue is owned by the locale
    authority, and the supported mutation is a manifest applied through
    ``dev.locales set-batch``; editing the YAML here would be exactly the
    hand-edit the locale contract forbids, and it would also skip the parity
    gate that proves every locale moved together. So the pass ends by naming the
    catalogues and the ids they still carry, which is the input that manifest
    is built from.
    """
    found: dict[str, dict[str, int]] = {}
    if not locales_root.is_dir():
        return found
    for path in sorted(locales_root.rglob("*.yml")):
        text = path.read_text(encoding="utf-8")
        counts = {old_id: text.count(old_id) for old_id in renames if old_id in text}
        if counts:
            found[str(path.relative_to(REPO_ROOT).as_posix())] = counts
    return found


def test_mentions(renames: Mapping[str, str], repo_root: Path = REPO_ROOT) -> dict[str, dict[str, int]]:
    """Return the test modules that still name a renamed identifier.

    :func:`code_reference_files` deliberately excludes test modules from the
    rewrite -- they belong to whoever is editing them, and rewriting another
    contributor's test under them is not this tool's call. That exclusion is
    only honest if the caller is actually HANDED the list, so it is reported
    here: a test naming an id the corpus no longer declares is a failure waiting
    to happen, and the owner needs to see it in the same run that causes it.
    """
    found: dict[str, dict[str, int]] = {}
    for root in (repo_root / "src" / "cadrumo", repo_root / "dev"):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            parts = path.relative_to(root).parts
            if "__pycache__" in parts or not ("tests" in parts or path.name.startswith("test_")):
                continue
            text = path.read_text(encoding="utf-8")
            counts = {old_id: text.count(old_id) for old_id in renames if old_id in text}
            if counts:
                found[str(path.relative_to(repo_root).as_posix())] = counts
    return found


def apply_family_collapse(
    plan: FamilyCollapsePlan,
    modelos_root: Path = REGISTRY_MODELOS_ROOT,
    mappings_root: Path = MAPPINGS_ROOT,
    *,
    code_files: Sequence[Path] | None = None,
    export_republish_acknowledged: bool = False,
) -> tuple[list[Path], int]:
    """Rewrite every declaration and reference of a planned rename; return touched files and hits.

    One textual pass over the authored corpus, so comments, ordering and
    hand-authored formatting survive. Both quote styles are rewritten: the
    authored corpus spells a reference in double quotes and the semantic maps
    spell it in either, and matching one style silently leaves the other behind.

    Raises:
        GeneratedExportTreeStaleError: When a published export tree quotes an id
            this plan renames and the caller has not stated that the same change
            republishes it.
    """
    renames = plan.rename_map
    if not renames:
        return [], 0
    if plan.stranded_export_trees and not export_republish_acknowledged:
        raise GeneratedExportTreeStaleError(plan.modelo, plan.stranded_export_trees)
    return rewrite_identifier_references(renames, modelos_root, mappings_root, code_files=code_files)


class ChainedRenameMapError(Exception):
    """A rename map whose target is also one of its own sources."""


def rewrite_identifier_references(
    renames: Mapping[str, str],
    modelos_root: Path = REGISTRY_MODELOS_ROOT,
    mappings_root: Path = MAPPINGS_ROOT,
    *,
    code_files: Sequence[Path] | None = None,
) -> tuple[list[Path], int]:
    """Rewrite every quoted occurrence of a renamed id across the authored corpus and code.

    One textual pass, so comments, ordering and hand-authored formatting survive,
    and it is deliberately id-shaped rather than field-shaped: a declaration, a
    casilla ``binding``/``alternate_bindings`` entry, a formula operand, an
    export layout's field binding, a construct member, a dependency
    classification's ``binding_refs`` and a verification expectation all spell
    the same id the same way, so matching the quoted id reaches every one of
    them without a per-field inventory that could go stale.

    Raises:
        ChainedRenameMapError: When any rename target is also a rename source.
            One pass cannot apply such a map: ``a -> b`` followed by ``b -> c``
            would carry ``a`` all the way to ``c`` while ``a -> b`` alone lands
            on ``b``, and the longest-first ordering decides which happens. The
            caller must compose the map before it gets here.
    """
    chained = sorted(set(renames.values()) & set(renames))
    if chained:
        pairs = ", ".join(f"{old_id} -> {renames[old_id]}" for old_id in chained)
        message = (
            "refusing a chained rename map: the rewrite is one textual pass over each file, so a "
            "target that is itself a source is rewritten again and the result depends on which "
            f"pair the pass reaches first; chained pairs: {pairs}"
        )
        raise ChainedRenameMapError(message)
    ordered = sorted(renames.items(), key=lambda pair: len(pair[0]), reverse=True)
    touched: list[Path] = []
    hits = 0
    code = list(code_reference_files()) if code_files is None else list(code_files)
    for path in [*rewritable_files(modelos_root, mappings_root), *code]:
        original = path.read_text(encoding="utf-8")
        updated = original
        for old_id, new_id in ordered:
            for quote in ('"', "'"):
                needle = f"{quote}{old_id}{quote}"
                if needle in updated:
                    hits += updated.count(needle)
                    updated = updated.replace(needle, f"{quote}{new_id}{quote}")
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            touched.append(path)
    return touched, hits


# ---------------------------------------------------------------------------
# Fourth rule: the fixed-width span strip (bindings only).
# ---------------------------------------------------------------------------

#: Modelo 714 is withheld from this pass entirely. Its 128 within-edition
#: collisions are repetition groups -- the same field of a repeated record block
#: -- so the surviving name needs the generator's repetition index, which this
#: rule does not have and must not invent. A separate step carries it.
SPAN_STRIP_EXCLUDED_MODELOS: frozenset[str] = frozenset({"714"})

#: A fixed-width address spelled into an identifier: ``<from>-<to>``. The
#: internal ``-`` is itself an identifier separator, so this is a segment RUN
#: rather than one segment, matched with the same both-sides boundary test the
#: edition-token rule uses.
_SPAN_RUN = re.compile(r"(?<![0-9])(?P<low>\d+)-(?P<high>\d+)(?![0-9])")


class SpanProviderMismatchError(Exception):
    """A binding id spells a fixed-width span that its own provider does not declare."""

    def __init__(self, modelo: str, edition: str, identifier: str, candidates: tuple[str, ...], address: str) -> None:
        """Record the identifier, the span-shaped runs it carries, and the provider address."""
        super().__init__(
            f"{modelo} {edition} bindings {identifier}: spells span-shaped {', '.join(candidates)} but its "
            f"provider addresses {address}; the id does not name this provider's own span, so the strip "
            "would remove a segment whose meaning it has not established"
        )
        self.identifier = identifier


@dataclass(frozen=True)
class SpanStrip:
    """One binding id the span strip would rewrite, with the address segment it loses."""

    modelo: str
    edition: str
    old_id: str
    new_id: str
    segment: str


@dataclass
class SpanStripPlan:
    """One modelo's span strip: what it rewrites, what it refuses, and why."""

    modelo: str
    strips: list[SpanStrip] = field(default_factory=list)
    refusals: list[str] = field(default_factory=list)
    collisions: list[str] = field(default_factory=list)
    stranded_export_trees: tuple[str, ...] = ()
    #: True once a within-edition collision withdrew the whole modelo.
    refused_modelo: bool = False

    @property
    def rename_map(self) -> dict[str, str]:
        """The accepted ``old id -> new id`` map, empty while the modelo is refused."""
        if self.refused_modelo:
            return {}
        return {strip.old_id: strip.new_id for strip in self.strips}

    def withdraw(self, identifiers: Set[str]) -> None:
        """Drop every planned strip whose source id is in *identifiers*."""
        self.strips = [strip for strip in self.strips if strip.old_id not in identifiers]


def provider_address(member: Mapping[str, Any]) -> tuple[int, int] | None:
    """Return a binding provider's ``(first, last)`` fixed-width offsets, or ``None``.

    The address is ``offset`` through ``offset + length - 1`` inclusive, which is
    exactly the span an id spells. A provider stating no offset or no positive
    length carries no address, and a candidate id beside one is refused rather
    than stripped: its span cannot be proven to restate anything.
    """
    provider = member.get("provider")
    if not isinstance(provider, Mapping):
        return None
    offset, length = provider.get("offset"), provider.get("length")
    if isinstance(offset, bool) or isinstance(length, bool):
        return None
    if not isinstance(offset, int) or not isinstance(length, int) or length < 1:
        return None
    return offset, offset + length - 1


def span_runs(identifier: str) -> tuple[tuple[int, int, int, int], ...]:
    """Return every separator-bounded ``<digits>-<digits>`` run as ``(start, end, low, high)``.

    Bounded on both sides by an identifier separator or by the identifier's own
    end, so the run is a segment the id states rather than digits found inside a
    longer word. The test is deliberately shape-only: whether a run is an
    address or an edition's year range is decided by comparing it with the
    member's provider, not by guessing from the numbers.
    """
    found: list[tuple[int, int, int, int]] = []
    for match in _SPAN_RUN.finditer(identifier):
        start, end = match.span()
        before_ok = start == 0 or identifier[start - 1] in _IDENTIFIER_SEPARATORS
        after_ok = end == len(identifier) or identifier[end] in _IDENTIFIER_SEPARATORS
        if before_ok and after_ok:
            found.append((start, end, int(match.group("low")), int(match.group("high"))))
    return tuple(found)


def strip_span_segment(identifier: str, start: int, end: int) -> str:
    """Return ``identifier`` with the run at ``[start, end)`` and one adjacent separator removed.

    The separator immediately before the run is preferred, falling back to the
    one immediately after when the run opens the identifier -- the same rule
    :func:`strip_edition_key` and :func:`strip_identifier_token` apply, so all
    four rules produce one spelling rather than four.
    """
    prefix, suffix = identifier[:start], identifier[end:]
    if prefix and prefix[-1] in _IDENTIFIER_SEPARATORS:
        return prefix[:-1] + suffix
    if suffix and suffix[0] in _IDENTIFIER_SEPARATORS:
        return prefix + suffix[1:]
    return prefix + suffix


def edition_declared_families(revision_dir: Path, revision_id: str) -> dict[str, list[dict[str, Any]]]:
    """Merge every authored fragment below one edition into one member list per declared family.

    Reads the families the edition actually declares rather than a list taken
    from the typed model, so the collision gate sees the whole authored
    namespace -- including a family this tool has never heard of -- and needs no
    import beyond ``tomllib``. Generator-owned ``export`` subtrees are collected
    separately by :func:`generated_layout_ids`.
    """
    merged: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(revision_dir.rglob("*.toml")):
        if _is_generated_path(path, revision_dir):
            continue
        table = _load_toml(path).get("revisions", {}).get(revision_id)
        if not isinstance(table, dict):
            continue
        for family, declared in table.items():
            if isinstance(declared, list):
                merged[family].extend(entry for entry in declared if isinstance(entry, dict))
    return dict(merged)


def plan_span_strip(modelo: str, modelos_root: Path = REGISTRY_MODELOS_ROOT) -> SpanStripPlan:
    """Decide which of one modelo's binding ids lose the fixed-width span they spell.

    A binding id such as ``modelo-131.page1.109-112.actividad-1-epigrafe`` names
    a slot AND its address, and the address is already stated -- typed, and the
    only copy anything reads -- by the row's own ``provider.offset``/``length``.
    The id's copy is therefore a restatement that goes stale the moment a record
    design moves a field, which is precisely when an identifier must not change.
    So the segment is removed, and only where the provider PROVES it is the
    address: a span-shaped run no provider declares is refused and listed rather
    than guessed at, because a run this rule cannot explain may be a year range,
    a legal-norm pair, or a repetition group, and each would mean something
    different.

    Refusal is per modelo where two of one edition's members would collapse onto
    one name. A partial application would leave the edition half converted under
    a rule no reader could apply by hand, so the modelo stays whole and the
    colliding pairs are listed for the step that resolves them.
    """
    plan = SpanStripPlan(modelo=modelo)
    modelo_dir = modelos_root / modelo
    if modelo in SPAN_STRIP_EXCLUDED_MODELOS:
        plan.refusals.append(f"{modelo}: withheld from the span strip; its collisions need a repetition index")
        plan.refused_modelo = True
        return plan
    if not modelo_dir.is_dir():
        plan.refusals.append(f"{modelo}: no such modelo directory under {modelos_root}")
        plan.refused_modelo = True
        return plan

    inventory: dict[str, list[tuple[str, str]]] = {}
    for revision_dir in iter_revision_dirs(modelo_dir):
        edition = revision_dir.name
        sections = edition_declared_families(revision_dir, edition)
        owned: dict[str, str] = {}
        for family, members in sorted(sections.items()):
            for member in members:
                if isinstance(member.get("id"), str):
                    owned.setdefault(member["id"], family)
        for layout_id in generated_layout_ids(revision_dir, edition):
            owned.setdefault(layout_id, "export_layouts")

        edition_strips: list[SpanStrip] = []
        seen: set[str] = set()
        for member in sections.get("bindings", ()):
            identifier = member.get("id")
            if not isinstance(identifier, str) or not identifier or identifier in seen:
                continue
            seen.add(identifier)
            runs = span_runs(identifier)
            if not runs:
                continue
            address = provider_address(member)
            matching = [] if address is None else [run for run in runs if (run[2], run[3]) == address]
            if address is None or not matching:
                candidates = tuple(identifier[start:end] for start, end, _low, _high in runs)
                rendered = "no offset/length" if address is None else f"{address[0]}-{address[1]}"
                plan.refusals.append(str(SpanProviderMismatchError(modelo, edition, identifier, candidates, rendered)))
                continue
            if len(matching) > 1:
                plan.refusals.append(
                    f"{modelo} {edition} bindings {identifier}: spells its provider address "
                    f"{address[0]}-{address[1]} more than once; refusing to choose which run to remove"
                )
                continue
            start, end, _low, _high = matching[0]
            new_id = strip_span_segment(identifier, start, end)
            if not new_id:
                plan.refusals.append(f"{modelo} {edition} bindings {identifier}: the whole identifier is the span")
                continue
            edition_strips.append(
                SpanStrip(
                    modelo=modelo,
                    edition=edition,
                    old_id=identifier,
                    new_id=new_id,
                    segment=identifier[start:end],
                )
            )

        # The post-strip image of this edition's WHOLE authored namespace, so a
        # stripped id landing on a name another family already owns is caught
        # alongside two stripped bindings landing on each other.
        stripped = {strip.old_id: strip.new_id for strip in edition_strips}
        after: dict[str, list[str]] = defaultdict(list)
        for identifier, family in sorted(owned.items()):
            after[stripped.get(identifier, identifier)].append(f"{family}:{identifier}")
        for collapsed, owners in sorted(after.items()):
            if len(owners) > 1:
                plan.collisions.append(f"{modelo} {edition}: {collapsed} would be shared by {', '.join(owners)}")
        plan.strips.extend(edition_strips)
        inventory[edition] = sorted(owned.items())

    # The same cross-edition projection the family collapse runs: the strip is
    # planned per edition but rewritten textually corpus-wide, so a stripped id
    # may land on a name a DIFFERENT edition already declares. Only the modelo's
    # whole post-image shows it.
    _refuse_post_image_collisions(plan, inventory)

    if plan.collisions:
        plan.refused_modelo = True
        plan.refusals.append(
            f"{modelo}: {len(plan.collisions)} within-edition collisions after the strip; the whole modelo is "
            "refused rather than half applied"
        )
    plan.stranded_export_trees = stranded_generated_trees(modelo_dir, plan.rename_map)
    return plan


def apply_span_strip(
    plan: SpanStripPlan,
    modelos_root: Path = REGISTRY_MODELOS_ROOT,
    mappings_root: Path = MAPPINGS_ROOT,
    *,
    code_files: Sequence[Path] | None = None,
    export_republish_acknowledged: bool = False,
) -> tuple[list[Path], int]:
    """Rewrite every declaration and reference of a planned span strip.

    Raises:
        GeneratedExportTreeStaleError: When a published export tree quotes an id
            this plan renames and the caller has not stated that the same change
            republishes it.
    """
    renames = plan.rename_map
    if not renames:
        return [], 0
    if plan.stranded_export_trees and not export_republish_acknowledged:
        raise GeneratedExportTreeStaleError(plan.modelo, plan.stranded_export_trees)
    return rewrite_identifier_references(renames, modelos_root, mappings_root, code_files=code_files)


def _run_span_strip(
    modelos: Sequence[str],
    *,
    write: bool,
    emit_json: bool,
    report_path: Path | None,
    export_republish_acknowledged: bool,
) -> int:
    """Report, and with ``--apply`` perform, the span strip for each named modelo."""
    report: dict[str, Any] = {"span_strip": {}}
    exit_code = 0
    for modelo in modelos:
        plan = plan_span_strip(modelo)
        entry = {
            "stripped_count": len(plan.rename_map),
            "candidates": len(plan.strips),
            "refused_modelo": plan.refused_modelo,
            "strips": [
                {"edition": s.edition, "old_id": s.old_id, "new_id": s.new_id, "segment": s.segment}
                for s in plan.strips
            ],
            "collisions": plan.collisions,
            "refused": plan.refusals,
            "stranded_export_trees": list(plan.stranded_export_trees),
            "locale_mentions": locale_mentions(plan.rename_map),
            "test_mentions": test_mentions(plan.rename_map),
        }
        report["span_strip"][modelo] = entry
        if not emit_json:
            print(f"Span strip {modelo}: {len(plan.rename_map)} binding ids, {len(plan.strips)} candidates")
            for collision in plan.collisions:
                print(f"  COLLISION {collision}")
            for refusal in plan.refusals:
                print(f"  REFUSED {refusal}")
            for revision in plan.stranded_export_trees:
                print(f"  STRANDS generated export tree {modelo}/{revision}; republish must land in this change")
            for catalogue, counts in sorted(entry["locale_mentions"].items()):
                print(
                    f"  LOCALE {catalogue} names {len(counts)} stripped ids; move them with "
                    "`uv run --no-sync python -m dev.locales set-batch <manifest>`"
                )
            for module, counts in sorted(entry["test_mentions"].items()):
                print(f"  TEST {module} names {len(counts)} stripped ids; owned by its author, not rewritten here")
        if plan.refused_modelo:
            exit_code = 1
            continue
        if write:
            try:
                touched, hits = apply_span_strip(plan, export_republish_acknowledged=export_republish_acknowledged)
            except GeneratedExportTreeStaleError as exc:
                print(f"Refusing to apply {modelo}: {exc}", file=sys.stderr)
                return 1
            entry["files_touched"] = len(touched)
            entry["references_rewritten"] = hits
            print(f"Span strip {modelo}: {hits} references rewritten, {len(touched)} files touched")
    if emit_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return exit_code


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
        "--family",
        action="append",
        default=[],
        help=(
            "Restrict the family-wide collapse to this id-keyed schema family; repeatable. "
            "Naming it also disables the older formula/binding-only rules, which it subsumes."
        ),
    )
    parser.add_argument(
        "--strip-spans",
        action="store_true",
        help=(
            "Run only the fixed-width span strip: remove a binding id's <from>-<to> segment where the row's "
            "own provider offset/length proves it is that address. Requires --modelo."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what --apply would rewrite and write nothing; the default when --apply is absent.",
    )
    parser.add_argument(
        "--export-republish-acknowledged",
        action="store_true",
        help="Apply even though a generated export tree quotes a renamed id; only within a change that republishes it.",
    )
    args = parser.parse_args(argv)

    selected = tuple(args.modelo)
    selected_families = tuple(args.family)
    if args.dry_run and args.apply:
        parser.error("--dry-run and --apply state opposite intents; pass one")
    write = args.apply and not args.dry_run

    _check_separator_set_matches_identifier_lineage()

    if args.strip_spans:
        if not selected:
            parser.error("--strip-spans is a per-modelo, auditable pass; name at least one --modelo")
        return _run_span_strip(
            selected,
            write=write,
            emit_json=args.json,
            report_path=args.report,
            export_republish_acknowledged=args.export_republish_acknowledged,
        )

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
    # The family-wide collapse subsumes both older rules -- its qualifying test
    # is the signal's tokeniser, which recognises the whole edition id and the
    # edition's own year alike -- so naming a family retires them for this run
    # rather than letting two rules rewrite one identifier in sequence.
    collapse_plans = [] if selected_families else [plan_edition_year_collapse(modelo) for modelo in selected]
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

    try:
        family_plans = [plan_family_collapse(modelo, selected_families) for modelo in selected]
    except FamilyWithoutIdentityError as exc:
        print(f"Refusing: {exc}", file=sys.stderr)
        return 1
    report["family_collapse"] = {
        plan.modelo: {
            "families": list(plan.families),
            "renamed_count": len(plan.renames),
            "per_family": plan.per_family(),
            "renames": [
                {
                    "edition": rename.edition,
                    "family": rename.family,
                    "old_id": rename.old_id,
                    "new_id": rename.new_id,
                    "token": rename.token,
                }
                for rename in plan.renames
            ],
            "collisions": plan.collisions,
            "refused": plan.refusals,
            "generated_skipped": plan.generated_skipped,
            "stranded_export_trees": list(plan.stranded_export_trees),
            "locale_mentions": locale_mentions(plan.rename_map),
        }
        for plan in family_plans
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

    for plan in family_plans:
        print(f"Family collapse {plan.modelo}: {len(plan.renames)} identifiers, per family {plan.per_family()}")
        for collision in plan.collisions:
            print(f"  COLLISION {collision}")
        for refusal in plan.refusals:
            print(f"  REFUSED {refusal}")
        for skipped in plan.generated_skipped:
            print(f"  SKIPPED generated {skipped}")
        for revision in plan.stranded_export_trees:
            print(f"  STRANDS generated export tree {plan.modelo}/{revision}")
        for catalogue, counts in sorted(locale_mentions(plan.rename_map).items()):
            print(
                f"  LOCALE {catalogue} names {len(counts)} renamed ids; move them with "
                f"`uv run --no-sync python -m dev.locales set-batch <manifest>`"
            )

    if write:
        for plan in family_plans:
            try:
                touched, hits = apply_family_collapse(
                    plan, export_republish_acknowledged=args.export_republish_acknowledged
                )
            except GeneratedExportTreeStaleError as exc:
                print(f"Refusing to apply {plan.modelo}: {exc}", file=sys.stderr)
                return 1
            print(
                f"Family collapse {plan.modelo}: {len(plan.renames)} identifiers renamed, "
                f"{hits} references rewritten, {len(touched)} files touched"
            )

    if write:
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
        files_touched = apply_renames(measurements) if not selected_families else {}
        total_files = sum(files_touched.values())
        print(f"Applied renames across {total_files} files in {len(files_touched)} modelos.")
        for modelo, count in sorted(files_touched.items()):
            renamed = len(measurements[modelo].renames)
            print(f"  {modelo}: {renamed} identifiers renamed, {count} files touched")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
