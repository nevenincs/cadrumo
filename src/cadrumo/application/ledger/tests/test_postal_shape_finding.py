"""An unreadable postal code is reported exactly when it cost a territorial answer.

Driven through the real check and the real domain authorities: no doubles, and
no restatement of the five-digit rule the domain owns. The pair that matters is
the two negative cases -- a correctly printed foreign code raising nothing, and
an unreadable one raising -- because a check that fires on both would be noise
and a check that fires on neither would be dead.
"""

from __future__ import annotations

import pytest

from ....core.confirmation_gate import ConfirmationBlockReason
from ....core.draft_discrepancy import DraftDiscrepancyKind
from ..confirmation_gate import BLOCKING_REASON_BY_DISCREPANCY_KIND, confirmation_blockers
from ..deterministic_findings import deterministic_check_names, deterministic_findings
from ..evidence_draft import InvoiceDraft
from ..postal_shape_finding import postal_shape_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: A real address line of the shape the free-text validator passes through whole.
_ADDRESS_BLOB = "Calle Mayor 3, 28013 Madrid"

#: A correctly printed postal code that is not five digits. The check must stay
#: silent on it, because the country beside it already settles the territory.
_BRITISH_CODE = "SW1A 1AA"


def _kinds(draft: InvoiceDraft) -> list[str]:
    return [finding.field or "" for finding in postal_shape_findings(draft)]


class TestItFiresWhereTheCodeWasNeeded:
    """Spain settles no territory by itself, so the postal code is load-bearing there."""

    def test_a_spanish_party_whose_code_is_an_address_blob_is_reported(self) -> None:
        draft = InvoiceDraft(supplier_postal_code=_ADDRESS_BLOB, supplier_country="España")

        findings = postal_shape_findings(draft)

        assert len(findings) == 1
        assert findings[0].kind is DraftDiscrepancyKind.POSTAL_CODE_UNREADABLE
        assert findings[0].field == "supplier_postal_code"
        assert "issuing party" in findings[0].detail

    def test_an_unreadable_code_with_no_country_printed_is_reported(self) -> None:
        """Nothing established the party at all, so the code was the only evidence."""
        draft = InvoiceDraft(supplier_postal_code=_BRITISH_CODE)

        assert _kinds(draft) == ["supplier_postal_code"]

    def test_the_detail_quotes_what_the_field_actually_holds(self) -> None:
        """An operator shown the printed text can read the real code out of it."""
        draft = InvoiceDraft(supplier_postal_code=_ADDRESS_BLOB, supplier_country="España")

        assert _ADDRESS_BLOB in postal_shape_findings(draft)[0].detail


class TestItStaysSilentWhereTheCodeCostNothing:
    """The anti-noise half. Every fire must be genuine or the check trains clicking-through."""

    def test_a_correctly_printed_foreign_code_is_not_a_finding(self) -> None:
        """The country resolved, so the sub-national evidence was never consulted.

        This is the case that makes the check worth having rather than a
        nuisance: British and Dutch codes are not five digits and are perfectly
        correct, and refusing confirmation on them would be a large legitimate
        population blocked for no gain.
        """
        draft = InvoiceDraft(supplier_postal_code=_BRITISH_CODE, supplier_country="Reino Unido")

        assert postal_shape_findings(draft) == ()

    def test_a_readable_spanish_code_is_not_a_finding(self) -> None:
        draft = InvoiceDraft(supplier_postal_code="35001", supplier_country="España")

        assert postal_shape_findings(draft) == ()

    def test_an_absent_code_is_an_honest_absence_rather_than_a_misread(self) -> None:
        draft = InvoiceDraft(supplier_country="España")

        assert postal_shape_findings(draft) == ()

    def test_a_blank_code_is_treated_as_absent(self) -> None:
        draft = InvoiceDraft(supplier_postal_code="   ", supplier_country="España")

        assert postal_shape_findings(draft) == ()


class TestBothPartiesAreAskedIndependently:
    """On an issued invoice the CUSTOMER is the counterparty whose territory decides."""

    def test_the_customer_side_is_checked(self) -> None:
        draft = InvoiceDraft(customer_postal_code=_ADDRESS_BLOB, customer_country="España")

        findings = postal_shape_findings(draft)

        assert _kinds(draft) == ["customer_postal_code"]
        assert "billed party" in findings[0].detail

    def test_one_party_settled_does_not_silence_the_other(self) -> None:
        draft = InvoiceDraft(
            supplier_postal_code=_BRITISH_CODE,
            supplier_country="Reino Unido",
            customer_postal_code=_ADDRESS_BLOB,
            customer_country="España",
        )

        assert _kinds(draft) == ["customer_postal_code"]

    def test_both_unsettled_parties_are_each_reported(self) -> None:
        draft = InvoiceDraft(
            supplier_postal_code=_ADDRESS_BLOB,
            supplier_country="España",
            customer_postal_code=_ADDRESS_BLOB,
            customer_country="España",
        )

        assert _kinds(draft) == ["supplier_postal_code", "customer_postal_code"]


class TestTheCheckIsWiredWhereItMustBe:
    """Enrolment and blocking, both of which are by construction rather than by hand."""

    def test_the_check_runs_from_the_shared_deterministic_list(self) -> None:
        """Both readers call that list, so enrolment is what reaches the structured path."""
        draft = InvoiceDraft(supplier_postal_code=_ADDRESS_BLOB, supplier_country="España")

        assert "postal_code_shape" in deterministic_check_names()
        assert any(
            finding.kind is DraftDiscrepancyKind.POSTAL_CODE_UNREADABLE for finding in deterministic_findings(draft)
        )

    def test_the_kind_blocks_confirmation_under_its_own_reason(self) -> None:
        """Not an ambiguous identity: no candidates competed and no identifier is in doubt."""
        draft = InvoiceDraft(supplier_postal_code=_ADDRESS_BLOB, supplier_country="España")
        reviewed = draft.model_copy(update={"discrepancies": deterministic_findings(draft)})

        blockers = confirmation_blockers(reviewed)

        assert [blocker.reason for blocker in blockers] == [ConfirmationBlockReason.UNDETERMINED_ESTABLISHMENT]
        assert blockers[0].field == "supplier_postal_code"

    def test_every_discrepancy_kind_still_maps_to_a_reason(self) -> None:
        """The totality the gate asserts at import, restated where a reader looks."""
        assert set(BLOCKING_REASON_BY_DISCREPANCY_KIND) == set(DraftDiscrepancyKind)
