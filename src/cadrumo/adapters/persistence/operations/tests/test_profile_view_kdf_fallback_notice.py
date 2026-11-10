"""A profile whose password envelope sits at the fixed KDF fallback is told so, with the password-change door."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.custody import kdf_supervision
from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.operator_actions.catalogue import lookup_action
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.passphrase_rotation import rotate_profile_passphrase
from cadrumo.application.user_profile.password_kdf_notice import (
    PROFILE_KDF_AT_FALLBACK_NOTICE_CODE,
    PROFILE_KDF_STRENGTHEN_ACTION_ID,
)
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.application.user_profile.view_operation import (
    ProfileViewNoticeItem,
    ProfileViewOperationRequest,
    ProfileViewPageKind,
)
from cadrumo.application.user_profile.view_reader import read_profile_view_page
from cadrumo.core.config import override_settings
from cadrumo.core.json_contract import NoticeSeverity
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]
_PROFILE_CREDENTIAL = "profile-kdf-notice-passphrase"
_MEBIBYTE = 1024 * 1024


def _register_profile() -> UUID:
    with bundled_indexed_authority().operation() as authority:
        registered = register_profile_with_credentials(
            label="KDF fallback notice",
            passphrase=_PROFILE_CREDENTIAL,
            facts=(),
            profile_create_context=authority.profile_create_context(),
            profile_decode_context=authority.profile_decode_context(),
        )
        authenticate_profile_for_invocation(
            name=registered.profile_id,
            passphrase_callback=lambda: _PROFILE_CREDENTIAL,
            profile_decode_context=authority.profile_decode_context(),
        )
    return UUID(registered.profile_id)


def _kdf_notices(profile_id: UUID) -> list[ProfileViewNoticeItem]:
    """Read every overview page at one pinned revision; notices trail the overview."""
    request = ProfileViewOperationRequest(profile_id=profile_id, page_kind=ProfileViewPageKind.OVERVIEW)
    items: list[object] = []
    with bundled_indexed_authority().operation() as authority:
        while True:
            page = read_profile_view_page(request, authority_operation=authority)
            assert page.refusal_code is None
            items.extend(page.items)
            if page.next_cursor is None:
                break
            request = request.model_copy(
                update={
                    "cursor": page.next_cursor,
                    "expected_revision": page.record_revision,
                    "expected_content_digest": page.content_digest,
                }
            )
    return [
        item
        for item in items
        if isinstance(item, ProfileViewNoticeItem) and item.code == PROFILE_KDF_AT_FALLBACK_NOTICE_CODE
    ]


def _point(profile_id: UUID) -> tuple[int, int, int]:
    kdf = load_committed_profile_password_material(profile_id).envelope.kdf
    return (kdf.memory_mib, kdf.iterations, kdf.parallelism)


def test_a_profile_at_the_fallback_point_is_served_a_warning_that_opens_the_password_change_door(
    tmp_path: Path,
) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        # The package registers without measuring, so enrolment adopts the fixed fallback.
        profile_id = _register_profile()
        assert _point(profile_id) == (64, 3, 1)

        (notice,) = _kdf_notices(profile_id)

    assert notice.severity is NoticeSeverity.WARNING
    assert notice.message.strip()
    assert notice.action is not None
    assert notice.action.action_id == PROFILE_KDF_STRENGTHEN_ACTION_ID
    assert notice.action.target_command_key == lookup_action(PROFILE_KDF_STRENGTHEN_ACTION_ID).target_command_key
    assert notice.action.target_command_key == "config.passphrase.change"


def test_rotating_to_the_same_password_recalibrates_and_clears_the_notice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register_profile()
        assert len(_kdf_notices(profile_id)) == 1

        # Measure a small real grid whose band every point there meets, so the
        # rotation's fresh calibration confirms a point above the fallback.
        monkeypatch.setattr(
            kdf_supervision,
            "profile_kdf_resources",
            lambda: kdf_supervision.ProfileCustodyKdfResources(available_memory_bytes=150 * _MEBIBYTE, cpu_count=1),
        )
        monkeypatch.setattr(kdf_supervision, "PROFILE_CUSTODY_KDF_TARGET_MIN_SECONDS", 0.001)
        monkeypatch.setattr(kdf_supervision, "PROFILE_CUSTODY_KDF_TARGET_MAX_SECONDS", 1.5)
        monkeypatch.setattr(kdf_supervision, "PROFILE_CUSTODY_KDF_SAMPLE_COUNT", 2)
        # A loaded test host must not end the search on launch or wall-clock time.
        monkeypatch.setattr(kdf_supervision, "PROFILE_CUSTODY_KDF_SAMPLE_DEADLINE_SECONDS", 60.0)
        monkeypatch.setattr(kdf_supervision, "PROFILE_CUSTODY_KDF_TOTAL_DEADLINE_SECONDS", 600.0)
        with (
            override_settings(cadrumo_profile_kdf_measure_calibration=True),
            bundled_indexed_authority().operation() as authority,
        ):
            outcome = rotate_profile_passphrase(
                profile_id=profile_id,
                current_passphrase=_PROFILE_CREDENTIAL,
                new_passphrase=_PROFILE_CREDENTIAL,
                new_passphrase_confirmation=_PROFILE_CREDENTIAL,
                profile_decode_context=authority.profile_decode_context(),
            )

        assert outcome.dek_epoch_preserved
        # The rotation retired the old envelope, so the person signs in again with the same password.
        with bundled_indexed_authority().operation() as authority:
            authenticate_profile_for_invocation(
                name=str(profile_id),
                passphrase_callback=lambda: _PROFILE_CREDENTIAL,
                profile_decode_context=authority.profile_decode_context(),
            )
        assert _point(profile_id) == (64, 10, 1)
        assert _kdf_notices(profile_id) == []
