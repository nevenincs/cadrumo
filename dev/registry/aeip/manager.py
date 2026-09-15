"""Inventory and chain-plan generator for the Modelo 100 anexo-A AEIP family.

The anexo-A "acontecimientos de excepcional interés público" table
(``resultados/anexo_a_res/deducciones_inversion_empresarial_res``, legal
``ley-35-2006:art-68.2``) is the registry's renumbering minefield: every event
row shares one ``semantic_role`` and the casilla ids are repacked yearly, so
neither the id nor the role identifies the underlying programme. What *does*
identify it is the official Spanish programme title, which is why the continuity
chain for this family is keyed on the event rather than on the box.

That title is not stored in the schema. A casilla declares only its
``localization_keys`` and the text is resolved from the shared locale
catalogues, so this module reads the family through the registry loader and
resolves each title with ``casilla.get_label`` on the mandatory ``es`` source
locale. It then derives the event-keyed chain ids and plans the stamps and
evolution records a grounding campaign would author. Planning is side-effect
free; the explicit apply boundary below can write only after a complete,
fail-closed preflight.

Grounding a chain has a direct payoff on that same locale surface. An
occurrence's key is per-revision
(``modelo.schema.100.revision.2024.casilla.1945.label``), so an ungrounded
programme spends one translatable key per year it appears. A stamped chain adds
the continuity key ``modelo.schema.100.casilla.continuidad.<chain>.label``,
which the resolver prefers, collapsing every occurrence of one programme onto a
single translated concept.

Identity is a legal judgment, never text similarity, so the planner fails
closed. Where the corpus is genuinely ambiguous -- a programme re-designated
under a fresh window after a gap, two title spellings that may or may not be
one programme, a title too long for the 128-character chain-id budget, or a
suspected transcription duplicate -- the planner refuses to invent an answer
and reports the case as an unadjudicated ambiguity. An operator resolves each
one in the adjudications file, and only then does the chain plan complete.
"""

from __future__ import annotations

import re
import tomllib
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from cadrumo.core.atomic_write import atomic_write_text
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.i18n.render import MissingTranslationError
from cadrumo.core.identity.continuidad import ContinuidadId
from cadrumo.domain.calculations.registry.errors import RegistryLoadError

from ..compiler.loader import load_modelo_directory
from .adjudications import AdjudicationSet

__all__ = [
    "AeipAmbiguity",
    "AeipApplyPlan",
    "AeipError",
    "AeipEvent",
    "AeipEvolutionWrite",
    "AeipInventory",
    "AeipOccurrence",
    "AeipStampWrite",
    "ChainPlan",
    "ChainPlanEntry",
    "EvolutionPair",
    "StaleAdjudication",
    "apply_prepared_plan",
    "build_inventory",
    "chain_id_for",
    "derive_slug",
    "detect_stale_adjudications",
    "extract_occurrences",
    "plan_chains",
    "prepare_apply",
    "render_evolution_record",
]

# The mandatory source locale: the official Spanish text AEAT publishes, which
# is what identifies a programme. A translated catalogue must never key a
# chain, so this is not an operator-tunable default.
SOURCE_LOCALE = "es"

# The anexo-A event rows. The sibling `_flag` role carries the *category* rows
# of the same table (régimen general LIS, I+D+i, producciones cinematográficas,
# ...) which name no programme and are therefore not part of this family.
EVENT_SEMANTIC_ROLE = "irpf_anexo_a_aeip_aplicado"
CATEGORY_SEMANTIC_ROLE = "irpf_anexo_a_aeip_aplicado_flag"
ANEXO_A_SECTION_LEAF = "deducciones_inversion_empresarial_res"

# Chain-id shape. Mirrors `ContinuidadId` in `cadrumo.core.identity`: max 128
# characters and the pattern below.
#
# The separator is a hyphen, not a dot, because the chain id is embedded whole
# into a locale key. `encode_modelo_locale_segment` passes `[A-Za-z0-9_-]+`
# through verbatim and base32-encodes anything else, so a dotted chain id turns
# its own continuity key into an opaque `x-...` blob while a kebab one stays
# readable to a translator. 802 of the 814 chain ids in the registry are already
# kebab-only for this reason.
#
# The column leaf is `aplicado` because AEAT numbers only that column. Its
# Diseño de Registros gives each programme three XML fields -- `...S` (deducción
# generated), `...A` (aplicado), `...P` (pendiente) -- and only the `A` field
# carries a casilla number, so it is the only one the registry models. The leaf
# is kept explicit so a numbered `pendiente` column could extend the scheme
# without renaming the chains that already exist.
CHAIN_PREFIX = "irpf-aeip-"
CHAIN_COLUMN_LEAF = "aplicado"

# The one authority for chain-id shape. A hand-copied regex here had drifted
# wider than the canonical constraint (it admitted "." and ":"), so the planner
# could emit an id that only failed later, at registry load.
_CHAIN_ID_ADAPTER = TypeAdapter(ContinuidadId)
CHAIN_ID_MAX_LENGTH: int = int(_CHAIN_ID_ADAPTER.json_schema()["maxLength"])


def chain_id_is_wellformed(candidate: str) -> bool:
    """Report whether ``candidate`` satisfies the canonical continuidad-id shape."""
    try:
        _CHAIN_ID_ADAPTER.validate_python(candidate)
    except ValidationError:
        return False
    return True


_APLICADO_SUFFIX = re.compile(r":\s*Aplicado en esta declaraci[oó]n\s*$", re.IGNORECASE)
_WRAPPING_QUOTES = re.compile(r"^\s*[“”«»\"](?P<title>.+?)[“”«»\"]\s*$")
_WHITESPACE = re.compile(r"\s+")
_YEAR_TOKEN = re.compile(r"(19|20)\d{2}")
_NON_SLUG = re.compile(r"[^a-z0-9]+")
_SLUG_RUNS = re.compile(r"-{2,}")


# Keep the public AEIP name for callers while using the registry's canonical
# error type. A new CadrumoError subclass here would need a global error-code
# registry entry outside this authoring lane; aliasing preserves the existing
# catch surface without introducing an unregistered exception class.
AeipError = RegistryLoadError


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


