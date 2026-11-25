"""Observe inventory and retained login witnesses without changing authority."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock

from cadrumo.application.user_profile.access_contracts import LoginEligibility, OsLockState, OsLoginContext
from cadrumo.core.diagnostic_log import DiagnosticValue
from cadrumo_client.contracts.access_vocabulary import Availability
from cadrumo_client.contracts.login import LoginEvidence, LoginInventory


@dataclass(frozen=True, slots=True)
class LoginInventoryReading:
    """A bounded inventory observation and its elapsed-time evidence."""

    inventory: LoginInventory
    logins: tuple[LoginEvidence, ...]
    observed: tuple[OsLoginContext, ...]
    started: float
    inventory_elapsed_ms: float
    observation_elapsed_ms: float


def read_login_inventory(
    inventory_source: Callable[[], LoginInventory], peers: tuple[LoginEvidence, ...]
) -> LoginInventoryReading:
    """Reobserve inventory and retain each connection's original native witness."""
    started = time.monotonic()
    inventory = inventory_source()
    inventory_elapsed_ms = round((time.monotonic() - started) * 1000, 3)
    logins = {login.login_id: login for login in inventory.logins}
    logins.update((login.login_id, login) for login in peers)
    observation_started = time.monotonic()
    observed = tuple(login.observe(credential_facilities=Availability.UNAVAILABLE) for login in logins.values())
    observation_elapsed_ms = round((time.monotonic() - observation_started) * 1000, 3)
    return LoginInventoryReading(
        inventory, tuple(logins.values()), observed, started, inventory_elapsed_ms, observation_elapsed_ms
    )


def login_witness_loss_fields(
    inventory: LoginInventory,
    peers: tuple[LoginEvidence, ...],
    observed: tuple[OsLoginContext, ...],
    inventory_elapsed_ms: float,
    observation_elapsed_ms: float,
) -> dict[str, DiagnosticValue]:
    """Summarize bounded counts and timings without exposing login identities."""
    return {
        "reason_code": "login_witness_loss",
        "inventory_complete": inventory.complete,
        "inventory_login_count": len(inventory.logins),
        "retained_peer_witness_count": len(peers),
        "observed_active_count": sum(login.active for login in observed),
        "observed_eligible_count": sum(
            login.active and login.unattended is LoginEligibility.ELIGIBLE for login in observed
        ),
        "observed_unknown_count": sum(login.unattended is LoginEligibility.UNKNOWN for login in observed),
        "inventory_elapsed_ms": inventory_elapsed_ms,
        "observation_elapsed_ms": observation_elapsed_ms,
    }


def has_eligible_login(observed: tuple[OsLoginContext, ...]) -> bool:
    """Check whether a live native login is eligible for unattended custody."""
    return any(login.active and login.unattended is LoginEligibility.ELIGIBLE for login in observed)


def has_unreported_login(observed: tuple[OsLoginContext, ...]) -> bool:
    """Check for a lock state that lacks reliable session notifications."""
    return any(login.lock_state in (OsLockState.NOT_APPLICABLE, OsLockState.UNKNOWN) for login in observed)


def has_unknown_login_lock(observed: tuple[OsLoginContext, ...]) -> bool:
    """Check whether any observed native lock state remains unknown."""
    return any(login.lock_state is OsLockState.UNKNOWN for login in observed)


class HeldLogin:
    """One logon as observed when its inventory was taken, observed again only for another credential availability."""

    def __init__(self, evidence: LoginEvidence, observed: OsLoginContext) -> None:
        """Retain the original witness and its first observation."""
        self._evidence = evidence
        self._lock = Lock()
        self._observed = {Availability.UNAVAILABLE: observed}

    @property
    def login_id(self) -> str:
        """Return the original native login identity."""
        return self._evidence.login_id

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Reuse or read the observation for the requested availability."""
        with self._lock:
            held = self._observed.get(credential_facilities)
        if held is None:
            held = self._evidence.observe(credential_facilities=credential_facilities)
            with self._lock:
                self._observed[credential_facilities] = held
        return held


@dataclass(frozen=True, slots=True)
class LoginObservation:
    """One logon observation and what it was taken under: the OS change count, its instant and the held peers."""

    changes: int
    observed_at: float
    peers: frozenset[str]
    logins: tuple[LoginEvidence, ...]
    unknown_lock: bool
