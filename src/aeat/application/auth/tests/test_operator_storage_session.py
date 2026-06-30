"""Storage-session regression coverage for operator auth services."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage import has_active_bucket_session
from ....application.user_profile._orchestration import profile_create_storage_span, profile_storage_session
from ....application.user_profile._testing import register_minimal_profile
from ....application.wizard import WIZARD_FLOWS
from ....application.workflow._persistence import workflow_state_repository
from ....domain.contribuyente._keys import required_profile_keys
from ....tests.secure_sql import isolated_profile_storage_root
from .._operator import clear_operator_auth, configure_operator_auth

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "11111111-1111-4111-8111-111111111111"


def test_clear_operator_auth_reopens_profile_storage_session_when_pointer_is_active(
    tmp_path: Path,
) -> None:
    """Operator auth clear must work after profile creation closes its storage span.

    The active-profile pointer can remain selected after the per-process
    master-key session is closed. In that production-shaped state,
    workflow-state reads and writes must be performed through the
    operator auth service's own profile storage session.
    """

    with isolated_profile_storage_root(tmp_path=tmp_path):
        assert WIZARD_FLOWS
        assert required_profile_keys()
        with profile_create_storage_span(_PROFILE_ID):
            workflow_state_repository().update(
                lambda state: register_minimal_profile(state, profile_id=_PROFILE_ID)
            )
            configure_operator_auth("certificate")

        assert has_active_bucket_session() is False

        result = clear_operator_auth(provider="certificate")

        assert result.cleared_workflow_state is True
        assert has_active_bucket_session() is False
        with profile_storage_session(_PROFILE_ID):
            state = workflow_state_repository().load()
        assert state.auth.provider is None
