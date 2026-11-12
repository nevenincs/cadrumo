"""Shared support for Modelo 100 registry tests."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Final

from ..binding_value_contract import BindingValueChannel
from ..ids import BindingId
from ..schema import BindingDefinition

#: M100's maternity binding for a scenario with no descendants, in every edition
#: that computes casilla 0611 through that binding. With no
#: hijos ``compute_deduccion_maternidad_0611([], ...)`` is provably zero whatever
#: the registry's dated operands say, so the binding is the literal and needs no
#: authority at import time. This module is the one home of the binding identity.
M100_NO_DESCENDANT_MATERNIDAD_BINDINGS: Final = MappingProxyType(
    {"renta-profile-deduccion-maternidad": Decimal(0)},
)

#: M100's negative savings balances pending from the four previous ejercicios (Ley
#: 35/2006 art. 49.2), each stated as nothing pending, for a scenario that does not
#: exercise their compensation: net capital income and net gains and losses, by origin year.
M100_NO_PENDING_SAVINGS_BALANCES: Final = MappingProxyType(
    {
        f"renta-saldo-negativo-{kind}-ahorro-{origin}-pendiente-inicio": Decimal(0)
        for kind in ("gyp", "rcm")
        for origin in ("em4", "em3", "em2", "em1")
    },
)

M100_NO_MARITIME_WORKER_BINDINGS: Final = MappingProxyType(
    {
        "renta-maritime-gross-navigation-income": Decimal(0),
        "renta-maritime-annual-salary": Decimal(0),
        "renta-maritime-qualifying-days": Decimal(0),
    },
)
"""The art. 7.p) LIRPF and art. 75 Ley 19/1994 operands of a filer with no maritime work.

Every supported edition computes the maritime exemption, so a scenario of an
unrelated chain states these as neutral zeros together with the path below."""

M100_NO_MARITIME_WORKER_BOOLEAN_BINDINGS: Final = MappingProxyType({"renta-maritime-path-rebeca": False})
"""The REBECA path flag of a filer with no maritime work."""


def neutral_binding_values(
    bindings: Iterable[BindingDefinition],
) -> tuple[dict[BindingId, Decimal], dict[BindingId, bool], dict[BindingId, date], dict[BindingId, str]]:
    """Neutral decimal, boolean, date and enum values for the scalar bindings given.

    An individual Madrid filer with no other income, family or carry-forward is
    the neutral profile; the caller drops bindings that arrive through another
    channel and sets any binding whose neutral value differs.
    """
    decimals: dict[BindingId, Decimal] = {}
    booleans: dict[BindingId, bool] = {}
    dates: dict[BindingId, date] = {}
    enums: dict[BindingId, str] = {}
    for binding in bindings:
        channel = binding.value.channel
        if channel in {BindingValueChannel.DECIMAL, BindingValueChannel.INTEGER}:
            decimals[binding.id] = Decimal("0")
        elif channel is BindingValueChannel.BOOLEAN:
            booleans[binding.id] = False
        elif channel is BindingValueChannel.DATE:
            dates[binding.id] = date(1975, 6, 15)
        elif channel is BindingValueChannel.ENUM:
            enums[binding.id] = "madrid"
    return decimals, booleans, dates, enums
