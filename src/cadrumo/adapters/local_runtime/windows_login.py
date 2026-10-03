"""Native login provenance, bounded inventory and exact desktop generation admission."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.login import RuntimeLoginInventory
from ...application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext
from .windows_desktop_logon import WindowsDesktopLogon, current_windows_desktop_logon
from .windows_desktop_observation import WindowsDesktopObservation, windows_desktop_observation
from .windows_login_native import (
    WindowsLogonRecord,
    WindowsTokenIdentity,
    read_windows_logon,
    read_windows_token_identity,
    windows_desktop_sessions,
    windows_logon_ids,
)

_INVENTORY_SECONDS = 2.0


@dataclass(frozen=True)
class WindowsLoginBinding:
    """Trusted, nonportable provenance captured from a retained native process handle."""

    os_owner_id: str
    authentication_id: int
    session_id: int
    desktop_logon_time: int

    @property
    def login_id(self) -> str:
        """Identify this exact token logon and desktop generation without a credential."""
        return f"windows:{self.authentication_id:x}:{self.session_id}:{self.desktop_logon_time}"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Reobserve this exact native login without recapturing a reused session ID."""
        return observe_windows_login(self, credential_facilities=credential_facilities)


def _matches_current_desktop(identity: WindowsTokenIdentity, witness: WindowsDesktopLogon) -> bool:
    return (
        identity.owner == witness.os_owner_id
        and identity.authentication_id == witness.authentication_id
        and identity.session_id == witness.session_id
    )


def _require_logon_time(logon: WindowsLogonRecord) -> None:
    if logon.logon_time is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def _same_desktop(before: WindowsDesktopObservation, after: WindowsDesktopObservation) -> bool:
    """Retain the WTS generation; lock transitions do not create another login."""
    return (
        before.session_id == after.session_id
        and before.os_owner_id == after.os_owner_id
        and before.logon_time == after.logon_time
    )


