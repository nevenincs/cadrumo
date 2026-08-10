"""Identity contract for the auth-configure result payload."""

from __future__ import annotations

import pytest

from ....application.auth import AuthConfigureResult
from .._config_payloads import AuthConfigurePayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_auth_configure_result_does_not_duplicate_the_envelope_profile_identity() -> None:
    """The result carries readiness booleans, never an internal profile id."""
    result = AuthConfigureResult(
        provider="clave_movil",
        complete=False,
        profile_tax_id_present=True,
        provider_identity_present=False,
        identity_alignment="clave_identity_missing",
    )

    payload = AuthConfigurePayload.from_result(result).model_dump(mode="json")

    assert payload["profile_tax_id_present"] is True
    assert "active_profile" not in payload
