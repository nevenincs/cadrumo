"""Refusal coverage for the compiler's IVA rate grounding verifier.

The shipped rate table compiles, so compiling it never fires a refusal. These
tests drive each refusal through :func:`verify_iva_rate_grounding` with the
real legal and source verifiers over synthetic but schema-valid rows. Nothing
is substituted: an "invalid" reference is a genuine model instance whose corpus
file does not exist, so the real verifier refuses it for the real reason, and
the window cases re-declare the window of a real shipped source whose corpus
file does verify, so the window refusal is the only one that can fire.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema_base import EvidenceTier
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference
from cadrumo.domain.iva.errors import IvaCatalogueError
from cadrumo.domain.iva.schema import EUMemberState, IvaRateKind, IvaRateRecord

from ..compiler.iva import verify_iva_rate_grounding
from ..compiler.legal_grounding import legal_ref_failures
from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: A real shipped source whose corpus file verifies. Only its declared window
#: is re-stated per case, which the corpus check does not read.
_REAL_VERIFIABLE_SOURCE = "eu-eprs-iva-rates-2025-07-01"
_WINDOW_REFUSAL = "no source_ref applicability window covers"


def _rate(
    *,
    member_state: EUMemberState = EUMemberState.DE,
    effective_from: date = date(2025, 8, 1),
    effective_until: date | None = None,
    legal_refs: tuple[str, ...] = (),
    source_refs: tuple[str, ...] = (_REAL_VERIFIABLE_SOURCE,),
) -> IvaRateRecord:
    """Build one schema-valid rate row; a Spanish row needs a legal ref, supplied as a filler."""
    if member_state is EUMemberState.ES and not legal_refs:
        legal_refs = ("filler-legal-ref",)
    return IvaRateRecord(
        member_state=member_state,
        kind=IvaRateKind.GENERAL,
        pct=Decimal("19"),
        effective_from=effective_from,
        effective_until=effective_until,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def _real_source(*, applies_from: date | None, applies_to: date | None) -> SourceReference:
    shipped = load_shared_catalogues(bundled_path("registry", "aeat")).sources[_REAL_VERIFIABLE_SOURCE]
    return shipped.model_copy(update={"applies_from": applies_from, "applies_to": applies_to})


def _absent_source(ref_id: str) -> SourceReference:
    return SourceReference(
        id=ref_id,
        evidence_tier="official_source_guidance",
        authority="other",
        kind="instructions",
        corpus_path="corpus/eu_official/iva/does-not-exist.html",
        sha256="0" * 64,
        bytes=1,
        retrieved_at=date(2025, 1, 1),
        applies_from=date(2024, 1, 1),
        applies_to=None,
        source_url="https://example.invalid/source",
        review_status="pending_review",
    )


def _absent_legal(ref_id: str) -> LegalReference:
    return LegalReference(
        id=ref_id,
        evidence_tier=EvidenceTier.LEGAL_AUTHORITY,
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


def _failures(
    *rates: IvaRateRecord,
    sources: dict[str, SourceReference],
    legal: dict[str, LegalReference] | None = None,
) -> str:
    """Return the verifier's refusal text for ``rates``, or an empty string when it accepts them."""
    table: dict[EUMemberState, tuple[IvaRateRecord, ...]] = {}
    for rate in rates:
        table[rate.member_state] = (*table.get(rate.member_state, ()), rate)
    try:
        verify_iva_rate_grounding(table, legal=legal or {}, sources=sources, source_root=bundled_path())
    except IvaCatalogueError as exc:
        return str(exc)
    return ""


def test_a_row_inside_a_verified_source_window_is_accepted() -> None:
    covering = _real_source(applies_from=date(2025, 7, 1), applies_to=None)
    assert _failures(_rate(), sources={_REAL_VERIFIABLE_SOURCE: covering}) == ""


def test_a_row_no_source_window_covers_is_refused_for_that_reason() -> None:
    stale = _real_source(applies_from=date(2026, 1, 1), applies_to=None)
    refusal = _failures(_rate(), sources={_REAL_VERIFIABLE_SOURCE: stale})
    assert _WINDOW_REFUSAL in refusal
    assert "invalid source_ref" not in refusal


