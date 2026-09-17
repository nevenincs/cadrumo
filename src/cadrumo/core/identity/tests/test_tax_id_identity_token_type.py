"""Real-behavior tests for the :data:`~core.identity.tax_id.TaxIdIdentityToken` alias.

The core token is trim-and-uppercase only and admits any bearer, Spanish or
not, because a counterparty on a ledger transaction or an invoice may be
non-resident. A non-Spanish-shaped identifier proves that this core contract
does not accidentally acquire a checksum or residency policy.

Uses the German NIF-IVA-shape example already established as canonical in
:mod:`core.identity.nif_iva` (``DE + 9 digits``), not an invented value.

See Also:
    :data:`~core.identity.tax_id.TaxIdIdentityToken`
        Alias under test.
    :mod:`core.identity.tests.test_tax_id_comparison`
        The comparison-function-level suite guarding the same normalisation
        forms.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from ....tests.fixtures.identity_holder import single_field_holder
from ..tax_id import TaxIdIdentityToken

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TokenHolder = single_field_holder("tax_id", TaxIdIdentityToken)

#: A real EU NIF-IVA-shaped counterparty identifier: the German pattern
#: (``^DE\\d{9}$``) already carried as the canonical worked example in
#: ``core.identity.nif_iva``'s own prefix specification table, not a value
#: invented for this suite.
_EU_NIF_IVA_SHAPED_ID = "DE123456789"


def test_a_non_spanish_nif_iva_shaped_id_validates_under_the_token_alias() -> None:
    holder = _TokenHolder.build(_EU_NIF_IVA_SHAPED_ID)
    assert _TokenHolder.value_of(holder) == _EU_NIF_IVA_SHAPED_ID


def test_the_token_alias_normalises_case_and_whitespace_but_asserts_no_checksum() -> None:
    holder = _TokenHolder.build(f"  {_EU_NIF_IVA_SHAPED_ID.lower()}  ")
    assert _TokenHolder.value_of(holder) == _EU_NIF_IVA_SHAPED_ID


def test_a_wire_payload_carrying_the_token_survives_a_json_roundtrip() -> None:
    """Persistence-boundary roundtrip: every ``TaxIdIdentityToken`` field this
    campaign retyped lives on a wire-facing payload (CLI results, LLM
    interchange models), so the alias must survive JSON serialise/deserialise
    unchanged, not merely pydantic construction.
    """

    class _WirePayload(BaseModel):
        counterparty_tax_id: TaxIdIdentityToken

    built = _WirePayload(counterparty_tax_id=_EU_NIF_IVA_SHAPED_ID)
    restored = _WirePayload.model_validate_json(built.model_dump_json())
    assert restored == built
    assert restored.counterparty_tax_id == _EU_NIF_IVA_SHAPED_ID
