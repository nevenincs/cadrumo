"""Refusal coverage for the IVA rate grounding verifier.

The shipped-corpus checks in ``test_rate_grounding.py`` only exercise the happy
path: the real table loads, so no refusal ever fires. Every refusal in
``_rates.verify_rate_grounding`` was therefore unprotected, and a grounding
verifier that silently stops refusing is worse than one that is merely complex.

These tests drive each refusal with the REAL verifier functions
(``verify_legal_reference`` / ``verify_source_file``) over synthetic but
schema-valid registry rows. Nothing here is mocked: an "invalid" reference is a
genuine model instance whose corpus path does not exist, so the real verifier
raises for the real reason.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.resources import bundled_path
from ...calculations.registry.schema_references import LegalReference, SourceReference
from .._grounding import legal_ref_failures
from ..errors import IvaCatalogueError
from ..rates import (
    _source_ref_failures,
    _source_window_covers,
    _source_window_failure,
    _verify_rate_grounding,
)
from ..schema import EUMemberState, IvaRateKind, IvaRateRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _rate(
    *,
    member_state: EUMemberState = EUMemberState.DE,
    effective_from: date = date(2025, 1, 1),
    effective_until: date | None = None,
    legal_refs: tuple[str, ...] = (),
    source_refs: tuple[str, ...] = (),
) -> IvaRateRecord:
    """Build one schema-valid rate row.

    ``IvaRateRecord`` refuses a Spanish row without ``legal_refs`` and a foreign
    row without ``source_refs``, so a filler reference is supplied for whichever
    axis the caller did not pin. The filler is inert: each test drives the
    helper whose axis it actually asserts on.
    """
    if member_state is EUMemberState.ES and not legal_refs:
        legal_refs = ("filler-legal-ref",)
    if member_state is not EUMemberState.ES and not source_refs:
        source_refs = ("filler-source-ref",)
    return IvaRateRecord(
        member_state=member_state,
        kind=IvaRateKind.GENERAL,
        pct=Decimal("19"),
        effective_from=effective_from,
        effective_until=effective_until,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def _source(
    ref_id: str,
    *,
    corpus_path: str = "corpus/eu_official/iva/does-not-exist.html",
    applies_from: date | None = date(2024, 1, 1),
    applies_to: date | None = None,
) -> SourceReference:
    """Build one schema-valid source row whose corpus file is absent by default."""
    return SourceReference(
        id=ref_id,
        evidence_tier="official_source_guidance",
        authority="other",
        kind="instructions",
        corpus_path=corpus_path,
        sha256="0" * 64,
        bytes=1,
        retrieved_at=date(2025, 1, 1),
        applies_from=applies_from,
        applies_to=applies_to,
        source_url="https://example.invalid/source",
        review_status="reviewed",
    )


def _legal(ref_id: str) -> LegalReference:
    """Build one schema-valid legal row whose corpus file is absent."""
    return LegalReference(
        id=ref_id,
        evidence_tier="legal_authority",
        authority="boe",
        kind="ley",
        corpus_ref="corpus/normatives/html/does-not-exist.html#a1",
        document_id="BOE-A-0000-00000",
        permalink="https://example.invalid/legal",
        effective_from=date(2024, 1, 1),
        review_status="operator_reviewed",
        reviewed_at=date(2025, 1, 1),
        reviewed_by="rate-grounding-refusal-test",
        required_text=("a provision this absent corpus file cannot contain",),
    )


# --------------------------------------------------------------------------
# Refusal 5: no source_ref applicability window covers the rate period
# --------------------------------------------------------------------------


def test_window_refusal_fires_when_no_source_covers_the_rate_period() -> None:
    rate = _rate(effective_from=date(2025, 1, 1))
    stale = _source("src-one", applies_from=date(2026, 1, 1))
    failure = _source_window_failure(rate, "DE/general/2025-01-01", [stale])
    assert failure is not None
    assert "no source_ref applicability window covers" in failure


def test_window_refusal_is_silent_when_a_source_covers_the_period() -> None:
    rate = _rate(effective_from=date(2025, 1, 1))
    covering = _source("src-one", applies_from=date(2024, 1, 1), applies_to=None)
    assert _source_window_failure(rate, "DE/general/2025-01-01", [covering]) is None


def test_window_refusal_is_skipped_for_spain() -> None:
    """The ES carve-out: Spanish rows are grounded by legal_refs, not by a window.

    Losing this would refuse every Spanish row, since ES rates carry no
    source_refs at all.
    """
    rate = _rate(member_state=EUMemberState.ES, effective_from=date(2025, 1, 1))
    assert _source_window_failure(rate, "ES/general/2025-01-01", []) is None
    # ... while the same empty source list refuses for any other member state,
    # and refuses for the window reason specifically (not some other cause).
    foreign = _rate(member_state=EUMemberState.DE, effective_from=date(2025, 1, 1))
    failure = _source_window_failure(foreign, "DE/general/2025-01-01", [])
    assert failure is not None
    assert "no source_ref applicability window covers" in failure


@pytest.mark.parametrize(
    ("applies_from", "applies_to", "effective_until", "covers"),
    (
        pytest.param(date(2024, 1, 1), None, None, True, id="open-ended-source-covers"),
        pytest.param(date(2025, 1, 1), None, None, True, id="starts-exactly-on-rate-start"),
        pytest.param(date(2025, 1, 2), None, None, False, id="starts-after-rate-start"),
        pytest.param(None, None, None, False, id="no-applies-from-never-covers"),
        pytest.param(date(2024, 1, 1), date(2025, 12, 31), date(2025, 6, 30), True, id="closed-window-contains"),
        pytest.param(date(2024, 1, 1), date(2025, 5, 1), date(2025, 6, 30), False, id="closed-window-too-short"),
        pytest.param(date(2024, 1, 1), date(2025, 12, 31), None, False, id="closed-window-vs-open-rate"),
    ),
)
def test_source_window_boundaries(
    applies_from: date | None,
    applies_to: date | None,
    effective_until: date | None,
    covers: bool,
) -> None:
    rate = _rate(effective_from=date(2025, 1, 1), effective_until=effective_until)
    reference = _source("src-one", applies_from=applies_from, applies_to=applies_to)
    assert _source_window_covers(reference, rate) is covers


#: A real shipped source that genuinely verifies. The memoisation trap below is
#: only observable once ``verified_sources`` is actually populated, which
#: requires ``verify_source_file`` to SUCCEED -- a synthetic source pointing at
#: an absent corpus file raises, never reaches the memo, and makes both
#: orderings behave identically.
_REAL_VERIFIABLE_SOURCE = "eu-eprs-iva-rates-2025-07-01"


def test_a_source_verified_on_an_earlier_row_still_grounds_a_later_row() -> None:
    """The memoisation trap: a repeated source_ref must still count on later rows.

    ``_source_ref_failures`` appends every resolvable source to ``row_sources``
    BEFORE the ``verified_sources`` memo check. Invert that order and the second
    row below sees an EMPTY source list, so the window check refuses a row whose
    grounding is in fact present -- a grounding verifier rejecting valid law.

    Two preconditions are asserted explicitly rather than assumed, because if
    either silently fails to hold this test passes while proving nothing: the
    source must really verify, and row one must really populate the memo.
    """
    from ...calculations.registry.loader import load_registry_tree

    source_root = bundled_path()
    _, catalogues = load_registry_tree(source_root / "registry" / "aeat")
    sources = catalogues.sources
    shared = sources[_REAL_VERIFIABLE_SOURCE]
    verified: set[str] = set()

    # Both rows sit inside the shared source's applicability window.
    first = _rate(effective_from=date(2025, 8, 1), source_refs=(_REAL_VERIFIABLE_SOURCE,))
    second = _rate(effective_from=date(2025, 9, 1), source_refs=(_REAL_VERIFIABLE_SOURCE,))

    first_failures, first_row_sources = _source_ref_failures(first, "row1", sources, source_root, verified)
    assert first_failures == [], "precondition: the shared source must verify cleanly"
    assert _REAL_VERIFIABLE_SOURCE in verified, (
        "precondition: row one must populate the memo, or the ordering under test "
        "is never exercised and this test proves nothing"
    )
    assert first_row_sources == [shared]

    _, second_row_sources = _source_ref_failures(second, "row2", sources, source_root, verified)
    assert second_row_sources == [shared], (
        "a source already verified on an earlier row vanished from the later row's "
        "sources; the window check would now refuse a correctly grounded row"
    )
    assert _source_window_failure(second, "row2", second_row_sources) is None


# --------------------------------------------------------------------------
# Refusals 1-4: unknown / invalid legal and source references
# --------------------------------------------------------------------------


def test_unknown_legal_ref_is_refused() -> None:
    rate = _rate(legal_refs=("no-such-legal-id",))
    failures = legal_ref_failures("row", rate.legal_refs, {}, bundled_path(), set())
    assert failures == ["row: unknown legal_ref 'no-such-legal-id'"]


def test_invalid_legal_ref_is_refused() -> None:
    """A resolvable legal row whose corpus file is absent must be refused."""
    rate = _rate(legal_refs=("broken-legal",))
    failures = legal_ref_failures(
        "row", rate.legal_refs, {"broken-legal": _legal("broken-legal")}, bundled_path(), set()
    )
    assert len(failures) == 1
    assert failures[0].startswith("row: invalid legal_ref 'broken-legal':")


def test_unknown_source_ref_is_refused() -> None:
    rate = _rate(source_refs=("no-such-source-id",))
    failures, row_sources = _source_ref_failures(rate, "row", {}, bundled_path(), set())
    assert failures == ["row: unknown source_ref 'no-such-source-id'"]
    assert row_sources == []


def test_invalid_source_ref_is_refused() -> None:
    """A resolvable source row whose corpus file is absent must be refused."""
    rate = _rate(source_refs=("broken-source",))
    failures, row_sources = _source_ref_failures(
        rate, "row", {"broken-source": _source("broken-source")}, bundled_path(), set()
    )
    assert len(failures) == 1
    assert failures[0].startswith("row: invalid source_ref 'broken-source':")
    # Still collected, so the window check sees it.
    assert len(row_sources) == 1


def test_a_verified_legal_ref_is_not_reverified() -> None:
    """The legal memo short-circuits, so a known-good id costs nothing on later rows."""
    rate = _rate(legal_refs=("already-verified",))
    assert legal_ref_failures("row", rate.legal_refs, {}, bundled_path(), {"already-verified"}) == []


# --------------------------------------------------------------------------
# End to end: the verifier raises rather than returning silently
# --------------------------------------------------------------------------


def test_verify_rate_grounding_raises_on_an_ungrounded_table() -> None:
    """A table of unresolvable references must raise, not pass quietly."""
    table = {
        EUMemberState.DE: (
            _rate(
                member_state=EUMemberState.DE,
                legal_refs=("no-such-legal-id",),
                source_refs=("no-such-source-id",),
            ),
        )
    }
    with pytest.raises(IvaCatalogueError, match="IVA rate grounding verification failed"):
        _verify_rate_grounding(table)
