"""Whether a frontend may offer an off-host evidence read is the backend's answer, not the frontend's guess.

The evidence review serves ``off_host_read_offered`` so the window asks for an
acknowledgement only where one can mint a consent. The answer comes from the
production composition against a real active profile: the deployment opt-in,
the gestor bar and the profile's own eligibility fact, the same three bars the
consent minting checks before it looks at the acknowledgement. A read the
bars refuse anyway settles with the refusal's own finished sentence, which a
frontend shows as served.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...adapters.outbound.llm.consent import mint_evidence_consent_token
from ...adapters.outbound.llm.errors import LLMConsentError
from ...adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from ...adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...application.operations.error_detail import build_operation_error_detail
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.capabilities import cloud_evidence_upload_eligible_for_active_profile
from ...core.capabilities import ServiceCapability
from ...core.config import Settings, override_settings
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import lookup_translation
from ...domain.user_profile.values import UserProfileFact
from ..evidence_followup_operation_composition import build_ledger_evidence_followup_operation_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE = UUID("3c5e7a9b-1d2f-4a6b-8c0d-2e4f6a8b0c1d")
_OTHER_PROFILE = "5e7a9b1d-2f4a-4b6c-8d0e-4f6a8b0c1d2e"
_SOURCE = "a" * 64


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as runtime_profile:
        yield runtime_profile


def _eligible(profile: TestRuntimeProfile, value: bool) -> None:
    upsert_test_profile_facts(
        _PROFILE,
        (UserProfileFact(path=ServiceCapability.CLOUD_EVIDENCE_UPLOAD.schema_path, value=value),),
        root=profile.storage_root,
    )


def _offered(*, permitted: bool, gestor: bool) -> bool:
    with override_settings(
        cadrumo_evidence_cloud_upload_permitted=permitted, cadrumo_evidence_gestor_mode=gestor
    ) as settings:
        ports = build_ledger_evidence_followup_operation_ports(settings=settings)
        return ports.off_host_read_askable(bucket_id=str(_PROFILE))


def _mints(settings: Settings) -> bool:
    try:
        mint_evidence_consent_token(
            settings=settings,
            profile_eligible=cloud_evidence_upload_eligible_for_active_profile(settings=settings),
            acknowledged=True,
            surface="test",
            evidence_content_address=_SOURCE,
        )
    except LLMConsentError:
        return False
    return True


def test_an_untouched_deployment_and_profile_offer_no_off_host_read(profile: TestRuntimeProfile) -> None:
    assert _offered(permitted=False, gestor=False) is False


@pytest.mark.parametrize(
    ("permitted", "gestor", "eligible"),
    [
        (True, False, True),
        (False, False, True),
        (True, True, True),
        (True, False, False),
    ],
)
def test_the_offer_holds_exactly_where_an_acknowledged_read_would_mint(
    profile: TestRuntimeProfile, *, permitted: bool, gestor: bool, eligible: bool
) -> None:
    _eligible(profile, eligible)
    offered = _offered(permitted=permitted, gestor=gestor)

    assert offered is (permitted and not gestor and eligible)
    with override_settings(
        cadrumo_evidence_cloud_upload_permitted=permitted, cadrumo_evidence_gestor_mode=gestor
    ) as settings:
        assert _mints(settings) is offered


def test_the_offer_is_answered_only_for_the_active_profile(profile: TestRuntimeProfile) -> None:
    _eligible(profile, True)
    with override_settings(cadrumo_evidence_cloud_upload_permitted=True) as settings:
        ports = build_ledger_evidence_followup_operation_ports(settings=settings)
        with pytest.raises(ProfileAccessRefusedError) as refused:
            ports.off_host_read_askable(bucket_id=_OTHER_PROFILE)

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_a_refused_off_host_read_serves_its_own_sentence(profile: TestRuntimeProfile, language: OutputLanguage) -> None:
    """The window shows why the read was refused, in the worker's language, never only that it was."""
    with override_settings(cadrumo_output_language=language.value) as settings:
        with pytest.raises(LLMConsentError) as refused:
            mint_evidence_consent_token(
                settings=settings,
                profile_eligible=cloud_evidence_upload_eligible_for_active_profile(settings=settings),
                acknowledged=True,
                surface="test",
                evidence_content_address=_SOURCE,
            )
        detail = build_operation_error_detail(refused.value)

    expected = lookup_translation("llm.evidence.consent.mint_refused", locale=language.value)
    assert expected is not None
    assert detail is not None
    assert detail.refusal_words == expected
    assert detail.refusal_words_language is language
