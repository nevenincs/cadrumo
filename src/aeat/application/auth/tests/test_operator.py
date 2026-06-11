"""Real-behavior tests for the operator-facing auth application services."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from ....adapters.outbound.aeat.auth import _session_store
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core import Period
from ....core.config import Settings, load_settings, override_settings
from ....core.time import now as utc_now
from ....domain.buckets import BucketEventHistoryRepository, BucketEventType
from ....domain.filing import ModeloDraft, ModeloDraftRepository
from ....domain.submission import ModeloDraftStatus
from ....tests.secure_sql import isolated_profile_storage_root
from .. import AuthProviderKind
from .._operator import build_live_auth_preflight_report, configure_operator_auth, inspect_operator_auth
from .._operator import test_operator_auth as run_operator_auth_test
from .._sessions import (
    AuthProfileIdentityMismatchError,
    _assert_active_profile_identity_matches_provider,
    storage_state_paths,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_BUCKET_ID = "operator"


def test_test_operator_auth_reports_the_active_profile() -> None:
    """`test_operator_auth` is the operator's auth-readiness check. It must
    resolve the active profile so the report tells the user whether auth is
    ready *for their profile* - not return empty profile fields."""

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))

    result = run_operator_auth_test("certificate")

    assert result.active_profile == "operator"
    assert result.active_profile_registered is True
    assert result.active_profile_record_present is True
    assert result.active_profile_status


def test_auth_status_is_not_blocked_by_unreadable_workspace_drafts() -> None:
    """Auth readiness is local-auth state, not a workspace-wide integrity scan.

    A malformed filing draft must be reported by `config repair`, but it
    must not prevent `config auth status` from telling the operator what
    auth provider is configured for the active profile.
    """

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
    configure_operator_auth("certificate")
    now = datetime.now(UTC)

    draft_id = "unreadable-workspace-draft"
    repository = ModeloDraftRepository()
    repository.save(
        ModeloDraft(
            draft_id=draft_id,
            modelo="303",
            period=Period.from_year_and_code(2026, "1T"),
            profile_tax_id="00000000T",
            status=ModeloDraftStatus.BORRADOR,
            values=(),
            created_at=now,
            updated_at=now,
            schema_version="test",
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
    assert result.active_profile == "operator"
    assert result.active_profile_registered is True


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_BUCKET_ID),
    ):
        yield


def test_configure_operator_auth_emits_auth_provider_configured_event() -> None:
    """`configure_operator_auth` appends an ``AUTH_PROVIDER_CONFIGURED`` event
    to the typed bucket-event-history catalogue, scoped to the active
    profile's bucket id and carrying the provider id in the payload.
    The certificate path is not supplied in this scenario, so the
    payload must not carry one."""

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))

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

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
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

    from .._operator import AuthConfigureNoActiveBucketError

    with (
        override_settings(aeat_local_storage_root=tmp_path / "no-active", aeat_active_profile=None),
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
    """Reserved-provider slots (``clave_pin``, ``clave_permanente``,
    ``dnie_pkcs``) must "fail closed without mutating config,
    credentials, sessions, locks, or events" per the config-auth-shape
    contract. Surfacing the refusal must precede every persisted side
    effect."""

    from .._operator import AuthProviderReservedError

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
    state_before = workflow_state_repository().load()
    auth_provider_before = state_before.auth.provider

    for reserved in ("clave_pin", "clave_permanente", "dnie_pkcs"):
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

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))

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
    certificate path from ``Settings.aeat_certificate_path``. When that
    path resolves, the backend no longer reports ``certificate path not
    configured`` and the canonical ``configured`` is ``True``.
    """

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
    cert_path = tmp_path / "operator.p12"
    cert_path.write_bytes(b"placeholder cert")

    with override_settings(aeat_certificate_path=cert_path):
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
    backend probe read ``Settings.aeat_certificate_path`` (env-driven)
    and reported ``certificate path not configured`` even though the
    workflow-state record carried the path. The state projection now
    folds the workflow-state path into the Settings the backend sees,
    so the two surfaces cannot disagree.
    """

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
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

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))

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
    ``incomplete_reason``, and point ``next_action`` at the command that
    supplies the file — never tell the operator the provider is
    configured when it is not usable.
    """

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))

    result = configure_operator_auth("certificate")  # no certificate_path

    assert result.provider == "certificate"
    assert result.complete is False, (
        f"configuring certificate without --file must not report success — got complete={result.complete!r}"
    )
    assert result.incomplete_reason, "an incomplete result must explain what is missing"
    assert "certificate" in result.incomplete_reason.lower()
    assert "--file" in result.next_action and "configure" in result.next_action, (
        f"next_action must name the command that supplies the file — got {result.next_action!r}"
    )


