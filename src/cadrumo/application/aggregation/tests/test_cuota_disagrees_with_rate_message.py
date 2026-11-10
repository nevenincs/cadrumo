"""The refused cuota reaches the operator with the row's own figures, in the filer's language.

Expected sentences are written out by hand: base 100.00 at 21% gives 21.00, and the
row records 25.00. Real-behaviour: real :class:`Transaction` rows through the real
IVA ledger classifier and the real source diagnostic projection. No mocks.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.config import override_settings
from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.transactions.models import TransactionCatalogue
from ..iva_ledger import IvaLedgerAggregationIssue, IvaLedgerAggregationIssueReason
from ..modelo_bindings_iva import selected_scope_iva_evidence_diagnostics
from .iva_authority_support import aggregate_iva_ledger_observations
from .iva_ledger_row_support import uncategorised_sale_row

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_PERIOD = Period.from_year_and_code(_YEAR, "4T")
_ON = date(_YEAR, 11, 6)

_FIGURES = ("100.00 EUR", "21%", "21.00 EUR", "25.00 EUR")


def _issues(*, base: str, rate: str, cuota: str) -> tuple[IvaLedgerAggregationIssue, ...]:
    row = uncategorised_sale_row(
        "row-figures", booked=_ON, base=Decimal(base), iva_rate=Decimal(rate), iva_amount=Decimal(cuota)
    )
    catalogue = TransactionCatalogue.model_validate({"transactions": {row.transaction_id: row}})
    return tuple(aggregate_iva_ledger_observations(catalogue, period=_PERIOD).issues)


@pytest.mark.parametrize("language", [language.value for language in OutputLanguage])
def test_the_diagnostic_carries_base_rate_expected_and_recorded_cuota_in_the_requested_language(language: str) -> None:
    with override_settings(cadrumo_output_language=language):
        issues = _issues(base="100.00", rate="0.21", cuota="25.00")
        (diagnostic,) = selected_scope_iva_evidence_diagnostics(issues, resolver_id="ledger_iva_aggregation")

    assert [issue.reason for issue in issues] == [IvaLedgerAggregationIssueReason.CUOTA_DISAGREES_WITH_RATE]
    assert diagnostic.message_language is OutputLanguage(language)
    for figure in _FIGURES:
        assert figure in diagnostic.message
    assert "selected-scope" not in diagnostic.message


def test_the_sentence_is_worded_in_each_language() -> None:
    expected = {
        "en": "Declared IVA cuota 25.00 EUR does not match base 100.00 EUR at rate 21%, which gives 21.00 EUR.",
        "es": "La cuota de IVA declarada 25.00 EUR no coincide con la base 100.00 EUR al tipo 21%, que da 21.00 EUR.",
        "ca": "La quota d'IVA declarada 25.00 EUR no coincideix amb la base 100.00 EUR al tipus 21%, que dona 21.00 EUR.",
        "hu": "A megadott 25.00 EUR IVA-összeg nem egyezik a(z) 100.00 EUR alap és a(z) 21% kulcs szorzatával, "
        "ami 21.00 EUR.",
    }
    for language, sentence in expected.items():
        with override_settings(cadrumo_output_language=language):
            (issue,) = _issues(base="100.00", rate="0.21", cuota="25.00")
        assert issue.detail.startswith(sentence), language


def test_a_rate_stored_with_trailing_zeros_is_a_plain_percentage() -> None:
    with override_settings(cadrumo_output_language="en"):
        (issue,) = _issues(base="200.00", rate="0.1000", cuota="25.00")

    assert "at rate 10%," in issue.detail
    assert "20.00 EUR" in issue.detail


def test_a_cent_of_difference_raises_no_finding_and_two_cents_do() -> None:
    assert _issues(base="100.00", rate="0.21", cuota="21.01") == ()
    assert [issue.reason for issue in _issues(base="100.00", rate="0.21", cuota="21.02")] == [
        IvaLedgerAggregationIssueReason.CUOTA_DISAGREES_WITH_RATE
    ]


def test_another_refusal_keeps_its_technical_marker_and_names_no_language() -> None:
    issue = IvaLedgerAggregationIssue(
        transaction_id="t-1", reason=IvaLedgerAggregationIssueReason.MISSING_IVA_RATE, detail="no rate"
    )
    (diagnostic,) = selected_scope_iva_evidence_diagnostics((issue,), resolver_id="ledger_iva_aggregation")

    assert diagnostic.message == "selected-scope IVA evidence failure: missing_iva_rate"
    assert diagnostic.message_language is None
