"""Domain exceptions for the calculations application layer."""

from __future__ import annotations

from ...core.errors import CoreError


class IvaCompensationModeloError(CoreError):
    """Raised when a non-Modelo 303 observation is passed to IVA compensation history.

    The IVA compensation carry-forward pipeline is exclusively sourced from
    Modelo 303 filed observations. Passing any other modelo violates the
    calculation boundary contract.
    """
