"""Unit tests for the Modelo 303 2026 ruleset.

The 2026 ruleset is a scoped régimen-general clone of the 2024 and
2025 rulesets because the BOE-grounded rates used by this ruleset
remain 21 %, 10 %, and 4 % under LIVA arts. 90 and 91. Expected values
in this module are derived from those articles and the Modelo 303 form
arithmetic, never from the ruleset's parameter table.

Exercises :data:`aeat.domain.formulas._rulesets.MODELO_303_2026` against
:class:`aeat.domain.formulas._engine.Engine` for both ``derive`` and
``audit_against`` paths.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_303_2025, MODELO_303_2026

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _provided() -> dict[str, Decimal]:
    """Return the externally anchored Q1 2026 IVA fixture for régimen general.

    LIVA art. 90 fixes the 21 % general rate; LIVA art. 91 fixes the
    reduced 10 % and super-reduced 4 % rates represented here. The
    remaining arithmetic follows the Modelo 303 liquidación structure:
    total devengado less total deductible VAT, then state attribution
    and prior-period compensation.

    Returns:
        A casilla-id keyed mapping suitable for
        :meth:`aeat.domain.formulas._engine.Engine.audit_against`.
    """
    return {
        "01": Decimal("1000.00"),
        "02": Decimal("4.00"),
        "03": Decimal("40.00"),
        "04": Decimal("2000.00"),
        "05": Decimal("10.00"),
        "06": Decimal("200.00"),
        "07": Decimal("10000.00"),
        "08": Decimal("21.00"),
        "09": Decimal("2100.00"),
        "28": Decimal("0.00"),
        "29": Decimal("100.00"),
        "30": Decimal("0.00"),
        "31": Decimal("50.00"),
        "32": Decimal("0.00"),
        "33": Decimal("25.00"),
        "34": Decimal("0.00"),
        "35": Decimal("0.00"),
        "36": Decimal("0.00"),
        "37": Decimal("0.00"),
        "38": Decimal("0.00"),
        "39": Decimal("0.00"),
        "40": Decimal("-10.00"),
        "41": Decimal("0.00"),
        "42": Decimal("0.00"),
        "43": Decimal("0.00"),
        "44": Decimal("165.00"),
        "45": Decimal("2175.00"),
        "64": Decimal("2175.00"),
        "65": Decimal("100.00"),
        "66": Decimal("2175.00"),
        "67": Decimal("125.00"),
        "69": Decimal("2050.00"),
        "71": Decimal("2050.00"),
    }


class TestModelo303Ruleset2026:
    """Behavioural tests for the 2026 Modelo 303 ruleset variant."""

    def test_consistent_quarter_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_303_2026,
            provided=_provided(),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_2026_no_drift_from_2025(self) -> None:
        provided = _provided()
        report_2025 = Engine().audit_against(
            ruleset=MODELO_303_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        report_2026 = Engine().audit_against(
            ruleset=MODELO_303_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report_2025.is_clean()
        assert report_2026.is_clean()
        assert {e.casilla_id: e.value for e in report_2025.ledger.entries} == {
            e.casilla_id: e.value for e in report_2026.ledger.entries
        }

    def test_ruleset_id_and_effective_range(self) -> None:
        assert MODELO_303_2026.ruleset_id == "modelo_303.2026"
        assert MODELO_303_2026.effective_from == date(2026, 1, 1)
        assert MODELO_303_2026.effective_to == date(2026, 12, 31)

    @pytest.mark.parametrize(
        ("base_casilla", "base_value", "quota_casilla", "expected_quota"),
        [
            ("01", Decimal("333.33"), "03", Decimal("13.33")),
            ("04", Decimal("333.33"), "06", Decimal("33.33")),
            ("07", Decimal("333.33"), "09", Decimal("70.00")),
        ],
    )
    def test_external_rate_bucket_rounding(
        self,
        base_casilla: str,
        base_value: Decimal,
        quota_casilla: str,
        expected_quota: Decimal,
    ) -> None:
        """LIVA art. 90/91 rate buckets round cent-exact per casilla."""
        values = {base_casilla: base_value, "65": Decimal("100.00")}
        derived = {e.casilla_id: e.value for e in Engine().derive(ruleset=MODELO_303_2026, inputs=values).entries}
        assert derived[quota_casilla] == expected_quota

    def test_deductible_components_feed_casilla_44(self) -> None:
        """LIVA title VIII deduction buckets are taxpayer-supplied and summed in c44."""
        values = {
            "29": Decimal("10.00"),
            "31": Decimal("20.00"),
            "33": Decimal("30.00"),
            "35": Decimal("40.00"),
            "37": Decimal("50.00"),
            "39": Decimal("60.00"),
            "40": Decimal("-5.00"),
            "41": Decimal("7.00"),
            "42": Decimal("8.00"),
            "43": Decimal("9.00"),
        }
        derived = {e.casilla_id: e.value for e in Engine().derive(ruleset=MODELO_303_2026, inputs=values).entries}
        assert derived["44"] == Decimal("229.00")

    def test_state_attribution_and_prior_compensation(self) -> None:
        """Modelo 303 c66/c69/c71 attribution chain uses c65 and c67."""
        values = {
            "07": Decimal("10000.00"),
            "65": Decimal("50.00"),
            "67": Decimal("100.00"),
        }
        derived = {e.casilla_id: e.value for e in Engine().derive(ruleset=MODELO_303_2026, inputs=values).entries}
        assert derived["09"] == Decimal("2100.00")
        assert derived["64"] == Decimal("2100.00")
        assert derived["66"] == Decimal("1050.00")
        assert derived["69"] == Decimal("950.00")
        assert derived["71"] == Decimal("950.00")

    def test_rate_mismatch_raises_discrepancy(self) -> None:
        provided = _provided()
        provided["09"] = Decimal("2000.00")
        report = Engine().audit_against(
            ruleset=MODELO_303_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert "09" in {d.casilla_id for d in report.discrepancies}
