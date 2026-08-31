"""Revision-span filing-coverage test support."""

from __future__ import annotations

from datetime import date

from .....core.period import PeriodKind, registry_period_kind
from ..schema import ModeloDefinition, ModeloRevision
from ._revision_span_boundary_support import (
    _boundaries_for,
    _compare_design_pair,
    _designs_claimed_by,
)
from ._revision_span_design_support import (
    _claimed_years,
    _design_years,
    _designs_for,
    _filing_supported_revisions,
    _source_epoch_proves_revision_span,
    _span_years,
    _unparseable_design_sources,
)


def _declared_span_is_single_year(revision: ModeloRevision) -> bool:
    """Whether this revision's OWN declared span covers exactly one filing year.

    Distinct from a shortage of comparable CORPUS years -- that conflates "the
    span itself is one year" with "we lack evidence for a wider one". This
    asks only about the DECLARATION: an explicit single-year selector
    (``years=(N,)``) or a closed range whose two ends coincide (``year_from ==
    year_to``). An open-ended span (``year_to is None``) is never single-year
    here, even when today's corpus happens to cover only its opening year --
    it is declared OPEN, so a wider internal comparison remains possible once
    more corpus lands, and it belongs to the multi-year, evidence-acquisition
    branch instead of the neighbour-comparison one.

    A genuinely single-year span cannot cross an internal re-layout boundary
    by construction -- there is no second year inside it to compare against.
    What it needs to prove is different: that its own design differs from the
    design either side of it, which is what warranted splitting it off as its
    own revision in the first place (:func:`_neighbour_divergence`).
    """
    selector = revision.period_selector
    if selector.years:
        return len(set(selector.years)) == 1
    if selector.year_from is None or selector.year_to is None:
        return False
    return selector.year_from == selector.year_to


def _ordered_revisions_by_modelo(
    all_revisions: list[tuple[ModeloDefinition, str, ModeloRevision]],
) -> dict[str, list[tuple[str, ModeloRevision]]]:
    """``{modelo id: [(revision id, revision), ...]}``, ordered by earliest claimed year.

    The ordering key is :func:`_span_years`'s own minimum, the SAME function
    the relayout gate already uses to bound an open-ended span -- one
    definition of "which year does this revision start from", not a second.
    """
    by_modelo: dict[str, list[tuple[str, ModeloRevision]]] = {}
    for modelo, revision_id, revision in all_revisions:
        by_modelo.setdefault(modelo.id, []).append((revision_id, revision))

    def _sort_key(item: tuple[str, ModeloRevision]) -> int:
        _revision_id, revision = item
        years = _span_years(revision)
        return min(years) if years else 0

    return {modelo_id: sorted(revisions, key=_sort_key) for modelo_id, revisions in by_modelo.items()}


def _distinct_orden_documents(modelo: ModeloDefinition) -> set[str]:
    """Every distinct BOE orden document this modelo's revisions cite, tree-wide.

    Keyed by the document token BEFORE the first ``:`` (``orden-eha-3434-2007``
    out of ``orden-eha-3434-2007:art-1``), so two articles of the SAME orden
    count as one document and only a genuinely DIFFERENT orden -- an amending
    or superseding instrument -- counts as legal evidence a revision split
    actually happened. Reads ``orden_aplicabilidad`` AND ``legal_refs`` on
    every revision this modelo declares, not just the one revision under
    test: a later revision's citation is evidence the amending orden exists
    in the catalogue even if it is not (yet) attached to the earlier one.

    This is deliberately NOT a per-revision-span date match. The question
    here is coarser and prior to that one: does ANY second orden exist in
    the record for this modelo at all. A modelo with only ever one cited
    orden, despite corpus-proven design evidence of a relayout, has no
    legal citation to even attempt dating -- that absence is what
    :func:`test_every_modelo_revision_span_is_corpus_proven` reports as its
    own distinct failure reason, never a pass.
    """
    documents: set[str] = set()
    for revision in modelo.revisions.values():
        for ref in (*revision.orden_aplicabilidad, *revision.legal_refs):
            if not ref.startswith("orden-"):
                continue
            documents.add(ref.split(":", 1)[0])
    return documents


