"""``ledger rule add`` validates ``--category-id`` under the scope dispatch opens.

The category catalogue is registry authority. The handler never opens a scope
of its own, so it used to depend on an earlier lease: the profile preflight
takes one only when it has to resume a session, and a run whose session was
already serving refused every category id with the missing-scope error. Every
other rule test borrows a test-level scope or omits ``--category-id``.

These tests invoke the real CLI with no enclosing governed-fact scope.
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

_PROFILE_ID = "0ac1e000-0000-4000-8000-000000515003"
_MISSING_SCOPE = "requires an explicit authority operation or scope"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="Ledger rule governed scope test profile",
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
        seed_test_profile_record(record, root=runtime_profile.storage_root, label="Ledger rule governed scope")


def _rule_add(category_id: str) -> tuple[int, str]:
    with outside_governed_fact_validation():
        result = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "ledger",
                "rule",
                "add",
                "--description-pattern",
                "material",
                "--classification",
                "BUSINESS",
                "--category-id",
                category_id,
            ],
        )
    return result.exit_code, result.output


def test_a_declared_category_is_accepted_without_a_borrowed_scope(runtime_profile: TestRuntimeProfile) -> None:
    """The documented rule is stored with the category the catalogue declares."""
    _seed_profile(runtime_profile)

    code, output = _rule_add("material_oficina")

    assert code == 0, output
    assert unwrap_schema_envelope(output)["category_id"] == "material_oficina"


def test_an_unknown_category_gets_the_catalogue_refusal_not_the_scope_error(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The refusal reads the catalogue for its example id, so it needs the scope too."""
    _seed_profile(runtime_profile)

    code, output = _rule_add("no_such_category")

    assert code == 2, output
    assert "no_such_category" in output
    assert _MISSING_SCOPE not in output
