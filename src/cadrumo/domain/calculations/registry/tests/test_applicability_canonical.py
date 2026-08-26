"""Regression tests asserting canonical access to applicability rules.

Pins the applicability collapse to its single domain source. The rules live in
``registry.applicability``, which is the canonical defining module rather than a
re-export bridge: the module was promoted out of its underscore-private name,
and consumers import ``derive_modelo_applicability`` from it directly.

Assertions:
- The former application overview re-export shim is not importable.
- The annual withholding summary duty is grounded in RIRPF art. 108.

Two assertions retired with the shapes they defended. One required the package
``__init__`` to re-export ``derive_modelo_applicability``; that namespace is now
inert by rule, carrying an empty ``__all__`` and no imports, so there is no
facade object to compare against. The other required
``registry.applicability`` to be absent, which was right while the name belonged
to a bridge and is wrong now that it names the implementation itself.

See Also:
    :func:`~domain.calculations.registry.applicability.derive_modelo_applicability`
        Canonical defining module for the applicability derivation.
    :func:`~domain.calculations.registry.applicability.iter_modelo_applicability_rules`
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


def test_annual_withholding_summary_applicability_uses_art_108_not_art_109() -> None:
    """M180/M190 filing duty is RIRPF art. 108, not pago-fraccionado art. 109."""
    domain_mod = importlib.import_module("cadrumo.domain.calculations.registry.applicability")
    core_mod = importlib.import_module("cadrumo.core")
    rules_by_modelo = {rule.modelo: rule for rule in domain_mod.iter_modelo_applicability_rules()}

    for modelo in (core_mod.Modelo.M180, core_mod.Modelo.M190):
        legal_refs = rules_by_modelo[modelo].legal_refs
        assert "rd-439-2007:art-108" in legal_refs
        assert "rd-439-2007:art-109" not in legal_refs
