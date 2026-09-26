"""Pure checks of the installed ordinary-M303 evidence journey's oracle and outcome gates."""

from __future__ import annotations

import pytest

from ..installed_m303_evidence_journey import (
    IvaInstalledM303Error,
    ReopenReadback,
    TuiOutcome,
    require_outcomes,
    require_reopen,
    resultado_matches_oracle,
)

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


_LISTED = ReopenReadback(
    revision_listed_current=True,
    revision_state="verificado_completo",
    results_page="not_applicable",
    results_resultado_matches_oracle=None,
)


@pytest.mark.parametrize(
    "readback",
    [
        _LISTED,
        ReopenReadback(
            revision_listed_current=True,
            revision_state="verificado_completo",
            results_page="rendered",
            results_resultado_matches_oracle=True,
        ),
    ],
    ids=["results-not-applicable", "results-rendered-equal"],
)
def test_reopen_gate_accepts_a_current_verified_revision(readback: ReopenReadback) -> None:
    """A not-applicable Results page is admitted here and reported as unexercised by the receipt, not as a match."""
    assert require_reopen(readback, scenario="tui_led") is readback


@pytest.mark.parametrize(
    "readback",
    [
        None,
        ReopenReadback(
            revision_listed_current=False,
            revision_state="verificado_completo",
            results_page="not_applicable",
            results_resultado_matches_oracle=None,
        ),
        ReopenReadback(
            revision_listed_current=True,
            revision_state="borrador",
            results_page="not_applicable",
            results_resultado_matches_oracle=None,
        ),
        ReopenReadback(
            revision_listed_current=True,
            revision_state="verificado_completo",
            results_page="rendered",
            results_resultado_matches_oracle=False,
        ),
        ReopenReadback(
            revision_listed_current=True,
            revision_state="verificado_completo",
            results_page="rendered",
            results_resultado_matches_oracle=None,
        ),
    ],
    ids=["no-readback", "not-current", "unverified", "rendered-mismatch", "rendered-unread"],
)
def test_reopen_gate_refuses_an_unlisted_unverified_or_unequal_readback(readback: ReopenReadback | None) -> None:
    with pytest.raises(IvaInstalledM303Error):
        require_reopen(readback, scenario="tui_led")
