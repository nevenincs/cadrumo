"""Certificate CLI bridges preserve profile, path, effect and secret boundaries."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from cadrumo.application.auth.certificate_source_contracts import (
    CertificateSourceRegisterProjection,
    CertificateSourceRegisterRequest,
    CertificateSourceRemoveProjection,
)
from cadrumo.application.auth.operator_results import CertificateSourceMutationResult
from cadrumo.core.operations import OperationEffect

from ...errors import CliRefusedBoundaryError
from ...registered_operation_contracts import RegisteredOperationCompletion
from .. import runtime_certificate as bridge

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]
_PROFILE_ID = UUID("11111111-1111-4111-8111-111111111111")
_OPERATION_ID = "a" * 64


def _context() -> typer.Context:
    return cast(typer.Context, SimpleNamespace())


def _bind_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bridge, "resolve_active_profile_pointer", lambda: SimpleNamespace(bucket_id=str(_PROFILE_ID)))
    monkeypatch.setattr(bridge, "require_profile_client", lambda *_a, **_kw: object())


def test_register_resolves_caller_relative_file_before_exact_profile_submission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_profile(monkeypatch)
    captured: dict[str, object] = {}
    path = Path("relative/synthetic.p12")

    def submit(_client: object, payload: CertificateSourceRegisterRequest, **kwargs: object):
        captured.update(kwargs)
        captured["payload"] = payload
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=CertificateSourceRegisterProjection(
                profile_id=_PROFILE_ID,
                result=CertificateSourceMutationResult(name="personal", certificate_path=str(path.resolve())),
            ),
            effect=OperationEffect.UPDATED,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    result = bridge.register_source(_context(), name="personal", file=path, friendly_name=None)
    payload = captured["payload"]
    assert isinstance(payload, CertificateSourceRegisterRequest)
    assert payload.profile_id == _PROFILE_ID
    assert payload.certificate_path == path.resolve()
    assert captured["subject_ref"] == f"profile:{_PROFILE_ID}"
    assert result.certificate_path == str(path.resolve())


def test_remove_rejects_false_effect_and_keeps_operation_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _bind_profile(monkeypatch)
    monkeypatch.setattr(
        bridge,
        "run_registered_operation",
        lambda *_a, **_kw: RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=CertificateSourceRemoveProjection(
                profile_id=_PROFILE_ID,
                result=CertificateSourceMutationResult(name="personal", removed=True),
            ),
            effect=OperationEffect.NONE,
        ),
    )
    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.remove_source(_context(), name="personal")
    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID


def test_passphrase_bytes_are_wiped_when_profile_admission_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bridge, "resolve_active_profile_pointer", lambda: SimpleNamespace(bucket_id=str(_PROFILE_ID)))

    def refuse(*_a: object, **_kw: object) -> object:
        raise CliRefusedBoundaryError(translated_message="synthetic admission refusal")

    monkeypatch.setattr(bridge, "require_profile_client", refuse)
    secret = bytearray(b"synthetic-passphrase")
    with pytest.raises(CliRefusedBoundaryError):
        bridge.set_source_passphrase(_context(), name="personal", secret=secret)
    assert secret == bytes(len(secret))
