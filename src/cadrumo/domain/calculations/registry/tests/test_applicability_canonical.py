"""Regression tests asserting canonical access to applicability rules.

Pins the applicability collapse to the single domain
source: ``derive_modelo_applicability`` access paths must resolve to the
same object in memory and both retired re-export bridges must stay absent.

Assertions:
- The former application overview re-export shim is not importable.
- The former ``registry.applicability`` focused re-export bridge is not
  importable either -- every public symbol it carried is already exported
  by the package's own top-level facade, and the bridge had no consumer of
  the underscore-prefixed internal constants it also carried.
- The function object imported via the package facade is identity-equal to
  the domain implementation.

See Also:
    :func:`~domain.calculations.registry.derive_modelo_applicability`
        Public package facade this test pins to the implementation object.
    :func:`~domain.calculations.registry._applicability.iter_modelo_applicability_rules`
        Canonical rule-table iterator checked for annual withholding refs.
"""

from __future__ import annotations

import importlib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_application_overview_applicability_shim_is_absent() -> None:
    """The application.overview._applicability re-export shim must not exist.

    The cross-domain continuity contract ratified the
    removal of ``cadrumo.application.overview._applicability`` — the
    application layer consumes the domain rules through the public
    registry surface directly (``cadrumo.domain.calculations.registry``)
    and the standalone re-export shim has no remaining caller. This
    test replaces the old identity-re-export check: a recurrence of
    the shim (an accidental restore) must be flagged at the structural
    boundary, not silently re-introduced.
    """
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("cadrumo.application.overview._applicability")


def test_registry_applicability_focused_bridge_is_absent() -> None:
    """The registry.applicability focused re-export bridge must not exist.

    Per the operator directive collapsing every redefinition onto its single
    canonical home: every public symbol this bridge carried was already
    re-exported by ``cadrumo.domain.calculations.registry`` itself, and none
    of the underscore-prefixed internal constants it also carried had a
    consumer through the bridge. A recurrence of the bridge (an accidental
    restore, or a new cross-package import reaching for the focused module
    instead of the package facade) must be flagged here, not silently
    re-introduced.
    """
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("cadrumo.domain.calculations.registry.applicability")


def test_facade_reexport_is_identity_equal_to_domain() -> None:
    """The package facade re-export resolves to the same object as the implementation."""
    domain_mod = importlib.import_module("cadrumo.domain.calculations.registry.applicability")
    facade_mod = importlib.import_module("cadrumo.domain.calculations.registry")
    assert facade_mod.derive_modelo_applicability is domain_mod.derive_modelo_applicability, (
        "package facade derive_modelo_applicability is not the same object as the domain implementation"
    )


def test_annual_withholding_summary_applicability_uses_art_108_not_art_109() -> None:
    """M180/M190 filing duty is RIRPF art. 108, not pago-fraccionado art. 109."""
    domain_mod = importlib.import_module("cadrumo.domain.calculations.registry.applicability")
    core_mod = importlib.import_module("cadrumo.core")
    rules_by_modelo = {rule.modelo: rule for rule in domain_mod.iter_modelo_applicability_rules()}

    for modelo in (core_mod.Modelo.M180, core_mod.Modelo.M190):
        legal_refs = rules_by_modelo[modelo].legal_refs
        assert "rd-439-2007:art-108" in legal_refs
        assert "rd-439-2007:art-109" not in legal_refs
