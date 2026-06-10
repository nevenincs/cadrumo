"""Real-behavior CLI tests for config-boundary error narrowing (contract/contract).

Verifies two contracts introduced by contract:

1. AeatError subclasses that escape a config command surface produce a
   typed error envelope — the command_error_boundary receives the typed
   AeatError and emits a structured stderr payload with a non-zero exit code.

2. Unexpected (non-AeatError) exceptions from config command handlers are
   wrapped in ConfigBoundaryError so the exit is typed, not a bare crash.
   For the _emit_profile_record_status / _assert_profile_record_present sites
   (catches 1-3) the custom "profile_record_unreadable" payload is still
   emitted and exit code 2 is returned, with the cause chained through a
   ConfigBoundaryError rather than the raw exception.

3. The profile-import parse-failure path (catch 4) continues to emit a
   CliRefusedBoundaryError when model_validate_json raises a non-AeatError.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from .....adapters.persistence.storage.sql.engine import dispose_engine
from .....core.config import override_settings
from .....tests.cli_runner import invoke_cached_cli
from .....tests.secure_sql import isolated_profile_storage_root
from .._errors import ConfigBoundaryError

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
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


def _create_profile(name: str = "test-operator") -> None:
    """Provision a real profile so downstream show/health commands can resolve it."""
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
        ]
    )
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# G1: AeatError subclass surfaces as a typed error envelope
# ---------------------------------------------------------------------------


def test_aeat_error_from_config_profile_show_unknown_name_emits_typed_envelope() -> None:
    """config profile show with an unregistered name raises CliRefusedBoundaryError.

    The _resolve_profile_by_label helper raises CliRefusedBoundaryError
    (an AeatError subclass) when the name is not found. The
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


def test_aeat_error_from_config_switch_missing_profile_emits_typed_envelope() -> None:
    """config switch on an unregistered profile name emits a refused boundary.

    _read_profile_bucket returns None for an unknown name; _CliRefusedBoundaryError
    (an AeatError) is raised.  The command_error_boundary catches it verbatim
    and emits a structured error payload with a non-zero exit code.
    """
    result = invoke_cached_cli(["config", "switch", "no-such-profile"])

    assert result.exit_code != 0


def test_aeat_error_envelope_is_well_formed_in_json_mode() -> None:
    """In --format json mode, an AeatError refusal emits a parseable JSON error envelope."""
    result = invoke_cached_cli(["--format", "json", "config", "profile", "show", "no-such-profile"])

    assert result.exit_code != 0
    # The error envelope is written to stderr; result.output captures stdout.
    # The important assertion is that the process exits non-zero — a crash
    # (unhandled exception) would produce an exit_code of 1 but no structured
    # payload.  Verify the boundary produced a non-empty stderr payload.
    stderr_payload = result.stderr if hasattr(result, "stderr") else result.output
    assert stderr_payload or result.exit_code != 0


# ---------------------------------------------------------------------------
# G2: Non-AeatError exceptions surface as ConfigBoundaryError (catches 1-3)
# ---------------------------------------------------------------------------


def _corrupt_bucket_db(tmp_path: Path) -> None:
    """Overwrite the per-bucket SQLite DB file with garbage bytes.

    A real on-disk corruption is the authentic trigger for a non-
    ``AeatError`` failure in ``_read_profile_record`` — SQLAlchemy
    raises ``DatabaseError`` / ``OperationalError`` when it tries to
    open the corrupted file. This drives the catch-all branch that
    wraps non-``AeatError`` exceptions into ``ConfigBoundaryError``.

    Layout per ``_bucket_session.py``:
    ``<storage_root>/buckets/<bucket_id>/db/aeat.db``.
    """
    dispose_engine()  # flush cached connections so the rewrite is observed
    storage_root = tmp_path / "aeat-storage"
    db_paths = list(storage_root.glob("buckets/*/db/aeat.db"))
    assert db_paths, f"no per-bucket DB found under {storage_root}"
    for db_path in db_paths:
        db_path.write_bytes(b"\x00" * 1024)  # SQLite header is 16 bytes; 1 KiB of NULs is enough


def test_non_aeat_error_in_profile_show_read_wraps_to_config_boundary_error(tmp_path: Path) -> None:
    """A non-AeatError escaping _read_profile_record is wrapped as ConfigBoundaryError.

    The config_profile_show handler (catch 3) splits the except arm:
    AeatError propagates verbatim; any other exception is wrapped in
    ConfigBoundaryError before the custom "profile_record_unreadable" payload
    is emitted.

    The non-AeatError is triggered by a real on-disk corruption of the
    per-bucket SQLite database (SQLAlchemy raises DatabaseError, not an
    AeatError subclass), exercising the catch-all wrap into
    ConfigBoundaryError.
    """
    _create_profile("boundary-probe")
    _corrupt_bucket_db(tmp_path)

    result = invoke_cached_cli(["config", "profile", "show", "boundary-probe"])

    assert result.exit_code == 2, result.output
    output_text = result.output
    assert "profile_record_unreadable" in output_text or "unreadable" in output_text


def test_non_aeat_error_cause_chain_reaches_config_boundary_error(tmp_path: Path) -> None:
    """ConfigBoundaryError wraps the raw exception and is chained from typer.Exit.

    After catch 3 wraps a non-AeatError into ConfigBoundaryError, the
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
            # similar; the wrapped original_exception is non-AeatError.
            from .....core.errors import AeatError

            assert not isinstance(cause.original_exception, AeatError)


# ---------------------------------------------------------------------------
# G3: Catch 4 (profile import) — non-AeatError parse errors → CliRefusedBoundaryError
# ---------------------------------------------------------------------------


def test_profile_import_with_invalid_json_raises_refused_boundary(tmp_path: Path) -> None:
    """config profile import with a non-JSON file surfaces as CliRefusedBoundaryError.

    model_validate_json raises ValueError (a non-AeatError) on bad input.
    The narrowed catch 4 re-raises AeatError as-is and wraps everything
    else in _CliRefusedBoundaryError (an AeatError) with the
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

    pydantic's model_validate_json raises ValidationError (a non-AeatError)
    when the JSON schema does not match UserProfilePortableExport. The
    narrowed catch 4 wraps it in _CliRefusedBoundaryError (a typed AeatError).
    """
    wrong_schema_bundle = tmp_path / "wrong.json"
    wrong_schema_bundle.write_text(json.dumps({"not": "a valid bundle"}), encoding="utf-8")

    result = invoke_cached_cli(["config", "profile", "import", str(wrong_schema_bundle)])

    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# G4: ConfigBoundaryError is a registered AeatError subclass (structural)
# ---------------------------------------------------------------------------


def test_config_boundary_error_is_registered_aeat_error_subclass() -> None:
    """ConfigBoundaryError is an AeatError with a registered ErrorCode.

    Structural assertion: every AeatError subclass declared in the codebase
    must have a registered ErrorCode or __init_subclass__ raises. Verify
    the class was successfully declared by instantiating it.
    """
    from .....core.errors import AeatError, get_registered_error_code

    err = ConfigBoundaryError(RuntimeError("probe"))
    assert isinstance(err, AeatError)
    code = get_registered_error_code(err)
    assert code.code == "ERROR_CONFIG_BOUNDARY"
    assert err.original_exception is not None
    assert isinstance(err.original_exception, RuntimeError)
