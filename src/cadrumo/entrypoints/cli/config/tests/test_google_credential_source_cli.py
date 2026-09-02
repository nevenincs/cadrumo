"""Real-behavior coverage for ``aeat config google credential-source set|show``.

Drives the full CLI surface (Typer callback, envelope emission, error
boundary) through :func:`~tests.cli_runner.invoke_cached_cli` against a real provisioned
profile. Confirms:

1. ``set --kind service-account-impersonation`` persists a
   :class:`~adapters.outbound.google.GoogleCredentialSourceSelection` and
   ``show`` reflects it back.
2. The persisted selection reaches
   :func:`~adapters.outbound.storage.build_google_credentials` (the real factory
   dispatch), proven the same way
   :mod:`~adapters.outbound.storage.tests.test_factory` proves it: pointing
   ``GOOGLE_APPLICATION_CREDENTIALS`` at a nonexistent path makes the real
   ``google.auth.default()`` call raise
   ``GoogleAuthAdcUnavailableError`` naming the persisted
   ``target_principal`` — reachable only if the CLI-persisted selection
   actually drove the impersonation resolver, not the OAuth-Desktop path.
3. ``set --kind oauth-desktop`` restores the default and clears any
   previously persisted impersonation configuration.
4. The persisted record carries no SA private key or access token field —
   only non-secret configuration.
5. An unaccepted ``--kind`` value is refused, and the refusal names the
   accepted set (Click ``Choice`` rendering).

Most assertions drive `set`/`show` through separate `invoke_cached_cli`
invocations, matching the project's standard CLI-runner pattern: each
command opens and tears down its own bucket session
(`ctx.with_resource(get_master_key_provider())`), so a persisted selection
is proven by a later command re-loading it from secure storage rather than
by a bare post-invocation repository read (the active-session ContextVar
is unbound once a command returns). The two tests that need to call a
non-CLI primitive directly (`build_google_credentials`,
`load_credential_source_selection`) instead wrap the whole exchange in
`isolated_runtime_profile`, whose `with`-block keeps one bucket session
active across both the CLI invocation and the direct call — the same
pattern :mod:`~adapters.outbound.google.tests.test_session_store_roundtrip`
and :mod:`~adapters.outbound.storage.tests.test_factory` use.

See Also:
    :mod:`~entrypoints.cli.config._google_credential_source_cli`
        Typer command group under test.
    :class:`GoogleCredentialSourceKind`
        Closed credential-source selector accepted by ``--kind``.
    :class:`~adapters.outbound.google.GoogleImpersonationConfig`
        Typed service-account impersonation configuration persisted by ``set``.
    :func:`~adapters.outbound.google.load_credential_source_selection`
        Secure-storage read path used to prove persistence.
    :func:`~adapters.outbound.google.save_credential_source_selection`
        Secure-storage write path invoked by the CLI command.
    :func:`~adapters.outbound.storage.build_google_credentials`
        Factory dispatch that consumes the persisted selection.
    :exc:`~adapters.outbound.google.GoogleAuthAdcUnavailableError`
        Real ADC failure proving impersonation dispatch was selected.
    :class:`~entrypoints.cli.config._google_credential_source_payloads.GoogleCredentialSourceViewResult`
        JSON envelope schema asserted for secret-free ``show`` output.
    :func:`~tests.secure_sql.isolated_runtime_profile`
        Real bucket-session harness used around direct repository reads.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .....adapters.outbound.google.impersonation import GoogleAuthAdcUnavailableError
from .....adapters.outbound.google.session_store import load_credential_source_selection
from .....adapters.outbound.storage.factory import build_google_credentials
from .....core.google_credential_source import GoogleCredentialSourceKind
from .....tests.cli_runner import invoke_cached_cli
from .....tests.env_scope import scoped_env_var
from .....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from .....tests.secure_sql import isolated_runtime_profile
from .....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TARGET_PRINCIPAL = "aeat-export@example-project.iam.gserviceaccount.com"

_PROFILE_CREATE_ARGS = (
    "--entity-type",
    "natural_person",
    "--tax-id",
    "00000000T",
    "--irpf-income-categories",
    "actividad_economica",
    "--name",
    "Test",
    "--surnames",
    "Operator",
    "--quiet",
    "--accept-defaults",
)


def _create_profile(name: str = "google-credential-source-operator") -> str:
    """Register the profile through the shared CLI registration door."""
    return register_cli_profile(
        label=name,
        facts={},
    )


def test_set_service_account_impersonation_then_show_reflects_it() -> None:
    _create_profile()

    set_result = invoke_cached_cli(
        [
            "--format",
            "json",
            "config",
            "google",
            "credential-source",
            "set",
            "--kind",
            GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION.value,
            "--target-principal",
            _TARGET_PRINCIPAL,
        ],
    )
    assert set_result.exit_code == 0, set_result.output
    assert GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION.value in set_result.output
    assert _TARGET_PRINCIPAL in set_result.output

    show_result = invoke_cached_cli(["--format", "json", "config", "google", "credential-source", "view"])
    assert show_result.exit_code == 0, show_result.output
    assert '"configured":true' in show_result.output.replace(" ", "")
    assert GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION.value in show_result.output
    assert _TARGET_PRINCIPAL in show_result.output


def test_set_impersonation_persists_no_secret_field(tmp_path: Path) -> None:
    """The persisted selection roundtrips through secure storage with no secret field.

    Asserted through both surfaces: the CLI ``show`` JSON payload schema
    (:class:`~entrypoints.cli.config._google_credential_source_payloads.GoogleCredentialSourceViewResult`)
    is itself the proof no secret
    field exists — it declares exactly `target_principal` / `target_scopes`
    / `delegates` / `subject` / `lifetime_s`, never a private key or access
    token field — and a direct secure-storage reload (inside the same
    `isolated_runtime_profile` bucket session) confirms the persisted
    `--scope` value round-trips byte-for-byte. The CLI's standing
    `url-host-only` output-redaction policy (`redact_for_cli_output`)
    deliberately truncates a scope URL's path in *rendered* text, so the
    full-URL assertion reads the persisted record rather than the CLI text.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="361721e5-da87-4f70-aba1-a78f62b7ec0b") as profile:
        set_result = invoke_cached_cli(
            [
                "config",
                "google",
                "credential-source",
                "set",
                "--kind",
                GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION.value,
                "--target-principal",
                _TARGET_PRINCIPAL,
                "--scope",
                "https://www.googleapis.com/auth/drive.file",
            ],
        )
        assert set_result.exit_code == 0, set_result.output

        show_result = invoke_cached_cli(["--format", "json", "config", "google", "credential-source", "view"])
        assert show_result.exit_code == 0, show_result.output
        assert GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION.value in show_result.output
        assert _TARGET_PRINCIPAL in show_result.output
        payload = json.loads(show_result.output)["result"]
        assert set(payload.keys()) == {
            "operation",
            "profile",
            "configured",
            "kind",
            "target_principal",
            "target_scopes",
            "delegates",
            "subject",
            "lifetime_s",
        }

        selection = load_credential_source_selection(profile.bucket_id)

    assert selection is not None
    assert selection.impersonation is not None
    assert selection.impersonation.target_scopes == ("https://www.googleapis.com/auth/drive.file",)
    assert set(selection.impersonation.model_dump().keys()) == {
        "target_principal",
        "target_scopes",
        "delegates",
        "subject",
        "lifetime_s",
    }