def detect_stale_adjudications(
    inventory: AeipInventory,
    adjudications: AdjudicationSet,
) -> tuple[StaleAdjudication, ...]:
    """Report adjudication entries the live corpus no longer supports.

    ``inventory`` must be the inventory built WITH ``adjudications`` applied
    (exclusions and aliases act during grouping), so that ``inventory.events``
    reflects the same slug space the adjudications were judged against.
    """
    found: list[StaleAdjudication] = []
    live_pairs = {(occurrence.revision_id, occurrence.casilla_id) for occurrence in inventory.occurrences}
    live_titles = {occurrence.title for occurrence in inventory.occurrences if occurrence.title}
    live_slugs = {event.slug for event in inventory.events}

    for exclusion in adjudications.exclusions:
        if (exclusion.revision, exclusion.casilla) not in live_pairs:
            found.append(
                StaleAdjudication(
                    kind="exclusion",
                    detail=f"{exclusion.revision}:{exclusion.casilla} names no occurrence in the live corpus",
                ),
            )

    for alias in adjudications.aliases:
        if not any(title in live_titles for title in alias.titles):
            found.append(
                StaleAdjudication(
                    kind="alias",
                    detail=f"slug {alias.slug!r} names no title the live corpus publishes: {alias.titles}",
                ),
            )

    for override in adjudications.chain_ids:
        if override.slug not in live_slugs:
            found.append(
                StaleAdjudication(
                    kind="chain_id",
                    detail=f"chain id override names slug {override.slug!r}, which is not a live programme",
                ),
            )

    for split in adjudications.splits:
        event = inventory.event_by_slug(split.slug)
        if event is None:
            found.append(
                StaleAdjudication(
                    kind="split",
                    detail=f"split names slug {split.slug!r}, which is not a live programme",
                ),
            )
        elif split.from_revision not in event.revisions:
            found.append(
                StaleAdjudication(
                    kind="split",
                    detail=(
                        f"split for {split.slug!r} names revision {split.from_revision!r}, "
                        f"which is not among {event.revisions}"
                    ),
                ),
            )

    for variants in adjudications.distinct_variants:
        missing = tuple(slug for slug in variants.slugs if slug not in live_slugs)
        if missing:
            found.append(
                StaleAdjudication(
                    kind="distinct_variants",
                    detail=f"distinct_variants names slug(s) no longer live: {missing}",
                ),
            )

    return tuple(sorted(found, key=lambda entry: (entry.kind, entry.detail)))


