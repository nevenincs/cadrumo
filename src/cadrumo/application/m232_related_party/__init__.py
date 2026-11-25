"""Registered operations for the taxpayer's Modelo 232 related-party statements.

The operator states, lists and withdraws the operations of one ejercicio, the
statement that the ejercicio had none, and the turnover the art. 2.3 ground is
tested against. Every write goes through the application's one guarded write
path for those statements, which owns the refusals; this package adds only the
exact-profile operation surface around it and the listing that shows what the
stated records decide.

Consumers import from the defining module; the package initializer exports no
symbols.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
