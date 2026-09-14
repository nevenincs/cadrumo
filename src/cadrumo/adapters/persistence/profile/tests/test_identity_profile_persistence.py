"""Encrypted profile persistence proof for auth-identity divergence.

The application auth tests own the identity comparison policy. This one test
owns the separate persistence fact: the validated profile edit door accepts a
divergent DNI/NIE and the two identifiers are genuinely persisted.
"""

from __future__ import annotations

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    replace_test_profile_record,
    seed_test_profile_record,
)
from cadrumo.adapters.persistence.storage.tests.profile_storage_root_fixture import bucket_session_storage_fixture
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "5a5a5a5a-5a5a-4a5a-8a5a-5a5a5a5a5a5a"
_PROFILE_LABEL = "divergence-operator"
_TAX_ID = "12345678Z"
_OTHER_TAX_ID = "00000001R"
_TAX_ID_PATH = "identity.tax_id"
_DNI_NIE_PATH = "auth.dni_nie"

_isolated_backend = bucket_session_storage_fixture(_BUCKET_ID)


def _register_with_tax_id() -> None:
    """Publish the capsule carrying a fiscal id before reading the bucket."""
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path=_TAX_ID_PATH, value=_TAX_ID),
                UserProfileFact(path="auth.clave_movil_route", value="qr"),
            ),
        ),
        label=_PROFILE_LABEL,
    )


def _write_dni_nie(value: str) -> None:
    """Set ``auth.dni_nie`` through the validated edit door."""
    with bound_test_profile_record(_BUCKET_ID) as repository:
        record = repository.load(_BUCKET_ID)
    replace_test_profile_record(
        record.model_copy(
            update={
                "facts": (
                    *(fact for fact in record.facts if fact.path != _DNI_NIE_PATH),
                    UserProfileFact(path=_DNI_NIE_PATH, value=value),
                ),
            },
        ),
    )


def _stored() -> dict[str, str | None]:
    with bound_test_profile_record(_BUCKET_ID) as repository:
        values = record_to_path_values(repository.load(_BUCKET_ID))
    return {path: values.get(path) for path in (_TAX_ID_PATH, _DNI_NIE_PATH)}


def test_the_validated_edit_door_accepts_a_dni_that_diverges_from_the_tax_id() -> None:
    """No write-time validator refuses the divergence; both values persist."""
    _register_with_tax_id()
    _write_dni_nie(_OTHER_TAX_ID)

    stored = _stored()
    assert stored[_TAX_ID_PATH] == _TAX_ID
    assert stored[_DNI_NIE_PATH] == _OTHER_TAX_ID
    assert stored[_TAX_ID_PATH] != stored[_DNI_NIE_PATH]
