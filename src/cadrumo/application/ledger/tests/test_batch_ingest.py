"""One bad document must not end the run, and a re-run must not duplicate.

The two properties a bounded batch rests on. Neither is provable by reading the
happy path: a runner that aborts on the first failure still reports correctly
when nothing fails, and a key that folds in a clock still looks right within a
single run.
"""

from __future__ import annotations

import itertools

import pytest
from pydantic import ValidationError

from ....domain.iva.classification import InvoiceKind
from ...operator_actions._models import PreconditionVerdict
from ..batch_ingest import (
    BATCH_ITEM_STATUSES,
    BatchItemResult,
    BatchItemStatus,
    batch_item_identity,
    order_batch_items,
    order_batch_sources,
    summarise_batch,
)
from ..preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _reader_unavailable_verdict() -> PreconditionVerdict:
    """Return the typed refusal a row carries when no on-host reader is available."""
    return ledger_no_recovery_verdict(
        LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE,
        facts={"reader_available": False},
    )


_A = "a" * 64
_B = "b" * 64
_C = "c" * 64


def _item(
    address: str,
    status: BatchItemStatus,
    *,
    direction: InvoiceKind = InvoiceKind.RECEIVED,
    refusal_code: str | None = None,
    refusal_verdict: PreconditionVerdict | None = None,
) -> BatchItemResult:
    """Build one row, naming the fields a case varies.

    Spelled out rather than forwarded through ``**kwargs: object``, which
    erased every value to ``object`` and needed two suppressions to reach the
    constructor at all -- so the helper type-checked nothing about the rows the
    assertions below are built from.
    """
    return BatchItemResult(
        content_address=address,
        identity=batch_item_identity(content_address=address, direction=direction),
        direction=direction,
        status=status,
        refusal_code=refusal_code,
        refusal_verdict=refusal_verdict,
    )


def test_identity_is_derived_from_the_bytes_and_the_direction_only() -> None:
    """Two runs over the same document derive the same identity.

    Called twice with no shared state between the calls: a key folding in a
    clock, a filename or a run id would differ here, and every re-run would
    mint a duplicate instead of reporting a no-op.
    """
    first = batch_item_identity(content_address=_A, direction=InvoiceKind.RECEIVED)
    second = batch_item_identity(content_address=_A, direction=InvoiceKind.RECEIVED)

    assert first == second
    assert _A in first


def test_the_same_bytes_under_two_directions_are_two_identities() -> None:
    """A sale and a purchase are different records even from identical bytes.

    The positive control for the stability above: a key stable enough to be
    idempotent must still not collapse two genuinely distinct records, and an
    address-only key would.
    """
    issued = batch_item_identity(content_address=_A, direction=InvoiceKind.ISSUED)
    received = batch_item_identity(content_address=_A, direction=InvoiceKind.RECEIVED)

    assert issued != received


def test_ordering_is_invariant_under_input_shuffling() -> None:
    """However the filesystem enumerated the folder, the report reads the same."""
    items = [_item(_C, "ingested"), _item(_A, "ingested"), _item(_B, "no_op")]
    baseline = [item.content_address for item in order_batch_items(items)]

    # EVERY permutation, not a sample of them: the property is that no input
    # order survives into the output, and an unlucky sample could miss the one
    # ordering that did.
    for permutation in itertools.permutations(items):
        assert [item.content_address for item in order_batch_items(permutation)] == baseline

    assert baseline == [_A, _B, _C]


def test_processing_order_is_settled_before_any_work_happens() -> None:
    """Ordering only the finished rows would leave the WORK order enumeration-dependent.

    Which items an interrupted run completed then depends on directory order,
    so two interrupted runs over the same folder leave different work done.
    """
    sources = [(_C, "third.pdf"), (_A, "first.pdf"), (_B, "second.pdf")]
    assert [address for address, _ in order_batch_sources(sources)] == [_A, _B, _C]
    assert order_batch_sources(reversed(sources)) == order_batch_sources(sources)


def test_a_refused_item_does_not_remove_the_others_from_the_report() -> None:
    """The whole point: one bad document leaves every other row intact."""
    result = summarise_batch(
        [
            _item(
                _A,
                "refused",
                refusal_code="no_reader_available",
                refusal_verdict=_reader_unavailable_verdict(),
            ),
            _item(_B, "ingested"),
            _item(_C, "no_op"),
        ],
    )

    assert len(result.items) == 3
    assert result.count_of("ingested") == 1
    assert result.count_of("no_op") == 1
    assert result.count_of("refused") == 1


def test_the_run_fails_when_any_item_failed_not_when_the_first_did() -> None:
    """Exit status reads 'any item failed', so work still gets done on a failed run."""
    trailing_failure = summarise_batch(
        [_item(_A, "ingested"), _item(_C, "refused", refusal_code="x", refusal_verdict=_reader_unavailable_verdict())]
    )
    leading_failure = summarise_batch(
        [_item(_A, "refused", refusal_code="x", refusal_verdict=_reader_unavailable_verdict()), _item(_C, "ingested")]
    )

    assert trailing_failure.any_failed
    assert leading_failure.any_failed
    assert leading_failure.count_of("ingested") == 1


def test_a_clean_run_does_not_report_failure() -> None:
    """Positive control: any_failed must not be true of everything."""
    assert not summarise_batch([_item(_A, "ingested"), _item(_B, "no_op")]).any_failed


def test_an_item_awaiting_review_does_not_fail_the_run() -> None:
    """Held for an operator is neither a success nor a failure, and must not exit non-zero."""
    result = summarise_batch([_item(_A, "pending_review"), _item(_B, "ingested")])

    assert not result.any_failed
    assert result.count_of("pending_review") == 1


def test_the_summary_names_every_status_even_at_zero() -> None:
    """A status absent from the summary reads as 'not applicable', not 'none occurred'."""
    summary = summarise_batch([_item(_A, "ingested")]).summary

    assert set(summary) == BATCH_ITEM_STATUSES
    assert summary["refused"] == 0
    assert summary["ingested"] == 1


def test_a_refusal_must_carry_its_reason() -> None:
    """A refused row that cannot say why claims a failure it cannot explain."""
    with pytest.raises(ValidationError, match="must carry the reason"):
        _item(_A, "refused")


def test_a_reason_without_a_refusal_is_refused() -> None:
    """The other direction: a code under a non-refused status makes the rows and summary disagree."""
    with pytest.raises(ValidationError, match="only meaningful for a refused item"):
        _item(_A, "ingested", refusal_code="no_reader_available")


def test_the_content_address_must_be_a_real_digest() -> None:
    """A filename or a truncated hash in this field would break ordering and identity."""
    with pytest.raises(ValidationError):
        _item("invoice.pdf", "ingested")
