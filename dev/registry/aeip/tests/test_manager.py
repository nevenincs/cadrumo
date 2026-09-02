"""Real-corpus tests for the anexo-A AEIP continuity planner.

Every test runs against the shipped registry, loaded the way production loads
it, with programme titles resolved from the shared locale catalogues rather
than read out of the schema.

Counts that would drift when a new filing year is authored are asserted as
invariants -- a chain id is well-formed and survives locale-key encoding, a gap
is refused, an adjudication changes the plan -- rather than as frozen totals, so
a 2026 revision extends the family without reddening the suite. The two things
pinned exactly are the revision set and the already-landed chain id; both are
deliberate and cheap to update.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from cadrumo.core.identity import ContinuidadId
from cadrumo.domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_continuity_locale_key,
    casilla_occurrence_locale_key,
)

from ...._paths import REPO_ROOT as _REPO_ROOT
from ..adjudications import (
    AdjudicationError,
    AdjudicationSet,
    Exclusion,
    Split,
    TitleAlias,
    VariantsDistinct,
    load_adjudications,
)
from ..manager import (
    CATEGORY_SEMANTIC_ROLE,
    EVENT_SEMANTIC_ROLE,
    AeipOccurrence,
    EvolutionPair,
    build_inventory,
    chain_id_for,
    derive_slug,
    extract_occurrences,
    plan_chains,
    render_evolution_record,
)

# The family is read from the shipped registry authoring tree on disk.
pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

# The chain-id constraint is imported from the registry schema rather than
# restated here, so a change to the real annotation fails this gate instead of
# silently diverging from a copied regex.
_CHAIN_ID_ADAPTER = TypeAdapter(ContinuidadId)

# The chain H1 already stamped into the corpus. The scheme must reproduce it
# exactly, or the scheme supersedes a landed stamp without saying so.
_LANDED_CHAIN_ID = "irpf-aeip-centenario-del-hockey-1923-2023-aplicado"


_MODELOS_ROOT = _REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"
_SHIPPED_ADJUDICATIONS = Path(__file__).resolve().parents[1] / "adjudications.toml"


@pytest.fixture(scope="module")
def modelos_root() -> Path:
    """The registry authoring tree the loader reads.

    The programme titles no longer live here -- the schema carries only locale
    keys and the text resolves from the shared catalogues -- so this fixture
    points the loader at the real tree and lets the canonical resolution path
    supply the labels.
    """
    return _MODELOS_ROOT


@pytest.fixture(scope="module")
def corpus(modelos_root: Path) -> tuple[tuple[AeipOccurrence, ...], dict[str, int]]:
    """The raw anexo-A occurrences and category-row counts read from ``HEAD``."""
    return extract_occurrences(modelos_root)


@pytest.fixture(scope="module")
def inventory(corpus):
    """The occurrences grouped into programmes, with nothing adjudicated."""
    occurrences, category_counts = corpus
    return build_inventory(occurrences, category_row_counts=category_counts)


@pytest.fixture(scope="module")
def adjudicated(corpus):
    """The family as the shipped judgments resolve it.

    Exclusions and aliases act while occurrences are grouped, so the shipped
    adjudications have to be supplied to ``build_inventory`` as well as to
    ``plan_chains``; an inventory built without them still shows the duplicate
    and the year-variant pair.
    """
    occurrences, category_counts = corpus
    adjudications = load_adjudications(_SHIPPED_ADJUDICATIONS)
    inventory = build_inventory(
        occurrences,
        adjudications=adjudications,
        category_row_counts=category_counts,
    )
    return inventory, plan_chains(inventory, adjudications=adjudications), adjudications


def test_extraction_reads_every_revision_of_the_family(inventory) -> None:
    """Every M100 revision carrying the family is read."""
    assert inventory.revisions == ("2020", "2021", "2022", "2023", "2024", "2025")
    assert inventory.occurrences, "the anexo-A AEIP family must not be empty"
    assert len(inventory.events) > 1
    # Category rows are counted but never enrolled as programmes.
    assert set(inventory.category_row_counts) == set(inventory.revisions)


def test_every_occurrence_carries_a_parsed_programme_title(inventory) -> None:
    """The resolved Spanish label is this family's only identity signal.

    Nothing else in an anexo-A event row distinguishes one programme from
    another: the ids repack yearly, the ``semantic_role`` is shared by the
    whole family, and the ``legal_refs`` vary only by revision, never by
    programme. The titles live in the shared locale catalogues rather than in
    the schema, so this gate is what catches a key that stops resolving -- an
    unenrolled occurrence, a dropped catalogue leaf, a renamed key -- while it
    is still a loud failure rather than a silently unkeyable programme.
    """
    assert inventory.events, "the family must resolve to at least one programme"
    assert not inventory.untitled_occurrences, (
        f"{len(inventory.untitled_occurrences)} anexo-A event rows carry no parsable "
        "programme title; the event-keyed scheme has lost its identity source"
    )
    # The title is the label minus the single published column suffix, so it
    # must never still carry it.
    assert not any("Aplicado en esta declaraci" in occ.title for occ in inventory.occurrences)


def test_derived_chain_ids_satisfy_the_registry_continuidad_constraint(inventory) -> None:
    """Chain ids the planner emits must validate as real ``ContinuidadId``s."""
    plan = plan_chains(inventory)
    assert plan.entries, "expected at least one planned chain"
    for entry in plan.entries:
        _CHAIN_ID_ADAPTER.validate_python(entry.chain_id)
        assert entry.chain_id.startswith("irpf-aeip-")
        assert entry.chain_id.endswith("-aplicado")


def test_chain_id_keeps_its_continuity_locale_key_readable() -> None:
    """The chain id must survive locale-key encoding without being mangled.

    A chain id is embedded whole into its continuity locale key, and
    ``encode_modelo_locale_segment`` base32-encodes any segment outside
    ``[A-Za-z0-9_-]``. A dotted chain id therefore turns its own key into an
    opaque ``x-...`` blob that no translator can read, which is why this family
    is keyed with hyphens. This is the gate on that decision.
    """
    kebab = chain_id_for("centenario-del-hockey-1923-2023")
    key = casilla_continuity_locale_key("100", kebab, ModeloLocalizationFieldKind.LABEL)
    assert kebab in key, "the chain id must appear verbatim in its locale key"
    assert ".x-" not in key, f"chain id was base32-encoded into an opaque key: {key}"

    # The refutation: the dotted form this scheme rejects really does mangle.
    dotted = "irpf.aeip.centenario-del-hockey-1923-2023.aplicado"
    assert ".x-" in casilla_continuity_locale_key("100", dotted, ModeloLocalizationFieldKind.LABEL)


def test_every_planned_chain_id_survives_locale_key_encoding(inventory) -> None:
    """No planned chain id may produce an encoded continuity key."""
    plan = plan_chains(inventory)
    assert plan.entries
    for entry in plan.entries:
        key = casilla_continuity_locale_key("100", entry.chain_id, ModeloLocalizationFieldKind.LABEL)
        assert ".x-" not in key, f"{entry.chain_id} encodes to {key}"


def test_grounding_collapses_per_revision_keys_onto_one_concept(adjudicated) -> None:
    """A chain's payoff on the locale surface is measurable, not asserted.

    Every occurrence spends one per-revision locale key. Grounding adds a single
    continuity key the resolver prefers, so a chain of N occurrences collapses N
    translatable keys onto one concept.
    """
    _, plan, _ = adjudicated
    assert plan.complete, "the shipped adjudications must leave nothing open"
    occurrence_keys = {
        casilla_occurrence_locale_key("100", occ.revision_id, occ.casilla_id, ModeloLocalizationFieldKind.LABEL)
        for entry in plan.entries
        for occ in entry.occurrences
    }
    continuity_keys = {
        casilla_continuity_locale_key("100", entry.chain_id, ModeloLocalizationFieldKind.LABEL)
        for entry in plan.entries
    }
    assert len(continuity_keys) == len(plan.entries)
    assert len(occurrence_keys) > len(continuity_keys), (
        "grounding must reduce the translatable key count, or the chain earns nothing"
    )


def test_shipped_adjudications_resolve_every_ambiguity(adjudicated) -> None:
    """The four recorded judgments leave the family fully plannable."""
    _, plan, adjudications = adjudicated
    assert plan.ambiguities == (), f"still open: {[a.kind for a in plan.ambiguities]}"
    # And they are grounded: every recorded judgment states its evidence.
    recorded = (
        *adjudications.exclusions,
        *adjudications.aliases,
        *adjudications.chain_ids,
        *adjudications.splits,
        *adjudications.distinct_variants,
    )
    assert recorded, "expected recorded adjudications"
    for entry in recorded:
        assert len(entry.reason.strip()) > 40, f"adjudication reason is too thin to audit: {entry}"


def test_oversize_title_on_a_single_revision_programme_is_not_blocked(inventory) -> None:
    """An over-long title only matters if the programme actually gets a chain.

    The two titles that exceed the budget are both single-revision programmes,
    so they are never stamped and demand no decision. Blocking on them would
    require an adjudication that changes nothing.
    """
    plan = plan_chains(inventory)
    oversize_slugs = {slug for a in plan.ambiguities if a.kind == "oversize_chain_id" for slug in a.slugs}
    for slug in oversize_slugs:
        event = inventory.event_by_slug(slug)
        assert event is not None
        assert event.spans_multiple_revisions, f"{slug} is single-revision and must not block"


def test_oversize_slug_is_refused_by_the_real_constraint() -> None:
    """The length guard is not decorative: the schema rejects the long form."""
    oversize = chain_id_for("x" * 200)
    with pytest.raises(ValidationError):
        _CHAIN_ID_ADAPTER.validate_python(oversize)


def test_scheme_reproduces_the_already_landed_chain(inventory) -> None:
    """The scheme must not silently supersede a chain already stamped."""
    plan = plan_chains(inventory)
    planned = {entry.chain_id for entry in plan.entries}
    assert _LANDED_CHAIN_ID in planned, (
        "the event-keyed scheme must reproduce the chain already stamped in the "
        "corpus, or it silently supersedes a landed grounding decision"
    )
    stamped = {occ.continuidad_id for occ in inventory.occurrences if occ.continuidad_id}
    assert stamped <= planned, f"stamped chains absent from the plan: {stamped - planned}"


def test_planner_fails_closed_on_unadjudicated_ambiguity(inventory) -> None:
    """With nothing adjudicated, the known ambiguity classes are reported."""
    plan = plan_chains(inventory)
    assert not plan.complete
    kinds = {ambiguity.kind for ambiguity in plan.ambiguities}
    assert kinds <= {"gapped_span", "intra_revision_duplicate", "oversize_chain_id", "title_variant"}
    assert kinds, "the corpus is known to carry open ambiguities"
    # A blocked programme is never planned as a chain.
    blocked = {slug for ambiguity in plan.ambiguities for slug in ambiguity.slugs}
    planned_slugs = {entry.chain_id for entry in plan.entries}
    for slug in blocked:
        assert chain_id_for(slug) not in planned_slugs


def test_gapped_programme_is_refused_until_split(inventory) -> None:
    """A present-absent-present programme blocks, and a split unblocks it."""
    plan = plan_chains(inventory)
    gapped = [a for a in plan.ambiguities if a.kind == "gapped_span"]
    assert gapped, "the corpus carries a known gapped programme"
    slug = gapped[0].slugs[0]
    event = inventory.event_by_slug(slug)
    assert event is not None
    resumption = event.revisions[-1]

    resolved = plan_chains(
        inventory,
        adjudications=AdjudicationSet(
            splits=(
                Split(
                    slug=slug,
                    from_revision=resumption,
                    chain_id=f"irpf-aeip-{slug}-{resumption}-aplicado",
                    reason="test: later window is a fresh designation",
                ),
            ),
        ),
    )
    assert not [a for a in resolved.ambiguities if a.kind == "gapped_span" and slug in a.slugs]
    # The earlier window keeps the clean id; only the later window is qualified.
    ids = {entry.chain_id for entry in resolved.entries}
    assert chain_id_for(slug) in ids


def test_exclusion_removes_an_intra_revision_duplicate(inventory, corpus) -> None:
    """Excluding the spurious occurrence clears the duplicate ambiguity."""
    occurrences, category_counts = corpus
    plan = plan_chains(inventory)
    duplicates = [a for a in plan.ambiguities if a.kind == "intra_revision_duplicate"]
    assert duplicates, "the corpus carries a known intra-revision duplicate"
    slug = duplicates[0].slugs[0]
    event = inventory.event_by_slug(slug)
    assert event is not None

    per_revision: dict[str, list[AeipOccurrence]] = {}
    for occurrence in event.occurrences:
        per_revision.setdefault(occurrence.revision_id, []).append(occurrence)
    revision, rows = next((rev, r) for rev, r in per_revision.items() if len(r) > 1)
    victim = sorted(rows, key=lambda row: row.casilla_id)[0]

    resolved_inventory = build_inventory(
        occurrences,
        adjudications=AdjudicationSet(
            exclusions=(
                Exclusion(revision=revision, casilla=victim.casilla_id, reason="test: transcription duplicate"),
            ),
        ),
        category_row_counts=category_counts,
    )
    resolved = plan_chains(resolved_inventory)
    assert not [a for a in resolved.ambiguities if a.kind == "intra_revision_duplicate" and slug in a.slugs]
    assert len(resolved_inventory.occurrences) == len(occurrences), "extraction is untouched by adjudication"


def test_alias_folds_title_variants_into_one_chain(inventory, corpus) -> None:
    """An alias merges year-variant titles into one multi-revision programme."""
    occurrences, category_counts = corpus
    plan = plan_chains(inventory)
    variants = [a for a in plan.ambiguities if a.kind == "title_variant"]
    assert variants, "the corpus carries known year-variant titles"
    group = variants[0]
    titles = tuple(event.title for slug in group.slugs if (event := inventory.event_by_slug(slug)) is not None)
    merged_slug = "test-merged-programme"

    resolved_inventory = build_inventory(
        occurrences,
        adjudications=AdjudicationSet(
            aliases=(TitleAlias(slug=merged_slug, titles=titles, reason="test: one relabelled programme"),),
        ),
        category_row_counts=category_counts,
    )
    merged = resolved_inventory.event_by_slug(merged_slug)
    assert merged is not None
    assert len(merged.revisions) >= 2, "folding the variants must produce one multi-revision programme"


def test_distinct_variants_keeps_two_programmes_apart(inventory) -> None:
    """Recording variants as distinct clears the ambiguity without merging."""
    plan = plan_chains(inventory)
    variants = [a for a in plan.ambiguities if a.kind == "title_variant"]
    assert variants
    group = variants[0]
    resolved = plan_chains(
        inventory,
        adjudications=AdjudicationSet(
            distinct_variants=(VariantsDistinct(slugs=group.slugs, reason="test: successive designations"),),
        ),
    )
    assert not [a for a in resolved.ambiguities if a.kind == "title_variant" and set(a.slugs) == set(group.slugs)]


def test_retirement_is_planned_for_a_programme_that_left_the_form(inventory) -> None:
    """A programme whose window closed ends its chain with a retirement."""
    plan = plan_chains(inventory)
    retirements = [pair for entry in plan.entries for pair in entry.pairs if pair.evolution_kind == "retired"]
    assert retirements, "programmes whose window closed must end with a retirement"
    newest = inventory.revisions[-1]
    for pair in retirements:
        assert pair.to_revision != pair.from_revision
        # A retirement never targets a revision beyond the tree.
        assert pair.to_revision in inventory.revisions
        assert pair.to_revision <= newest


def _assert_all_contiguous(inventory, plan) -> None:
    order = {revision: index for index, revision in enumerate(inventory.revisions)}
    for entry in plan.entries:
        indexes = sorted(order[occ.revision_id] for occ in entry.occurrences)
        assert indexes == list(range(indexes[0], indexes[0] + len(indexes))), f"{entry.chain_id} spans a gap"


def test_every_planned_chain_is_contiguous(inventory) -> None:
    """The planner must never emit a chain the contiguity policy would refuse."""
    _assert_all_contiguous(inventory, plan_chains(inventory))


def test_a_misplaced_split_is_refused_rather_than_emitting_a_gapped_chain(inventory) -> None:
    """A split that does not land on the gap must re-block, not plan a gap.

    Splitting a gapped programme at the wrong revision leaves one segment still
    spanning the gap. That segment is exactly the chain the contiguity policy
    rejects, so the planner must report it rather than emit it.
    """
    plan = plan_chains(inventory)
    gapped = [a for a in plan.ambiguities if a.kind == "gapped_span"]
    assert gapped
    slug = gapped[0].slugs[0]
    event = inventory.event_by_slug(slug)
    assert event is not None
    order = {revision: index for index, revision in enumerate(inventory.revisions)}
    present = sorted(order[revision] for revision in event.revisions)
    # The gap sits after this index; splitting *before* it leaves the gap inside
    # the later segment.
    gap_at = next(i for i, j in pairwise(present) if j != i + 1)
    misplaced = inventory.revisions[gap_at]

    resolved = plan_chains(
        inventory,
        adjudications=AdjudicationSet(
            splits=(
                Split(
                    slug=slug,
                    from_revision=misplaced,
                    chain_id=f"irpf.aeip.{slug}.misplaced.aplicado",
                    reason="test: split placed before the gap",
                ),
            ),
        ),
    )
    assert [a for a in resolved.ambiguities if a.kind == "gapped_span" and slug in a.slugs], (
        "a split that leaves a segment spanning the gap must still be refused"
    )
    _assert_all_contiguous(inventory, resolved)


def test_legal_refs_drift_is_classified_not_called_unchanged(inventory) -> None:
    """A pair whose legal refs moved must not be recorded as ``unchanged``.

    The 2025 revision adds an ordinal reference to every row in the family, so
    every chain crossing 2024 -> 2025 really has evolved its legal refs.
    Recording those as ``unchanged`` would be a drift the strict cross-revision
    validator refuses, which is exactly the failure this pins.
    """
    plan = plan_chains(inventory)
    # A retirement also spans 2024 -> 2025 but describes a box the target
    # revision no longer declares, so only continuing pairs are in scope here.
    crossing = [
        pair
        for entry in plan.entries
        for pair in entry.pairs
        if (pair.from_revision, pair.to_revision) == ("2024", "2025") and pair.evolution_kind != "retired"
    ]
    assert crossing, "expected continuing chains spanning the 2024 -> 2025 boundary"
    assert all(pair.evolution_kind != "unchanged" for pair in crossing), (
        "the 2025 legal-refs addition must be reflected in the evolution kind"
    )
    assert all("legal_refs_evolved" in pair.evolution_kind for pair in crossing)

    # Every planned kind stays inside the registry's closed set.
    allowed = {
        "unchanged",
        "label_evolved",
        "legal_refs_evolved",
        "label_and_legal_refs_evolved",
        "repurposed",
        "retired",
    }
    assert {pair.evolution_kind for entry in plan.entries for pair in entry.pairs} <= allowed


def test_rendered_record_carries_the_target_revision_legal_refs(inventory) -> None:
    """A record renders the refs its pair actually carries, not a fixed default."""
    import tomllib

    plan = plan_chains(inventory)
    pair = next(
        pair
        for entry in plan.entries
        for pair in entry.pairs
        if (pair.from_revision, pair.to_revision) == ("2024", "2025") and pair.evolution_kind != "retired"
    )
    rendered = tomllib.loads(render_evolution_record(pair, casilla_id="0000"))
    record = rendered["revisions"]["2025"]["casilla_continuidad_evolutions"][0]
    assert record["legal_refs"] == list(pair.legal_refs)
    assert len(record["legal_refs"]) > 1, "the 2025 rows carry more than the framework article"

    # A retirement instead keeps the refs of the revision that last declared
    # the box, since the target revision declares nothing to cite.
    retirement = next(pair for entry in plan.entries for pair in entry.pairs if pair.evolution_kind == "retired")
    assert retirement.legal_refs, "a retirement still cites the chain's own refs"


def test_slug_derivation_folds_accents_and_ordinals() -> None:
    """Accents and Spanish ordinal indicators fold to readable slug text."""
    assert derive_slug("4ª Edición de la Barcelona World Race") == "4a-edicion-de-la-barcelona-world-race"
    assert derive_slug("150.º aniversario del nacimiento de Pau Casals").startswith("150-o-aniversario")
    assert derive_slug("Año Santo Jacobeo 2021") == "ano-santo-jacobeo-2021"
    assert derive_slug('Celebración del Summit "MADBLUE"') == "celebracion-del-summit-madblue"


def test_roles_are_distinct_constants() -> None:
    """The event role and the category role are not the same surface."""
    assert EVENT_SEMANTIC_ROLE != CATEGORY_SEMANTIC_ROLE


def test_rendered_evolution_record_parses_as_toml() -> None:
    """A rendered record is valid TOML with the fields the registry expects."""
    import tomllib

    plan_pair = render_evolution_record(
        EvolutionPair(
            chain_id="irpf-aeip-example-aplicado",
            from_revision="2023",
            to_revision="2024",
            evolution_kind="unchanged",
        ),
        casilla_id="1945",
        source_refs=("aeat-dr-100-2024-dictionary",),
    )
    parsed = tomllib.loads(plan_pair)
    record = parsed["revisions"]["2024"]["casilla_continuidad_evolutions"][0]
    assert record["continuidad_id"] == "irpf-aeip-example-aplicado"
    assert record["from_revision"] != record["to_revision"]
    assert record["source_refs"] == ["aeat-dr-100-2024-dictionary"]


def test_adjudications_file_ships_and_loads(tmp_path: Path) -> None:
    """The shipped adjudications file loads; a missing one is not an error."""
    shipped = Path(__file__).resolve().parents[1] / "adjudications.toml"
    assert shipped.is_file()
    loaded = load_adjudications(shipped)
    assert isinstance(loaded, AdjudicationSet)
    # A missing file is not an error; it means nothing is adjudicated yet.
    assert load_adjudications(tmp_path / "absent.toml") == AdjudicationSet.empty()


def test_ungrounded_adjudication_is_refused(tmp_path: Path) -> None:
    """An entry with no stated reason has no audit trail, so it is rejected."""
    path = tmp_path / "adjudications.toml"
    path.write_text(
        '[[exclusions]]\nrevision = "2020"\ncasilla = "0757"\n',
        encoding="utf-8",
    )
    with pytest.raises(AdjudicationError, match="reason"):
        load_adjudications(path)
