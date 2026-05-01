"""Cross-track metadata consistency between ruleset and schema.

Each formula ruleset carries metadata (``modelo``, ``variant``,
``effective_from``, ``effective_to``) that must align with the
per-modelo schema module it pairs with — otherwise a CLI dispatch
could route a 130 ruleset to a 303 schema (or vice-versa) and
silently serialise casillas into the wrong fichero-BOE envelope.

Concrete invariants locked here:

1. ``ruleset_id`` format is ``modelo_{code}.{YYYY}`` and its
   ``{code}`` matches the modelo number the schema module was
   authored for (e.g. ``modelo_130.2024`` pairs with
   :mod:`.modelo_130_2024`).
2. ``effective_from`` year equals the schema's ejercicio.
3. ``effective_to`` is within the same ejercicio (no cross-year
   rulesets until 0.2.x when rectificativa rulesets land).

This is the companion Stream A invariant to /118 (which
locked the provenance citations *inside* each schema module
docstring); the *external* metadata pointer from
the ruleset into the schema.
"""

from __future__ import annotations

import pytest

from ......domain.formulas._ruleset import Ruleset
from ......domain.formulas._rulesets.modelo_130_2024 import RULESET as RULESET_130_2024
from ......domain.formulas._rulesets.modelo_130_2025 import RULESET as RULESET_130_2025
from ......domain.formulas._rulesets.modelo_303_2024 import RULESET as RULESET_303_2024
from ......domain.formulas._rulesets.modelo_303_2025 import RULESET as RULESET_303_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


_RULESETS: list[tuple[str, str, Ruleset]] = [
    ("130", "2024", RULESET_130_2024),
    ("130", "2025", RULESET_130_2025),
    ("303", "2024", RULESET_303_2024),
    ("303", "2025", RULESET_303_2025),
]

_IDS = [f"{m}-{e}" for m, e, _ in _RULESETS]


class TestRulesetMetadataAlignsWithSchema:
    @pytest.mark.parametrize(("modelo", "ejercicio", "ruleset"), _RULESETS, ids=_IDS)
    def test_ruleset_id_shape(self, modelo: str, ejercicio: str, ruleset: Ruleset) -> None:
        """``ruleset_id`` must be ``modelo_{modelo}.{ejercicio}`` so a registry
        lookup by schema module name can deterministically find its ruleset."""
        expected = f"modelo_{modelo}.{ejercicio}"
        assert ruleset.ruleset_id == expected, f"ruleset_id {ruleset.ruleset_id!r} != expected {expected!r}"

    @pytest.mark.parametrize(("modelo", "ejercicio", "ruleset"), _RULESETS, ids=_IDS)
    def test_modelo_matches(self, modelo: str, ejercicio: str, ruleset: Ruleset) -> None:
        """ruleset.modelo must be the ``ModeloCode`` enum value for ``modelo``."""
        assert str(ruleset.modelo.value) == modelo, f"ruleset.modelo {ruleset.modelo!r} != expected {modelo!r}"

    @pytest.mark.parametrize(("modelo", "ejercicio", "ruleset"), _RULESETS, ids=_IDS)
    def test_effective_from_year_matches_ejercicio(self, modelo: str, ejercicio: str, ruleset: Ruleset) -> None:
        assert ruleset.effective_from.year == int(ejercicio), (
            f"ruleset.effective_from.year {ruleset.effective_from.year} != expected {ejercicio}"
        )

    @pytest.mark.parametrize(("modelo", "ejercicio", "ruleset"), _RULESETS, ids=_IDS)
    def test_effective_to_stays_within_ejercicio(self, modelo: str, ejercicio: str, ruleset: Ruleset) -> None:
        """No cross-year rulesets shipped yet. When rectificativa rulesets
        (#234 / 0.2.x) land, relax this assertion per-modelo."""
        effective_to = ruleset.effective_to
        assert effective_to is not None, f"ruleset {ruleset.ruleset_id!r} has open-ended effective_to"
        assert effective_to.year == int(ejercicio), (
            f"ruleset.effective_to.year {effective_to.year} != expected {ejercicio} — "
            f"cross-year ruleset not yet supported."
        )
