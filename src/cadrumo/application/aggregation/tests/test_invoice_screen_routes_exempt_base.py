"""An exempt base must reach the casilla that declares it, not merely survive.

Keeping a cuota-less line in the screen was the precondition. This is the
routing half: the line's base has to arrive at Modelo 303 casilla 59 for an
intra-community supply, or casilla 60 for an export.

It did not, and the reason is an asymmetry between two feeds of ONE binding
source. The bank-transaction path reads the transaction's declared IVA category
first and falls back to the rate-derived domestic category only when none is
declared. The invoice path read the RATE SLOT alone, which cannot tell an
intra-community supply from a domestic exemption -- both print an exempt slot --
so every such line became ``domestic_exempt``/``exempt``. Casilla 59 selects
``intra_community_supply``/``zero`` and casilla 60 the two export categories, so
the observation missed on category AND on rate kind, and the base landed
nowhere. Two surfaces populating one source with divergent logic is what
``one-aggregation-path-pull-equals-calculate`` exists to prevent.

Asserted at the resolved BINDING VALUES rather than at the observation, because
an observation that classifies correctly and still matches no selector is
exactly the failure this file exists to catch -- and is precisely what the
previous attempt produced.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.authority import bundled_authority
from ....domain.invoices.enums import IvaRate
from ....domain.invoices.models import Invoice
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from .._iva_ledger import resolve_iva_ledger_binding_values
from .._modelo_bindings_invoice_iva import _invoice_line_iva_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BASE = Decimal("5000.00")
_DEVENGO = date(2024, 3, 15)

_CASILLA_59 = "modelo-303-casilla-59-entregas-intracomunitarias-base"
_CASILLA_60 = "modelo-303-casilla-60-exportaciones-base"


def _revision():
    return bundled_authority().snapshot("303", filing_year=2024, period="1T").revision


def _invoice(
    *,
    category: IvaCategory,
    country: str,
    tax_id: str = "DE811907980",
    identification: str | None = "de",
) -> Invoice:
    """One issued invoice carrying a single exempt line and a declared category.

    A real aggregate rather than a stand-in: the model re-checks its own totals
    identity on construction, so a fixture that did not add up could not be
    built at all.
    """
    return Invoice.model_validate(
        {
            "bucket_id": "29292929-2929-4929-8929-292929292929",
            "kind": InvoiceKind.ISSUED.value,
            "invoice_number": "F-2024-0044",
            "issued_at": _DEVENGO.isoformat(),
            "counterparty_name": "Cliente Exterior",
            "counterparty_tax_id": tax_id,
            "counterparty_country": country,
            # Ley 37/1992 art. 25 exempts on the acquirer's IVA IDENTIFICATION,
            # so the screen reads this rather than the address above. A US
            # counterparty prints no Member State IVA number, and absent stays
            # absent -- it is never resolved from the country.
            "counterparty_identification_state": identification,
            "base_total": format(_BASE, "f"),
            "iva_total": "0.00",
            "grand_total": format(_BASE, "f"),
            "currency": "EUR",
            "payment_status": "PENDING",
            "iva_category": category.value,
            "lines": [
                {
                    "description": "Suministro exento",
                    "quantity": "1",
                    "unit_price": format(_BASE, "f"),
                    "subtotal": format(_BASE, "f"),
                    "iva_rate": IvaRate.EXEMPT.value,
                    "iva_amount": "0.00",
                },
            ],
        },
    )


def _resolved_for(invoice: Invoice) -> dict[str, Decimal]:
    """Project the invoice's single line the way the screen does, then resolve."""
    line = invoice.lines[0]
    base_amount_eur = invoice.line_amount_eur(line.subtotal)
    iva_amount_eur = invoice.line_amount_eur(line.iva_amount)
    assert base_amount_eur is not None
    assert iva_amount_eur is not None
    observation = _invoice_line_iva_observation(
        invoice=invoice,
        line=line,
        line_index=0,
        devengo_date=_DEVENGO,
        recargo_amount=Decimal("0"),
        base_amount_eur=base_amount_eur,
        iva_amount_eur=iva_amount_eur,
    )
    if observation is None:
        return {}
    return {str(k): v for k, v in resolve_iva_ledger_binding_values(_revision(), (observation,)).items()}


def test_an_intra_community_supply_base_reaches_casilla_59() -> None:
    """The exempt base is declared where LIVA art. 25 says it is declared.

    The counterparty is in another member state, which is what makes the supply
    an intra-community one rather than a domestic exemption. Both print an
    exempt slot, so nothing but the declared category distinguishes them.
    """
    resolved = _resolved_for(_invoice(category=IvaCategory.INTRA_COMMUNITY_SUPPLY, country="DE"))

    assert resolved.get(_CASILLA_59) == _BASE, (
        f"the intra-community base never reached casilla 59: {resolved.get(_CASILLA_59)!r}"
    )
    assert not resolved.get(_CASILLA_60), "an intra-community supply is not an export"


