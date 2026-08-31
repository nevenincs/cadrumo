"""Real-behavior tests for the operator-facing auth application services."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from ....adapters.outbound.aeat.auth import session_store
from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.filing_drafts import ModeloDraftRepository
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....core.auth_provider import AuthProviderKind, ClaveMovilRoute
from ....core.config import Settings, load_settings, override_settings
from ....core.operator_action_enums import NoRecoveryOutcome
from ....core.period import Period
from ....core.time.clock import frozen_clock
from ....domain.buckets.event import BucketEventType
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.filing.schema import ModeloDraft, compute_modelo_draft_id, registry_schema_version
from ....domain.submission.models import ModeloDraftStatus
from ....tests.profile_storage_root_fixture import bucket_session_storage_fixture
from ....tests.user_profile import register_minimal_profile
from ..._state_projection_auth import ProjectionAuthReadiness
from ...workflow.persistence import workflow_state_repository
from ..acquisition_lock import acquire_auth_acquisition_lock, auth_acquisition_lock_path
from ..certificate_source_operations import register_operator_certificate_source, set_operator_certificate_source_secret
from ..credentials import active_auth_projection_span, resolve_certificate_source_secret
from ..operator import (
    build_live_auth_preflight_report,
    configure_operator_auth,
    inspect_operator_auth,
    login_operator_auth,
    reset_operator_auth,
)
from ..operator import test_operator_auth as run_operator_auth_test
from ..operator_probes import ProviderConfigurationProbe
from ..operator_results import AuthLoginPreconditionError, AuthTestResult, LiveAuthPreflightReport
from ..probes import ProviderProbeResult
from ..sessions import (
    AuthProfileIdentityMismatchError,
    _prepare_clave_auth,
    storage_state_paths,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_PROFILE_LABEL = "operator"
_DRAFT_STORAGE_WRITTEN_AT = datetime(2026, 5, 26, 10, 0, 0, tzinfo=UTC)
_SESSION_PROBE_NOW = datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC)
_EXPIRED_SESSION_AUTHENTICATED_AT = _SESSION_PROBE_NOW - timedelta(minutes=30)
_LIVE_SESSION_AUTHENTICATED_AT = _SESSION_PROBE_NOW - timedelta(minutes=5)


def _register_operator_profile() -> None:
    """Publish the operator profile capsule before anything reads its bucket."""
    register_minimal_profile(
        profile_id=_BUCKET_ID,
        display_name=_PROFILE_LABEL,
    )


def test_test_operator_auth_reports_the_active_profile() -> None:
    """`test_operator_auth` is the operator's auth-readiness check. It must
    resolve the active profile so the report tells the user whether auth is
    ready *for their profile* - not return empty profile fields."""

    _register_operator_profile()

    result = run_operator_auth_test("certificate")

    assert result.active_profile == _PROFILE_LABEL
    assert result.active_profile_registered is True
    assert result.active_profile_record_present is True
    assert result.active_profile_status


def test_auth_status_preserves_the_active_profile_typed_verdict() -> None:
    """Auth status forwards the state projection verdict without recovery prose."""

    result = inspect_operator_auth("certificate")

    assert not hasattr(result, "active_profile_next_action")
    verdict = result.active_profile_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "profile.active.pointer_registered"
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


def test_auth_status_is_not_blocked_by_unreadable_workspace_drafts() -> None:
    """Auth readiness is local-auth state, not a workspace-wide integrity scan.

    A malformed filing draft must be reported by `config repair`, but it
    must not prevent `config auth status` from telling the operator what
    auth provider is configured for the active profile.
    """

    _register_operator_profile()
    configure_operator_auth("certificate")
    now = _DRAFT_STORAGE_WRITTEN_AT

    period = Period.from_year_and_code(2026, "1T")
    snapshot_ref = RegistrySnapshotRef(
        modelo="303",
        revision_id="2026-v1",
        modelo_year=2026,
        period="1T",
    )
    # The repository files a draft under its content address, so the corrupted
    # row this test writes must be keyed by the same derived id.
    draft_id = compute_modelo_draft_id(
        modelo="303",
        period=period,
        profile_tax_id="00000000T",
        snapshot_ref=snapshot_ref,
        values=(),
    )
    repository = ModeloDraftRepository()
    repository.save(
        ModeloDraft(
            draft_id=draft_id,
            modelo="303",
            period=period,
            profile_tax_id="00000000T",
            subject_tax_id="00000000T",
            snapshot_ref=snapshot_ref,
            status=ModeloDraftStatus.BORRADOR,
            values=(),
            created_at=now,
            updated_at=now,
            schema_version=registry_schema_version(modelo="303", revision_id="2026-v1"),
        ),
    )
    secure_object_repository_for_active_bucket().save(
        namespace=ModeloDraftRepository.namespace,
        object_key=draft_id,
        classification=ModeloDraftRepository.sensitivity,
        schema_version=ModeloDraftRepository.schema_version,
        written_at=now,
        payload=b"{not-json",
    )

    result = inspect_operator_auth("certificate")

    assert result.provider == "certificate"
    assert result.active_profile == _PROFILE_LABEL
    assert result.active_profile_registered is True


_isolated_backend = bucket_session_storage_fixture(_BUCKET_ID)


def test_configure_operator_auth_emits_auth_provider_configured_event() -> None:
    """`configure_operator_auth` appends an ``AUTH_PROVIDER_CONFIGURED`` event
    to the typed bucket-event-history catalogue, scoped to the active
    profile's bucket id and carrying the provider id in the payload.
    The certificate path is not supplied in this scenario, so the
    payload must not carry one."""

    _register_operator_profile()

    configure_operator_auth("certificate")

    state = workflow_state_repository().load()
    active_bucket_id = state.active_profile_bucket_id()
    assert active_bucket_id is not None

    catalogue = BucketEventHistoryRepository().load()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.AUTH_PROVIDER_CONFIGURED and event.bucket_id == active_bucket_id
    ]
    assert matching, [event.event_type for event in catalogue.events.values()]
    payload = matching[-1].payload
    assert payload["provider_id"] == "certificate"
    assert "certificate_path" not in payload


def test_configure_operator_auth_event_payload_records_certificate_path(tmp_path: Path) -> None:
    """When a certificate path is supplied, the typed event payload records
    the filesystem reference. Passwords and key material remain outside
    the payload by construction."""

    _register_operator_profile()
    cert_path = tmp_path / "operator.p12"
    cert_path.write_bytes(b"binary certificate payload")

    configure_operator_auth("certificate", certificate_path=cert_path)

    catalogue = BucketEventHistoryRepository().load()
    matching = [
        event for event in catalogue.events.values() if event.event_type is BucketEventType.AUTH_PROVIDER_CONFIGURED
    ]
    assert matching
    payload = matching[-1].payload
    assert payload["certificate_path"] == str(cert_path)


def test_configure_operator_auth_refuses_when_no_active_profile_bucket(tmp_path: Path) -> None:
    """``configure_operator_auth`` refuses with
        :class:`AuthConfigureNoActiveBucketError` when no active profile
    bucket exists. The bucket-event-history contract requires every event
        to be scoped to a bucket id; running provider configuration before
        ``aeat config profile create NAME`` activates a profile would either silently drop
        the audit event or require deferred replay. Surfacing the refusal
        at the application service keeps the bootstrap order explicit and
        leaves no audit hole."""

    from ..operator_results import AuthConfigureNoActiveBucketError

    # The refusal is exercised against an empty root below, but the audit-hole
    # assertion afterwards reads this profile's real bucket event catalogue, and
    # a catalogue only exists once its capsule is published.
    _register_operator_profile()

    with (
        override_settings(cadrumo_local_storage_root=tmp_path / "no-active", cadrumo_active_profile=None),
        pytest.raises(AuthConfigureNoActiveBucketError) as excinfo,
    ):
        configure_operator_auth("certificate")
    assert excinfo.value.translated_message == "application.auth.operator.errors.no_active_bucket"

    catalogue = BucketEventHistoryRepository().load()
    typed_auth_events = [
        event for event in catalogue.events.values() if event.event_type is BucketEventType.AUTH_PROVIDER_CONFIGURED
    ]
    assert typed_auth_events == []


def test_configure_operator_auth_reserved_provider_emits_no_event() -> None:
    """Reserved-provider slots (``clave_pin``, ``dnie_pkcs``) must "fail
    closed without mutating config, credentials, sessions, locks, or
    events" per the config-auth-shape contract. Surfacing the refusal
    must precede every persisted side effect."""

    from ..operator_results import AuthProviderReservedError

    _register_operator_profile()
    state_before = workflow_state_repository().load()
    auth_provider_before = state_before.auth.provider

    for reserved in ("clave_pin", "dnie_pkcs"):
        with pytest.raises(AuthProviderReservedError):
            configure_operator_auth(reserved)

    state_after = workflow_state_repository().load()
    assert state_after.auth.provider == auth_provider_before

    catalogue = BucketEventHistoryRepository().load()
    typed_auth_events = [
        event for event in catalogue.events.values() if event.event_type is BucketEventType.AUTH_PROVIDER_CONFIGURED
    ]
    assert typed_auth_events == []


def test_inspect_operator_auth_configured_is_false_without_certificate_path() -> None:
    """``inspect_operator_auth`` must report ``configured: False`` when the
    certificate provider is selected but no ``--file`` path has been
    supplied.

    Regression for the self-contradictory ``auth status`` output where
    ``configured: True`` co-existed with ``health_summary: certificate
    path not configured``.  The ``configured`` field must reflect
    operational readiness, not merely that a provider was *selected*;
    for the certificate provider that means a file path must be present
    in workflow state.
    """

    _register_operator_profile()

    configure_operator_auth("certificate")  # no certificate_path argument

    result = inspect_operator_auth()

    assert result.provider == "certificate"
    assert result.configured is False, (
        "configured must be False when certificate_path is absent — "
        f"got configured={result.configured!r}, certificate_path={result.certificate_path!r}, "
        f"health_summary={result.health_summary!r}"
    )
    assert result.certificate_path == ""


def test_inspect_operator_auth_configured_is_true_with_certificate_path(
    tmp_path: Path,
) -> None:
    """``inspect_operator_auth`` reports ``configured: True`` when the
    certificate provider is selected, a ``--file`` path is recorded in
    workflow state, and the backend health probe resolves the same path.

    ``configured`` is operational readiness, and it must stay coherent
    with ``health_summary``: the live backend probe sources the
    certificate path from ``Settings.cadrumo_certificate_path``. When that
    path resolves, the backend no longer reports ``certificate path not
    configured`` and the canonical ``configured`` is ``True``.
    """

    _register_operator_profile()
    cert_path = tmp_path / "operator.p12"
    cert_path.write_bytes(b"placeholder cert")

    with override_settings(cadrumo_certificate_path=cert_path):
        configure_operator_auth("certificate", certificate_path=cert_path)

        result = inspect_operator_auth()

    assert result.provider == "certificate"
    assert result.configured is True, (
        f"configured must be True when certificate_path is set — got {result.configured!r}"
    )
    assert result.certificate_path == str(cert_path)
    assert result.health_summary != "certificate path not configured", (
        "health_summary must not contradict configured: True"
    )


def test_inspect_operator_auth_configured_true_when_path_persisted_to_workflow_state(
    tmp_path: Path,
) -> None:
    """``auth configure`` and ``auth status`` must agree on ``configured``.

    Round-5 B1: ``auth configure --provider certificate --file PATH``
    persists the path to workflow state. Without an env-var override,
    ``auth status`` previously contradicted itself because the live
    backend probe read ``Settings.cadrumo_certificate_path`` (env-driven)
    and reported ``certificate path not configured`` even though the
    workflow-state record carried the path. The state projection now
    folds the workflow-state path into the Settings the backend sees,
    so the two surfaces cannot disagree.
    """

    _register_operator_profile()
    cert_path = tmp_path / "operator.p12"
    cert_path.write_bytes(b"placeholder cert")

    configure_operator_auth("certificate", certificate_path=cert_path)

    result = inspect_operator_auth()

    assert result.provider == "certificate"
    assert result.certificate_path == str(cert_path), (
        f"workflow-state certificate path must surface on status — got {result.certificate_path!r}"
    )
    # The backend may still report a parse error on a fake PKCS#12
    # body, but it must NEVER claim the path is unconfigured when one
    # is persisted in workflow state and the file exists.
    assert "not configured" not in result.health_summary.lower(), (
        "health_summary must not claim the certificate path is unconfigured "
        f"when one is persisted and the file exists — got {result.health_summary!r}"
    )


def test_inspect_operator_auth_distinguishes_no_path_set_from_file_missing(
    tmp_path: Path,
) -> None:
    """Three distinct certificate states must produce three distinct messages.

    Round-5 minor: ``no path set``, ``path set + file missing``, and
    ``path set + file present`` are three different operator failure
    modes and must surface as three different ``health_summary``
    strings. The ``info`` severity is reserved for "no path set" (an
    undeclared state); ``warning`` for "path set, file missing" (a
    degraded state); ``error`` only for genuine faults reported by the
    health classifier (round-5 M5).
    """

    _register_operator_profile()

    # 1) no path set
    configure_operator_auth("certificate")  # no --file
    no_path = inspect_operator_auth()
    assert no_path.configured is False
    assert no_path.health_severity == "info", f"no-path-set must be info, not error — got {no_path.health_severity!r}"
    no_path_summary = no_path.health_summary

    # 2) path set + file missing
    ghost = tmp_path / "missing.p12"
    configure_operator_auth("certificate", certificate_path=ghost)
    missing_file = inspect_operator_auth()
    assert missing_file.configured is False
    assert missing_file.health_severity == "warning", (
        f"path-set + file-missing must be warning — got {missing_file.health_severity!r}"
    )
    assert missing_file.health_summary != no_path_summary, (
        "no-path-set and path-set+file-missing must produce distinct summaries"
    )


def test_configure_operator_auth_certificate_without_file_is_incomplete() -> None:
    """``configure_operator_auth`` for the certificate provider with no
    certificate path must NOT report plain success.

    The certificate provider cannot be used without a certificate file;
    configuring it without ``--file`` records only the provider
    selection. The result must mark itself ``complete=False``, carry an
    ``incomplete_reason``, and retain the application-owned failed
    precondition — never tell the operator the provider is configured when it
    is not usable or invent a command for a file the operator has not chosen.
    """

    _register_operator_profile()

    result = configure_operator_auth("certificate")  # no certificate_path

    assert result.provider == "certificate"
    assert result.complete is False, (
        f"configuring certificate without --file must not report success — got complete={result.complete!r}"
    )
    assert result.incomplete_reason, "an incomplete result must explain what is missing"
    assert "certificate" in result.incomplete_reason.lower()
    assert not hasattr(result, "next_action")
    verdict = result.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "auth.certificate.file_ready"
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.evidence[0].values == {
        "certificate_file_provided": False,
        "certificate_file_resolves": False,
        "provider": "certificate",
    }


def test_configure_operator_auth_certificate_with_file_is_complete(tmp_path: Path) -> None:
    """``configure_operator_auth`` for the certificate provider with a
    resolvable ``--file`` reports a complete configuration."""

    _register_operator_profile()
    cert_path = tmp_path / "operator.p12"
    cert_path.write_bytes(b"placeholder cert")

    result = configure_operator_auth("certificate", certificate_path=cert_path)

    assert result.complete is True, f"a supplied resolvable file must be complete — got {result.complete!r}"
    assert result.incomplete_reason == ""
    assert result.file == str(cert_path)
    assert result.precondition_verdict is None


def test_configure_operator_auth_certificate_with_unresolved_file_is_incomplete(tmp_path: Path) -> None:
    """``configure_operator_auth`` for the certificate provider with a
    ``--file`` that does not resolve to an existing file must report an
    incomplete configuration, not plain success."""

    _register_operator_profile()
    ghost = tmp_path / "missing.p12"

    result = configure_operator_auth("certificate", certificate_path=ghost)

    assert result.complete is False, (
        f"an unresolvable certificate path must not report success — got complete={result.complete!r}"
    )
    assert result.incomplete_reason
    verdict = result.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "auth.certificate.file_ready"
    assert verdict.evidence[0].values["certificate_file_provided"] is True
    assert verdict.evidence[0].values["certificate_file_resolves"] is False


def test_auth_status_and_test_agree_when_no_provider_configured() -> None:
    """``auth status`` and ``auth test`` must report the same state.

    Regression for the cross-surface contradiction where, in a fresh
    state with no provider configured, ``auth status`` reported
    ``provider: ""`` / ``available: False`` while ``auth test``
    silently defaulted to ``clave_movil``, live-probed it, and reported
    ``available: True``. With no provider configured and none
    requested, ``auth test`` must not invent a default — it reports the
    same "no provider configured" state ``auth status`` reports.
    """

    _register_operator_profile()

    status = inspect_operator_auth()
    probe = run_operator_auth_test()

    assert status.provider == ""
    assert status.provider == probe.provider, (
        f"auth status / auth test disagree on provider — status={status.provider!r}, test={probe.provider!r}"
    )
    assert status.available == probe.available, (
        f"auth status / auth test disagree on available — status={status.available}, test={probe.available}"
    )
    assert status.configured == probe.configured
    assert status.health_summary == probe.health_summary


def test_invalid_persisted_provider_fails_closed_across_snapshot_consumers() -> None:
    """A malformed stored selector never escapes the typed projection boundary.

    The real workflow repository persists a non-empty legacy selector that cannot
    hydrate :class:`AuthProviderKind`. The route snapshot must narrow it to
    ``None``; status, test, and live preflight must then expose the same empty,
    unconfigured, unavailable state. Login must refuse at that boundary, before
    any provider or browser-session construction can begin.
    """

    from ...state_projection import build_operator_state_projection

    invalid_selector = "certificate-private-taxpayer-note"
    _register_operator_profile()
    workflow_state_repository().update(
        lambda state: state.model_copy(
            update={
                "auth": state.auth.model_copy(
                    update={"provider": invalid_selector},
                ),
            },
        ),
    )

    with active_auth_projection_span() as snapshot:
        assert snapshot.state is not None
        assert snapshot.state.auth.provider == invalid_selector
        assert snapshot.provider is None
        projection = build_operator_state_projection(
            auth_snapshot=snapshot,
            probe_live_backend=True,
            include_workspace_summary=False,
            include_pending_obligations=False,
        )
        direct_state_projection = build_operator_state_projection(
            state=snapshot.state,
            probe_live_backend=True,
            include_workspace_summary=False,
            include_pending_obligations=False,
        )

    status = inspect_operator_auth()
    probe = run_operator_auth_test()
    preflight = build_live_auth_preflight_report()

    for readiness in (projection.auth, direct_state_projection.auth, status, probe, preflight):
        assert readiness.provider == ""
        assert readiness.configured is False
        assert readiness.available is False
        assert invalid_selector not in readiness.model_dump_json()

    with pytest.raises(AuthLoginPreconditionError) as excinfo:
        asyncio.run(login_operator_auth(pytest_current_test=""))

    assert excinfo.value.translated_message == "application.auth.operator.errors.provider_not_configured"
    assert invalid_selector not in str(excinfo.value)


def test_auth_test_probes_the_provider_when_one_is_configured() -> None:
    """``auth test`` still actively scopes readiness to the configured
    provider when workflow state has one — it only declines to invent a
    default when nothing is configured and nothing is requested."""

    _register_operator_profile()
    configure_operator_auth("certificate")

    probe = run_operator_auth_test()

    assert probe.provider == "certificate"


def test_auth_test_probes_explicitly_requested_provider() -> None:
    """``auth test --provider clave_movil`` actively probes the requested
    provider even when nothing is configured in workflow state."""

    _register_operator_profile()

    probe = run_operator_auth_test("clave_movil")

    assert probe.provider == "clave_movil"


def test_live_auth_preflight_reports_redacted_clave_profile_alignment() -> None:
    """Live-auth preflight exposes identity readiness without raw taxpayer values."""

    register_minimal_profile(
        profile_id=_BUCKET_ID,
        display_name=_PROFILE_LABEL,
        overrides={"identity.tax_id": "12345678Z", "auth.clave_movil_route": ClaveMovilRoute.QR.value},
    )
    settings = load_settings().model_copy(
        update={
            "cadrumo_clave_movil_dni_nie": SecretStr("12345678Z"),
            "cadrumo_clave_movil_nie_soporte": SecretStr("support-present"),
            "cadrumo_clave_prefer_non_qr": True,
            "cadrumo_clave_movil_timeout_ms": 120_000,
        },
    )

    report = build_live_auth_preflight_report("clave_movil", settings=settings)

    assert report.provider == "clave_movil"
    assert report.active_profile == _PROFILE_LABEL
    assert report.profile_tax_id_present is True
    assert report.provider_identity_present is True
    assert report.identity_alignment == "matches"
    assert report.identity_kind == "DNI"
    assert report.auth_mode == "non_qr"
    assert report.prefer_non_qr is True
    assert report.timeout_ms == 120_000
    assert report.nie_soporte_configured is True
    assert report.persisted_session_state == "no_session"
    assert "12345678Z" not in report.model_dump_json()
    assert "support-present" not in report.model_dump_json()


def test_live_auth_preflight_reports_expired_persisted_session_state() -> None:
    """Live preflight must distinguish local Cl@ve config health from session reuse readiness."""

    register_minimal_profile(
        profile_id=_BUCKET_ID,
        display_name=_PROFILE_LABEL,
        overrides={"identity.tax_id": "12345678Z", "auth.clave_movil_route": ClaveMovilRoute.QR.value},
    )
    with override_settings(cadrumo_clave_movil_dni_nie=SecretStr("12345678Z")):
        configure_operator_auth("clave_movil")
        captured_at = _EXPIRED_SESSION_AUTHENTICATED_AT
        path = storage_state_paths(AuthProviderKind.CLAVE_MOVIL).storage_state
        session_store.save(
            path,
            storage_state={"cookies": [], "origins": []},
            metadata={
                "provider_kind": AuthProviderKind.CLAVE_MOVIL.value,
                "identity_nif": "12345678Z",
                "authenticated_at": captured_at.isoformat(),
                "idle_deadline": (captured_at + timedelta(minutes=18)).isoformat(),
            },
        )

        with frozen_clock(_SESSION_PROBE_NOW):
            report = build_live_auth_preflight_report("clave_movil")

    assert report.probe_result is ProviderProbeResult.OK
    assert report.persisted_session_present is True
    assert report.persisted_session_expired is True
    assert report.persisted_session_state == "expired"


def test_live_auth_preflight_uses_explicit_certificate_settings(tmp_path: Path) -> None:
    _register_operator_profile()
    configure_operator_auth("certificate")
    cert_path = tmp_path / "operator.p12"
    cert_path.write_bytes(b"not a pkcs12 bundle")
    base_settings = load_settings()
    explicit_settings = Settings(
        cadrumo_local_storage_root=base_settings.cadrumo_local_storage_root,
        cadrumo_active_profile=base_settings.cadrumo_active_profile,
        cadrumo_secret_store_backend=base_settings.cadrumo_secret_store_backend,
        cadrumo_secret_store_dir=base_settings.cadrumo_secret_store_dir,
        cadrumo_secret_passphrase=base_settings.cadrumo_secret_passphrase,
        cadrumo_certificate_path=cert_path,
    )

    with override_settings(cadrumo_certificate_path=None):
        report = build_live_auth_preflight_report("certificate", settings=explicit_settings)

    assert report.provider == "certificate"
    assert report.certificate_path_configured is True
    assert report.certificate_file_present is True
    assert report.probe_result is ProviderProbeResult.CORRUPT


def test_auth_probe_verdict_contract_refuses_unknown_values() -> None:
    """Readiness projections must not turn malformed provider verdicts into readiness output."""

    invalid_probe_result = {"probe_result": "apparently_ready"}
    with pytest.raises(ValidationError):
        ProjectionAuthReadiness.model_validate(invalid_probe_result)
    with pytest.raises(ValidationError):
        AuthTestResult.model_validate(invalid_probe_result)
    with pytest.raises(ValidationError):
        LiveAuthPreflightReport.model_validate(invalid_probe_result)
    with pytest.raises(ValidationError):
        ProviderConfigurationProbe.model_validate({"provider": "certificate", "result": "apparently_ready"})


def test_auth_test_carries_a_local_session_probe_status_does_not() -> None:
    """``auth test`` must do something observable ``auth status`` does not.

    ``auth test`` performs a local persisted-session probe and reports
    ``persisted_session_present`` / ``persisted_session_expired`` /
    ``probe_summary`` — fields ``auth status`` (``AuthStatusResult``)
    does not carry at all. On a fresh state
    with no persisted token the probe reports no session and a concrete
    operator-facing summary.
    """

    _register_operator_profile()
    configure_operator_auth("certificate")

    status = inspect_operator_auth()
    probe = run_operator_auth_test()

    # The probe fields are an ``auth test`` exclusive — not on the
    # ``auth status`` result shape.
    status_fields = set(status.model_dump())
    probe_fields = set(probe.model_dump())
    assert "persisted_session_present" not in status_fields
    assert {
        "persisted_session_present",
        "persisted_session_expired",
        "persisted_session_state",
        "probe_summary",
    } <= probe_fields

    # No login has been performed, so there is no persisted token.
    assert probe.persisted_session_present is False
    assert probe.persisted_session_expired is None
    assert probe.persisted_session_state == "no_session"
    assert probe.probe_summary != ""


def test_configure_clave_movil_mismatch_carries_an_explanatory_detail() -> None:
    """An ``identity_alignment: mismatch`` must explain what mismatches.

    A bare ``mismatch`` token tells the operator nothing. The result
    must carry an ``identity_alignment_detail`` that names both compared
    values — the Cl@ve DNI/NIE and the active profile tax id — plus an exact
    typed no-recovery outcome because the application cannot choose which
    identity the operator should change.
    """

    register_minimal_profile(
        profile_id=_BUCKET_ID,
        display_name=_PROFILE_LABEL,
        overrides={"identity.tax_id": "00000000T", "auth.clave_movil_route": ClaveMovilRoute.QR.value},
    )
    with override_settings(cadrumo_clave_movil_dni_nie="00000001R"):
        result = configure_operator_auth("clave_movil")

    assert result.identity_alignment == "mismatch"
    assert result.identity_alignment_detail != ""
    assert result.complete is False
    assert result.incomplete_reason == result.identity_alignment_detail
    assert "00000000T" in result.identity_alignment_detail
    assert "00000001R" in result.identity_alignment_detail
    verdict = result.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "auth.clave_movil.identity_aligned"
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.evidence[0].values["identity_alignment"] == "mismatch"


def test_configure_clave_movil_match_carries_no_alignment_detail() -> None:
    """When the Cl@ve identity matches the profile there is nothing to explain."""

    register_minimal_profile(
        profile_id=_BUCKET_ID,
        display_name=_PROFILE_LABEL,
        overrides={"identity.tax_id": "12345678Z", "auth.clave_movil_route": ClaveMovilRoute.QR.value},
    )
    with override_settings(cadrumo_clave_movil_dni_nie="12345678Z"):
        result = configure_operator_auth("clave_movil")

    assert result.identity_alignment == "matches"
    assert result.identity_alignment_detail == ""
    assert result.complete is True
    assert result.incomplete_reason == ""
    assert result.precondition_verdict is None


def test_configure_clave_movil_without_provider_identity_is_incomplete() -> None:
    """Provider selection alone must not claim Cl@ve Móvil is operational."""

    register_minimal_profile(
        profile_id=_BUCKET_ID,
        display_name=_PROFILE_LABEL,
        overrides={"identity.tax_id": "12345678Z", "auth.clave_movil_route": ClaveMovilRoute.QR.value},
    )

    with override_settings(cadrumo_clave_movil_dni_nie=None):
        result = configure_operator_auth("clave_movil")

    assert result.identity_alignment == "clave_identity_missing"
    assert result.complete is False
    assert result.incomplete_reason == result.identity_alignment_detail
    verdict = result.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "auth.clave_movil.identity_aligned"
    assert verdict.evidence[0].values["identity_alignment"] == "clave_identity_missing"


def test_operator_auth_test_reports_profile_scoped_clave_session() -> None:
    """`auth test` must inspect the encrypted session in the active profile store."""

    register_minimal_profile(
        profile_id=_BUCKET_ID, display_name=_PROFILE_LABEL, overrides={"identity.tax_id": "TEST-IDENTITY"}
    )
    with override_settings(cadrumo_clave_movil_dni_nie=SecretStr("TEST-IDENTITY")):
        configure_operator_auth("clave_movil")
        captured_at = _LIVE_SESSION_AUTHENTICATED_AT
        path = storage_state_paths(AuthProviderKind.CLAVE_MOVIL).storage_state
        session_store.save(
            path,
            storage_state={"cookies": [], "origins": []},
            metadata={
                "provider_kind": AuthProviderKind.CLAVE_MOVIL.value,
                "identity_nif": "TEST-IDENTITY",
                "authenticated_at": captured_at.isoformat(),
                "idle_deadline": (captured_at + timedelta(minutes=18)).isoformat(),
            },
        )

        with frozen_clock(_SESSION_PROBE_NOW):
            result = run_operator_auth_test("clave_movil")

    assert result.persisted_session_present is True
    assert result.persisted_session_expired is False
    assert result.persisted_session_state == "live"


def test_clave_live_auth_guard_accepts_matching_active_profile_identity() -> None:
    """A Cl@ve live read may proceed only when the active profile owns the Cl@ve identity."""

    register_minimal_profile(
        profile_id=_BUCKET_ID,
        display_name=_PROFILE_LABEL,
        overrides={"identity.tax_id": "12345678Z", "auth.clave_movil_route": ClaveMovilRoute.QR.value},
    )
    with override_settings(cadrumo_clave_movil_dni_nie=SecretStr("12345678Z")) as settings:
        _bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)
        assert expected_identity == "12345678Z"


def test_clave_live_auth_guard_rejects_mismatched_active_profile_identity() -> None:
    """A Cl@ve session for one taxpayer must never be persisted under another profile."""

    register_minimal_profile(
        profile_id=_BUCKET_ID,
        display_name=_PROFILE_LABEL,
        overrides={"identity.tax_id": "00000000T", "auth.clave_movil_route": ClaveMovilRoute.QR.value},
    )
    with override_settings(cadrumo_clave_movil_dni_nie=SecretStr("00000001R")) as settings:
        with pytest.raises(AuthProfileIdentityMismatchError) as raised:
            _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)
        # The refusal text is routed through the locale system so it honours
        # the profile language; assert it equals
        # the localised string for the canonical key rather than a
        # hard-coded English fragment.
        assert raised.value.translated_message == "application.auth.sessions.errors.clave_identity_profile_mismatch"


def test_reset_provider_scope_removes_only_the_target_provider_artefacts(tmp_path: Path) -> None:
    """A provider-scoped reset clears only the target provider's session, lock, registration, and secret.

    The certificate provider is given a real persisted session, an acquisition
    lock, a named source registration, and its secure-storage secret. An
    unrelated Cl@ve Móvil session and acquisition lock live in the same bucket.
    Resetting the certificate provider must delete every certificate artefact
    and leave every Cl@ve Móvil artefact byte-for-byte in place.
    """

    _register_operator_profile()
    cert_path = tmp_path / "operator.p12"
    cert_path.write_bytes(b"placeholder cert")
    settings = load_settings()

    configure_operator_auth("certificate", certificate_path=cert_path)
    register_operator_certificate_source(name="personal", certificate_path=cert_path)
    set_operator_certificate_source_secret(name="personal", secret=SecretStr("cert-passphrase"))

    certificate_session = storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state
    session_store.save(
        certificate_session,
        storage_state={"cookies": [], "origins": []},
        metadata={"provider_kind": "certificate"},
    )
    unrelated_session = storage_state_paths(AuthProviderKind.CLAVE_MOVIL).storage_state
    session_store.save(
        unrelated_session,
        storage_state={"cookies": [], "origins": []},
        metadata={"provider_kind": "clave_movil"},
    )

    certificate_lock = auth_acquisition_lock_path(settings, AuthProviderKind.CERTIFICATE, bucket_id=_BUCKET_ID)
    clave_lock = auth_acquisition_lock_path(settings, AuthProviderKind.CLAVE_MOVIL, bucket_id=_BUCKET_ID)

    with (
        acquire_auth_acquisition_lock(settings, AuthProviderKind.CERTIFICATE, ttl_seconds=60, operation="target"),
        acquire_auth_acquisition_lock(settings, AuthProviderKind.CLAVE_MOVIL, ttl_seconds=60, operation="unrelated"),
    ):
        assert certificate_lock.is_file()
        assert clave_lock.is_file()

        result = reset_operator_auth(provider="certificate")

        assert certificate_lock.exists() is False
        assert clave_lock.is_file(), "an unrelated provider's acquisition lock must survive a scoped reset"

    state = workflow_state_repository().load()

    assert result.cleared_provider_configuration is True
    assert result.removed_sessions == 1
    assert result.cleared_locks == 1
    assert result.removed_certificate_sources == 1
    assert result.removed_certificate_secrets == 1
    assert session_store.exists(certificate_session) is False
    assert state.auth.certificate_sources == {}
    assert resolve_certificate_source_secret(name="personal", bucket_id=_BUCKET_ID) is None

    assert session_store.exists(unrelated_session) is True, (
        "an unrelated provider's persisted session must survive a scoped reset"
    )


def test_configure_operator_auth_repeated_calls_append_distinct_events() -> None:
    """Repeated ``configure_operator_auth`` calls append distinct events
    to the append-only catalogue. The bucket-event-history contract records
        immutable ids; two emissions that share content but differ in
        timestamp produce two distinct ``event_id`` hashes by construction
        because ``derive_bucket_event_id`` mixes the timestamp into the
        digest."""

    _register_operator_profile()

    configure_operator_auth("certificate")
    configure_operator_auth("certificate")

    catalogue = BucketEventHistoryRepository().load()
    matching = [
        event for event in catalogue.events.values() if event.event_type is BucketEventType.AUTH_PROVIDER_CONFIGURED
    ]
    assert len(matching) >= 2
    ids = {event.event_id for event in matching}
    assert len(ids) == len(matching)