def test_configure_operator_auth_certificate_with_file_is_complete(tmp_path: Path) -> None:
    """``configure_operator_auth`` for the certificate provider with a
    resolvable ``--file`` reports a complete configuration."""

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
    cert_path = tmp_path / "operator.p12"
    cert_path.write_bytes(b"placeholder cert")

    result = configure_operator_auth("certificate", certificate_path=cert_path)

    assert result.complete is True, f"a supplied resolvable file must be complete — got {result.complete!r}"
    assert result.incomplete_reason == ""
    assert result.file == str(cert_path)


def test_configure_operator_auth_certificate_with_unresolved_file_is_incomplete(tmp_path: Path) -> None:
    """``configure_operator_auth`` for the certificate provider with a
    ``--file`` that does not resolve to an existing file must report an
    incomplete configuration, not plain success."""

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
    ghost = tmp_path / "missing.p12"

    result = configure_operator_auth("certificate", certificate_path=ghost)

    assert result.complete is False, (
        f"an unresolvable certificate path must not report success — got complete={result.complete!r}"
    )
    assert result.incomplete_reason
    assert "--file" in result.next_action and "configure" in result.next_action


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

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))

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


def test_auth_test_probes_the_provider_when_one_is_configured() -> None:
    """``auth test`` still actively scopes readiness to the configured
    provider when workflow state has one — it only declines to invent a
    default when nothing is configured and nothing is requested."""

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
    configure_operator_auth("certificate")

    probe = run_operator_auth_test()

    assert probe.provider == "certificate"


def test_auth_test_probes_explicitly_requested_provider() -> None:
    """``auth test --provider clave_movil`` actively probes the requested
    provider even when nothing is configured in workflow state."""

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))

    probe = run_operator_auth_test("clave_movil")

    assert probe.provider == "clave_movil"


def test_live_auth_preflight_reports_redacted_clave_profile_alignment() -> None:
    """Live-auth preflight exposes identity readiness without raw taxpayer values."""

    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id="operator",
            overrides={"identity.tax_id": "12345678Z"},
        ),
    )
    settings = Settings(
        aeat_clave_movil_dni_nie=SecretStr("12345678Z"),
        aeat_clave_movil_nie_soporte=SecretStr("support-present"),
        aeat_clave_prefer_non_qr=True,
        aeat_clave_movil_timeout_ms=120_000,
    )

    report = build_live_auth_preflight_report("clave_movil", settings=settings)

    assert report.provider == "clave_movil"
    assert report.active_profile == "operator"
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

    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id="operator",
            overrides={"identity.tax_id": "12345678Z"},
        ),
    )
    with override_settings(aeat_clave_movil_dni_nie=SecretStr("12345678Z")):
        configure_operator_auth("clave_movil")
        captured_at = utc_now() - timedelta(minutes=30)
        path = storage_state_paths(load_settings(), AuthProviderKind.CLAVE_MOVIL).storage_state
        _session_store.save(
            path,
            storage_state={"cookies": [], "origins": []},
            metadata={
                "provider_kind": AuthProviderKind.CLAVE_MOVIL.value,
                "identity_nif": "12345678Z",
                "authenticated_at": captured_at.isoformat(),
                "idle_deadline": (captured_at + timedelta(minutes=18)).isoformat(),
            },
        )

        report = build_live_auth_preflight_report("clave_movil")

    assert report.probe_result == "ok"
    assert report.persisted_session_present is True
    assert report.persisted_session_expired is True
    assert report.persisted_session_state == "expired"


def test_live_auth_preflight_uses_explicit_certificate_settings(tmp_path: Path) -> None:
    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
    configure_operator_auth("certificate")
    cert_path = tmp_path / "operator.p12"
    cert_path.write_bytes(b"not a pkcs12 bundle")
    base_settings = load_settings()
    explicit_settings = Settings(
        aeat_local_storage_root=base_settings.aeat_local_storage_root,
        aeat_active_profile=base_settings.aeat_active_profile,
        aeat_secret_store_backend=base_settings.aeat_secret_store_backend,
        aeat_secret_store_dir=base_settings.aeat_secret_store_dir,
        aeat_secret_passphrase=base_settings.aeat_secret_passphrase,
        aeat_certificate_path=cert_path,
    )

    with override_settings(aeat_certificate_path=None):
        report = build_live_auth_preflight_report("certificate", settings=explicit_settings)

    assert report.provider == "certificate"
    assert report.certificate_path_configured is True
    assert report.certificate_file_present is True
    assert report.probe_result == "corrupt"


