"""Gate: a registry declaration authored in one edition only needs a cited official difference.

A declaration (casilla, formula, binding, parameter, ...) that the hydrated
registry carries in exactly one of a modelo's editions inside the supported
filing years is either a genuine official difference or an authoring accident:
the law applied across several years but was written into one edition. The
registry has no field that marks "this difference is official"; the audit
therefore reads the citation the declaration already carries.

A casilla that carries no formula or binding is a printed input box: its
existence in an edition is the official form design itself, so only casillas
that calculate are audited. Deadline windows are dated per period by nature and
are outside this audit.

A singleton is cited when both of its boundaries are explained:

* appearing: some cited legal reference came into force after the preceding
  edition began and no later than the end of this edition. A casilla may
  instead state the boundary through its continuity origin (new on the form,
  with evidence), or be the grounded continuation of a preceding-edition
  casilla renumbered by the form.
* disappearing: some cited legal reference expired within this edition. A
  casilla may instead be explicitly removed by the following edition, or
  continue under another number there (same grounded continuity identity).

The first edition in scope has no appearing boundary and the last has no
disappearing one. Years come only from the registry support envelope.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
from cadrumo.domain.calculations.registry.snapshot_globals import SupportedFilingYearsCatalogue

from .edition_member_continuity import CasillaFact, casilla_facts

__all__ = (
    "DeclarationView",
    "EditionSingletonFinding",
    "EditionView",
    "LegalWindow",
    "singleton_findings",
)

_SCOPED_FAMILIES: tuple[str, ...] = (
    "casillas",
    "formulas",
    "bindings",
    "parameters",
    "applicability",
    "constructs",
    "verification_predicates",
    "application_links",
)
_CASILLA_FAMILY = "casillas"
_NEW_ON_FORM_ORIGINS = frozenset({CasillaLineageOrigin.NEW_ON_FORM, CasillaLineageOrigin.NOT_ON_FORM})
_DECLARED_ID = re.compile(r'^\s*id\s*=\s*"([^"]+)"', re.MULTILINE)


@dataclass(frozen=True, slots=True)
class LegalWindow:
    """The effectivity window of one legal reference a declaration cites."""

    ref_id: str
    effective_from: date
    effective_to: date | None


@dataclass(frozen=True, slots=True)
class DeclarationView:
    """The facts about one hydrated declaration the singleton audit reads."""

    family: str
    declaration_id: str
    legal_windows: tuple[LegalWindow, ...]
    states_new_on_form: bool = False
    removed_by_next_edition: bool = False
    calculated: bool = True
    grounded_continuidad_id: str | None = None


@dataclass(frozen=True, slots=True)
class EditionView:
    """One edition of a modelo with its declarations."""

    edition: str
    valid_from: date
    valid_to: date | None
    declarations: tuple[DeclarationView, ...]
    track: tuple[str, ...] = ()
    casillas: Mapping[str, CasillaFact] = field(default_factory=dict[str, CasillaFact])


@dataclass(frozen=True, slots=True)
class EditionSingletonFinding:
    """A declaration present in exactly one edition without a cited difference."""

    modelo: str
    family: str
    declaration_id: str
    edition: str
    appearing_cited: bool
    disappearing_cited: bool
    path: str = ""

    @property
    def key(self) -> str:
        """Return the stable baseline key."""
        return f"edition-only|{self.modelo}|{self.family}|{self.declaration_id}|{self.edition}|{self.reason}"

    @property
    def reason(self) -> str:
        """Name which boundary lacks a cited difference."""
        missing = [
            name
            for name, cited in (("appearing", self.appearing_cited), ("disappearing", self.disappearing_cited))
            if not cited
        ]
        return "uncited " + " and ".join(missing) + " boundary"


def _renumbered_in(declaration: DeclarationView, edition: EditionView | None) -> bool:
    """Whether the neighbouring edition carries this declaration's grounded continuation under another number."""
    if edition is None or declaration.grounded_continuidad_id is None:
        return False
    return any(
        other.family == declaration.family
        and other.declaration_id != declaration.declaration_id
        and other.grounded_continuidad_id == declaration.grounded_continuidad_id
        for other in edition.declarations
    )


def _window_opens(declaration: DeclarationView, previous: EditionView, edition: EditionView) -> bool:
    return any(
        previous.valid_from < window.effective_from
        and (edition.valid_to is None or window.effective_from <= edition.valid_to)
        for window in declaration.legal_windows
    )


