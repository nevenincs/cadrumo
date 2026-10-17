"""Shared-client admission proofs, independent of tax command parsing."""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from typing import cast, override
from uuid import UUID, uuid4

import pytest
import typer

from cadrumo.application.cli_exception_preconditions import nested_terminal_precondition_verdict
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.login_session import ProfileReceiptRefusedError
from cadrumo.application.workflow.profile_bucket_models import ProfileBucketPointer
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo_client.commands import profile_admission as admission
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.profile_authentication import ProfileAuthenticationMethod, ProfileSecretSourceOptions
from cadrumo_client.commands.secure_input import ProfileSecretChannel, ProfileSecretSelection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _context(source: ProfileSecretSourceOptions) -> typer.Context:
    app = typer.Typer()

    @app.command()
    def noop() -> None:
        return

    context = typer.Context(typer.main.get_command(app))
    cast("dict[str, object]", context.ensure_object(dict))["profile_secret_source"] = source
    return context


class _AdmittedClient:
    def __init__(self, profile_id: UUID) -> None:
        self.profile_id = profile_id
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def resume_receipt(self) -> None:
        pytest.fail("reference route attempted a human receipt")

    def login_password(self, _secret: bytearray) -> None:
        pytest.fail("reference route attempted password login")


@pytest.mark.parametrize(
    ("method", "secret"),
    [
        (ProfileAuthenticationMethod.PASSWORD, ""),
        (ProfileAuthenticationMethod.PASSWORD, "  "),
        (ProfileAuthenticationMethod.PASSWORD, " incorrect password "),
        (ProfileAuthenticationMethod.API_KEY, " incorrect key "),
    ],
)
def test_password_proof_refusals_are_translated_without_changing_api_key_refusals(
    monkeypatch: pytest.MonkeyPatch, method: ProfileAuthenticationMethod, secret: str
) -> None:
    profile_id = uuid4()
    observed: list[tuple[str, bytes, bytearray]] = []
    refusal = FrontendRefusedError("credential_rejected", holder_operation_id="synthetic-holder")

    class RefusingClient(_AdmittedClient):
        @override
        def login_password(self, _secret: bytearray) -> None:
            observed.append(("password", bytes(_secret), _secret))
            raise refusal

        def login_api_key(self, supplied: bytearray) -> None:
            observed.append(("api-key", bytes(supplied), supplied))
            raise refusal

    client = RefusingClient(profile_id)

    async def open_client(**_kwargs: object) -> FrontendClient:
        return cast(FrontendClient, client)

    field = "profile_passphrase" if method is ProfileAuthenticationMethod.PASSWORD else "api_key"
    monkeypatch.setattr(admission, "open_installed_client", open_client)
    monkeypatch.setattr(admission, "subscribe_profile_notices", lambda *_args: None)
    with io.TextIOWrapper(io.BytesIO(json.dumps({field: secret}).encode())) as stdin:
        monkeypatch.setattr("sys.stdin", stdin)
        with pytest.raises(CliRefusedBoundaryError) as caught:
            admission.activate_profile(
                _context(ProfileSecretSourceOptions(method=method, stdin=True)),
                target_bucket_id=str(profile_id),
                target_profile_label="operator",
                root_selection=ProfileSecretSelection(ProfileSecretChannel.STDIN),
                method=method,
            )

    assert client.closed
    if secret:
        assert len(observed) == 1
        used_method, supplied, retained = observed[0]
        assert used_method == method.value
        assert supplied == secret.encode()
        assert retained == bytes(len(supplied))
        assert caught.value.context == refusal.context
    else:
        assert observed == []
        assert caught.value.context == {"reason": "credential_rejected"}
    if method is ProfileAuthenticationMethod.PASSWORD:
        assert caught.value.translated_message == "application.user_profile.errors.profile_authentication_refused"
    else:
        assert caught.value.translated_message is None


