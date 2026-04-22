"""Cross-track invariant: ruleset casillas vs schema casillas (wave 113).

Stream B perpetual — every casilla_id declared in a formula ruleset
must either have a corresponding schema field so it ends up in the
emitted bytes, OR be explicitly listed in the per-modelo gap set
below. A casilla in the ruleset that has no schema field is
silently dropped at serialise time, which is exactly the kind of
drift the continuous-cycle mandate wants caught here, not at the
AEAT-upload failure surface.

When a gap is closed (e.g. the DR303 xlsx extraction learns to
capture casillas 45 / 64 / 67 / 71), this test fails and forces an
update to ``_EXPECTED_GAPS`` plus a commit message explaining the
ruleset/schema evolution.

This is the sibling of ``test_reserved_literal_lengths.py`` (wave
112) — both enforce cross-layer consistency so neither the ruleset
nor the schema can drift alone without an audible test failure.
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from ...formulas._casilla import CasillaDefinition
from ...formulas._rulesets.modelo_130_2024 import RULESET as RULESET_130_2024
from ...formulas._rulesets.modelo_303_2024 import RULESET as RULESET_303_2024
from ._record_spec import RecordFieldSpec, SegmentSpec
from .modelo_130_2024 import RECORD_SPECS as RECORD_SPECS_130
from .modelo_303_2024 import ENVELOPE as ENVELOPE_303

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


#: Per-modelo casilla_ids that the ruleset computes but the schema does
#: not carry. Closing any of these gaps requires either regenerating the
#: schema from an updated DR fixture or hand-adding the missing fields.
_EXPECTED_GAPS: dict[str, frozenset[str]] = {
    # Modelo 303 2024: the DR303e24 xlsx extraction did not capture the
    # cuota-devengada-total / diferencia / a-ingresar casillas. They live
    # in the ruleset (and therefore still compute correctly in-memory)
    # but serialise_envelope silently drops them because no RecordFieldSpec
    # claims the casilla_id. Wave-N+ will regenerate the JSON fixture with
    # these fields added; the gap set shrinks as each is closed.
    "303.2024": frozenset({"45", "64", "67", "71"}),
    "130.2024": frozenset(),
}


def _ruleset_casilla_ids(ruleset_casillas: Iterable[CasillaDefinition]) -> frozenset[str]:
    return frozenset(c.casilla_id for c in ruleset_casillas)


def _record_schema_casilla_ids(specs: Iterable[RecordFieldSpec]) -> frozenset[str]:
    return frozenset(s.casilla_id for s in specs if s.casilla_id is not None)


def _envelope_schema_casilla_ids(envelope: Iterable[SegmentSpec]) -> frozenset[str]:
    out: set[str] = set()
    for seg in envelope:
        for s in seg.specs:
            if s.casilla_id is not None:
                out.add(s.casilla_id)
    return frozenset(out)


class TestRulesetSchemaCoverage:
    def test_modelo_130_2024_fully_covered(self) -> None:
        """Every 130 ruleset casilla has a schema field and vice versa.

        Modelo 130 is the reference case: the 19-casilla fixture is
        hand-authored from dr130.09.pdf and complete, so there must be
        no drift in either direction.
        """
        ruleset_cids = _ruleset_casilla_ids(RULESET_130_2024.casillas)
        schema_cids = _record_schema_casilla_ids(RECORD_SPECS_130)
        assert ruleset_cids == schema_cids, (
            f"130 2024 ruleset/schema casilla divergence.\n"
            f"  ruleset only: {sorted(ruleset_cids - schema_cids)}\n"
            f"  schema only:  {sorted(schema_cids - ruleset_cids)}"
        )

    def test_modelo_303_2024_gap_is_exactly_known(self) -> None:
        """303 ruleset minus schema must equal the documented gap set.

        If this fails with a SHRUNK gap, the DR fixture just gained a
        missing casilla — update ``_EXPECTED_GAPS`` and ship.
        If it fails with a GROWN gap, the ruleset declared a new
        casilla without a corresponding schema field — audit first.
        """
        ruleset_cids = _ruleset_casilla_ids(RULESET_303_2024.casillas)
        schema_cids = _envelope_schema_casilla_ids(ENVELOPE_303)
        actual_gap = ruleset_cids - schema_cids
        expected_gap = _EXPECTED_GAPS["303.2024"]
        assert actual_gap == expected_gap, (
            f"303 2024 ruleset/schema gap drift.\n"
            f"  expected ruleset-only: {sorted(expected_gap)}\n"
            f"  actual   ruleset-only: {sorted(actual_gap)}\n"
            "Update _EXPECTED_GAPS in this test and explain the delta in "
            "the commit message (gap closed = fixture gained a field; "
            "gap grew = ruleset declared a new casilla without schema backing)."
        )

    def test_no_runaway_schema_orphans(self) -> None:
        """The 303 schema carries ~100 casillas but the ruleset only formulates
        a subset. The schema-only set is Kent-observable (he can fill a casilla
        manually even if the ruleset doesn't derive it), so we don't lock its
        exact contents here — just assert the count stays above 50 so an
        accidental fixture truncation can't silently drop dozens of fields
        without failing a test."""
        schema_cids = _envelope_schema_casilla_ids(ENVELOPE_303)
        assert len(schema_cids) >= 50, (
            f"303 envelope schema dropped below 50 casillas ({len(schema_cids)}); probable fixture regression."
        )
