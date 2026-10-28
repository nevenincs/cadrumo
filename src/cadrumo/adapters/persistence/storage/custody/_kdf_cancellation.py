"""Owned nonblocking wakeup descriptors for profile proof cancellation."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from .....application.user_profile.proof_cancellation import ProfileProofCancellation
from ._kdf_codec import close_fd


@contextmanager
def kdf_cancellation_pipe(cancellation: ProfileProofCancellation | None) -> Generator[int | None]:
    """Select cancellation beside producer readiness without a polling thread."""
    if cancellation is None:
        yield None
        return
    reader, writer = os.pipe()
    try:
        os.set_blocking(writer, False)

        def wake() -> None:
            os.write(writer, b"C")

        with cancellation.watch(wake):
            yield reader
    finally:
        # watch joins a callback chosen just before unsubscription, so this
        # cannot close and recycle a descriptor while a callback writes it.
        close_fd(reader)
        close_fd(writer)


__all__ = ["kdf_cancellation_pipe"]
