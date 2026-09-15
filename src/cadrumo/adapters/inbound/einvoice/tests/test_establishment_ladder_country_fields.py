"""Structured e-invoice country fields are owned by the inbound parser."""

from __future__ import annotations

import pytest

from cadrumo.adapters.inbound.einvoice.parsers import ParsedEInvoice, parse_einvoice_document
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from cadrumo.domain.iva.classification import IvaTerritorialScope
from cadrumo.domain.iva.establishment import territorial_scope_for_spanish_postal_code

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_the_structured_parser_exposes_each_party_country_and_postal_field() -> None:
    """The parser contract carries the fields that feed establishment routing."""
    parsed_fields = set(ParsedEInvoice.__slots__)

    assert {"supplier_country_code", "customer_country_code"} <= parsed_fields
    assert {"supplier_postal_code", "customer_postal_code"} <= parsed_fields


def test_the_cross_industry_invoice_branch_states_a_country_before_postal_routing() -> None:
    """A CII CountryID reaches the parser and pairs with its postal code."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        specimen = b"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100">
  <rsm:ExchangedDocument><ram:ID>CII-2026-0001</ram:ID></rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name>Vendedor Insular SL</ram:Name>
        <ram:PostalTradeAddress>
          <ram:PostcodeCode>38001</ram:PostcodeCode>
          <ram:CountryID>ES</ram:CountryID>
        </ram:PostalTradeAddress>
      </ram:SellerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>
"""
        parsed = parse_einvoice_document(specimen)

        assert parsed.supplier_postal_code == "38001"
        assert parsed.supplier_country_code == "ES"
        assert territorial_scope_for_spanish_postal_code(
            "38001", operation=_authority_operation_for_test
        ) is IvaTerritorialScope.from_registry("es_canarias")
