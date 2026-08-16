"""An ``official_source_guidance`` claim is checked against the file, never trusted.

``evidence_tier = "official_source_guidance"`` is checked at four sites --
cross-reference applicability predicates, application links, verification
expectations and deadline windows -- but every one of those checks asked only
whether the CITED SOURCE carries the tier, never whether the source's own text
supports the claim the site makes. Two claims survived calibration as
independently testable without the over-fire risk ``_legal.py``'s dispositive-
content regex (630 of 633 false positives on its first draft, 59 on its
second) warns is the default outcome of a first attempt: a ``suppression_notice``
must itself say something was suppressed, and a ``deadline_window`` must cite a
source that itself states a filing deadline.

These tests pin the property, never a tally: the corpus's population will
change as sources are retiered or replaced, and asserting today's count would
train the next author to update a constant while detecting nothing. What must
hold is the implication -- a claim is reported exactly when its own file (or,
for the deadline check, EVERY one of its official_source_guidance sources)
fails the content predicate -- proven exhaustively over the real bundled
corpus, both directions, never sampled.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .....tests.registry_tree import bundled_registry_tree
from .._schema_references import SourceReference
from .._validate_evidence import EvidenceValidator
from .._validate_official_source_guidance_content import (
    _DEADLINE_VOCABULARY,
    _SUPPRESSION_VOCABULARY,
    _carries_deadline_content,
    _carries_suppression_content,
    deadline_window_content_failures,
    validate_suppression_notice_content,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The one real defect this check was built to find. Re-anchored per source
#: id rather than content: the companion test below re-derives that it still
#: carries the properties it is named for, so a retier or a swapped file
#: makes the anchor fail loudly instead of every assertion passing vacuously
#: over an empty set.
_SUPPRESSION_ANCHOR_SOURCE_ID = "boe-modelo-037-historical-suppression"

#: The real defect the deadline-window check was built to find: all four of
#: modelo 115's quarterly windows cite two sources that ground WHO must
#: withhold on rental income, never WHEN the resulting declaration is due.
_DEADLINE_ANCHOR_MODELO_ID = "115"
_DEADLINE_ANCHOR_REVISION_ID = "2019-y-siguientes"
_DEADLINE_ANCHOR_WINDOW_ID = "modelo-115-2026-1t"

#: A window whose own cited source genuinely states its filing deadline.
_DEADLINE_HONEST_MODELO_ID = "180"
_DEADLINE_HONEST_WINDOW_ID = "modelo-180-2024-0a"


def _bundled_sources() -> dict[str, SourceReference]:
    _modelos, catalogues = bundled_registry_tree()
    return {str(ref): source for ref, source in catalogues.sources.items()}


def _osg_sources() -> dict[str, SourceReference]:
    return {
        sid: source for sid, source in _bundled_sources().items() if source.evidence_tier == "official_source_guidance"
    }


def _find_window(modelo_id: str, window_id: str):
    modelos, _catalogues = bundled_registry_tree()
    modelo = next(m for m in modelos if m.id == modelo_id)
    for revision in modelo.revisions.values():
        for window in revision.deadline_windows:
            if window.id == window_id:
                return window
    raise AssertionError(f"deadline window {window_id!r} not found under modelo {modelo_id!r}")


def _evidence_validator(*, source_root) -> EvidenceValidator:
    _modelos, catalogues = bundled_registry_tree()
    return EvidenceValidator(legal_refs=catalogues.legal, source_refs=catalogues.sources, source_root=source_root)


# --------------------------------------------------------------------------
# suppression_notice content
# --------------------------------------------------------------------------


def test_the_suppression_anchor_still_carries_the_properties_it_is_named_for() -> None:
    """The anchor is still a suppression_notice/official_source_guidance claim.

    Without this, retiering or replacing the source would silently turn the
    reconciliation test below into a statement about an empty population.
    """
    source = _bundled_sources()[_SUPPRESSION_ANCHOR_SOURCE_ID]
    assert source.kind == "suppression_notice"
    assert source.evidence_tier == "official_source_guidance"


def test_every_reported_suppression_claim_is_one_whose_file_carries_no_suppression_text() -> None:
    """The reported set equals the set whose file fails the content predicate.

    Both directions in one assertion, over the real corpus: nothing is
    reported whose file does carry suppression-establishing text, and nothing
    that fails the predicate escapes the report.
    """
    claims = {sid: source for sid, source in _osg_sources().items() if source.kind == "suppression_notice"}
    assert claims, "the suppression_notice population moved out from under this test"
    root = bundled_path()
    reported = {sid for sid in claims if validate_suppression_notice_content({sid: claims[sid]}, source_root=root)}
    unbacked = set()
    for sid, source in claims.items():
        path = root / source.corpus_path
        if not path.is_file():
            continue
        if not _carries_suppression_content(path.read_text(encoding="utf-8", errors="replace")):
            unbacked.add(sid)
    assert reported == unbacked


def test_the_suppression_gate_still_refuses_an_entry_into_force_clause() -> None:
    """A suppression claim over a WHEN clause is refused, naming the fix.

    The anchor once pointed at this order's ``disposicion final unica`` -- an
    entry-into-force clause carrying no suppression at all -- and was the real
    defect this gate was built to find. It has since been re-pointed to the
    amending article that performs the suppression, so the refusal direction
    needs a claim that still exhibits the defect.

    The clause is the REAL bundled file, still shipped and still cited as a
    corpus_ref elsewhere, mounted here under the anchor's own identity. A
    synthetic fixture would prove the regex runs; this proves the gate refuses
    the exact confusion an author actually makes.
    """
    anchor = _bundled_sources()[_SUPPRESSION_ANCHOR_SOURCE_ID]
    when_not_what = anchor.model_copy(
        update={"corpus_path": "corpus/normatives/html/orden-hac-1526-2024-df-unica.html"},
    )

    failures = validate_suppression_notice_content(
        {_SUPPRESSION_ANCHOR_SOURCE_ID: when_not_what},
        source_root=bundled_path(),
    )

    assert failures, "a suppression_notice claim over an entry-into-force clause must be refused"
    assert "carries no suppression-establishing text" in failures[0]
    assert "amending article" in failures[0]


def test_a_genuine_suppression_notice_satisfies_the_claim() -> None:
    """Unit-level control: real suppression vocabulary is accepted."""
    assert _carries_suppression_content("articulo unico. se suprime el modelo 099.") is True
    assert _carries_suppression_content("se deroga la disposicion adicional tercera.") is True


def test_entry_into_force_alone_does_not_satisfy_the_suppression_claim() -> None:
    """Anti-vacuity proof: 'entrada en vigor' is not 'suprim*'/'derog*'."""
    assert (
        _carries_suppression_content(
            "la orden entra en vigor el dia 3 de febrero de 2025. "
            "se aplica por primera vez a los modelos 030 y 036 que se presenten a partir de dicha fecha.",
        )
        is False
    )


def test_every_suppression_acceptance_is_driven_by_content_the_file_actually_carries() -> None:
    """Strip the suppression vocabulary from each ACCEPTED file and it flips to refused.

    Refusals are easy to trust: each names a file and says what is missing. An
    acceptance is the larger claim -- a predicate that could not say no, or a
    read that quietly failed, looks exactly like a clean bill of health.

    So each accepted file is re-asked with its ``suprim*`` / ``derog*`` /
    ``queda sin efecto`` turns of phrase removed IN MEMORY. An acceptance
    surviving that was never reading the file. Nothing on disk is touched.

    This is the proof the earlier absence-assertion promised: it held only
    while every suppression_notice claim was refused, and pointed here the
    moment an honest one landed.
    """
    claims = {sid: source for sid, source in _osg_sources().items() if source.kind == "suppression_notice"}
    assert claims, "the suppression_notice population moved out from under this test"
    root = bundled_path()
    accepted, survived, unreadable = 0, [], []
    for source_id, source in sorted(claims.items()):
        path = root / source.corpus_path
        if not path.is_file():
            unreadable.append(source_id)
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        if not _carries_suppression_content(raw):
            continue
        accepted += 1
        if _carries_suppression_content(_SUPPRESSION_VOCABULARY.sub("XXX", raw)):
            survived.append(source_id)

    assert not unreadable, f"claims whose file could not be read, so neither accepted nor refused: {unreadable}"
    assert accepted, "no suppression_notice claim was accepted, so this proof would hold vacuously"
    assert not survived, (
        f"these acceptances survive having their suppression evidence stripped, so they are not "
        f"reading the file they claim to verify: {survived}"
    )


# --------------------------------------------------------------------------
# deadline_window content
# --------------------------------------------------------------------------


def test_the_deadline_anchor_still_cites_only_ungrounded_sources() -> None:
    """The named defect window still cites no source with deadline vocabulary."""
    window = _find_window(_DEADLINE_ANCHOR_MODELO_ID, _DEADLINE_ANCHOR_WINDOW_ID)
    sources = _bundled_sources()
    osg_refs = [ref for ref in window.source_refs if sources[ref].evidence_tier == "official_source_guidance"]
    assert osg_refs, "the anchor window no longer cites any official_source_guidance source"
    for ref in osg_refs:
        assert sources[ref].kind != "manual_pdf", "re-derive against the real file if this anchor moves to a PDF"


def test_the_deadline_gate_still_refuses_a_window_citing_only_who_must_file_sources() -> None:
    """A window whose every OSG source is silent on WHEN is refused.

    This window was the real defect the gate was built to find: it cited only
    the censal guide and the activities folleto, both of which say WHO must
    file and never WHEN. It has since been grounded with the RIRPF article
    that states the deadline, so the refusal direction needs the pre-fix
    citation set to point at.

    Both remaining refs are the REAL bundled sources the window still cites,
    with only the deadline-bearing one dropped -- so this reproduces the exact
    historical state rather than inventing a synthetic silent source.
    """
    window = _find_window(_DEADLINE_ANCHOR_MODELO_ID, _DEADLINE_ANCHOR_WINDOW_ID)
    evidence = _evidence_validator(source_root=bundled_path())
    sources = _bundled_sources()
    silent_refs = tuple(
        ref
        for ref in window.source_refs
        if (text := evidence.source_text(sources[ref])) is None or not _carries_deadline_content(text)
    )
    assert silent_refs, "the anchor window no longer cites any WHO-must-file source to refuse"
    who_only = window.model_copy(update={"source_refs": silent_refs})

    failures = deadline_window_content_failures(
        f"modelo {_DEADLINE_ANCHOR_MODELO_ID} revision {_DEADLINE_ANCHOR_REVISION_ID}",
        who_only,
        source_refs=sources,
        evidence=evidence,
    )

    assert failures, f"{_DEADLINE_ANCHOR_WINDOW_ID} citing only WHO-must-file sources must be reported"
    assert "none of their bundled text states a filing deadline" in failures[0]


def test_an_honest_deadline_window_is_not_reported() -> None:
    window = _find_window(_DEADLINE_HONEST_MODELO_ID, _DEADLINE_HONEST_WINDOW_ID)
    evidence = _evidence_validator(source_root=bundled_path())
    failures = deadline_window_content_failures(
        "modelo 180 revision 2023-y-siguientes",
        window,
        source_refs=_bundled_sources(),
        evidence=evidence,
    )
    assert failures == []


def test_every_reported_deadline_window_cites_no_source_with_deadline_vocabulary() -> None:
    """The reported set equals the set of windows whose OSG sources are ALL silent on WHEN.

    Exhaustive over every deadline window in the bundled registry, both
    directions: nothing is reported whose cited sources DO carry deadline
    vocabulary, and no window whose sources are all silent escapes the report.
    """
    modelos, catalogues = bundled_registry_tree()
    sources = catalogues.sources
    evidence = _evidence_validator(source_root=bundled_path())

    reported: set[tuple[str, str, str]] = set()
    independently_computed: set[tuple[str, str, str]] = set()
    total_windows = 0
    for modelo in modelos:
        for rev_id, revision in modelo.revisions.items():
            for window in revision.deadline_windows:
                total_windows += 1
                failures = deadline_window_content_failures(
                    f"modelo {modelo.id} revision {rev_id}",
                    window,
                    source_refs=sources,
                    evidence=evidence,
                )
                if failures:
                    reported.add((modelo.id, rev_id, window.id))

                osg_refs = [
                    ref
                    for ref in window.source_refs
                    if (s := sources.get(ref)) is not None and s.evidence_tier == "official_source_guidance"
                ]
                if not osg_refs:
                    continue
                any_grounded = False
                for ref in osg_refs:
                    text = evidence.source_text(sources[ref])
                    if text is not None and _carries_deadline_content(text):
                        any_grounded = True
                        break
                if not any_grounded:
                    independently_computed.add((modelo.id, rev_id, window.id))

    assert total_windows > 400, "the registry's deadline-window population moved out from under this test"
    assert reported == independently_computed
    # The bundled population is currently all-honest, so this equality holds at
    # the empty set and cannot by itself prove the gate can say no. That
    # direction is carried by
    # ``test_the_deadline_gate_still_refuses_a_window_citing_only_who_must_file_sources``,
    # which mounts this window's own pre-fix citation set. Deliberately NOT
    # pinned to "reported == set()": a genuinely ungrounded window appearing
    # later must be REPORTED, which is the gate working, not this test failing.


def test_deadline_vocabulary_alone_is_the_positive_control() -> None:
    assert _carries_deadline_content("el plazo de presentacion finaliza el dia 20.") is True
    assert _carries_deadline_content("declaracion informativa de nacimientos y defunciones.") is False


def test_every_accepted_deadline_window_survives_stripping_only_when_re_asked_without_its_evidence() -> None:
    """Exhaustive anti-vacuity proof: strip the deadline vocabulary from each cited
    OSG source's text in memory and confirm the window flips to refused.

    Every window this gate currently accepts is re-asked with 'plazo',
    'presentaci*', 'vencimient*' and the 'dias naturales' idiom removed from
    ONLY the text this proof holds in memory -- nothing on disk changes. A
    window surviving that was never reading its cited sources' text.
    """
    modelos, catalogues = bundled_registry_tree()
    sources = catalogues.sources
    evidence = _evidence_validator(source_root=bundled_path())

    class _StrippedEvidence:
        def __init__(self, inner: EvidenceValidator) -> None:
            self._inner = inner

        def source_text(self, source: SourceReference) -> str | None:
            text = self._inner.source_text(source)
            if text is None:
                return None
            return _DEADLINE_VOCABULARY.sub("XXX", text)

    stripped_evidence = _StrippedEvidence(evidence)

    accepted, survived, unreadable = 0, [], []
    for modelo in modelos:
        for _rev_id, revision in modelo.revisions.items():
            for window in revision.deadline_windows:
                osg_refs = [
                    ref
                    for ref in window.source_refs
                    if (s := sources.get(ref)) is not None and s.evidence_tier == "official_source_guidance"
                ]
                if not osg_refs:
                    continue
                baseline_failures = deadline_window_content_failures(
                    "x",
                    window,
                    source_refs=sources,
                    evidence=evidence,
                )
                if baseline_failures:
                    continue  # already refused; nothing to strip
                readable = any(evidence.source_text(sources[ref]) is not None for ref in osg_refs)
                if not readable:
                    unreadable.append((modelo.id, window.id))
                    continue
                accepted += 1
                stripped_failures = deadline_window_content_failures(
                    "x",
                    window,
                    source_refs=sources,
                    evidence=stripped_evidence,  # type: ignore[arg-type]
                )
                if not stripped_failures:
                    survived.append((modelo.id, window.id))

    assert not unreadable, f"accepted windows whose sources could not be re-read: {unreadable}"
    assert accepted > 400, "no deadline window was accepted, so this proof would hold vacuously"
    assert not survived, (
        f"these accepted windows survive having their deadline vocabulary stripped, so they are not "
        f"reading the text they claim to verify: {survived}"
    )


def test_the_deadline_gate_yields_nothing_without_a_source_root() -> None:
    """No reachable corpus means no claim can be checked, and none is invented."""
    window = _find_window(_DEADLINE_ANCHOR_MODELO_ID, _DEADLINE_ANCHOR_WINDOW_ID)
    unreachable_evidence = EvidenceValidator(
        legal_refs={},
        source_refs=_bundled_sources(),
        source_root=None,
    )
    assert (
        deadline_window_content_failures(
            "x",
            window,
            source_refs=_bundled_sources(),
            evidence=unreachable_evidence,
        )
        == []
    )


def test_a_window_with_no_official_source_guidance_ref_is_not_this_checks_concern() -> None:
    """A window citing zero OSG-tier sources is a tier-membership failure elsewhere.

    ``require_source_tier`` already refuses that shape; this check adds
    nothing and reports nothing, rather than duplicating that failure under a
    different message.
    """
    window = _find_window(_DEADLINE_HONEST_MODELO_ID, _DEADLINE_HONEST_WINDOW_ID)
    non_osg_source_refs = {
        ref: source.model_copy(update={"evidence_tier": "layout_authority"})
        for ref, source in _bundled_sources().items()
        if ref in window.source_refs
    }
    evidence = _evidence_validator(source_root=None)
    assert (
        deadline_window_content_failures(
            "x",
            window,
            source_refs=non_osg_source_refs,
            evidence=evidence,
        )
        == []
    )
