"""Shared support for Modelo 100 registry tests."""

from __future__ import annotations

from decimal import Decimal
from types import MappingProxyType
from typing import Final

#: M100 2024's maternity binding for a scenario with no descendants. With no
#: hijos ``compute_deduccion_maternidad_0611([], ...)`` is provably zero whatever
#: the registry's dated operands say, so the binding is the literal and needs no
#: authority at import time. This module is the one home of the binding identity.
M100_2024_EMPTY_MATERNIDAD_BINDINGS: Final = MappingProxyType(
    {"renta-profile-deduccion-maternidad": Decimal(0)},
)
