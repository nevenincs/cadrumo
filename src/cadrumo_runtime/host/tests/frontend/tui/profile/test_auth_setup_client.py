"""Runtime adapter persistence, CAS and protected-credential client boundaries."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Self, cast, override
from uuid import uuid4

import pytest
from pydantic import BaseModel

from cadrumo.application.auth.credential_operations import AuthCredentialSaveResult
from cadrumo.application.auth.operation_definitions import AuthConfigureOperationRequest
from cadrumo.application.auth.provider_configure_operation_access import AuthConfigurePublicResultV2
from cadrumo.application.auth.sync_readiness import AuthSyncReadiness
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.language_resolver import adopt_profile_output_language, register_language_resolver
from cadrumo.application.user_profile.overview import ProfileOverview
from cadrumo.application.user_profile.view_operation import ProfileViewPageKind
from cadrumo.core.auth_provider import AuthProviderKind, ClaveMovilRoute
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import profile_output_language_precedence
from cadrumo.domain.user_profile.values import ProfileSetupState
from cadrumo.entrypoints.tui.profile.tests.test_aeat_auth_setup import (
    auth_setup_overview_projection,
    auth_setup_readiness_projection,
)
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError, ProfileViewCollection

from .....frontend.tui.profile import aeat_auth_client
from .....frontend.tui.profile.aeat_auth_client import AeatAuthClient
from .....frontend.tui.profile.manager_client import ProfileManagerClientComposition

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_runtime_setup_serializes_cas_writes_keeps_secrets_off_profile_and_rereads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = cast("FrontendClient", type("Client", (), {"profile_id": uuid4(), "session_id": uuid4()})())
    values: dict[str, str] = {}
    revision = [1]
    calls: list[tuple[str, int]] = []
    configured: list[AuthConfigureOperationRequest] = []
    secrets: list[bytes] = []
    overview_reads = 0

    def overview() -> ProfileOverview:
        nonlocal overview_reads
        overview_reads += 1
        return auth_setup_overview_projection(values, revision[0])

    def persist(path: str, value: str, expected: int, _digest: str) -> ProfileViewCollection:
        assert expected == revision[0]
        calls.append((path, expected))
        values[path] = value
        revision[0] += 1
        return ProfileViewCollection(
            profile_id=client.profile_id,
            record_revision=revision[0],
            content_digest="a" * 64,
            setup_state=ProfileSetupState.INCOMPLETE,
            schema_version=1,
            valid=True,
            page_kinds=(ProfileViewPageKind.FACTS,),
            pages=(),
        )

    def configure(_client: FrontendClient, request: AuthConfigureOperationRequest) -> AuthConfigurePublicResultV2:
        assert request.expected_profile_revision == revision[0]
        configured.append(request)
        return AuthConfigurePublicResultV2(
            profile_id=client.profile_id,
            provider=request.provider,
            changed=True,
            certificate_file_provided=False,
            complete=False,
            profile_tax_id_present=True,
            provider_identity_present=True,
            identity_alignment="matches",
        )

    async def operation(
        _client: FrontendClient,
        definition: str,
        payload: BaseModel,
        result_type: type[BaseModel],
        *,
        secret: bytearray | None = None,
    ) -> AuthCredentialSaveResult:
        assert definition == "auth.credential.save"
        assert "private-password" not in payload.model_dump_json()
        assert secret is not None
        secrets.append(bytes(secret))
        return AuthCredentialSaveResult(provider="clave_permanente")

    async def readiness(_client: FrontendClient) -> AuthSyncReadiness:
        if not configured:
            return auth_setup_readiness_projection()
        assert secrets
        return auth_setup_readiness_projection("clave_permanente", ready=True)

    monkeypatch.setattr(aeat_auth_client, "configure_profile_authentication", configure)
    monkeypatch.setattr(aeat_auth_client, "run_auth_operation", operation)
    monkeypatch.setattr(aeat_auth_client, "read_sync_readiness", readiness)
    door = AeatAuthClient(client, overview=overview, persist=persist, pin=lambda: None)
    await door.snapshot()
    secret = bytearray(b"private-password")
    saved, result = await door.save(
        AuthProviderKind.CLAVE_PERMANENTE,
        ClaveMovilRoute.APP_REQUEST,
        {"identity.tax_id": "12345678Z", "auth.dni_nie": "12345678Z"},
        "",
        secret,
    )
    assert calls == [("identity.tax_id", 1), ("auth.dni_nie", 2)]
    assert saved.record_revision == 3 and result.ready
    assert json.loads(secrets[0]) == {"password": "private-password"}
    assert secret == bytes(len(secret))
    assert all("password" not in key for key in values)
    assert overview_reads == 2  # displayed baseline and final persisted readback


@pytest.mark.asyncio
async def test_held_auth_setup_reads_live_locale_on_open_and_after_save_preserving_exact_cas(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Installed door orchestration uses explicit read/configuration ports, not native admission evidence."""
    fake_client = SimpleNamespace(profile_id=uuid4(), session_id=uuid4(), frontend=OperationFrontendProjection.TUI)
    client = cast(FrontendClient, fake_client)
    reads: list[tuple[OutputLanguage, int]] = []
    configured: list[AuthConfigureOperationRequest] = []
    current = auth_setup_overview_projection({"identity.tax_id": "12345678Z"}, 7).model_copy(
        update={"profile_id": str(client.profile_id)}
    )

    def overview(bound: FrontendClient, _label: str, language: OutputLanguage) -> ProfileOverview:
        assert bound is client
        reads.append((language, threading.get_ident()))
        return current.model_copy(update={"label": f"Profile {language.value}"})

    def configure(bound: FrontendClient, request: AuthConfigureOperationRequest) -> AuthConfigurePublicResultV2:
        assert bound is client
        assert request.expected_profile_revision == 7
        assert request.expected_profile_digest == "a" * 64
        configured.append(request)
        return AuthConfigurePublicResultV2(
            profile_id=client.profile_id,
            provider=request.provider,
            changed=False,
            certificate_file_provided=False,
            complete=False,
            profile_tax_id_present=True,
            provider_identity_present=True,
            identity_alignment="matches",
        )

    async def readiness(bound: FrontendClient) -> AuthSyncReadiness:
        assert bound is client
        return auth_setup_readiness_projection()

    monkeypatch.setattr(aeat_auth_client, "configure_profile_authentication", configure)
    monkeypatch.setattr(aeat_auth_client, "read_sync_readiness", readiness)
    with (
        override_settings(cadrumo_storage_root=tmp_path, cadrumo_output_language=""),
        profile_output_language_precedence(),
    ):
        register_language_resolver()
        try:
            adopt_profile_output_language(OutputLanguage.EN)
            composition = ProfileManagerClientComposition(
                client, profile_label="Selected", output_language=OutputLanguage.EN, overview_reader=overview
            )
            door = composition.auth_setup()
            first, _ = await door.snapshot()
            assert first.label == "Profile en"
            adopt_profile_output_language(OutputLanguage.ES)
            opened, _ = await door.snapshot()
            assert opened.label == "Profile es"
            saved, _ = await door.save(AuthProviderKind.CLAVE_MOVIL, ClaveMovilRoute.APP_REQUEST, {}, "", None)
            assert saved.label == "Profile es"
            assert [language for language, _thread_id in reads] == [
                OutputLanguage.EN,
                OutputLanguage.ES,
                OutputLanguage.ES,
            ]
            assert all(thread_id != threading.get_ident() for _language, thread_id in reads)
            assert len(configured) == 1
            assert saved.profile_id == str(client.profile_id)
            assert (saved.record_revision, saved.content_digest) == (opened.record_revision, opened.content_digest)
            fake_client.session_id = uuid4()
            with pytest.raises(FrontendRefusedError):
                await door.snapshot()
            assert len(reads) == 3
        finally:
            register_language_resolver()