def test_factory_dispatches_to_impersonation_after_cli_set(tmp_path: Path) -> None:
    """The CLI-persisted selection genuinely drives `build_google_credentials`.

    Pointing `GOOGLE_APPLICATION_CREDENTIALS` at a nonexistent path makes the
    real `google.auth.default()` call inside
    `resolve_impersonated_credentials` raise `GoogleAuthAdcUnavailableError`
    naming the persisted `target_principal` — a failure mode only reachable
    if the factory actually dispatched to the impersonation resolver (the
    OAuth-Desktop path would instead raise a client-not-registered error).
    """
    with (
        scoped_env_var("GOOGLE_APPLICATION_CREDENTIALS", "/nonexistent/path/does-not-exist.json"),
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="b596182a-a527-44d0-bcc5-b408ff9424e8") as profile,
    ):
        result = invoke_cached_cli(
            [
                "config",
                "google",
                "credential-source",
                "set",
                "--kind",
                GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION.value,
                "--target-principal",
                _TARGET_PRINCIPAL,
            ],
        )
        assert result.exit_code == 0, result.output

        with pytest.raises(GoogleAuthAdcUnavailableError) as raised:
            build_google_credentials(profile=profile.bucket_id)

    assert raised.value.context == {"target_principal": _TARGET_PRINCIPAL}


def test_set_oauth_desktop_restores_the_default_after_impersonation(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="a0230b2f-7a63-4a83-950c-3b3fb2ec7723") as profile:
        impersonation_result = invoke_cached_cli(
            [
                "config",
                "google",
                "credential-source",
                "set",
                "--kind",
                GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION.value,
                "--target-principal",
                _TARGET_PRINCIPAL,
            ],
        )
        assert impersonation_result.exit_code == 0, impersonation_result.output

        restore_result = invoke_cached_cli(
            [
                "config",
                "google",
                "credential-source",
                "set",
                "--kind",
                GoogleCredentialSourceKind.OAUTH_DESKTOP.value,
            ],
        )
        assert restore_result.exit_code == 0, restore_result.output

        selection = load_credential_source_selection(profile.bucket_id)

    assert selection is not None
    assert selection.kind is GoogleCredentialSourceKind.OAUTH_DESKTOP
    assert selection.impersonation is None


def test_show_before_any_set_reports_the_oauth_desktop_default() -> None:
    _create_profile()

    result = invoke_cached_cli(["--format", "json", "config", "google", "credential-source", "view"])
    assert result.exit_code == 0, result.output
    assert '"configured":false' in result.output.replace(" ", "")
    assert GoogleCredentialSourceKind.OAUTH_DESKTOP.value in result.output


def test_set_oauth_desktop_rejects_impersonation_only_options() -> None:
    _create_profile()

    result = invoke_cached_cli(
        [
            "config",
            "google",
            "credential-source",
            "set",
            "--kind",
            GoogleCredentialSourceKind.OAUTH_DESKTOP.value,
            "--target-principal",
            _TARGET_PRINCIPAL,
        ],
    )
    assert result.exit_code != 0


def test_set_impersonation_without_target_principal_is_refused() -> None:
    _create_profile()

    result = invoke_cached_cli(
        [
            "config",
            "google",
            "credential-source",
            "set",
            "--kind",
            GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION.value,
        ],
    )
    assert result.exit_code != 0


def test_set_with_unaccepted_kind_names_the_accepted_set() -> None:
    _create_profile()

    result = invoke_cached_cli(
        [
            "config",
            "google",
            "credential-source",
            "set",
            "--kind",
            "not-a-real-kind",
            "--target-principal",
            _TARGET_PRINCIPAL,
        ],
    )
    assert result.exit_code != 0
    assert GoogleCredentialSourceKind.OAUTH_DESKTOP.value in result.output
    assert GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION.value in result.output
