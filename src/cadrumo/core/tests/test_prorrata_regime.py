"""Core-only structural checks for opaque prorrata-register tokens."""

from __future__ import annotations

import pytest

from ..prorrata_register import (
    ProrrataEspecialTransitionKind,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("token_type", "value"),
    (
        (ProrrataRegisterRegime, "general"),
        (ProrrataEspecialTransitionKind, "opcion"),
        (ProrrataProvisionalProvenance, "carried_prior_definitiva"),
        (SectorDiferenciadoLetra, "a"),
    ),
)
def test_registry_tokens_are_opaque_and_structurally_non_empty(token_type: type[str], value: str) -> None:
    """Core constructs tokens only through the explicit registry projection."""
    token = token_type._from_registry(value)
    assert token.value == value
    with pytest.raises(TypeError):
        token_type(value)
