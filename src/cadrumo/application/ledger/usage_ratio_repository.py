"""Explicit lifetime binding for usage-ratio profile persistence."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
from typing import Protocol

from ...domain.usage_ratios.model import UsageRatioProfile


class UsageRatioCensoGuardLoader(Protocol):
    """Load one profile's persisted usage ratios under its censo guard."""

    def __call__(
        self,
        *,
        bucket_id: str,
        raw_afectacion_ratio: Decimal | None,
        year: int,
    ) -> UsageRatioProfile:
        """Return the guarded ratio profile for ``bucket_id`` under ``year``'s rules."""
        ...


class UsageRatioProfileLoader(Protocol):
    """Load one profile's persisted usage ratios."""

    def __call__(self, *, bucket_id: str) -> UsageRatioProfile:
        """Return the persisted ratio profile for ``bucket_id``."""
        ...


class UsageRatioProfileSaver(Protocol):
    """Persist one profile's usage ratios."""

    def __call__(self, profile: UsageRatioProfile, *, bucket_id: str) -> None:
        """Persist ``profile`` for ``bucket_id``."""
        ...


_BOUND_USAGE_RATIO_CENSO_GUARD_LOADER: ContextVar[UsageRatioCensoGuardLoader] = ContextVar(
    "cadrumo_usage_ratio_censo_guard_loader"
)
_BOUND_USAGE_RATIO_PROFILE_PERSISTENCE: ContextVar[tuple[UsageRatioProfileLoader, UsageRatioProfileSaver]] = ContextVar(
    "cadrumo_usage_ratio_profile_persistence"
)


@contextmanager
def bind_usage_ratio_profile_persistence(
    *,
    loader: UsageRatioProfileLoader,
    saver: UsageRatioProfileSaver,
) -> Generator[None]:
    """Bind the load/save pair as one atomic usage-ratio persistence lifetime."""
    token = _BOUND_USAGE_RATIO_PROFILE_PERSISTENCE.set((loader, saver))
    try:
        yield
    finally:
        _BOUND_USAGE_RATIO_PROFILE_PERSISTENCE.reset(token)


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
    year: int,
) -> UsageRatioProfile:
    """Resolve and invoke the composed censo-guarded ratio loader for ``year``."""
    try:
        loader = _BOUND_USAGE_RATIO_CENSO_GUARD_LOADER.get()
    except LookupError as error:
        raise RuntimeError("usage-ratio persistence has not been composed") from error
    return loader(
        bucket_id=bucket_id,
        raw_afectacion_ratio=raw_afectacion_ratio,
        year=year,
    )


def load_usage_ratio_profile(*, bucket_id: str) -> UsageRatioProfile:
    """Load the usage-ratio profile through the explicitly composed authority."""
    try:
        loader, _saver = _BOUND_USAGE_RATIO_PROFILE_PERSISTENCE.get()
    except LookupError as error:
        raise RuntimeError("usage-ratio persistence has not been composed") from error
    return loader(bucket_id=bucket_id)


def save_usage_ratio_profile(profile: UsageRatioProfile, *, bucket_id: str) -> None:
    """Persist the usage-ratio profile through the explicitly composed authority."""
    try:
        _loader, saver = _BOUND_USAGE_RATIO_PROFILE_PERSISTENCE.get()
    except LookupError as error:
        raise RuntimeError("usage-ratio persistence has not been composed") from error
    saver(profile, bucket_id=bucket_id)


__all__ = [
    "UsageRatioCensoGuardLoader",
    "UsageRatioProfileLoader",
    "UsageRatioProfileSaver",
    "bind_usage_ratio_censo_guard_loader",
    "bind_usage_ratio_profile_persistence",
    "load_usage_ratio_profile",
    "save_usage_ratio_profile",
    "usage_ratio_profile_with_censo_guard",
]
