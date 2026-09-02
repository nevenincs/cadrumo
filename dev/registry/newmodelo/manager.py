"""Scaffold the skeleton registry authoring tree for a new modelo revision.

Generates the standard per-modelo, per-revision directory layout the loader
(:mod:`cadrumo.domain.calculations.registry`) expects in *directory mode*:
``manifest.toml`` at the modelo root, and ``revisions/<revision-id>/`` holding
``revision.toml`` plus one fragment subdirectory per registry section
(casillas, formulas, bindings, completeness_manifest, verification_expectations,
export_layouts, extraction_profiles, application_links).

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
from dataclasses import dataclass, field
from pathlib import Path

from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.domain.calculations.registry.modelo_localization import (
    modelo_locale_key,
    revision_locale_key,
)

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
_SECTION_DIRECTORIES: tuple[str, ...] = (
    "casillas",
    "formulas",
    "bindings",
    "completeness_manifest",
    "verification_expectations",
    "export_layouts",
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


def _revision_toml(modelo_id: str, revision_id: str) -> str:
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
        "valid_from = 2026-01-01  # TODO: real applicability start date\n"
        "# valid_to = 2026-12-31  # TODO: uncomment + set if this revision has a known end\n"
        'period_selector = { year_from = 2026, periods = ["0A"] }  # TODO\n'
        "legal_refs = []  # TODO\n"
        "source_refs = []  # TODO\n"
        "# Mandatory: cite the Orden(es) ministeriales that approve or amend this\n"
        "# revision's form.\n"
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


_SECTION_CHECKLIST_HINTS: dict[str, str] = {
    "casillas": "author every casilla with legal grounding (checklist item 3).",
    "formulas": "author formulas for every computed casilla (checklist item 4).",
    "bindings": "author bindings for every data-sourced casilla (checklist item 5).",
    "completeness_manifest": "close the calculation-completeness manifest (checklist item 6).",
    "verification_expectations": "author verification expectations and predicates (checklist item 7).",
    "export_layouts": "register the export layout(s) (checklist item 8).",
    "extraction_profiles": "register an extraction profile, if applicable (checklist item 9).",
    "application_links": "declare any cross-modelo application links this revision depends on.",
}


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

        entries: list[ScaffoldPlanEntry] = [
            ScaffoldPlanEntry(Path("manifest.toml"), _manifest_toml(modelo_id, resolved_title)),
            ScaffoldPlanEntry(
                Path("revisions") / revision_id / "revision.toml",
                _revision_toml(modelo_id, revision_id),
            ),
        ]
        for section in _SECTION_DIRECTORIES:
            hint = _SECTION_CHECKLIST_HINTS[section]
            entries.append(
                ScaffoldPlanEntry(
                    Path("revisions") / revision_id / section / f"0001-{section}.toml",
                    _section_fragment_toml(revision_id, section, hint),
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
