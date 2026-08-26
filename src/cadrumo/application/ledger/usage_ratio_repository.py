"""Explicit lifetime binding for censo-guarded usage-ratio persistence."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
from typing import Protocol

from ...domain.usage_ratios import UsageRatioProfile


class UsageRatioCensoGuardLoader(Protocol):
    """Load one profile's persisted usage ratios under its censo guard."""

    def __call__(
        self,
        *,
        bucket_id: str,
        raw_afectacion_ratio: Decimal | None,
    ) -> UsageRatioProfile:
        """Return the guarded ratio profile for ``bucket_id``."""
        ...


_BOUND_USAGE_RATIO_CENSO_GUARD_LOADER: ContextVar[UsageRatioCensoGuardLoader] = ContextVar(
    "cadrumo_usage_ratio_censo_guard_loader"
)


@contextmanager
def bind_usage_ratio_censo_guard_loader(
    loader: UsageRatioCensoGuardLoader,
) -> Generator[UsageRatioCensoGuardLoader]:
    """Bind one outward-composed censo-guarded usage-ratio loader."""
    token = _BOUND_USAGE_RATIO_CENSO_GUARD_LOADER.set(loader)
    try:
        yield loader
    finally:
        _BOUND_USAGE_RATIO_CENSO_GUARD_LOADER.reset(token)


def usage_ratio_profile_with_censo_guard(
    *,
    bucket_id: str,
    raw_afectacion_ratio: Decimal | None,
) -> UsageRatioProfile:
    """Resolve and invoke the composed censo-guarded ratio loader."""
    try:
        loader = _BOUND_USAGE_RATIO_CENSO_GUARD_LOADER.get()
    except LookupError as error:
        raise RuntimeError("usage-ratio persistence has not been composed") from error
    return loader(
        bucket_id=bucket_id,
        raw_afectacion_ratio=raw_afectacion_ratio,
    )


__all__ = [
    "UsageRatioCensoGuardLoader",
    "bind_usage_ratio_censo_guard_loader",
    "usage_ratio_profile_with_censo_guard",
]
