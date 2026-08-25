"""Real-behavior tests: no provider binds a session against a blank profile identity.

A profile's fiscal id is what every identity guard in this module
ultimately compares against. Cleared, the certificate provider's
credential guard skipped (it has no operator-configured credential) AND
its deferred session comparison admitted (nothing to compare), so one
absent field disarmed both guards on that path.

The fix is narrow - one refusal at the site that chooses the expectation.
The gate deliberately is not. The defect this descends from was not a
misplaced guard but the absence of any proof that a property held for
EVERY provider, and certificate was missed precisely because it took its
own route through the same function. So the sweep below is parametrised
over the whole provider enum: a provider added later, reaching a
different line, is covered by a test that already exists.

A profile still in setup is exempt by design. It may never have recorded
an identity and legitimately needs a session to finish setting up; the
read it performs is what must refuse, and that guard lives with the read.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from ....core import AuthProviderKind
from ....core.config import override_settings
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import (
    bound_test_profile_record,
    replace_test_profile_record,
    seed_test_profile_record,
)
from ....tests.profile_storage_root_fixture import bucket_session_storage_fixture
from ..sessions import AuthProfileIdentityMismatchError, _prepare_clave_auth

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "77777777-7777-4777-8777-777777777777"
_TAX_ID = "12345678Z"
_TAX_ID_PATH = "identity.tax_id"


def _register_complete() -> None:
    """Register a schema-complete profile carrying its fiscal id.

    ``UserProfileStatus.ACTIVE`` is now ``ProfileSetupState.COMPLETE`` and the
    operator-chosen label left the record for the capsule, so the label rides
    the seeding call rather than a record field. The property under test --
    a completed profile whose identity is present or blank -- is untouched.
    """
    seed_test_profile_record(
        UserProfileRecord(
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path=_TAX_ID_PATH, value=_TAX_ID),
                UserProfileFact(path="auth.clave_movil_route", value="qr"),
            ),
            setup_state=ProfileSetupState.COMPLETE,
        ),
        label="cleared-identity-operator",
    )


def _register_complete_then_clear_identity() -> None:
    """Reach the proven exploit state: setup complete, with its fiscal id removed.

    Built below the validated edit door deliberately. That door now
    refuses to clear a schema-required field, which is what closed the
    operator-reachable route to this state. These guards exist for the
    case where it is reached some OTHER way, so the fixture has to reach
    it some other way too — driving it through the door would now fail
    at setup and prove nothing about the guards.
    """
    _register_complete()
    with bound_test_profile_record(_BUCKET_ID) as repository:
        record = repository.load(_BUCKET_ID)
    assert record.setup_state is ProfileSetupState.COMPLETE
    cleared = tuple(
        fact.model_copy(update={"value": None}) if fact.path == _TAX_ID_PATH else fact for fact in record.facts
    )
    replace_test_profile_record(record.model_copy(update={"facts": cleared}))
    assert not _stored_tax_id(), "the fixture must actually have cleared the identity"


def _stored_tax_id() -> object | None:
    with bound_test_profile_record(_BUCKET_ID) as repository:
        record = repository.load(_BUCKET_ID)
    return next((fact.value for fact in record.facts if fact.path == _TAX_ID_PATH), None)


@pytest.mark.parametrize("kind", list(AuthProviderKind))
def test_no_provider_binds_a_session_against_a_blank_profile_identity(kind: AuthProviderKind) -> None:
    """Swept across the enum, because the last defect here was a provider nobody swept.

    Cl@ve credentials are supplied so the Cl@ve arms reach the identity
    comparison rather than stopping at an incompleteness refusal - which
    would be a refusal for the wrong reason and would let this pass
    without exercising what it claims to.
    """

    _register_complete_then_clear_identity()
    with (
        override_settings(
            cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID),
            cadrumo_clave_permanente_dni_nie=SecretStr(_TAX_ID),
        ) as settings,
        pytest.raises(AuthProfileIdentityMismatchError),
    ):
        _prepare_clave_auth(settings, kind)


def test_a_profile_still_in_setup_may_still_authenticate() -> None:
    """The exemption is deliberate, so it is pinned rather than left implicit.

    Setup mints a profile before its fiscal id is recorded and needs a
    session to complete. Refusing here would break that flow; the live
    read performed against such a session is what has to refuse.
    """

    seed_test_profile_record(
        UserProfileRecord(
            profile_id=_BUCKET_ID,
            facts=(),
            setup_state=ProfileSetupState.INCOMPLETE,
        ),
        label="mid-setup",
    )
    with override_settings() as settings:
        _bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CERTIFICATE)

    assert expected_identity is None


def test_a_recorded_identity_is_unaffected() -> None:
    """The control. A refusal that fired on every profile would pass the sweep."""

    _register_complete()
    with override_settings() as settings:
        _bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CERTIFICATE)

    assert expected_identity == _TAX_ID


_isolated_backend = bucket_session_storage_fixture(_BUCKET_ID)
