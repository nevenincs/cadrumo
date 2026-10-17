"""A protected credential reference admits only an exact runtime profile."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from uuid import uuid4

import pytest
import typer
from click.testing import Result

from cadrumo.entrypoints.cli import _profile_authentication_gate as gate
from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.profile_authentication import ProfileAuthenticationMethod, ProfileSecretSourceOptions

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
            "config_login",
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
    with pytest.raises(CliRefusedBoundaryError) as caught:
        gate.preflight_parsed_leaf(
            _context(source),
            graph=COMMAND_GRAPH,
            spec=COMMAND_GRAPH.node(key).spec,
            arguments=arguments,
            activate_connection=lambda *_args, **_kwargs: pytest.fail("refusal opened a runtime client"),
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
    source = ProfileSecretSourceOptions(method=ProfileAuthenticationMethod.API_KEY, credential_reference=reference)
    gate.preflight_parsed_leaf(
        _context(source),
        graph=COMMAND_GRAPH,
        spec=COMMAND_GRAPH.node("config_profile_view").spec,
        arguments={},
        activate_connection=lambda ctx, **kwargs: observed.append(kwargs),
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


def test_root_parser_rejects_malformed_reference_without_reading_a_secret(
    run_cadrumo_cli: Callable[..., Result],
) -> None:
    result = run_cadrumo_cli(
        ("--profile-auth-method", "api-key", "--profile-credential-ref", "not-a-uuid", "config", "profile", "view"),
        input="not-secret-json",
    )
    assert result.exit_code == 2
    assert "profile_secrets_stdin_invalid_json" not in result.output
