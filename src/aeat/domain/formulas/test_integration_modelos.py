"""Cross-check that every shipped ruleset binds to the authoritative registry."""

from __future__ import annotations

import pytest

from ..modelos import MODELO_REGISTRY, ModeloCode
from ._registry import get_registry

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@pytest.mark.unit
def test_every_ruleset_binds_to_a_registered_modelo() -> None:
    """Each ruleset's :class:`ModeloCode` must exist in ``MODELO_REGISTRY``."""
    registry = get_registry()
    for ruleset in registry.rulesets:
        assert ruleset.modelo in MODELO_REGISTRY
        assert isinstance(ruleset.modelo, ModeloCode)


@pytest.mark.unit
def test_no_ruleset_uses_the_casillas_local_modelo_code() -> None:
    """Rulesets must use ``aeat.models.ModeloCode``, not the casillas-local enum."""
    from ..casillas.models import ModeloCode as CasillasModeloCode

    registry = get_registry()
    for ruleset in registry.rulesets:
        assert not isinstance(ruleset.modelo, CasillasModeloCode) or isinstance(ruleset.modelo, ModeloCode)
        assert ruleset.modelo.__class__.__module__ == "aeat.domain.modelos._codes"