def _normalise(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return _WHITESPACE.sub(" ", folded).strip().rstrip(".,;:")


def derive_slug(title: str) -> str:
    """Fold an official programme title into the chain-id slug segment.

    Accent-strips, lowercases, and collapses every non-alphanumeric run to a
    single hyphen. ``ñ`` folds to ``n`` and the ordinal indicators ``º``/``ª``
    to ``o``/``a`` before stripping, so "150.º aniversario" and "4ª Edición"
    keep a readable slug instead of losing the ordinal entirely.
    """
    decomposed = unicodedata.normalize("NFKD", title)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    folded = stripped.replace("ñ", "n").replace("Ñ", "n").replace("º", "o").replace("ª", "a")
    slug = _NON_SLUG.sub("-", folded.lower()).strip("-")
    return _SLUG_RUNS.sub("-", slug)


def chain_id_for(slug: str, *, column: str = CHAIN_COLUMN_LEAF) -> str:
    """Compose the full continuity chain id for one event slug."""
    return f"{CHAIN_PREFIX}{slug}-{column}"


def _title_from_label(label: str) -> str | None:
    """Pull the programme title out of an anexo-A event label.

    The published label is ``"<title>": Aplicado en esta declaración``. Most
    titles are wrapped in typographic quotes, but a handful carry quotes
    *inside* the title instead (``Celebración del Summit "MADBLUE"``), so the
    wrapping quotes are stripped only when they actually wrap the whole core.
    """
    if not _APLICADO_SUFFIX.search(label):
        return None
    core = _APLICADO_SUFFIX.sub("", label).strip()
    if not core:
        return None
    wrapped = _WRAPPING_QUOTES.match(core)
    if wrapped is None:
        return core.strip()
    title = wrapped.group("title")
    assert isinstance(title, str)
    return title.strip()


def extract_occurrences(
    modelos_root: Path,
    *,
    modelo_id: str = "100",
    locale: str = SOURCE_LOCALE,
) -> tuple[tuple[AeipOccurrence, ...], dict[str, int]]:
    """Read every anexo-A AEIP event row through the registry loader.

    The schema carries no natural-language label: a casilla declares only its
    ``localization_keys``, and the text is resolved from the shared locale
    catalogues. So the family is read through
    :func:`~cadrumo.domain.calculations.registry.load_modelo_directory` and each
    programme title comes from ``casilla.get_label`` rather than from a
    fragment field, which keeps this planner on the one canonical resolution
    path instead of re-deriving keys or re-reading TOML.

    Returns the event-row occurrences plus a per-revision count of the sibling
    category rows, which the inventory reports but never enrols in a chain.
    """
    modelo_root = modelos_root / modelo_id
    if not modelo_root.is_dir():
        raise AeipError(f"no registry directory for modelo {modelo_id} at {modelo_root}")
    try:
        definition = load_modelo_directory(modelo_root)
    except RegistryLoadError as error:
        raise AeipError(f"cannot load modelo {modelo_id} registry: {error}") from error

    occurrences: list[AeipOccurrence] = []
    category_counts: dict[str, int] = defaultdict(int)
    for revision in definition.revisions.values():
        for casilla in revision.casillas:
            if ANEXO_A_SECTION_LEAF not in tuple(casilla.section or ()):
                continue
            role = str(casilla.semantic_role or "")
            if role == CATEGORY_SEMANTIC_ROLE:
                category_counts[revision.id] += 1
                continue
            if role != EVENT_SEMANTIC_ROLE:
                continue
            # A key with no catalogue entry leaves the occurrence untitled
            # rather than raising: the rest of the family still needs to be
            # plannable, and the gap surfaces as a `missing_title` ambiguity.
            try:
                label = casilla.get_label(locale)
            except MissingTranslationError:
                label = ""
            occurrences.append(
                AeipOccurrence(
                    revision_id=revision.id,
                    casilla_id=casilla.id,
                    label=label,
                    title=_title_from_label(label) or "",
                    localization_keys=tuple(casilla.localization_keys),
                    legal_refs=tuple(str(ref) for ref in casilla.legal_refs),
                    continuidad_id=casilla.continuidad_id,
                    source_refs=tuple(str(ref) for ref in casilla.source_refs),
                ),
            )
    return tuple(occurrences), dict(category_counts)


def build_inventory(
    occurrences: tuple[AeipOccurrence, ...],
    *,
    adjudications: AdjudicationSet | None = None,
    category_row_counts: dict[str, int] | None = None,
) -> AeipInventory:
    """Group occurrences into programmes, honouring any alias adjudications."""
    resolved = adjudications or AdjudicationSet.empty()
    grouped: dict[str, list[AeipOccurrence]] = defaultdict(list)
    titles: dict[str, str] = {}
    untitled: list[AeipOccurrence] = []
    for occurrence in occurrences:
        if resolved.is_excluded(occurrence.revision_id, occurrence.casilla_id):
            continue
        if not occurrence.title:
            untitled.append(occurrence)
            continue
        slug = resolved.slug_for(occurrence.title) or derive_slug(occurrence.title)
        grouped[slug].append(occurrence)
        titles.setdefault(slug, occurrence.title)

    events = tuple(
        AeipEvent(slug=slug, title=titles[slug], occurrences=tuple(rows)) for slug, rows in sorted(grouped.items())
    )
    revisions = tuple(sorted({occurrence.revision_id for occurrence in occurrences}))
    return AeipInventory(
        events=events,
        occurrences=occurrences,
        revisions=revisions,
        category_row_counts=dict(category_row_counts or {}),
        untitled_occurrences=tuple(untitled),
    )


def _is_contiguous(revision_ids: list[str], order: dict[str, int]) -> bool:
    indexes = sorted(order[revision_id] for revision_id in set(revision_ids))
    return indexes == list(range(indexes[0], indexes[0] + len(indexes)))


def _segments_for(
    event: AeipEvent,
    adjudications: AdjudicationSet,
    order: dict[str, int],
) -> list[tuple[str, list[AeipOccurrence]]]:
    """Partition an event's occurrences into the chains it should become.

    Without a split adjudication that is one chain. With one, the occurrences
    from the adjudicated resumption revision onward become a second chain.
    """
    ordered = sorted(event.occurrences, key=lambda occurrence: order[occurrence.revision_id])
    base_chain_id = adjudications.chain_id_for(event.slug) or chain_id_for(event.slug)
    split = adjudications.split_for(event.slug)
    if split is None:
        return [(base_chain_id, ordered)]

    boundary = order.get(split.from_revision)
    if boundary is None:
        raise AeipError(
            f"split for {event.slug!r} names revision {split.from_revision!r}, which is not among {tuple(order)}",
        )
    segments: list[tuple[str, list[AeipOccurrence]]] = []
    earlier = [row for row in ordered if order[row.revision_id] < boundary]
    later = [row for row in ordered if order[row.revision_id] >= boundary]
    if earlier:
        segments.append((base_chain_id, earlier))
    if later:
        segments.append((split.chain_id, later))
    return segments


def _detect_ambiguities(
    inventory: AeipInventory,
    adjudications: AdjudicationSet,
) -> tuple[AeipAmbiguity, ...]:
    found: list[AeipAmbiguity] = []
    order = {revision: index for index, revision in enumerate(inventory.revisions)}

    for occurrence in inventory.untitled_occurrences:
        found.append(
            AeipAmbiguity(
                kind="missing_title",
                slugs=(f"{occurrence.revision_id}:{occurrence.casilla_id}",),
                detail=(
                    f"casilla {occurrence.casilla_id} in revision {occurrence.revision_id} "
                    f"resolves no programme title from {occurrence.localization_keys or ('no locale key',)}, "
                    "so it cannot be keyed to an event"
                ),
            ),
        )

    for event in inventory.events:
        # A programme present, absent, then present again asserts one legal
        # concept across a year the form says it did not exist in. The
        # contiguity policy refuses that, so it needs a split adjudication --
        # and the split must actually land on the gap. A split placed at the
        # wrong revision leaves a segment still spanning the gap, which would
        # emit exactly the chain the policy rejects, so both shapes are caught
        # by checking the planned segments rather than the raw event.
        for chain_id, rows in _segments_for(event, adjudications, order):
            if _is_contiguous([row.revision_id for row in rows], order):
                continue
            spans = ", ".join(sorted({row.revision_id for row in rows}))
            found.append(
                AeipAmbiguity(
                    kind="gapped_span",
                    slugs=(event.slug,),
                    detail=(
                        f"{event.title!r} would be chained as {chain_id!r} across {spans}, which spans a gap; "
                        "a re-designated programme needs a split at the resumption revision"
                    ),
                ),
            )

        # The same programme at two ids in one revision has no discriminator in
        # the registry, so the planner cannot tell a genuine second column from
        # a transcription duplicate.
        per_revision: dict[str, list[str]] = defaultdict(list)
        for occurrence in event.occurrences:
            per_revision[occurrence.revision_id].append(occurrence.casilla_id)
        for revision_id, casilla_ids in sorted(per_revision.items()):
            if len(casilla_ids) > 1:
                found.append(
                    AeipAmbiguity(
                        kind="intra_revision_duplicate",
                        slugs=(event.slug,),
                        detail=(
                            f"{event.title!r} occupies ids {sorted(casilla_ids)} in revision {revision_id}; "
                            "adjudicate which is authoritative and exclude the other"
                        ),
                    ),
                )

        # Chain-id shape is only a question for a programme that actually gets
        # a chain. A single-revision programme asserts no cross-revision
        # identity and is never stamped, so an over-long title there is not a
        # decision anyone has to make -- and blocking on it would demand an
        # adjudication that changes nothing. If such a programme later gains a
        # revision, this fires then, which is the point at which it matters.
        if not event.spans_multiple_revisions:
            continue
        chain_id = adjudications.chain_id_for(event.slug) or chain_id_for(event.slug)
        if len(chain_id) > CHAIN_ID_MAX_LENGTH:
            found.append(
                AeipAmbiguity(
                    kind="oversize_chain_id",
                    slugs=(event.slug,),
                    detail=(
                        f"chain id for {event.title!r} is {len(chain_id)} characters "
                        f"(limit {CHAIN_ID_MAX_LENGTH}); adjudicate a shortened slug"
                    ),
                ),
            )
        elif not chain_id_is_wellformed(chain_id):
            found.append(
                AeipAmbiguity(
                    kind="oversize_chain_id",
                    slugs=(event.slug,),
                    detail=f"chain id {chain_id!r} does not satisfy the continuidad_id pattern",
                ),
            )

    # Two titles that differ only in an embedded year may be one programme
    # relabelled or two successive designations. Both shapes occur in the
    # corpus, so the distinction is a legal judgment, not a text rule.
    masked: dict[str, list[AeipEvent]] = defaultdict(list)
    for event in inventory.events:
        masked[_YEAR_TOKEN.sub("Y", _normalise(event.title))].append(event)
    for variants in masked.values():
        if len(variants) < 2:
            continue
        slugs = tuple(event.slug for event in variants)
        if adjudications.variants_resolved(slugs):
            continue
        found.append(
            AeipAmbiguity(
                kind="title_variant",
                slugs=slugs,
                detail=(
                    "titles differ only by an embedded year: "
                    + " | ".join(f"{event.title!r} ({', '.join(event.revisions)})" for event in variants)
                    + "; adjudicate one relabelled programme (alias) or successive designations (keep apart)"
                ),
            ),
        )

    return tuple(sorted(found, key=lambda ambiguity: (ambiguity.kind, ambiguity.slugs)))


def _classify_pair(earlier: AeipOccurrence, later: AeipOccurrence) -> str:
    """Name the evolution kind for one adjacent-revision pair.

    An anexo-A event row declares no structural core, so the two axes that can
    drift are the published label and the legal refs. Both must be compared:
    the 2025 revision adds an ordinal reference to every row in the family, so
    a pair crossing that boundary really has evolved its legal refs, and
    recording it as ``unchanged`` would be a drift the strict cross-revision
    validator refuses. A retirement is planned separately.
    """
    label_moved = _normalise(earlier.label) != _normalise(later.label)
    refs_moved = tuple(earlier.legal_refs) != tuple(later.legal_refs)
    if label_moved and refs_moved:
        return "label_and_legal_refs_evolved"
    if label_moved:
        return "label_evolved"
    if refs_moved:
        return "legal_refs_evolved"
    return "unchanged"


def _merge_source_refs(*occurrences: AeipOccurrence | None) -> tuple[str, ...]:
    """Return validated occurrence source ids in stable, duplicate-free order."""
    refs: list[str] = []
    for occurrence in occurrences:
        if occurrence is None:
            continue
        for ref in occurrence.source_refs:
            clean = str(ref).strip()
            if clean and clean not in refs:
                refs.append(clean)
    return tuple(refs)


def plan_chains(
    inventory: AeipInventory,
    *,
    adjudications: AdjudicationSet | None = None,
) -> ChainPlan:
    """Plan the chain stamps and evolution records for the family.

    Only programmes spanning more than one revision get a chain: a single-year
    programme has no cross-revision identity to assert. The plan is emitted
    only for events free of blocking ambiguity, so a partially-adjudicated
    corpus yields a partial plan rather than a guessed one.
    """
    resolved = adjudications or AdjudicationSet.empty()
    ambiguities = _detect_ambiguities(inventory, resolved)
    blocked = {slug for ambiguity in ambiguities for slug in ambiguity.slugs}
    order = {revision: index for index, revision in enumerate(inventory.revisions)}

    entries: list[ChainPlanEntry] = []
    singles: list[AeipEvent] = []
    for event in inventory.events:
        if event.slug in blocked:
            continue
        if not event.spans_multiple_revisions:
            singles.append(event)
            continue
        # A re-designated programme is two chains, not one: the later window
        # asserts a concept no norm carried through the gap, so it takes its
        # own grounded id from the adjudicated resumption revision onward.
        for chain_id, rows in _segments_for(event, resolved, order):
            if len(rows) < 2:
                # A one-revision segment asserts no cross-revision identity.
                singles.append(AeipEvent(slug=event.slug, title=event.title, occurrences=tuple(rows)))
                continue
            pairs = tuple(
                EvolutionPair(
                    chain_id=chain_id,
                    from_revision=earlier.revision_id,
                    to_revision=later.revision_id,
                    evolution_kind=_classify_pair(earlier, later),
                    legal_refs=later.legal_refs,
                    source_refs=_merge_source_refs(earlier, later),
                )
                for earlier, later in pairwise(rows)
            )
            # A segment whose last declaring revision is not the newest revision
            # in the tree has left the form: the chain ends with a retirement.
            last_index = order[rows[-1].revision_id]
            if last_index < len(inventory.revisions) - 1:
                pairs += (
                    EvolutionPair(
                        chain_id=chain_id,
                        from_revision=rows[-1].revision_id,
                        to_revision=inventory.revisions[last_index + 1],
                        evolution_kind="retired",
                        legal_refs=rows[-1].legal_refs,
                        source_refs=_merge_source_refs(rows[-1]),
                    ),
                )
            entries.append(
                ChainPlanEntry(
                    chain_id=chain_id,
                    title=event.title,
                    occurrences=tuple(rows),
                    pairs=pairs,
                ),
            )

    return ChainPlan(
        entries=tuple(entries),
        ambiguities=ambiguities,
        single_revision_events=tuple(singles),
    )


def render_evolution_record(
    pair: EvolutionPair,
    *,
    casilla_id: str,
    modelo_id: str = "100",
    legal_refs: tuple[str, ...] | None = None,
    source_refs: tuple[str, ...] | None = None,
) -> str:
    """Render one evolution record fragment for review or a prepared write.

    ``legal_refs`` defaults to the refs the pair carries at its target
    revision. ``source_refs`` defaults to the validated refs carried by the
    pair; an explicit value remains available for review-only rendering.
    """
    refs = ", ".join(f'"{ref}"' for ref in (pair.legal_refs if legal_refs is None else legal_refs))
    sources = ", ".join(f'"{ref}"' for ref in (pair.source_refs if source_refs is None else source_refs))
    record_id = f"{modelo_id}-{casilla_id}-{pair.from_revision}-{pair.to_revision}-{pair.evolution_kind}"
    return "\n".join(
        (
            f'[[revisions."{pair.to_revision}".casilla_continuidad_evolutions]]',
            f'id = "m{record_id}"',
            f'continuidad_id = "{pair.chain_id}"',
            f'from_revision = "{pair.from_revision}"',
            f'to_revision = "{pair.to_revision}"',
            f'evolution_kind = "{pair.evolution_kind}"',
            f"legal_refs = [{refs}]",
            f"source_refs = [{sources}]",
        ),
    )


# --------------------------------------------------------------------------- apply planning


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


def _add_refusal(refusals: list[str], seen: set[str], detail: str) -> None:
    """Append one stable refusal without flooding a report with duplicates."""
    if detail not in seen:
        seen.add(detail)
        refusals.append(detail)


def _safe_resolve(path: Path, root: Path) -> Path | None:
    """Resolve a path and return it only when it stays below ``root``."""
    try:
        resolved = path.resolve(strict=False)
    except OSError:
        return None
    return resolved if resolved.is_relative_to(root) else None


def _raw_casilla_tables(document: object, revision_id: str) -> tuple[dict[str, object], ...]:
    """Extract raw casilla tables from one source-native TOML document."""
    if not isinstance(document, dict):
        return ()
    revisions = document.get("revisions")
    if not isinstance(revisions, dict):
        return ()
    revision = revisions.get(revision_id)
    if not isinstance(revision, dict):
        return ()
    casillas = revision.get("casillas", ())
    if not isinstance(casillas, list):
        return ()
    tables: list[dict[str, object]] = []
    for raw_table in casillas:
        if not isinstance(raw_table, dict):
            continue
        table: dict[str, object] = {}
        for key, value in raw_table.items():
            if not isinstance(key, str):
                continue
            table[key] = value
        tables.append(table)
    return tuple(tables)


def _locate_casilla_file(
    modelo_root: Path,
    revision_id: str,
    casilla_id: str,
    refusals: list[str],
    seen_refusals: set[str],
) -> Path | None:
    """Find exactly one safe source-native file declaring one casilla.

    The loader is authoritative for semantic materialisation.  This narrow
    raw scan is only localization for the existing insertion helper; it does
    not construct a second registry model or infer a row from its filename.
    """
    revision_candidate = modelo_root / "revisions" / revision_id
    if revision_candidate.is_symlink():
        _add_refusal(
            refusals,
            seen_refusals,
            f"{revision_id}/{casilla_id}: revision path is a symlink",
        )
        return None
    revision_root = _safe_resolve(revision_candidate, modelo_root)
    if revision_root is None:
        _add_refusal(
            refusals,
            seen_refusals,
            f"{revision_id}/{casilla_id}: revision path escapes the Modelo 100 registry root",
        )
        return None
    casillas_root = revision_root / "casillas"
    if casillas_root.is_symlink() or not casillas_root.is_dir():
        _add_refusal(
            refusals,
            seen_refusals,
            f"{revision_id}/{casilla_id}: casillas source directory is missing or unsafe",
        )
        return None

    matches: list[Path] = []
    try:
        candidates = sorted(casillas_root.iterdir(), key=lambda path: path.name)
    except OSError as error:
        _add_refusal(
            refusals,
            seen_refusals,
            f"{revision_id}/{casilla_id}: cannot enumerate casillas source directory: {error}",
        )
        return None
    for path in candidates:
        if path.suffix.lower() != ".toml":
            continue
        if path.is_symlink() or _safe_resolve(path, modelo_root) is None:
            _add_refusal(
                refusals,
                seen_refusals,
                f"{revision_id}/{casilla_id}: unsafe casilla fragment path {path}",
            )
            continue
        try:
            document = tomllib.loads(path.read_text(encoding=UTF_8_ENCODING))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
            _add_refusal(
                refusals,
                seen_refusals,
                f"{revision_id}/{casilla_id}: cannot parse casilla fragment {path}: {error}",
            )
            continue
        tables = _raw_casilla_tables(document, revision_id)
        if any(str(table.get("id", "")) == casilla_id for table in tables):
            matches.append(path)

    if len(matches) != 1:
        detail = "no source-native casilla fragment found" if not matches else f"{len(matches)} fragments found"
        _add_refusal(refusals, seen_refusals, f"{revision_id}/{casilla_id}: {detail}")
        return None
    return matches[0]


def _origin_value(value: object) -> str | None:
    """Read an enum or raw lineage origin as its canonical token."""
    if value is None:
        return None
    token = getattr(value, "value", value)
    return str(token)


def _source_refs_are_grounded(refs: tuple[str, ...]) -> bool:
    """Require a non-empty list of non-blank source catalogue ids."""
    return bool(refs) and all(isinstance(ref, str) and bool(ref.strip()) for ref in refs)


def _grounded_row_evidence(pair: EvolutionPair, earlier: AeipOccurrence, later: AeipOccurrence) -> str:
    """Render deterministic, source-backed evidence for a grounded successor row."""
    refs = _merge_source_refs(earlier, later)
    if not _source_refs_are_grounded(refs):
        raise AeipError(
            f"{pair.chain_id} {pair.from_revision}->{pair.to_revision}: missing authoritative source refs",
        )
    evidence = (
        f"AEAT Diseño de Registros sources {', '.join(refs)}: Modelo 100 "
        f"{earlier.revision_id}/{earlier.casilla_id} and {later.revision_id}/{later.casilla_id} "
        f"resolve the adjudicated AEIP programme {later.title!r}; transition classified "
        f"{pair.evolution_kind} from the official Spanish labels."
    )
    if len(evidence) > 1024:
        raise AeipError(
            f"{pair.chain_id} {pair.from_revision}->{pair.to_revision}: grounded evidence exceeds 1024 characters",
        )
    return evidence


def _pair_endpoints(entry: ChainPlanEntry, pair: EvolutionPair) -> tuple[AeipOccurrence, AeipOccurrence | None] | None:
    """Return the source and target occurrences represented by an evolution pair."""
    earlier = [occurrence for occurrence in entry.occurrences if occurrence.revision_id == pair.from_revision]
    if len(earlier) != 1:
        return None
    if pair.evolution_kind == "retired":
        return earlier[0], None
    later = [occurrence for occurrence in entry.occurrences if occurrence.revision_id == pair.to_revision]
    if len(later) != 1:
        return None
    return earlier[0], later[0]


def _evolution_core(record: object) -> tuple[str, str, str, str] | None:
    """Get the identity-bearing fields from a loaded evolution record."""
    values: list[str] = []
    for field_name in ("continuidad_id", "from_revision", "to_revision", "evolution_kind"):
        value = getattr(record, field_name, None)
        if value is None:
            return None
        values.append(str(getattr(value, "value", value)))
    if len(values) != 4:
        return None
    return values[0], values[1], values[2], values[3]


def _expected_evolution_id(modelo_id: str, casilla_id: str, pair: EvolutionPair) -> str:
    """Use the loader's source-native record identity convention."""
    return f"m{modelo_id}-{casilla_id}-{pair.from_revision}-{pair.to_revision}-{pair.evolution_kind}"


def _safe_evolution_filename(casilla_id: str, pair: EvolutionPair) -> str | None:
    """Return a source-native filename only for safe single-component fields."""
    tokens = (casilla_id, pair.from_revision, pair.to_revision, pair.evolution_kind)
    if any(re.fullmatch(r"[A-Za-z0-9_-]+", token) is None for token in tokens):
        return None
    # Loader-owned continuity fragment names are dot/dash filenames; the
    # schema's evolution token keeps underscores.  Match existing source-native
    # files (``legal-refs-evolved.toml``) without changing the record token.
    kind_filename = pair.evolution_kind.replace("_", "-")
    return f"{casilla_id}-{pair.from_revision}-{pair.to_revision}-{kind_filename}.toml"


def prepare_apply(
    modelos_root: Path,
    inventory: AeipInventory,
    plan: ChainPlan,
    adjudications: AdjudicationSet,
    *,
    modelo_id: str = "100",
) -> AeipApplyPlan:
    """Preflight an idempotent AEIP write against the current Modelo 100 tree.

    No file is written here.  Every refusal is retained in the returned plan;
    callers must inspect ``ready`` before invoking :func:`apply_prepared_plan`.
    """
    stamp_writes: list[AeipStampWrite] = []
    evolution_writes: list[AeipEvolutionWrite] = []
    refusals: list[str] = []
    seen_refusals: set[str] = set()
    if modelo_id != "100":
        _add_refusal(refusals, seen_refusals, f"AEIP apply is restricted to Modelo 100, not {modelo_id!r}")

    try:
        base_root = modelos_root.resolve()
    except OSError as error:
        _add_refusal(refusals, seen_refusals, f"cannot resolve modelos root: {error}")
        return AeipApplyPlan((), (), 0, 0, 0, tuple(refusals))
    modelo_root = _safe_resolve(base_root / modelo_id, base_root)
    if modelo_root is None or not modelo_root.is_dir():
        _add_refusal(refusals, seen_refusals, f"Modelo {modelo_id} registry path is missing or unsafe")
        return AeipApplyPlan((), (), 0, 0, 0, tuple(refusals))

    for ambiguity in plan.ambiguities:
        _add_refusal(refusals, seen_refusals, f"ambiguity [{ambiguity.kind}] {ambiguity.detail}")
    for stale in detect_stale_adjudications(inventory, adjudications):
        _add_refusal(refusals, seen_refusals, f"stale adjudication [{stale.kind}] {stale.detail}")

    try:
        definition = load_modelo_directory(modelo_root)
    except RegistryLoadError as error:
        _add_refusal(refusals, seen_refusals, f"Modelo {modelo_id} canonical load failed: {error}")
        return AeipApplyPlan((), (), 0, 0, 0, tuple(refusals))

    current_rows: dict[tuple[str, str], Any] = {}
    for revision in definition.revisions.values():
        for casilla in revision.casillas:
            key = (str(revision.id), str(casilla.id))
            if key in current_rows:
                _add_refusal(refusals, seen_refusals, f"duplicate loaded casilla {key[0]}/{key[1]}")
            current_rows[key] = casilla

    planned_rows: dict[tuple[str, str], tuple[str, bool, AeipOccurrence]] = {}
    pair_endpoints: list[tuple[ChainPlanEntry, EvolutionPair, AeipOccurrence, AeipOccurrence | None]] = []
    for entry in plan.entries:
        if entry.chain_id in {existing[0] for existing in planned_rows.values()}:
            _add_refusal(refusals, seen_refusals, f"duplicate planned AEIP chain id {entry.chain_id!r}")
        for index, occurrence in enumerate(entry.occurrences):
            key = (str(occurrence.revision_id), str(occurrence.casilla_id))
            if key in planned_rows:
                _add_refusal(refusals, seen_refusals, f"duplicate planned AEIP occurrence {key[0]}/{key[1]}")
            planned_rows[key] = (entry.chain_id, index > 0, occurrence)
        for pair in entry.pairs:
            endpoints = _pair_endpoints(entry, pair)
            if endpoints is None:
                _add_refusal(
                    refusals,
                    seen_refusals,
                    f"{entry.chain_id} {pair.from_revision}->{pair.to_revision}: cannot localize pair endpoints",
                )
                continue
            pair_endpoints.append((entry, pair, endpoints[0], endpoints[1]))

    existing_stamps = 0
    from dev.registry.analysis.casilla_lineage_seed import insert_lineage_keys

    for key, (chain_id, is_successor, occurrence) in sorted(planned_rows.items()):
        current = current_rows.get(key)
        if current is None:
            _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} is absent from canonical Modelo 100 load")
            continue
        if (
            ANEXO_A_SECTION_LEAF not in tuple(current.section or ())
            or str(current.semantic_role or "") != EVENT_SEMANTIC_ROLE
        ):
            _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} is no longer an AEIP event row")
        try:
            current_label = current.get_label(SOURCE_LOCALE)
        except MissingTranslationError:
            current_label = ""
        if (
            current_label != occurrence.label
            or tuple(str(item) for item in current.localization_keys) != occurrence.localization_keys
        ):
            _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} label/localization changed since adjudication")
        if tuple(str(item) for item in current.legal_refs) != occurrence.legal_refs:
            _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} legal refs changed since adjudication")
        current_sources = tuple(str(item) for item in current.source_refs)
        if not _source_refs_are_grounded(current_sources):
            _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} has no authoritative source refs")
        elif current_sources != occurrence.source_refs:
            _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} source refs changed since adjudication")

        current_id = None if current.continuidad_id is None else str(current.continuidad_id)
        current_origin = _origin_value(current.continuidad_origin)
        current_evidence = current.continuidad_evidence
        if current_id == chain_id:
            existing_stamps += 1
        elif current_id is not None:
            _add_refusal(
                refusals,
                seen_refusals,
                f"{key[0]}/{key[1]} already carries conflicting continuidad_id {current_id!r}",
            )

        expected: dict[str, str] = {"continuidad_id": chain_id}
        if is_successor:
            endpoint = next(
                (
                    (earlier, later, pair)
                    for entry, pair, earlier, later in pair_endpoints
                    if entry.chain_id == chain_id and later is not None and later.revision_id == occurrence.revision_id
                ),
                None,
            )
            if endpoint is None:
                _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} has no grounded predecessor pair")
            else:
                evidence = _grounded_row_evidence(endpoint[2], endpoint[0], endpoint[1])
                expected.update(continuidad_origin="grounded", continuidad_evidence=evidence)
            if current_origin == "grounded":
                if not isinstance(current_evidence, str) or not current_evidence.strip():
                    _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} grounded origin has empty evidence")
                # Existing grounded evidence is preserved; it may carry a
                # more precise official citation than the deterministic plan.
            elif current_origin is not None:
                _add_refusal(
                    refusals,
                    seen_refusals,
                    f"{key[0]}/{key[1]} carries conflicting continuity origin {current_origin!r}",
                )
            elif current_evidence is not None:
                _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} carries evidence without grounded origin")
        else:
            if current_origin is not None or current_evidence is not None:
                _add_refusal(
                    refusals,
                    seen_refusals,
                    f"{key[0]}/{key[1]} chain root already carries origin/evidence",
                )

        missing = {
            field: value
            for field, value in expected.items()
            if (field == "continuidad_id" and current_id is None)
            or (field == "continuidad_origin" and current_origin is None)
            or (field == "continuidad_evidence" and current_evidence is None)
        }
        # The condition above is intentionally explicit about each field, but
        # use a second conflict check so an existing value can never be
        # silently replaced by an insertion helper.
        if current_id is not None and current_id == expected.get("continuidad_id"):
            missing.pop("continuidad_id", None)
        if current_origin is not None and current_origin == expected.get("continuidad_origin"):
            missing.pop("continuidad_origin", None)
        if current_evidence is not None and "continuidad_evidence" in expected:
            missing.pop("continuidad_evidence", None)
        if missing:
            path = _locate_casilla_file(modelo_root, key[0], key[1], refusals, seen_refusals)
            if path is not None:
                try:
                    raw_text = path.read_text(encoding=UTF_8_ENCODING)
                    _, done = insert_lineage_keys(raw_text, key[0], {key[1]: missing})
                except (OSError, UnicodeError, ValueError) as error:
                    _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} lineage insertion refused: {error}")
                else:
                    if done != {key[1]}:
                        _add_refusal(
                            refusals, seen_refusals, f"{key[0]}/{key[1]} was not uniquely located by insertion helper"
                        )
                    else:
                        stamp_writes.append(
                            AeipStampWrite(
                                path=path,
                                revision_id=key[0],
                                casilla_id=key[1],
                                keys=tuple(missing.items()),
                            ),
                        )

    planned_keys = set(planned_rows)
    for occurrence in inventory.occurrences:
        key = (str(occurrence.revision_id), str(occurrence.casilla_id))
        if key in planned_keys:
            continue
        current = current_rows.get(key)
        if current is not None and current.continuidad_id is not None:
            _add_refusal(
                refusals,
                seen_refusals,
                f"{key[0]}/{key[1]} carries AEIP continuidad_id outside the adjudicated plan",
            )
    # Category rows share the Anexo-A table but are deliberately not event
    # occurrences. They must never acquire an event chain by accident.
    for key, current in current_rows.items():
        if key in planned_keys or ANEXO_A_SECTION_LEAF not in tuple(current.section or ()):
            continue
        category_chain = None if current.continuidad_id is None else str(current.continuidad_id)
        if (
            str(current.semantic_role or "") == CATEGORY_SEMANTIC_ROLE
            and category_chain
            and category_chain.startswith(CHAIN_PREFIX)
        ):
            _add_refusal(
                refusals,
                seen_refusals,
                f"{key[0]}/{key[1]} category row carries an AEIP continuidad_id outside the plan",
            )

    chain_ids = {entry.chain_id for entry in plan.entries}
    desired: dict[tuple[str, str, str, str], tuple[ChainPlanEntry, EvolutionPair, str]] = {}
    for entry, pair, earlier, later in pair_endpoints:
        endpoint = earlier if later is None else later
        if not _source_refs_are_grounded(pair.source_refs):
            _add_refusal(
                refusals,
                seen_refusals,
                f"{pair.chain_id} {pair.from_revision}->{pair.to_revision}: evolution has no authoritative source refs",
            )
        if not pair.legal_refs:
            _add_refusal(
                refusals,
                seen_refusals,
                f"{pair.chain_id} {pair.from_revision}->{pair.to_revision}: evolution has no legal refs",
            )
        core = (pair.chain_id, pair.from_revision, pair.to_revision, pair.evolution_kind)
        if core in desired:
            _add_refusal(refusals, seen_refusals, f"duplicate planned evolution {core!r}")
        desired[core] = (entry, pair, endpoint.casilla_id)

    existing_by_core: dict[tuple[str, str, str, str], list[Any]] = defaultdict(list)
    for revision_id, revision in definition.revisions.items():
        for record in revision.casilla_continuidad_evolutions:
            core = _evolution_core(record)
            if core is None or not core[0].startswith(CHAIN_PREFIX):
                continue
            existing_by_core[core].append((str(revision_id), record))
            if str(record.to_revision) != str(revision_id):
                _add_refusal(
                    refusals,
                    seen_refusals,
                    f"evolution {record.id!s} is materialized under {revision_id!r} but targets {record.to_revision!s}",
                )

    existing_evolutions = sum(len(records) for core, records in existing_by_core.items() if core in desired)
    unexpected_evolutions = sum(len(records) for core, records in existing_by_core.items() if core not in desired)
    for core, (entry, pair, casilla_id) in sorted(desired.items()):
        records = existing_by_core.get(core, [])
        if len(records) > 1:
            _add_refusal(refusals, seen_refusals, f"duplicate existing evolution {core!r}")
        if records:
            _, record = records[0]
            expected_id = _expected_evolution_id(modelo_id, casilla_id, pair)
            if str(record.id) != expected_id:
                _add_refusal(refusals, seen_refusals, f"evolution {core!r} has conflicting id {record.id!s}")
            if tuple(str(ref) for ref in record.legal_refs) != tuple(pair.legal_refs):
                _add_refusal(refusals, seen_refusals, f"evolution {core!r} legal refs conflict with adjudicated plan")
            if not _source_refs_are_grounded(tuple(str(ref) for ref in record.source_refs)):
                _add_refusal(refusals, seen_refusals, f"evolution {core!r} has empty source refs")
            continue
        filename = _safe_evolution_filename(casilla_id, pair)
        if filename is None:
            _add_refusal(refusals, seen_refusals, f"evolution {core!r} has unsafe source-native filename fields")
            continue
        target_dir_candidate = modelo_root / "revisions" / pair.to_revision / "casilla_continuidad_evolutions"
        if target_dir_candidate.is_symlink():
            _add_refusal(refusals, seen_refusals, f"evolution {core!r} target directory is a symlink")
            continue
        target_dir = _safe_resolve(target_dir_candidate, modelo_root)
        if target_dir is None or not target_dir.is_dir():
            _add_refusal(refusals, seen_refusals, f"evolution {core!r} target directory is missing or unsafe")
            continue
        path = _safe_resolve(target_dir / filename, modelo_root)
        if path is None or (path.exists() and path.is_symlink()):
            _add_refusal(refusals, seen_refusals, f"evolution {core!r} target file is unsafe")
            continue
        content = render_evolution_record(pair, casilla_id=casilla_id, modelo_id=modelo_id) + "\n"
        try:
            parsed = tomllib.loads(content)
        except tomllib.TOMLDecodeError as error:
            _add_refusal(refusals, seen_refusals, f"evolution {core!r} rendered invalid TOML: {error}")
            continue
        revision_table = parsed.get("revisions", {}).get(pair.to_revision, {})
        records_rendered = (
            revision_table.get("casilla_continuidad_evolutions", ()) if isinstance(revision_table, dict) else ()
        )
        record_rendered = (
            records_rendered[0] if isinstance(records_rendered, list) and len(records_rendered) == 1 else None
        )
        if not isinstance(record_rendered, dict) or record_rendered.get("id") != _expected_evolution_id(
            modelo_id, casilla_id, pair
        ):
            _add_refusal(refusals, seen_refusals, f"evolution {core!r} rendered identity does not round-trip")
            continue
        if not record_rendered.get("source_refs"):
            _add_refusal(refusals, seen_refusals, f"evolution {core!r} rendered without source refs")
            continue
        if path.exists():
            try:
                existing_text = path.read_text(encoding=UTF_8_ENCODING)
            except (OSError, UnicodeError) as error:
                _add_refusal(refusals, seen_refusals, f"evolution {core!r} cannot read colliding target: {error}")
            else:
                if existing_text != content:
                    _add_refusal(
                        refusals, seen_refusals, f"evolution {core!r} collides with different existing file {path}"
                    )
                # An exact pre-existing file is idempotent; the canonical load
                # should normally have counted it above, but preserving it is
                # safer than scheduling a duplicate write.
            continue
        evolution_writes.append(AeipEvolutionWrite(path=path, pair=pair, casilla_id=casilla_id, content=content))

    paths = [write.path for write in stamp_writes] + [write.path for write in evolution_writes]
    if len(paths) != len(set(paths)):
        _add_refusal(refusals, seen_refusals, "apply plan contains duplicate target paths")

    return AeipApplyPlan(
        stamp_writes=tuple(stamp_writes),
        evolution_writes=tuple(evolution_writes),
        existing_stamps=existing_stamps,
        existing_evolutions=existing_evolutions,
        unexpected_evolutions=unexpected_evolutions,
        refusals=tuple(refusals),
    )


