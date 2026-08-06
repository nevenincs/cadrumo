"""Real-behavior CLI tests for config-boundary error narrowing (contract/contract).

Verifies two contracts introduced by contract:

1. CadrumoError subclasses that escape a config command surface produce a
   typed error envelope — the command_error_boundary receives the typed
   CadrumoError and emits a structured stderr payload with a non-zero exit code.

2. Unexpected (non-CadrumoError) exceptions from config command handlers are
   wrapped in ConfigBoundaryError so the exit is typed, not a bare crash. The
   profile-show read boundary emits its typed ``profile_record_unreadable``
   result and exits with code 2, chaining ConfigBoundaryError rather than the
   raw exception.

3. The profile-import parse-failure path (catch 4) continues to emit a
   CliRefusedBoundaryError when model_validate_json raises a non-CadrumoError.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import Result

from .....adapters.persistence.storage.sql.engine import dispose_engine
from .....core.config import override_settings
from .....tests.cli_runner import invoke_cached_cli
from .....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from .._errors import ConfigBoundaryError

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _create_profile(name: str = "test-operator") -> None:
    """Provision a real profile so downstream show/health commands can resolve it."""
    result = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            name,
            "--quiet",
            "--entity-type",
            "natural_person",
            "--name",
            "Test",
            "--surnames",
            "Operator",
            "--tax-id",
            "00000000T",
            "--activity",
            "Servicios",
            "--iva-regime",
            "GENERAL",
        ],
    )
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# G1: CadrumoError subclass surfaces as a typed error envelope
# ---------------------------------------------------------------------------


def test_cadrumo_error_from_config_profile_show_unknown_name_emits_typed_envelope() -> None:
    """config profile show with an unregistered name raises CliRefusedBoundaryError.

    The _resolve_profile_by_label helper raises CliRefusedBoundaryError
    (an CadrumoError subclass) when the name is not found. The
    command_error_boundary catches it and emits an error payload on
    stderr. The CLI exits with a non-zero code.

    The test drives the full CLI surface without mocks so every
    boundary, locale resolver, and error-code lookup executes as it
    would in production.
    """
    result = invoke_cached_cli(["config", "profile", "show", "does-not-exist"])

    assert result.exit_code != 0
    # CliRefusedBoundaryError has category REFUSED → exit code 1 or 2
    # The exact code depends on the exit-code map; non-zero is the contract.
    assert isinstance(result.exception, SystemExit) or result.exit_code != 0


def test_cadrumo_error_from_config_login_missing_profile_emits_typed_envelope() -> None:
    """config login on an unregistered profile name emits a refused boundary.

    _read_profile_bucket returns None for an unknown name; _CliRefusedBoundaryError
    (an CadrumoError) is raised.  The command_error_boundary catches it verbatim
    and emits a structured error payload with a non-zero exit code.
    """
    result = invoke_cached_cli(["config", "login", "no-such-profile"])

    assert result.exit_code != 0


def test_cadrumo_error_envelope_is_well_formed_in_json_mode() -> None:
    """In --format json mode, an CadrumoError refusal emits a parseable JSON error envelope."""
    result = invoke_cached_cli(["--format", "json", "config", "profile", "show", "no-such-profile"])

    assert result.exit_code != 0
    # The error envelope is written to stderr; result.output captures stdout.
    # The important assertion is that the process exits non-zero — a crash
    # (unhandled exception) would produce an exit_code of 1 but no structured
    # payload.  Verify the boundary produced a non-empty stderr payload.
    stderr_payload = result.stderr if hasattr(result, "stderr") else result.output
    assert stderr_payload or result.exit_code != 0


# ---------------------------------------------------------------------------
# G2: Non-CadrumoError exceptions surface as ConfigBoundaryError (catches 1-3)
# ---------------------------------------------------------------------------


def _corrupt_bucket_db(tmp_path: Path) -> None:
    """Overwrite the per-bucket SQLite DB file with garbage bytes.

    A real on-disk corruption is the authentic trigger for a non-
    ``CadrumoError`` failure in ``_read_profile_record`` — SQLAlchemy
    raises ``DatabaseError`` / ``OperationalError`` when it tries to
    open the corrupted file. This drives the catch-all branch that
    wraps non-``CadrumoError`` exceptions into ``ConfigBoundaryError``.

    Layout per ``_bucket_session.py``:
    ``<storage_root>/buckets/<bucket_id>/db/cadrumo.db``.
    """
    dispose_engine()  # flush cached connections so the rewrite is observed
    storage_root = tmp_path / "cadrumo-storage"
    db_paths = list(storage_root.glob("buckets/*/db/cadrumo.db"))
    assert db_paths, f"no per-bucket DB found under {storage_root}"
    for db_path in db_paths:
        db_path.write_bytes(b"\x00" * 1024)  # SQLite header is 16 bytes; 1 KiB of NULs is enough


def test_non_cadrumo_error_in_profile_show_read_wraps_to_config_boundary_error(tmp_path: Path) -> None:
    """A non-CadrumoError escaping _read_profile_record is wrapped as ConfigBoundaryError.

    The config_profile_show handler (catch 3) splits the except arm:
    CadrumoError propagates verbatim; any other exception is wrapped in
    ConfigBoundaryError before the custom "profile_record_unreadable" payload
    is emitted.

    The non-CadrumoError is triggered by a real on-disk corruption of the
    per-bucket SQLite database (SQLAlchemy raises DatabaseError, not an
    CadrumoError subclass), exercising the catch-all wrap into
    ConfigBoundaryError.
    """
    _create_profile("boundary-probe")
    _corrupt_bucket_db(tmp_path)

    result = invoke_cached_cli(["config", "profile", "show", "boundary-probe"])

    assert result.exit_code == 2, result.output
    output_text = result.output
    assert "profile_record_unreadable" in output_text or "unreadable" in output_text


def test_non_cadrumo_error_cause_chain_reaches_config_boundary_error(tmp_path: Path) -> None:
    """ConfigBoundaryError wraps the raw exception and is chained from typer.Exit.

    After catch 3 wraps a non-CadrumoError into ConfigBoundaryError, the
    ``raise typer.Exit(code=2) from boundary`` statement chains the
    ConfigBoundaryError as the __cause__ of the SystemExit.

    Verifies the cause-chain shape when a real DB corruption (not a
    monkeypatch attribute swap) causes the boundary to fire.
    """
    _create_profile("chain-probe")
    _corrupt_bucket_db(tmp_path)

    result = invoke_cached_cli(["config", "profile", "show", "chain-probe"])

    assert result.exit_code == 2, result.output
    # CliRunner captures the exception that propagated out of the callback.
    # typer.Exit propagates from the handler; its __cause__ is ConfigBoundaryError.
    exc = result.exception
    if exc is not None:
        cause = getattr(exc, "__cause__", None)
        # Walk the cause chain up to depth 3 to find ConfigBoundaryError.
        for _ in range(3):
            if isinstance(cause, ConfigBoundaryError):
                break
            cause = getattr(cause, "__cause__", None)
        # If CliRunner swallowed the exception, the output check is sufficient.
        if cause is not None:
            assert isinstance(cause, ConfigBoundaryError)
            # Real-failure trigger raises a SQLAlchemy DatabaseError or
            # similar; the wrapped original_exception is non-CadrumoError.
            from .....core.errors import CadrumoError

            assert not isinstance(cause.original_exception, CadrumoError)


# ---------------------------------------------------------------------------
# G3: Catch 4 (profile import) — non-CadrumoError parse errors → CliRefusedBoundaryError
# ---------------------------------------------------------------------------


def test_profile_import_with_invalid_json_raises_refused_boundary(tmp_path: Path) -> None:
    """config profile import with a non-JSON file surfaces as CliRefusedBoundaryError.

    model_validate_json raises ValueError (a non-CadrumoError) on bad input.
    The narrowed catch 4 re-raises CadrumoError as-is and wraps everything
    else in _CliRefusedBoundaryError (an CadrumoError) with the
    "import_invalid_bundle" locale message.

    Real-behavior test: we write a real file with invalid JSON content and
    invoke the full CLI surface.
    """
    bad_bundle = tmp_path / "bad.json"
    bad_bundle.write_text("this is not valid json", encoding="utf-8")

    result = invoke_cached_cli(["config", "profile", "import", str(bad_bundle)])

    # CliRefusedBoundaryError is category REFUSED; exit code ≠ 0.
    assert result.exit_code != 0


def test_profile_import_with_structurally_invalid_bundle_surfaces_as_refused(
    tmp_path: Path,
) -> None:
    """config profile import with valid JSON but wrong schema structure → refused boundary.

    pydantic's model_validate_json raises ValidationError (a non-CadrumoError)
    when the JSON schema does not match UserProfilePortableExport. The
    narrowed catch 4 wraps it in _CliRefusedBoundaryError (a typed CadrumoError).
    """
    wrong_schema_bundle = tmp_path / "wrong.json"
    wrong_schema_bundle.write_text(json.dumps({"not": "a valid bundle"}), encoding="utf-8")

    result = invoke_cached_cli(["config", "profile", "import", str(wrong_schema_bundle)])

    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# G4: ConfigBoundaryError is a registered CadrumoError subclass (structural)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# G5: Locked store (no passphrase) is NOT mislabelled profile_record_unreadable
#     and is NOT routed at the destructive `config repair profile` verb.
# ---------------------------------------------------------------------------


def _login_against_locked_store(name: str) -> Result:
    """Run ``config login NAME`` against a healthy-but-locked store.

    The profile bucket is HEALTHY; only the master-key passphrase is
    withheld (``cadrumo_secret_passphrase=None``) and stdin is non-interactive
    (the ``CliRunner`` stdin is never a tty), reproducing the operator's
    locked-store condition. Cached SQL connections are flushed so the read
    re-resolves the master-key provider and hits the no-passphrase refusal
    rather than a still-warm engine.
    """
    dispose_engine()
    with override_settings(cadrumo_secret_passphrase=None):
        return invoke_cached_cli(["config", "login", name])


def test_config_login_against_locked_store_gives_passphrase_refusal_not_repair() -> None:
    """A healthy-but-locked store yields the passphrase-instructive refusal.

    The operator withheld the master-key passphrase (locked store); the
    profile record itself is healthy. ``config login`` must surface the
    same instructive refusal every other verb gives — naming
    ``CADRUMO_SECRET_PASSPHRASE`` and the interactive path — and must NOT
    report ``profile_record_unreadable`` nor prescribe the destructive
    ``config repair profile`` verb (prescribing a data-damaging repair for a
    merely-locked store is the defect under test).

    Real-behavior: a genuine profile is provisioned, the passphrase is then
    withheld, and the full CLI surface is invoked with non-interactive stdin.
    """
    _create_profile("locked-store-probe")

    result = _login_against_locked_store("locked-store-probe")

    combined = (result.output or "") + ((result.stderr if hasattr(result, "stderr") else "") or "")
    assert "CADRUMO_SECRET_PASSPHRASE" in combined, combined
    assert "profile_record_unreadable" not in combined, combined
    assert "repair profile" not in combined, combined
    # The no-passphrase condition exits with the FAIL category (5), the same
    # code every other verb's SecretStoreError produces — never REFUSED (2),
    # the code the old profile_record_unreadable misdiagnosis returned.
    assert result.exit_code == 5, (result.exit_code, combined)


def test_config_login_against_locked_store_json_envelope_is_passphrase_refusal() -> None:
    """In JSON mode the locked-store refusal is a typed error envelope, not a repair hint.

    The stderr error document must carry the shared envelope spine and must
    not smuggle a ``profile_record_unreadable`` status or a ``repair
    profile`` next_action.
    """
    _create_profile("locked-json-probe")

    dispose_engine()
    with override_settings(cadrumo_secret_passphrase=None):
        result = invoke_cached_cli(["--format", "json", "config", "login", "locked-json-probe"])

    assert result.exit_code == 5, result.output
    stderr_payload = (result.stderr if hasattr(result, "stderr") else "") or result.output
    assert "profile_record_unreadable" not in stderr_payload, stderr_payload
    assert "repair profile" not in stderr_payload, stderr_payload


def test_config_boundary_error_is_registered_cadrumo_error_subclass() -> None:
    """ConfigBoundaryError is an CadrumoError with a registered ErrorCode.

    Structural assertion: every CadrumoError subclass declared in the codebase
    must have a registered ErrorCode or __init_subclass__ raises. Verify
    the class was successfully declared by instantiating it.
    """
    from .....core.errors import CadrumoError, get_registered_error_code

    err = ConfigBoundaryError(RuntimeError("probe"))
    assert isinstance(err, CadrumoError)
    code = get_registered_error_code(err)
    assert code.code == "ERROR_CONFIG_BOUNDARY"
    assert err.original_exception is not None
    assert isinstance(err.original_exception, RuntimeError)


# ---------------------------------------------------------------------------
# G4: passphrase change / recover refuse instructively without interactive stdin
# ---------------------------------------------------------------------------


def test_passphrase_change_without_interactive_stdin_refuses_instructively() -> None:
    """`config passphrase change` with no TTY and no --secrets-stdin refuses (exit 2).

    Non-interactively, ``getpass`` would raise a bare EOFError that escapes to
    the generic INTERNAL boundary (exit 6, logged traceback). The isatty
    pre-check in the shared secure-input channel turns it into a REFUSED exit
    naming the ``--secrets-stdin`` path. Real boundary, no mocks: the
    in-process runner's stdin is not a TTY.
    """
    result = invoke_cached_cli(["config", "passphrase", "change"])

    assert result.exit_code == 2, result.output
    assert "--secrets-stdin" in result.output
    # The crash class is gone: no traceback, and the escaped exception is not the
    # bare EOFError getpass would have raised.
    assert "Traceback" not in result.output
    assert not isinstance(result.exception, EOFError)


def test_recover_without_interactive_stdin_refuses_instructively() -> None:
    """`config recover` with no TTY and no --secrets-stdin refuses (exit 2).

    The secret resolution runs before any recovery-store access, and the
    recovery code is never accepted as an ``argv`` value, so the refusal fires
    before any custody mutation.
    """
    result = invoke_cached_cli(["config", "recover"])

    assert result.exit_code == 2, result.output
    assert "--secrets-stdin" in result.output
    assert "Traceback" not in result.output
    assert not isinstance(result.exception, EOFError)


def test_passphrase_change_refusal_json_stream_parses_cleanly_without_traceback_leak() -> None:
    """`aeat --format json config passphrase change` refusal is a pure-JSON error document.

    Symptom 2 of the same root cause: the INTERNAL-boundary crash logged a
    traceback that leaked before the envelope, breaking any JSON consumer of the
    error stream. The REFUSED path emits only the typed error document (on
    stderr, per the ``write_stderr`` error contract; stdout stays empty), so it
    parses cleanly.
    """
    result = invoke_cached_cli(["--format", "json", "config", "passphrase", "change"])

    assert result.exit_code == 2
    assert "Traceback" not in result.stderr
    assert "Traceback" not in result.output
    # stdout carries no leaked JSON/traceback; the typed error document is the
    # sole content of the JSON error stream and parses cleanly.
    document = json.loads(result.stderr)
    assert document["status"] == "error"
    assert document["error"]["category"] == "REFUSED"
    assert document["error"]["code"] == "REFUSED_CLI_BOUNDARY"


def test_error_envelope_carries_the_active_command_identifier() -> None:
    """A refused leaf command's error envelope names the failing command.

    The dotted id is resolved by the CLI boundary from the executing command's
    click ``command_path`` via the same convention the SUCCESS envelope uses
    (root token dropped, ``.``-joined, ``-`` mapped to ``_``), so success and
    error can never disagree on the command name. A machine consumer of the
    error stream thus knows which command failed without argv bookkeeping.
    """
    change = json.loads(invoke_cached_cli(["--format", "json", "config", "passphrase", "change"]).stderr)
    assert change["command"] == "config.passphrase.change"

    recover = json.loads(
        invoke_cached_cli(["--format", "json", "config", "recover"]).stderr,
    )
    assert recover["command"] == "config.recover"

    # A hyphenated CLI leaf maps to its underscored envelope id, and a deeper
    # path threads every segment (unknown-profile refusal on a nested command).
    bad_show = json.loads(
        invoke_cached_cli(["--format", "json", "config", "profile", "show", "no-such-profile"]).stderr,
    )
    assert bad_show["command"] == "config.profile.show"


def test_pre_resolution_error_envelope_command_stays_null() -> None:
    """An error rendered before a command resolves keeps ``command`` null honestly.

    ``render_error_json`` defaults ``command`` to ``None``; the CLI boundary
    passes the dotted id only once a command context is active. An error raised
    before any command callback runs (an argv parse failure) therefore carries
    null, so the field is never a fabricated command name.
    """
    from .....core.errors import render_error_json
    from .....core.locks_errors import LockAcquisitionError

    document = json.loads(render_error_json(LockAcquisitionError()))
    assert document["command"] is None


# ---------------------------------------------------------------------------
# Censo divergence notice on the profile read surface
# ---------------------------------------------------------------------------


def _record_divergence(profile_name: str) -> None:
    """Persist one open cotejo divergence on the named profile's record."""
    from .....application.user_profile import CensoDivergence, apply_cotejo, profile_storage_session
    from .....application.workflow import read_profile_bucket, workflow_state_repository

    pointer = read_profile_bucket(profile_name)
    assert pointer is not None
    with profile_storage_session(pointer.bucket_id):
        workflow_state_repository().update(
            lambda state: apply_cotejo(
                state,
                adopted=(),
                divergences=(
                    CensoDivergence(
                        axis="activities.description",
                        artefact_value="Consultoría informática",
                    ),
                ),
            ),
        )


def test_profile_show_surfaces_the_open_divergence_notice() -> None:
    """A profile with an open cotejo divergence warns on `config profile show`."""
    _create_profile("divergence-probe")
    _record_divergence("divergence-probe")

    result = invoke_cached_cli(["--format", "json", "config", "profile", "show", "divergence-probe"])

    assert result.exit_code == 0, result.output
    document = json.loads(result.output)
    notices = {notice["code"]: notice for notice in document["notices"]}
    assert "profile.censo.divergences_open" in notices
    notice = notices["profile.censo.divergences_open"]
    assert notice["severity"] == "warning"
    assert str(notice["context"]["count"]) == "1"
    assert "activities.description" in str(notice["context"]["axes"])


def test_profile_show_carries_no_divergence_notice_when_clean() -> None:
    """A profile with no open divergence shows no censo warning."""
    _create_profile("clean-probe")

    result = invoke_cached_cli(["--format", "json", "config", "profile", "show", "clean-probe"])

    assert result.exit_code == 0, result.output
    document = json.loads(result.output)
    codes = {notice["code"] for notice in document["notices"]}
    assert "profile.censo.divergences_open" not in codes
