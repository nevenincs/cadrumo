"""Real-behavior tests for the operator-facing auth application services."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...adapters.persistence.storage.master_key._active_session import activate_session
from ...adapters.persistence.storage.master_key._bucket_session import BucketSession
from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...application.user_profile._testing import register_minimal_profile
from ...application.workflow._persistence import workflow_state_repository
from ...core.config import Settings, override_settings
from ...core.i18n import tr
from ...domain.buckets import BucketEventHistoryRepository, BucketEventType
from ...domain.filing import ModeloDraft, ModeloDraftRepository
from ...domain.submission import ModeloDraftStatus
from . import AuthProviderKind
from ._operator import configure_operator_auth, inspect_operator_auth, test_operator_auth
from ._sessions import (
    AuthProfileIdentityMismatchError,
    _assert_active_profile_identity_matches_provider,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]
_BUCKET_ID = "operator"


def _session(*, dek: bytes = b"d" * 32) -> BucketSession:
    return BucketSession.open(
        bucket_id=_BUCKET_ID,
        kek=b"k" * 32,
        dek=dek,
        idle_minutes=15,
        opened_at=datetime.now(UTC),
    )


def test_test_operator_auth_reports_the_active_profile() -> None:
    """`test_operator_auth` is the operator's auth-readiness check. It must
    resolve the active profile so the report tells the user whether auth is
    ready *for their profile* - not return empty profile fields."""

    workflow_state_repository().update(
        lambda state: register_minimal_profile(state, profile_id="operator")
    )

    result = test_operator_auth("certificate")

    assert result.active_profile == "operator"
    assert result.active_profile_registered is True
    assert result.active_profile_record_present is True
    assert result.active_profile_status


def test_auth_status_is_not_blocked_by_unreadable_workspace_drafts() -> None:
    """Auth readiness is local-auth state, not a workspace-wide integrity scan.

    A rotated-key filing draft must be reported by `config repair`, but it
    must not prevent `config auth status` from telling the operator what
    auth provider is configured for the active profile.
    """

    workflow_state_repository().update(
        lambda state: register_minimal_profile(state, profile_id="operator")
    )
    configure_operator_auth("certificate")
    now = datetime.now(UTC)

    with activate_session(_session(dek=b"x" * 32)):
        ModeloDraftRepository().save(
            ModeloDraft(
                draft_id="unreadable-workspace-draft",
                modelo="303",
                period="2026Q1",
                profile_tax_id="00000000T",
                status=ModeloDraftStatus.BORRADOR,
                values=(),
                created_at=now,
                updated_at=now,
                schema_version="test",
            )
        )

    result = inspect_operator_auth("certificate")

    assert result.provider == "certificate"
    assert result.active_profile == "operator"
    assert result.active_profile_registered is True


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=_BUCKET_ID) as settings,
        activate_session(_session()),
    ):
        dispose_engine(settings)
        try:
            yield
        finally:
            dispose_engine(settings)


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
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.AUTH_PROVIDER_CONFIGURED
    ]
    assert matching
    payload = matching[-1].payload
    assert payload["certificate_path"] == str(cert_path)


def test_configure_operator_auth_refuses_when_no_active_profile_bucket() -> None:
    """``configure_operator_auth`` refuses with
    :class:`AuthConfigureNoActiveBucketError` when no active profile
    bucket exists. The bucket-event-history ADR requires every event
    to be scoped to a bucket id; running provider configuration before
    ``aeat config profile create NAME`` activates a profile would either silently drop
    the audit event or require deferred replay. Surfacing the refusal
    at the application service keeps the bootstrap order explicit and
    leaves no audit hole."""

    from ._operator import AuthConfigureNoActiveBucketError

    with override_settings(aeat_active_profile=None), pytest.raises(
        AuthConfigureNoActiveBucketError,
        match=r"aeat config profile create NAME",
    ):
        configure_operator_auth("certificate")

    catalogue = BucketEventHistoryRepository().load()
    typed_auth_events = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.AUTH_PROVIDER_CONFIGURED
    ]
    assert typed_auth_events == []


def test_configure_operator_auth_reserved_provider_emits_no_event() -> None:
    """Reserved-provider slots (``clave_pin``, ``clave_permanente``,
    ``dnie_pkcs``) must "fail closed without mutating config,
    credentials, sessions, locks, or events" per the config-auth-shape
    ADR. Surfacing the refusal must precede every persisted side
    effect."""

    from ._operator import AuthProviderReservedError

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
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.AUTH_PROVIDER_CONFIGURED
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    monkeypatch.setenv("AEAT_CERTIFICATE_PATH", str(cert_path))

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


def test_inspect_operator_auth_configured_false_when_backend_path_unset(tmp_path: Path) -> None:
    """``configured`` must stay coherent with ``health_summary``.

    Regression for the self-contradictory ``auth status`` output where
    ``configured: True`` co-existed with ``health_summary: certificate
    path not configured``. A certificate path recorded only in workflow
    state, while the live backend probe (sourced from
    ``Settings.aeat_certificate_path``) sees no path, must NOT report
    ``configured: True`` — that contradicts the health summary the same
    probe produces.
    """

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
    cert_path = tmp_path / "operator.p12"
    cert_path.write_bytes(b"placeholder cert")

    configure_operator_auth("certificate", certificate_path=cert_path)

    result = inspect_operator_auth()

    assert result.provider == "certificate"
    assert result.health_summary == "certificate path not configured"
    assert result.configured is False, (
        "configured must be False when the health probe reports the path is not "
        f"configured — got configured={result.configured!r}, "
        f"health_summary={result.health_summary!r}"
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
    probe = test_operator_auth()

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

    probe = test_operator_auth()

    assert probe.provider == "certificate"


def test_auth_test_probes_explicitly_requested_provider() -> None:
    """``auth test --provider clave_movil`` actively probes the requested
    provider even when nothing is configured in workflow state."""

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))

    probe = test_operator_auth("clave_movil")

    assert probe.provider == "clave_movil"


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
    probe = test_operator_auth()

    # The probe fields are an ``auth test`` exclusive — not on the
    # ``auth status`` result shape.
    status_fields = set(status.model_dump())
    probe_fields = set(probe.model_dump())
    assert "persisted_session_present" not in status_fields
    assert {"persisted_session_present", "persisted_session_expired", "probe_summary"} <= probe_fields

    # No login has been performed, so there is no persisted token.
    assert probe.persisted_session_present is False
    assert probe.persisted_session_expired is None
    assert probe.probe_summary != ""


def test_configure_clave_movil_mismatch_carries_an_explanatory_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        )
    )
    monkeypatch.setenv("AEAT_CLAVE_MOVIL_DNI_NIE", "00000001R")

    result = configure_operator_auth("clave_movil")

    assert result.identity_alignment == "mismatch"
    assert result.identity_alignment_detail != ""
    assert "00000000T" in result.identity_alignment_detail
    assert "00000001R" in result.identity_alignment_detail
    assert "auth test" not in result.next_action, (
        "a misaligned Cl@ve identity cannot pass auth test; the next "
        f"action must route to the fix — got {result.next_action!r}"
    )


def test_configure_clave_movil_match_carries_no_alignment_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the Cl@ve identity matches the profile there is nothing to explain."""

    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id="operator",
            overrides={"identity.tax_id": "12345678Z"},
        )
    )
    monkeypatch.setenv("AEAT_CLAVE_MOVIL_DNI_NIE", "12345678Z")

    result = configure_operator_auth("clave_movil")

    assert result.identity_alignment == "matches"
    assert result.identity_alignment_detail == ""


