"""Cross-layer metadata consistency between ruleset and schema modules.

Each formula ruleset carries metadata (``modelo``, ``variant``,
``effective_from``, ``effective_to``) that must align with the
per-modelo schema module it pairs with; otherwise a CLI dispatch
could route a 130 ruleset to a 303 schema (or vice versa) and
silently serialise casillas into the wrong fichero-BOE envelope.

Invariants locked here:

* ``ruleset_id`` follows the format ``modelo_{code}.{YYYY}`` and the
  ``{code}`` matches the modelo number the schema module was
  authored for (e.g. ``modelo_130.2024`` pairs with
  :mod:`.modelo_130_2024`).
* ``effective_from`` year equals the schema's ejercicio.
* ``effective_to`` falls within the same ejercicio; cross-year
  rulesets are not yet supported until rectificativa rulesets land.

This pins the external metadata pointer from the ruleset into the
schema; the in-module provenance citations are pinned separately by
the schema-coverage suites.
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
    """Cross-layer metadata invariants for ruleset / schema pairs."""

    @pytest.mark.parametrize(("modelo", "ejercicio", "ruleset"), _RULESETS, ids=_IDS)
    def test_ruleset_id_shape(self, modelo: str, ejercicio: str, ruleset: Ruleset) -> None:
        """Assert ``ruleset_id`` matches ``modelo_{modelo}.{ejercicio}``.

        A deterministic ID shape lets a registry lookup by schema
        module name resolve directly to the paired ruleset.
        """
        expected = f"modelo_{modelo}.{ejercicio}"
        assert ruleset.ruleset_id == expected, f"ruleset_id {ruleset.ruleset_id!r} != expected {expected!r}"

    @pytest.mark.parametrize(("modelo", "ejercicio", "ruleset"), _RULESETS, ids=_IDS)
    def test_modelo_matches(self, modelo: str, ejercicio: str, ruleset: Ruleset) -> None:
        """Assert ``ruleset.modelo`` equals the ``ModeloCode`` enum value for ``modelo``."""
        assert str(ruleset.modelo.value) == modelo, f"ruleset.modelo {ruleset.modelo!r} != expected {modelo!r}"

    @pytest.mark.parametrize(("modelo", "ejercicio", "ruleset"), _RULESETS, ids=_IDS)
    def test_effective_from_year_matches_ejercicio(self, modelo: str, ejercicio: str, ruleset: Ruleset) -> None:
        """Assert ``ruleset.effective_from.year`` equals the schema's ejercicio."""
        assert ruleset.effective_from.year == int(ejercicio), (
            f"ruleset.effective_from.year {ruleset.effective_from.year} != expected {ejercicio}"
        )

    @pytest.mark.parametrize(("modelo", "ejercicio", "ruleset"), _RULESETS, ids=_IDS)
    def test_effective_to_stays_within_ejercicio(self, modelo: str, ejercicio: str, ruleset: Ruleset) -> None:
        """Assert ``ruleset.effective_to`` falls within the same ejercicio.

        Cross-year rulesets are not yet supported; when rectificativa
        rulesets land, relax this assertion per-modelo deliberately.
        """
        effective_to = ruleset.effective_to
        assert effective_to is not None, f"ruleset {ruleset.ruleset_id!r} has open-ended effective_to"
        assert effective_to.year == int(ejercicio), (
            f"ruleset.effective_to.year {effective_to.year} != expected {ejercicio} — "
            f"cross-year ruleset not yet supported."
        )
