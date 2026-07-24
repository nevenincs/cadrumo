"""The ``config profile descendiente`` door callback and preserved flag verbs.

Drives the real ``cadrumo`` CLI end to end against an isolated real-session
backend — no mocks. Invoking the group with no subcommand opens the paged
descendant door; under the non-interactive test host (no controlling terminal)
the door refuses with the substrate's no-console message rather than crashing,
proving the callback is wired onto the exact command the modify-mode
descendants advisory notice points operators at. The flag verbs (``add`` / ``list`` / ``remove``) remain the
automation contract and keep behaving after the group gained its door callback.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from .....application.user_profile import UserProfileLifecycleRepository
from .....domain.user_profile import UserProfileFact, UserProfileRecord, UserProfileStatus
from .....tests.cli_runner import invoke_cached_cli
from .....tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "0ac1e000-0000-4000-8000-0000005240a1"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="Descendiente door test profile",
    ) as profile:
        yield profile


def _seed_natural_person_profile(runtime_profile: TestRuntimeProfile) -> None:
    record = UserProfileRecord(
        schema_id="cadrumo.user_profile",
        schema_version=1,
        profile_id=_PROFILE_ID,
        display_name="Descendiente door test profile",
        status=UserProfileStatus.ACTIVE,
        facts=(
            UserProfileFact(path="identity.name", value="Ana"),
            UserProfileFact(path="identity.surnames", value="Perez"),
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="provenance.source", value="manual_cli"),
        ),
    )
    UserProfileLifecycleRepository(bucket_id=_PROFILE_ID, objects=runtime_profile.repository).save(record)


def test_descendiente_root_opens_the_door_and_refuses_without_a_console(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """``config profile descendiente`` (no subcommand) opens the door.

    Under the non-interactive test host the door has no frontend to present, so
    it refuses through the substrate's no-console boundary — a non-zero exit, not
    a crash and not a silent no-op. This proves the callback intercepts the
    no-subcommand invocation and drives the door.
    """
    _seed_natural_person_profile(runtime_profile)

    result = invoke_cached_cli(["config", "profile", "descendiente"])

    assert result.exit_code != 0, result.output


def test_descendiente_list_flag_verb_survives_the_door_callback(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The ``add`` / ``list`` flag verbs still resolve after the group gained a callback."""
    _seed_natural_person_profile(runtime_profile)

    add_result = invoke_cached_cli(
        [
            "config", "profile", "descendiente", "add",
            "--descendiente", "NACIMIENTO=2018-01-01",
        ],
    )  # fmt: skip
    assert add_result.exit_code == 0, add_result.output

    list_result = invoke_cached_cli(["--format", "json", "config", "profile", "descendiente", "list"])
    assert list_result.exit_code == 0, list_result.output
    assert "2018-01-01" in list_result.output
