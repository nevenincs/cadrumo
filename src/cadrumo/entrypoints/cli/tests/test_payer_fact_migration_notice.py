"""The notice that names payer facts a profile schema migration cleared.

A migrated legacy capsule with a stored ``false`` on the intracommunity payer
fact must tell the operator, in their language, which fact was cleared and the exact
flags that answer it, with a typed action on the profile edit verb; the flags
must exist on that live verb; and the notice is delivered once for the
invocation that migrated.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.profile_schema_legacy_support import (
    publish_legacy_capsule,
    record_session,
)
from cadrumo.application.user_profile.profile_schema_migration import (
    drain_migration_cleared_paths,
    migrate_profile_record_on_open,
)
from cadrumo.core.i18n.render import tr
from cadrumo.core.json_contract import ResolvedNoticeAction

from ....core.config import override_settings
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.user_profile.values import UserProfileFact
from ...payer_fact_migration_notices import (
    NOTICE_CODE,
    drain_payer_fact_migration_notices,
    payer_fact_cleared_notices,
    payer_fact_gated_modelos,
)
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FACT = "iva.does_intracomunitario"
_FLAG = "does-intracomunitario"
_ART109_FACT = "irpf.art109_activity_income_withholding_ge_70pct"
_ART109_FLAG = "art109-activity-income-withholding-ge-70pct"
_CLEARED = ((_FACT, _FLAG), (_ART109_FACT, _ART109_FLAG))


@pytest.fixture
def leased_operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


@pytest.mark.parametrize(("fact", "flag"), _CLEARED)
@pytest.mark.parametrize("language", ("en", "es", "ca", "hu"))
def test_the_notice_names_the_cleared_fact_and_both_edit_flags(
    language: str,
    fact: str,
    flag: str,
    leased_operation: PinnedAuthorityOperation,
) -> None:
    with override_settings(cadrumo_output_language=language):
        (notice,) = payer_fact_cleared_notices([fact], operation=leased_operation)
        label = tr(f"profile.schema.field.{fact}.label")
        template = tr(
            "cli.config.profile.notices.payer_fact_cleared",
            fact="{fact}",
            yes_flag="{yes_flag}",
            no_flag="{no_flag}",
        )

    assert notice.code == NOTICE_CODE
    assert notice.context == {"path": fact, "flag": f"--{flag}"}
    assert label in notice.message
    assert f"--{flag}" in notice.message
    assert f"--no-{flag}" in notice.message
    assert isinstance(notice.action, ResolvedNoticeAction)
    assert notice.action.action.target_command_key == "config.profile.edit"
    if language != "en":
        with override_settings(cadrumo_output_language="en"):
            english = tr(
                "cli.config.profile.notices.payer_fact_cleared",
                fact="{fact}",
                yes_flag="{yes_flag}",
                no_flag="{no_flag}",
            )
        assert template != english


def test_each_cleared_fact_is_scoped_to_the_modelos_its_own_gate_reads(
    leased_operation: PinnedAuthorityOperation,
) -> None:
    """Modelo 130 reads the Art. 109 fact through an exclusion, not a requirement."""
    assert payer_fact_gated_modelos(_ART109_FACT, operation=leased_operation) == frozenset({"130"})
    intracommunity = payer_fact_gated_modelos(_FACT, operation=leased_operation)
    assert "349" in intracommunity
    assert "130" not in intracommunity


@pytest.mark.parametrize("flag", [flag for _path, flag in _CLEARED])
def test_the_named_flags_exist_on_the_live_profile_edit_verb(flag: str) -> None:
    result = invoke_cached_cli(["config", "profile", "edit", "--help"])

    assert result.exit_code == 0, result.output
    assert f"--{flag}" in result.output
    assert f"--no-{flag}" in result.output


@pytest.mark.parametrize(("fact", "flag"), _CLEARED)
def test_a_migration_delivers_its_notice_once_for_the_invocation(fact: str, flag: str, tmp_path: Path) -> None:
    with bundled_indexed_authority().operation() as operation:
        create_context, decode_context = operation.profile_create_context(), operation.profile_decode_context()
    publish_legacy_capsule(
        tmp_path,
        version=7,
        facts=(
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path=fact, value=False),
        ),
        create_context=create_context,
        decode_context=decode_context,
    )
    drain_migration_cleared_paths()
    session = record_session(decode_context)
    try:
        migrate_profile_record_on_open(session, root=tmp_path)
        with override_settings(cadrumo_output_language="en"):
            first = drain_payer_fact_migration_notices()
            second = drain_payer_fact_migration_notices()
    finally:
        session.close()
        drain_migration_cleared_paths()

    assert [notice.context for notice in first] == [{"path": fact, "flag": f"--{flag}"}]
    assert second == ()