def _signal_label(evidence_item: str) -> str:
    """Classify one evidence string by which of the seven signals produced it.

    LIGHTWEIGHT SUBSTRING CLASSIFICATION, matching this module's own established
    convention -- the ``_DESCRIPTION_ONLY`` marking already classifies evidence
    the same way -- rather than a structural refactor of every signal function's
    return shape to carry a label. Seven signals, seven distinguishable phrasings.

    The seventh, ``straddle``, is why this function raises rather than returning
    'unknown': it was added to :func:`_compare_design_pair` without being added
    here, and the loud failure is what surfaced the omission instead of letting a
    live signal classify as nothing.

    Raises rather than falling through to "unknown", deliberately: a seventh
    signal added later without updating this function must fail LOUDLY here,
    the same anti-vacuity posture the rest of the module takes toward a
    detector going quiet without anyone noticing.
    """
    if "shared boxes moved" in evidence_item:
        return "box-displacement"
    if "box SET changed" in evidence_item:
        return "box-SET"
    if "RECORD SET CHANGED" in evidence_item or "page byte-lengths differ" in evidence_item:
        return "page-length/record-count"
    if "RETIRED into reserved space" in evidence_item or "REVIVED out of reserved space" in evidence_item:
        return "occupancy"
    if "field SET changed at these positions" in evidence_item:
        return "position-SET"
    if "unnumbered slot(s) re-described" in evidence_item:
        return "description-flip"
    if "straddle the other design's boundaries" in evidence_item:
        return "straddle"
    raise AssertionError(
        f"evidence string matches none of the seven known signal phrasings -- either a new signal "
        f"was added without updating _signal_label, or an existing one's wording changed under it: "
        f"{evidence_item!r}"
    )


