"""Scaffold the skeleton registry authoring tree for a new modelo revision.

Generates the standard per-modelo, per-revision directory layout the loader
(:mod:`cadrumo.domain.calculations.registry`) expects in *directory mode*:
``manifest.toml`` at the modelo root, and ``revisions/<revision-id>/`` holding
``revision.toml`` plus one fragment subdirectory per registry section
(casillas, formulas, bindings, completeness_manifest, verification_expectations,
extraction_profiles, application_links).

The emitted skeleton is *edition-delta shaped*. An edition declares its defaults
once in ``revision.toml`` — the ``predecessor`` it is authored relative to, and
the ``casilla_source_refs`` the loader fills into every row stating none — so a
scaffolded row restates neither, and carries no edition year in the identifiers
it names. That is the shape the corpus is authored in; a scaffold that proposed
the full-copy shape instead taught every new edition to restate what its edition
already says, one row at a time.

The scaffolded tree is a *skeleton*: every section fragment starts empty (a
commented placeholder, since registry section fields default to ``()``/``None``
and the loader tolerates an absent or empty fragment file). The tree does not
validate as calc-grade on its own — a contributor fills in the regulated
content named by the contributor checklist in
:mod:`dev.registry.newmodelo.checklist`. ``scaffold(..., check=True)`` never
writes; it reports whether the expected skeleton exists.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import cast

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.domain.calculations.registry.modelo_localization import (
    modelo_locale_key,
    revision_locale_key,
)

from ..conformance.manager import reset_conformance_cache

__all__ = [
    "NewModeloError",
    "NewModeloScaffoldManager",
    "ScaffoldPlanEntry",
    "ScaffoldResult",
]

_UTF_8 = UTF_8_ENCODING
_MODELO_ID_RE = re.compile(r"^\d{3}$")
_REVISION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]*[a-z0-9]$|^[a-z0-9]$")

# One fragment subdirectory per ModeloRevision registry section that a new
# modelo revision is expected to populate. Kept as an explicit ordered tuple
# (rather than derived from the runtime schema) because the scaffold's
# authorship order mirrors the contributor checklist, not the schema's
# internal field order; a schema field with no scaffolded fragment directory
# (e.g. `parameters`) is optional and only needed by a
# subset of modelos, so it is not force-created by default.
#
# The export tree is deliberately ABSENT. A hand-authored fixed-width layout is
# a transcription of the official record design, and a scaffold that creates the
# directory makes transcription the path of least resistance: the authored export
# surface grew back faster than it was migrated, one new revision at a time. The
# supported path is to author the generator inputs -- the semantic map and the
# render profile -- and let the export tree be GENERATED from the design, so a
# shipped field can be traced to the row it came from. Hand-authoring remains
# possible and is now the declared exception, which checklist item 8 states.
#
# When that tree is generated it lands at `export/`, the directory name the
# loader maps onto the `export_layouts` schema section. `export_layouts/` is the
# displaced directory spelling; nothing this scaffold emits or names proposes it.
_SECTION_DIRECTORIES: tuple[str, ...] = (
    "casillas",
    "formulas",
    "bindings",
    "completeness_manifest",
    "verification_expectations",
    "extraction_profiles",
    "application_links",
)


class NewModeloError(RuntimeError):
    """Raised when a new-modelo scaffold cannot be planned or written."""


@dataclass(frozen=True, slots=True)
class ScaffoldPlanEntry:
    """One file the scaffold would write, relative to the modelo directory.

    Attributes:
        relative_path: Path relative to the modelo root directory
            (``src/cadrumo/_data/registry/aeat/modelos/<modelo_id>/``).
        content: The exact file content the scaffold would write.
    """

    relative_path: Path
    content: str


@dataclass(frozen=True, slots=True)
class ScaffoldResult:
    """Summary of a scaffold (or ``--check``) run.

    Attributes:
        modelo_id: The three-digit modelo identifier scaffolded.
        revision_id: The revision identifier scaffolded.
        modelo_root: Absolute path to the modelo's registry directory.
        written: Relative paths of files newly written (empty on ``--check``).
        already_present: Relative paths that already existed (left untouched).
        missing: Relative paths the skeleton expects but that do not exist yet
            (only populated in ``--check`` / drift-only mode).
    """

    modelo_id: str
    revision_id: str
    modelo_root: Path
    written: tuple[Path, ...] = ()
    already_present: tuple[Path, ...] = ()
    missing: tuple[Path, ...] = field(default_factory=tuple)

    @property
    def is_conformant(self) -> bool:
        """Return whether the expected skeleton is fully present (used by ``--check``)."""
        return not self.missing


def _validate_modelo_id(modelo_id: str) -> None:
    if not _MODELO_ID_RE.match(modelo_id):
        raise NewModeloError(f"{modelo_id!r}: modelo id must be exactly three digits, e.g. '410'")


def _validate_revision_id(revision_id: str) -> None:
    if not _REVISION_ID_RE.match(revision_id):
        raise NewModeloError(
            f"{revision_id!r}: revision id must be a lowercase kebab-style ref, e.g. '2026-y-siguientes'",
        )


# First line of every scaffolded manifest.toml. Used as the sole signal that an
# existing manifest.toml on disk was authored by this scaffold (and is
# therefore safe to leave alone / overwrite with --force) rather than being
# real, already-modelled registry content this scaffold must never graft onto.
_SCAFFOLDED_MANIFEST_SENTINEL = "# Scaffolded modelo manifest —"


def _manifest_toml(modelo_id: str, title: str) -> str:
    return (
        f"{_SCAFFOLDED_MANIFEST_SENTINEL} TODO fill in per the contributor checklist\n"
        "# (python -m dev.registry.newmodelo checklist), item 1: 'Declare the modelo manifest'.\n"
        "#\n"
        "# Presentation text is NOT declared here. A modelo's title and official name are\n"
        "# localizable values owned by the shared locale catalogues, and the schema rejects\n"
        "# them as unknown fields. Author them against the derived keys instead:\n"
        f'#   python -m dev.locales set es {modelo_locale_key(modelo_id, "title")} "{title}"\n'
        f"#   python -m dev.locales set es {modelo_locale_key(modelo_id, 'official_name')} "
        f'"TODO: official AEAT modelo {modelo_id} name"\n'
        "# Spanish is source-authoritative and load-blocking; repeat for en, ca and hu.\n"
        "[modelo]\n"
        f'id = "{modelo_id}"\n'
        '# tax_domain: one of "iva" | "irpf" | "sociedades" | "informative" | ... (see TaxDomain)\n'
        'tax_domain = "TODO"\n'
        '# cadence: "monthly" | "quarterly" | "annual" | "ad_hoc" | "profile_based"\n'
        'cadence = "TODO"\n'
        'jurisdiction = "ES-AEAT"\n'
        "legal_refs = []  # TODO: legal catalogue ids grounding this modelo's authority\n"
        "source_refs = []  # TODO: source catalogue ids (AEAT procedure / Diseño refs)\n"
    )


def _predecessor_block(predecessor: str | None) -> str:
    """Render the ``predecessor`` declaration, or the note that stands in for it.

    A first edition declares no predecessor at all: absence is the grounded
    statement that this edition copies from no sibling, and a placeholder key
    naming nothing would be a claim the scaffold cannot make.
    """
    if predecessor is None:
        return (
            "# No `predecessor` key: this modelo has no earlier edition on disk, so this\n"
            "# edition states every row itself. An edition that DOES follow a sibling must\n"
            "# declare it, or the delta shape reads as a full copy.\n"
        )
    return (
        "# The latest edition of this modelo already on disk, offered as this edition's\n"
        "# predecessor. TODO: confirm it is the edition this form actually succeeds --\n"
        "# the delta is read against whatever is named here.\n"
        f'predecessor = "{predecessor}"\n'
    )


def _revision_toml(modelo_id: str, revision_id: str, predecessor: str | None) -> str:
    return (
        f'# Scaffolded revision metadata for modelo {modelo_id}, revision "{revision_id}".\n'
        "# TODO fill in per the contributor checklist, item 2: 'Ground the revision window\n"
        "# and applicability'.\n"
        "#\n"
        "# The revision label is a localizable value owned by the shared locale catalogues,\n"
        "# not a schema field; the loader rejects it here. Author it against the derived key:\n"
        f"#   python -m dev.locales set es {revision_locale_key(modelo_id, revision_id)} "
        f'"TODO: human-readable label for revision {revision_id}"\n'
        f'[revisions."{revision_id}"]\n'
        f"{_predecessor_block(predecessor)}"
        "valid_from = 2026-01-01  # TODO: real applicability start date\n"
        "# valid_to = 2026-12-31  # TODO: uncomment + set if this revision has a known end\n"
        'period_selector = { year_from = 2026, periods = ["0A"] }  # TODO\n'
        "legal_refs = []  # TODO\n"
        "source_refs = []  # TODO\n"
        "# The edition's DEFAULT source grounding for its casilla rows, declared once here\n"
        "# instead of on every row: the loader fills it into each row, and each row's\n"
        "# constraints table, that states no source_refs of its own. A row citing something\n"
        "# the default lacks adds it with `additional_source_refs`, never by restating this.\n"
        "casilla_source_refs = []  # TODO\n"
        "# Mandatory: cite the Orden(es) ministeriales that approve or amend this\n"
        "# revision's form. These also fill the legal_refs of every row stating none, so a\n"
        "# row restating exactly this list states nothing the edition has not said already.\n"
        "orden_aplicabilidad = []  # TODO\n"
    )


def _section_fragment_toml(revision_id: str, section: str, checklist_hint: str) -> str:
    return (
        f'# Scaffolded "{section}" fragment for revision "{revision_id}".\n'
        f"# TODO: {checklist_hint}\n"
        "#\n"
        f'# [[revisions."{revision_id}".{section}]]\n'
        '# id = "..."\n'
        "# ...\n"
    )


def _casillas_fragment_toml(modelo_id: str, revision_id: str, checklist_hint: str) -> str:
    """Render the casillas fragment as a delta-shaped exemplar row.

    The commented row is the whole point of this renderer. A generic
    ``id = "..."`` stub says nothing about what a row may leave out, and the
    three restatements below are the ones the corpus had to be migrated out
    of afterwards -- each one individually valid, and each one saying again
    what the edition manifest already said once.
    """
    return (
        f'# Scaffolded "casillas" fragment for revision "{revision_id}".\n'
        f"# TODO: {checklist_hint}\n"
        "#\n"
        "# Rows are authored in EDITION-DELTA shape. The edition manifest states its\n"
        "# defaults once, so a row states only what is true of the box and not of the\n"
        "# edition:\n"
        "#   - no `source_refs` equal to the edition's `casilla_source_refs`. A box whose\n"
        "#     concept cites more than the default adds only the difference, through\n"
        "#     `additional_source_refs`.\n"
        "#   - no `legal_refs` equal to the edition's `orden_aplicabilidad`. Cite the\n"
        "#     specific provision that establishes THIS box, or state none and inherit.\n"
        "#   - no edition year inside an identifier. A formula or binding id names what it\n"
        f'#     computes, not when: "modelo-{modelo_id}-iva-resultado-final", never\n'
        f'#     "modelo-{modelo_id}-{revision_id}-iva-resultado-final". A row inherited by a\n'
        "#     later edition keeps the id it was authored with, and a dated id would have\n"
        "#     to be rewritten -- or would quietly claim to belong to the wrong edition.\n"
        "#\n"
        f'# [[revisions."{revision_id}".casillas]]\n'
        '# id = "..."\n'
        '# continuidad_id = "..."\n'
        '# number = "..."\n'
        '# data_type = "money"\n'
        '# input_kind = "computed"\n'
        f'# formula = "modelo-{modelo_id}-..."\n'
        '# additional_source_refs = ["..."]  # only what the edition default does not cover\n'
    )


_SECTION_CHECKLIST_HINTS: dict[str, str] = {
    "casillas": "author every casilla with legal grounding (checklist item 3).",
    "formulas": (
        "author formulas for every computed casilla (checklist item 4); id them by what "
        "they compute, with no edition year inside the id."
    ),
    "bindings": (
        "author bindings for every data-sourced casilla (checklist item 5); id them by "
        "what they bind, with no edition year inside the id."
    ),
    "completeness_manifest": "close the calculation-completeness manifest (checklist item 6).",
    "verification_expectations": "author verification expectations and predicates (checklist item 7).",
    "extraction_profiles": "register an extraction profile, if applicable (checklist item 9).",
    "application_links": "declare any cross-modelo application links this revision depends on.",
}


def _as_toml_table(value: object) -> dict[str, object] | None:
    """Narrow a parsed TOML value to a string-keyed table, or ``None``."""
    if not isinstance(value, dict):
        return None
    if any(not isinstance(key, str) for key in cast("dict[object, object]", value)):
        return None
    return cast("dict[str, object]", value)


def _declared_valid_from(revision_root: Path) -> date | None:
    """Return the ``valid_from`` an existing edition on disk declares, if readable.

    Returns ``None`` for anything this scaffold cannot read as a dated edition
    -- an absent or malformed ``revision.toml``, a fragment-only directory, an
    ambiguous set of revision tables -- so an unreadable sibling is never
    offered as a predecessor on the strength of its directory name alone.
    """
    manifest = revision_root / "revision.toml"
    if not manifest.is_file():
        return None
    try:
        document = tomllib.loads(manifest.read_text(encoding=_UTF_8))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    editions = _as_toml_table(document.get("revisions"))
    if editions is None:
        return None
    table = _as_toml_table(editions.get(revision_root.name))
    if table is None:
        if len(editions) != 1:
            return None
        table = _as_toml_table(next(iter(editions.values())))
        if table is None:
            return None
    declared = table.get("valid_from")
    return declared if isinstance(declared, date) else None


def _latest_existing_edition(modelo_root: Path, revision_id: str) -> str | None:
    """Return the modelo's latest edition already on disk, excluding *revision_id*.

    "Latest" is decided by declared ``valid_from``, never by directory order:
    the corpus's own predecessor chains run in date order, and revision ids
    such as ``2024-hasta-08-y-2t`` and ``2024-desde-09-y-3t`` sort against that
    order rather than with it. Ties fall back to the revision id so the answer
    is deterministic. ``revision_id`` itself is excluded, so re-running the
    scaffold over an already-written edition does not offer it its own name.
    """
    revisions_root = modelo_root / "revisions"
    if not revisions_root.is_dir():
        return None
    dated = [
        (valid_from, child.name)
        for child in scan_directory(revisions_root, select=DirectoryEntryKind.DIRECTORIES)
        if child.name != revision_id and (valid_from := _declared_valid_from(child)) is not None
    ]
    if not dated:
        return None
    return max(dated)[1]


class NewModeloScaffoldManager:
    """Plan and write the skeleton registry directory tree for a new modelo revision."""

    def __init__(self, registry_modelos_root: Path) -> None:
        """Initialise the manager with the registry modelos root directory.

        Args:
            registry_modelos_root: Absolute path to
                ``src/cadrumo/_data/registry/aeat/modelos/``.
        """
        self.registry_modelos_root = registry_modelos_root

    def modelo_root(self, modelo_id: str) -> Path:
        """Return the absolute directory a modelo's registry tree lives under."""
        return self.registry_modelos_root / modelo_id

    @staticmethod
    def _refuse_foreign_manifest(root: Path, plan: tuple[ScaffoldPlanEntry, ...]) -> None:
        """Refuse to scaffold onto a modelo directory whose manifest is not ours.

        A ``manifest.toml`` that exists but does not start with this
        scaffold's own sentinel line is real, already-modelled registry
        content (or foreign content of unknown origin); writing revision
        fragments alongside it would silently graft a skeleton revision onto
        a live modelo. Only ``force=True`` may bypass this.

        Raises:
            NewModeloError: If a foreign ``manifest.toml`` is present.
        """
        manifest_entry = next(entry for entry in plan if entry.relative_path == Path("manifest.toml"))
        manifest_path = root / manifest_entry.relative_path
        if not manifest_path.is_file():
            return
        existing = manifest_path.read_text(encoding=_UTF_8)
        if not existing.startswith(_SCAFFOLDED_MANIFEST_SENTINEL):
            raise NewModeloError(
                f"{root}: manifest.toml already exists and was not written by this scaffold "
                "(it looks like real registry content); refusing to add a revision skeleton "
                "onto it. Pass force=True / --force only if you are certain this is intended.",
            )

    def plan(self, modelo_id: str, revision_id: str, *, title: str | None = None) -> tuple[ScaffoldPlanEntry, ...]:
        """Compute the full skeleton file plan without writing anything.

        Reads the modelo's existing editions to offer the newest of them as the
        new edition's ``predecessor``; a modelo with no earlier edition on disk
        is planned with no ``predecessor`` key at all. The read is the only way
        the plan touches the filesystem, and it writes nothing.

        Returns:
            An ordered tuple of :class:`ScaffoldPlanEntry`, each naming a
            path relative to the modelo root plus its exact placeholder content.

        Raises:
            NewModeloError: If ``modelo_id`` or ``revision_id`` fail their
                registry identifier shape (mirrors ``ModeloId``/``RevisionId``).
        """
        _validate_modelo_id(modelo_id)
        _validate_revision_id(revision_id)
        resolved_title = title or f"TODO: title for modelo {modelo_id}"
        predecessor = _latest_existing_edition(self.modelo_root(modelo_id), revision_id)

        entries: list[ScaffoldPlanEntry] = [
            ScaffoldPlanEntry(Path("manifest.toml"), _manifest_toml(modelo_id, resolved_title)),
            ScaffoldPlanEntry(
                Path("revisions") / revision_id / "revision.toml",
                _revision_toml(modelo_id, revision_id, predecessor),
            ),
        ]
        for section in _SECTION_DIRECTORIES:
            hint = _SECTION_CHECKLIST_HINTS[section]
            content = (
                _casillas_fragment_toml(modelo_id, revision_id, hint)
                if section == "casillas"
                else _section_fragment_toml(revision_id, section, hint)
            )
            entries.append(
                ScaffoldPlanEntry(
                    Path("revisions") / revision_id / section / f"0001-{section.replace('_', '-')}.toml",
                    content,
                ),
            )
        return tuple(entries)

    def scaffold(
        self,
        modelo_id: str,
        revision_id: str,
        *,
        title: str | None = None,
        force: bool = False,
    ) -> ScaffoldResult:
        """Write the skeleton registry tree for a new modelo revision.

        Idempotent for a *repeated scaffold of the same modelo*: re-running
        with the same ids leaves existing files untouched (reported in
        ``already_present``) unless ``force=True``, which overwrites every
        planned file with the canonical placeholder content.

        Refuses (unless ``force=True``) to scaffold a *new* revision onto a
        modelo directory that already carries an unrelated ``manifest.toml``
        this exact scaffold did not author (e.g. a real, already-modelled
        modelo such as ``100``) — this is the guard that stops a mistyped
        modelo id from grafting a skeleton revision onto live registry
        content instead of failing loudly.

        Returns:
            A :class:`ScaffoldResult` summarising what was written.

        Raises:
            NewModeloError: If the ids are malformed, if the modelo root
                already exists as a file (not a directory), or if the modelo
                root already carries a manifest this scaffold run does not
                own (only bypassed with ``force=True``).
        """
        plan = self.plan(modelo_id, revision_id, title=title)
        root = self.modelo_root(modelo_id)
        if root.exists() and not root.is_dir():
            raise NewModeloError(f"{root}: exists and is not a directory")
        if not force:
            self._refuse_foreign_manifest(root, plan)

        written: list[Path] = []
        already_present: list[Path] = []
        for entry in plan:
            target = root / entry.relative_path
            if target.is_file() and not force:
                already_present.append(entry.relative_path)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(entry.content, encoding=_UTF_8, newline="\n")
            written.append(entry.relative_path)

        if written:
            # The conformance snapshot cache is keyed only on `validate`, never
            # on registry source state, so it cannot notice this write on its
            # own; a scaffold-then-audit call in one process would otherwise
            # see the pre-scaffold profile. See reset_conformance_cache.
            reset_conformance_cache()

        return ScaffoldResult(
            modelo_id=modelo_id,
            revision_id=revision_id,
            modelo_root=root,
            written=tuple(written),
            already_present=tuple(already_present),
        )

    def check(self, modelo_id: str, revision_id: str, *, title: str | None = None) -> ScaffoldResult:
        """Report which skeleton files are missing without writing anything.

        Returns:
            A :class:`ScaffoldResult` whose ``missing`` field lists every
            planned relative path that does not yet exist on disk;
            :attr:`ScaffoldResult.is_conformant` is ``True`` when the full
            skeleton is already present.
        """
        plan = self.plan(modelo_id, revision_id, title=title)
        root = self.modelo_root(modelo_id)

        present: list[Path] = []
        missing: list[Path] = []
        for entry in plan:
            target = root / entry.relative_path
            if target.is_file():
                present.append(entry.relative_path)
            else:
                missing.append(entry.relative_path)

        return ScaffoldResult(
            modelo_id=modelo_id,
            revision_id=revision_id,
            modelo_root=root,
            already_present=tuple(present),
            missing=tuple(missing),
        )
