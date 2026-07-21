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
:func:`~dev.docs.terminology._unified_record.to_search_record` funnel and the
legal-target id shape :func:`~dev.docs.terminology._resolution` builds), and
joins that derivable surface against the record ids the committed mapping
references. A target with no inbound reference is *uncovered*; a mapping target
that belongs to none of the four derivable surfaces (a doc-page or source-code
grounding surface, outside the enumerable four) is an *orphan mapping target*,
reported rather than crashed on.

The report carries per-kind totals, per-kind covered counts, and the ordered
list of uncovered ids per kind. It carries NO timestamp and NO machine path, so
two runs on two machines produce byte-identical JSON -- the determinism the
committed-artifact discipline requires.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import ValidatedRegistryAuthority, bundled_authority

from ._casilla_projection import project_casilla_search_records
from ._cli_projection import CliOptionRecord, CliSurfaceRecord, project_cli_search_records
from ._concept_cards import ConceptCardRecord, project_concept_cards
from ._miss_rate import load_committed_relevance
from ._search_record import CasillaSearchRecord
from ._sweep import SweepResult
from ._unified_record import to_search_record

__all__ = [
    "CoverageKind",
    "CoverageReport",
    "KindCoverage",
    "compute_coverage_report",
    "coverage_report_path",
    "legal_provision_ids",
    "legal_target_record_id",
]

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_UTF_8: Final[str] = "utf-8"

#: The record-id prefix the resolution layer stamps on a legal-grounding
#: target (``_resolution._legal_target`` builds ``id=f"legal:{legal_id}"``).
#: Mirrored here so the derivable legal surface joins the mapping on the exact
#: same id shape.
_LEGAL_RECORD_ID_PREFIX: Final[str] = "legal:"


class CoverageKind(StrEnum):
    """The four enumerable target surfaces a coverage report measures.

    ``legal`` is a distinct coverage axis even though a legal target serialises
    into the unified index as a ``page``-kind record: it is derived from the
    legal catalogue's provision vocabulary, not from a page walk, so the report
    tracks it as its own surface.
    """

    CONCEPT = "concept"
    CASILLA = "casilla"
    CLI = "cli"
    LEGAL = "legal"


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


class CoverageReport(BaseModel):
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
    """Return the bundled path for the committed coverage report."""
    return bundled_path("terminology", "evaluation", "coverage-report.json")


def legal_target_record_id(legal_id: str) -> str:
    """Return the search-record id for a legal-catalogue provision.

    Mirrors the id shape the resolution layer builds for a legal-grounding
    target, so the derivable legal surface joins the committed mapping on the
    same key.
    """
    return f"{_LEGAL_RECORD_ID_PREFIX}{legal_id}"


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


def compute_coverage_report(
    *,
    relevance: SweepResult | None = None,
    concept_cards: tuple[ConceptCardRecord, ...] | None = None,
    casilla_records: tuple[CasillaSearchRecord, ...] | None = None,
    cli_command_records: tuple[CliSurfaceRecord, ...] | None = None,
    cli_option_records: tuple[CliOptionRecord, ...] | None = None,
    legal_ids: tuple[str, ...] | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> CoverageReport:
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
        A deterministic :class:`CoverageReport`.
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

    referenced = {target.record_id for mapping in resolved_relevance.mappings for target in mapping.targets}

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

    return CoverageReport(
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


def _has_permalink(entry: object) -> bool:
    permalink = getattr(entry, "permalink", None)
    return bool(permalink and str(permalink).strip())
