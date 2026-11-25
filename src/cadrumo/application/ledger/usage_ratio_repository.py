"""Explicit lifetime binding for usage-ratio profile persistence."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

from ...core.errors.hierarchy import InternalInvariantError

if TYPE_CHECKING:
    from ...core.secure_object_write import SecureObjectWrite
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.usage_ratios.model import UsageRatioProfile


class UsageRatioCensoGuardLoader(Protocol):
    """Load one profile's persisted usage ratios under its censo guard."""

    def __call__(
        self,
        *,
        bucket_id: str,
        raw_afectacion_ratio: Decimal | None,
        year: int,
        operation: PinnedAuthorityOperation,
    ) -> UsageRatioProfile:
        """Return the guarded ratio profile for ``bucket_id`` under ``year``'s rules."""
        ...


class UsageRatioProfileLoader(Protocol):
    """Load one profile's persisted usage ratios."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> UsageRatioProfile:
        """Return the persisted ratio profile for ``bucket_id``."""
        ...


class UsageRatioProfileCoSaver(Protocol):
    """Persist one profile's usage ratios in the same unit of work as other secure objects."""

    def __call__(
        self,
        profile: UsageRatioProfile,
        extra_writes: tuple[SecureObjectWrite, ...],
        *,
        bucket_id: str,
    ) -> None:
        """Atomically persist ``profile`` and ``extra_writes`` for ``bucket_id``."""
        ...


_BOUND_USAGE_RATIO_CENSO_GUARD_LOADER: ContextVar[UsageRatioCensoGuardLoader] = ContextVar(
    "cadrumo_usage_ratio_censo_guard_loader"
)
type _UsageRatioPersistence = tuple[UsageRatioProfileLoader, UsageRatioProfileCoSaver]

_BOUND_USAGE_RATIO_PROFILE_PERSISTENCE: ContextVar[_UsageRatioPersistence] = ContextVar(
    "cadrumo_usage_ratio_profile_persistence"
)


@contextmanager
def bind_usage_ratio_profile_persistence(
    *,
    loader: UsageRatioProfileLoader,
    co_saver: UsageRatioProfileCoSaver,
) -> Generator[None]:
    """Bind the load and co-save pair as one usage-ratio persistence lifetime."""
    token = _BOUND_USAGE_RATIO_PROFILE_PERSISTENCE.set((loader, co_saver))
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
    operation: PinnedAuthorityOperation,
) -> UsageRatioProfile:
    """Resolve and invoke the composed censo-guarded ratio loader for ``year``."""
    try:
        loader = _BOUND_USAGE_RATIO_CENSO_GUARD_LOADER.get()
    except LookupError as error:
        raise InternalInvariantError("usage-ratio persistence has not been composed") from error
    return loader(
        bucket_id=bucket_id,
        raw_afectacion_ratio=raw_afectacion_ratio,
        year=year,
        operation=operation,
    )


def load_usage_ratio_profile(*, bucket_id: str, operation: PinnedAuthorityOperation) -> UsageRatioProfile:
    """Load the usage-ratio profile through the explicitly composed authority."""
    try:
        loader, _co_saver = _BOUND_USAGE_RATIO_PROFILE_PERSISTENCE.get()
    except LookupError as error:
        raise InternalInvariantError("usage-ratio persistence has not been composed") from error
    return loader(bucket_id=bucket_id, operation=operation)


def save_usage_ratio_profile_with_writes(
    profile: UsageRatioProfile,
    extra_writes: tuple[SecureObjectWrite, ...],
    *,
    bucket_id: str,
) -> None:
    """Persist the profile and ``extra_writes`` in one unit of work through the composed authority."""
    try:
        _loader, co_saver = _BOUND_USAGE_RATIO_PROFILE_PERSISTENCE.get()
    except LookupError as error:
        raise InternalInvariantError("usage-ratio persistence has not been composed") from error
    co_saver(profile, extra_writes, bucket_id=bucket_id)


__all__ = [
    "UsageRatioCensoGuardLoader",
    "UsageRatioProfileCoSaver",
    "UsageRatioProfileLoader",
    "bind_usage_ratio_censo_guard_loader",
    "bind_usage_ratio_profile_persistence",
    "load_usage_ratio_profile",
    "save_usage_ratio_profile_with_writes",
    "usage_ratio_profile_with_censo_guard",
]
