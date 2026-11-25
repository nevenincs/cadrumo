"""The link command correlates a prefix selector with the one invoice it resolved to."""

from __future__ import annotations

from uuid import uuid4

import pytest

from ....application.ledger.link_operation import LedgerLinkOperationResult
from ..ledger_commands import _link_refusal
from ..operation_ledger_export_link import _link_invoice_selector_invalid

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FIRST = "ab" + "1" * 62
_SECOND = "ab" + "2" * 62


def _refused(reason: str, invoice_id: str, candidates: tuple[str, ...] = ()) -> LedgerLinkOperationResult:
    return LedgerLinkOperationResult.model_validate(
        {
            "profile_id": uuid4(),
            "transaction_id": "0123456789ab",
            "invoice_id": invoice_id,
            "outcome": "refused",
            "reason": reason,
            "candidate_invoice_ids": candidates,
        }
    )


def test_a_refusal_must_echo_the_selector_exactly() -> None:
    result = _refused("missing_invoice", "ab")

    assert not _link_invoice_selector_invalid(result, "ab")
    assert _link_invoice_selector_invalid(result, "abc")


def test_ambiguous_refusal_names_the_prefix_and_every_candidate() -> None:
    result = _refused("ambiguous_invoice", "ab", (_FIRST, _SECOND))

    message = str(_link_refusal(result))

    assert "ab" in message
    assert _FIRST in message and _SECOND in message


@pytest.mark.parametrize("candidates", [(), (_FIRST,), (_FIRST, _FIRST)])
def test_an_ambiguous_refusal_needs_two_distinct_candidates(candidates: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="distinct candidates"):
        _refused("ambiguous_invoice", "ab", candidates)


def test_only_an_ambiguous_refusal_carries_candidates() -> None:
    with pytest.raises(ValueError, match="only an ambiguous"):
        _refused("missing_invoice", "ab", (_FIRST, _SECOND))
