"""Skip ``os_keychain`` cases on a host whose credential store refuses them.

The marker already carries the per-case classification: a test wears it when it
cannot reach its subject without a minted acceleration receipt, because
``resume_profile_session`` leaves the login process-scoped and mints nothing
when the keychain is unavailable. That classification was made per function
rather than per module, so this hook adds no judgement of its own -- it asks
only whether the host can do what those cases already declare they need.

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

__all__ = ["apply", "os_credential_store_refusal"]


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


def apply(node: pytest.Item) -> None:
    """Skip one ``os_keychain`` node when the host's store is measurably shut.

    A node without the marker is left untouched, so this can never silence a
    red outside the set the project itself classified.
    """
    if node.get_closest_marker("os_keychain") is None:
        return
    refusal = os_credential_store_refusal()
    if refusal is not None:
        pytest.skip(f"the OS credential store cannot custody a profile-session key on this host: {refusal}")
