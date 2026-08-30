"""The model-reading path resolves the printed country NAME into a country code.

The reader is asked for the country as the document prints it -- "España",
"Deutschland" -- because asking for an alpha-2 code would be a translation, and
translation is inference. Turning that name into a code is a deterministic
lookup against a closed vocabulary, and it is the SAME lookup the structured
e-invoice lane already uses, so a printed name and a machine-readable country
element resolve through one authority rather than two.

Two properties matter more than the happy path:

* the printed name survives -- it is the evidence, and the code is a derivation
  of it, so a derivation that destroyed its input could not be audited;
* a name the vocabulary does not carry produces NO code rather than the nearest
  one, because every consumer of the code branches domestic versus not and none
  can express that the question went unanswered.
"""

from __future__ import annotations

import json

import pytest

from ...core import FieldOrigin
from ..invoice_field_contract import anchor_key_for_field
from ..invoice_field_grounding import ground_extracted_fields, parse_invoice_extraction_response

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CIF = "B12345674"
_CUSTOMER_NIF = "A58818501"


def _reply(*, supplier_country: str | None, customer_country: str | None) -> str:
    """Render one model reply in the flat value+anchor shape the prompt asks for.

    Built as the READER emits it -- printed names, European numerals, an anchor
    quoting the surrounding address line -- rather than as canonical codes,
    because a fixture authored in codes would never exercise the resolution
    under test.
    """
    values = {
        "supplier_tax_id": _CIF,
        "supplier_name": "Ferreteria Insular S.L.",
        "supplier_postal_code": "35001",
        "supplier_country": supplier_country,
        "customer_tax_id": _CUSTOMER_NIF,
        "customer_name": "Talleres Mayor S.A.",
        "customer_postal_code": "28013",
        "customer_country": customer_country,
        "invoice_number": "2026-0142",
        "invoice_date": "10/03/2026",
        "taxable_base": "1.200,00",
        "iva_rate": "21",
        "iva_amount": "252,00",
        "retencion_rate": None,
        "retencion_amount": None,
        "grand_total": "1.452,00",
        "regime_legend": None,
        "currency": "EUR",
    }
    anchors = {
        "supplier_tax_id": f"CIF: {_CIF}",
        "supplier_name": "Emisor: Ferreteria Insular S.L.",
        "supplier_postal_code": "35001 Las Palmas de Gran Canaria",
        "supplier_country": f"35001 Las Palmas de Gran Canaria, {supplier_country}",
        "customer_tax_id": f"NIF cliente: {_CUSTOMER_NIF}",
        "customer_name": "Cliente: Talleres Mayor S.A.",
        "customer_postal_code": "Calle Mayor 3, 28013 Madrid",
        "customer_country": f"Calle Mayor 3, 28013 Madrid, {customer_country}",
        "invoice_number": "Factura n.o 2026-0142",
        "invoice_date": "10/03/2026",
        "taxable_base": "1.200,00 EUR",
        "iva_rate": "21%",
        "iva_amount": "252,00 EUR",
        "retencion_rate": None,
        "retencion_amount": None,
        "grand_total": "1.452,00 EUR",
        "regime_legend": None,
        "currency": "EUR",
    }
    payload: dict[str, str | None] = dict(values)
    payload.update({anchor_key_for_field(name): anchor for name, anchor in anchors.items()})
    return json.dumps(payload)


def _draft(*, supplier_country: str | None, customer_country: str | None):
    return ground_extracted_fields(
        parse_invoice_extraction_response(
            _reply(supplier_country=supplier_country, customer_country=customer_country),
        ),
        raw_text_length=256,
        origin=FieldOrigin.TEXT_LAYER,
    )


def test_a_printed_spanish_name_resolves_to_its_code() -> None:
    draft = _draft(supplier_country="España", customer_country="España")

    assert draft.supplier_country_code == "ES"
    assert draft.customer_country_code == "ES"


def test_a_printed_foreign_name_resolves_to_that_country_not_to_spain() -> None:
    """The discriminating case: Spain is the majority population here.

    A wiring that defaulted, or that resolved everything to the domestic code,
    passes the test above and fails this one.
    """
    draft = _draft(supplier_country="Deutschland", customer_country="Alemania")

    assert draft.supplier_country_code == "DE"
    assert draft.customer_country_code == "DE"


def test_the_printed_name_survives_the_derivation() -> None:
    """The name is the evidence; the code is derived from it. Both are kept."""
    draft = _draft(supplier_country="Deutschland", customer_country="España")

    assert draft.supplier_country == "Deutschland"
    assert draft.customer_country == "España"


def test_a_misspelled_name_produces_no_code_rather_than_the_nearest_one() -> None:
    """A near miss is not a match, and must not become one."""
    draft = _draft(supplier_country="Esapna", customer_country="Alemanha")

    assert draft.supplier_country_code is None
    assert draft.customer_country_code is None
    # The unresolvable name is still carried, so the operator can see what the
    # document said and why nothing was derived from it.
    assert draft.supplier_country == "Esapna"


def test_a_name_the_vocabulary_does_not_carry_produces_no_code() -> None:
    draft = _draft(supplier_country="Freedonia", customer_country="Freedonia")

    assert draft.supplier_country_code is None
    assert draft.customer_country_code is None


def test_an_absent_country_produces_no_code() -> None:
    """Absence must stay absence -- never Spain, which is the majority population."""
    draft = _draft(supplier_country=None, customer_country=None)

    assert draft.supplier_country_code is None
    assert draft.customer_country_code is None