def test_a_spanish_row_is_grounded_by_legislation_not_by_a_source_window() -> None:
    """Spanish rows carry no source window; the same empty source list refuses any other state."""
    spanish = _rate(member_state=EUMemberState.ES, source_refs=())
    shipped_legal = load_shared_catalogues(bundled_path("registry", "aeat")).legal
    legal_ref = next(iter(sorted(shipped_legal)))
    spanish = spanish.model_copy(update={"legal_refs": (legal_ref,)})
    assert _WINDOW_REFUSAL not in _failures(spanish, sources={}, legal=dict(shipped_legal))

    # A foreign row whose cited source resolves to nothing has the same empty source list, and is refused.
    foreign = _rate(source_refs=("no-such-source-id",))
    assert _WINDOW_REFUSAL in _failures(foreign, sources={})


@pytest.mark.parametrize(
    ("applies_from", "applies_to", "effective_until", "covers"),
    (
        pytest.param(date(2025, 7, 1), None, None, True, id="open-ended-source-covers"),
        pytest.param(date(2025, 8, 1), None, None, True, id="starts-exactly-on-rate-start"),
        pytest.param(date(2025, 8, 2), None, None, False, id="starts-after-rate-start"),
        pytest.param(None, None, None, False, id="no-applies-from-never-covers"),
        pytest.param(date(2025, 7, 1), date(2025, 12, 31), date(2025, 10, 31), True, id="closed-window-contains"),
        pytest.param(date(2025, 7, 1), date(2025, 9, 30), date(2025, 10, 31), False, id="closed-window-too-short"),
        pytest.param(date(2025, 7, 1), date(2025, 12, 31), None, False, id="closed-window-vs-open-rate"),
    ),
)
def test_source_window_boundaries(
    applies_from: date | None,
    applies_to: date | None,
    effective_until: date | None,
    covers: bool,
) -> None:
    source = _real_source(applies_from=applies_from, applies_to=applies_to)
    refusal = _failures(_rate(effective_until=effective_until), sources={_REAL_VERIFIABLE_SOURCE: source})
    assert (_WINDOW_REFUSAL not in refusal) is covers
    assert "invalid source_ref" not in refusal


def test_a_source_verified_on_an_earlier_row_still_grounds_a_later_row() -> None:
    """A source memoised as verified on one row must still count toward a later row's window.

    Both rows cite the same verifying source. Were a memoised source dropped
    from the later row's sources, that row would be refused for having no
    covering window although its grounding is present.
    """
    covering = _real_source(applies_from=date(2025, 7, 1), applies_to=None)
    first = _rate(effective_from=date(2025, 8, 1), effective_until=date(2025, 8, 31))
    second = _rate(effective_from=date(2025, 9, 1))
    assert _failures(first, second, sources={_REAL_VERIFIABLE_SOURCE: covering}) == ""


def test_an_unknown_source_ref_is_refused() -> None:
    assert "unknown source_ref 'no-such-source-id'" in _failures(_rate(source_refs=("no-such-source-id",)), sources={})


def test_a_source_ref_whose_corpus_file_is_absent_is_refused() -> None:
    refusal = _failures(
        _rate(source_refs=("broken-source",)), sources={"broken-source": _absent_source("broken-source")}
    )
    assert "invalid source_ref 'broken-source'" in refusal


def test_an_unknown_legal_ref_is_refused() -> None:
    assert legal_ref_failures("row", ("no-such-legal-id",), {}, bundled_path(), set()) == [
        "row: unknown legal_ref 'no-such-legal-id'"
    ]


def test_a_legal_ref_whose_corpus_file_is_absent_is_refused() -> None:
    failures = legal_ref_failures(
        "row", ("broken-legal",), {"broken-legal": _absent_legal("broken-legal")}, bundled_path(), set()
    )
    assert len(failures) == 1
    assert failures[0].startswith("row: invalid legal_ref 'broken-legal':")


def test_a_verified_legal_ref_is_not_reverified() -> None:
    assert legal_ref_failures("row", ("already-verified",), {}, bundled_path(), {"already-verified"}) == []


def test_an_ungrounded_table_names_every_failure() -> None:
    refusal = _failures(
        _rate(legal_refs=("no-such-legal-id",), source_refs=("no-such-source-id",)),
        sources={},
    )
    assert refusal.startswith("IVA rate grounding verification failed")
    for expected in ("unknown legal_ref 'no-such-legal-id'", "unknown source_ref 'no-such-source-id'", _WINDOW_REFUSAL):
        assert expected in refusal
