"""The LIRPF art. 30.2.5.a cap reaches the shipped aggregation, both limbs and all.

The rule and the resolver were correct before this test existed and never ran: the
production construction site of :class:`RentaDeductibilityContext` supplied no
insured-person counts, so every filer got a flat 500 euros for the contribuyente
alone however many people the policy actually covered. An expressible fix that
production never reaches is not a fix, so these tests drive the whole path --
stored profile facts, the domain count, the context, the registry cap variants --
rather than calling the resolver with counts handed to it.

The article, verbatim from the bundled consolidated corpus:

    a) Las primas de seguro de enfermedad satisfechas por el contribuyente en la
    parte correspondiente a su propia cobertura y a la de su conyuge e hijos
    menores de veinticinco anos que convivan con el. El limite maximo de deduccion
    sera de 500 euros por cada una de las personas senaladas anteriormente o de
    1.500 euros por cada una de ellas con discapacidad.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.resources import resources
from ....domain.categories.spending_category import SpendingCategory
from ....domain.invoices import InvoiceCatalogue
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from .._renta_ledger import (
    _SEGURO_DISCAPACIDAD_VARIANT,
    _SEGURO_GENERAL_VARIANT,
    aggregate_renta_ledger_expenses,
)
from ._renta_income_aggregation_support import _period
from ._secure_objects_fixtures import SECURE_OBJECTS_BUCKET_ID

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FILING_YEAR = 2025
_ANNUAL = _period(_FILING_YEAR, "0A")

#: Well above any limb the article grants, so the deducted amount is always the
#: cap rather than the premium. A premium under the cap would pass whatever the
#: cap resolved to and would prove nothing.
_PREMIUM = Decimal("9000.00")


def _seguro_transaction() -> Transaction:
    """Return a real, ACTIVE, business-classified seguro de enfermedad premium."""
    raw = RawTransaction(
        provider_transaction_id="seguro-salud",
        booked_date=date(_FILING_YEAR, 3, 1),
        value_date=date(_FILING_YEAR, 3, 1),
        amount=_PREMIUM,
        currency="EUR",
        counterparty="Aseguradora SA",
        description="prima seguro de enfermedad",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(_FILING_YEAR, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": "seguro salud"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": SpendingCategory.SEGUROS_SALUD_AUTONOMO.value,
            "taxable_base": _PREMIUM,
            "iva_rate": None,
            "iva_amount": None,
            "irpf_category": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_FILING_YEAR, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _profile(**facts: str) -> UserProfileRecord:
    """Return a real UserProfileRecord carrying the stored family facts, no mocks."""
    return UserProfileRecord(
        profile_id="55555555-5555-4555-8555-555555555555",
        setup_state=ProfileSetupState.COMPLETE,
        facts=tuple(UserProfileFact(path=path, value=value) for path, value in facts.items()),
    )


def _deducted(profile: UserProfileRecord | None) -> Decimal:
    """Run the shipped aggregation and return what it allowed for the premium."""
    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((_seguro_transaction(),)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL,
        profile_record=profile,
    )
    assert len(result.observations) == 1, (
        f"the seguro premium did not survive aggregation; issues={[i.reason for i in result.issues]}"
    )
    return result.observations[0].deductible_amount


def test_a_lone_contribuyente_is_capped_at_the_ordinary_limb() -> None:
    """One insured person, no discapacidad: 500 euros, the ordinary limit."""
    assert _deducted(_profile()) == Decimal("500")


def test_a_married_couple_is_capped_at_two_ordinary_limbs() -> None:
    """The defect in one line: the cap is a sum over persons, not one flat limit.

    The article insures "su propia cobertura y a la de su conyuge". Before the
    counts were wired the answer here was 500 for a policy the statute caps at
    1.000, so the filer deducted half what the law allowed and nothing in the
    product said so.
    """
    couple = _profile(**{"renta_taxpayer.marital_status": "2"})

    assert _deducted(couple) == Decimal("1000")


def test_a_declared_discapacidad_moves_that_person_to_the_higher_limb() -> None:
    """RIRPF art. 72 qualifies a grado at or above 33 for the 1.500 euro limit."""
    couple = _profile(
        **{"renta_taxpayer.marital_status": "2", "renta_spouse.disability_grade": "65"},
    )

    assert _deducted(couple) == Decimal("2000")


def test_a_cohabiting_child_under_twenty_five_joins_the_cap() -> None:
    """The article names hijos menores de veinticinco anos que convivan con el."""
    household = _profile(
        **{
            "renta_taxpayer.marital_status": "2",
            "renta_family.descendiente.0.birth_date": "2012-05-04",
            "renta_family.descendiente.0.convivencia": "true",
        },
    )

    assert _deducted(household) == Decimal("1500")


def test_a_child_of_twenty_five_or_more_does_not_raise_the_cap() -> None:
    """Membership is this article's age limb, not the wider Art. 58.1 one.

    Art. 58.1 would still admit this descendant on its "under 25 OR any
    discapacidad" test. Borrowing that population would over-grant the cap to a
    person this article does not name -- an error in the opposite direction from
    the one being fixed, and just as wrong.
    """
    household = _profile(
        **{
            "renta_family.descendiente.0.birth_date": "1995-05-04",
            "renta_family.descendiente.0.convivencia": "true",
        },
    )

    assert _deducted(household) == Decimal("500")


def test_the_wired_variant_ids_are_the_ones_the_shipped_rule_declares() -> None:
    """The counts are keyed by variant id, so a corpus rename must red here.

    The resolver refuses a count naming a variant the rule does not declare, but
    the opposite slip is silent: rename a variant in the corpus and the wiring
    keeps supplying the old key, the population it counted resolves to nothing,
    and the cap quietly falls back to the ordinary limb for everyone. Asserting
    the two names agree is what makes that loud.
    """
    profiles = resources().category_profiles.get(_FILING_YEAR)
    rule = profiles[SpendingCategory.SEGUROS_SALUD_AUTONOMO].proportionality
    declared = {variant.id for variant in rule.statutory_cap_variants}

    assert declared == {_SEGURO_GENERAL_VARIANT, _SEGURO_DISCAPACIDAD_VARIANT}
