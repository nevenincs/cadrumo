"""Explicit-settings and bucket-isolation tests for certificate-source resolution."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from cadrumo.adapters.outbound.aeat.auth import session_store
from cadrumo.adapters.outbound.aeat.browser.factory import default_browser_session_factory
from cadrumo.adapters.persistence.profile.tests.operator_projection_test_support import (
    build_live_auth_preflight_report,
    build_operator_state_projection,
    configure_operator_auth,
)
from cadrumo.adapters.persistence.profile.tests.operator_projection_test_support import (
    test_operator_auth as run_operator_auth_test,
)
from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.auth.actions import update_auth
from cadrumo.application.auth.certificate_source_operations import (
    check_operator_certificate_sources,
    register_operator_certificate_source,
    select_operator_certificate_source,
    set_operator_certificate_source_secret,
)
from cadrumo.application.auth.credentials import (
    active_auth_projection_span,
    project_active_certificate_credentials,
    resolve_active_certificate_credentials,
)
from cadrumo.application.auth.operator import login_operator_auth
from cadrumo.application.auth.operator_probes import probe_provider_credentials
from cadrumo.application.auth.operator_results import (
    AuthLoginPreconditionError,
    AuthOperationRequiresCustodySessionError,
)
from cadrumo.application.auth.probes import ProviderProbeResult
from cadrumo.application.auth.providers import select_provider
from cadrumo.application.auth.sessions import load_persisted_session, storage_state_paths
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.application.workflow.persistence import workflow_state_repository
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.bucket_pointer import BucketPointer, write_pointer
from cadrumo.core.config import load_settings, override_settings
from cadrumo.domain.calculations.registry.authority import (
    bundled_indexed_authority as _certificate_indexed_authority_for_test,
)
from cadrumo.tests.certificates import CERTIFICATE_BUNDLE_INPUT, build_pkcs12_bundle

from .certificate_sources_check_support import (
    _BUCKET_B,
    _BUCKET_ID,
    _MISSING_BUCKET,
    _NOW,
    _OPERATOR_PROBE_PORTS,
    _OPERATOR_SCOPE_PORTS,
    _PROFILE_LABEL,
    _PROFILE_LABEL_B,
    CERTIFICATE_BUNDLE_INPUT_B,
    _register_operator_profile,
)
from .certificate_sources_check_support import (
    _isolated_backend as _isolated_backend,
)
from .certificate_sources_check_support import (
    _manages_storage_roots as _manages_storage_roots,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]


def test_explicit_settings_second_root_uses_its_own_cached_secret_store(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    _manages_storage_roots: None,
    tmp_path: Path,
) -> None:
    """Initializing root A first cannot redirect root B certificate secrets into A."""
    with _certificate_indexed_authority_for_test().operation() as _certificate_authority_operation_for_test:
        root_a_fixture = tmp_path / "route-a"
        with (
            isolated_profile_storage_root(tmp_path=root_a_fixture),
            open_test_profile_session(_BUCKET_ID),
        ):
            _register_operator_profile()
            now = datetime.now(UTC)
            cert_a = build_pkcs12_bundle(
                tmp_path,
                not_valid_before=now - timedelta(days=1),
                not_valid_after=now + timedelta(days=200),
                name="route-a",
                subject_cn="route-a",
            )
            register_operator_certificate_source(
                name="selected",
                certificate_path=cert_a,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            set_operator_certificate_source_secret(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                name="selected",
                secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            select_operator_certificate_source(
                name="selected",
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            configure_operator_auth(
                AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a, operator_scope_ports=_OPERATOR_SCOPE_PORTS
            )
            settings_a = load_settings()

        root_b_fixture = tmp_path / "route-b"
        with (
            isolated_profile_storage_root(tmp_path=root_b_fixture),
            open_test_profile_session(_BUCKET_B),
        ):
            register_minimal_profile(
                profile_id=_BUCKET_B,
                display_name="gestor-route-b",
            )
            cert_b = build_pkcs12_bundle(
                tmp_path,
                not_valid_before=now - timedelta(days=1),
                not_valid_after=now + timedelta(days=200),
                name="route-b",
                subject_cn="route-b",
                password=CERTIFICATE_BUNDLE_INPUT_B,
            )
            register_operator_certificate_source(
                name="selected",
                certificate_path=cert_b,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            settings_b = load_settings()
            set_operator_certificate_source_secret(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                name="selected",
                secret=SecretStr(CERTIFICATE_BUNDLE_INPUT_B),
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            select_operator_certificate_source(
                name="selected",
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            configure_operator_auth(
                AuthProviderKind.CERTIFICATE.value,
                certificate_path=cert_b,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            )
            credentials_b = resolve_active_certificate_credentials(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                settings=settings_b,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            )
            provider_b = select_provider(
                AuthProviderKind.CERTIFICATE,
                settings=settings_b,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            ).describe()
            operator_test_b = run_operator_auth_test(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                settings=settings_b,
                operator_probe_ports=_OPERATOR_PROBE_PORTS,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            )

        assert settings_a.cadrumo_storage_root != settings_b.cadrumo_storage_root
        assert credentials_b.certificate_path == cert_b
        assert credentials_b.password is not None
        assert credentials_b.password.get_secret_value() == CERTIFICATE_BUNDLE_INPUT_B
        assert provider_b.available is True
        assert operator_test_b.certificate_path == str(cert_b)
        assert operator_test_b.probe_result == ProviderProbeResult.OK


def test_explicit_settings_same_bucket_id_uses_target_root_and_restores_ambient_session(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    _manages_storage_roots: None,
    tmp_path: Path,
) -> None:
    """A matching UUID cannot reuse key material from a different storage root.

    Per-profile custody changed what "cannot" looks like. These calls once
    opened root B's bucket on demand and answered from B's own material; they
    now cannot, because opening B's custody session needs the operator's
    password. The guarantee under test is unchanged and the stricter end of it
    holds: root A's open session never answers a root B question.

    The surfaces split on HOW they decline, and the split is asserted rather
    than smoothed over. The credential resolver and the provider factory
    swallow the refusal and return an empty credential -- a truthful "no
    credential is available", which every consumer already reads as
    not-configured. ``check``, ``auth test`` and the live preflight let it
    through, because each renders an operator VERDICT about a named profile
    and a silent "nothing found" would be indistinguishable from "inspected
    and found nothing" when nothing was inspected at all.
    """
    with _certificate_indexed_authority_for_test().operation() as _certificate_authority_operation_for_test:
        now = datetime.now(UTC)
        root_b_fixture = tmp_path / "same-id-route-b"
        with (
            isolated_profile_storage_root(tmp_path=root_b_fixture),
            open_test_profile_session(_BUCKET_ID),
        ):
            _register_operator_profile()
            cert_b = build_pkcs12_bundle(
                tmp_path,
                not_valid_before=now - timedelta(days=1),
                not_valid_after=now + timedelta(days=200),
                name="same-id-route-b",
                subject_cn="same-id-route-b",
                password=CERTIFICATE_BUNDLE_INPUT_B,
            )
            register_operator_certificate_source(
                name="selected",
                certificate_path=cert_b,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            set_operator_certificate_source_secret(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                name="selected",
                secret=SecretStr(CERTIFICATE_BUNDLE_INPUT_B),
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            select_operator_certificate_source(
                name="selected",
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            configure_operator_auth(
                AuthProviderKind.CERTIFICATE.value, certificate_path=cert_b, operator_scope_ports=_OPERATOR_SCOPE_PORTS
            )
            settings_b = load_settings()

        root_a_fixture = tmp_path / "same-id-route-a"
        with (
            isolated_profile_storage_root(tmp_path=root_a_fixture),
            open_test_profile_session(_BUCKET_ID),
        ):
            _register_operator_profile()
            cert_a = build_pkcs12_bundle(
                tmp_path,
                not_valid_before=now - timedelta(days=1),
                not_valid_after=now + timedelta(days=200),
                name="same-id-route-a",
                subject_cn="same-id-route-a",
            )
            register_operator_certificate_source(
                name="selected",
                certificate_path=cert_a,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            set_operator_certificate_source_secret(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                name="selected",
                secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            select_operator_certificate_source(
                name="selected",
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            configure_operator_auth(
                AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a, operator_scope_ports=_OPERATOR_SCOPE_PORTS
            )
            configure_operator_auth(AuthProviderKind.CLAVE_MOVIL.value, operator_scope_ports=_OPERATOR_SCOPE_PORTS)

            ambient_before = _OPERATOR_SCOPE_PORTS.session.current()
            assert ambient_before is not None
            assert ambient_before.bucket_id == _BUCKET_ID

            degraded_credentials = resolve_active_certificate_credentials(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                settings=settings_b,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            )
            degraded_provider = select_provider(
                AuthProviderKind.CERTIFICATE,
                settings=settings_b,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            ).describe()

            assert degraded_credentials.certificate_path is None
            assert degraded_credentials.password is None
            assert degraded_credentials.source_name is None
            assert degraded_provider.configured is False
            assert degraded_provider.available is False

            for verdict_operation in (
                lambda: check_operator_certificate_sources(
                    certificate_secret_backend_factory=certificate_secret_backend_factory,
                    settings=settings_b,
                    operator_probe_ports=_OPERATOR_PROBE_PORTS,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                ),
                lambda: run_operator_auth_test(
                    certificate_secret_backend_factory=certificate_secret_backend_factory,
                    settings=settings_b,
                    operator_probe_ports=_OPERATOR_PROBE_PORTS,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                ),
                lambda: build_live_auth_preflight_report(
                    certificate_secret_backend_factory=certificate_secret_backend_factory,
                    settings=settings_b,
                    operator_probe_ports=_OPERATOR_PROBE_PORTS,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                ),
            ):
                with pytest.raises(AuthOperationRequiresCustodySessionError) as raised:
                    verdict_operation()
                context = raised.value.context
                assert context is not None
                assert context["bucket_id"] == _BUCKET_ID
                assert root_b_fixture.name in str(context["storage_root"])
                assert root_a_fixture.name not in str(context["storage_root"])

            ambient_after = _OPERATOR_SCOPE_PORTS.session.current()
            assert ambient_after == ambient_before
            assert ambient_after.bucket_id == _BUCKET_ID
            assert cert_a.exists()
            assert cert_b.exists()


def test_preloaded_state_never_combines_its_certificate_path_with_another_bucket_secret(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """A retained state snapshot has no authority to read a later bucket's secret."""
    with _certificate_indexed_authority_for_test().operation() as _certificate_authority_operation_for_test:
        _register_operator_profile()
        now = datetime.now(UTC)
        cert_a = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="retained-state-a",
            subject_cn="retained-state-a",
            password=CERTIFICATE_BUNDLE_INPUT_B,
        )
        register_operator_certificate_source(
            name="selected",
            certificate_path=cert_a,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="selected",
            secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        select_operator_certificate_source(
            name="selected",
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        configure_operator_auth(
            AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a, operator_scope_ports=_OPERATOR_SCOPE_PORTS
        )
        workflow_state_repository().update(
            lambda state: update_auth(
                state,
                provider=AuthProviderKind.CERTIFICATE.value,
                authenticated=True,
            ),
        )
        retained_state_a = workflow_state_repository().load()
        assert retained_state_a.auth.authenticated_at is not None

        with open_test_profile_session(_BUCKET_B):
            register_minimal_profile(
                profile_id=_BUCKET_B,
                display_name="gestor-retained-state-b",
            )
            cert_b = build_pkcs12_bundle(
                tmp_path,
                not_valid_before=now - timedelta(days=1),
                not_valid_after=now + timedelta(days=200),
                name="retained-state-b",
                subject_cn="retained-state-b",
                password=CERTIFICATE_BUNDLE_INPUT_B,
            )
            register_operator_certificate_source(
                name="selected",
                certificate_path=cert_b,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            set_operator_certificate_source_secret(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                name="selected",
                secret=SecretStr(CERTIFICATE_BUNDLE_INPUT_B),
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            select_operator_certificate_source(
                name="selected",
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            configure_operator_auth(
                AuthProviderKind.CERTIFICATE.value, certificate_path=cert_b, operator_scope_ports=_OPERATOR_SCOPE_PORTS
            )

        with open_test_profile_session(_BUCKET_B):
            projected_credentials = project_active_certificate_credentials(
                retained_state_a,
                settings=load_settings(),
            )
            projection = build_operator_state_projection(
                state=retained_state_a,
                requested_provider=AuthProviderKind.CERTIFICATE.value,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=_OPERATOR_PROBE_PORTS,
                probe_live_backend=True,
                include_workspace_summary=False,
                include_pending_obligations=False,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            )

        assert projected_credentials.certificate_path == cert_a
        assert projected_credentials.source_name == "selected"
        assert projected_credentials.password is None
        assert projection.auth.certificate_path == str(cert_a)
        assert projection.auth.available is False
        assert projection.auth.health_summary == ""


def test_resolved_credential_snapshot_survives_an_intervening_source_selection(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    with _certificate_indexed_authority_for_test().operation() as _certificate_authority_operation_for_test:
        _register_operator_profile()
        now = datetime.now(UTC)
        cert_a = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="snapshot-a",
            subject_cn="snapshot-a",
            password=CERTIFICATE_BUNDLE_INPUT,
        )
        cert_b = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="snapshot-b",
            subject_cn="snapshot-b",
            password=CERTIFICATE_BUNDLE_INPUT_B,
        )
        register_operator_certificate_source(
            name="source-a",
            certificate_path=cert_a,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="source-a",
            secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        select_operator_certificate_source(
            name="source-a",
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        configure_operator_auth(
            AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a, operator_scope_ports=_OPERATOR_SCOPE_PORTS
        )
        snapshot_a = resolve_active_certificate_credentials(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

        register_operator_certificate_source(
            name="source-b",
            certificate_path=cert_b,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="source-b",
            secret=SecretStr(CERTIFICATE_BUNDLE_INPUT_B),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        select_operator_certificate_source(
            name="source-b",
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        snapshot_b = resolve_active_certificate_credentials(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

        probe_a = probe_provider_credentials(
            AuthProviderKind.CERTIFICATE.value,
            str(snapshot_a.certificate_path or ""),
            settings=load_settings(),
            certificate_credentials=snapshot_a,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
        )
        probe_b = probe_provider_credentials(
            AuthProviderKind.CERTIFICATE.value,
            str(snapshot_b.certificate_path or ""),
            settings=load_settings(),
            certificate_credentials=snapshot_b,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
        )

        assert snapshot_a.source_name == "source-a"
        assert snapshot_a.certificate_path == cert_a
        assert snapshot_b.source_name == "source-b"
        assert snapshot_b.certificate_path == cert_b
        assert probe_a.result == ProviderProbeResult.OK
        assert probe_b.result == ProviderProbeResult.OK


def test_auth_projection_span_pins_state_and_credentials_when_pointer_changes(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    with _certificate_indexed_authority_for_test().operation() as _certificate_authority_operation_for_test:
        _register_operator_profile()
        now = datetime.now(UTC)
        cert_a = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="route-snapshot-a",
            subject_cn="route-snapshot-a",
            password=CERTIFICATE_BUNDLE_INPUT,
        )
        register_operator_certificate_source(
            name="selected",
            certificate_path=cert_a,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="selected",
            secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        select_operator_certificate_source(
            name="selected",
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        configure_operator_auth(
            AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a, operator_scope_ports=_OPERATOR_SCOPE_PORTS
        )
        session_captured_at = _NOW
        session_a_path = storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state
        session_store.save(
            session_a_path,
            storage_state={"cookies": [], "origins": []},
            metadata={
                "provider_kind": AuthProviderKind.CERTIFICATE.value,
                "identity_nif": "ROUTE-A",
                "authenticated_at": session_captured_at.isoformat(),
                "idle_deadline": (session_captured_at + timedelta(minutes=30)).isoformat(),
            },
        )

        with open_test_profile_session(_BUCKET_B):
            register_minimal_profile(
                profile_id=_BUCKET_B,
                display_name=_PROFILE_LABEL_B,
            )
            cert_b = build_pkcs12_bundle(
                tmp_path,
                not_valid_before=now - timedelta(days=1),
                not_valid_after=now + timedelta(days=200),
                name="route-snapshot-b",
                subject_cn="route-snapshot-b",
                password=CERTIFICATE_BUNDLE_INPUT_B,
            )
            register_operator_certificate_source(
                name="selected",
                certificate_path=cert_b,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            set_operator_certificate_source_secret(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                name="selected",
                secret=SecretStr(CERTIFICATE_BUNDLE_INPUT_B),
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            select_operator_certificate_source(
                name="selected",
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            configure_operator_auth(
                AuthProviderKind.CERTIFICATE.value, certificate_path=cert_b, operator_scope_ports=_OPERATOR_SCOPE_PORTS
            )
            session_b_path = storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state
            session_store.save(
                session_b_path,
                storage_state={"cookies": [], "origins": []},
                metadata={
                    "provider_kind": AuthProviderKind.CERTIFICATE.value,
                    "identity_nif": "ROUTE-B",
                    "authenticated_at": session_captured_at.isoformat(),
                    "idle_deadline": (session_captured_at + timedelta(minutes=30)).isoformat(),
                },
            )

        settings = load_settings()
        write_pointer(
            settings.cadrumo_storage_root,
            BucketPointer.selected(bucket_id=_BUCKET_ID, transition_revision=1),
        )
        with override_settings(cadrumo_active_profile=None):
            with active_auth_projection_span(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                requested_provider=AuthProviderKind.CERTIFICATE.value,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            ) as snapshot:
                assert snapshot.bucket_id == _BUCKET_ID
                assert snapshot.state is not None
                assert snapshot.certificate_credentials is not None
                write_pointer(
                    settings.cadrumo_storage_root,
                    BucketPointer.selected(bucket_id=_BUCKET_B, transition_revision=2),
                )
                state_after_pointer_change = workflow_state_repository().load()
                credentials_after_pointer_change = resolve_active_certificate_credentials(
                    certificate_secret_backend_factory=certificate_secret_backend_factory,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                )
                projection_after_pointer_change = build_operator_state_projection(
                    auth_snapshot=snapshot,
                    requested_provider=AuthProviderKind.CERTIFICATE.value,
                    certificate_secret_backend_factory=certificate_secret_backend_factory,
                    operator_probe_ports=_OPERATOR_PROBE_PORTS,
                    probe_live_backend=True,
                    include_workspace_summary=False,
                    include_pending_obligations=False,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                )
                session_after_pointer_change = load_persisted_session(
                    load_settings(),
                    AuthProviderKind.CERTIFICATE,
                )
                operator_test_after_pointer_change = run_operator_auth_test(
                    AuthProviderKind.CERTIFICATE.value,
                    certificate_secret_backend_factory=certificate_secret_backend_factory,
                    operator_probe_ports=_OPERATOR_PROBE_PORTS,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                )
                preflight_after_pointer_change = build_live_auth_preflight_report(
                    AuthProviderKind.CERTIFICATE.value,
                    certificate_secret_backend_factory=certificate_secret_backend_factory,
                    operator_probe_ports=_OPERATOR_PROBE_PORTS,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                )

                assert state_after_pointer_change.auth.certificate_path == str(cert_a)
                assert credentials_after_pointer_change.certificate_path == cert_a
                assert credentials_after_pointer_change.password is not None
                assert credentials_after_pointer_change.password.get_secret_value() == CERTIFICATE_BUNDLE_INPUT
                assert projection_after_pointer_change.active_profile.profile_id == _BUCKET_ID
                assert projection_after_pointer_change.auth.certificate_path == str(cert_a)
                assert projection_after_pointer_change.auth.available is True
                assert session_after_pointer_change is not None
                assert session_after_pointer_change.identity_nif == "ROUTE-A"
                # ``AuthTestResult.active_profile`` is an operator-facing display
                # field: it prefers the profile's label and falls back to the bucket
                # UUID. The immutable id is asserted above on the projection, which
                # is where it lives; here the label is the identity, and naming
                # bucket B's label explicitly keeps the pinning claim unambiguous.
                assert operator_test_after_pointer_change.active_profile == _PROFILE_LABEL
                assert operator_test_after_pointer_change.active_profile != _PROFILE_LABEL_B
                assert operator_test_after_pointer_change.certificate_path == str(cert_a)
                assert operator_test_after_pointer_change.persisted_session_present is True
                assert preflight_after_pointer_change.active_profile == _PROFILE_LABEL
                assert preflight_after_pointer_change.certificate_path_configured is True
                assert preflight_after_pointer_change.persisted_session_present is True

            # The pointer now names bucket B, so resolution follows it -- but only
            # once B's custody session is open. The nested active-profile reset
            # keeps the route pointer-driven rather than letting the session
            # helper's own override answer the question under test.
            with (
                open_test_profile_session(_BUCKET_B),
                override_settings(cadrumo_active_profile=None),
            ):
                credentials_after_span = resolve_active_certificate_credentials(
                    certificate_secret_backend_factory=certificate_secret_backend_factory,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                )
                session_after_span = load_persisted_session(load_settings(), AuthProviderKind.CERTIFICATE)
            assert credentials_after_span.certificate_path == cert_b
            assert credentials_after_span.password is not None
            assert credentials_after_span.password.get_secret_value() == CERTIFICATE_BUNDLE_INPUT_B
            assert session_after_span is not None
            assert session_after_span.identity_nif == "ROUTE-B"


def test_explicit_settings_provider_resolution_uses_target_bucket_and_restores_ambient_session(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """Direct provider construction resolves the bucket named by Settings, not ambient state.

    Both roots are the same here, so bucket B's custody session can be opened
    and the original resolution assertions stand unchanged. The unauthenticated
    call is asserted first: naming bucket B in Settings resolves B's material
    or nothing -- never bucket A's, whichever session happens to be ambient.
    """
    with _certificate_indexed_authority_for_test().operation() as _certificate_authority_operation_for_test:
        _register_operator_profile()
        now = datetime.now(UTC)
        cert_a = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="bucket-a",
            subject_cn="bucket-a",
        )
        register_operator_certificate_source(
            name="selected",
            certificate_path=cert_a,
            friendly_name="bucket-a",
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="selected",
            secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        select_operator_certificate_source(
            name="selected",
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        configure_operator_auth(
            AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a, operator_scope_ports=_OPERATOR_SCOPE_PORTS
        )

        with open_test_profile_session(_BUCKET_B):
            register_minimal_profile(
                profile_id=_BUCKET_B,
                display_name="gestor-cert-b",
            )
            cert_b = build_pkcs12_bundle(
                tmp_path,
                not_valid_before=now - timedelta(days=1),
                not_valid_after=now + timedelta(days=200),
                name="bucket-b",
                subject_cn="bucket-b",
                password=CERTIFICATE_BUNDLE_INPUT_B,
            )
            register_operator_certificate_source(
                name="selected",
                certificate_path=cert_b,
                friendly_name="bucket-b",
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            set_operator_certificate_source_secret(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                name="selected",
                secret=SecretStr(CERTIFICATE_BUNDLE_INPUT_B),
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            select_operator_certificate_source(
                name="selected",
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_certificate_authority_operation_for_test,
            )
            configure_operator_auth(
                AuthProviderKind.CERTIFICATE.value, certificate_path=cert_b, operator_scope_ports=_OPERATOR_SCOPE_PORTS
            )

        ambient_before = _OPERATOR_SCOPE_PORTS.session.current()
        assert ambient_before is not None
        assert ambient_before.bucket_id == _BUCKET_ID
        with override_settings(cadrumo_active_profile=_BUCKET_B) as settings_b:
            pass

        unauthenticated = resolve_active_certificate_credentials(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            settings=settings_b,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        assert unauthenticated.certificate_path is None
        assert unauthenticated.password is None
        assert unauthenticated.source_name is None

        with open_test_profile_session(_BUCKET_B):
            credentials = resolve_active_certificate_credentials(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                settings=settings_b,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            )
            provider_description = select_provider(
                AuthProviderKind.CERTIFICATE,
                settings=settings_b,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            ).describe()
            check_report = check_operator_certificate_sources(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                settings=settings_b,
                operator_probe_ports=_OPERATOR_PROBE_PORTS,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            )

        ambient_after = _OPERATOR_SCOPE_PORTS.session.current()
        assert credentials.source_name == "selected"
        assert credentials.certificate_path == cert_b
        assert credentials.password is not None
        assert credentials.password.get_secret_value() == CERTIFICATE_BUNDLE_INPUT_B
        assert credentials.friendly_name == "bucket-b"
        assert provider_description.available is True
        assert len(check_report.entries) == 1
        assert check_report.entries[0].certificate_path == str(cert_b)
        assert check_report.entries[0].result == ProviderProbeResult.OK
        assert ambient_after == ambient_before


def test_unreadable_explicit_settings_target_fails_closed_without_global_fallback(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """An unreadable explicit bucket cannot inherit otherwise valid global credentials.

    The empty result now has two independent causes upstream and the same
    contract downstream: the custody guard declines to answer for a bucket with
    no open session, and the resolver's own refusal handling turns that into an
    empty credential. Neither path may reach for the perfectly valid global
    password sitting in Settings.
    """
    _register_operator_profile()
    now = datetime.now(UTC)
    global_path = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="global-must-not-leak",
        subject_cn="global-must-not-leak",
    )
    with override_settings(
        cadrumo_active_profile=_MISSING_BUCKET,
        cadrumo_certificate_path=global_path,
        cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
    ) as missing_settings:
        pass

    credentials = resolve_active_certificate_credentials(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        settings=missing_settings,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    provider_description = select_provider(
        AuthProviderKind.CERTIFICATE,
        settings=missing_settings,
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    ).describe()

    assert credentials.certificate_path is None
    assert credentials.password is None
    assert credentials.friendly_name is None
    assert credentials.source_name is None
    assert provider_description.configured is False
    assert provider_description.available is False
    assert global_path.exists(), "the valid global bundle stays on disk and still never leaks into the empty result"

    with pytest.raises(AuthOperationRequiresCustodySessionError) as raised_verdict:
        check_operator_certificate_sources(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            settings=missing_settings,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
    context = raised_verdict.value.context
    assert context is not None
    assert context["bucket_id"] == _MISSING_BUCKET


def test_login_refuses_selected_missing_file_before_unrelated_valid_global_certificate(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """Public login applies the selected source path before its local precondition."""
    with _certificate_indexed_authority_for_test().operation() as _certificate_authority_operation_for_test:
        _register_operator_profile()
        now = datetime.now(UTC)
        selected_path = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="selected-missing",
            subject_cn="selected-missing",
        )
        global_path = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="unrelated-global",
            subject_cn="unrelated-global",
        )
        register_operator_certificate_source(
            name="selected",
            certificate_path=selected_path,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        select_operator_certificate_source(
            name="selected",
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        configure_operator_auth(
            AuthProviderKind.CERTIFICATE.value,
            certificate_path=selected_path,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        selected_path.unlink()

        with (
            override_settings(
                cadrumo_certificate_path=global_path,
                cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
                cadrumo_live_tests_enabled="1",
            ),
            pytest.raises(AuthLoginPreconditionError) as raised,
        ):
            asyncio.run(
                login_operator_auth(
                    AuthProviderKind.CERTIFICATE.value,
                    certificate_secret_backend_factory=certificate_secret_backend_factory,
                    browser_session_factory=default_browser_session_factory,
                    operator_probe_ports=_OPERATOR_PROBE_PORTS,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                ),
            )

        assert raised.value.translated_message == "application.auth.operator.login.refused_certificate_file_missing"
        context = raised.value.context
        assert context is not None
        assert context["path"] == str(selected_path)


def test_check_named_source_without_secret_never_inherits_a_valid_global_password(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """A named source without a bound secret fails closed even when the global password would open it."""
    with _certificate_indexed_authority_for_test().operation() as _certificate_authority_operation_for_test:
        _register_operator_profile()
        now = datetime.now(UTC)
        cert_path = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="personal",
            subject_cn="gestor-personal",
        )
        register_operator_certificate_source(
            name="personal",
            certificate_path=cert_path,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        select_operator_certificate_source(
            name="personal",
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )

        with override_settings(cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_INPUT)):
            report = check_operator_certificate_sources(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=_OPERATOR_PROBE_PORTS,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            )

        assert len(report.entries) == 1
        assert report.entries[0].name == "personal"
        assert report.entries[0].result == ProviderProbeResult.CORRUPT


def test_check_named_source_fails_closed_when_secure_storage_cannot_be_read(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """A real corrupt secure-storage index cannot redirect a named source to the valid global password."""
    with _certificate_indexed_authority_for_test().operation() as _certificate_authority_operation_for_test:
        _register_operator_profile()
        now = datetime.now(UTC)
        cert_path = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="personal",
            subject_cn="gestor-personal",
        )
        register_operator_certificate_source(
            name="personal",
            certificate_path=cert_path,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="personal",
            secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        select_operator_certificate_source(
            name="personal",
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        certificate_secret_backend_factory.make_unreadable()
        with override_settings(cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_INPUT)):
            report = check_operator_certificate_sources(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=_OPERATOR_PROBE_PORTS,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            )

        assert len(report.entries) == 1
        assert report.entries[0].name == "personal"
        assert report.entries[0].result == ProviderProbeResult.CORRUPT
