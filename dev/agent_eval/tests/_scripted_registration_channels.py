"""Bounded machine channels for driving the real profile-creation verb headlessly.

``config profile create`` refuses to discover a passphrase from the environment,
settings, or a keyring, and it refuses to skip recovery enrollment. On a host
with no controlling terminal it therefore needs three explicit channels: a
strict-JSON secrets payload, a descriptor it writes the recovery mnemonic to,
and a descriptor it reads the operator's possession proof back from.

Golden-eval tests that drive the real verb had none of them, so they refused
before any profile work began and never reached the behaviour they exist to
prove. Two evaluation modules were failing that way.

Marking them as requiring an interactive session would have been wrong. Nothing
here needs a terminal or a credential store - only real pipes and a relay that
plays the operator's part, reading the mnemonic the CLI hands out and handing it
straight back as the proof of possession. That is what an operator does at a
prompt, performed by a thread.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress

from cadrumo.core.config import load_settings

_HANDOFF_CHUNK = 4096


def creation_secrets_payload() -> str:
    """Return the strict-JSON creation payload the bounded stdin channel accepts.

    The value is the isolated backend's own seeded passphrase, so anything that
    later reopens the profile in the same runtime unlocks the envelope this
    creation actually minted.
    """
    passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    return json.dumps({"passphrase": passphrase, "passphrase_confirmation": passphrase})


def _relay_the_mnemonic(handoff_read: int, verification_write: int) -> None:
    """Read the handed-out mnemonic and return it as the possession proof.

    Both directions carry the same ``{"recovery_mnemonic": ...}`` document, so
    the operator's part is an echo. It runs on its own thread because the CLI
    writes the handoff and then BLOCKS reading the verification within one
    call - nothing in the invoking thread gets to run in between.
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

    The CLI owns neither end for longer than the call, but it may close what it
    was given, so every close here tolerates a descriptor that is already gone
    rather than turning cleanup into the test's failure.
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
        for descriptor in (handoff_write, handoff_read, verification_read, verification_write):
            with suppress(OSError):
                os.close(descriptor)
        relay.join(timeout=5.0)


def login_secrets_payload() -> str:
    """Return the strict-JSON payload that unlocks a just-created profile.

    Creation mints the custody envelope but leaves the session closed, so
    every verb after it refuses with `You are not logged in`. The passphrase
    is resolvable from no environment, settings entry or keyring, so the
    unlock has to come over the same bounded channel the creation used.
    """
    passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    return json.dumps({"passphrase": passphrase})
