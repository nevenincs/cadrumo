"""Canonical data shapes shared by the AEIP inventory, chain plan, and apply stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AeipOccurrence:
    """One AEIP event-row casilla as declared by one revision."""

    revision_id: str
    casilla_id: str
    label: str
    title: str
    # The locale keys the schema declares for this occurrence, most specific
    # first. A grounded occurrence carries its continuity key alongside the
    # per-occurrence one, which is how one chain collapses many occurrence
    # keys into a single translated concept.
    localization_keys: tuple[str, ...] = ()
    legal_refs: tuple[str, ...] = ()
    continuidad_id: str | None = None
    # Source catalogue ids are hydrated by the canonical loader. They are
    # carried into the apply plan so an evolution can never be authored from
    # an empty or guessed evidence list.
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AeipEvent:
    """One programme, as carried across the revisions that declare it."""

    slug: str
    title: str
    occurrences: tuple[AeipOccurrence, ...]

    @property
    def revisions(self) -> tuple[str, ...]:
        """The revisions declaring this programme, in ascending order."""
        return tuple(sorted({occurrence.revision_id for occurrence in self.occurrences}))

    @property
    def spans_multiple_revisions(self) -> bool:
        """True when the programme appears in more than one revision."""
        return len(self.revisions) > 1


@dataclass(frozen=True, slots=True)
class AeipAmbiguity:
    """A case the planner refuses to resolve on its own.

    ``kind`` is one of ``gapped_span``, ``intra_revision_duplicate``,
    ``oversize_chain_id``, or ``title_variant``. Each is a real shape measured
    in the corpus, not a hypothetical; ``detail`` carries the evidence an
    operator needs to adjudicate it.
    """

    kind: str
    slugs: tuple[str, ...]
    detail: str

    @property
    def blocking(self) -> bool:
        """Every ambiguity blocks: the planner never guesses an identity."""
        return True


@dataclass(frozen=True, slots=True)
class EvolutionPair:
    """One adjacent-revision pair a chain needs an evolution record for."""

    chain_id: str
    from_revision: str
    to_revision: str
    evolution_kind: str
    # The legal refs the chain carries at the target revision. A retirement
    # keeps the source revision's refs, since the target no longer declares
    # the box at all.
    legal_refs: tuple[str, ...] = ()
    # Source catalogue ids consulted for this transition. Normal pairs carry
    # both endpoints; a retirement carries the last declaring row.
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ChainPlanEntry:
    """One planned continuity chain: what to stamp and what records to author."""

    chain_id: str
    title: str
    occurrences: tuple[AeipOccurrence, ...]
    pairs: tuple[EvolutionPair, ...]


@dataclass(frozen=True, slots=True)
class ChainPlan:
    """The full planned chain set plus everything still needing adjudication."""

    entries: tuple[ChainPlanEntry, ...]
    ambiguities: tuple[AeipAmbiguity, ...]
    single_revision_events: tuple[AeipEvent, ...]

    @property
    def complete(self) -> bool:
        """True when nothing is left to adjudicate."""
        return not self.ambiguities

    @property
    def stamp_count(self) -> int:
        """How many occurrences the plan would stamp."""
        return sum(len(entry.occurrences) for entry in self.entries)

    @property
    def record_count(self) -> int:
        """How many evolution records the plan would author."""
        return sum(len(entry.pairs) for entry in self.entries)


@dataclass(frozen=True, slots=True)
class AeipInventory:
    """The extracted family, grouped by programme."""

    events: tuple[AeipEvent, ...]
    occurrences: tuple[AeipOccurrence, ...]
    revisions: tuple[str, ...]
    category_row_counts: dict[str, int] = field(default_factory=dict)
    untitled_occurrences: tuple[AeipOccurrence, ...] = ()

    def event_by_slug(self, slug: str) -> AeipEvent | None:
        """The programme carrying this slug, when the family has one."""
        return next((event for event in self.events if event.slug == slug), None)


@dataclass(frozen=True, slots=True)
class StaleAdjudication:
    """One adjudication entry the live corpus no longer grounds.

    This is the mirror image of :class:`AeipAmbiguity`: an ambiguity is a live
    case with no judgment, a stale adjudication is a judgment with no live
    case. An exclusion whose occurrence was renumbered away, an alias whose
    title AEAT no longer publishes, or a split/override/distinct-variants entry
    naming a programme the corpus no longer yields all become permanent
    silent no-ops -- nothing fails, the entry simply stops doing anything --
    unless something reads the corpus against the ledger in this direction too.
    """

    kind: str
    detail: str


@dataclass(frozen=True, slots=True)
class AeipStampWrite:
    """One row-local lineage update prepared against the live source tree."""

    path: Path
    revision_id: str
    casilla_id: str
    keys: tuple[tuple[str, str], ...]

    @property
    def key_map(self) -> dict[str, str]:
        """Return the insertion mapping consumed by the shared writer."""
        return dict(self.keys)


@dataclass(frozen=True, slots=True)
class AeipEvolutionWrite:
    """One evolution fragment prepared against the live source tree."""

    path: Path
    pair: EvolutionPair
    casilla_id: str
    content: str


@dataclass(frozen=True, slots=True)
class AeipApplyPlan:
    """Fail-closed, idempotent Modelo 100 AEIP write plan.

    The plan is a reportable value rather than a mutable transaction.  It is
    produced only after the canonical modelo loader has accepted the live
    tree, and the apply function re-reads every target before replacing it.
    ``refusals`` therefore remain visible to a caller instead of being
    converted into a partial write.
    """

    stamp_writes: tuple[AeipStampWrite, ...]
    evolution_writes: tuple[AeipEvolutionWrite, ...]
    existing_stamps: int
    existing_evolutions: int
    unexpected_evolutions: int
    refusals: tuple[str, ...]

    @property
    def ready(self) -> bool:
        """Whether the plan passed every preflight refusal gate."""
        return not self.refusals
