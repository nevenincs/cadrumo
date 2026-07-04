"""Real-behavior coverage for ``aeat config google credential-source set|show``.

Drives the full CLI surface (Typer callback, envelope emission, error
boundary) through :func:`invoke_cached_cli` against a real provisioned
profile — no mocks. Confirms:

1. ``set --kind service-account-impersonation`` persists a
   :class:`GoogleCredentialSourceSelection` and ``show`` reflects it back.
2. The persisted selection reaches
   :func:`build_google_credentials` (the real factory dispatch), proven the
   same way :mod:`adapters.outbound.storage.tests.test_factory` proves it:
   pointing ``GOOGLE_APPLICATION_CREDENTIALS`` at a nonexistent path makes
   the real, unmocked ``google.auth.default()`` call raise
   ``GoogleAuthAdcUnavailableError`` naming the persisted
   ``target_principal`` — reachable only if the CLI-persisted selection
   actually drove the impersonation resolver, not the OAuth-Desktop path.
3. ``set --kind oauth-desktop`` restores the default and clears any
   previously persisted impersonation configuration.
4. The persisted record carries no SA private key or access token field —
   only non-secret configuration.
5. An unaccepted ``--kind`` value is refused, and the refusal names the
   accepted set (Click ``Choice`` rendering).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....adapters.outbound.google import GoogleAuthAdcUnavailableError
from .....adapters.outbound.google._session_store import load_credential_source_selection
from .....adapters.outbound.storage import build_google_credentials
from .....core import GoogleCredentialSourceKind
from .....core.config import override_settings
from .....tests.cli_runner import invoke_cached_cli
from .....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TARGET_PRINCIPAL = "aeat-export@example-project.iam.gserviceaccount.com"


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path):  # noqa: ANN201 - pytest fixture generator
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(
            aeat_token_dir=tmp_path / "tokens",
            aeat_runs_dir=tmp_path / "runs",
            aeat_financial_txs_dir=tmp_path / "txs",
            aeat_invoices_dir=tmp_path / "invoices",
            aeat_drafts_dir=tmp_path / "drafts",
        ),
    ):
        yield


def _create_profile(name: str = "google-credential-source-operator") -> str:
    """Provision and activate a real profile; return its resolved profile id."""
    result = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            name,
            "--quiet",
            "--tax-id",
            "00000000T",
            "--activity",
            "Servicios",
            "--iva-regime",
            "GENERAL",
        ],
    )
    assert result.exit_code == 0, result.output
    return name


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

    show_result = invoke_cached_cli(["--format", "json", "config", "google", "credential-source", "show"])
    assert show_result.exit_code == 0, show_result.output
    assert '"configured":true' in show_result.output.replace(" ", "")
    assert GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION.value in show_result.output
    assert _TARGET_PRINCIPAL in show_result.output


def test_set_impersonation_persists_no_secret_field(tmp_path: Path) -> None:
    """The persisted selection roundtrips through secure storage with no secret field."""
    profile = _create_profile()

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
            "--scope",
            "https://www.googleapis.com/auth/drive.file",
        ],
    )
    assert result.exit_code == 0, result.output

    selection = load_credential_source_selection(profile)
    assert selection is not None
    assert selection.kind is GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION
    assert selection.impersonation is not None
    assert selection.impersonation.target_principal == _TARGET_PRINCIPAL
    # The persisted model carries only configuration: no SA private key,
    # refresh token, or access token field exists anywhere on it.
    assert set(selection.impersonation.model_dump().keys()) == {
        "target_principal",
        "target_scopes",
        "delegates",
        "subject",
        "lifetime_s",
    }


def test_factory_dispatches_to_impersonation_after_cli_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI-persisted selection genuinely drives `build_google_credentials`.

    Pointing `GOOGLE_APPLICATION_CREDENTIALS` at a nonexistent path makes the
    real, unmocked `google.auth.default()` call inside
    `resolve_impersonated_credentials` raise `GoogleAuthAdcUnavailableError`
    naming the persisted `target_principal` — a failure mode only reachable
    if the factory actually dispatched to the impersonation resolver (the
    OAuth-Desktop path would instead raise a client-not-registered error).
    """
    profile = _create_profile()
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/nonexistent/path/does-not-exist.json")

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
        build_google_credentials(profile=profile)

    assert raised.value.context == {"target_principal": _TARGET_PRINCIPAL}


def test_set_oauth_desktop_restores_the_default_after_impersonation() -> None:
    profile = _create_profile()

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

    selection = load_credential_source_selection(profile)
    assert selection is not None
    assert selection.kind is GoogleCredentialSourceKind.OAUTH_DESKTOP
    assert selection.impersonation is None


def test_show_before_any_set_reports_the_oauth_desktop_default() -> None:
    _create_profile()

    result = invoke_cached_cli(["--format", "json", "config", "google", "credential-source", "show"])
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