def _window_closes(declaration: DeclarationView, following: EditionView, edition: EditionView) -> bool:
    return any(
        window.effective_to is not None and edition.valid_from <= window.effective_to < following.valid_from
        for window in declaration.legal_windows
    )


def _appearing_cited(declaration: DeclarationView, previous: EditionView | None, edition: EditionView) -> bool:
    if previous is None:
        return True
    if declaration.family == _CASILLA_FAMILY and declaration.states_new_on_form:
        return True
    return _renumbered_in(declaration, previous) or _window_opens(declaration, previous, edition)


def _disappearing_cited(declaration: DeclarationView, following: EditionView | None, edition: EditionView) -> bool:
    if following is None:
        return True
    if declaration.family == _CASILLA_FAMILY and declaration.removed_by_next_edition:
        return True
    return _renumbered_in(declaration, following) or _window_closes(declaration, following, edition)


def _presence(editions: Sequence[EditionView]) -> dict[tuple[str, str], list[int]]:
    seen: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, edition in enumerate(editions):
        for declaration in edition.declarations:
            seen[(declaration.family, declaration.declaration_id)].append(index)
    return seen


def _single_finding(
    modelo: str, editions: Sequence[EditionView], key: tuple[str, str], index: int
) -> EditionSingletonFinding | None:
    family, declaration_id = key
    edition = editions[index]
    declaration = next(
        item for item in edition.declarations if item.family == family and item.declaration_id == declaration_id
    )
    if not declaration.calculated:
        return None
    previous = editions[index - 1] if index > 0 else None
    following = editions[index + 1] if index + 1 < len(editions) else None
    appearing = _appearing_cited(declaration, previous, edition)
    disappearing = _disappearing_cited(declaration, following, edition)
    if appearing and disappearing:
        return None
    return EditionSingletonFinding(modelo, family, declaration_id, edition.edition, appearing, disappearing)


def singleton_findings(modelo: str, editions: Sequence[EditionView]) -> tuple[EditionSingletonFinding, ...]:
    """Return every uncited single-edition declaration of one modelo.

    Editions are compared within a track: editions that print the same periods.
    Editions of different period tracks are parallel schemes, not successive
    versions of one form, so one's absence from another says nothing.
    """
    tracks: dict[tuple[str, ...], list[EditionView]] = defaultdict(list)
    for edition in editions:
        tracks[edition.track].append(edition)
    return tuple(
        sorted(
            (finding for group in tracks.values() for finding in _track_findings(modelo, group)),
            key=lambda item: (item.family, item.edition, item.declaration_id),
        )
    )


def _track_findings(modelo: str, editions: Sequence[EditionView]) -> tuple[EditionSingletonFinding, ...]:
    if len(editions) < 2:
        return ()
    found = (
        _single_finding(modelo, editions, key, indexes[0])
        for key, indexes in _presence(editions).items()
        if len(indexes) == 1
    )
    return tuple(
        sorted(
            (item for item in found if item is not None),
            key=lambda item: (item.family, item.edition, item.declaration_id),
        )
    )


def _legal_windows(refs: Iterable[str], catalogues: RegistryCatalogues) -> tuple[LegalWindow, ...]:
    windows: list[LegalWindow] = []
    for ref in refs:
        legal = catalogues.legal.get(ref)
        if legal is not None:
            windows.append(LegalWindow(str(ref), legal.effective_from, legal.effective_to))
    return tuple(windows)


def _carries_calculation(casilla: object) -> bool:
    return bool(
        getattr(casilla, "formula", None)
        or getattr(casilla, "binding", None)
        or getattr(casilla, "alternate_bindings", ())
    )


def _grounded_continuidad_id(origin: object, item: object) -> str | None:
    continuidad_id = getattr(item, "continuidad_id", None)
    if origin is CasillaLineageOrigin.GROUNDED and continuidad_id is not None:
        return str(continuidad_id)
    return None


def _declaration_view(
    family: str, item: object, catalogues: RegistryCatalogues, removed: frozenset[str]
) -> DeclarationView | None:
    declaration_id = getattr(item, "id", None)
    if declaration_id is None:
        return None
    origin = getattr(item, "continuidad_origin", None)
    return DeclarationView(
        family=family,
        declaration_id=str(declaration_id),
        legal_windows=_legal_windows(getattr(item, "legal_refs", ()), catalogues),
        states_new_on_form=origin in _NEW_ON_FORM_ORIGINS and bool(getattr(item, "continuidad_evidence", None)),
        removed_by_next_edition=family == _CASILLA_FAMILY and str(declaration_id) in removed,
        calculated=family != _CASILLA_FAMILY or _carries_calculation(item),
        grounded_continuidad_id=_grounded_continuidad_id(origin, item),
    )


