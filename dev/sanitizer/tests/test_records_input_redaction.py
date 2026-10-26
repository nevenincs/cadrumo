"""A refused token map never echoes the cleartext value it was asked to replace."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import BaseModel, ValidationError

from .._records import IbanReplacement, TokenMap

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# Synthetic: the ISO 13616 documentation example.
_REAL_IBAN = "ES9121000418450200051332"
# Pydantic shortens a long echoed input in the middle, so a leak can show only the tail.
_REAL_TAIL = _REAL_IBAN[-12:]
# The entry has no synthetic replacement, so it is refused with the whole entry in hand.
_ENTRY = {"surface_label": "iban", "real": _REAL_IBAN}


def _refusal(validate: Callable[[], object]) -> ValidationError:
    with pytest.raises(ValidationError) as caught:
        validate()
    return caught.value


@pytest.mark.parametrize(
    ("model", "payload"),
    [(IbanReplacement, _ENTRY), (TokenMap, {"iban": (_ENTRY,)})],
    ids=["replacement", "token map"],
)
def test_a_refused_replacement_never_echoes_the_real_value(model: type[BaseModel], payload: object) -> None:
    refusal = _refusal(lambda: model.model_validate(payload))

    # The structured error still holds the rejected entry, so a rendering that
    # echoed it would carry the cleartext value.
    assert _REAL_IBAN in str(refusal.errors(include_input=True)), "the refusal never reaches the real value"
    assert _REAL_TAIL not in f"{refusal} {refusal!r}"
