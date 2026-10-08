"""A refused filing model never echoes the account IBAN it was given.

The snapshot models that carry a refund or charge account, an IVA or taxpayer
profile, or a flat IBAN fact are financial identity data. When one of them is
refused -- directly or while validating the model that holds it -- the rendered
error names the location and the rule, never the submitted value.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import pytest
from pydantic import BaseModel, ValidationError

from ..export_envelope import FilingEnvelopeRenderRequest
from ..producer_snapshot import (
    ChargeAccountSelection,
    FilingProducerSnapshot,
    Modelo202ProducerProfile,
    Modelo210DevolucionFactSet,
    Modelo210IngresoFactSet,
    Modelo210ProfileFacts,
    RefundAccountSelection,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Synthetic: the ISO 13616 documentation example, a valid mod-97 residue, so the
# account itself is accepted and only the surrounding model refuses the input.
_IBAN = "ES9121000418450200051332"
# Pydantic shortens a long echoed input in the middle, so a leak can show only
# the tail of the account number.
_IBAN_TAIL = _IBAN[-12:]
_ACCOUNT = {"iban": _IBAN}
# No tax ID: the profile is refused as a whole, so the echo would carry the account.
_PROFILE_WITHOUT_TAX_ID = {"iva": {"refund_account": _ACCOUNT}}

_CASES: Mapping[str, tuple[type[BaseModel], dict[str, object]]] = {
    "refund selection without a role": (RefundAccountSelection, {"account": _ACCOUNT}),
    "charge selection without a role": (ChargeAccountSelection, {"account": _ACCOUNT}),
    "210 devolucion iban as bytes": (Modelo210DevolucionFactSet, {"cuenta_sepa_iban": _IBAN.encode()}),
    "210 ingreso iban as bytes": (Modelo210IngresoFactSet, {"cuenta_sepa_iban": _IBAN.encode()}),
    "210 profile holding a refused devolucion": (
        Modelo210ProfileFacts,
        {"devolucion": {"cuenta_sepa_iban": _IBAN.encode()}},
    ),
    "202 profile holding a taxpayer profile": (
        Modelo202ProducerProfile,
        {"taxpayer_profile": _PROFILE_WITHOUT_TAX_ID},
    ),
    "snapshot holding a selected account": (
        FilingProducerSnapshot,
        {"selected_account": {"role": "refund", "account": _ACCOUNT}},
    ),
    "envelope request holding a snapshot": (
        FilingEnvelopeRenderRequest,
        {"producer_snapshot": {"selected_account": {"role": "charge", "account": _ACCOUNT}}},
    ),
}


def _refusal(validate: Callable[[], object]) -> ValidationError:
    with pytest.raises(ValidationError) as caught:
        validate()
    return caught.value


@pytest.mark.usefixtures("authority_operation")
@pytest.mark.parametrize("case", sorted(_CASES))
def test_a_refused_filing_model_never_echoes_the_iban(case: str) -> None:
    model, payload = _CASES[case]

    refusal = _refusal(lambda: model.model_validate(payload))

    # The structured error still holds the rejected input, so a rendering that
    # echoed it would carry the account number.
    assert _IBAN in str(refusal.errors(include_input=True)), f"{case}: the refusal never reaches the IBAN"
    rendered = f"{refusal} {refusal!r}"
    assert _IBAN_TAIL not in rendered, f"{case}: the IBAN leaked into the refusal"
