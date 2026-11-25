"""The notice that names payer facts a profile schema migration cleared.

A migrated legacy capsule whose cleared path carried the wizard's own default
must tell the operator, in their language, which fact was cleared and the exact
flags that answer it, with a typed action on the profile edit verb; the flags
must exist on that live verb; and the notice is delivered once for the
invocation that migrated.

A yes/no fact and a select are answered differently, so the notice carries two
wordings: the yes/no fact names ``--flag`` and ``--no-flag``, while the
residency select names one flag that takes a value. Naming
``--no-fiscal-residency`` would send the operator to a flag the verb does not
have, so the two are asserted apart.
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
_CAPITAL_FACT = "withholding.pays_capital_income_with_retencion"
_CAPITAL_FLAG = "pays-capital-income-with-retencion"
_LARGE_COMPANY_FACT = "censo.large_company"
_LARGE_COMPANY_FLAG = "enrollment-large-company"
_OSS_FACT = "iva.oss_enrolled"
_OSS_FLAG = "iva-oss-enrolled"
_CLEARED = (
    (_FACT, _FLAG),
    (_ART109_FACT, _ART109_FLAG),
    (_CAPITAL_FACT, _CAPITAL_FLAG),
    (_LARGE_COMPANY_FACT, _LARGE_COMPANY_FLAG),
    (_OSS_FACT, _OSS_FLAG),
)
"""Every cleared yes/no fact asserted here, with the question id its flag carries."""

_RESIDENCY_FACT = "taxpayer_type.fiscal_residency"
_RESIDENCY_FLAG = "fiscal-residency"
_RESIDENT_CATEGORY = "resident_irpf"
"""The cleared select, which is answered by one flag and a value."""


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


@pytest.mark.parametrize("language", ("en", "es", "ca", "hu"))
def test_the_residency_notice_names_one_flag_and_never_a_negated_one(
    language: str,
    leased_operation: PinnedAuthorityOperation,
) -> None:
    """A select is not answered by a negated flag, so the notice must not invent one."""
    with override_settings(cadrumo_output_language=language):
        (notice,) = payer_fact_cleared_notices([_RESIDENCY_FACT], operation=leased_operation)
        label = tr(f"profile.schema.field.{_RESIDENCY_FACT}.label")

    assert notice.code == NOTICE_CODE
    assert notice.context == {"path": _RESIDENCY_FACT, "flag": f"--{_RESIDENCY_FLAG}"}
    assert label in notice.message
    assert f"--{_RESIDENCY_FLAG}" in notice.message
    assert f"--no-{_RESIDENCY_FLAG}" not in notice.message


def test_the_residency_flag_exists_on_the_live_profile_edit_verb_and_takes_a_value() -> None:
    result = invoke_cached_cli(["config", "profile", "edit", "--help"])

    assert result.exit_code == 0, result.output
    assert f"--{_RESIDENCY_FLAG}" in result.output
    assert f"--no-{_RESIDENCY_FLAG}" not in result.output


def test_the_migration_delivers_the_residency_notice_once_for_the_invocation(tmp_path: Path) -> None:
    with bundled_indexed_authority().operation() as operation:
        create_context, decode_context = operation.profile_create_context(), operation.profile_decode_context()
    publish_legacy_capsule(
        tmp_path,
        version=7,
        facts=(
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path=_RESIDENCY_FACT, value=_RESIDENT_CATEGORY),
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

    assert [notice.context for notice in first] == [
        {"path": _RESIDENCY_FACT, "flag": f"--{_RESIDENCY_FLAG}"},
    ]
    assert second == ()


def test_each_cleared_fact_is_scoped_to_the_modelos_its_own_gate_reads(
    leased_operation: PinnedAuthorityOperation,
) -> None:
    """Modelo 130 reads the Art. 109 fact through an exclusion, not a requirement."""
    assert payer_fact_gated_modelos(_ART109_FACT, operation=leased_operation) == frozenset({"130"})
    intracommunity = payer_fact_gated_modelos(_FACT, operation=leased_operation)
    assert "349" in intracommunity
    assert "130" not in intracommunity
    assert payer_fact_gated_modelos(_CAPITAL_FACT, operation=leased_operation) == frozenset(
        {"117", "123", "126", "128", "187", "188", "193", "194"},
    )
    assert payer_fact_gated_modelos(_OSS_FACT, operation=leased_operation) == frozenset({"369"})
    assert payer_fact_gated_modelos(_LARGE_COMPANY_FACT, operation=leased_operation) == frozenset({"347"})


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
