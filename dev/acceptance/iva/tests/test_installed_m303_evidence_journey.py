"""Pure checks of the installed ordinary-M303 evidence journey's oracle and outcome gates."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..m303_evidence_contracts import IvaInstalledM303Error, ReopenReadback, TuiOutcome
from ..m303_evidence_projection import require_outcomes, require_reopen, resultado_matches_oracle

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("rendered", "matches"),
    [
        ("10.50", True),
        ("10.5", True),
        ("10.500", True),
        ("10.49", False),
        ("-10.50", False),
        ("", False),
        ("n/a", False),
    ],
)
def test_the_independent_oracle_accepts_only_the_expected_resultado(rendered: str, matches: bool) -> None:
    """21.00 output IVA minus 10.50 deductible IVA, whatever the rendering's trailing zeros."""
    assert resultado_matches_oracle(rendered) is matches


def test_outcome_gate_refuses_a_missing_step_or_a_different_terminal_or_notice() -> None:
    """A step proves nothing unless both its terminal and its visible notice match."""
    observed = (
        TuiOutcome(step="calculate", terminal_condition="succeeded", visible_notice_key=None),
        TuiOutcome(
            step="cancelled", terminal_condition="cancelled_without_request", visible_notice_key="key.cancelled"
        ),
    )
    require_outcomes(
        observed, {"calculate": ("succeeded", None), "cancelled": ("cancelled_without_request", "key.cancelled")}
    )
    with pytest.raises(IvaInstalledM303Error):
        require_outcomes(observed, {"verify": ("succeeded", None)})
    with pytest.raises(IvaInstalledM303Error):
        require_outcomes(observed, {"calculate": ("refused", None)})
    with pytest.raises(IvaInstalledM303Error):
        require_outcomes(observed, {"cancelled": ("cancelled_without_request", "key.other")})


def _readback(
    *,
    listed: bool = True,
    state: str | None = "verificado_completo",
    origin: str | None = "calculated",
    matches: bool = True,
) -> ReopenReadback:
    return ReopenReadback(
        revision_listed_current=listed,
        revision_state=state,
        resultado_origin=origin,
        resultado_matches_oracle=matches,
    )


def test_reopen_gate_accepts_a_current_verified_revision_whose_workbench_shows_the_oracle() -> None:
    readback = _readback()
    assert require_reopen(readback, scenario="tui_led") is readback


@pytest.mark.parametrize(
    "readback",
    [
        None,
        _readback(listed=False),
        _readback(state="borrador"),
        _readback(state=None),
        _readback(matches=False),
        _readback(origin=None, matches=False),
        _readback(origin="not_calculated_yet"),
        _readback(origin="default_to_confirm"),
    ],
    ids=[
        "no-readback",
        "not-current",
        "unverified",
        "state-unread",
        "resultado-mismatch",
        "resultado-not-shown",
        "resultado-not-calculated",
        "resultado-not-from-the-calculation",
    ],
)
def test_reopen_gate_refuses_an_unlisted_unverified_or_unequal_readback(readback: ReopenReadback | None) -> None:
    with pytest.raises(IvaInstalledM303Error):
        require_reopen(readback, scenario="tui_led")


@pytest.mark.parametrize(
    ("value", "matches"),
    [(Decimal("10.50"), True), (Decimal("10.5"), True), (Decimal("-10.50"), False), (None, False)],
)
def test_the_oracle_reads_the_typed_value_the_workbench_form_holds(value: Decimal | None, matches: bool) -> None:
    """The workbench's form holds a typed Decimal, or nothing, never a rendered string."""
    assert resultado_matches_oracle(value) is matches
