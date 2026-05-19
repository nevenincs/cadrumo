"""Real-behavior tests for the operator-facing auth application services."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ...adapters.persistence.storage import EphemeralMasterKeyProvider
from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...application.user_profile._testing import register_minimal_profile
from ...application.workflow._persistence import workflow_state_repository
from ...domain.buckets import BucketEventHistoryRepository, BucketEventType
from ._operator import configure_operator_auth

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'auth-operator.db').as_posix()}")
    dispose_engine()
    with EphemeralMasterKeyProvider():
        try:
            yield
        finally:
            dispose_engine()


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
    ``aeat config init`` activates a profile would either silently drop
    the audit event or require deferred replay. Surfacing the refusal
    at the application service keeps the bootstrap order explicit and
    leaves no audit hole."""

    from ._operator import AuthConfigureNoActiveBucketError

    with pytest.raises(AuthConfigureNoActiveBucketError, match=r"aeat config init"):
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
