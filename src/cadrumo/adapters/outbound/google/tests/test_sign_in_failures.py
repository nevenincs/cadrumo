"""Every Google sign-in failure maps to one closed category, by type and condition, never by text."""

from __future__ import annotations

import socket
import ssl
from pathlib import Path

import pytest
import requests
from google.auth.exceptions import TransportError

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory
from cadrumo_client.contracts.google_auth import (
    GoogleAuthClientMetadataUnavailableError,
    GoogleAuthPreconditionCondition,
)

from ...storage.errors import OutboundStorageNotFoundError, OutboundStorageQuotaError
from ..installation_client import load_installation_client
from ..sign_in_failures import google_condition_category, google_failure_category
from .installation_client_support import use_absent_installation_client

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_every_sign_in_refusal_condition_has_a_category() -> None:
    for condition in GoogleAuthPreconditionCondition:
        assert google_condition_category(condition.value) is not None
    assert google_condition_category("google.auth.not_a_condition") is None


def _chained(outer: Exception, cause: BaseException) -> Exception:
    outer.__cause__ = cause
    return outer


@pytest.mark.parametrize(
    ("error", "category"),
    (
        (_chained(TransportError("refresh failed"), ssl.SSLError("bad certificate")), "secure_connection_failed"),
        (_chained(TransportError("refresh failed"), socket.gaierror(socket.EAI_NONAME, "no name")), "offline"),
        (_chained(TransportError("refresh failed"), ConnectionRefusedError("refused")), "host_unreachable"),
        (requests.exceptions.ProxyError("proxy refused"), "blocked_by_network"),
        (OutboundStorageNotFoundError("gone"), "needs_sign_in"),
        (OutboundStorageQuotaError("slow down"), "unexpected"),
        (ValueError("anything else"), "unexpected"),
    ),
    ids=("tls", "dns", "refused", "proxy", "drive-not-found", "drive-quota", "other"),
)
def test_failures_map_to_their_category_by_type(error: Exception, category: str) -> None:
    assert google_failure_category(error) is DependencyFailureCategory(category)


def test_a_typed_refusal_maps_through_its_condition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_absent_installation_client(monkeypatch, tmp_path / "installation")
    with pytest.raises(GoogleAuthClientMetadataUnavailableError) as refused:
        load_installation_client()

    assert google_failure_category(refused.value) is DependencyFailureCategory.NOT_IN_THIS_BUILD
