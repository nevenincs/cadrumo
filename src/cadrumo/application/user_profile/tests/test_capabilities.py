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
from ....core.parsing import parse_bool
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from .. import CapabilitySource, resolve_capability
from .._capabilities import _parse_bool_fact

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
    cases: tuple[tuple[ServiceCapability, bool, CapabilitySource], ...] = (
        (ServiceCapability.CLOUD_EVIDENCE_UPLOAD, False, CapabilitySource.GLOBAL_SETTING),
        (ServiceCapability.LLM_VISION, True, CapabilitySource.DEFAULT),
    )

    for capability, expected_enabled, expected_source in cases:
        resolved = resolve_capability(capability, profile_record=None, settings=settings)

        assert resolved.enabled is expected_enabled
        assert resolved.source is expected_source


def test_profile_fact_overrides_the_default() -> None:
    settings = load_settings()
    record = _record(
        UserProfileFact(path="capabilities.llm_vision", value=False),
        UserProfileFact(path="capabilities.cloud_evidence_upload", value=True),
    )

    for capability, expected_enabled in (
        (ServiceCapability.LLM_VISION, False),
        (ServiceCapability.CLOUD_EVIDENCE_UPLOAD, True),
    ):
        resolved = resolve_capability(capability, profile_record=record, settings=settings)

        # The profile opted in, and gestor mode is off + global default off, so the
        # profile fact is the deciding layer.
        assert resolved.enabled is expected_enabled
        assert resolved.source is CapabilitySource.PROFILE


@pytest.mark.parametrize("token", ["no", "n", "false", "falso", "0"])
def test_a_negative_answer_in_any_accepted_form_is_honoured(token: str) -> None:
    """A stored opt-out decides, rather than deferring to the deployment flag.

    The capability reader once carried its own token set that recognised none of
    the Spanish forms, so ``falso`` and ``n`` read as UNSET -- and an unset
    cloud-upload fact falls through to ``cadrumo_evidence_cloud_upload_permitted``.
    An explicit opt-out was therefore replaced by the deployment default, and the
    decision recorded ``GLOBAL_SETTING`` while a profile opt-out existed.

    The ``source`` assertion is the load-bearing half: reading the token as unset
    yields ``enabled=False`` too whenever the global flag happens to be off, so a
    test checking only ``enabled`` would have passed throughout the defect.
    """
    record = _record(UserProfileFact(path="capabilities.cloud_evidence_upload", value=token))

    resolved = resolve_capability(
        ServiceCapability.CLOUD_EVIDENCE_UPLOAD,
        profile_record=record,
        settings=load_settings(),
    )

    assert resolved.enabled is False
    assert resolved.source is CapabilitySource.PROFILE


def test_the_reader_accepts_exactly_what_the_write_door_stores() -> None:
    """Reader and write door share one vocabulary, by construction.

    ``boolean_value_refusal`` admits a string exactly when ``parse_bool`` reads
    it, and its refusal message names ``true/false, sí/no, 1/0`` -- so the
    taxpayer is told those forms work. A reader with its own token set can
    therefore silently discard an answer the door invited, which is what
    happened. Binding the two here means a future divergence fails rather than
    resolving to the deployment default.

    ``on``/``off`` are in the sample deliberately: the reader once accepted them
    while the door refuses them outright, so the drift ran in both directions.
    """
    for token in ("sí", "si", "s", "y", "yes", "true", "1", "verdadero", "no", "n", "falso", "0", "false", "on", "off"):
        assert _parse_bool_fact(token) == parse_bool(token), f"reader and write door disagree on {token!r}"


def test_gestor_mode_bars_cloud_upload_even_with_profile_opt_in() -> None:
    settings = load_settings().model_copy(update={"cadrumo_evidence_gestor_mode": True})
    record = _record(UserProfileFact(path="capabilities.cloud_evidence_upload", value=True))
    cloud = resolve_capability(ServiceCapability.CLOUD_EVIDENCE_UPLOAD, profile_record=record, settings=settings)
    # The safety floor wins absolutely — a capability narrows, never widens.
    assert cloud.enabled is False and cloud.source is CapabilitySource.SAFETY_FLOOR


def test_global_flag_enables_cloud_when_no_profile_fact() -> None:
    settings = load_settings().model_copy(update={"cadrumo_evidence_cloud_upload_permitted": True})
    cloud = resolve_capability(ServiceCapability.CLOUD_EVIDENCE_UPLOAD, profile_record=None, settings=settings)
    assert cloud.enabled is True and cloud.source is CapabilitySource.GLOBAL_SETTING
