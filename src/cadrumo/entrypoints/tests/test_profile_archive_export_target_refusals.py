"""The export operation refuses an unwritable destination itself, as the command does before it submits."""

from __future__ import annotations

from pathlib import Path

import pytest

from ...application.operations.operation_definition import OperationDefinition
from ...application.operations.registry import OperationPublicDefinitionRegistrationV1
from ...application.user_profile.archive_operation import (
    PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID,
    ProfileArchiveExportProjection,
    ProfileArchiveExportRequest,
    build_profile_archive_operation_definitions,
    build_profile_archive_operation_registrations,
)
from ...application.user_profile.capsule_archive import (
    PROFILE_CAPSULE_ARCHIVE_SUFFIX,
    ProfileCapsuleArchiveError,
    inspect_profile_capsule_archive,
)
from ...core.config import override_settings
from ...core.errors.error_codes import get_registered_error_code
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..cli.config._archive_cli import _refuse_an_archive_target_the_writer_would_reject
from ..cli.errors import CliRefusedBoundaryError
from ..profile_archive_operation_composition import build_profile_archive_operation_ports
from .profile_operation_supervisor import SettledOperation, SupervisedProfile, supervised_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_SUFFIX_KEY = "cli.config.profile.archive.refusal.export_suffix"
_EXISTS_KEY = "cli.config.profile.archive.refusal.export_target_exists"


def _composed() -> tuple[tuple[OperationDefinition, OperationPublicDefinitionRegistrationV1], ...]:
    definitions = build_profile_archive_operation_definitions(build_profile_archive_operation_ports)
    return tuple(zip(definitions, build_profile_archive_operation_registrations(definitions), strict=True))


def _command_refusal(target: Path) -> CliRefusedBoundaryError:
    """Return what ``config profile archive export`` refuses ``target`` with before it submits.

    The command needs a running runtime to be admitted at all, so its own
    refusal is taken from the check it runs first, not from a whole invocation.
    """
    with pytest.raises(CliRefusedBoundaryError) as refused:
        _refuse_an_archive_target_the_writer_would_reject(target)
    return refused.value


def _export(profile: SupervisedProfile, target: Path) -> SettledOperation:
    return profile.run(
        definition_id=PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile.profile_id)),
        payload=ProfileArchiveExportRequest(profile_id=profile.profile_id, target=target),
    )


def test_a_direct_client_meets_the_refusals_the_command_gives_and_a_good_target_is_written(tmp_path: Path) -> None:
    wrong_suffix = tmp_path / "backup.zip"
    existing = tmp_path / f"earlier{PROFILE_CAPSULE_ARCHIVE_SUFFIX}"
    existing.write_bytes(b"an earlier backup the operator still holds")
    fresh = tmp_path / f"fresh{PROFILE_CAPSULE_ARCHIVE_SUFFIX}"

    with (
        supervised_profile(tmp_path, _composed()) as profile,
        override_settings(cadrumo_active_profile=str(profile.profile_id), cadrumo_output_language="en"),
    ):
        targets = {_SUFFIX_KEY: wrong_suffix, _EXISTS_KEY: existing}
        refused = {key: _export(profile, target) for key, target in targets.items()}
        details = {key: profile.error_detail(outcome) for key, outcome in refused.items()}
        commanded = {key: _command_refusal(target) for key, target in targets.items()}
        exported = _export(profile, fresh)
        receipt = profile.result(exported, ProfileArchiveExportProjection).receipt

    for key, outcome in refused.items():
        assert outcome.receipt.condition is OperationTerminalCondition.REFUSED
        assert outcome.receipt.effect is OperationEffect.NONE
        assert details[key].error_code == get_registered_error_code(ProfileCapsuleArchiveError).code
        # The key and the context a direct client receives are the ones the command refuses with.
        assert details[key].message_key == key == commanded[key].translated_message
        assert details[key].context_mapping() == (commanded[key].context or {})
    assert details[_SUFFIX_KEY].context_mapping() == {"suffix": PROFILE_CAPSULE_ARCHIVE_SUFFIX}
    assert not wrong_suffix.exists()
    assert existing.read_bytes() == b"an earlier backup the operator still holds"
    assert (exported.receipt.condition, exported.receipt.effect) == (
        OperationTerminalCondition.SUCCEEDED,
        OperationEffect.UPDATED,
    )
    assert receipt.target == str(fresh)
    assert str(inspect_profile_capsule_archive(fresh).bucket_id) == str(profile.profile_id)
