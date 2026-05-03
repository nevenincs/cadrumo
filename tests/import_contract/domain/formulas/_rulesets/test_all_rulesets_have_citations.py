"""Hard regression guard for the mandatory-citation invariant.

The :class:`CasillaDefinition` validator raises at construction time
when a ``computed=True`` casilla has empty ``legal_basis``. This test
walks every ruleset registered under
:data:`ALL_RULESETS` and asserts 100% coverage on every computed
casilla — defence in depth against any future ruleset that bypasses
the validator via :meth:`pydantic.BaseModel.model_construct` or any
other escape hatch.

Together with the per-validator unit tests in
``src/aeat/formulas/test_casilla_validator.py``, this file is the CI
guarantee that the mandatory-citation contract holds across the entire
registered ruleset universe.
"""

from __future__ import annotations

import pytest

from aeat.domain.formulas._ruleset import Ruleset
from aeat.domain.formulas._rulesets import ALL_RULESETS
from aeat.entrypoints.cli.audit import validate_citation_coverage

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@pytest.mark.parametrize(
    "ruleset",
    ALL_RULESETS,
    ids=[ruleset.ruleset_id for ruleset in ALL_RULESETS],
)
def test_every_computed_casilla_has_at_least_one_citation(ruleset: Ruleset) -> None:
    """Every ``computed=True`` casilla in ``ruleset`` carries a citation."""
    report = validate_citation_coverage(ruleset)
    assert report.is_complete, (
        f"ruleset {report.ruleset_id!r} has missing legal_basis on computed casillas: {list(report.missing_casillas)!r}"
    )


def test_every_landed_ruleset_carries_at_least_one_computed_casilla() -> None:
    """Sanity check: each ruleset is a non-trivial calc surface.

    A ruleset with zero computed casillas trivially passes the
    coverage gate but provides no calc value; this guard surfaces a
    future drift where a ruleset author accidentally lands a
    formula-free shell.
    """
    bad: list[str] = []
    for ruleset in ALL_RULESETS:
        if not any(c.computed for c in ruleset.casillas):
            bad.append(ruleset.ruleset_id)
    assert not bad, f"rulesets without any computed casilla: {bad!r}"
