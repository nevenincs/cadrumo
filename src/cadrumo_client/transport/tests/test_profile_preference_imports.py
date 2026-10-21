"""Reading a language preference must not initialize profile write executors."""

import subprocess
import sys
from textwrap import dedent

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_profile_preference_read_imports_defer_execution_until_mutation_registration() -> None:
    """Use a fresh interpreter so collection cannot hide an eager dependency."""
    completed = subprocess.run(  # noqa: S603 -- fixed probe in the current interpreter; no shell.
        [
            sys.executable,
            "-c",
            dedent(
                """
                import sys
                from cadrumo_client.transport.profile_language import read_profile_language
                from cadrumo_client.transport.profile_mutations import _registration
                from cadrumo.application.user_profile.profile_operation_contracts import (
                    ProfileFieldMutationOperationRequest,
                )

                assert callable(read_profile_language)
                assert 'cadrumo.application.user_profile.operations' not in sys.modules
                assert 'cadrumo.application.user_profile.profile_operation_execution' not in sys.modules
                registration = _registration(ProfileFieldMutationOperationRequest)
                assert registration.contract.definition_id == 'user-profile.field-mutation'
                assert registration.contract.result_schema is not None
                assert 'cadrumo.application.user_profile.profile_operation_execution' in sys.modules
                print('read-light-mutation-ready')
                """
            ),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "read-light-mutation-ready"
