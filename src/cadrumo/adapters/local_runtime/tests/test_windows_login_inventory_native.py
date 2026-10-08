"""Selected read-only LSA/WTS acceptance in a normal limited desktop logon.

Reuse ``CADRUMO_TEST_WINDOWS_CREDENTIAL_MANAGER_EXPECTATION=protected`` and
its existing native desktop guard; no credential-store calls are made. A
requested but unavailable facility fails. Unique nonsecret evidence survives
both passing and failing cases under the repository's ``.tmp`` directory.

Native LSA/WTS calls cannot be cancelled by the processing-time checks. Root's
owning native launcher must retain its independent process timeout. No desktop
lock, disconnect, logout, permission change or credential enumeration occurs.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.test_windows_automation_secret_store_native import (
    require_selected_normal_desktop,
)
from cadrumo.application.runtime.contracts import RuntimeRefusalError
from cadrumo.application.runtime.login import RuntimeLoginInventory
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility, OsLockState

from ..windows_desktop_observation import windows_desktop_observation
from ..windows_login import WindowsLoginBinding, capture_windows_login, windows_login_inventory
from ..windows_login_native import read_windows_logon, windows_desktop_sessions, windows_logon_ids

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.serial,
]

_PROCESSING_SECONDS = 8.0


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _native_error_number(error: BaseException) -> int | None:
    value = error.args[0] if error.args else None
    return value if type(value) is int else None


@contextmanager
def _evidence(kind: str) -> Iterator[dict[str, object]]:
    facts: dict[str, object] = {"passed": False}
    artifact = (
        Path(__file__).resolve().parents[5]
        / ".tmp"
        / ("mcp-windows-login-inventory-native-" + kind + "-" + uuid4().hex + ".json")
    )
    primary: BaseException | None = None
    try:
        yield facts
        facts["passed"] = True
    except BaseException as error:
        primary = error
        facts["failure_type_digest"] = _digest(type(error).__module__ + "." + type(error).__qualname__)
        facts["failure_native_error_number"] = _native_error_number(error)
        raise
    finally:
        try:
            artifact.parent.mkdir(exist_ok=True)
            with artifact.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(facts, indent=2) + "\n")
        except OSError:
            if primary is None:
                raise
            primary.add_note("Nonsecret native login evidence could not be retained")


def _current_binding(facts: dict[str, object]) -> WindowsLoginBinding:
    import win32api
    import win32security

    process = win32api.GetCurrentProcess()
    token = win32security.OpenProcessToken(process, 8)
    try:
        sid, _attributes = win32security.GetTokenInformation(token, win32security.TokenUser)
        owner = win32security.ConvertSidToStringSid(sid)
        statistics = win32security.GetTokenInformation(token, win32security.TokenStatistics)
        authentication_id = int(statistics["AuthenticationId"])
        session_id = int(win32security.GetTokenInformation(token, win32security.TokenSessionId))
        facts["pre_capture_stage"] = "lsa_metadata"
        actual_logon = read_windows_logon(authentication_id)
        facts["pre_capture_logon_kind"] = actual_logon.kind
        facts["pre_capture_lsa_owner_matches_token"] = actual_logon.owner == owner
        facts["pre_capture_lsa_session_matches_token"] = actual_logon.session == session_id
        facts["pre_capture_lsa_time_present"] = actual_logon.logon_time is not None
        facts["pre_capture_stage"] = "wts_metadata"
        desktop = windows_desktop_observation(session_id)
        facts["pre_capture_wts_owner_matches_token"] = desktop.os_owner_id == owner
        facts["pre_capture_wts_session_matches_token"] = desktop.session_id == session_id
        facts["pre_capture_lsa_wts_owner_equal"] = actual_logon.owner == desktop.os_owner_id
        facts["pre_capture_lsa_wts_session_equal"] = actual_logon.session == desktop.session_id
        facts["pre_capture_wts_time_present"] = desktop.logon_time > 0
        facts["pre_capture_wts_state"] = desktop.state
        facts["pre_capture_wts_flags"] = desktop.flags
        facts["pre_capture_lsa_minus_wts_microseconds"] = None
        facts["pre_capture_lsa_wts_time_equal"] = None
        if actual_logon.logon_time is not None:
            try:
                desktop_time = datetime(1601, 1, 1, tzinfo=UTC) + timedelta(microseconds=desktop.logon_time // 10)
            except OverflowError:
                facts["pre_capture_lsa_wts_time_equal"] = None
            else:
                difference = actual_logon.logon_time - desktop_time
                facts["pre_capture_lsa_minus_wts_microseconds"] = (
                    difference.days * 86_400_000_000 + difference.seconds * 1_000_000 + difference.microseconds
                )
                facts["pre_capture_lsa_wts_time_equal"] = actual_logon.logon_time == desktop_time
        facts["pre_capture_stage"] = "canonical_capture"
        binding = capture_windows_login(process, expected_owner=owner)
        facts["owner_digest"] = _digest(owner)
        facts["originating_login_digest"] = _digest(binding.login_id)
        facts["token_owner_matches"] = binding.os_owner_id == owner
        facts["token_authentication_matches"] = binding.authentication_id == authentication_id
        facts["token_session_matches"] = binding.session_id == session_id
        assert binding.os_owner_id == owner
        assert binding.authentication_id == authentication_id
        assert binding.session_id == session_id and session_id > 0
        return binding
    finally:
        win32api.CloseHandle(token)


def _inventory_with_bookends(binding: WindowsLoginBinding, facts: dict[str, object]) -> RuntimeLoginInventory:
    started = time.monotonic()
    luids_before = windows_logon_ids()
    desktops_before = windows_desktop_sessions()
    inventory = windows_login_inventory(expected_owner=binding.os_owner_id)
    desktops_after = windows_desktop_sessions()
    luids_after = windows_logon_ids()
    facts["lsa_count_before"] = len(luids_before)
    facts["lsa_count_after"] = len(luids_after)
    facts["wts_count_before"] = len(desktops_before)
    facts["wts_count_after"] = len(desktops_after)
    facts["lsa_bookends_equal"] = luids_before == luids_after
    facts["wts_bookends_equal"] = desktops_before == desktops_after
    facts["processing_bound_observed"] = time.monotonic() - started < _PROCESSING_SECONDS
    facts["inventory_complete"] = inventory.complete
    facts["inventory_login_count"] = len(inventory.logins)
    facts["current_originating_binding_present"] = binding in inventory.logins
    facts["originating_luid_enumerated"] = binding.authentication_id in luids_before
    facts["originating_desktop_enumerated"] = any(session == binding.session_id for session, _state in desktops_before)
    assert luids_before == luids_after, "native LSA inventory changed during observation"
    assert desktops_before == desktops_after, "native WTS inventory changed during observation"
    assert facts["processing_bound_observed"], "native inventory exceeded its processing observation budget"
    assert binding.authentication_id in luids_before
    assert any(session == binding.session_id for session, _state in desktops_before)
    for login in inventory.logins:
        assert isinstance(login, WindowsLoginBinding)
        assert login.os_owner_id == binding.os_owner_id
    return inventory


def _record_metadata_readability(facts: dict[str, object]) -> None:
    """Retain numeric native failures only; discard each actual metadata row."""
    import pywintypes

    deadline = time.monotonic() + 2.0
    identifiers = windows_logon_ids()
    read_count = 0
    failure_count = 0
    errors: list[int] = []
    for identifier in identifiers:
        if time.monotonic() >= deadline:
            break
        read_count += 1
        try:
            read_windows_logon(identifier)
        except (pywintypes.error, RuntimeRefusalError, KeyError, TypeError, ValueError, OverflowError) as error:
            failure_count += 1
            number = _native_error_number(error)
            if number is not None:
                errors.append(number)
    facts["metadata_luid_count"] = len(identifiers)
    facts["metadata_read_count"] = read_count
    facts["metadata_failure_count"] = failure_count
    facts["metadata_scan_complete"] = read_count == len(identifiers)
    facts["metadata_native_error_numbers"] = errors


def test_normal_desktop_current_login_is_a_fresh_inventory_witness() -> None:
    with _evidence("current") as facts:
        require_selected_normal_desktop()
        facts["normal_limited_desktop_verified"] = True
        binding = _current_binding(facts)
        inventory = _inventory_with_bookends(binding, facts)
        assert binding in inventory.logins, "actual originating desktop login missing from trusted inventory"
        assert inventory.eligibility is LoginEligibility.ELIGIBLE
        before = binding.observe(credential_facilities=Availability.UNAVAILABLE)
        after = binding.observe(credential_facilities=Availability.UNAVAILABLE)
        facts["own_login_active_bookends"] = before.active and after.active
        facts["own_login_eligible_bookends"] = before.unattended is after.unattended is LoginEligibility.ELIGIBLE
        facts["own_generation_unchanged"] = before.login_id == after.login_id == binding.login_id
        assert before.active and after.active
        assert before.unattended is after.unattended is LoginEligibility.ELIGIBLE
        assert before.login_id == after.login_id == binding.login_id
        assert before.credential_facilities is after.credential_facilities is Availability.UNAVAILABLE

        altered = replace(binding, desktop_logon_time=binding.desktop_logon_time + 1)
        refused = altered.observe(credential_facilities=Availability.UNAVAILABLE)
        facts["altered_generation_refused"] = (
            not refused.active
            and refused.lock_state is OsLockState.UNKNOWN
            and refused.unattended is LoginEligibility.INELIGIBLE
        )
        facts["altered_binding_not_recaptured"] = refused.login_id == altered.login_id != binding.login_id
        assert not refused.active and refused.lock_state is OsLockState.UNKNOWN
        assert refused.unattended is LoginEligibility.INELIGIBLE
        assert refused.login_id == altered.login_id != binding.login_id


def test_normal_limited_desktop_inventory_is_complete_at_stable_native_bookends() -> None:
    with _evidence("complete") as facts:
        require_selected_normal_desktop()
        facts["normal_limited_desktop_verified"] = True
        binding = _current_binding(facts)
        _record_metadata_readability(facts)
        inventory = _inventory_with_bookends(binding, facts)
        assert binding in inventory.logins
        assert inventory.eligibility is LoginEligibility.ELIGIBLE
        assert inventory.complete, "limited-token native inventory has unreadable or uncorrelated rows"