def _removed_by(revision: ModeloRevision | None, predecessor_id: str) -> frozenset[str]:
    if revision is None:
        return frozenset[str]()
    return frozenset(
        str(removal.selector.id) for removal in revision.casilla_removals if removal.selector.revision == predecessor_id
    )


def _period_track(revision: ModeloRevision) -> tuple[str, ...]:
    return tuple(sorted(revision.period_selector.periods))


def _edition_view(
    revision: ModeloRevision, following: ModeloRevision | None, catalogues: RegistryCatalogues
) -> EditionView:
    removed = _removed_by(following, str(revision.id))
    views = (
        _declaration_view(family, item, catalogues, removed)
        for family in _SCOPED_FAMILIES
        for item in getattr(revision, family, ())
    )
    return EditionView(
        edition=str(revision.id),
        valid_from=revision.valid_from,
        valid_to=revision.valid_to,
        declarations=tuple(view for view in views if view is not None),
        track=_period_track(revision),
        casillas=casilla_facts(revision),
    )


def editions_in_support(
    definition: ModeloDefinition, catalogues: RegistryCatalogues, support: SupportedFilingYearsCatalogue
) -> tuple[EditionView, ...]:
    """Project a hydrated modelo's editions that reach the supported filing years."""
    floor = support.date_envelope().floor
    revisions = tuple(ordered_revisions(definition))
    return tuple(
        _edition_view(revision, revisions[index + 1] if index + 1 < len(revisions) else None, catalogues)
        for index, revision in enumerate(revisions)
        if revision.valid_to is None or revision.valid_to >= floor
    )


def _declaration_files(family_dir: Path) -> Mapping[str, str]:
    located: dict[str, str] = {}
    if not family_dir.is_dir():
        return located
    for path in sorted(family_dir.rglob("*.toml")):
        for match in _DECLARED_ID.finditer(path.read_text(encoding="utf-8")):
            located.setdefault(match.group(1), path.as_posix())
    return located


def with_paths(findings: Sequence[EditionSingletonFinding], modelos_root: Path) -> tuple[EditionSingletonFinding, ...]:
    """Attach the authored file declaring each finding, or its edition directory."""
    cache: dict[tuple[str, str, str], Mapping[str, str]] = {}
    located: list[EditionSingletonFinding] = []
    for finding in findings:
        edition_dir = modelos_root / finding.modelo / "revisions" / finding.edition
        key = (finding.modelo, finding.edition, finding.family)
        if key not in cache:
            cache[key] = _declaration_files(edition_dir / finding.family)
        path = cache[key].get(finding.declaration_id, edition_dir.as_posix())
        located.append(
            EditionSingletonFinding(
                finding.modelo,
                finding.family,
                finding.declaration_id,
                finding.edition,
                finding.appearing_cited,
                finding.disappearing_cited,
                path,
            )
        )
    return tuple(located)


def audit_registry(
    modelos: Iterable[ModeloDefinition], catalogues: RegistryCatalogues, modelos_root: Path
) -> tuple[EditionSingletonFinding, ...]:
    """Return the singleton findings of every modelo, with authored file paths."""
    support = catalogues.require_supported_filing_years()
    findings: list[EditionSingletonFinding] = []
    for definition in modelos:
        views = editions_in_support(definition, catalogues, support)
        findings.extend(singleton_findings(str(definition.id), views))
    return with_paths(findings, modelos_root)


def render_edition_findings(findings: Sequence[EditionSingletonFinding]) -> list[str]:
    """Render a count table and one line per finding."""
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for finding in findings:
        counts[(finding.modelo, finding.family)] += 1
    lines = [f"edition-only declarations without a cited difference: {len(findings)}"]
    lines.extend(f"  count modelo={modelo} family={family} n={n}" for (modelo, family), n in sorted(counts.items()))
    lines.extend(
        f"  {item.modelo} {item.family} {item.declaration_id} edition={item.edition} ({item.reason}) {item.path}"
        for item in findings
    )
    return lines
