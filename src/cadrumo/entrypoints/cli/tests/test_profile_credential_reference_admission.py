"""A protected credential reference admits only an exact runtime profile."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from uuid import UUID, uuid4

import pytest
import typer

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.operations.registry import OperationFrontendProjection

from .. import _profile_authentication_gate as gate
from .. import runtime_profile_admission
from .._profile_authentication_contract import ProfileAuthenticationMethod, ProfileSecretSourceOptions
from ..command_specs import COMMAND_GRAPH
from ..errors import CliRefusedBoundaryError
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _context(source: ProfileSecretSourceOptions) -> typer.Context:
    app = typer.Typer()

    @app.command()
    def noop() -> None:
        return

    context = typer.Context(typer.main.get_command(app))
    cast("dict[str, object]", context.ensure_object(dict))["profile_secret_source"] = source
    return context


@pytest.mark.parametrize(
    ("source", "key", "arguments", "reason"),
    (
        (
            ProfileSecretSourceOptions(
                stdin=True, method=ProfileAuthenticationMethod.API_KEY, credential_reference=uuid4()
            ),
            "config_profile_view",
            {},
            "profile_credential_ref_conflict",
        ),
        (
            ProfileSecretSourceOptions(credential_reference=uuid4()),
            "config_profile_view",
            {},
            "profile_credential_ref_requires_api_key",
        ),
        (
            ProfileSecretSourceOptions(method=ProfileAuthenticationMethod.API_KEY, credential_reference=uuid4()),
            "config_profile_resume",
            {},
            "profile_credential_ref_inapplicable",
        ),
        # A leaf that authenticates against the runtime for its ordinary mode,
        # invoked in the local document-only mode that opens no runtime client.
        # The posture alone is not enough: the reference is inapplicable to the
        # invocation, not to the verb.
        (
            ProfileSecretSourceOptions(method=ProfileAuthenticationMethod.API_KEY, credential_reference=uuid4()),
            "app_modelo_work_report_verify",
            {"document_only": True},
            "profile_credential_ref_inapplicable",
        ),
        (
            ProfileSecretSourceOptions(method=ProfileAuthenticationMethod.API_KEY, credential_reference=uuid4()),
            "config_provision_status",
            {},
            "profile_credential_ref_inapplicable",
        ),
    ),
)
def test_reference_refuses_invalid_routes_before_storage_or_secret_reads(
    monkeypatch: pytest.MonkeyPatch,
    source: ProfileSecretSourceOptions,
    key: str,
    arguments: dict[str, object],
    reason: str,
) -> None:
    monkeypatch.setattr(
        "cadrumo.application.cli_provisioning.provision_cli_storage",
        lambda **_kwargs: pytest.fail("refusal provisioned storage"),
    )
    monkeypatch.setattr(gate, "_read_and_stage_leaf", lambda **_kwargs: pytest.fail("refusal read a leaf secret"))
    monkeypatch.setattr(
        runtime_profile_admission,
        "activate_runtime_profile",
        lambda *_args, **_kwargs: pytest.fail("refusal opened a runtime client"),
    )
    with pytest.raises(CliRefusedBoundaryError) as caught:
        gate.preflight_parsed_leaf(
            _context(source), graph=COMMAND_GRAPH, spec=COMMAND_GRAPH.node(key).spec, arguments=arguments
        )
    assert caught.value.translated_message is not None
    assert caught.value.translated_message.endswith(reason)


def test_reference_routes_only_one_exact_migrated_profile_without_root_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id, reference = uuid4(), uuid4()
    observed: list[dict[str, object]] = []
    monkeypatch.setattr("cadrumo.application.cli_provisioning.provision_cli_storage", lambda **_kwargs: None)
    monkeypatch.setattr(gate, "_resolve_profile_targets", lambda *_args, **_kwargs: (str(profile_id), "exact"))
    monkeypatch.setattr(gate, "_diagnose_unregistered_profile", lambda **_kwargs: False)
    monkeypatch.setattr(
        runtime_profile_admission,
        "activate_runtime_profile",
        lambda _ctx, **kwargs: observed.append(kwargs),
    )
    source = ProfileSecretSourceOptions(method=ProfileAuthenticationMethod.API_KEY, credential_reference=reference)
    gate.preflight_parsed_leaf(
        _context(source), graph=COMMAND_GRAPH, spec=COMMAND_GRAPH.node("config_profile_view").spec, arguments={}
    )
    assert observed == [
        {
            "target_bucket_id": str(profile_id),
            "target_profile_label": "exact",
            "root_selection": None,
            "method": ProfileAuthenticationMethod.API_KEY,
            "credential_reference": reference,
        }
    ]


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
        on_connected: Callable[[RuntimeFrontendClient], None],
    ) -> RuntimeFrontendClient:
        opened.append((profile_id, credential_reference, frontend))
        on_connected(cast(RuntimeFrontendClient, client))
        return cast(RuntimeFrontendClient, client)

    monkeypatch.setattr(runtime_profile_admission, "open_installed_credential_client", open_credential)
    monkeypatch.setattr(
        runtime_profile_admission,
        "open_installed_runtime_client",
        lambda **_kwargs: pytest.fail("reference route opened the unadmitted password door"),
    )
    monkeypatch.setattr(
        runtime_profile_admission, "bind_profile_target", lambda _ctx, *, bucket_id: bound.append(("target", bucket_id))
    )
    monkeypatch.setattr(
        runtime_profile_admission,
        "bind_profile_client",
        lambda _ctx, bound_client, *, profile_id: bound.append(("client", (bound_client, profile_id))),
    )
    runtime_profile_admission.activate_runtime_profile(
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

    async def refuse(**_kwargs: object) -> RuntimeFrontendClient:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.profile_credential_ref_inapplicable"
        )

    monkeypatch.setattr(runtime_profile_admission, "open_installed_credential_client", refuse)
    monkeypatch.setattr(
        runtime_profile_admission,
        "open_installed_runtime_client",
        lambda **_kwargs: pytest.fail("reference refusal attempted a password or receipt fallback"),
    )
    with pytest.raises(CliRefusedBoundaryError):
        runtime_profile_admission.activate_runtime_profile(
            _context(
                ProfileSecretSourceOptions(method=ProfileAuthenticationMethod.API_KEY, credential_reference=reference)
            ),
            target_bucket_id=str(profile_id),
            target_profile_label="exact",
            root_selection=None,
            method=ProfileAuthenticationMethod.API_KEY,
            credential_reference=reference,
        )


def test_root_parser_rejects_malformed_reference_without_reading_a_secret() -> None:
    result = invoke_cached_cli(
        ("--profile-auth-method", "api-key", "--profile-credential-ref", "not-a-uuid", "config", "profile", "view"),
        input="not-secret-json",
    )
    assert result.exit_code == 2
    assert "profile_secrets_stdin_invalid_json" not in result.output
