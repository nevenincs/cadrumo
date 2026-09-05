"""Strict-JSON secret payloads for driving the real profile verbs headlessly.

``config profile create`` refuses to discover a passphrase from the
environment, settings, or a keyring. On a host with no controlling terminal it
therefore needs an explicit bounded payload, and every verb after creation
needs a second one to unlock the profile the creation minted.

The recovery-enrollment descriptors the same verb requires are not built here:
they are a channel rather than a payload, and callers that spawn the CLI as a
child process need the identical exchange. They come from
``scripted_registration_descriptors``.
"""

from __future__ import annotations

import json

from cadrumo.core.config import load_settings


def creation_secrets_payload() -> str:
    """Return the strict-JSON creation payload the bounded stdin channel accepts.

    The value is the isolated backend's own seeded passphrase, so anything that
    later reopens the profile in the same runtime unlocks the envelope this
    creation actually minted.
    """
    passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    return json.dumps({"passphrase": passphrase, "passphrase_confirmation": passphrase})


def login_secrets_payload() -> str:
    """Return the strict-JSON payload that unlocks a just-created profile.

    Creation mints the custody envelope but leaves the session closed, so
    every verb after it refuses with `You are not logged in`. The passphrase
    is resolvable from no environment, settings entry or keyring, so the
    unlock has to come over the same bounded channel the creation used.
    """
    passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    return json.dumps({"passphrase": passphrase})
