from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import NoReturn, cast

import pytest
from pydantic import SecretStr

from ......application.auth_credentials import unnamed_certificate_credentials
from ......core.config import Settings
from ..authenticator import AeatAuthenticator
from ..authenticator_types import CertificateHealthCheck
from ..certificate import CertificateError
from ..errors import AuthValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _UnexpectedError(Exception):
    pass


def _settings(tmp_path: Path) -> Settings:
    cert_path = tmp_path / "cert.p12"
    cert_path.write_bytes(b"x")
    return Settings(
        cadrumo_certificate_path=cert_path,
        cadrumo_certificate_password_secret=SecretStr("test"),
    )


def test_unexpected_certificate_health_error_raises_auth_validation_error(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    def raise_unexpected(
        path: Path,
        *,
        password: SecretStr,
        warn_days: int,
        critical_days: int,
        friendly_name: str | None = None,
        now: datetime | None = None,
    ) -> NoReturn:
        raise _UnexpectedError("boom")

    auth = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
        certificate_health_check=cast(CertificateHealthCheck, raise_unexpected),
    )

    with pytest.raises(AuthValidationError) as raised:
        auth.describe()

    assert str(raised.value)


def test_certificate_error_returns_unavailable_description(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    def raise_certificate_error(
        path: Path,
        *,
        password: SecretStr,
        warn_days: int,
        critical_days: int,
        friendly_name: str | None = None,
        now: datetime | None = None,
    ) -> NoReturn:
        raise CertificateError("expired")

    auth = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
        certificate_health_check=cast(CertificateHealthCheck, raise_certificate_error),
    )

    description = auth.describe()

    assert description.available is False
    assert description.health_summary
