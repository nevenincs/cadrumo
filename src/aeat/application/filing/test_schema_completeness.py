"""Cross-validation: casilla schema is a superset of the formula ruleset.

Silent drift between the casilla schema (what the builder iterates) and
the formula ruleset (what the formula engine computes) is a real
correctness bug. The builder honours only casillas the schema knows
about; any ruleset entry outside that set is silently orphaned.

This module parametrises over every ``(modelo, año)`` tuple that has
both a schema and a ruleset, asserting that the schema's casilla-ID set
is a superset of the ruleset's. See
:mod:`aeat.domain.formulas._rulesets` for the ruleset definitions and
:func:`aeat.application.filing.runtime.build_runtime_schema_provider` for
the schema source.
"""

from __future__ import annotations

import pytest

from ...domain.formulas._rulesets.modelo_130_2024 import RULESET as RULESET_130_2024
from ...domain.formulas._rulesets.modelo_130_2025 import RULESET as RULESET_130_2025
from ...domain.formulas._rulesets.modelo_303_2024 import RULESET as RULESET_303_2024
from ...domain.formulas._rulesets.modelo_303_2025 import RULESET as RULESET_303_2025
from .runtime import build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _ruleset_casilla_ids(ruleset) -> set[str]:
    """Return the set of casilla IDs the ruleset's formulas write to."""
    return {formula.casilla_id for formula in ruleset.formulas}


def _schema_casilla_ids(modelo: str) -> set[str]:
    """Return the set of casilla IDs the runtime schema enumerates."""
    provider = build_runtime_schema_provider()
    return {c.id for c in provider.get_collection(modelo).all()}


_RULESET_FIXTURES = (
    pytest.param("130", 2024, RULESET_130_2024, id="modelo-130-2024"),
    pytest.param("130", 2025, RULESET_130_2025, id="modelo-130-2025"),
    pytest.param("303", 2024, RULESET_303_2024, id="modelo-303-2024"),
    pytest.param("303", 2025, RULESET_303_2025, id="modelo-303-2025"),
)


@pytest.mark.parametrize(("modelo", "año", "ruleset"), _RULESET_FIXTURES)
def test_schema_covers_every_ruleset_casilla(
    modelo: str,
    año: int,
    ruleset,
) -> None:
    """Every casilla written by the ruleset must appear in the schema."""
    del año  # reserved for per-año schema versioning
    schema_ids = _schema_casilla_ids(modelo)
    ruleset_ids = _ruleset_casilla_ids(ruleset)
    missing = ruleset_ids - schema_ids
    assert not missing, (
        f"Ruleset references casillas missing from schema: {sorted(missing)}. "
        "Schema/ruleset drift detected."
    )
