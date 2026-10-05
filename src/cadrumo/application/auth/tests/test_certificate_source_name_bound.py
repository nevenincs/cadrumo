"""A certificate source name the record admits is a name every request admits."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from cadrumo.application.auth.certificate_secret_operation import CertificateSecretMutationRequest
from cadrumo.application.auth.certificate_source_contracts import (
    CertificateSourceRegisterRequest,
    CertificateSourceRemoveRequest,
    CertificateSourceSelectRequest,
)
from cadrumo.application.auth.models import CertificateSourceRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("00000000-0000-4000-8000-000000000001")


def _record(name: str) -> CertificateSourceRecord:
    return CertificateSourceRecord(
        name=name, certificate_path="cert.p12", registered_at=datetime(2026, 1, 1, tzinfo=UTC)
    )


type _NamedRequest = (
    CertificateSourceRegisterRequest
    | CertificateSourceSelectRequest
    | CertificateSourceRemoveRequest
    | CertificateSecretMutationRequest
)


def _requests(name: str) -> tuple[_NamedRequest, ...]:
    return (
        CertificateSourceRegisterRequest(profile_id=_PROFILE, name=name, certificate_path=Path("cert.p12")),
        CertificateSourceSelectRequest(profile_id=_PROFILE, name=name),
        CertificateSourceRemoveRequest(profile_id=_PROFILE, name=name),
        CertificateSecretMutationRequest(profile_id=_PROFILE, name=name),
    )


@pytest.mark.parametrize("length", [1, 128, 129, 160])
def test_every_request_admits_each_length_the_record_admits(length: int) -> None:
    name = "n" * length
    assert _record(f"  {name}  ").name == name
    for request in _requests(f"  {name}  "):
        assert request.name == name, type(request).__name__


@pytest.mark.parametrize("name", ["n" * 161, "", "   "])
def test_every_request_refuses_a_name_the_record_refuses(name: str) -> None:
    with pytest.raises(ValidationError):
        _record(name)
    for build in (
        lambda: CertificateSourceRegisterRequest(profile_id=_PROFILE, name=name, certificate_path=Path("cert.p12")),
        lambda: CertificateSourceSelectRequest(profile_id=_PROFILE, name=name),
        lambda: CertificateSourceRemoveRequest(profile_id=_PROFILE, name=name),
        lambda: CertificateSecretMutationRequest(profile_id=_PROFILE, name=name),
    ):
        with pytest.raises(ValidationError):
            build()
