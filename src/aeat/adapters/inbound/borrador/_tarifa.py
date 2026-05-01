"""Tarifa progresiva IRPF post-validator for Modelo 100.

The summary-block ruleset covers four top-level derivations (cuota
íntegra total, total deducciones, cuota líquida, cuota resultante) by
treating each cuota íntegra component as a literal Kent fills in. The
*real* computation of the cuota íntegra goes through Spain's progressive
IRPF tax scale — the **tarifa progresiva** — applied separately to the
base liquidable general and the base liquidable del ahorro, split
further into state and autonomous halves.

This module implements the state halves (common to every Kent regardless
of CCAA) as a piecewise-linear tax calculation, and exposes
:func:`validate_tarifa_estatal`, the post-validator that Kent's verdict
pipeline calls after the formula engine pass. Autonomous halves stay out
of scope — they vary per comunidad autónoma.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

# Tarifa progresiva IRPF estatal general 2025 — art. 63 Ley 35/2006.
# Each entry: (upper_inclusive_decimal_str_or_None, marginal_rate_str).
_TARIFA_ESTATAL_GENERAL_2025: tuple[tuple[str | None, str], ...] = (
    ("12450.00", "0.095"),
    ("20200.00", "0.12"),
    ("35200.00", "0.15"),
    ("60000.00", "0.185"),
    ("300000.00", "0.225"),
    (None, "0.245"),
)

# Tarifa progresiva IRPF estatal del ahorro 2025 — art. 66 Ley 35/2006.
_TARIFA_ESTATAL_AHORRO_2025: tuple[tuple[str | None, str], ...] = (
    ("6000.00", "0.095"),
    ("50000.00", "0.105"),
    ("200000.00", "0.115"),
    ("300000.00", "0.1375"),
    (None, "0.14"),
)

_TWO_CENT_TOLERANCE = Decimal("0.02")
_QUANTUM = Decimal("0.01")

_SUPPORTED_EJERCICIOS: frozenset[str] = frozenset({"2024", "2025"})
"""Ejercicios currently covered by the state-IRPF scale constants.