def _neighbour_divergence(
    modelo_id: str,
    revision_id: str,
    ordered: list[tuple[str, ModeloRevision]],
) -> tuple[bool, str]:
    """Whether a single-year revision's design DIFFERS from its adjacent revision(s).

    Reuses :func:`_compare_design_pair`, the SAME comparator
    :func:`_boundaries_for` uses internally -- one instrument, two callers.
    Where that function asks "does a span's OWN internal designs disagree",
    this asks "does this one-year design disagree with what came immediately
    before or after it" -- the question a single-year span can actually
    answer, since it has no internal pair to compare.

    Returns ``(proven, detail)``:

    * ``proven`` is ``True`` when the revision's own design differs from AT
      LEAST ONE neighbour it has. A real difference at either edge is what
      justifies this revision existing as its own split -- a neighbourless
      edge, or an identical one on the OTHER side, is a separate finding
      about that other boundary, not evidence against this revision. ``detail``
      names WHICH signal(s) carried the proof (:func:`_signal_label`), so a
      pass resting on exactly one signal is a property of the returned text,
      not a fact that only exists in whoever ran this by hand -- a real,
      single-signal difference IS a legitimate proof (no corroboration
      threshold is imposed here), but a reader must be able to tell it rests
      on one signal rather than several before trusting it further.
    * ``proven`` is ``False`` either because every available neighbour
      comparison is IDENTICAL (the split introduced no design change and was
      unwarranted) or because no neighbour has a readable design to compare
      against at all (nothing to prove it with, yet). When the revision's OWN
      design is the missing piece, ``detail`` distinguishes ABSENT (no file
      bundled for this year at all -- an acquisition gap) from UNPARSEABLE (a
      file IS bundled but :func:`_design_sheets` cannot read it at all -- an
      extraction-layer defect, never an acquisition gap) via
      :func:`_unparseable_design_sources`. Conflating the two sends a
      fix-owner to acquire a design that is already sitting in the corpus.
    """
    index = next(i for i, (rid, _revision) in enumerate(ordered) if rid == revision_id)
    _own_id, own_revision = ordered[index]
    own_designs = _designs_claimed_by(modelo_id, own_revision)
    if not own_designs:
        own_year = min(_span_years(own_revision)) if _span_years(own_revision) else None
        matching_unparseable = [
            path
            for path in _unparseable_design_sources(modelo_id)
            if own_year is not None and own_year in _design_years(path.name)
        ]
        if matching_unparseable:
            names = ", ".join(path.name for path in matching_unparseable)
            return False, (
                f"a design for {own_year} IS bundled ({names}) but its sheets fail to parse -- "
                "UNPARSEABLE, not absent: this is an extraction-layer defect, not a corpus gap, "
                "and acquiring another copy from AEAT would not help"
            )
        return False, "no design is bundled for its own filing year at all -- ABSENT, so no comparison is possible"

    checks: list[tuple[str, str, list[str]]] = []
    if index > 0:
        neighbour_id, neighbour_revision = ordered[index - 1]
        neighbour_designs = _designs_claimed_by(modelo_id, neighbour_revision)
        if neighbour_designs:
            checks.append(("predecessor", neighbour_id, _compare_design_pair(neighbour_designs[-1], own_designs[0])))
    if index < len(ordered) - 1:
        neighbour_id, neighbour_revision = ordered[index + 1]
        neighbour_designs = _designs_claimed_by(modelo_id, neighbour_revision)
        if neighbour_designs:
            checks.append(("successor", neighbour_id, _compare_design_pair(own_designs[-1], neighbour_designs[0])))

    if not checks:
        return False, "no adjacent revision in this modelo has a readable design to compare against"

    diverging = [(direction, neighbour_id, evidence) for direction, neighbour_id, evidence in checks if evidence]
    if diverging:
        direction, neighbour_id, evidence = diverging[0]
        labels = sorted({_signal_label(item) for item in evidence})
        corroboration = "SINGLE SIGNAL, uncorroborated" if len(labels) == 1 else f"{len(labels)} signals agree"
        return True, (
            f"differs from its {direction} {neighbour_id!r} via {corroboration} [{', '.join(labels)}]: "
            f"{' + '.join(evidence)}"
        )

    names = ", ".join(f"{direction} {neighbour_id!r}" for direction, neighbour_id, _evidence in checks)
    return False, f"identical to its {names} -- the split introduces no design change"


