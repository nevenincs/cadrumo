"""Regression test for annual withholding-summary applicability.

The annual withholding summary duty is grounded in RIRPF art. 108.

See Also:
    :func:`~domain.calculations.registry.applicability.iter_modelo_applicability_rules`
        Rule-table iterator checked for annual withholding refs.
"""

from __future__ import annotations

import importlib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_annual_withholding_summary_applicability_uses_art_108_not_art_109() -> None:
    """M180/M190 filing duty is RIRPF art. 108, not pago-fraccionado art. 109."""
    domain_mod = importlib.import_module("..applicability", package=__package__)
    core_mod = importlib.import_module(".....core.modelo", package=__package__)
    rules_by_modelo = {rule.modelo: rule for rule in domain_mod.iter_modelo_applicability_rules()}

    for modelo in (core_mod.Modelo.M180, core_mod.Modelo.M190):
        legal_refs = rules_by_modelo[modelo].legal_refs
        assert "rd-439-2007:art-108" in legal_refs
        assert "rd-439-2007:art-109" not in legal_refs
