"""Real-behavior tests for the operator-facing auth application services."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ...adapters.persistence.storage import EphemeralMasterKeyProvider, override_master_key_provider
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
    override_master_key_provider(EphemeralMasterKeyProvider())
    try:
        yield
    finally:
        override_master_key_provider(None)
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


def test_configure_operator_auth_without_active_profile_records_no_typed_event() -> None:
    """When no active profile bucket exists yet (early bootstrap), the
    workflow-state-internal event log still records the transition but
    the typed catalogue receives no AUTH_PROVIDER_CONFIGURED event,
    because there is no bucket to scope it to. The bucket-event-history
    ADR requires every event to carry a bucket id."""

    configure_operator_auth("certificate")

    catalogue = BucketEventHistoryRepository().load()
    typed_auth_events = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.AUTH_PROVIDER_CONFIGURED
    ]
    assert typed_auth_events == []
