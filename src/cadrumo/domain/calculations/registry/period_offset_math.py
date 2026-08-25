"""Period-offset arithmetic shared by previous-filing and relation binding helpers.

Supports quarterly (``1T``..``4T``), pago-fraccionado (``1P``..``3P``), and
zero-padded monthly (``01``..``12``) period codes.  Offsets wrap across
calendar-year boundaries and return the derived period plus the relative year
delta.

See Also:
    :mod:`cadrumo.domain.calculations.registry.bindings_previous_filing`
        Previous-filing selectors that derive target-relative source period
        anchors.
    :mod:`cadrumo.domain.calculations.registry.relations`
        Relation source requirements that use the same offset arithmetic.
"""

from __future__ import annotations

from .errors import RegistryValidationError

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
    the target year (negative = prior year, positive = following year). The
    tuple is consumed by previous-filing and
    :class:`~cadrumo.domain.calculations.registry.RelationDefinition`
    ``source_period_offset_from_target`` resolution.

    Raises:
        :exc:`~cadrumo.domain.calculations.registry.RegistryValidationError`: When
        ``target_period`` is not a recognised period-code format.
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
    raise RegistryValidationError(f"source_period_offset_from_target cannot interpret target period {target_period!r}")


def same_ejercicio_prior_quarter_anchors(target_period: str) -> tuple[tuple[int, str], ...]:
    """Return the same-ejercicio quarters strictly preceding ``target_period``.

    The Modelo 130 cumulative carry needs every prior quarter from the current
    ejercicio: ``1T`` has none, while ``2T`` through ``4T`` have ``1T``;
    ``1T, 2T``; and ``1T, 2T, 3T`` respectively.  Derive that sequence by
    repeatedly applying the canonical offset authority, stopping precisely at
    the prior-year boundary.  The returned anchors therefore always carry a
    zero year delta and are ordered from earliest to latest prior quarter.

    Raises:
        RegistryValidationError: When ``target_period`` is not a quarterly
            registry token.
    """
    if target_period not in _QUARTERLY_PERIOD_ORDINAL:
        raise RegistryValidationError(
            "same-ejercicio prior-quarter sequence cannot interpret target period "
            f"{target_period!r}; only quarterly codes 1T..4T are supported",
        )

    anchors: list[tuple[int, str]] = []
    offset = -1
    while True:
        year_delta, prior_period = apply_period_offset(offset, target_period=target_period)
        if year_delta != 0:
            break
        anchors.append((year_delta, prior_period))
        offset -= 1
    return tuple(reversed(anchors))
