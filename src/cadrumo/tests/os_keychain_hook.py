"""Shared credential-store probe for cases that cannot run without one.

Call :func:`require_os_credential_store` as the first statement of a case whose
subject is unreachable when the OS credential store refuses. It is deliberately
NOT wired as an autouse fixture over the ``os_keychain`` marker: the marker says
a case needs custody to reach its subject, not that it cannot run at all, and on
a store-refusing host several marked cases still pass by asserting the refusal
path. A blanket marker-keyed skip measured here turned 33 reds into 41 skips,
discarding six live assertions and silencing one failure that was NOT the store.
Per-case invocation keeps that from happening.

The capability is a property of the LOGON SESSION, not of the dependency set.
A headless CI runner and an agent's SSH network logon both select a real
backend that then refuses every credential call, so no keychain-custodied
session key can exist there at all and no code change closes the resulting red.

The probe stands BELOW Cadrumo: it drives ``keyring`` directly, under its own
service name and a synthetic value it deletes again, so a refusal it reports is
a property of the host rather than of anything this repository wrote. When the
store answers, nothing is skipped and the cases run the real mint, failing
loudly on any regression. That is what separates this from pinning a null or
file backend, which would leave the mint asserting nothing about the writer it
names.
"""

from __future__ import annotations

from contextlib import suppress
from functools import lru_cache
from secrets import token_urlsafe
from uuid import uuid4

import keyring
import pytest

_PROBE_SERVICE = "cadrumo-credential-store-probe"

__all__ = ["os_credential_store_refusal", "require_os_credential_store"]


@lru_cache(maxsize=1)
def os_credential_store_refusal() -> str | None:
    """Report why this host cannot custody a session key, or ``None`` if it can.

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
        with suppress(Exception):
            keyring.delete_password(_PROBE_SERVICE, account)
    if stored != probe_value:
        return f"{backend} accepted a synthetic probe write but its read-back disagreed"
    return None


def require_os_credential_store() -> None:
    """Fail THIS case on a measured refusal, naming what the host refused.

    ``mint_profile_session`` has no file-store fallback: the persisted receipt
    is split knowledge whose on-disk half is written only once the store has
    taken the session key. A case whose subject needs a receipt that EXISTS
    cannot reach it on a refusing host, so the case must not run there -- which
    is exactly what the ``os_keychain`` marker decides, and every lane excludes
    it. Once a lane has explicitly enrolled the marker, an absent prerequisite
    is a red naming the measured reason, never a green skip: the same shape
    ``requires_live_enabled`` uses for the live opt-in. Pinning a null or file
    backend instead would leave the mint asserting nothing about the writer it
    names.
    """
    refusal = os_credential_store_refusal()
    if refusal is not None:
        pytest.fail(f"the OS credential store cannot custody a profile-session key on this host: {refusal}")