def test_an_export_base_reaches_casilla_60() -> None:
    """The same line, a third-country counterparty, a different casilla.

    Run alongside the intra-community case rather than instead of it: a routing
    that sent every exempt base to one casilla would satisfy either test alone
    and fail the pair.
    """
    resolved = _resolved_for(
        _invoice(
            category=IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
            country="US",
            tax_id="US987654321",
            identification=None,
        )
    )

    assert resolved.get(_CASILLA_60) == _BASE, (
        f"the export base never reached casilla 60: {resolved.get(_CASILLA_60)!r}"
    )
    assert not resolved.get(_CASILLA_59), "an export is not an intra-community supply"


def test_a_domestic_exemption_is_not_routed_to_either_base_casilla() -> None:
    """A domestic exemption belongs in neither, and must not be swept into one.

    This is the discrimination the rate slot could not make. LIVA art. 20 exempts
    the operation without making it a supply to another member state or a
    despatch out of the Union, and Modelo 303 has no base-only casilla for it. A
    routing keyed on "the cuota is zero" rather than on the declared category
    would put this base in casilla 59 and over-declare intra-community volume.
    """
    resolved = _resolved_for(
        _invoice(category=IvaCategory.DOMESTIC_EXEMPT, country="ES", tax_id="ESB12345674", identification="es")
    )

    assert not resolved.get(_CASILLA_59)
    assert not resolved.get(_CASILLA_60)


def test_an_intra_community_supply_to_a_third_country_is_not_routed() -> None:
    """A supply outside the Union is not an intra-community one, whatever it claims.

    The model already refuses the OTHER direction of this coupling -- an entrega
    intracomunitaria naming Spain is unconstructible, LIVA art. 25 -- but it
    accepts one naming a third country. So this case reaches the screen and only
    the screen can decline it, which is why the check is here rather than left to
    the aggregate. Routing it would report volume to a member state that never
    received it.
    """
    resolved = _resolved_for(
        _invoice(
            category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
            country="US",
            tax_id="US987654321",
            identification=None,
        ),
    )

    assert not resolved.get(_CASILLA_59), "a third-country destination was routed as an intra-community supply"


def test_the_aggregate_already_refuses_an_intra_community_supply_to_spain() -> None:
    """The layering, pinned so neither guard is removed as redundant.

    The screen's coupling check also excludes Spain, and that clause is
    defence in depth rather than the only guard: this record cannot be built at
    all. Stating it here means a later reader deleting one of the two knows
    which one still holds the line, instead of discovering it from a wrong
    return.
    """
    with pytest.raises(ValidationError):
        _invoice(
            category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
            country="ES",
            tax_id="ESB12345674",
            identification="es",
        )


def test_an_export_claimed_to_a_member_state_is_not_routed() -> None:
    """The mirror coupling: an export leaves the Union, so an EU counterparty contradicts it."""
    resolved = _resolved_for(
        _invoice(
            category=IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
            country="FR",
            tax_id="FR12345678901",
            identification="fr",
        )
    )

    assert not resolved.get(_CASILLA_60), "an EU counterparty was routed as a third-country export"


def test_an_ordinary_rated_line_still_routes_through_the_standard_path() -> None:
    """The rated case is untouched, asserted rather than assumed.

    The change adds a branch for cuota-less lines; a regression that diverted
    ordinary rated lines into it would move real cuota out of the repercutido
    casillas, which is a far larger error than the one being fixed.
    """
    rated = Invoice.model_validate(
        {
            "bucket_id": "29292929-2929-4929-8929-292929292929",
            "kind": InvoiceKind.ISSUED.value,
            "invoice_number": "F-2024-0045",
            "issued_at": _DEVENGO.isoformat(),
            "counterparty_name": "Cliente Nacional",
            "counterparty_tax_id": "12345678Z",
            "counterparty_country": "ES",
            "base_total": "1000.00",
            "iva_total": "210.00",
            "grand_total": "1210.00",
            "currency": "EUR",
            "payment_status": "PENDING",
            "lines": [
                {
                    "description": "Servicio",
                    "quantity": "1",
                    "unit_price": "1000.00",
                    "subtotal": "1000.00",
                    "iva_rate": IvaRate.RATE_21.value,
                    "iva_amount": "210.00",
                },
            ],
        },
    )
    rated_line = rated.lines[0]
    rated_base_amount_eur = rated.line_amount_eur(rated_line.subtotal)
    rated_iva_amount_eur = rated.line_amount_eur(rated_line.iva_amount)
    assert rated_base_amount_eur is not None
    assert rated_iva_amount_eur is not None
    observation = _invoice_line_iva_observation(
        invoice=rated,
        line=rated_line,
        line_index=0,
        devengo_date=_DEVENGO,
        recargo_amount=Decimal("0"),
        base_amount_eur=rated_base_amount_eur,
        iva_amount_eur=rated_iva_amount_eur,
    )

    assert observation is not None
    assert observation.category is IvaCategory.DOMESTIC_GENERAL
    assert observation.base_amount == Decimal("1000.00")
    assert observation.iva_amount == Decimal("210.00")
