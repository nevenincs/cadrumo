"""The profile manager saves authentication fields through the shared registered configuration."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from .....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from .....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from .....adapters.local_runtime.profile_mutations import ProfileMutationCompletion, ProfileMutationRequest
from .....application.auth.operation_definitions import AuthConfigureOperationRequest
from .....application.auth.provider_configure_operation_access import AuthConfigurePublicResultV2
from .....application.operations.registry import OperationFrontendProjection
from .....application.user_profile.overview import ProfileFieldView, ProfileOverview, ProfileSectionView
from .....application.user_profile.profile_operation_contracts import (
    ProfileFieldMutationOperationRequest,
    ProfileMutationOperationProjection,
)
from .....core.auth_provider import AuthProviderKind, ClaveMovilRoute
from .....core.external_constants import OutputLanguage
from .....core.operations import OperationEffect
from .....domain.user_profile.values import ProfileSetupState
from ..runtime_manager import RuntimeProfileManagerComposition

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DIGEST = "a" * 64
_NEXT_DIGEST = "c" * 64


class _Client(RuntimeFrontendClient):
    """An exact-profile wire boundary with no local custody or operation behaviour."""

    def __init__(self, profile_id: UUID) -> None:
        self._profile_id = profile_id
        self._frontend = OperationFrontendProjection.TUI
        self._session_id = uuid4()


def _overview(profile_id: UUID, revision: int, *, provider: str | None) -> ProfileOverview:
    return ProfileOverview(
        profile_id=str(profile_id),
        record_revision=revision,
        content_digest=_DIGEST if revision == 4 else _NEXT_DIGEST,
        label="Chosen profile",
        setup_state=ProfileSetupState.INCOMPLETE,
        sections=(
            ProfileSectionView(
                key="auth",
                title="Authentication",
                summary="",
                repeatable=False,
                fields=(
                    ProfileFieldView(
                        path="auth.provider", label="Provider", value=provider, masked=False, required=False
                    ),
                ),
            ),
        ),
    )


class _Recorder:
    """Stands in for the runtime doors; records what the manager submits and serves overviews."""

    def __init__(self, profile_id: UUID, *, provider: str | None) -> None:
        self.profile_id = profile_id
        self.provider = provider
        self.revision = 4
        self.configured: list[AuthConfigureOperationRequest] = []
        self.mutated: list[ProfileMutationRequest] = []

    def read(self, _client: RuntimeFrontendClient, _label: str, _language: OutputLanguage) -> ProfileOverview:
        return _overview(self.profile_id, self.revision, provider=self.provider)

    def configure(
        self, client: RuntimeFrontendClient, request: AuthConfigureOperationRequest
    ) -> AuthConfigurePublicResultV2:
        assert client.profile_id == self.profile_id
        self.configured.append(request)
        self.provider, self.revision = request.provider.value, self.revision + 1
        return AuthConfigurePublicResultV2(
            profile_id=self.profile_id,
            provider=request.provider,
            changed=True,
            certificate_file_provided=False,
            complete=True,
            profile_tax_id_present=False,
            provider_identity_present=False,
            identity_alignment="not_applicable",
        )

    def mutate(self, client: RuntimeFrontendClient, request: ProfileMutationRequest) -> ProfileMutationCompletion:
        assert client.profile_id == self.profile_id
        self.mutated.append(request)
        self.revision += 1
        return ProfileMutationCompletion(
            operation_id="b" * 64,
            projection=ProfileMutationOperationProjection(profile_id=self.profile_id, record_revision=self.revision),
            effect=OperationEffect.UPDATED,
        )


def _manager(recorder: _Recorder, client: _Client) -> RuntimeProfileManagerComposition:
    return RuntimeProfileManagerComposition(
        client,
        profile_label="Chosen profile",
        output_language=OutputLanguage.ES,
        mutation_runner=recorder.mutate,
        overview_reader=recorder.read,
        auth_configurer=recorder.configure,
    )


def test_provider_save_submits_the_shared_configuration_with_the_dialog_baseline() -> None:
    profile_id = uuid4()
    recorder = _Recorder(profile_id, provider=None)
    manager = _manager(recorder, _Client(profile_id))
    screen = manager.compose()

    saved = screen._persist_field("auth.provider", "certificate", 4, _DIGEST)

    assert recorder.configured == [
        AuthConfigureOperationRequest(
            provider=AuthProviderKind.CERTIFICATE,
            expected_profile_revision=4,
            expected_profile_digest=_DIGEST,
        )
    ]
    assert recorder.mutated == []
    assert saved.record_revision == 5


def test_route_save_for_clave_movil_carries_the_route_through_the_same_configuration() -> None:
    profile_id = uuid4()
    recorder = _Recorder(profile_id, provider="clave_movil")
    manager = _manager(recorder, _Client(profile_id))
    screen = manager.compose()

    screen._persist_field("auth.clave_movil_route", "app_request", 4, _DIGEST)

    assert recorder.configured == [
        AuthConfigureOperationRequest(
            provider=AuthProviderKind.CLAVE_MOVIL,
            clave_movil_route=ClaveMovilRoute.APP_REQUEST,
            expected_profile_revision=4,
            expected_profile_digest=_DIGEST,
        )
    ]
    assert recorder.mutated == []


def test_route_save_under_another_provider_stays_an_ordinary_field_save() -> None:
    profile_id = uuid4()
    recorder = _Recorder(profile_id, provider="certificate")
    manager = _manager(recorder, _Client(profile_id))
    screen = manager.compose()

    screen._persist_field("auth.clave_movil_route", "qr", 4, _DIGEST)

    assert recorder.configured == []
    assert recorder.mutated == [
        ProfileFieldMutationOperationRequest(
            profile_id=profile_id,
            expected_revision=4,
            expected_content_digest=_DIGEST,
            path="auth.clave_movil_route",
            value="qr",
        )
    ]


def test_a_replaced_session_refuses_before_any_configuration() -> None:
    profile_id = uuid4()
    recorder = _Recorder(profile_id, provider=None)
    client = _Client(profile_id)
    manager = _manager(recorder, client)
    screen = manager.compose()
    client._session_id = uuid4()

    with pytest.raises(RuntimeFrontendRefusedError):
        screen._persist_field("auth.provider", "certificate", 4, _DIGEST)

    assert recorder.configured == []
