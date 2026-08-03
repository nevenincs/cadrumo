"""Real-behavior tests: the tax-id/DNI match is an auth-time rule, not a write-time one.

``auth.dni_nie`` and ``identity.tax_id`` carry the same identifier on
every profile the shipped paths accept, and the schema says so. What the
schema does NOT say -- and what nothing else recorded until this module
-- is WHERE that agreement is enforced. It is enforced once, at the entry
to a live session, by the comparison in
:mod:`application.auth._sessions`. No validator refuses the divergent
write, so a profile carrying two different identifiers can be created,
persisted, and read back; it simply cannot authenticate.

That distinction is worth pinning for two reasons. It is the premise
behind keeping the two fields separate rather than deriving one from the
other: derive them and the divergence refusal becomes unreachable, which
would look like the guard passing rather than the guard being gone. And
it bounds what the refusal protects -- everything upstream of a session
(the manager, exports, calculations) reads whichever field it names and
will not notice the disagreement, so a reader must not assume the two
have been reconciled merely because they are stored.

The write below goes through :func:`set_active_field`, the validated
edit door, deliberately. A fixture that wrote the fact underneath the
door would prove only that the storage layer is untyped; driving the
real door is what shows no validator refuses this.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core import AuthProviderKind
from ....core.config import override_settings
from ....domain.user_profile import UserProfileFact
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...user_profile import (
    ProfileRepository,
    profile_create_storage_span,
    record_to_path_values,
    set_active_field,
)
from ...workflow import workflow_state_repository
from .._sessions import AuthProfileIdentityMismatchError, _prepare_clave_auth

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "5a5a5a5a-5a5a-4a5a-8a5a-5a5a5a5a5a5a"
_PROFILE_LABEL = "divergence-operator"
_TAX_ID = "12345678Z"
_OTHER_TAX_ID = "00000001R"
_TAX_ID_PATH = "identity.tax_id"
_DNI_NIE_PATH = "auth.dni_nie"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_BUCKET_ID),
    ):
        yield


def _register_with_tax_id() -> None:
    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id=_BUCKET_ID,
            display_name=_PROFILE_LABEL,
            overrides={_TAX_ID_PATH: _TAX_ID},
        ),
    )


def _write_dni_nie(value: str) -> None:
    """Set ``auth.dni_nie`` through the validated edit door."""
    workflow_state_repository().update(
        lambda state: set_active_field(state, UserProfileFact(path=_DNI_NIE_PATH, value=value)),
    )


def _stored() -> dict[str, str | None]:
    values = record_to_path_values(ProfileRepository().load(_BUCKET_ID).record)
    return {path: values.get(path) for path in (_TAX_ID_PATH, _DNI_NIE_PATH)}


def test_the_validated_edit_door_accepts_a_dni_that_diverges_from_the_tax_id() -> None:
    """No write-time validator refuses the divergence; both values persist.

    DISCRIMINATING: the assertion is that the write SUCCEEDS and that the
    two stored values are actually different afterwards. Asserting only
    that no exception was raised would also pass if the door had silently
    coerced the new value to match the tax id, which would be a different
    -- and arguably better -- behaviour that this project does not have.
    """

    _register_with_tax_id()
    _write_dni_nie(_OTHER_TAX_ID)

    stored = _stored()
    assert stored[_TAX_ID_PATH] == _TAX_ID
    assert stored[_DNI_NIE_PATH] == _OTHER_TAX_ID
    assert stored[_TAX_ID_PATH] != stored[_DNI_NIE_PATH], (
        "the profile must genuinely hold two different identifiers for the auth-time proof below to mean anything"
    )


@pytest.mark.parametrize("kind", [AuthProviderKind.CLAVE_MOVIL, AuthProviderKind.CLAVE_PERMANENTE])
def test_live_authentication_is_where_the_divergence_is_refused(kind: AuthProviderKind) -> None:
    """The rule has teeth, and they close at session entry rather than at the write.

    Swept over both Cl@ve modes because the comparison once returned
    early for anything but Cl@ve Movil, so a mode-specific pass here
    would reproduce exactly the gap that left two providers unchecked.
    The certificate provider is excluded on purpose: it resolves no
    Cl@ve credentials, so it never reaches this comparison and is
    covered where its own deferred check lives.
    """

    _register_with_tax_id()
    _write_dni_nie(_OTHER_TAX_ID)

    with override_settings() as settings, pytest.raises(AuthProfileIdentityMismatchError) as raised:
        _prepare_clave_auth(settings, kind)
    assert raised.value.translated_message == "application.auth.sessions.errors.clave_identity_profile_mismatch"


@pytest.mark.parametrize("kind", [AuthProviderKind.CLAVE_MOVIL, AuthProviderKind.CLAVE_PERMANENTE])
def test_the_matching_profile_still_authenticates(kind: AuthProviderKind) -> None:
    """The positive control, without which the refusal above proves nothing.

    A guard that refused every profile would satisfy the divergence test
    just as happily. This writes the SAME identifier through the same
    door and asserts the expectation comes back populated, so the
    refusal is shown to key on the divergence rather than on the
    presence of the field.
    """

    _register_with_tax_id()
    _write_dni_nie(_TAX_ID)

    with override_settings() as settings:
        _bound, expected_identity = _prepare_clave_auth(settings, kind)
    assert expected_identity == _TAX_ID
