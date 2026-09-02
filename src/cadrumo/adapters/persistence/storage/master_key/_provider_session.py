"""Shared provider-owned bucket-session teardown."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from .active_session import close_active_bucket_session, current_active_bucket_session

if TYPE_CHECKING:
    import types
    from contextlib import AbstractContextManager

    from .bucket_session import BucketSession


class ProviderSessionOwner(Protocol):
    """Provider state required by :func:`exit_provider_session`."""

    activation_cm: AbstractContextManager[None] | None
    session: BucketSession | None


def exit_provider_session(
    provider: ProviderSessionOwner,
    exc_type: type[BaseException] | None,
    exc: BaseException | None,
    tb: types.TracebackType | None,
) -> None:
    """Close the exact provider-owned session before restoring its prior binding.

    Bookkeeping is detached before cleanup so repeated or reentrant exits are
    no-ops. If another boundary already replaced the active binding, only the
    captured session is closed; a different current session is never evicted.
    """
    activation = provider.activation_cm
    session = provider.session
    provider.activation_cm = None
    provider.session = None
    try:
        if session is not None:
            if current_active_bucket_session() is session:
                close_active_bucket_session()
            else:
                session.close()
    finally:
        if activation is not None:
            activation.__exit__(exc_type, exc, tb)


__all__ = ["ProviderSessionOwner", "exit_provider_session"]
