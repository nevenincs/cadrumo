"""Strict installed M303 oracle, receipt and completion outcome projection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, cast

from .m303_evidence_contracts import _ORACLE_RESULTADO, IvaInstalledM303Error, ReopenReadback, TuiOutcome

if TYPE_CHECKING:
    pass


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise IvaInstalledM303Error(f"{label} returned no object")
    return cast(Mapping[str, object], value)


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise IvaInstalledM303Error(f"{label} returned no text")
    return value


def _year_end_observed_at(year: int) -> str:
    """The attestation observation instant: noon UTC on the last day of the filing year."""
    return f"{year}-12-31T12:00:00+00:00"


def resultado_matches_oracle(raw: object) -> bool:
    """Compare one public ``iva.resultado`` rendering with the independent 21.00 - 10.50 oracle."""
    try:
        return Decimal(str(raw)).quantize(Decimal("0.01")) == _ORACLE_RESULTADO
    except (InvalidOperation, ValueError):
        return False


def require_reopen(readback: ReopenReadback | None, *, scenario: str) -> ReopenReadback:
    """Require the fresh TUI to list the verified revision as current and its workbench to show the oracle's result."""
    if readback is None or not readback.revision_listed_current or readback.revision_state != "verificado_completo":
        raise IvaInstalledM303Error(f"fresh installed TUI did not list the {scenario} revision as current and verified")
    if readback.resultado_origin != "calculated" or readback.resultado_matches_oracle is not True:
        raise IvaInstalledM303Error(
            f"fresh installed TUI workbench for {scenario} did not show a calculated iva.resultado equal to the oracle"
        )
    return readback


def require_outcomes(outcomes: Sequence[TuiOutcome], expected: Mapping[str, tuple[str, str | None]]) -> None:
    """Require each named step to have reached the expected terminal and, when named, visible notice."""
    observed = {item.step: (item.terminal_condition, item.visible_notice_key) for item in outcomes}
    for step, (condition, notice) in expected.items():
        actual = observed.get(step)
        if actual is None or actual[0] != condition or (notice is not None and actual[1] != notice):
            raise IvaInstalledM303Error(f"installed TUI step {step} observed {actual}, expected {(condition, notice)}")
