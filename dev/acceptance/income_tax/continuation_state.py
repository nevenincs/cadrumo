"""Canonical installed continuation state construction and receipt decoding."""

from __future__ import annotations

from collections.abc import Sequence

from .continuation_contracts import InstalledContinuationError
from .financial_lifecycle import _m130_expected
from .scenario import build_scenario
from .tui_continuation_evidence import (
    canonical_financial_value_fingerprint,
)
from .tui_contracts import ContinuationStateEvidence


def _oracle_fingerprint(year: int) -> str:
    """Fingerprint the independent scenario oracle, never a frontend readback."""
    scenario = build_scenario(year)
    values: dict[str, str] = {}
    for oracle in scenario.quarter_oracle:
        values.update({f"130.{oracle.period}.{key}": value for key, value in _m130_expected(oracle).items()})
    annual = scenario.annual_oracle
    values.update(
        {
            "100.0A.E1INGRESO": f"{annual.activity_income:.2f}",
            "100.0A.E1NGD": f"{annual.deductible_expenses:.2f}",
            "100.0A.E1RN": f"{annual.activity_net_income:.2f}",
            "100.0A.PAGOS": f"{annual.m130_payments:.2f}",
        }
    )
    return canonical_financial_value_fingerprint(values=values)


def _state(
    *, generation: str, year: int, periods: Sequence[str], filed: Sequence[str], annual_exported: bool
) -> ContinuationStateEvidence:
    quarter_periods = tuple(sorted(set(periods)))
    filed_periods = tuple(sorted(set(filed)))
    return ContinuationStateEvidence(
        authority_generation=generation,
        profile_complete=True,
        transactions=8,
        invoices=8,
        links=8,
        work_periods=quarter_periods,
        calculated_periods=filed_periods,
        verified_periods=filed_periods,
        locally_filed_periods=filed_periods,
        export_ready_modelos=("100",) if annual_exported else (),
        exported_modelos=("100",) if annual_exported else (),
        # The shared continuation contract currently carries one fingerprint.
        # This is explicitly an oracle guard; the receipt labels it as such and
        # keeps cross-frontend observed-value equality unexercised.
        canonical_value_fingerprint=_oracle_fingerprint(year),
    )


def _parse_child_state(document: dict[str, object], key: str) -> ContinuationStateEvidence:
    raw = document.get(key)
    if not isinstance(raw, dict):
        raise InstalledContinuationError(f"TUI continuation receipt has no {key}")
    tuple_fields = (
        "work_periods",
        "calculated_periods",
        "verified_periods",
        "locally_filed_periods",
        "export_ready_modelos",
        "exported_modelos",
    )
    decoded = dict(raw)
    for name in tuple_fields:
        value = decoded.get(name)
        if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value):
            raise InstalledContinuationError(f"TUI continuation receipt has invalid {key}.{name}")
        decoded[name] = tuple(value)
    try:
        return ContinuationStateEvidence(**decoded)
    except TypeError as exc:
        raise InstalledContinuationError(f"TUI continuation receipt has invalid {key}") from exc