def test_every_modelo_revision_span_is_corpus_proven() -> None:
    """HARD FAIL: every declared revision span must be corpus-PROVEN, tree-wide.

    Operator directive, verbatim in substance: this is a law-derived project.
    AEAT published a record design for every filing year of every modelo that
    has ever existed. Whether this repository has BUNDLED that document is a
    fact about the repository, never a fact about the world -- so a revision
    this module cannot yet compare is NOT UNKNOWABLE, it is NOT YET PROVEN,
    and the correct treatment of "not yet proven" is the same as any other
    unmet requirement: the gate FAILS, by name, naming the one concrete act
    that clears it. There is no third verdict here and no soft status that
    lets a gap flow onward looking like a passed check.

    ONE VERDICT: a revision's span is corpus-proven, or the gate fails on it.
    Corpus-proven requires BOTH:

    1. ``_boundaries_for(modelo.id, revision) == {}`` -- the SAME corpus-diffing
       instrument the sibling tests in this module already prove trustworthy
       (page-length, box-displacement, box-SET-change, reserved-space
       retire/revive, and unnumbered-slot signals, unioned into one verdict)
       finds no re-layout the declared span crosses.
    2. Depends on the SHAPE of the declared span (:func:`_declared_span_is_single_year`):

       - A MULTI-YEAR or open-ended span needs at least TWO comparable
         bundled design years inside it (``_claimed_years`` against
         ``_designs_for``'s output) -- it is a CLAIM that one layout serves
         every year in it, and a claim nobody has checked is not thereby
         true.
       - A SINGLE-YEAR span cannot contain an internal boundary by
         construction, so it proves itself differently
         (:func:`_neighbour_divergence`): its own design must DIFFER from at
         least one adjacent revision's design. That is what justifies the
         split existing at all; an identical neighbour means the split
         introduced no change and was unwarranted, and no neighbour at all
         means there is nothing to prove it with yet. Operator ruling,
         verbatim in substance: there is no undecidable verdict, and a span
         that could NEVER pass regardless of any work anyone does re-creates
         exactly that under a different name -- structural rather than
         evidentiary, and worse for it. Both branches here are answerable
         from corpus: everything is passable.

    Passing on fewer than two comparable years for a wide span, or without a
    genuine neighbour divergence for a narrow one, would mean this gate
    reports "proven" for exactly the modelos it looked hardest at and found
    nothing to compare -- the same shape as the sweep that withdrew nine
    modelos' export layouts behind real-looking legal citations while the
    validator checked only that a citation RESOLVED, never that it PROHIBITED
    anything: the larger the evidence gap, the quieter it was. This gate is
    built to make that shape impossible to reproduce by omission.

    NO ALLOWLIST. NO PER-MODELO EXEMPTION. NO SKIP, XFAIL, OR CONDITIONAL
    GUARD. A failing revision names its own fix in the same line, because the
    remedies are different acts and a fix-owner who reads "split this
    revision" when the real need is "bundle the missing design" wastes a day
    and invents a split with no basis: split the revision at a corpus-proven
    boundary, bundle AEAT's published design for a named year, or merge a
    single-year revision whose split introduced no design change. Every
    remedy has an owner and an action. None is a status to wait out.

    Measured at authoring time, PER REVISION, which is the precision this
    property needs -- a modelo-level tally (design-year COUNT anywhere against
    boundary COUNT anywhere) was tried first and was wrong: it does not check
    whether the comparable years fall INSIDE the specific revision being
    judged. Modelo 100 makes the gap concrete -- its bundled designs run
    2009-2019 while all six of its revisions run 2020-2025, zero overlap --
    and the modelo-level tally called that "11 designs, 0 boundaries, proven"
    by counting the absence of a comparison as the success of one. The
    per-revision check this test runs does not make that mistake.

    97 total revisions: 10 fail the relayout crossing, 64 fail on missing
    corpus for a multi-year span, 11 fail the neighbour-divergence check for a
    single-year span (either no readable neighbour exists yet, or the split
    turned out to introduce no design change), and 12 PASS -- 3 multi-year (131
    revision 2019-2023; 202 revisions 2019-2022 and 2023-2024) plus 9
    single-year revisions the neighbour-comparison branch resolves, all from
    Modelo 131's and Modelo 303's and Modelo 390's declared single-year spans
    (Modelo 100's six single-year revisions do NOT resolve here -- their own
    designs are unreadable/unattributed, a corpus gap the neighbour check
    cannot paper over any more than the multi-year branch could). 85 of 97
    fail overall, down from 94 before the neighbour-comparison branch existed:
    real corpus evidence closed 9 revisions the prior instrument could never
    have proven regardless of any acquisition, because it never asked the
    question a single-year span can actually answer. Modelo 347's
    2008-y-siguientes moved from the multi-year branch (misdiagnosed as
    needing more corpus) to the relayout-crossing branch (its true cause,
    proven) once the fifth signal stopped discarding evidence it had already
    computed -- the fail count did not change, its ACCURACY did.

    WHICH INSTRUMENT EACH PASS RESTS ON, stated explicitly because a pass
    proven by a weaker signal should be legible as such. Of the 9 single-year
    passes: 5 (131/2024, 303/2023, 390/2022, 390/2023, 390/2024) carry at
    least one box-KEYED signal (displacement or box-SET); the other 4
    (131/2025, 131/2026, 303/2025, 390/2025) rest ENTIRELY on box-FREE
    signals -- occupancy, page-length, position-SET, or description-flip.
    None of the 9 rests SOLELY on the newest, least-exercised signal
    (position-SET, added this session) -- every pass position-SET
    contributes to is independently corroborated by at least one other
    signal. This number moves as the bundled
    corpus grows; re-run rather than trust a stale figure.
    """
    ordered_by_modelo = _ordered_revisions_by_modelo(_filing_supported_revisions())

    failures: list[str] = []
    single_signal_passes: list[str] = []
    for modelo, revision_id, revision in _filing_supported_revisions():
        boundaries = _boundaries_for(modelo.id, revision)
        if boundaries:
            detail = "; ".join(
                f"{f'{earlier} mid-year' if earlier == later else f'{earlier}/{later}'} ({' + '.join(evidence)})"
                for (earlier, later), evidence in sorted(boundaries.items())
            )
            failures.append(
                f"modelo {modelo.id} revision {revision_id!r}: spans {len(boundaries)} corpus-evidenced "
                f"re-layout(s), needs {len(boundaries) + 1} revisions -- {detail} -- FIX: split the "
                "revision at the named boundary year(s)",
            )
            orden_documents = _distinct_orden_documents(modelo)
            if len(orden_documents) <= 1:
                # A DISTINCT failure reason from the one above, never a substitute for
                # it and never a path to a pass. The design-evidence failure says WHERE
                # a split is needed; this one says the legal record offers no citation
                # to justify or date it -- the founding orden is the only orden this
                # modelo's entire revision history ever cites, despite corpus evidence
                # a relayout happened somewhere in this revision's span. Absence of a
                # second orden citation is not positive evidence of non-revision, it is
                # evidence the legal catalogue is incomplete -- so this reason can NEVER
                # be cleared by design evidence, and NEVER becomes a pass condition;
                # only a positively-cited amending or superseding orden clears it.
                failures.append(
                    f"modelo {modelo.id} revision {revision_id!r}: NO LEGAL EVIDENCE OF REVISION "
                    f"RECORDED -- the design-evidence failure above proves a relayout crosses this "
                    f"revision's span, but this modelo's entire revision history cites only the "
                    f"founding orden ({sorted(orden_documents)!r}); no amending or superseding orden "
                    "is recorded anywhere in the bundled legal catalogue -- FIX: acquire and cite the "
                    "BOE orden that authorises the later layout; do not attempt to satisfy this with "
                    "design evidence alone, and do not treat the gap as anything other than a failure",
                )
            continue

        receipt_proven, _receipt_detail = _source_epoch_proves_revision_span(modelo.id, revision)
        if receipt_proven:
            # The revision cites an authoritative record-design dependency whose
            # declared epoch covers its entire span. Requiring duplicate annual
            # copies after this point would replace authority with a file count.
            continue

        if _declared_span_is_single_year(revision):
            proven, detail = _neighbour_divergence(modelo.id, revision_id, ordered_by_modelo[modelo.id])
            if not proven:
                # Three distinct remedies for three distinct causes -- naming the wrong one
                # sends a fix-owner to acquire a design that is already bundled, or to
                # wait on AEAT for evidence that is actually an in-tree extraction defect.
                if "UNPARSEABLE, not absent" in detail:
                    fix = "the design IS bundled but unreadable -- fix the extractor for the named file(s); acquiring another copy from AEAT would not help"
                elif "ABSENT" in detail:
                    fix = "no design is bundled for this year at all -- bundle AEAT's published record design for an adjacent ejercicio so the split can be proven"
                else:
                    fix = "identical to a neighbour -- merge this revision into it, the split introduced no design change and was unwarranted"
                failures.append(
                    f"modelo {modelo.id} revision {revision_id!r}: single-year span, {detail} -- FIX: {fix}",
                )
            elif "SINGLE SIGNAL, uncorroborated" in detail:
                # A real, legitimate PASS -- no corroboration threshold is imposed here, one
                # signal finding a genuine difference is proof enough. But a reader of the
                # verdict alone cannot tell this pass rests on one instrument while its
                # neighbours rest on several, and the always-visible failure text below is
                # this gate's only durable output, so recording it there is what makes
                # thinness a property of the gate rather than a fact only a chat message
                # carries. Not a failure; do not add to `failures`.
                single_signal_passes.append(f"modelo {modelo.id} revision {revision_id!r}: PASSES, {detail}")
            continue

        design_years, _unreadable = _designs_for(modelo.id)
        claimed = _claimed_years(revision, set(design_years))
        if len(claimed) < 2:
            # Distinguish ABSENT (no file at all for a needed year -- acquire from AEAT)
            # from UNPARSEABLE (a file is already bundled for that year but the parser
            # returns nothing usable -- an extraction-layer defect, never an acquisition
            # gap) before naming the fix. Conflating the two sends a fix-owner to acquire
            # a design that is already sitting in the corpus.
            unparseable = _unparseable_design_sources(modelo.id)
            unparseable_years = set()
            unparseable_names: list[str] = []
            for path in unparseable:
                matched = _claimed_years(revision, set(_design_years(path.name)))
                if matched:
                    unparseable_years |= matched
                    unparseable_names.append(path.name)
            note = ""
            if unparseable_years:
                note = (
                    f" -- NOTE: {len(unparseable_years)} of the missing year(s) "
                    f"({sorted(unparseable_years)}) already have a BUNDLED design file that fails to "
                    f"parse entirely ({', '.join(unparseable_names)}) -- UNPARSEABLE, not absent: fix "
                    "the extractor for those files before acquiring anything new for those specific years"
                )
            failures.append(
                f"modelo {modelo.id} revision {revision_id!r}: only {len(claimed)} comparable bundled "
                "design year(s) fall inside its claimed span -- FIX: bundle AEAT's published record "
                "design for the missing year(s); do not split this revision on today's evidence, and "
                "do not treat the gap as anything other than a failure" + note,
            )

    single_signal_note = (
        "\n\nSINGLE-SIGNAL PASSES (informational only, NOT failures -- one signal finding a genuine "
        "difference is a legitimate proof and no corroboration threshold is imposed; recorded here "
        "so a reader can tell which passes rest on one instrument rather than several before "
        "trusting them further):\n  " + "\n  ".join(sorted(single_signal_passes))
        if single_signal_passes
        else ""
    )

    assert not failures, (
        "every modelo's declared revision span must be corpus-proven before it may pass: zero "
        "corpus-evidenced re-layout boundaries, AND (a multi-year span) at least two comparable bundled "
        "design years checked inside it, OR (a single-year span) a proven divergence from an adjacent "
        "revision's design. AEAT published a design for every filing year; a gap here is a fact about "
        "this repository's bundled corpus, never about the world -- it is fixed by bundling the design, "
        "splitting the revision, or merging an unwarranted split, never accepted as a standing state:\n  "
        + "\n  ".join(sorted(failures))
        + single_signal_note
    )


