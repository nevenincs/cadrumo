"""Bidirectional parity gate for two registry-owned Modelo 210 code axes.

Proves that :func:`validate_m210_tipo_renta_code_projection_parity` fails the
registry build in BOTH directions — a revision-declared code with no governed
fact projection, and a projected code the revision does not declare — so the
two axes cannot drift. The gate is
exercised against the real, loaded M210 modelo definition; divergence is
induced through the validator's explicit projected-code input, never by
fabricating a modelo. The registry-declared codes additionally carry the canonical registry
legal-grounding gate (their ``legal_refs`` -> corpus), validated when the
authority loads below.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.irnr_tipo_renta import m210_tipo_renta_code_projection

from ..compiler import validate_revision_rules as rules

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]


def _m210_definition():
    """Return the loaded, validated M210 :class:`ModeloDefinition`."""
    authority = bundled_authority()
    return next(modelo for modelo in authority.modelos if modelo.id == "210")


def test_revision_and_governed_fact_projection_are_in_parity() -> None:
    # The shipped revision code set and governed-fact projection agree, so
    # the gate produces no failures on the real definition.
    assert rules.validate_m210_tipo_renta_code_projection_parity(_m210_definition()) == []


def test_declared_code_without_governed_fact_projection_fails_build() -> None:
    # Drop code "01" from the governed-fact projection: it stays declared in the revision
    # but no longer projects, so the gate must refuse (declared-not-projected).
    reduced = set(m210_tipo_renta_code_projection()) - {"01"}

    failures = rules.validate_m210_tipo_renta_code_projection_parity(
        _m210_definition(),
        projected_codes=reduced,
    )

    assert any("'01'" in failure and "no governed-fact" in failure for failure in failures), failures


def test_governed_fact_projected_code_not_declared_fails_build() -> None:
    # Add code "99" to the governed-fact projection that the revision never declares,
    # so the gate must refuse (projected-not-declared).
    augmented = set(m210_tipo_renta_code_projection()) | {"99"}

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
