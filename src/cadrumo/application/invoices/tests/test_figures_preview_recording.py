"""The questions the desktop's invoice figures-preview recording asks are answered as the preview's rules say."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authority_lease_support import private_authority_lease
from .figures_preview_support import recorded_preview_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_QUESTIONS: Final = (
    Path(__file__).resolve().parents[5] / "dev/fixtures/ledger-recording-questions/ledgerInvoicePreview.json"
)
_ASKED: Final[dict[str, dict[str, Any]]] = json.loads(_QUESTIONS.read_text(encoding="utf-8"))

#: Worked from the rules: 550 plus 2 x 275 is a base of 1100.00; IVA at 21% is 231.00, so the total is 1331.00; a 15%
#: retention of 165 leaves 1166.00; a stated IVA a cent off is within the tolerance and one ten cents off is not.
_TOTALS: Final = {
    "two_lines": {"base": "1100.00", "iva": "231.00", "total": "1331.00", "net_of_retention": "1331.00"},
    "retention_15": {"base": "1100.00", "iva": "231.00", "total": "1331.00", "net_of_retention": "1166.00"},
    "stated_iva_within": {"base": "1100.00", "iva": "231.01", "total": "1331.01", "net_of_retention": "1331.01"},
}
_VERDICTS: Final = {
    "bare_2026": ("incomplete", None),
    "two_lines": ("would_accept", None),
    "retention_15": ("would_accept", None),
    "retention_above_base": ("would_refuse", "retention_amount_above_base"),
    "stated_iva_within": ("would_accept", None),
    "stated_iva_refused": ("would_refuse", "line_iva_mismatch"),
    "rate_not_in_force": ("would_refuse", "line_rate_not_in_force"),
}


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with private_authority_lease() as leased:
        yield leased


def test_the_stated_expectations_name_committed_questions() -> None:
    assert set(_VERDICTS) <= set(_ASKED)
    assert set(_TOTALS) <= set(_VERDICTS)


@pytest.mark.parametrize("name", _ASKED)
def test_every_committed_question_is_answered_with_a_verdict(name: str, operation: PinnedAuthorityOperation) -> None:
    result = recorded_preview_result(_ASKED[name], operation)

    assert result["verdict"] in {"would_accept", "would_refuse", "incomplete"}


@pytest.mark.parametrize("name", _VERDICTS)
def test_a_stated_question_is_answered_as_its_rule_says(name: str, operation: PinnedAuthorityOperation) -> None:
    result = recorded_preview_result(_ASKED[name], operation)

    assert (result["verdict"], result["refusal_code"]) == _VERDICTS[name]


@pytest.mark.parametrize("name", _TOTALS)
def test_the_totals_are_the_lines_worked_by_hand(name: str, operation: PinnedAuthorityOperation) -> None:
    totals = recorded_preview_result(_ASKED[name], operation)["totals"]

    assert {key: totals[key]["decimal"] for key in _TOTALS[name]} == _TOTALS[name]
