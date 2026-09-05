"""The bounded recovery-enrollment channel `config profile create` requires.

Creation never publishes a password-only profile. The verb hands the recovery
mnemonic over exactly once and requires the exact phrase back as proof of
possession before the registration transaction publishes. At a terminal the
operator reads the phrase and types it back; on a host with no controlling
terminal the same exchange runs over two explicit descriptors, a writable
handoff and a readable verification.

Playing the operator's part is a relay: read the one bounded document the verb
writes, hand the identical document back. It has to run on its own thread
because the verb writes the handoff and then BLOCKS reading the verification
within one call, so a caller that tried both in sequence on one thread would
deadlock against itself.

This module is stdlib-only and knows nothing about how the verb is reached. An
in-process caller passes the yielded descriptors straight to the command; a
caller that spawns the CLI as a child process has them inherited. Both need the
same two pipes and the same relay.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from typing import Final

_HANDOFF_CHUNK: Final[int] = 4096
_RELAY_JOIN_SECONDS: Final[float] = 5.0


def _relay_the_mnemonic(handoff_read: int, verification_write: int) -> None:
    """Read the handed-out mnemonic and return it as the possession proof.

    Both directions carry the same ``{"recovery_mnemonic": ...}`` document, so
    the operator's part is an echo. Neither side depends on end-of-file: the
    document is newline-framed, and reading stops at the frame.
    """
    payload = bytearray()
    while not payload.endswith(b"\n"):
        chunk = os.read(handoff_read, _HANDOFF_CHUNK)
        if not chunk:
            break
        payload.extend(chunk)
    with suppress(OSError):
        os.write(verification_write, bytes(payload))
    with suppress(OSError):
        os.close(verification_write)


@contextmanager
def scripted_registration_descriptors() -> Iterator[tuple[int, int]]:
    """Yield the ``(handoff_write, verification_read)`` descriptors for one creation.

    The two yielded descriptors are the verb's ends of the exchange. The
    relay's own ends stay here and are released only once the relay has
    stopped, so no descriptor is ever closed underneath a blocked reader.
    Closing the verb's ends first is what releases that reader when the verb
    refused before writing anything at all.
    """
    handoff_read, handoff_write = os.pipe()
    verification_read, verification_write = os.pipe()
    relay = threading.Thread(
        target=_relay_the_mnemonic,
        args=(handoff_read, verification_write),
        daemon=True,
    )
    relay.start()
    try:
        yield handoff_write, verification_read
    finally:
        for descriptor in (handoff_write, verification_read):
            with suppress(OSError):
                os.close(descriptor)
        relay.join(timeout=_RELAY_JOIN_SECONDS)
        for descriptor in (handoff_read, verification_write):
            with suppress(OSError):
                os.close(descriptor)


__all__ = ["scripted_registration_descriptors"]
