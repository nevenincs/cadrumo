"""Auth configure uses only its exact-profile registered operation result."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from .....application.auth.operation_definitions import (
    AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
    AuthConfigureOperationRequest,
)
from .....application.auth.operator_results import AuthConfigureResult
from .....application.auth.provider_configure_operation_access import (
    AuthConfigureOperationProjection,
    AuthConfigureResultSnapshot,
)
from .....application.runtime.contracts import RuntimeRefusalCode
from .....core.auth_provider import AuthProviderKind
from .....core.external_constants import OutputLanguage
from .....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...config_payloads import AuthConfigurePayload
from ...errors import CliRefusedBoundaryError
from ...runtime_registered_operation import RegisteredOperationCompletion
from .. import _auth as auth_cli
from .. import runtime_auth_configure as bridge

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_FOREIGN_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64


def _projection(
    *,
    profile_id: UUID = _PROFILE,
    provider: str = "certificate",
) -> AuthConfigureOperationProjection:
    return AuthConfigureOperationProjection(
        profile_id=profile_id,
        result=AuthConfigureResultSnapshot(
            provider=provider,
            file="C:/synthetic/aeat-certificate.p12",
            complete=True,
        ),
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projection: BaseModel,
    *,
    effect: OperationEffect = OperationEffect.UPDATED,
    terminal_condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> tuple[list[tuple[object, BaseModel, dict[str, object]]], list[UUID]]:
    client = SimpleNamespace(profile_id=_PROFILE)
    bound_profiles: list[UUID] = []
    submitted: list[tuple[object, BaseModel, dict[str, object]]] = []

    monkeypatch.setattr(
        bridge,
        "resolve_active_profile_pointer",
        lambda: SimpleNamespace(bucket_id=_PROFILE),
    )

    def require_client(_ctx: object, *, expected_profile_id: UUID) -> object:
        bound_profiles.append(expected_profile_id)
        assert expected_profile_id == _PROFILE
        return client

    def submit(
        submitted_client: object,
        request: BaseModel,
        **kwargs: object,
    ) -> RegisteredOperationCompletion[BaseModel]:
        assert submitted_client is client
        submitted.append((submitted_client, request, kwargs))
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=terminal_condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(bridge, "require_profile_client", require_client)
    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submitted, bound_profiles


def _context() -> typer.Context:
    return cast(typer.Context, cast(object, None))


def test_configure_submits_exact_profile_operation_and_returns_operator_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    projection = _projection()
    submitted, bound_profiles = _bind(monkeypatch, projection)
    certificate = tmp_path / "certificate.p12"

    result = bridge.run_auth_configure(
        _context(),
        provider="certificate",
        certificate_path=certificate,
    )

    assert bound_profiles == [_PROFILE]
    assert result == projection.result.to_result()
    assert len(submitted) == 1
    _client, request, options = submitted[0]
    assert request == AuthConfigureOperationRequest(
        provider=AuthProviderKind.CERTIFICATE,
        certificate_path=certificate,
    )
    assert options["definition_id"] == AUTH_CONFIGURE_OPERATION_DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["result_type"] is AuthConfigureOperationProjection
    assert options["request_version"] == options["result_version"] == 1
    assert options["timeout"] == 120


def test_relative_certificate_reference_keeps_caller_file_after_worker_cwd_changes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The deferred request keeps the caller's file across serialization and cwd."""
    caller = tmp_path / "caller"
    worker = tmp_path / "worker"
    relative = Path("certificates") / "personal.p12"
    intended = caller / relative
    unintended = worker / relative
    intended.parent.mkdir(parents=True)
    unintended.parent.mkdir(parents=True)
    intended.write_bytes(b"synthetic caller certificate input")
    unintended.write_bytes(b"different worker-relative file")
    projection = AuthConfigureOperationProjection(
        profile_id=_PROFILE,
        result=AuthConfigureResultSnapshot(provider="certificate", file=str(intended), complete=True),
    )
    submitted, bound_profiles = _bind(monkeypatch, projection)
    monkeypatch.chdir(caller)

    result = bridge.run_auth_configure(_context(), provider="certificate", certificate_path=relative)

    assert bound_profiles == [_PROFILE]
    assert len(submitted) == 1
    request = submitted[0][1]
    assert isinstance(request, AuthConfigureOperationRequest)
    # Exercise the canonical request's wire representation before deferred read.
    received = AuthConfigureOperationRequest.model_validate_json(request.model_dump_json())
    monkeypatch.chdir(worker)
    assert relative.read_bytes() == b"different worker-relative file"
    assert received.certificate_path is not None
    assert received.certificate_path.read_bytes() == b"synthetic caller certificate input"
    assert result.file == str(intended)