def _current_filing_year() -> int:
    """Today's calendar year, the rolling upper bound a coverage sweep must reach.

    Computed at call time rather than pinned as a literal: a coverage hole at the
    tail of a modelo's declared revisions is dated by the CALENDAR, not by when
    this module was last edited. A hardcoded year would itself become a silent
    hole the moment it goes stale -- the exact failure shape this check exists
    to catch, reproduced in the checker.
    """
    return date.today().year


def _covers_year(revision, year: int) -> bool:
    """Whether one revision's period selector resolves for a given filing year.

    Deliberately NOT :func:`_claimed_years` or :func:`_span_years`. Those both
    bound an open-ended (``year_to is None``) span at ``year_from`` alone, on
    purpose, because the relayout-crossing gate above can only ever speak about
    years the bundled CORPUS covers. This function answers a different
    question -- does the revision's own LAW-DETERMINED selector resolve this
    year -- so an open upper bound must extend all the way to the year asked
    about, corpus or no corpus. Collapsing the two meanings into one helper
    would make an open-ended revision that legitimately still covers today read
    as covering only its opening year, inventing a hole that is not there.
    """
    selector = revision.period_selector
    if selector.years:
        return year in selector.years
    if selector.year_from is None:
        return False
    if year < selector.year_from:
        return False
    return selector.year_to is None or year <= selector.year_to


