"""An admitted service reads its exact profile's capability through the registered profile view.

The runtime, its workers and the encrypted profile are real, and so is the service's
own connection and lease. Installed image verification is the controlled port the
service-record tests use, so this is not native installed-service evidence. The
service's ceiling is the packaged one: every public operation action and no
disclosure of its own.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cadrumo.application.user_profile.profile_operation_contracts import ProfileFieldMutationOperationRequest
from cadrumo.application.user_profile.view_operation import PROFILE_VIEW_OPERATION_DEFINITION_ID
from cadrumo.core.capabilities import ServiceCapability
from cadrumo.core.config import Settings
from cadrumo.core.operations import OperationEffect, OperationFrontendProjection
from cadrumo_client.contracts.access_vocabulary import AccessAction, AccessScope
from cadrumo_client.contracts.service_access import ServiceConnected
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.profile_mutations import run_profile_mutation
from cadrumo_client.transport.service_profile_view import InstalledServiceProfileView

from .profile_record_support import profile_view_facts
from .test_service_records import ServiceRecordRuntime, service_record_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows transport and workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_CAPABILITY = ServiceCapability.CLOUD_EVIDENCE_UPLOAD
_SETTINGS = Settings(cadrumo_evidence_gestor_mode=False, cadrumo_evidence_cloud_upload_permitted=True)
_PACKAGED_CEILING = AccessScope(
    operations=frozenset({PROFILE_VIEW_OPERATION_DEFINITION_ID}),
    actions=frozenset(AccessAction),
    disclosures=frozenset(),
    periods=None,
    allow_period_independent=True,
    allow_delegation=False,
)


def _person(runtime: ServiceRecordRuntime) -> FrontendClient:
    person = FrontendClient(runtime.human, profile_id=runtime.profile_id, frontend=OperationFrontendProjection.CLI)
    person._session_id = runtime.person_session_id
    return person


def _choose(person: FrontendClient, *, enabled: bool) -> None:
    revision, digest, _ = profile_view_facts(person)
    completed = run_profile_mutation(
        person,
        ProfileFieldMutationOperationRequest(
            profile_id=person.profile_id,
            expected_revision=revision,
            expected_content_digest=digest,
            path=_CAPABILITY.schema_path,
            value=str(enabled).lower(),
        ),
        timeout=60,
    )
    assert completed.effect is OperationEffect.UPDATED


def test_a_service_reads_the_profiles_own_choice_at_every_decision(tmp_path: Path) -> None:
    with service_record_runtime(tmp_path, operation_scope=_PACKAGED_CEILING) as runtime:
        service = runtime.connect_service()
        assert isinstance(runtime.admit(service), ServiceConnected)
        assert service.claim() is not None
        view = InstalledServiceProfileView(service)
        person = _person(runtime)

        # No choice yet: the owner's default for this capability is off.
        untouched = view.read_capability(_CAPABILITY, settings=_SETTINGS, timeout=60)
        assert untouched.enabled is False

        _choose(person, enabled=True)
        assert view.read_capability(_CAPABILITY, settings=_SETTINGS, timeout=60).enabled is True

        _choose(person, enabled=False)
        assert view.read_capability(_CAPABILITY, settings=_SETTINGS, timeout=60).enabled is False

        # The gestor floor of the profile owner still bars an opted-in profile.
        _choose(person, enabled=True)
        gestor = _SETTINGS.model_copy(update={"cadrumo_evidence_gestor_mode": True})
        assert view.read_capability(_CAPABILITY, settings=gestor, timeout=60).enabled is False


def test_a_service_without_a_lease_cannot_read_the_profile(tmp_path: Path) -> None:
    with service_record_runtime(tmp_path, operation_scope=_PACKAGED_CEILING) as runtime:
        service = runtime.connect_service()
        view = InstalledServiceProfileView(service)

        with pytest.raises(FrontendRefusedError):
            view.read_capability(_CAPABILITY, settings=_SETTINGS, timeout=60)


def test_a_service_whose_ceiling_names_no_profile_read_is_refused(tmp_path: Path) -> None:
    with service_record_runtime(tmp_path) as runtime:
        service = runtime.connect_service()
        assert isinstance(runtime.admit(service), ServiceConnected)
        assert service.claim() is not None
        view = InstalledServiceProfileView(service)

        with pytest.raises(FrontendRefusedError):
            view.read_capability(_CAPABILITY, settings=_SETTINGS, timeout=60)