@pytest.mark.parametrize(
    ("projection", "effect", "terminal_condition", "refusal_code"),
    [
        (
            _projection(profile_id=_FOREIGN_PROFILE),
            OperationEffect.UPDATED,
            OperationTerminalCondition.SUCCEEDED,
            None,
        ),
        (
            _projection(provider="clave_movil"),
            OperationEffect.UPDATED,
            OperationTerminalCondition.SUCCEEDED,
            None,
        ),
        (_projection(), OperationEffect.NONE, OperationTerminalCondition.SUCCEEDED, None),
        (_projection(), OperationEffect.UNKNOWN, OperationTerminalCondition.SUCCEEDED, None),
        (_projection(), OperationEffect.UPDATED, OperationTerminalCondition.REFUSED, "REFUSED_PROFILE_MISMATCH"),
        (_projection(), OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED, "REFUSED_PROFILE_MISMATCH"),
        (_projection(), OperationEffect.UPDATED, OperationTerminalCondition.FAILED, None),
    ],
    ids=[
        "foreign-profile",
        "wrong-provider",
        "no-effect",
        "unknown-effect",
        "refused",
        "refusal-code",
        "failed-terminal",
    ],
)
def test_configure_correlates_projection_and_settled_receipt(
    monkeypatch: pytest.MonkeyPatch,
    projection: AuthConfigureOperationProjection,
    effect: OperationEffect,
    terminal_condition: OperationTerminalCondition,
    refusal_code: str | None,
) -> None:
    _bind(
        monkeypatch,
        projection,
        effect=effect,
        terminal_condition=terminal_condition,
        refusal_code=refusal_code,
    )

    with pytest.raises(CliRefusedBoundaryError) as error:
        bridge.run_auth_configure(_context(), provider="certificate")

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value
    assert error.value.context["effect"] == effect.value
    assert error.value.context["terminal_condition"] == terminal_condition.value


def test_unknown_provider_keeps_cli_message_without_resolving_profile_or_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_profile_lookup() -> object:
        raise AssertionError("provider syntax is validated before resolving a profile")

    monkeypatch.setattr(bridge, "resolve_active_profile_pointer", no_profile_lookup)

    with pytest.raises(CliRefusedBoundaryError) as error:
        bridge.run_auth_configure(_context(), provider="unknown_provider")

    assert error.value.translated_message == "cli.config.auth.unknown_provider"
    assert error.value.context == {"provider": "unknown_provider"}


def test_no_active_profile_keeps_configure_refusal_before_runtime_submission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge, "resolve_active_profile_pointer", lambda: None)
    monkeypatch.setattr(
        bridge,
        "require_profile_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no profile means no worker")),
    )

    with pytest.raises(CliRefusedBoundaryError) as error:
        bridge.run_auth_configure(_context(), provider="certificate")

    assert error.value.translated_message == "cli.config.auth.no_active_bucket"


def test_auth_configure_keeps_payload_and_operator_text_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = AuthConfigureResult(
        provider="clave_movil",
        file="",
        complete=True,
        profile_tax_id_present=True,
        provider_identity_present=True,
        identity_alignment="aligned",
        identity_alignment_detail="identities match",
    )
    invoked: list[tuple[typer.Context, str, Path | None]] = []
    emitted: list[dict[str, object]] = []
    activated: list[tuple[typer.Context, OutputLanguage | None]] = []
    ctx = _context()

    monkeypatch.setattr(
        auth_cli,
        "_activate_subcommand_output_language",
        lambda passed_ctx, language: activated.append((passed_ctx, language)),
    )
    monkeypatch.setattr(
        "cadrumo.entrypoints.cli.config.runtime_auth_configure.run_auth_configure",
        lambda passed_ctx, *, provider, certificate_path: (
            invoked.append((passed_ctx, provider, certificate_path)) or result
        ),
    )
    monkeypatch.setattr(
        auth_cli,
        "emit_envelope",
        lambda passed_ctx, **kwargs: emitted.append({"ctx": passed_ctx, **kwargs}),
    )

    auth_cli.auth_configure(
        ctx,
        provider="clave_movil",
        file=None,
        output_language=OutputLanguage.EN,
    )

    assert invoked == [(ctx, "clave_movil", None)]
    assert activated == [(ctx, OutputLanguage.EN)]
    assert len(emitted) == 1
    assert emitted[0]["ctx"] is ctx
    assert emitted[0]["command"] == "config.auth.configure"
    payload = emitted[0]["result"]
    assert isinstance(payload, AuthConfigurePayload)
    assert payload.provider == "clave_movil"
    assert payload.complete is True
    assert emitted[0]["lines"] == [
        "provider\tclave_movil",
        "file\t",
        "status\tconfigured",
        "profile_tax_id\tpresent",
        "clave_identity\tpresent",
        "identity_alignment\taligned",
        "identity_alignment_detail\tidentities match",
    ]
