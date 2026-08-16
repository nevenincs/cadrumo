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
    """The named defect is still a suppression_notice/official_source_guidance claim.

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


def test_the_suppression_gate_reports_the_defect_it_was_built_for() -> None:
    claims = {_SUPPRESSION_ANCHOR_SOURCE_ID: _bundled_sources()[_SUPPRESSION_ANCHOR_SOURCE_ID]}
    failures = validate_suppression_notice_content(claims, source_root=bundled_path())
    assert failures, (
        f"{_SUPPRESSION_ANCHOR_SOURCE_ID} declares suppression evidence over a file that says WHEN, not WHAT"
    )
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


def test_no_suppression_notice_claim_is_currently_accepted() -> None:
    """The suppression_notice population is exactly one source today, and it is REFUSED.

    There is therefore no accepted claim to run the strip-in-memory
    anti-vacuity proof against. That absence is asserted explicitly, so a
    future honest suppression_notice source starts failing THIS test loudly
    -- the signal to extend it with the strip-and-reassert proof
    ``_validate_layout_authority_content.py``'s sibling check performs --
    rather than silently leaving the acceptance direction unproven forever.
    """
    claims = {sid: source for sid, source in _osg_sources().items() if source.kind == "suppression_notice"}
    root = bundled_path()
    accepted = [
        sid
        for sid, source in claims.items()
        if (root / source.corpus_path).is_file()
        and _carries_suppression_content((root / source.corpus_path).read_text(encoding="utf-8", errors="replace"))
    ]
    assert accepted == []


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


def test_the_deadline_gate_reports_the_defect_it_was_built_for() -> None:
    window = _find_window(_DEADLINE_ANCHOR_MODELO_ID, _DEADLINE_ANCHOR_WINDOW_ID)
    evidence = _evidence_validator(source_root=bundled_path())
    failures = deadline_window_content_failures(
        "modelo 115 revision 2019-y-siguientes",
        window,
        source_refs=_bundled_sources(),
        evidence=evidence,
    )
    assert failures, f"{_DEADLINE_ANCHOR_WINDOW_ID} cites only WHO-must-file sources and must be reported"
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
    assert (_DEADLINE_ANCHOR_MODELO_ID, _DEADLINE_ANCHOR_REVISION_ID, _DEADLINE_ANCHOR_WINDOW_ID) in reported


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
