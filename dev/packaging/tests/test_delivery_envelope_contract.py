"""Installed CLI delivery-envelope contract coverage."""

from __future__ import annotations

from typing import Any

import pytest

from ..installed_tax_oracle import (
    PROFILE_LABEL,
    InstalledTaxOracleError,
    assert_envelope_contract,
    assert_no_diagnostic_notices,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_COMMAND = "modelo.work.calculate"


def _envelope(**overrides: Any) -> dict[str, Any]:
    """A conforming delivered envelope, with named fields overridden."""
    envelope: dict[str, Any] = {
        "command": _COMMAND,
        "status": "success",
        "active_profile": PROFILE_LABEL,
        "result": {"work_unit_id": "wu-1"},
        "notices": [],
    }
    envelope.update(overrides)
    return envelope


def test_conforming_envelope_returns_its_result_mapping() -> None:
    """A conforming envelope yields the result object the caller consumes."""
    result = assert_envelope_contract(
        _envelope(),
        command=_COMMAND,
        error=InstalledTaxOracleError,
    )

    assert result == {"work_unit_id": "wu-1"}


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"command": "modelo.work.create"}, "expected command"),
        ({"status": "error"}, "did not succeed"),
        ({"active_profile": "someone-else"}, "active profile"),
        ({"result": ["not", "an", "object"]}, "result is not an object"),
        ({"notices": {"not": "a list"}}, "notices are not a list"),
    ],
)
def test_each_spine_violation_is_refused(overrides: dict[str, Any], fragment: str) -> None:
    """Every field of the spine is load-bearing, not merely read.

    Each case breaks exactly one field of an otherwise conforming envelope, so a
    helper that stopped checking that field would let its case through.
    """
    with pytest.raises(InstalledTaxOracleError) as excinfo:
        assert_envelope_contract(
            _envelope(**overrides),
            command=_COMMAND,
            error=InstalledTaxOracleError,
        )

    assert fragment in str(excinfo.value)


def test_warning_status_passes_the_spine_but_fails_the_clean_notice_gate() -> None:
    """``warning`` is a delivered status, yet not a clean run.

    The two assertions answer different questions, and collapsing them would
    either reject a legitimate warning envelope or accept a diagnostic one.
    """
    warned = _envelope(
        status="warning",
        notices=[{"severity": "warning", "code": "modelo.work.calculate.plazo_vencido"}],
    )

    assert assert_envelope_contract(warned, command=_COMMAND, error=InstalledTaxOracleError)

    with pytest.raises(InstalledTaxOracleError) as excinfo:
        assert_no_diagnostic_notices(warned, command=_COMMAND, error=InstalledTaxOracleError)

    # The NOTICE is what refuses this envelope, not the status. With nothing
    # excused, any diagnostic raises before the status branch is reached, and
    # that branch additionally requires ``not diagnostics`` - so for an
    # envelope carrying one it cannot fire at all. Asserting the status
    # message here named a refusal this input can never produce.
    assert "unexpected diagnostic notices" in str(excinfo.value)


def test_a_non_success_status_without_diagnostics_is_refused_on_the_status() -> None:
    """The other branch: nothing to report, yet the run did not succeed.

    Reached only when no diagnostic notice exists, which is why no case above
    exercises it - each carries a notice that refuses first. Without this the
    status branch had no proof at all, and the message it raises was asserted
    nowhere the helper could produce it.
    """
    with pytest.raises(InstalledTaxOracleError) as excinfo:
        assert_no_diagnostic_notices(
            _envelope(status="warning", notices=[]),
            command=_COMMAND,
            error=InstalledTaxOracleError,
        )

    assert "expected success status" in str(excinfo.value)


def test_diagnostic_notice_under_success_status_is_refused() -> None:
    """A success envelope carrying an error notice is not a clean run."""
    with pytest.raises(InstalledTaxOracleError) as excinfo:
        assert_no_diagnostic_notices(
            _envelope(notices=[{"severity": "error", "code": "x.y"}]),
            command=_COMMAND,
            error=InstalledTaxOracleError,
        )

    assert "unexpected diagnostic notices" in str(excinfo.value)


def test_informational_notices_do_not_fail_the_clean_notice_gate() -> None:
    """An info notice is not a diagnostic, so a clean run still passes."""
    assert_no_diagnostic_notices(
        _envelope(notices=[{"severity": "info", "code": "x.y"}]),
        command=_COMMAND,
        error=InstalledTaxOracleError,
    )