def _period_overlap(id_a: str, periods_a: tuple[str, ...], id_b: str, periods_b: tuple[str, ...]) -> str | None:
    """Evidence that two same-year revisions genuinely collide, or ``None``.

    NOT "more than one revision claims this year" -- that naive check produces
    two confirmed false positives in the bundled corpus. Modelo 303 splits
    2024 mid-course by PERIOD (``2024-hasta-08-y-2t`` declares periods
    ``1T, 2T, 01..08``; ``2024-desde-09-y-3t`` declares ``3T, 4T, 09..12``) --
    two revisions, one year, disjoint periods, zero ambiguity. Modelo 369
    declares three simultaneous 'esquema' revisions from 2021 onward, each
    using its OWN period-token vocabulary (``EXT-1T..EXT-4T`` for the exterior
    scheme, plain ``01..12`` for the import scheme, plain ``1T..4T`` for the
    union scheme) -- a parallel regime axis, not a date collision.

    The revision-selector's own ``periods`` field is therefore the finer-grained
    signal a year-only check cannot see, matching how the production resolver
    actually disambiguates a candidate: two revisions genuinely overlap only
    when their period-token sets share a member, or when either declares NO
    period restriction at all (an empty ``periods`` tuple matches every token,
    so it collides with anything the other side claims for that year).
    """
    if not periods_a or not periods_b:
        return (
            f"revisions {id_a!r} and {id_b!r} both resolve, and at least one declares no "
            "period-level restriction, so nothing distinguishes them"
        )
    shared = sorted(set(periods_a) & set(periods_b))
    if shared:
        return f"revisions {id_a!r} and {id_b!r} both resolve for period token(s) {shared!r}"
    return None


