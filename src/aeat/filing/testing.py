"""Public test-double helpers for :mod:`aeat.filing`.

This module exposes the synthetic Modelo 130 casilla schema and a
small profile / deadline-checker pair so that downstream tests can
exercise :func:`aeat.filing.build_draft` end-to-end without
reaching into private builder internals. These helpers are
intentionally test-grade — they will be replaced once the real
casilla DB (#23), modelo catalogue (#6), and deadline engine
(#38) land on ``main``.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from ._builders._modelo_130_schema import (
    MODELO_130_SCHEMA,
    StaticCasillaCollection,
    StaticCasillaSchema,
    StaticCasillaSchemaProvider,
    default_schema_provider,
)


class SyntheticProfile(BaseModel):
    """A frozen :class:`aeat.filing.FilingProfile`-conforming record."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    tax_id: str
    display_name: str
    applicable_modelos: tuple[str, ...]


class SyntheticDeadlineStatus(BaseModel):
    """A frozen :class:`aeat.filing.DeadlineStatus`-conforming record."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    due_date: date
    is_overdue: bool


class SyntheticDeadlineChecker(BaseModel):
    """A frozen :class:`aeat.filing.DeadlineChecker`-conforming record.

    The checker returns the same :class:`SyntheticDeadlineStatus`
    for every ``(modelo, period)`` query, which keeps tests
    deterministic.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    status: SyntheticDeadlineStatus

    def check(self, modelo: str, period: str) -> SyntheticDeadlineStatus:
        """Return the configured :class:`SyntheticDeadlineStatus`."""
        del modelo, period
        return self.status


__all__ = [
    "MODELO_130_SCHEMA",
    "StaticCasillaCollection",
    "StaticCasillaSchema",
    "StaticCasillaSchemaProvider",
    "SyntheticDeadlineChecker",
    "SyntheticDeadlineStatus",
    "SyntheticProfile",
    "default_schema_provider",
]
