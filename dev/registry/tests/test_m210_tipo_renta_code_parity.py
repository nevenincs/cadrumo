"""Bidirectional parity gate: registry code set vs core projection.

Proves that :func:`validate_m210_tipo_renta_code_projection_parity` fails the
registry build in BOTH directions — a registry-declared code with no core
projection, and a core-projected code the registry does not declare — so the
two axes cannot drift. The gate is
exercised against the real, loaded M210 modelo definition; divergence is
induced through the validator's explicit projected-code input, never by
fabricating a modelo. The registry-declared codes additionally carry the canonical registry
legal-grounding gate (their ``legal_refs`` -> corpus), validated when the
authority loads below.
"""

from __future__ import annotations

import pytest

from .....core.irnr import M210_TIPO_RENTA_CODE_PROJECTION
from .. import _validate_revision_rules as rules
from ..authority import bundled_authority

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]


def _m210_definition():
    """Return the loaded, validated M210 :class:`ModeloDefinition`."""
    authority = bundled_authority()
    return next(modelo for modelo in authority.modelos if modelo.id == "210")


def test_registry_and_core_projection_are_in_parity() -> None:
    # The shipped registry code set and the shipped core projection agree, so
    # the gate produces no failures on the real definition.
    assert rules.validate_m210_tipo_renta_code_projection_parity(_m210_definition()) == []


def test_declared_code_without_core_projection_fails_build() -> None:
    # Drop code "01" from the core projection: it stays declared in the registry
    # but no longer projects, so the gate must refuse (declared-not-projected).
    reduced = set(M210_TIPO_RENTA_CODE_PROJECTION) - {"01"}

    failures = rules.validate_m210_tipo_renta_code_projection_parity(
        _m210_definition(),
        projected_codes=reduced,
    )

    assert any("'01'" in failure and "no core" in failure for failure in failures), failures


def test_core_projected_code_not_declared_fails_build() -> None:
    # Add a code "99" to the core projection that the registry never declares,
    # so the gate must refuse (projected-not-declared).
    augmented = set(M210_TIPO_RENTA_CODE_PROJECTION) | {"99"}

    failures = rules.validate_m210_tipo_renta_code_projection_parity(
        _m210_definition(),
        projected_codes=augmented,
    )

    assert any("'99'" in failure and "not" in failure and "declared" in failure for failure in failures), failures


def test_non_m210_modelo_is_a_noop() -> None:
    # A modelo carrying no m210-tipo-renta-code- parameter is never inspected.
    authority = bundled_authority()
    m303 = next(modelo for modelo in authority.modelos if modelo.id == "303")
    assert rules.validate_m210_tipo_renta_code_projection_parity(m303) == []
