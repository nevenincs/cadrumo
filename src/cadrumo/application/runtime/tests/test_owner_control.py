"""Global stop consent is short-lived, single-use and independent of key custody."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.runtime.contracts import RuntimePeer, RuntimeRefusalError
from cadrumo.application.runtime.owner_control import (
    RuntimeOwnerControl,
    RuntimeStopConfirm,
    RuntimeStopPreviewRequest,
)
from cadrumo.application.runtime.transport import RuntimeConnectionContext
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class ObservedLogin:
    """Explicit native-observation port for policy tests; never profile proof."""

    login_id = "test-login-incarnation"
    active = True
    locked = False
    owner = "test-owner"
    eligibility = LoginEligibility.ELIGIBLE

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        assert credential_facilities is Availability.NOT_REQUIRED
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=self.owner,
            active=self.active,
            locked=self.locked,
            unattended=self.eligibility,
            credential_facilities=credential_facilities,
        )


def _context() -> RuntimeConnectionContext:
    return RuntimeConnectionContext(uuid4(), uuid4(), RuntimePeer(os_owner_id="test-owner", process_id=42))


def test_stop_requires_exact_explicit_single_use_consent_and_claims_only_acceptance() -> None:
    context = _context()
    control = RuntimeOwnerControl(context, login=ObservedLogin())
    now = datetime.now(UTC)
    preview = control.preview(RuntimeStopPreviewRequest(request_id=uuid4()), now=now, monotonic_now=10)
    confirm = RuntimeStopConfirm(
        request_id=uuid4(),
        runtime_boot_id=context.runtime_boot_id,
        preview_id=preview.preview_id,
        acknowledge_all_profiles_and_work=True,
    )
    accepted = control.confirm(confirm, now=now + timedelta(seconds=1), monotonic_now=11)
    assert accepted.kind == "runtime_stop_accepted"
    assert accepted.scope == "all_profiles_and_work"
    assert accepted.runtime_boot_id == context.runtime_boot_id
    assert accepted.connection_id == context.connection_id
    with pytest.raises(RuntimeRefusalError):
        control.confirm(confirm, now=now + timedelta(seconds=2), monotonic_now=12)
    with pytest.raises(ValidationError):
        RuntimeStopConfirm.model_validate_json(
            confirm.model_dump_json().replace(
                '"acknowledge_all_profiles_and_work":true', '"acknowledge_all_profiles_and_work":false'
            )
        )


@pytest.mark.parametrize("change", ["locked", "logout", "owner", "login", "unknown"])
def test_stop_reobserves_login_instead_of_reusing_preview_authority(change: str) -> None:
    login = ObservedLogin()
    context = _context()
    control = RuntimeOwnerControl(context, login=login)
    now = datetime.now(UTC)
    preview = control.preview(RuntimeStopPreviewRequest(request_id=uuid4()), now=now, monotonic_now=10)
    if change == "locked":
        login.locked = True
    elif change == "logout":
        login.active = False
    elif change == "owner":
        login.owner = "different-owner"
    elif change == "login":
        login.login_id = "replacement-incarnation"
    else:
        login.eligibility = LoginEligibility.UNKNOWN
    with pytest.raises(RuntimeRefusalError):
        control.confirm(
            RuntimeStopConfirm(
                request_id=uuid4(),
                runtime_boot_id=context.runtime_boot_id,
                preview_id=preview.preview_id,
                acknowledge_all_profiles_and_work=True,
            ),
            now=now + timedelta(seconds=1),
            monotonic_now=11,
        )


@pytest.mark.parametrize("wall,elapsed", [(-1, 1), (60, 1), (1, -1), (1, 60), (1, float("nan"))])
def test_stop_refuses_expiry_and_clock_rollback(wall: int, elapsed: float) -> None:
    context = _context()
    control = RuntimeOwnerControl(context, login=ObservedLogin())
    now = datetime.now(UTC)
    preview = control.preview(RuntimeStopPreviewRequest(request_id=uuid4()), now=now, monotonic_now=10)
    with pytest.raises(RuntimeRefusalError):
        control.confirm(
            RuntimeStopConfirm(
                request_id=uuid4(),
                runtime_boot_id=context.runtime_boot_id,
                preview_id=preview.preview_id,
                acknowledge_all_profiles_and_work=True,
            ),
            now=now + timedelta(seconds=wall),
            monotonic_now=10 + elapsed,
        )


def test_preview_cannot_cross_connections_or_replacement_runtime_boot() -> None:
    context = _context()
    control = RuntimeOwnerControl(context, login=ObservedLogin())
    now = datetime.now(UTC)
    preview = control.preview(RuntimeStopPreviewRequest(request_id=uuid4()), now=now, monotonic_now=10)
    other = RuntimeOwnerControl(
        RuntimeConnectionContext(uuid4(), context.runtime_boot_id, context.peer), login=ObservedLogin()
    )
    other.preview(RuntimeStopPreviewRequest(request_id=uuid4()), now=now, monotonic_now=10)
    confirm = RuntimeStopConfirm(
        request_id=uuid4(),
        runtime_boot_id=context.runtime_boot_id,
        preview_id=preview.preview_id,
        acknowledge_all_profiles_and_work=True,
    )
    with pytest.raises(RuntimeRefusalError):
        other.confirm(confirm, now=now, monotonic_now=11)
    with pytest.raises(RuntimeRefusalError):
        control.confirm(confirm.model_copy(update={"runtime_boot_id": uuid4()}), now=now, monotonic_now=11)


@pytest.mark.parametrize("acknowledgement", ["1", '"true"', "null", "false"])
def test_acknowledgement_requires_a_literal_json_boolean(acknowledgement: str) -> None:
    wire = (
        f'{{"request_id":"{uuid4()}","runtime_boot_id":"{uuid4()}","preview_id":"{uuid4()}",'
        f'"acknowledge_all_profiles_and_work":{acknowledgement}}}'
    )
    with pytest.raises(ValidationError):
        RuntimeStopConfirm.model_validate_json(wire)