def test_auth_overview_refuses_a_language_change_during_its_read(
    tmp_path: Path,
) -> None:
    client = cast(
        FrontendClient,
        SimpleNamespace(profile_id=uuid4(), session_id=uuid4(), frontend=OperationFrontendProjection.TUI),
    )
    current = auth_setup_overview_projection({}, 4).model_copy(update={"profile_id": str(client.profile_id)})

    def overview(_bound: FrontendClient, _label: str, language: OutputLanguage) -> ProfileOverview:
        assert language is OutputLanguage.EN
        adopt_profile_output_language(OutputLanguage.ES)
        return current

    with (
        override_settings(cadrumo_storage_root=tmp_path, cadrumo_output_language=""),
        profile_output_language_precedence(),
    ):
        register_language_resolver()
        try:
            adopt_profile_output_language(OutputLanguage.EN)
            composition = ProfileManagerClientComposition(
                client, profile_label="Selected", output_language=OutputLanguage.EN, overview_reader=overview
            )
            with pytest.raises(RefusalError) as changed:
                composition._auth_overview()
            assert changed.value.reason is RefusalCode.UNAVAILABLE
        finally:
            register_language_resolver()


@pytest.mark.asyncio
async def test_saving_a_certificate_resolves_its_path_off_the_event_loop_thread(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Resolving the operator's certificate path reads the filesystem, so it never runs on the loop."""
    client = cast("FrontendClient", type("Client", (), {"profile_id": uuid4(), "session_id": uuid4()})())
    certificate = tmp_path / "certificate.p12"
    resolution_threads: list[int] = []
    configured: list[AuthConfigureOperationRequest] = []

    class _RecordedPath(Path):
        """A path whose resolution, the filesystem read, records the thread it ran on."""

        @override
        def resolve(self, strict: bool = False) -> Self:
            resolution_threads.append(threading.get_ident())
            return super().resolve(strict=strict)

    def configure(_client: FrontendClient, request: AuthConfigureOperationRequest) -> AuthConfigurePublicResultV2:
        configured.append(request)
        return AuthConfigurePublicResultV2(
            profile_id=client.profile_id,
            provider=request.provider,
            changed=True,
            certificate_file_provided=True,
            complete=False,
            profile_tax_id_present=True,
            provider_identity_present=True,
            identity_alignment="matches",
        )

    async def readiness(_client: FrontendClient) -> AuthSyncReadiness:
        return auth_setup_readiness_projection()

    monkeypatch.setattr(aeat_auth_client, "Path", _RecordedPath)
    monkeypatch.setattr(aeat_auth_client, "configure_profile_authentication", configure)
    monkeypatch.setattr(aeat_auth_client, "read_sync_readiness", readiness)
    door = AeatAuthClient(
        client,
        overview=lambda: auth_setup_overview_projection({}, 1),
        persist=lambda *_args: pytest.fail("no profile fact changes"),
        pin=lambda: None,
    )

    await door.save(AuthProviderKind.CERTIFICATE, ClaveMovilRoute.APP_REQUEST, {}, str(certificate), None)

    assert resolution_threads
    assert threading.get_ident() not in resolution_threads
    assert [request.certificate_path for request in configured] == [certificate.resolve()]