@pytest.mark.parametrize("explicit_label", [None, "explicit operator"])
def test_missing_receipt_login_remedy_preserves_the_public_profile_label(
    monkeypatch: pytest.MonkeyPatch, explicit_label: str | None
) -> None:
    profile_id = uuid4()
    observed: list[str] = []

    class MissingReceiptClient(_AdmittedClient):
        @override
        def resume_receipt(self) -> None:
            raise ProfileReceiptRefusedError(ProfileSessionRefusalReason.ABSENT)

    client = MissingReceiptClient(profile_id)

    async def open_client(*, profile_id: UUID, frontend: OperationFrontendProjection) -> FrontendClient:
        assert profile_id == client.profile_id and frontend is OperationFrontendProjection.CLI
        return cast(FrontendClient, client)

    def public_pointer(bucket_id: str) -> ProfileBucketPointer:
        observed.append(bucket_id)
        assert bucket_id == str(profile_id)
        return ProfileBucketPointer(bucket_id=bucket_id, label="ambient operator")

    monkeypatch.setattr(admission, "resolve_active_bucket_id", lambda: str(profile_id))
    monkeypatch.setattr(admission, "open_installed_client", open_client)
    monkeypatch.setattr(admission, "subscribe_profile_notices", lambda *_args: None)
    monkeypatch.setattr("cadrumo.application.workflow.profile_bucket_scan.read_profile_bucket_by_id", public_pointer)
    with pytest.raises(CliRefusedBoundaryError) as caught:
        admission.activate_profile(
            _context(ProfileSecretSourceOptions()),
            target_bucket_id=None if explicit_label is None else str(profile_id),
            target_profile_label=explicit_label,
            root_selection=None,
        )

    verdict = nested_terminal_precondition_verdict(caught.value)
    assert verdict is not None and verdict.action is not None
    assert verdict.failed_condition_id == "profile.session.logged_in"
    assert verdict.action.action_id == "operator.profile.login"
    assert verdict.evidence[0].values["profile_name"] == (explicit_label or "ambient operator")
    assert verdict.argument_bindings[0].value == (explicit_label or "ambient operator")
    assert observed == ([] if explicit_label is not None else [str(profile_id)])
    assert client.closed


def test_reference_uses_installed_credential_door_and_binds_exact_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id, reference = uuid4(), uuid4()
    client = _AdmittedClient(profile_id)
    opened: list[tuple[UUID, UUID, OperationFrontendProjection]] = []
    bound: list[tuple[str, object]] = []

    async def open_credential(
        *,
        profile_id: UUID,
        credential_reference: UUID,
        frontend: OperationFrontendProjection,
        on_connected: Callable[[FrontendClient], None],
    ) -> FrontendClient:
        opened.append((profile_id, credential_reference, frontend))
        on_connected(cast(FrontendClient, client))
        return cast(FrontendClient, client)

    monkeypatch.setattr(admission, "open_installed_credential_client", open_credential)
    monkeypatch.setattr(
        admission,
        "open_installed_client",
        lambda **_kwargs: pytest.fail("reference route opened the unadmitted password door"),
    )
    monkeypatch.setattr(
        admission, "bind_profile_target", lambda _ctx, *, bucket_id: bound.append(("target", bucket_id))
    )
    monkeypatch.setattr(
        admission,
        "bind_profile_client",
        lambda _ctx, bound_client, *, profile_id: bound.append(("client", (bound_client, profile_id))),
    )
    admission.activate_profile(
        _context(
            ProfileSecretSourceOptions(method=ProfileAuthenticationMethod.API_KEY, credential_reference=reference)
        ),
        target_bucket_id=str(profile_id),
        target_profile_label="exact",
        root_selection=None,
        method=ProfileAuthenticationMethod.API_KEY,
        credential_reference=reference,
    )
    assert opened == [(profile_id, reference, OperationFrontendProjection.CLI)]
    assert bound == [("target", str(profile_id)), ("client", (client, profile_id))]
    assert not client.closed


def test_bad_reference_is_a_refusal_without_password_or_receipt_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id, reference = uuid4(), uuid4()

    async def refuse(**_kwargs: object) -> FrontendClient:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.profile_credential_ref_inapplicable"
        )

    monkeypatch.setattr(admission, "open_installed_credential_client", refuse)
    monkeypatch.setattr(
        admission,
        "open_installed_client",
        lambda **_kwargs: pytest.fail("reference refusal attempted a password or receipt fallback"),
    )
    with pytest.raises(CliRefusedBoundaryError):
        admission.activate_profile(
            _context(
                ProfileSecretSourceOptions(method=ProfileAuthenticationMethod.API_KEY, credential_reference=reference)
            ),
            target_bucket_id=str(profile_id),
            target_profile_label="exact",
            root_selection=None,
            method=ProfileAuthenticationMethod.API_KEY,
            credential_reference=reference,
        )