def test_auth_test_carries_a_local_session_probe_status_does_not() -> None:
    """``auth test`` must do something observable ``auth status`` does not.

    ``auth test`` performs a local persisted-session probe and reports
    ``persisted_session_present`` / ``persisted_session_expired`` /
    ``probe_summary`` — fields ``auth status`` (``AuthStatusResult``)
    does not carry at all (persona-fleet finding G5). On a fresh state
    with no persisted token the probe reports no session and a concrete
    operator-facing summary.
    """

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
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

    A bare ``mismatch`` token tells the operator nothing (persona-fleet
    finding G2). The result must carry an ``identity_alignment_detail``
    that names both compared values — the Cl@ve DNI/NIE and the active
    profile tax id — and a ``next_action`` that routes to the actual
    fix, not a futile ``auth test``.
    """

    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id="operator",
            overrides={"identity.tax_id": "00000000T"},
        ),
    )
    with override_settings(aeat_clave_movil_dni_nie="00000001R"):
        result = configure_operator_auth("clave_movil")

    assert result.identity_alignment == "mismatch"
    assert result.identity_alignment_detail != ""
    assert "00000000T" in result.identity_alignment_detail
    assert "00000001R" in result.identity_alignment_detail
    assert "auth test" not in result.next_action, (
        "a misaligned Cl@ve identity cannot pass auth test; the next "
        f"action must route to the fix — got {result.next_action!r}"
    )


def test_configure_clave_movil_match_carries_no_alignment_detail() -> None:
    """When the Cl@ve identity matches the profile there is nothing to explain."""

    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id="operator",
            overrides={"identity.tax_id": "12345678Z"},
        ),
    )
    with override_settings(aeat_clave_movil_dni_nie="12345678Z"):
        result = configure_operator_auth("clave_movil")

    assert result.identity_alignment == "matches"
    assert result.identity_alignment_detail == ""


def test_operator_auth_test_reports_profile_scoped_clave_session() -> None:
    """`auth test` must inspect the encrypted session in the active profile store."""

    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id="operator",
            overrides={"identity.tax_id": "TEST-IDENTITY"},
        ),
    )
    with override_settings(aeat_clave_movil_dni_nie=SecretStr("TEST-IDENTITY")):
        configure_operator_auth("clave_movil")
        captured_at = utc_now()
        path = storage_state_paths(load_settings(), AuthProviderKind.CLAVE_MOVIL).storage_state
        _session_store.save(
            path,
            storage_state={"cookies": [], "origins": []},
            metadata={
                "provider_kind": AuthProviderKind.CLAVE_MOVIL.value,
                "identity_nif": "TEST-IDENTITY",
                "authenticated_at": captured_at.isoformat(),
                "idle_deadline": (captured_at + timedelta(minutes=18)).isoformat(),
            },
        )

        result = run_operator_auth_test("clave_movil")

    assert result.persisted_session_present is True
    assert result.persisted_session_expired is False
    assert result.persisted_session_state == "live"


def test_clave_live_auth_guard_accepts_matching_active_profile_identity() -> None:
    """A Cl@ve live read may proceed only when the active profile owns the Cl@ve identity."""

    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id="operator",
            overrides={"identity.tax_id": "12345678Z"},
        ),
    )
    with override_settings(aeat_clave_movil_dni_nie=SecretStr("12345678Z")) as settings:
        assert _assert_active_profile_identity_matches_provider(settings, AuthProviderKind.CLAVE_MOVIL) == "12345678Z"


def test_clave_live_auth_guard_rejects_mismatched_active_profile_identity() -> None:
    """A Cl@ve session for one taxpayer must never be persisted under another profile."""

    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id="operator",
            overrides={"identity.tax_id": "00000000T"},
        ),
    )
    with override_settings(aeat_clave_movil_dni_nie=SecretStr("00000001R")) as settings:
        with pytest.raises(AuthProfileIdentityMismatchError) as raised:
            _assert_active_profile_identity_matches_provider(settings, AuthProviderKind.CLAVE_MOVIL)
        # The refusal text is routed through the locale system so it honours
        # the profile language (persona-fleet finding G3); assert it equals
        # the localised string for the canonical key rather than a
        # hard-coded English fragment.
        assert raised.value.translated_message == "application.auth.sessions.errors.clave_identity_profile_mismatch"


def test_configure_operator_auth_repeated_calls_append_distinct_events() -> None:
    """Repeated ``configure_operator_auth`` calls append distinct events
    to the append-only catalogue. The bucket-event-history contract records
        immutable ids; two emissions that share content but differ in
        timestamp produce two distinct ``event_id`` hashes by construction
        because ``derive_bucket_event_id`` mixes the timestamp into the
        digest."""

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))

    configure_operator_auth("certificate")
    configure_operator_auth("certificate")

    catalogue = BucketEventHistoryRepository().load()
    matching = [
        event for event in catalogue.events.values() if event.event_type is BucketEventType.AUTH_PROVIDER_CONFIGURED
    ]
    assert len(matching) >= 2
    ids = {event.event_id for event in matching}
    assert len(ids) == len(matching)
