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
evolution records a grounding campaign would author. It is a *planner*: nothing
here writes into the registry.

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
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

from cadrumo.core.i18n import MissingTranslationError
from cadrumo.domain.calculations.registry import RegistryLoadError, load_modelo_directory

from .adjudications import AdjudicationSet

__all__ = [
    "AeipAmbiguity",
    "AeipError",
    "AeipEvent",
    "AeipInventory",
    "AeipOccurrence",
    "ChainPlan",
    "ChainPlanEntry",
    "EvolutionPair",
    "build_inventory",
    "chain_id_for",
    "derive_slug",
    "extract_occurrences",
    "plan_chains",
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
CHAIN_ID_MAX_LENGTH = 128
CHAIN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:-]*[a-z0-9]$|^[a-z0-9]$")

_APLICADO_SUFFIX = re.compile(r":\s*Aplicado en esta declaraci[oó]n\s*$", re.IGNORECASE)
_WRAPPING_QUOTES = re.compile(r"^\s*[“”«»\"](?P<title>.+?)[“”«»\"]\s*$")
_WHITESPACE = re.compile(r"\s+")
_YEAR_TOKEN = re.compile(r"(19|20)\d{2}")
_NON_SLUG = re.compile(r"[^a-z0-9]+")
_SLUG_RUNS = re.compile(r"-{2,}")


class AeipError(RuntimeError):
    """Raised when the AEIP family cannot be read or planned."""


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
    return (wrapped.group("title") if wrapped else core).strip()


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
        elif not CHAIN_ID_PATTERN.match(chain_id):
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
    source_refs: tuple[str, ...] = (),
) -> str:
    """Render one evolution record fragment for review.

    The output is a preview an operator reads and lands deliberately; this
    module never writes into the registry. ``legal_refs`` defaults to the refs
    the pair carries at its target revision; ``source_refs`` must cite what was
    actually consulted there, so it is supplied by the caller rather than
    guessed here.
    """
    refs = ", ".join(f'"{ref}"' for ref in (pair.legal_refs if legal_refs is None else legal_refs))
    sources = ", ".join(f'"{ref}"' for ref in source_refs)
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
