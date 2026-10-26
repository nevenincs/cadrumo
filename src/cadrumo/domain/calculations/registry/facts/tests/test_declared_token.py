"""Contract tests for coercing a value into a governed vocabulary token."""

from __future__ import annotations

import pytest

from .....contribuyente.renta_codes import SituacionFamiliar, SituacionFamiliarM145
from ...errors import RegistryValidationError
from ..declared_token import require_declared_registry_token

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DECLARED = frozenset({SituacionFamiliar.from_registry("1"), SituacionFamiliar.from_registry("2")})


def _require(value: object) -> SituacionFamiliar:
    return require_declared_registry_token(
        value,
        token_type=SituacionFamiliar,
        declared=_DECLARED,
        subject="family-situation",
        fact_id="fact-under-test",
    )


def test_text_is_stripped_and_projected_to_the_declared_token() -> None:
    assert _require("  2 ") == SituacionFamiliar.from_registry("2")


def test_projected_token_is_returned_unchanged() -> None:
    token = SituacionFamiliar.from_registry("1")

    assert _require(token) is token


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("   ", "family-situation token must be non-empty"),
        (3, "family-situation token must be a string token"),
        ("3", "family-situation token '3' is not declared by fact 'fact-under-test'"),
    ],
)
def test_undeclared_blank_or_non_text_values_are_refused(value: object, message: str) -> None:
    with pytest.raises(RegistryValidationError, match=message):
        _require(value)


def test_token_of_a_sibling_vocabulary_is_not_accepted_as_declared() -> None:
    # A projected token of another vocabulary is text, so it is re-projected and
    # judged against this vocabulary's declared set rather than trusted by type.
    sibling = SituacionFamiliarM145.from_registry("9")

    with pytest.raises(RegistryValidationError, match="is not declared by fact"):
        _require(sibling)
