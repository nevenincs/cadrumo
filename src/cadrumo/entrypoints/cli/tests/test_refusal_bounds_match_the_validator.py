"""A refusal that quotes a length must quote the one actually enforced.

The ``--binding`` and ``--casilla`` refusals tell the operator a maximum
length. That number used to be a literal beside the check, restating a bound
declared on :data:`BindingId` and :data:`CasillaId`. Restating it makes the
message a second declaration, and this one is uniquely undetectable: the value
is only ever printed, so nothing fails when it drifts. The operator is simply
told the wrong limit.

The support module now reads the bound off the alias. These tests prove the
reading agrees with the validator by PROBING it -- constructing an identifier
one character over the quoted bound and confirming the validator refuses it,
and one exactly at the bound and confirming it does not. Asserting the derived
number equals the declared number would only prove the reader can read.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from ....core import CasillaId
from ....domain.calculations.registry.ids import BindingId
from .._modelo_cli_support import _BINDING_MAX_LEN, _CASILLA_MAX_LEN

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("alias", "quoted", "filler"),
    [
        (BindingId, _BINDING_MAX_LEN, "a"),
        (CasillaId, _CASILLA_MAX_LEN, "A"),
    ],
    ids=["binding", "casilla"],
)
def test_the_quoted_bound_is_the_one_the_validator_enforces(alias: object, quoted: int, filler: str) -> None:
    """One character over the quoted bound must refuse; exactly at it must not."""
    adapter: TypeAdapter[str] = TypeAdapter(alias)

    adapter.validate_python(filler * quoted)

    with pytest.raises(ValidationError):
        adapter.validate_python(filler * (quoted + 1))
