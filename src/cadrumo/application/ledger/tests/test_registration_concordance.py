"""A foreign registration settles no place alone, corroborates quietly, and conflicts loudly.

Rung one used to be the strongest one: a printed ``DE`` prefix resolved to
``EU_MEMBER`` and stopped the walk. Every Member State registers non-residents on
exactly the terms Spain does, so that read a party's REGISTRATION as its PLACE —
and it did so on one side only, because a Spanish registration was already
correctly refused. The foreign direction was the dangerous one: a
German-registered entity actually established in Spain resolved silently and
confidently, where its Spanish mirror failed loud to the operator.

Three properties are gated here and they fail in three different directions.

**A registration alone never settles a territory.** If it does, the silent
``EU_MEMBER`` is back and the whole change is undone.

**Concordant papers still resolve with no question.** That is the cost the split
was designed not to pay. A gate proving only the refusal would be satisfied by a
ladder that asks about every foreign invoice, which is a worse product.

**Conflicted papers surface instead of resolving either way.** A foreign IVA
number beside Spanish-indicating evidence is the characteristic face of an
establecimiento permanente operating here, and preferring either side would put a
guess behind a filing.

Real store, real registry, real rate schedule: the repository is the shipped
encrypted one over a real SQLite engine, and the Spanish rate check asks the
bundled registry rather than comparing a literal.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ._ledger_value_fixtures import repository

__all__ = ["repository"]

from ....core.classifier_input_source import ClassifierInputSource
from ....domain.iva.classification import IvaTerritorialScope
from ....domain.iva.schema import EUMemberState
from ..counterparty_establishment import ConfirmedCounterpartyFactsRepository
from ..establishment_ladder import (
    CounterpartyEstablishment,
    EstablishmentRung,
    resolve_counterparty_establishment_scope,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "37373737-3737-4737-8737-373737373738"
runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")

_GERMAN_IVA = "DE811234567"
_SPANISH_CIF = "B12345674"

_MADRID = "28013"
_BERLIN = "10115"

#: The reverse-charge mention exactly as RD 1619/2012 art. 6.1.m fixes it. An
#: issuer printing it has stated it did not have to charge here, which is what
#: LIVA art. 84.Uno.2 makes true of a supplier not established in the territory.
_REVERSE_CHARGE = "inversión del sujeto pasivo"

#: A Spanish general-tier rate, and the date it is asked about. The gate does not
#: assert the percentage means anything by itself -- the registry is asked
#: whether it carries the rate on the date, so a schedule change moves the gate
#: with it rather than leaving a stale literal behind.
_SPANISH_GENERAL_RATE = Decimal("21")
_ON_DATE = date(2026, 3, 10)


def _resolve(
    repository: ConfirmedCounterpartyFactsRepository,
    *,
    tax_identifier: str | None = None,
    country_name: str | None = None,
    postal_code: str | None = None,
    regime_legend: str | None = None,
    charged_iva_rates: tuple[Decimal, ...] = (),
    on_date: date | None = _ON_DATE,
) -> CounterpartyEstablishment:
    return resolve_counterparty_establishment_scope(
        bucket_id=_BUCKET_ID,
        tax_identifier=tax_identifier,
        stated_country_name=country_name,
        postal_code=postal_code,
        regime_legend=regime_legend,
        charged_iva_rates=charged_iva_rates,
        on_date=on_date,
        repository=repository,
    )


class TestARegistrationAloneSettlesNoTerritory:
    """The rung that was removed, asserted from both sides of the symmetry."""

    def test_a_german_iva_number_alone_establishes_nothing(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """The defect itself: this used to return EU_MEMBER and stop the ladder."""
        resolved = _resolve(repository, tax_identifier=_GERMAN_IVA)

        assert resolved.scope is None
        assert resolved.rung is None
        assert not resolved.established

    def test_a_spanish_identifier_alone_establishes_nothing(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """The side that was already right, pinned so a fix cannot arrive by tightening it."""
        resolved = _resolve(repository, tax_identifier=_SPANISH_CIF)

        assert resolved.scope is None
        assert resolved.rung is None

    def test_both_registrations_leave_the_territory_equally_unsettled(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """The symmetry itself. A repair tightening one side reddens exactly this."""
        german = _resolve(repository, tax_identifier=_GERMAN_IVA)
        spanish = _resolve(repository, tax_identifier=_SPANISH_CIF)

        assert (german.scope, german.rung) == (spanish.scope, spanish.rung) == (None, None)

    def test_the_registration_still_settles_the_identification_terminally(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """The other half of the split: decisive for the fact registration IS.

        Paired with the case above deliberately. The same call settles one fact
        and refuses the other, which is the whole content of the split — a gate
        asserting only the refusal would be satisfied by a ladder that had
        stopped reading the number at all.
        """
        resolved = _resolve(repository, tax_identifier=_GERMAN_IVA)

        assert resolved.identification_state is EUMemberState.DE
        assert resolved.scope is None


class TestConcordantPapersResolveSilently:
    """The cost the split was designed not to pay."""

    def test_a_printed_address_country_settles_it_without_the_registration(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """The commonest concordant shape, and it needs no corroboration rule.

        The address rung answers on its own authority: a German address places a
        German-established party whatever State registered it. This is why the
        prefix could be demoted without asking about most foreign invoices.
        """
        resolved = _resolve(repository, tax_identifier=_GERMAN_IVA, country_name="Alemania", postal_code=_BERLIN)

        assert resolved.scope is IvaTerritorialScope.EU_MEMBER
        assert resolved.rung is EstablishmentRung.ADDRESS_COUNTRY
        assert resolved.source is ClassifierInputSource.DOCUMENT_EVIDENCE
        assert resolved.registration_conflict is None

    def test_a_reverse_charge_mention_corroborates_where_no_address_country_was_printed(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """The concordance rung proper: registration plus an independent treatment."""
        resolved = _resolve(repository, tax_identifier=_GERMAN_IVA, regime_legend=_REVERSE_CHARGE)

        assert resolved.scope is IvaTerritorialScope.EU_MEMBER
        assert resolved.rung is EstablishmentRung.CONCORDANT_REGISTRATION
        assert resolved.identification_state is EUMemberState.DE
        assert resolved.registration_conflict is None

    def test_the_mention_corroborates_nothing_without_a_registration(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """The control. Concordance needs two signals, so one of them alone is not it."""
        resolved = _resolve(repository, regime_legend=_REVERSE_CHARGE)

        assert resolved.scope is None
        assert resolved.rung is None

    def test_the_mention_stops_corroborating_when_spanish_iva_is_charged_beside_it(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """A document disagreeing with itself is not a corroboration.

        The shipped legend record says this mention expects no repercutido line,
        so a charged Spanish rate beside it contradicts the words printed above
        it. Reading the phrase while ignoring the arithmetic would take the
        issuer's claim and discard the issuer's evidence against it.
        """
        resolved = _resolve(
            repository,
            tax_identifier=_GERMAN_IVA,
            regime_legend=_REVERSE_CHARGE,
            charged_iva_rates=(_SPANISH_GENERAL_RATE,),
        )

        assert resolved.scope is not IvaTerritorialScope.EU_MEMBER
        assert resolved.rung is not EstablishmentRung.CONCORDANT_REGISTRATION


class TestConflictedPapersSurface:
    """The dangerous population, failing loud where it used to resolve silently."""

    def test_spanish_iva_charged_beside_a_foreign_registration_conflicts(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """The design's named conflict fixture, and never a silent EU_MEMBER."""
        resolved = _resolve(
            repository,
            tax_identifier=_GERMAN_IVA,
            charged_iva_rates=(_SPANISH_GENERAL_RATE,),
        )

        assert resolved.conflicted
        assert resolved.scope is None
        assert resolved.registration_conflict is not None
        assert resolved.registration_conflict.identification_state is EUMemberState.DE
        assert resolved.registration_conflict.spain_indicating

    def test_a_spanish_address_beside_a_foreign_registration_conflicts(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """The other face of the same entity: registered abroad, addressed here."""
        resolved = _resolve(repository, tax_identifier=_GERMAN_IVA, country_name="España", postal_code=_MADRID)

        assert resolved.conflicted
        assert resolved.scope is None

    def test_the_postal_rung_never_quietly_answers_a_conflicted_document(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """Why the conflict check runs BEFORE the ordinary rungs.

        A Spanish address opens the postal rung, which would resolve Madrid to
        the peninsula perfectly well — a well-formed answer to a question the
        document has not settled. Checking after the rungs would let exactly the
        dangerous population resolve, just to a different wrong value.
        """
        resolved = _resolve(repository, tax_identifier=_GERMAN_IVA, country_name="España", postal_code=_MADRID)

        assert resolved.scope is not IvaTerritorialScope.ES_MAINLAND
        assert resolved.rung is not EstablishmentRung.SPANISH_POSTAL_CODE

    def test_a_spanish_registration_with_a_spanish_address_does_not_conflict(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """The control that keeps the conflict specific to a FOREIGN registration.

        An ordinary domestic invoice prints a Spanish identifier and a Spanish
        address, and nothing about that disagrees. A conflict rule firing here
        would put a finding on the commonest document there is.
        """
        resolved = _resolve(repository, tax_identifier=_SPANISH_CIF, country_name="España", postal_code=_MADRID)

        assert not resolved.conflicted
        assert resolved.scope is IvaTerritorialScope.ES_MAINLAND
        assert resolved.rung is EstablishmentRung.SPANISH_POSTAL_CODE

    def test_a_foreign_rate_charged_beside_a_foreign_registration_does_not_conflict(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """Charged tax is only Spain-indicating when the rate is a SPANISH one.

        A German supplier invoicing at the German general rate has said nothing
        about Spain. Reading any charged tax as Spanish tax would put a finding
        on ordinary foreign invoices and train an operator to dismiss it.
        """
        resolved = _resolve(
            repository,
            tax_identifier=_GERMAN_IVA,
            regime_legend=_REVERSE_CHARGE,
            charged_iva_rates=(Decimal("19"),),
        )

        assert not resolved.conflicted

    def test_an_unreadable_date_raises_no_conflict_from_a_rate_it_cannot_check(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """Inconclusive contributes nothing in either direction.

        A false conflict blocks a legitimate filing, so a rate nobody could
        verify against the schedule must not raise one — and it supplies no
        corroboration either, so the operation falls to a question rather than
        to a value.
        """
        resolved = _resolve(
            repository,
            tax_identifier=_GERMAN_IVA,
            charged_iva_rates=(_SPANISH_GENERAL_RATE,),
            on_date=None,
        )

        assert not resolved.conflicted
        assert resolved.scope is None