2024 and 2025 share identical brackets under art. 63 / art. 66 Ley
35/2006 (Ley de Presupuestos 2024/2025 did not shift estatal brackets).
New ejercicios must register their own bracket tuple and extend this
set.
"""


def apply_tarifa(
    base_liquidable: Decimal,
    brackets: tuple[tuple[str | None, str], ...],
) -> Decimal:
    """Apply a progressive tax scale to ``base_liquidable``.

    For each bracket with upper-inclusive ``U_i`` and marginal rate
    ``r_i`` (lower bound = previous upper or 0), the contribution is
    ``r_i * max(0, min(base, U_i) - U_{i-1})``. The cuota íntegra is the
    sum of all bracket contributions, rounded to cents using
    :data:`decimal.ROUND_HALF_UP`.

    Args:
        base_liquidable: The base liquidable to which the scale is
            applied.
        brackets: Tuple of ``(upper_inclusive_decimal_str_or_None,
            marginal_rate_str)`` tuples describing the progressive
            scale.

    Returns:
        The cuota íntegra. Returns ``Decimal('0.00')`` for non-positive
        bases.
    """
    if base_liquidable <= Decimal("0"):
        return Decimal("0.00")

    cuota = Decimal("0")
    previous_upper = Decimal("0")
    for upper_str, rate_str in brackets:
        rate = Decimal(rate_str)
        if upper_str is None:
            top = base_liquidable
        else:
            upper = Decimal(upper_str)
            top = min(base_liquidable, upper)
        slice_width = top - previous_upper
        if slice_width > 0:
            cuota += rate * slice_width
        if upper_str is None or base_liquidable <= Decimal(upper_str):
            break
        previous_upper = Decimal(upper_str)

    return cuota.quantize(_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class TarifaFinding:
    """One cuota íntegra vs. tarifa mismatch surfaced by the validator.

    Attributes:
        casilla_id: AEAT casilla id whose extracted cuota diverges from
            the tarifa-derived value (``"0550"`` for the general scale,
            ``"0560"`` for the savings scale).
        base_casilla_id: AEAT casilla id of the base liquidable used as
            the input to the tarifa (``"0545"`` for general,
            ``"0555"`` for savings).
        expected_cuota: The cuota the tarifa scale produces for the
            given base.
        actual_cuota: The cuota actually printed in the PDF.
        delta: ``actual_cuota - expected_cuota``.
    """

    casilla_id: str  # "0550" or "0560"
    base_casilla_id: str  # "0545" or "0555"
    expected_cuota: Decimal
    actual_cuota: Decimal
    delta: Decimal


def validate_tarifa_estatal(
    *,
    ejercicio: str,
    base_liquidable_general: Decimal | None,
    base_liquidable_ahorro: Decimal | None,
    cuota_estatal_general: Decimal | None,
    cuota_estatal_ahorro: Decimal | None,
    tolerance: Decimal = _TWO_CENT_TOLERANCE,
) -> tuple[TarifaFinding, ...]:
    """Compare extracted cuota íntegra estatal against the progressive tarifa.

    Args:
        ejercicio: Four-digit tax year. Must be a member of
            :data:`_SUPPORTED_EJERCICIOS`.
        base_liquidable_general: Extracted base liquidable general, or
            ``None`` to skip the general check.
        base_liquidable_ahorro: Extracted base liquidable del ahorro, or
            ``None`` to skip the savings check.
        cuota_estatal_general: Extracted cuota íntegra estatal general,
            or ``None`` to skip the general check.
        cuota_estatal_ahorro: Extracted cuota íntegra estatal del
            ahorro, or ``None`` to skip the savings check.
        tolerance: Absolute euro tolerance (default
            :data:`_TWO_CENT_TOLERANCE`) between the extracted cuota and
            the tarifa-derived value.

    Returns:
        One :class:`TarifaFinding` per casilla where the extracted cuota
        diverges from the tarifa-derived value by more than ``tolerance``
        euros. Missing inputs (``None``) silently skip their check — a
        partial extraction is not a discrepancy.

    Raises:
        ValueError: If ``ejercicio`` is not in
            :data:`_SUPPORTED_EJERCICIOS`. Unknown ejercicios are a
            correctness risk — silently validating a 2027 filing against
            the 2025 scale would mask real legislative drift.
    """
    if ejercicio not in _SUPPORTED_EJERCICIOS:
        raise ValueError(
            f"tarifa progresiva estatal is only defined for {sorted(_SUPPORTED_EJERCICIOS)}; "
            f"got ejercicio={ejercicio!r}"
        )
    findings: list[TarifaFinding] = []
    if base_liquidable_general is not None and cuota_estatal_general is not None:
        expected = apply_tarifa(base_liquidable_general, _TARIFA_ESTATAL_GENERAL_2025)
        delta = cuota_estatal_general - expected
        if abs(delta) > tolerance:
            findings.append(
                TarifaFinding(
                    casilla_id="0550",
                    base_casilla_id="0545",
                    expected_cuota=expected,
                    actual_cuota=cuota_estatal_general,
                    delta=delta,
                )
            )
    if base_liquidable_ahorro is not None and cuota_estatal_ahorro is not None:
        expected = apply_tarifa(base_liquidable_ahorro, _TARIFA_ESTATAL_AHORRO_2025)
        delta = cuota_estatal_ahorro - expected
        if abs(delta) > tolerance:
            findings.append(
                TarifaFinding(
                    casilla_id="0560",
                    base_casilla_id="0555",
                    expected_cuota=expected,
                    actual_cuota=cuota_estatal_ahorro,
                    delta=delta,
                )
            )
    return tuple(findings)


__all__ = [
    "apply_tarifa",
    "validate_tarifa_estatal",
]