def _earliest_declared_year(revisions: list[tuple[str, ModeloRevision]]) -> int | None:
    """The earliest filing year any of a modelo's revisions declares, or ``None``.

    ``None`` for a modelo whose every revision declares no dateable start at
    all -- there is nothing to sweep a coverage window from, and reporting a
    hole for a modelo with no stated coverage would be inventing a claim the
    registry never made.
    """
    starts: list[int] = []
    for _revision_id, revision in revisions:
        selector = revision.period_selector
        if selector.years:
            starts.append(min(selector.years))
        elif selector.year_from is not None:
            starts.append(selector.year_from)
    return min(starts) if starts else None


def _offset_annual_modelo(revisions: list[tuple[str, ModeloRevision]]) -> bool:
    """Whether every one of a modelo's revisions declares ONLY annual-cadence periods.

    Derived, not declared: :class:`~core.PeriodKind` is already the canonical,
    closed cadence classifier every period token resolves through
    (:func:`~core.registry_period_kind`), and a modelo whose every revision
    declares nothing but the annual token (``0A``) is, by construction, filed
    IN ARREARS -- an annual return cannot be computed before its own ejercicio
    closes, so its filing window necessarily opens the FOLLOWING calendar
    year. A periodic modelo (quarterly, monthly) files within its own
    ejercicio instead.

    Confirmed against the bundled corpus's own declared ``deadline_windows``
    rather than assumed: every revision of modelos 100, 189, 280, 289, 345
    and 390 that declares a deadline window shows ``opens_on.year ==
    filing_year + 1`` (e.g. Modelo 100's 2025 revision opens 2026-04-08); the
    periodic control, Modelo 303, shows ``opens_on.year == filing_year``. No
    new field is declared for this -- the offset is arithmetic on data the
    registry already carries (the period cadence), not a second axis beside
    it, per the operator's instruction not to redeclare what is already
    derivable.

    A modelo with NO declared periods at all, or with even one non-annual
    period on any revision, is treated as NOT offset -- the strict, urgent
    default a permissive read would invert. Silently classifying an
    ambiguous modelo as filed-in-arrears would hide a live gap behind an
    assumption nothing in the registry actually states.
    """
    kinds: set[PeriodKind] = set()
    any_periods = False
    for _revision_id, revision in revisions:
        for token in revision.period_selector.periods:
            any_periods = True
            try:
                kinds.add(registry_period_kind(token))
            except ValueError:
                return False
    return any_periods and kinds == {PeriodKind.ANNUAL}