def test_clave_live_auth_guard_accepts_matching_active_profile_identity() -> None:
    """A Cl@ve live read may proceed only when the active profile owns the Cl@ve identity."""

    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id="operator",
            overrides={"identity.tax_id": "12345678Z"},
        )
    )
    settings = Settings().model_copy(update={"aeat_clave_movil_dni_nie": "12345678Z"})

    assert (
        _assert_active_profile_identity_matches_provider(settings, AuthProviderKind.CLAVE_MOVIL)
        == "12345678Z"
    )


def test_clave_live_auth_guard_rejects_mismatched_active_profile_identity() -> None:
    """A Cl@ve session for one taxpayer must never be persisted under another profile."""

    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id="operator",
            overrides={"identity.tax_id": "00000000T"},
        )
    )
    settings = Settings().model_copy(update={"aeat_clave_movil_dni_nie": "00000001R"})

    with pytest.raises(AuthProfileIdentityMismatchError) as raised:
        _assert_active_profile_identity_matches_provider(settings, AuthProviderKind.CLAVE_MOVIL)
    # The refusal text is routed through the locale system so it honours
    # the profile language (persona-fleet finding G3); assert it equals
    # the localised string for the canonical key rather than a
    # hard-coded English fragment.
    assert str(raised.value) == tr(
        "application.auth.sessions.errors.clave_identity_profile_mismatch"
    )


def test_configure_operator_auth_repeated_calls_append_distinct_events() -> None:
    """Repeated ``configure_operator_auth`` calls append distinct events
    to the append-only catalogue. The bucket-event-history ADR records
    immutable ids; two emissions that share content but differ in
    timestamp produce two distinct ``event_id`` hashes by construction
    because ``derive_bucket_event_id`` mixes the timestamp into the
    digest."""

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))

    configure_operator_auth("certificate")
    configure_operator_auth("certificate")

    catalogue = BucketEventHistoryRepository().load()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.AUTH_PROVIDER_CONFIGURED
    ]
    assert len(matching) >= 2
    ids = {event.event_id for event in matching}
    assert len(ids) == len(matching)