def apply_prepared_plan(plan: AeipApplyPlan) -> tuple[int, int]:
    """Apply a ready plan after re-reading every target for concurrent edits."""
    if not plan.ready:
        raise AeipError("refusing AEIP apply because preflight has refusals: " + "; ".join(plan.refusals))
    from dev.registry.analysis.casilla_lineage_seed import insert_lineage_keys

    stamp_rows = 0
    by_path: dict[Path, list[AeipStampWrite]] = defaultdict(list)
    for write in plan.stamp_writes:
        by_path[write.path].append(write)
    for path, writes in sorted(by_path.items(), key=lambda item: str(item[0])):
        if path.is_symlink() or not path.is_file():
            raise AeipError(f"concurrent AEIP casilla target became missing or unsafe: {path}")
        try:
            current_text = path.read_text(encoding=UTF_8_ENCODING)
        except (OSError, UnicodeError) as error:
            raise AeipError(f"cannot re-read AEIP casilla target {path}: {error}") from error
        edits = {write.casilla_id: write.key_map for write in writes}
        try:
            new_text, done = insert_lineage_keys(current_text, writes[0].revision_id, edits)
        except ValueError as error:
            raise AeipError(f"concurrent AEIP casilla change conflicts at {path}: {error}") from error
        expected = set(edits)
        if done != expected:
            raise AeipError(
                f"concurrent AEIP casilla change moved rows at {path}: expected {sorted(expected)}, got {sorted(done)}"
            )
        if new_text != current_text:
            atomic_write_text(path, new_text, encoding=UTF_8_ENCODING)
            stamp_rows += len(done)

    evolution_records = 0
    for write in plan.evolution_writes:
        path = write.path
        if path.parent.is_symlink() or path.is_symlink():
            raise AeipError(f"concurrent AEIP evolution target became symlink: {path}")
        if path.exists():
            try:
                current = path.read_text(encoding=UTF_8_ENCODING)
            except (OSError, UnicodeError) as error:
                raise AeipError(f"cannot re-read AEIP evolution target {path}: {error}") from error
            if current != write.content:
                raise AeipError(f"concurrent AEIP evolution change conflicts at {path}")
            continue
        atomic_write_text(path, write.content, encoding=UTF_8_ENCODING)
        evolution_records += 1
    return stamp_rows, evolution_records
