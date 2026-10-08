"""Shared credential-store probe for cases that cannot run without one.

Call :func:`require_os_credential_store` as the first statement of a case, or
of the fixture that builds its subject, when that subject is unreachable while
the OS credential store refuses. It is deliberately NOT wired as an autouse
fixture over the ``os_keychain`` marker: the marker says a case needs custody
to reach its subject, not that it cannot run at all, and on a store-refusing
host several marked cases still pass by asserting the refusal path. A blanket
marker-keyed skip measured here turned 33 reds into 41 skips, discarding six
live assertions and silencing one failure that was NOT the store. Per-case
invocation keeps that from happening.

The capability is a property of the LOGON SESSION, not of the dependency set.
A headless CI runner and an agent's SSH network logon both select a real
backend that then refuses every credential call, so no keychain-custodied
secret can exist there at all and no code change closes the resulting red.
Such a case is therefore skipped, under a warning that says it was not
verified -- a red there names nothing the reader can repair, and trains them
to discount this lane's failures.

The probe stands BELOW Cadrumo: it drives ``keyring`` directly, under its own
service name and a synthetic value it deletes again, so a refusal it reports is
a property of the host rather than of anything this repository wrote. That is
the whole licence for the skip. The verdict is taken before the case runs and
never from an exception the case itself raised, so a custody regression on a
host whose store answers still fails loudly. It is also what separates this
from pinning a null or file backend, which would leave the mint asserting
nothing about the writer it names.
"""

from __future__ import annotations

import warnings
from contextlib import suppress
from functools import lru_cache
from secrets import token_urlsafe
from uuid import uuid4

import keyring
import keyring.errors
import pytest

_PROBE_SERVICE = "cadrumo-credential-store-probe"

__all__ = ["OsCredentialStoreRefusedWarning", "os_credential_store_refusal", "require_os_credential_store"]


class OsCredentialStoreRefusedWarning(pytest.PytestWarning):
    """Announces a case skipped, unverified, because this logon session's credential store refused."""


@lru_cache(maxsize=1)
def os_credential_store_refusal() -> str | None:
    """Report why this logon session cannot custody a secret, or ``None`` if it can.

    Cached for the lifetime of the worker: the answer is a property of the
    logon session, and a write/read/delete round trip per test would cost more
    than it proves.
    """
    try:
        backend = keyring.get_keyring()
        priority = float(getattr(backend, "priority", 0))
    except Exception as exc:
        return f"the OS credential store backend cannot be inspected: {exc}"
    if priority <= 0:
        return f"no usable OS credential store is configured (selected backend {backend})"

    account = f"probe:{uuid4()}"
    probe_value = token_urlsafe(16)
    try:
        keyring.set_password(_PROBE_SERVICE, account, probe_value)
    except Exception as exc:
        return f"{backend} refused a synthetic probe write: {exc}"
    try:
        stored = keyring.get_password(_PROBE_SERVICE, account)
    except Exception as exc:
        return f"{backend} refused a synthetic probe read: {exc}"
    finally:
        # The probe's own cleanup, and only the store refusing to delete is
        # tolerable here: a backend that cannot remove one synthetic entry has
        # already answered the question this probe asks, and the read above
        # carries the verdict. Anything else is a defect in this hook.
        with suppress(keyring.errors.KeyringError, OSError):
            keyring.delete_password(_PROBE_SERVICE, account)
    if stored != probe_value:
        return f"{backend} accepted a synthetic probe write but its read-back disagreed"
    return None


def require_os_credential_store() -> None:
    """Skip THIS case, under a warning, on a measured refusal naming what the host refused.

    ``mint_profile_session`` has no file-store fallback: the persisted receipt
    is split knowledge whose on-disk half is written only once the store has
    taken the session key, and native automation custody has no fallback
    either. A case whose subject needs a stored secret that EXISTS cannot reach
    it in a refusing logon session, so it must not run there.

    The skip is never silent. The warning reaches the run's warnings summary
    and the skip reason its short summary, both naming the measured refusal, so
    a green run on such a host reads as unverified rather than as coverage.
    """
    refusal = os_credential_store_refusal()
    if refusal is None:
        return
    reason = f"the OS credential store refuses this logon session, so this case was NOT verified: {refusal}"
    warnings.warn(reason, OsCredentialStoreRefusedWarning, stacklevel=2)
    pytest.skip(reason)
