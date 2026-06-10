"""Period-offset arithmetic shared by previous-filing and relation binding helpers.

Supports quarterly (``1T``..``4T``), pago-fraccionado (``1P``..``3P``), and
zero-padded monthly (``01``..``12``) period codes.  Offsets wrap across
calendar-year boundaries and return the derived period plus the relative year
delta.
"""

from __future__ import annotations

from ._errors import RegistryValidationError

_QUARTERLY_PERIOD_ORDINAL: dict[str, int] = {"1T": 1, "2T": 2, "3T": 3, "4T": 4}
_ORDINAL_TO_QUARTERLY: dict[int, str] = {ordinal: code for code, ordinal in _QUARTERLY_PERIOD_ORDINAL.items()}
_PAGO_FRACCIONADO_PERIOD_ORDINAL: dict[str, int] = {"1P": 1, "2P": 2, "3P": 3}
_ORDINAL_TO_PAGO_FRACCIONADO: dict[int, str] = {
    ordinal: code for code, ordinal in _PAGO_FRACCIONADO_PERIOD_ORDINAL.items()
}


def apply_period_offset(offset: int, *, target_period: str) -> tuple[int, str]:
    """Apply an integer period offset to a target period code.

    Returns ``(year_delta, derived_period)`` where ``year_delta`` is the
    number of calendar years by which the derived period precedes or follows
    the target year (negative = prior year, positive = following year).

    Raises :exc:`RegistryValidationError` when ``target_period`` is not a
    recognised period-code format.
    """
    if target_period in _QUARTERLY_PERIOD_ORDINAL:
        year_delta, zero_based = divmod(_QUARTERLY_PERIOD_ORDINAL[target_period] - 1 + offset, 4)
        return year_delta, _ORDINAL_TO_QUARTERLY[zero_based + 1]
    if target_period in _PAGO_FRACCIONADO_PERIOD_ORDINAL:
        year_delta, zero_based = divmod(_PAGO_FRACCIONADO_PERIOD_ORDINAL[target_period] - 1 + offset, 3)
        return year_delta, _ORDINAL_TO_PAGO_FRACCIONADO[zero_based + 1]
    if len(target_period) == 2 and target_period.isdigit():
        year_delta, zero_based = divmod(int(target_period) - 1 + offset, 12)
        return year_delta, f"{zero_based + 1:02d}"
    raise RegistryValidationError(
        f"source_period_offset_from_target cannot interpret target period {target_period!r}"
    )
