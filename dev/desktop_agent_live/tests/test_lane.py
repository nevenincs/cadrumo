"""The lane names the developer's key variable from the provider id it is given, never from a fixed provider."""

from __future__ import annotations

import pytest

from ..lane import key_variable

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("provider_id", "variable"),
    [
        ("alpha", "CADRUMO_LLM_ALPHA_API_KEY"),
        ("beta_two", "CADRUMO_LLM_BETA_TWO_API_KEY"),
        ("Mixed_Case", "CADRUMO_LLM_MIXED_CASE_API_KEY"),
    ],
)
def test_the_key_variable_is_built_from_the_provider_id(provider_id: str, variable: str) -> None:
    assert key_variable(provider_id) == variable
