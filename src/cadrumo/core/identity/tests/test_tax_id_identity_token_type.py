"""Real-behavior tests for the :data:`~core.identity.TaxIdIdentityToken` alias.

Guards the direction of the ``SubjectTaxId`` / ``TaxIdIdentityToken`` split this
campaign applied: ``SubjectTaxId`` is checksum-enforced and Spanish-only,
``TaxIdIdentityToken`` is trim-and-uppercase only and admits any bearer,
Spanish or not, because a counterparty on a ledger transaction or an invoice
may be non-resident. A non-Spanish-shaped identifier is the one input that
tells the two aliases apart — a case-only fixture passes under either and
proves nothing about which alias a given field actually carries.

Uses the German VAT-shape example already established as canonical in
:mod:`core.identity._nif_iva` (``DE + 9 digits``), not an invented value.

See Also:
    :data:`~core.identity.TaxIdIdentityToken`
        Alias under test.
    :data:`~core.identity.SubjectTaxId`
        The checksum-enforced sibling this suite proves rejects the same value.
    :mod:`core.identity.tests.test_tax_id_comparison`
        The comparison-function-level suite guarding the same split's two
        normalisation forms.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from ....tests.fixtures.identity_holder import single_field_holder
from .. import SubjectTaxId, TaxIdIdentityToken

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TokenHolder = single_field_holder("tax_id", TaxIdIdentityToken)
_SubjectHolder = single_field_holder("tax_id", SubjectTaxId)

#: A real EU VAT-shaped counterparty identifier: the German pattern
#: (``^DE\\d{9}$``) already carried as the canonical worked example in
#: ``core.identity._nif_iva``'s own prefix specification table, not a value
#: invented for this suite.
_EU_VAT_SHAPED_ID = "DE123456789"


def test_a_non_spanish_vat_shaped_id_validates_under_the_token_alias() -> None:
    holder = _TokenHolder.build(_EU_VAT_SHAPED_ID)
    assert _TokenHolder.value_of(holder) == _EU_VAT_SHAPED_ID


def test_the_token_alias_normalises_case_and_whitespace_but_asserts_no_checksum() -> None:
    holder = _TokenHolder.build(f"  {_EU_VAT_SHAPED_ID.lower()}  ")
    assert _TokenHolder.value_of(holder) == _EU_VAT_SHAPED_ID


def test_the_same_eu_vat_shaped_id_is_refused_by_the_checksum_enforced_sibling() -> None:
    """The teeth: proves the split's DIRECTION, not just that one side accepts.

    If a future edit swapped a counterparty field from ``TaxIdIdentityToken``
    onto ``SubjectTaxId`` -- applying the split backwards -- this is the
    input that would start failing. A fixture that only proves the token
    alias accepts the value would stay green through exactly that
    regression, because nothing would force the swap to be noticed.
    """
    with pytest.raises(ValidationError):
        _SubjectHolder.build(_EU_VAT_SHAPED_ID)


def test_a_wire_payload_carrying_the_token_survives_a_json_roundtrip() -> None:
    """Persistence-boundary roundtrip: every ``TaxIdIdentityToken`` field this
    campaign retyped lives on a wire-facing payload (CLI results, LLM
    interchange models), so the alias must survive JSON serialise/deserialise
    unchanged, not merely pydantic construction.
    """

    class _WirePayload(BaseModel):
        counterparty_tax_id: TaxIdIdentityToken

    built = _WirePayload(counterparty_tax_id=_EU_VAT_SHAPED_ID)
    restored = _WirePayload.model_validate_json(built.model_dump_json())
    assert restored == built
    assert restored.counterparty_tax_id == _EU_VAT_SHAPED_ID
