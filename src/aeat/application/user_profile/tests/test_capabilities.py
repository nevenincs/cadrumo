"""The capability resolver overlays profile facts onto the global posture.

A capability may only NARROW the global safety floor: gestor mode bars cloud
evidence upload absolutely (no profile opt-in re-enables it); otherwise the
profile fact wins, falling back to the global Settings flag (cloud) or the
conservative default (vision / google).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core import ServiceCapability
from ....core.config import load_settings
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from .. import CapabilitySource, resolve_capability

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)


def _record(*facts: UserProfileFact) -> UserProfileRecord:
    return UserProfileRecord(
        profile_id="19191919-1919-4191-8191-191919191919",
        display_name="P1",
        facts=facts,
        created_at=_NOW,
        updated_at=_NOW,
    )


def test_no_profile_fact_falls_back_to_global_default() -> None:
    settings = load_settings()
    cloud = resolve_capability(ServiceCapability.CLOUD_EVIDENCE_UPLOAD, profile_record=None, settings=settings)
    assert cloud.enabled is False and cloud.source is CapabilitySource.GLOBAL_SETTING
    vision = resolve_capability(ServiceCapability.LLM_VISION, profile_record=None, settings=settings)
    assert vision.enabled is True and vision.source is CapabilitySource.DEFAULT


def test_profile_fact_overrides_the_default() -> None:
    settings = load_settings()
    record = _record(
        UserProfileFact(path="capabilities.llm_vision", value=False),
        UserProfileFact(path="capabilities.cloud_evidence_upload", value=True),
    )
    vision = resolve_capability(ServiceCapability.LLM_VISION, profile_record=record, settings=settings)
    assert vision.enabled is False and vision.source is CapabilitySource.PROFILE
    cloud = resolve_capability(ServiceCapability.CLOUD_EVIDENCE_UPLOAD, profile_record=record, settings=settings)
    # The profile opted in, and gestor mode is off + global default off, so the
    # profile fact is the deciding layer.
    assert cloud.enabled is True and cloud.source is CapabilitySource.PROFILE


def test_gestor_mode_bars_cloud_upload_even_with_profile_opt_in() -> None:
    settings = load_settings().model_copy(update={"aeat_evidence_gestor_mode": True})
    record = _record(UserProfileFact(path="capabilities.cloud_evidence_upload", value=True))
    cloud = resolve_capability(ServiceCapability.CLOUD_EVIDENCE_UPLOAD, profile_record=record, settings=settings)
    # The safety floor wins absolutely — a capability narrows, never widens.
    assert cloud.enabled is False and cloud.source is CapabilitySource.SAFETY_FLOOR


def test_global_flag_enables_cloud_when_no_profile_fact() -> None:
    settings = load_settings().model_copy(update={"aeat_evidence_cloud_upload_permitted": True})
    cloud = resolve_capability(ServiceCapability.CLOUD_EVIDENCE_UPLOAD, profile_record=None, settings=settings)
    assert cloud.enabled is True and cloud.source is CapabilitySource.GLOBAL_SETTING
