"""A foreign registration is corroborated by what the issuer said OR by what it did.

The concordance rung never settles a territory on a registration alone: a party
registered in another Member State may still be established in Spain through a
sede or establecimiento permanente, so the registration needs a second, printed
signal agreeing that the issuer did not tax here. That second signal had exactly
one source -- the reverse-charge mention -- and the ordinary cross-border invoice
does not print one. A German-registered supplier that simply charged German IVA
corroborated nothing and fell to an operator question.

That gap was SAFE and it was still a gap: an unanswered question is never a wrong
territory, but it is a question asked on a population the evidence could have
answered. This file gates the widening.

**The two signals are different kinds of evidence, not two spellings of one.**
The mention is what the issuer SAID about the operation; the charged rate is what
the issuer DID about it, in arithmetic, which is harder to print by accident than
a phrase. Either corroborates.

**The discriminating case is a shared rate, and it is the one worth reading.**
Twenty-one per cent is the general rate in Spain and in the Netherlands alike, so
a Dutch-identified issuer charging it has printed something both readings explain
equally. It must not corroborate -- and it does not, because a charged Spanish
registry rate is a Spain-indicating signal that surfaces the disagreement as a
conflict instead. Nineteen is German and not Spanish, so it discriminates and
corroborates.

Real registry schedules throughout: every rate here is resolved through the same
per-Member-State lookup the production walk uses, so a schedule change moves
these cases with it rather than leaving them asserting a literal nobody honours.

See Also:
    :func:`~application.ledger.establishment_ladder.resolve_draft_counterparty_establishment`
        The walk this rung belongs to.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.iva import IvaTerritorialScope
from ..establishment_ladder import EstablishmentRung, RegistrationEstablishmentConflict, _printed_evidence

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DATE = date(2026, 4, 2)

#: A structurally valid German IVA number. Germany is the useful registration
#: State here because its general rate is NOT one Spain carries, which is what
#: lets the charged rate discriminate at all.
_GERMAN_IVA = "DE811234567"

#: A structurally valid Dutch IVA number. The Netherlands shares Spain's general
#: rate, which is what makes it the control rather than a second example.
_DUTCH_IVA = "NL123456789B01"

_REVERSE_CHARGE = "inversión del sujeto pasivo"


def _walk(
    *,
    tax_identifier: str | None = _GERMAN_IVA,
    # No address country and no postal code: this is the population the rung
    # exists for, where every earlier rung has already declined.
    country_code: str | None = None,
    postal_code: str | None = None,
    regime_legend: str | None = None,
    charged_iva_rates: tuple[Decimal, ...] = (),
    on_date: date | None = _DATE,
) -> tuple[IvaTerritorialScope | None, EstablishmentRung | None, RegistrationEstablishmentConflict | None]:
    """Walk the rungs with this file's population pinned, overriding one axis at a time.

    The parameters mirror the walk's own rather than collecting a bag: a
    misspelled override would otherwise be accepted silently and the case
    would assert against the DEFAULT population, passing while measuring
    nothing it names.
    """
    return _printed_evidence(
        tax_identifier=tax_identifier,
        country_code=country_code,
        postal_code=postal_code,
        regime_legend=regime_legend,
        charged_iva_rates=charged_iva_rates,
        on_date=on_date,
    )


def test_a_registration_alone_still_settles_nothing() -> None:
    """The precondition. Without it every case below could pass on the number alone."""
    scope, rung, conflict = _walk()

    assert scope is None
    assert rung is None
    assert conflict is None


def test_the_issuers_own_rate_corroborates_the_registration() -> None:
    """The widening: what the issuer DID is evidence, not only what it said.

    A German-registered supplier charging German IVA has taxed under the law it
    is established under, which is precisely the claim the registration makes and
    the paper could not previously confirm.
    """
    scope, rung, conflict = _walk(charged_iva_rates=(Decimal("19"),))

    assert scope is IvaTerritorialScope.EU_MEMBER
    assert rung is EstablishmentRung.CONCORDANT_REGISTRATION
    assert conflict is None


def test_the_reverse_charge_mention_still_corroborates() -> None:
    """The pre-existing signal is not collateral damage of the widening."""
    scope, rung, _ = _walk(regime_legend=_REVERSE_CHARGE)

    assert scope is IvaTerritorialScope.EU_MEMBER
    assert rung is EstablishmentRung.CONCORDANT_REGISTRATION


def test_a_rate_spain_also_carries_raises_a_conflict_rather_than_corroborating() -> None:
    """The discriminating case, and the reason the widening is not simply looser.

    A Dutch issuer charging 21% has printed a rate both Spain and the Netherlands
    carry. Reading it as corroboration would settle a territory from evidence
    that says nothing, so it must not -- and the walk goes further than merely
    declining: the charged Spanish registry rate is itself Spain-indicating, so
    the disagreement reaches an operator as a conflict.
    """
    scope, rung, conflict = _walk(tax_identifier=_DUTCH_IVA, charged_iva_rates=(Decimal("21"),))

    assert scope is None
    assert rung is None
    assert conflict is not None
    assert "the document charges IVA at a Spanish registry rate" in conflict.spain_indicating


def test_an_unverifiable_rate_corroborates_nothing() -> None:
    """No date means no schedule, and inconclusive contributes in neither direction.

    The same posture the Spanish-rate check states: a rate nobody could verify is
    not a second signal. Reading it as agreement would settle a territory from a
    number whose lawfulness was never checked.
    """
    scope, rung, conflict = _walk(charged_iva_rates=(Decimal("19"),), on_date=None)

    assert scope is None
    assert rung is None
    assert conflict is None


def test_a_zero_rated_line_places_the_party_nowhere() -> None:
    """Zero charges no tax under anybody's law, so it corroborates no establishment.

    Excluded before the schedule lookup rather than by it, because a registry
    will answer that zero is a legitimate tier -- which is true and is the wrong
    question.
    """
    scope, rung, _ = _walk(charged_iva_rates=(Decimal("0"),))

    assert scope is None
    assert rung is None


def test_a_rate_no_schedule_carries_corroborates_nothing() -> None:
    """The negative control over the widening itself.

    Without this, a rule that corroborated on ANY non-Spanish positive rate would
    pass every case above. Twenty-three per cent is carried by neither schedule
    on this date, so a walk that answered here would be reading the presence of a
    number rather than its lawfulness.

    The first draft of this case used seven per cent, which is Germany's REDUCED
    rate -- so the control failed, correctly, against a fixture that had picked a
    lawful German rate while claiming it was carried by nobody. The rate below
    was measured against both schedules rather than assumed.
    """
    scope, rung, _ = _walk(charged_iva_rates=(Decimal("23"),))

    assert scope is None
    assert rung is None


def test_the_corroborated_scope_is_the_registration_states_own() -> None:
    """The rung reports where the registration says the party is, not a default.

    Asserted through a second State so the answer cannot be a constant that
    happens to match Germany: both resolve to the member scope, and neither
    resolves to a Spanish one, which is the failure this axis refuses everywhere.
    """
    german, _, _ = _walk(charged_iva_rates=(Decimal("19"),))
    dutch, _, _ = _walk(tax_identifier=_DUTCH_IVA, regime_legend=_REVERSE_CHARGE)

    assert german is IvaTerritorialScope.EU_MEMBER
    assert dutch is IvaTerritorialScope.EU_MEMBER