def capture_windows_login(process_handle: int, *, expected_owner: str) -> WindowsLoginBinding:
    """Admit same-account peers from any session onto the runtime's desktop.

    The retained peer token establishes account ownership. The runtime's
    interactive desktop supplies login lifetime and browser presentation,
    including when a client connects from a noninteractive Session 0.
    """
    if sys.platform != "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    import pywintypes
    import win32api
    import win32security

    try:
        open_token = cast(Callable[[int, int], int], win32security.OpenProcessToken)
        token = open_token(process_handle, 8)
        try:
            identity = read_windows_token_identity(token)
            logon = read_windows_logon(identity.authentication_id)
            if (
                identity.owner != expected_owner
                or logon.owner != identity.owner
                or logon.session != identity.session_id
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            witness = current_windows_desktop_logon()
            desktop_identity = WindowsTokenIdentity(witness.os_owner_id, witness.authentication_id, witness.session_id)
            desktop_logon = read_windows_logon(witness.authentication_id)
            _require_capture_identity(desktop_identity, desktop_logon, expected_owner)
            _require_logon_time(desktop_logon)
            observation = windows_desktop_observation(witness.session_id)
            if observation.os_owner_id != identity.owner:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            verified = windows_desktop_observation(witness.session_id)
            _require_unchanged_capture(token, identity, logon, witness, observation, verified)
            if read_windows_logon(witness.authentication_id) != desktop_logon:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            return WindowsLoginBinding(
                witness.os_owner_id, witness.authentication_id, witness.session_id, observation.logon_time
            )
        finally:
            win32api.CloseHandle(token)
    except (pywintypes.error, KeyError, TypeError, ValueError, OverflowError):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None


def observe_windows_login(binding: WindowsLoginBinding, *, credential_facilities: Availability) -> OsLoginContext:
    """Revalidate logon existence and WTS generation on each authority observation.

    Credential readiness is separately supplied by the owning native-store
    capability. Desktop presence alone never claims that key custody is usable.
    """
    if sys.platform != "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    import pywintypes

    try:
        witness = current_windows_desktop_logon()
        logon = read_windows_logon(binding.authentication_id)
        _require_logon_time(logon)
        observation = windows_desktop_observation(binding.session_id)
        verified = windows_desktop_observation(binding.session_id)
        if (
            not _same_desktop(observation, verified)
            or read_windows_logon(binding.authentication_id) != logon
            or current_windows_desktop_logon() != witness
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        valid = _bound_desktop_is_valid(binding, witness, logon, observation, verified)
        return OsLoginContext(
            login_id=binding.login_id,
            os_owner_id=binding.os_owner_id,
            active=valid,
            locked=not valid or verified.flags == 0,
            unattended=LoginEligibility.ELIGIBLE if valid else LoginEligibility.INELIGIBLE,
            credential_facilities=credential_facilities,
        )
    except (pywintypes.error, RuntimeRefusalError, KeyError, TypeError, ValueError, OverflowError):
        return OsLoginContext(
            login_id=binding.login_id,
            os_owner_id=binding.os_owner_id,
            active=False,
            locked=True,
            unattended=LoginEligibility.UNKNOWN,
            credential_facilities=Availability.UNAVAILABLE,
        )


def windows_login_inventory(*, expected_owner: str) -> RuntimeLoginInventory:
    """Observe owner desktop incarnations without client or manager assumptions.

    Counts and processing time are bounded; individual native calls have no
    cancellable deadline. Unreadable rows never establish complete absence.
    Account lookup may contact the system's trusted domain controllers.
    """
    unknown = RuntimeLoginInventory((), False)
    if sys.platform != "win32" or not 1 <= len(expected_owner) <= 256:
        return unknown
    import pywintypes

    deadline = time.monotonic() + _INVENTORY_SECONDS
    try:
        before = windows_logon_ids()
        desktops_before = windows_desktop_sessions()
        witness = current_windows_desktop_logon()
        if witness.os_owner_id != expected_owner:
            return unknown
        desktop_ids = {session for session, _ in desktops_before}
        # Current-session association cannot prove absence if its own LUID
        # disappeared or was excluded. Unreadable/unsupported other rows also
        # remain incomplete, even when a positive current witness is available.
        collected = _collect_windows_logins(before, expected_owner, desktop_ids, witness, deadline)
        if collected is None:
            return unknown
        logins, complete, current_verified = collected
        if _inventory_bookends_changed(desktops_before, before, witness, deadline):
            return unknown
        return RuntimeLoginInventory(logins, complete and current_verified)
    except (pywintypes.error, RuntimeRefusalError, KeyError, TypeError, ValueError, OverflowError):
        return unknown


def _require_capture_identity(identity: WindowsTokenIdentity, logon: WindowsLogonRecord, expected_owner: str) -> None:
    """Require a desktop-kind peer token and exact native owner/session association."""
    if (
        identity.owner != expected_owner
        or identity.session_id <= 0
        or logon.kind not in (2, 10, 11, 12)
        or logon.session != identity.session_id
        or logon.owner != identity.owner
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)


def _require_unchanged_capture(
    token: int,
    identity: WindowsTokenIdentity,
    logon: WindowsLogonRecord,
    witness: WindowsDesktopLogon,
    observation: WindowsDesktopObservation,
    verified: WindowsDesktopObservation,
) -> None:
    """Recheck native token, logon and desktop bookends in their original order."""
    if (
        not _same_desktop(observation, verified)
        or observation.state not in (0, 4)
        or verified.state not in (0, 4)
        or read_windows_logon(identity.authentication_id) != logon
        or read_windows_token_identity(token) != identity
        or current_windows_desktop_logon() != witness
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def _bound_desktop_is_valid(
    binding: WindowsLoginBinding,
    witness: WindowsDesktopLogon,
    logon: WindowsLogonRecord,
    observation: WindowsDesktopObservation,
    verified: WindowsDesktopObservation,
) -> bool:
    """Keep eligibility tied to the captured logon and desktop generation."""
    return (
        _matches_current_desktop(
            WindowsTokenIdentity(binding.os_owner_id, binding.authentication_id, binding.session_id), witness
        )
        and logon.kind in (2, 10, 11, 12)
        and logon.session == binding.session_id
        and logon.owner == binding.os_owner_id
        and observation.os_owner_id == binding.os_owner_id
        and observation.logon_time == binding.desktop_logon_time
        and observation.state in (0, 4)
        and verified.state in (0, 4)
    )


def _inventory_login_binding(
    authentication_id: int,
    expected_owner: str,
    desktop_ids: set[int],
    witness: WindowsDesktopLogon,
) -> tuple[WindowsLoginBinding | None, bool]:
    """Read one native row; irrelevant owners preserve completeness, ambiguous rows do not."""
    logon = read_windows_logon(authentication_id)
    if logon.owner != expected_owner or logon.kind not in (2, 10, 11, 12) or logon.session == 0:
        return None, True
    if not _matches_current_desktop(WindowsTokenIdentity(logon.owner, authentication_id, logon.session), witness):
        return None, False
    return _inventory_desktop_binding(logon, authentication_id, expected_owner, desktop_ids)


def _collect_windows_logins(
    before: tuple[int, ...],
    expected_owner: str,
    desktop_ids: set[int],
    witness: WindowsDesktopLogon,
    deadline: float,
) -> tuple[tuple[WindowsLoginBinding, ...], bool, bool] | None:
    """Bound row processing and retain incompleteness after every ambiguous native row."""
    import pywintypes

    complete = witness.authentication_id in before
    current_verified = False
    logins: list[WindowsLoginBinding] = []
    for authentication_id in before:
        if time.monotonic() >= deadline:
            return None
        try:
            binding, entry_complete = _inventory_login_binding(authentication_id, expected_owner, desktop_ids, witness)
            complete = complete and entry_complete
            if binding is not None:
                logins.append(binding)
                current_verified = True
        except (pywintypes.error, RuntimeRefusalError, KeyError, TypeError, ValueError, OverflowError):
            complete = False
    return tuple(logins), complete, current_verified


def _inventory_desktop_binding(
    logon: WindowsLogonRecord,
    authentication_id: int,
    expected_owner: str,
    desktop_ids: set[int],
) -> tuple[WindowsLoginBinding | None, bool]:
    """Require correlated WTS bookends before admitting one current desktop incarnation."""
    _require_logon_time(logon)
    try:
        observation = windows_desktop_observation(logon.session)
    except RuntimeRefusalError as error:
        # Naked NOT_FOUND may hide missing native query permission.
        # Exclude only when successful WTS bookends corroborate it.
        if (
            error.__dict__.get("_wts_error_code") == 7022
            and logon.session not in desktop_ids
            and read_windows_logon(authentication_id) == logon
        ):
            return None, False
        raise
    if observation.os_owner_id != expected_owner or observation.state not in (0, 4) or logon.session not in desktop_ids:
        return None, False
    verified = windows_desktop_observation(logon.session)
    if _inventory_desktop_changed(authentication_id, logon, observation, verified):
        return None, False
    return WindowsLoginBinding(expected_owner, authentication_id, logon.session, verified.logon_time), True


def _inventory_desktop_changed(
    authentication_id: int,
    logon: WindowsLogonRecord,
    observation: WindowsDesktopObservation,
    verified: WindowsDesktopObservation,
) -> bool:
    """Reobserve the same native logon before comparing the atomic WTS generation."""
    return (
        read_windows_logon(authentication_id) != logon
        or not _same_desktop(observation, verified)
        or verified.state not in (0, 4)
    )


def _inventory_bookends_changed(
    desktops_before: tuple[tuple[int, int], ...],
    before: tuple[int, ...],
    witness: WindowsDesktopLogon,
    deadline: float,
) -> bool:
    """Recheck complete WTS and LSA inventories, current witness and absolute deadline in order."""
    return (
        windows_desktop_sessions() != desktops_before
        or windows_logon_ids() != before
        or current_windows_desktop_logon() != witness
        or time.monotonic() >= deadline
    )
