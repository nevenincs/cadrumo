"""Profile creation runs in the runtime, under the passphrase the person confirmed, and leaves the profile signed out."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.master_key.active_session import (
    close_active_bucket_session,
    has_active_bucket_session,
)
from cadrumo.application.evidence.profile_legal_hold import LegalHoldCaseAuthority
from cadrumo.application.filing.retention import FilingRetentionAuthority
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.custody_ports import (
    load_profile_custody_password_material,
    unlock_profile_custody_password,
)
from cadrumo.application.user_profile.registration import ProfileRegistrationError
from cadrumo.core.config import override_settings
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo_client.contracts.installation_requests import (
    InstallationAct,
    InstallationRefused,
    ProfileCreateReply,
    ProfileCreateRequest,
    ProfileListReply,
    ProfileListRequest,
)
from cadrumo_client.transport.installation_client import InstallationClient, installation_new_passphrase_document

from .installation_profile_support import PROFILE_INPUT, PROFILE_LABEL, installation_client, serving_profile_acts

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_CLI = OperationFrontendProjection.CLI
_SHORT_INPUT = "short"
"""Fewer characters than any profile password may have."""


def _create(
    client: InstallationClient,
    *,
    label: str = PROFILE_LABEL,
    passphrase: str = PROFILE_INPUT,
    confirmation: str | None = None,
) -> ProfileCreateReply | InstallationRefused:
    secret = installation_new_passphrase_document(
        bytearray(passphrase, "utf-8"), bytearray(passphrase if confirmation is None else confirmation, "utf-8")
    )
    reply = client.perform(
        ProfileCreateRequest(request_id=uuid4(), frontend=_CLI, label=label), ProfileCreateReply, secret=secret
    )
    assert secret == bytes(len(secret))
    assert not isinstance(reply, ProfileCreateReply) or reply.label == label
    return reply if isinstance(reply, ProfileCreateReply | InstallationRefused) else pytest.fail(repr(reply))


def _listed(client: InstallationClient) -> ProfileListReply:
    listed = client.perform(ProfileListRequest(request_id=uuid4(), frontend=_CLI), ProfileListReply)
    assert isinstance(listed, ProfileListReply)
    return listed


def _fresh_root(tmp_path: Path) -> Path:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    return root


def test_creation_selects_the_profile_signed_out_under_the_confirmed_passphrase(tmp_path: Path) -> None:
    root = _fresh_root(tmp_path)
    close_active_bucket_session()
    with serving_profile_acts(root) as endpoint, installation_client(endpoint) as client:
        created = _create(client)
        listed = _listed(client)

    assert isinstance(created, ProfileCreateReply), created
    assert created.selected and created.signed_in is False
    assert created.setup_state == "incomplete"
    assert [(row.bucket_id, row.active) for row in listed.profiles] == [(created.profile_id, True)]
    assert listed.active_profile == PROFILE_LABEL
    # Nothing was signed in: no process holds the new profile's key.
    assert not has_active_bucket_session()
    profile_id = UUID(created.profile_id)
    with override_settings(cadrumo_local_storage_root=root):
        # The deletion preflight's facts are recorded as for any created profile.
        assert FilingRetentionAuthority().path(profile_id).is_file()
        assert LegalHoldCaseAuthority().path(profile_id).is_file()
    # The capsule opens under the passphrase the person chose, and only under it.
    material = load_profile_custody_password_material(profile_id, root=root)
    assert unlock_profile_custody_password(material, password=PROFILE_INPUT).profile_id == profile_id


def test_a_confirmation_that_differs_is_refused_before_anything_is_written(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = _fresh_root(tmp_path)
    caplog.set_level(logging.DEBUG)
    other = "a-different-but-long-enough-passphrase"
    with serving_profile_acts(root) as endpoint, installation_client(endpoint) as client:
        refused = _create(client, confirmation=other)
        listed = _listed(client)

    assert isinstance(refused, InstallationRefused), refused
    assert refused.act is InstallationAct.PROFILE_CREATE
    assert refused.detail.error_code == get_registered_error_code(ProfileRegistrationError).code
    assert listed.profiles == ()
    for secret in (PROFILE_INPUT, other):
        assert secret not in refused.model_dump_json()
        assert secret not in caplog.text


def test_a_short_passphrase_and_a_taken_label_are_refused_as_the_command_refuses_them(tmp_path: Path) -> None:
    root = _fresh_root(tmp_path)
    with serving_profile_acts(root) as endpoint, installation_client(endpoint) as client:
        short = _create(client, passphrase=_SHORT_INPUT)
        created = _create(client)
        taken = _create(client, label=PROFILE_LABEL.upper())
        listed = _listed(client)

    assert isinstance(short, InstallationRefused) and isinstance(taken, InstallationRefused)
    assert isinstance(created, ProfileCreateReply)
    registration = get_registered_error_code(ProfileRegistrationError).code
    assert short.detail.error_code == taken.detail.error_code == registration
    assert ("reason", "too_few_scalars") in {(entry.key, entry.value) for entry in short.detail.context}
    assert taken.detail.message_key == "application.user_profile.errors.profile_already_exists"
    assert [row.bucket_id for row in listed.profiles] == [created.profile_id]
