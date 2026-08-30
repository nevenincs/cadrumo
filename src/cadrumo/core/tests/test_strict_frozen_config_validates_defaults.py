"""The shared strict-frozen configuration validates defaults, not just inputs.

A default value is the one input nobody supplies, so it is the one input that
goes unchecked unless the configuration says otherwise. A model whose default
violates its own field constraint is then accepted silently and only fails
somewhere downstream that happens to re-validate it - or does not fail at all,
and the invalid value ships.

These assertions are written against the shared constant rather than against
any model that embeds it, because the guarantee belongs to the constant. A
per-module declaration would leave every module that forgot it unprotected,
which is the state this replaced.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    "config",
    (STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG),
    ids=("strict_frozen", "strict_frozen_hidden_input"),
)
def test_the_shared_configurations_declare_default_validation(config: ConfigDict) -> None:
    """Both shared configurations carry the declaration, and the baseline with it."""
    assert config.get("validate_default") is True
    assert config.get("strict") is True
    assert config.get("frozen") is True
    assert config.get("extra") == "forbid"


def test_a_default_that_violates_its_own_field_constraint_is_refused() -> None:
    """The constraint governs the default, not only a supplied value."""

    class DefaultBreaksItsOwnPattern(BaseModel):
        model_config = STRICT_FROZEN_CONFIG

        code: str = Field(default="", pattern=r"^\d{2}$")

    with pytest.raises(ValidationError) as refusal:
        DefaultBreaksItsOwnPattern()

    assert refusal.value.errors()[0]["type"] == "string_pattern_mismatch"


def test_the_refusal_comes_from_the_shared_declaration_and_not_the_field() -> None:
    """Anti-tautology: the same model without the declaration accepts the default.

    Without this, the assertion above would pass just as happily against a
    field that pydantic checks for some unrelated reason, and would prove
    nothing about the shared configuration at all.
    """
    permissive = ConfigDict(strict=True, frozen=True, extra="forbid")

    class SameFieldWithoutTheDeclaration(BaseModel):
        model_config = permissive

        code: str = Field(default="", pattern=r"^\d{2}$")

    accepted = SameFieldWithoutTheDeclaration()

    assert accepted.code == ""
    assert permissive.get("validate_default") is None


def test_a_valid_default_still_passes_and_a_supplied_value_is_still_checked() -> None:
    """Turning the declaration on refuses bad defaults without refusing good ones."""

    class DefaultSatisfiesItsOwnPattern(BaseModel):
        model_config = STRICT_FROZEN_CONFIG

        code: str = Field(default="01", pattern=r"^\d{2}$")

    assert DefaultSatisfiesItsOwnPattern().code == "01"
    assert DefaultSatisfiesItsOwnPattern(code="42").code == "42"

    with pytest.raises(ValidationError):
        DefaultSatisfiesItsOwnPattern(code="not-two-digits")


def test_a_default_factory_result_is_validated_too() -> None:
    """A default produced by a factory is a default and is checked the same way."""

    class FactoryProducesAnInvalidDefault(BaseModel):
        model_config = STRICT_FROZEN_CONFIG

        code: str = Field(default_factory=lambda: "", pattern=r"^\d{2}$")

    with pytest.raises(ValidationError):
        FactoryProducesAnInvalidDefault()
