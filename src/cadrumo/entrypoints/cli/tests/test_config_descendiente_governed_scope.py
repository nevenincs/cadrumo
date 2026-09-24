"""The descendiente verbs run inside the authority scope that dispatch opens.

Parsing a ``--descendiente`` row reads the registry's disability grades and the
relación default, and the stored rows are validated against the same
authority. Every other descendiente test runs under a test-level authority
lease, which lent the command a scope the command never opened, so a real
invocation refused with the catch-all "must declare NACIMIENTO" text on a row
that declared it.

These tests invoke the real CLI with no enclosing governed-fact scope, so the
scope the command runs under is proven to come from the CLI itself.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record

from ....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.governed_fact_scope import (
    outside_governed_fact_validation,
    validating_governed_facts,
)
from ....domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ....tests.cli_envelope import unwrap_schema_envelope
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "0ac1e000-0000-4000-8000-000000515002"
_ROW = "NACIMIENTO=2018-04-01,DISCAPACIDAD=0,CONVIVENCIA=true"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="Descendiente governed scope test profile",
    ) as profile:
        yield profile


def _seed_profile(runtime_profile: TestRuntimeProfile) -> None:
    """Seed a natural-person profile; the seed itself may lease the authority."""
    with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
        record = create_user_profile_record(
            profile_id=_PROFILE_ID,
            setup_state=ProfileSetupState.COMPLETE,
            facts=(
                UserProfileFact(path="identity.name", value="Ana"),
                UserProfileFact(path="identity.surnames", value="Perez"),
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="provenance.source", value="manual_cli"),
            ),
            context=profile_creation_context_for_test(),
        )
        seed_test_profile_record(record, root=runtime_profile.storage_root, label="Descendiente governed scope")


def _cli(*args: str) -> tuple[int, str]:
    with outside_governed_fact_validation():
        result = invoke_cached_cli(["--format", "json", "config", "profile", "descendiente", *args])
    return result.exit_code, result.output


def test_add_list_and_remove_open_their_own_authority_scope(runtime_profile: TestRuntimeProfile) -> None:
    """A well-formed row is accepted, listed and removed with no borrowed scope."""
    _seed_profile(runtime_profile)

    added_code, added = _cli("add", "--descendiente", _ROW)
    assert added_code == 0, added
    assert unwrap_schema_envelope(added)["total"] == 1

    listed_code, listed = _cli("list")
    assert listed_code == 0, listed

    removed_code, removed = _cli("remove", "0")
    assert removed_code == 0, removed
    assert unwrap_schema_envelope(removed)["total"] == 0


def test_a_row_missing_its_birth_date_still_refuses_without_a_borrowed_scope(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Opening the scope must not loosen the parser: NACIMIENTO stays required."""
    _seed_profile(runtime_profile)

    code, output = _cli("add", "--descendiente", "DISCAPACIDAD=0")

    assert code == 2, output
    assert "NACIMIENTO" in output
