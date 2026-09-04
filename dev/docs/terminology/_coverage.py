"""Corpus coverage report for the committed terminology relevance mapping.

This report answers a single question -- "measure, then widen, the query
vocabulary" -- of the shipped relevance mapping: of every target a build-time
sweep *could* resolve to, which ones have NO inbound entry in the committed
mapping? Those
uncovered targets are the widening backlog -- the casilla labels, legal
provisions, concept cards, and CLI surfaces a reader can reach in the product
but which no swept query term yet points at.

This module derives that answer deterministically. It materialises the four
enumerable target surfaces from the same authorities the product itself grounds
against -- the approved Handbook concept cards, the registry casilla
projections (through the validated authority, never raw TOML), the live CLI
projection, and the legal catalogue's provision vocabulary -- assigns each its
canonical search-record id (the exact id a sweep would emit, via the shared
:func:`~dev.docs.terminology.unified_record.to_search_record` funnel and the
canonical :func:`~dev.docs.terminology._legal_projection.legal_target_record_id`
helper), and
joins that derivable surface against the record ids the committed mapping
references. A target with no inbound reference is *uncovered*; a mapping target
that belongs to none of the four derivable surfaces (a doc-page or source-code
grounding surface, outside the enumerable four) is an *orphan mapping target*,
reported rather than crashed on.

The report carries per-kind totals, per-kind covered counts, and the ordered
list of uncovered ids per kind. It carries NO timestamp and NO machine path, so
two runs on two machines produce byte-identical JSON -- the determinism the
committed-artifact discipline requires.

The separate casilla census below measures deterministic projection contracts
that the relevance widening report cannot represent: exact target derivation,
the currently carried invariant definition, authored non-Spanish registry
locale entries, and sparse inbound relevance. It does not claim Pagefind or generated-site
runtime parity.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n import lookup_translation_entry
from cadrumo.domain.calculations.registry.authority import (
    ValidatedRegistryAuthority,
    bundled_authority,
)
from cadrumo.domain.calculations.registry.errors import RegistrySnapshotError

from ..._paths import UTF_8
from ._cli_projection import CliOptionRecord, CliSurfaceRecord, project_cli_search_records
from ._concept_cards import ConceptCardRecord, project_concept_cards
from ._legal_projection import legal_target_record_id
from ._miss_rate import load_committed_relevance
from ._sweep import SweepResult
from .casilla_projection import project_casilla_search_records
from .search_record import CasillaSearchRecord
from .unified_record import SearchRecord, to_search_record

__all__ = [
    "CasillaCoverageCensus",
    "CasillaCoverageKind",
    "CasillaSurfaceCoverage",
    "CoverageKind",
    "KindCoverage",
    "TerminologyCoverageReport",
    "compute_casilla_coverage_census",
    "compute_coverage_report",
    "coverage_report_path",
    "legal_provision_ids",
    "legal_target_record_id",
]

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_UTF_8: Final[str] = UTF_8
_NON_SPANISH_LOCALES: Final[tuple[str, ...]] = ("en", "ca", "hu")


class CoverageKind(StrEnum):
    """The four enumerable target surfaces a coverage report measures.

    ``legal`` is a distinct coverage axis because a legal target serialises
    into the unified index as a ``LEGAL``-kind record: it is derived from the
    legal catalogue's provision vocabulary, not from a page walk, so the report
    tracks it as its own surface.
    """

    CONCEPT = "concept"
    CASILLA = "casilla"
    CLI = "cli"
    LEGAL = "legal"


class CasillaCoverageKind(StrEnum):
    """The deterministic casilla surfaces measured by the coverage census.

    ``projected`` is the deduplicated casilla surface produced by the registry
    projection. The other surfaces are subsets of that same record identity:
    ``exact-target`` observes the canonical unified-record destination,
    ``definition`` observes the Spanish invariant description currently carried
    by the projection, ``locale`` observes at least one authored non-Spanish
    registry label, and ``relevance`` observes an inbound reference in the
    committed sparse mapping.

    None of these values observes Pagefind or a generated HTML artefact. They
    are build-time data contracts only; runtime/index parity belongs to a later
    gate with an artefact it can actually inspect.
    """

    PROJECTED = "projected"
    EXACT_TARGET = "exact-target"
    DEFINITION = "definition"
    LOCALE = "locale"
    RELEVANCE = "relevance"


class KindCoverage(BaseModel):
    """Coverage of one target surface by the committed relevance mapping.

    ``total`` is the size of the derivable surface for ``kind``; ``covered`` is
    how many of those record ids the mapping references; ``uncovered_ids`` is
    the deterministically-ordered list of derivable ids with no inbound mapping
    entry (the widening backlog for this surface).
    """

    model_config = _STRICT_FROZEN

    kind: CoverageKind
    total: int = Field(ge=0)
    covered: int = Field(ge=0)
    uncovered_ids: tuple[str, ...] = ()

    @property
    def coverage_fraction(self) -> float:
        """Fraction of the derivable surface with an inbound mapping entry.

        An empty surface (``total == 0``) is fully covered by convention: there
        is nothing left to widen toward.
        """
        if self.total == 0:
            return 1.0
        return self.covered / self.total


class CasillaSurfaceCoverage(BaseModel):
    """Coverage of one casilla contract surface over projected record ids.

    ``total`` is always the projected casilla denominator. ``covered`` is the
    number of projected ids satisfying ``surface`` and ``uncovered_ids`` is the
    sorted deterministic remainder. The ``projected`` surface is represented
    as fully covered by definition, making the relationship between the
    projection denominator and every later contract explicit.
    """

    model_config = _STRICT_FROZEN

    surface: CasillaCoverageKind
    total: int = Field(ge=0)
    covered: int = Field(ge=0)
    uncovered_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _coverage_partition_is_valid(self) -> CasillaSurfaceCoverage:
        if self.covered > self.total:
            raise ValueError(f"casilla {self.surface.value} coverage cannot exceed total")
        if self.covered + len(self.uncovered_ids) != self.total:
            raise ValueError(
                f"casilla {self.surface.value} coverage must partition total into covered and uncovered_ids",
            )
        if len(self.uncovered_ids) != len(set(self.uncovered_ids)):
            raise ValueError(f"casilla {self.surface.value} uncovered_ids must be unique")
        if self.uncovered_ids != tuple(sorted(self.uncovered_ids)):
            raise ValueError(f"casilla {self.surface.value} uncovered_ids must be sorted")
        return self

    @property
    def coverage_fraction(self) -> float:
        """Fraction of projected records satisfying this surface contract."""
        if self.total == 0:
            return 1.0
        return self.covered / self.total


class CasillaCoverageCensus(BaseModel):
    """Deterministic coverage census for the projected casilla surface.

    This is deliberately separate from :class:`TerminologyCoverageReport`: the latter's
    relevance fields remain the widening report over all four enumerable
    target surfaces. This census adds the casilla-only contract axes needed by
    later parity work without changing that report's meaning.
    """

    model_config = _STRICT_FROZEN

    surfaces: tuple[CasillaSurfaceCoverage, ...] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def _surfaces_are_canonical(self) -> CasillaCoverageCensus:
        expected = tuple(CasillaCoverageKind)
        actual = tuple(entry.surface for entry in self.surfaces)
        if actual != expected:
            raise ValueError(
                "casilla coverage census surfaces must contain exactly the five "
                "CasillaCoverageKind entries in canonical order",
            )

        projected_total = self.surfaces[0].total
        if any(entry.total != projected_total for entry in self.surfaces[1:]):
            raise ValueError("casilla coverage census surfaces must share the projected denominator")
        return self

    def surface(self, surface: CasillaCoverageKind) -> CasillaSurfaceCoverage:
        """Return the coverage entry for one casilla surface."""
        for entry in self.surfaces:
            if entry.surface is surface:
                return entry
        raise KeyError(surface)


class TerminologyCoverageReport(BaseModel):
    """Corpus coverage of the committed relevance mapping.

    ``kinds`` carries one :class:`KindCoverage` per surface in the canonical
    :class:`CoverageKind` order. ``orphan_mapping_target_ids`` are the record
    ids the mapping references that belong to NONE of the four derivable
    surfaces (doc-page / source-code grounding targets outside the enumerable
    four) -- a reported honesty field, not an error. ``referenced_target_count``
    is the number of distinct record ids the mapping references.

    Every field is derived deterministically from bundled authorities and the
    committed mapping, with all id lists sorted, so the serialised report is
    byte-identical across machines and runs.
    """

    model_config = _STRICT_FROZEN

    kinds: tuple[KindCoverage, ...] = Field(min_length=1)
    orphan_mapping_target_ids: tuple[str, ...] = ()
    referenced_target_count: int = Field(ge=0)

    def kind(self, kind: CoverageKind) -> KindCoverage:
        """Return the :class:`KindCoverage` for one surface."""
        for entry in self.kinds:
            if entry.kind is kind:
                return entry
        raise KeyError(kind)


def coverage_report_path() -> Path:
    """Return the dev-local path for the coverage report.

    A measurement artefact, not shipped data: it is regenerated by a coverage
    run and no runtime consumer reads it, so it lives beside this harness under
    ``dev/`` rather than in the production ``_data`` tree.
    """
    return Path(__file__).resolve().parent / "evaluation" / "coverage-report.json"


def legal_provision_ids(authority: ValidatedRegistryAuthority) -> tuple[str, ...]:
    """Return the sorted legal-catalogue provision ids that can be targeted.

    A provision is a derivable target only when its catalogue entry carries a
    permalink: the resolution layer drops a permalink-less legal entry rather
    than emit an unreachable target, so a permalink-less provision is not part
    of the derivable surface either.
    """
    catalogue = authority.catalogues.legal
    return tuple(
        sorted(legal_id for legal_id, entry in catalogue.items() if _has_permalink(entry)),
    )


def compute_casilla_coverage_census(
    *,
    relevance: SweepResult | None = None,
    casilla_records: tuple[CasillaSearchRecord, ...] | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> CasillaCoverageCensus:
    """Compute deterministic coverage for the projected casilla contracts.

    The census uses only the real projection and the committed relevance
    mapping. A projected record is exact-target covered when the shared
    :func:`to_search_record` funnel supplies its canonical non-empty target;
    this records deterministic enrollment, not Pagefind index membership or
    generated-page/anchor existence. Definition coverage is limited to the
    Spanish invariant description currently present on the projection, and
    locale coverage means at least one authored non-Spanish registry label.
    Display descriptions may still use Spanish fallback for reader-facing
    rendering and are therefore not authoritative for this census axis.

    Relevance coverage is the same inbound-record-id join used by
    :func:`compute_coverage_report`, restricted to projected casilla ids. It is
    intentionally not used as a prerequisite for exact-target enrollment.

    Args:
        relevance: The committed sweep mapping; defaults to the bundled load.
        casilla_records: Projected casilla records; defaults to the bundled
            validated-authority projection.
        authority: The validated registry authority used when projecting the
            default casilla records and checking authored locale entries.

    Returns:
        A strict, frozen, deterministic census in
        :class:`CasillaCoverageKind` order.
    """
    resolved_relevance = relevance if relevance is not None else load_committed_relevance()
    resolved_authority = authority if authority is not None else bundled_authority()
    if casilla_records is None:
        resolved_casillas = project_casilla_search_records(resolved_authority)[0]
    else:
        resolved_casillas = casilla_records

    by_id: dict[str, list[SearchRecord]] = {}
    authored_locale: set[str] = set()
    for record in resolved_casillas:
        search_record = to_search_record(record)
        by_id.setdefault(search_record.id, []).append(search_record)
        if _has_authored_locale(record, resolved_authority):
            authored_locale.add(search_record.id)

    projected = set(by_id)
    exact_target = {
        record_id for record_id, records in by_id.items() if any(_has_exact_target(record) for record in records)
    }
    definition = {
        record_id for record_id, records in by_id.items() if any(_has_definition(record) for record in records)
    }
    locale = authored_locale
    referenced = _referenced_record_ids(resolved_relevance)
    relevance_ids = projected & referenced

    coverage_by_surface = {
        CasillaCoverageKind.PROJECTED: projected,
        CasillaCoverageKind.EXACT_TARGET: exact_target,
        CasillaCoverageKind.DEFINITION: definition,
        CasillaCoverageKind.LOCALE: locale,
        CasillaCoverageKind.RELEVANCE: relevance_ids,
    }
    surfaces = tuple(
        _casilla_surface_coverage(surface, projected, coverage_by_surface[surface]) for surface in CasillaCoverageKind
    )
    return CasillaCoverageCensus(surfaces=surfaces)


def compute_coverage_report(
    *,
    relevance: SweepResult | None = None,
    concept_cards: tuple[ConceptCardRecord, ...] | None = None,
    casilla_records: tuple[CasillaSearchRecord, ...] | None = None,
    cli_command_records: tuple[CliSurfaceRecord, ...] | None = None,
    cli_option_records: tuple[CliOptionRecord, ...] | None = None,
    legal_ids: tuple[str, ...] | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> TerminologyCoverageReport:
    """Compute the corpus coverage report.

    Materialises the four derivable target surfaces (approved concept cards,
    casilla projections, CLI command + option records, legal provisions),
    assigns each its canonical search-record id, and joins that surface against
    the record ids the committed relevance mapping references.

    Every argument defaults to the production authority / projection, and is
    injectable so a test can drive a narrowed, deterministic surface. The CLI
    projection is the one costly default (it walks the live command tree in
    four language-pinned subprocesses); inject ``cli_command_records`` /
    ``cli_option_records`` to avoid it.

    Args:
        relevance: The committed sweep mapping; defaults to the bundled load.
        concept_cards: Handbook concept cards; defaults to the bundled
            projection. Only APPROVED cards form the derivable concept surface,
            matching the swept query vocabulary (approved-only).
        casilla_records: Casilla search records; defaults to the bundled
            projection.
        cli_command_records: CLI command records; defaults to the live
            projection.
        cli_option_records: CLI option records; defaults to the live
            projection.
        legal_ids: Targetable legal-provision ids; defaults to the permalink
            -bearing catalogue provisions.
        authority: The validated registry authority the casilla and legal
            surfaces read through; defaults to the bundled authority.

    Returns:
        A deterministic :class:`TerminologyCoverageReport`.
    """
    resolved_authority = authority if authority is not None else bundled_authority()
    resolved_relevance = relevance if relevance is not None else load_committed_relevance()
    resolved_cards = concept_cards if concept_cards is not None else project_concept_cards()[0]
    resolved_casillas = (
        casilla_records
        if casilla_records is not None
        else project_casilla_search_records(
            resolved_authority,
        )[0]
    )
    resolved_legal = legal_ids if legal_ids is not None else legal_provision_ids(resolved_authority)
    if cli_command_records is None or cli_option_records is None:
        commands, options, _ = project_cli_search_records()
        resolved_commands = cli_command_records if cli_command_records is not None else commands
        resolved_options = cli_option_records if cli_option_records is not None else options
    else:
        resolved_commands = cli_command_records
        resolved_options = cli_option_records

    referenced = _referenced_record_ids(resolved_relevance)

    surfaces: dict[CoverageKind, set[str]] = {
        CoverageKind.CONCEPT: {to_search_record(card).id for card in resolved_cards if card.is_approved},
        CoverageKind.CASILLA: {to_search_record(record).id for record in resolved_casillas},
        CoverageKind.CLI: {to_search_record(record).id for record in (*resolved_commands, *resolved_options)},
        CoverageKind.LEGAL: {legal_target_record_id(legal_id) for legal_id in resolved_legal},
    }

    kinds = tuple(_kind_coverage(kind, surfaces[kind], referenced) for kind in CoverageKind)

    derivable = surfaces[CoverageKind.CONCEPT].union(
        surfaces[CoverageKind.CASILLA],
        surfaces[CoverageKind.CLI],
        surfaces[CoverageKind.LEGAL],
    )
    orphans = tuple(sorted(referenced - derivable))

    return TerminologyCoverageReport(
        kinds=kinds,
        orphan_mapping_target_ids=orphans,
        referenced_target_count=len(referenced),
    )


def _kind_coverage(kind: CoverageKind, derivable: set[str], referenced: set[str]) -> KindCoverage:
    covered = derivable & referenced
    uncovered = tuple(sorted(derivable - referenced))
    return KindCoverage(
        kind=kind,
        total=len(derivable),
        covered=len(covered),
        uncovered_ids=uncovered,
    )


def _casilla_surface_coverage(
    surface: CasillaCoverageKind,
    projected: set[str],
    covered: set[str],
) -> CasillaSurfaceCoverage:
    return CasillaSurfaceCoverage(
        surface=surface,
        total=len(projected),
        covered=len(covered),
        uncovered_ids=tuple(sorted(projected - covered)),
    )


def _referenced_record_ids(relevance: SweepResult) -> set[str]:
    return {target.record_id for mapping in relevance.mappings for target in mapping.targets}


def _has_exact_target(record: SearchRecord) -> bool:
    return bool(record.target.strip())


def _has_definition(record: SearchRecord) -> bool:
    description = record.descriptions.get(OutputLanguage.ES)
    return bool(description and description.strip())


def _has_authored_locale(record: CasillaSearchRecord, authority: ValidatedRegistryAuthority) -> bool:
    """Return whether the latest registry definition has an authored label."""
    try:
        definition = authority.modelo(record.modelo.value)
    except RegistrySnapshotError:
        return False
    candidates = [
        (revision.valid_from, str(revision_id), casilla)
        for revision_id, revision in definition.revisions.items()
        for casilla in revision.casillas
        if casilla.id == record.casilla_id
    ]
    if not candidates:
        return False
    latest = max(candidates, key=lambda candidate: (candidate[0], candidate[1]))[2]
    return any(
        present and value is not None
        for locale in _NON_SPANISH_LOCALES
        for key in latest.localization_keys
        for present, value in (lookup_translation_entry(key, locale=locale),)
    )


def _has_permalink(entry: object) -> bool:
    permalink = getattr(entry, "permalink", None)
    return bool(permalink and str(permalink).strip())
