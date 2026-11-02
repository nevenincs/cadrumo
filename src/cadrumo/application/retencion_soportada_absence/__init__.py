"""Registered operations for the operator's suffered-withholding absence attestations.

The operator attests that no payer withheld on one income class in one
ejercicio, or withdraws that attestation. Every write goes through the
application's one guarded write path for attestations, which owns the
refusals; this package adds only the exact-profile operation surface around it.

Consumers import from the defining module; the package initializer exports no
symbols.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
