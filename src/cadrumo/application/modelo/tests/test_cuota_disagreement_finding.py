"""A checked revision states each disagreeing cuota's own figures, in the requested language.

Figures are worked by hand: base 100.00 at 21% gives 21.00 and the row records
25.00; base 200.00 at 10% gives 20.00 and the row records 20.01, inside the
one-cent tolerance. Rows come from the real ledger reader fixture and the
finding is rendered through the real catalogue.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.calculation_revision_sources import CalculationSourceIssue
from ....domain.modelos.verification_report import ModeloVerificationFinding
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ...aggregation.tests.iva_ledger_row_support import uncategorised_sale_row
from ..finding_message_text import finding_message_text
from ..preconditions import ModeloPreconditionFailure
from ..verification_iva_evidence import append_iva_selected_scope_evidence_finding
from ..work_form_findings import finding_action_locale_key
from .test_unrecordable_deduction_documents import Transactions, work_and_target

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_ON = date(filing_year_envelope().horizon, 2, 15)
_KEY = "application.modelo.findings.iva_cuota_disagrees_with_rate"


def _row(row_id: str, *, base: str, rate: str, cuota: str) -> Transaction:
    return uncategorised_sale_row(
        row_id, booked=_ON, base=Decimal(base), iva_rate=Decimal(rate), iva_amount=Decimal(cuota)
    )


def _issue(transaction_id: str) -> CalculationSourceIssue:
    return CalculationSourceIssue(
        reason="iva_selected_scope_evidence_failure",
        binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        message="selected-scope IVA evidence failure",
        source_ref=f"transaction:{transaction_id}",
    )


def _verify(
    rows: tuple[Transaction, ...],
) -> tuple[list[ModeloVerificationFinding], dict[int, ModeloPreconditionFailure]]:
    repository = Transactions(
        bucket_id="13000000-0000-4000-8000-000000000303",
        catalogue=TransactionCatalogue.from_transactions(rows),
    )
    work, target = work_and_target(repository.bucket_id, tuple(_issue(row.transaction_id) for row in rows))
    findings: list[ModeloVerificationFinding] = []
    failures: dict[int, ModeloPreconditionFailure] = {}
    append_iva_selected_scope_evidence_finding(
        work_unit=work,
        target=target,
        transaction_repository=repository,
        findings=findings,
        failures_by_finding_id=failures,
    )
    return findings, failures


_SENTENCES = {
    OutputLanguage.EN: "records a cuota of 25.00 EUR, but its base of 100.00 EUR at a rate of 21% gives 21.00 EUR",
    OutputLanguage.ES: "registra una cuota de 25,00 EUR, pero su base de 100,00 EUR al tipo del 21 % da 21,00 EUR",
    OutputLanguage.CA: "registra una quota de 25,00 EUR, però la seva base de 100,00 EUR al tipus del 21 % dona 21,00 EUR",
    OutputLanguage.HU: "25,00 EUR IVA-összeget rögzít, de a(z) 100,00 EUR alap 21 százalékos kulcs mellett 21,00 EUR-t ad",
}


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_the_finding_carries_base_rate_expected_and_recorded_cuota_in_the_requested_language(
    language: OutputLanguage,
) -> None:
    bad = _row("bad", base="100.00", rate="0.21", cuota="25.00")
    findings, failures = _verify((bad,))

    (finding,) = findings
    assert finding.message_locale_key == _KEY
    assert finding.message_facts["transaction_ids"] == bad.transaction_id
    assert id(finding) in failures
    assert finding_action_locale_key(finding) == "application.modelo.work_form.finding_action.correct_and_recalculate"
    text = finding_message_text(finding, language)
    assert _SENTENCES[language] in " ".join(text.split()), text
    assert bad.transaction_id not in text


def test_only_the_disagreeing_rows_get_a_figure_finding_and_the_rest_keep_the_general_one() -> None:
    bad = _row("bad", base="100.00", rate="0.21", cuota="25.00")
    within_a_cent = _row("cent", base="200.00", rate="0.10", cuota="20.01")
    other_bad = _row("other", base="200.00", rate="0.10", cuota="30.00")
    findings, _failures = _verify((bad, within_a_cent, other_bad))

    figured = {
        finding.message_facts["transaction_ids"]: finding for finding in findings if finding.message_locale_key == _KEY
    }
    assert set(figured) == {bad.transaction_id, other_bad.transaction_id}
    assert figured[other_bad.transaction_id].message_facts["expected_cuota"] == Decimal("20.00")
    assert figured[other_bad.transaction_id].message_facts["recorded_cuota"] == Decimal("30.00")
    assert figured[other_bad.transaction_id].message_facts["iva_rate_percent"] == Decimal("10")
    (general,) = (finding for finding in findings if "source_ref_ids" in finding.message_facts)
    assert general.message_facts["source_ref_ids"] == f"transaction:{within_a_cent.transaction_id}"


def test_a_row_whose_cuota_agrees_leaves_only_the_general_finding() -> None:
    fine = _row("fine", base="100.00", rate="0.21", cuota="21.00")
    findings, _failures = _verify((fine,))

    assert [finding.message_locale_key for finding in findings] != [_KEY]
    assert all(finding.message_locale_key != _KEY for finding in findings)
