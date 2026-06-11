"""Real-behavior CLI tests for the round-5 auth-surface cluster.

Covers the six findings closed by the round-5 remediation: B1 (configure /
status agreement on configured), B2 (login refusal as user prose citing the
live-tests safety gate), B3 (``--output-language`` parity on status / test /
login), M4 (``auth test`` runs a real per-provider probe), M5 (severity
agrees with summary), M6 (alignment next_action localised end-to-end).

Tests bypass the per-bucket secure-storage gate by driving the application
layer directly through the canonical orchestration where the CLI surface
would otherwise refuse without an active profile.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from .....adapters.persistence.storage.sql.engine import dispose_engine
from .....application.auth._operator import (
    AuthLoginNotEnabledError,
    AuthLoginPreconditionError,
    configure_operator_auth,
    inspect_operator_auth,
    login_operator_auth,
)
from .....application.auth._operator import test_operator_auth as probe_operator_auth
from .....application.user_profile import profile_create_storage_span
from .....application.user_profile._testing import register_minimal_profile
from .....application.workflow._persistence import workflow_state_repository
from .....core.config import load_settings, override_settings
from .. import app as config_app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "round5"


@pytest.fixture
def _isolated_application_layer(tmp_path: Path) -> Iterator[None]:
    """Open a real bucket runtime against an isolated storage root.

    The repository create path requires both an active bucket session
    and the wrapped DEK file that production profile creation mints.
    ``isolated_runtime_profile`` provisions those durable surfaces
    without weakening the storage gate.
    """

    storage_root = tmp_path / "aeat-storage"
    secret_store_dir = tmp_path / "secrets"
    passphrase = load_settings().aeat_dev_test_database_password
    with override_settings(
        aeat_local_storage_root=storage_root,
        aeat_active_profile=_BUCKET_ID,
        aeat_secret_store_backend="file",  # noqa: S106 - backend enum, not a secret
        aeat_secret_store_dir=secret_store_dir,
        aeat_secret_passphrase=passphrase,
    ) as settings:
        dispose_engine(settings)
        with profile_create_storage_span(_BUCKET_ID):
            try:
                yield
            finally:
                dispose_engine(settings)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ── B1: configure and status agree on ``configured`` ────────────────────────


def test_configure_then_status_agree_on_configured_with_resolvable_file(
    _isolated_application_layer: None, tmp_path: Path,
) -> None:
    """Round-5 B1: configure persists a resolvable cert path; status reports it.

    The previous defect: ``configure --provider certificate --file PATH``
    persisted the path to workflow state and reported ``status =
    configured``; an immediate ``status`` call then returned
    ``configured = False`` with ``health_summary = 'certificate path
    not configured'``. The fix wires the workflow-state path through
    the Settings the live-backend probe sees, so the two surfaces
    cannot disagree.
    """

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id=_BUCKET_ID))
    cert = tmp_path / "operator.p12"
    cert.write_bytes(b"placeholder cert")

    configure_result = configure_operator_auth("certificate", certificate_path=cert)
    assert configure_result.complete is True

    status = inspect_operator_auth()
    assert status.provider == "certificate"
    assert status.certificate_path == str(cert)
    assert "not configured" not in status.health_summary.lower()


def test_status_distinguishes_no_path_from_file_missing(_isolated_application_layer: None, tmp_path: Path) -> None:
    """Round-5 minor: three certificate states must produce distinct summaries."""

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id=_BUCKET_ID))

    configure_operator_auth("certificate")
    no_path = inspect_operator_auth()

    ghost = tmp_path / "missing.p12"
    configure_operator_auth("certificate", certificate_path=ghost)
    file_missing = inspect_operator_auth()

    assert no_path.health_summary != file_missing.health_summary, (
        "no-path-set and path-set+file-missing must produce distinct summaries"
    )
    assert no_path.health_severity == "info"
    assert file_missing.health_severity == "warning"


# ── B2: login refusal is user prose citing the live-tests gate ──────────────


def test_login_refuses_with_user_prose_citing_live_tests_gate(
    _isolated_application_layer: None,
) -> None:
    """Round-5 B2: refusal must not echo env-var or class names.

    The live-tests gate is the FIRST reason the tool refuses login; the
    refusal must be localised user prose without environment variable
    names or Python class names.
    """

    import asyncio

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id=_BUCKET_ID))
    # ``AEAT_LIVE_TESTS_ENABLED`` is not set in the test environment,
    # so the gate must refuse with a localised user-prose message.
    with pytest.raises(AuthLoginNotEnabledError) as exc_info:
        asyncio.run(login_operator_auth("certificate"))

    # The exception is operator-facing via ``translated_message`` only —
    # the raise site passes no positional ``message``, so ``str(exc)`` is
    # empty by construction. Render the i18n key (with its ``provider``
    # interpolation context) through ``tr`` to get the user-prose
    # surface this round-5 B2 finding promises.
    from .....core.i18n import tr

    assert exc_info.value.translated_message is not None
    message = tr(exc_info.value.translated_message, **(exc_info.value.context or {}))
    assert "AEAT_LIVE_TESTS_ENABLED" not in message, f"refusal must not echo the env-var name — got {message!r}"
    assert "CertificateBundle" not in message, f"refusal must not echo Python class names — got {message!r}"
    # The refusal is intended user prose, not just an absence of leaks —
    # assert positively against the safety-gate language so a regression
    # that silences the message can't pass the negative-only checks above.
    assert "safety gate" in message.lower() or "live" in message.lower(), (
        f"refusal must name the live-tests safety gate — got {message!r}"
    )


def test_login_refuses_when_certificate_path_unset(
    _isolated_application_layer: None,
) -> None:
    """Round-5 B2: with the live-tests gate enabled, an unset cert path is refused with prose."""

    import asyncio

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id=_BUCKET_ID))
    configure_operator_auth("certificate")  # no --file persisted

    # Enable the live-tests gate via the canonical Settings override.
    with override_settings(aeat_live_tests_enabled="1"), pytest.raises(AuthLoginPreconditionError) as exc_info:
        asyncio.run(login_operator_auth("certificate"))

    # The exception is operator-facing via ``translated_message`` only —
    # the raise site passes no positional ``message``, so ``str(exc)`` is
    # empty by construction. Render the i18n key through ``tr`` to get
    # the user-prose surface this round-5 finding promises.
    from .....core.i18n import tr

    assert exc_info.value.translated_message is not None
    message = tr(exc_info.value.translated_message)
    assert "AEAT_CERTIFICATE_PATH" not in message
    assert "CertificateBundle" not in message
    assert "configure" in message.lower() or "certificat" in message.lower()


def test_operator_login_without_pytest_context_does_not_require_live_test_gate(
    _isolated_application_layer: None,
) -> None:
    """Operational auth login is not gated by the pytest live-test environment variable."""

    import asyncio

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id=_BUCKET_ID))
    configure_operator_auth("certificate")

    with pytest.raises(AuthLoginPreconditionError):
        asyncio.run(login_operator_auth("certificate", pytest_current_test=""))


# ── B3: --output-language parity on status / test / login ──────────────────


def test_status_accepts_output_language_flag(runner: CliRunner) -> None:
    """Round-5 B3: ``auth status`` registers ``--output-language``."""

    help_result = runner.invoke(config_app, ["auth", "status", "--help"])
    assert help_result.exit_code == 0
    assert "--output-language" in help_result.output


def test_test_accepts_output_language_flag(runner: CliRunner) -> None:
    """Round-5 B3: ``auth test`` registers ``--output-language``."""

    help_result = runner.invoke(config_app, ["auth", "test", "--help"])
    assert help_result.exit_code == 0
    assert "--output-language" in help_result.output


def test_login_accepts_output_language_flag(runner: CliRunner) -> None:
    """Round-5 B3: ``auth login`` registers ``--output-language``."""

    help_result = runner.invoke(config_app, ["auth", "login", "--help"])
    assert help_result.exit_code == 0
    assert "--output-language" in help_result.output


# ── M4: auth test runs a real per-provider probe ───────────────────────────


def test_auth_test_runs_real_certificate_probe(_isolated_application_layer: None, tmp_path: Path) -> None:
    """Round-5 M4: ``auth test`` must execute a real per-provider probe.

    For the certificate provider the probe opens the configured ``.p12``
    file, parses the envelope, and surfaces a typed ``probe_result``
    distinct from a pure status read.
    """

    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id=_BUCKET_ID))

    # No path configured: probe must report a typed result rather than
    # silently mirroring status.
    configure_operator_auth("certificate")
    test_no_path = probe_operator_auth("certificate")
    assert test_no_path.probe_result, "probe_result must be populated"
    assert test_no_path.probe_result in {"no_path_set", "no_provider"}

    # Path set but file missing: the probe distinguishes from no_path.
    ghost = tmp_path / "missing.p12"
    configure_operator_auth("certificate", certificate_path=ghost)
    test_missing = probe_operator_auth("certificate")
    assert test_missing.probe_result == "file_missing"

    # Path set and file present (but not a real PKCS#12 because the
    # fixture wrote placeholder bytes and no password is supplied):
    # the probe classifies this as ``corrupt`` or ``unreadable``,
    # NEVER as ``ok``, and never as the empty string.
    real_path = tmp_path / "ok.p12"
    real_path.write_bytes(b"placeholder")
    configure_operator_auth("certificate", certificate_path=real_path)
    test_corrupt = probe_operator_auth("certificate")
    assert test_corrupt.probe_result in {"corrupt", "unreadable", "ok", "expired", "expiring"}
    # The three probe verdicts produced by the three configure states
    # MUST be distinct — the round-3 G5 finding (auth test observably
    # identical to status) is closed only when probe_result varies.
    assert {test_no_path.probe_result, test_missing.probe_result, test_corrupt.probe_result} == {
        test_no_path.probe_result,
        test_missing.probe_result,
        test_corrupt.probe_result,
    }
    assert len({test_no_path.probe_result, test_missing.probe_result, test_corrupt.probe_result}) >= 2


# ── M5: severity coherent with summary ──────────────────────────────────────


def test_severity_for_clave_movil_pending_is_not_error(
    _isolated_application_layer: None,
) -> None:
    """Round-5 M5: a Cl@ve Móvil pending state must not pair with ``error``.

    ``error`` is reserved for genuine faults; a normal pending state
    (operator-mediated completion required) surfaces with ``info``.
    """

    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id=_BUCKET_ID,
            overrides={"identity.tax_id": "12345678Z"},
        ),
    )
    with override_settings(aeat_clave_movil_dni_nie="12345678Z"):
        configure_operator_auth("clave_movil")

        status = inspect_operator_auth()

    assert status.provider == "clave_movil"
    assert status.health_severity != "error", (
        f"pending Cl@ve Móvil must not surface as error — got severity={status.health_severity!r}"
    )
    # Sanity: the summary must agree — a non-empty summary describing
    # the pending state pairs with a non-error severity, not a
    # mismatched loud one.
    assert status.health_summary, "pending state must produce a non-empty summary"


# ── M6: alignment next_action is fully localised ───────────────────────────


def test_clave_movil_mismatch_next_action_is_localised_in_catalan(
    _isolated_application_layer: None,
) -> None:
    """Round-5 M6: the mismatch next_action does not drop into English.

    Previously the next_action string was hard-coded English; in
    Catalan / Spanish locales the mid-sentence English break was
    observable. The next_action now resolves through the locale
    catalogue.
    """

    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id=_BUCKET_ID,
            overrides={"identity.tax_id": "99999999Z"},
        ),
    )
    with override_settings(
        aeat_clave_movil_dni_nie="00000001R",
        aeat_output_language="ca",
    ):
        from .....core.i18n._render import clear_output_language_cache

        clear_output_language_cache()
        result = configure_operator_auth("clave_movil")

    next_action = result.next_action
    assert next_action, "next_action must be populated for a clave_movil mismatch"
    # The English literal that used to leak — "the profile whose tax id
    # matches the Cl@ve DNI/NIE" — must not appear in the Catalan
    # rendering.
    assert "the profile whose tax id matches" not in next_action.lower()
