"""A ``--descendiente`` refusal is rendered with the copy for its own cause.

The ``invalid_flag`` copy tells the operator that every row must declare
``NACIMIENTO``. Rendered for any other refusal it names a cause that did not
happen, so it is reserved for refusals the parser attributes to ``NACIMIENTO``;
everything else, including a refusal that names no key, takes ``invalid_row``.
"""

from __future__ import annotations

import pytest

from .....core.errors.hierarchy import ProfileAnswerTypeError
from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.contribuyente.descendant_facts import parse_descendiente_flag
from ..descendiente import _descendiente_refusal_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_INVALID_ROW = "cli.config.profile.descendiente.invalid_row"
_INVALID_FLAG = "cli.config.profile.descendiente.invalid_flag"


def test_an_unattributed_refusal_names_no_field() -> None:
    assert _descendiente_refusal_key(ProfileAnswerTypeError("x")) == (_INVALID_ROW, {})


def test_a_birth_date_refusal_keeps_the_nacimiento_copy() -> None:
    error = ProfileAnswerTypeError("x", context={"key": "NACIMIENTO"})

    assert _descendiente_refusal_key(error) == (_INVALID_FLAG, {"key": "NACIMIENTO"})


def test_another_attributed_refusal_names_its_own_key() -> None:
    error = ProfileAnswerTypeError("x", context={"key": "DISCAPACIDAD"})

    assert _descendiente_refusal_key(error) == (_INVALID_ROW, {"key": "DISCAPACIDAD"})


def test_the_guarderia_spend_conflict_keeps_its_dedicated_copy() -> None:
    """Driven through the real parser so the mapper reads the context it actually raises."""
    with bundled_indexed_authority().operation(), pytest.raises(ProfileAnswerTypeError) as raised:
        parse_descendiente_flag("NACIMIENTO=2021-04-15,GASTOS_GUARDERIA=2400,GASTOS_GUARDERIA_MENSUAL=5-7:200")

    assert _descendiente_refusal_key(raised.value) == (
        "cli.config.profile.descendiente.guarderia_spend_shapes_conflict",
        {"key": "GASTOS_GUARDERIA_MENSUAL"},
    )
