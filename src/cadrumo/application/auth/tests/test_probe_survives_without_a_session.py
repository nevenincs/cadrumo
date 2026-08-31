"""The auth readiness probes do not read the profile without a session.

``probe_provider_configuration`` promises it works "without any network
call or active-profile session" and "never raises"; ``run_preflight_checks``
promises "the aggregate never raises". Those promises lived only in
docstrings until a change made the probes read the active profile, and
the encrypted store refuses without a bucket session: SQLAlchemy wraps
that refusal in a driver exception no domain-level except clause catches,
so ``config check`` emitted an error document instead of a payload and
the operator could not run the doctor until they logged in.

What is asserted here is that the probe DECLINES the read, not merely
that it survives one. "Does not raise" depends on which secret-store
backend the machine has - a file-backed store decrypts happily without a
bucket session, so a test written that way passes on the isolated
backend whether the guard exists or not, and only fails where the
keychain is genuinely locked. Declining the read is the guarantee the
code actually makes, it holds on every backend, and it fails loudly if
the guard is removed.

The condition is built rather than simulated: a real profile is created,
its session span exited, and the active-profile pointer left set - which
is exactly the operator's locked workstation, and exactly what the
isolation helper's default of no pointer would have hidden.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.outbound.storage import windows_worst_case_object_path_suffix_length
from ....adapters.persistence.storage import has_active_bucket_session
from ....core.auth_provider import AuthProviderKind
from ....core.config import override_settings
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...preflight import run_preflight_checks
from ..operator import build_live_auth_preflight_report
from ..operator_probes import (
    _active_profile_path_values,
    live_auth_identity_state,
    probe_clave_credentials,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Measured from the storage adapter's real on-disk grammar, the same value the
#: composition root supplies in production. Reaching for it here keeps these
#: probes exercising the true margin rather than a hand-picked sample.
_SUFFIX_LENGTH = windows_worst_case_object_path_suffix_length()

_BUCKET_ID = "99999999-9999-4999-8999-999999999999"
_TAX_ID = "12345678Z"


def test_the_fixture_leaves_a_readable_profile_and_no_session() -> None:
    """Anti-tautology guard for every case below.

    Two things have to be true or the rest prove nothing: no session is
    bound, and the profile really is there to be read. If the profile
    were absent, a probe that had lost its guard would return empty for
    the wrong reason and every assertion below would still pass.
    """

    assert has_active_bucket_session() is False

    with open_test_profile_session(_BUCKET_ID):
        readable = _active_profile_path_values()

    assert readable.get("identity.tax_id") == _TAX_ID


def test_the_profile_read_is_declined_when_no_session_is_bound() -> None:
    """The guarantee itself: no session means no read is attempted.

    With the guard removed this returns the profile's real values on a
    file-backed store, and raises through SQLAlchemy on a locked
    keychain. Asserting the decline catches both.
    """

    assert _active_profile_path_values() == {}


def test_the_credential_probe_reports_nothing_from_an_unread_profile() -> None:
    """A locked workstation reports no profile-borne credential.

    Not an error and not a guess: the honest answer is that the profile
    could not be consulted, which reads the same as absent.
    """

    with override_settings(cadrumo_clave_movil_dni_nie=None) as settings:
        credentials = probe_clave_credentials(AuthProviderKind.CLAVE_MOVIL, settings=settings)

    assert credentials is not None
    assert credentials.dni_nie == ""


def test_the_identity_state_probe_answers_without_a_session() -> None:
    """The alignment ladder reports a state rather than refusing."""

    with override_settings(cadrumo_clave_movil_dni_nie=None) as settings:
        profile_present, provider_present, alignment = live_auth_identity_state(
            AuthProviderKind.CLAVE_MOVIL,
            settings=settings,
        )

    assert profile_present is False
    assert provider_present is False
    assert alignment


def test_the_preflight_report_builds_without_a_session() -> None:
    """An operator asks whether auth is ready before unlocking anything."""

    report = build_live_auth_preflight_report(AuthProviderKind.CLAVE_MOVIL.value)

    assert report.provider == AuthProviderKind.CLAVE_MOVIL.value


def test_the_preflight_aggregate_returns_rows_without_a_session() -> None:
    """The contract the ``config check`` verb depends on.

    The doctor emitted an error document instead of a payload when this
    broke, which the operator met as a refusal to run at all.
    """

    rows = run_preflight_checks(object_path_suffix_length=_SUFFIX_LENGTH)

    assert rows
    assert any(row.check.startswith("auth") for row in rows), (
        f"no auth row survived the locked-store probe; got {[row.check for row in rows]}"
    )


@pytest.fixture(autouse=True)
def _profile_on_disk_but_nothing_unlocked(tmp_path: Path) -> Iterator[None]:
    """Create a profile, exit its session, and leave the pointer set.

    The pointer matters as much as the absent session. The isolation
    helper defaults ``cadrumo_active_profile`` to ``None``, and with no
    pointer nothing downstream even tries to open the profile, so the
    guard would look unnecessary.
    """

    with isolated_profile_storage_root(tmp_path=tmp_path):
        with open_test_profile_session(_BUCKET_ID):
            register_minimal_profile(
                profile_id=_BUCKET_ID,
                display_name="locked-operator",
                overrides={"identity.tax_id": _TAX_ID, "auth.dni_nie": _TAX_ID},
            )
        with override_settings(cadrumo_active_profile=_BUCKET_ID):
            yield
