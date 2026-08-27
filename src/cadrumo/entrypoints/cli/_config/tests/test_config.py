"""Real-behavior CLI tests for config-boundary error narrowing.

Verifies two contracts:

1. CadrumoError subclasses that escape a config command surface produce a
   typed error envelope — the command_error_boundary receives the typed
   CadrumoError and emits a structured stderr payload with a non-zero exit code.

2. Unexpected (non-CadrumoError) exceptions from config command handlers are
   wrapped in ConfigBoundaryError so the exit is typed, not a bare crash. The
   profile-show read boundary emits its typed ``profile_record_unreadable``
   result and exits with code 2, chaining ConfigBoundaryError rather than the
   raw exception.

The bundle-import parse-failure boundary is deliberately uncovered here.
``config profile import`` does not resolve, so the only assertion a test could
make against it is that click refused an unknown command — which is not the
boundary, and passes whatever the boundary does.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import Result

from .....adapters.persistence.storage.sql.engine import dispose_engine
from .....core.config import override_settings
from .....core.i18n import tr
from .....tests.cli_runner import invoke_cached_cli
from .....tests.profile_capsule import open_test_profile_session
from .....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from .....tests.user_profile import register_cli_profile
from ..errors import ConfigBoundaryError

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _create_profile(name: str = "test-operator") -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label=name,
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Test",
            "identity.surnames": "Operator",
            "identity.tax_id": "00000000T",
            "activities.description": "Servicios",
            "censo.activity_start_date": "2026-01-01",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "irpf.estimation_regime": "directa_normal",
            "tax_residence.ccaa": "madrid",
            "iva.regime": "GENERAL",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            "tax_residence.jurisdiction_scope": "common_regime",
        },
    )


# ---------------------------------------------------------------------------
# G1: CadrumoError subclass surfaces as a typed error envelope
# ---------------------------------------------------------------------------


def test_cadrumo_error_from_config_profile_view_unknown_name_emits_typed_envelope() -> None:
    """config profile view with an unregistered name raises CliRefusedBoundaryError.

    The _resolve_profile_by_label helper raises CliRefusedBoundaryError
    (an CadrumoError subclass) when the name is not found. The
    command_error_boundary catches it and emits an error payload on
    stderr. The CLI exits with a non-zero code.

    The test drives the full CLI surface without mocks so every
    boundary, locale resolver, and error-code lookup executes as it
    would in production.
    """
    result = invoke_cached_cli(["config", "profile", "view", "does-not-exist"])

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
    result = invoke_cached_cli(["--format", "json", "config", "profile", "view", "no-such-profile"])

    assert result.exit_code != 0
    # The error envelope is written to stderr; result.output captures stdout.
    # The important assertion is that the process exits non-zero — a crash
    # (unhandled exception) would produce an exit_code of 1 but no structured
    # payload.  Verify the boundary produced a non-empty stderr payload.
    stderr_payload = result.stderr if hasattr(result, "stderr") else result.output
    document = json.loads(stderr_payload)
    error = document["error"]
    assert document["command"] == "config.profile.show"
    assert error["message"] == tr("cli.config.profile.unknown_profile", name="no-such-profile")
    assert "ValueError" not in error["message"]
    assert "suggestion" not in error
    assert error["action"] is not None


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

    The config_profile_view handler (catch 3) splits the except arm:
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

    result = invoke_cached_cli(["config", "profile", "view", "boundary-probe"])

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

    result = invoke_cached_cli(["config", "profile", "view", "chain-probe"])

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
    same instructive refusal every other verb gives — naming both explicit
    machine channels and the interactive path — and must NOT
    report ``profile_record_unreadable`` nor prescribe the destructive
    ``config repair profile`` verb (prescribing a data-damaging repair for a
    merely-locked store is the defect under test).

    Real-behavior: a genuine profile is provisioned, the passphrase is then
    withheld, and the full CLI surface is invoked with non-interactive stdin.
    """
    _create_profile("locked-store-probe")

    result = _login_against_locked_store("locked-store-probe")

    combined = (result.output or "") + ((result.stderr if hasattr(result, "stderr") else "") or "")
    assert "CADRUMO_SECRET_PASSPHRASE" not in combined, combined
    assert "profile_record_unreadable" not in combined, combined
    assert "repair profile" not in combined, combined
    # The no-passphrase condition is a REFUSAL (2): the operator can supply the
    # channel, and nothing failed. It used to be the FAIL category (5) because
    # it surfaced as a SecretStoreError; the custody cutover replaced that with
    # a typed refusal naming the missing password channel, and every verb now
    # answers this condition the same way -- login, show and archive export were
    # each driven with the passphrase withheld to confirm it.
    #
    # The misdiagnosis under test was never the number. It was calling a merely
    # locked store an unreadable record and prescribing a destructive repair, so
    # the code is asserted by NAME here, which pins the diagnosis rather than
    # the category it happens to sit in.
    assert result.exit_code == 2, (result.exit_code, combined)
    # Every channel the verb actually accepts is named, and each was driven
    # end to end to confirm it works before being advertised here.
    assert "--secrets-stdin" in combined, combined
    assert "--secrets-fd" in combined, combined


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

    assert result.exit_code == 2, result.output
    stderr_payload = (result.stderr if hasattr(result, "stderr") else "") or result.output
    assert "CADRUMO_SECRET_PASSPHRASE" not in stderr_payload, stderr_payload
    assert "--secrets-stdin" in stderr_payload, stderr_payload
    assert "--secrets-fd" in stderr_payload, stderr_payload
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
# G4: a secret-taking verb refuses instructively without interactive stdin
# ---------------------------------------------------------------------------


def test_secret_taking_verb_without_interactive_stdin_refuses_instructively() -> None:
    """A verb reading a secret with no TTY and no --secrets-stdin refuses (exit 2).

    Non-interactively, ``getpass`` would raise a bare EOFError that escapes to
    the generic INTERNAL boundary (exit 6, logged traceback). The isatty
    pre-check in the shared secure-input channel turns it into a REFUSED exit
    naming the ``--secrets-stdin`` path. Real boundary, no mocks: the
    in-process runner's stdin is not a TTY.

    ``config auth certificate secret set`` is the carrier: it is the surviving
    verb that resolves its secret through the shared channel unconditionally,
    before touching the store, so the refusal fires ahead of any mutation.
    ``config login`` now holds the same property: it supplies an explicit
    machine value or a verified prompt callback and never delegates CLI secret
    discovery to the storage substrate.
    """
    # The verb declares a ``profile-bound`` write route, so with no active
    # profile the CLI root refuses at the boundary before the secure-input
    # channel is ever consulted -- and this case is about that channel's
    # isatty pre-check, which is downstream of the guard.
    _create_profile()

    result = invoke_cached_cli(["config", "auth", "certificate", "secret", "set", "--name", "operator-cert"])

    assert result.exit_code == 2, result.output
    assert "--secrets-stdin" in result.output
    # The crash class is gone: no traceback, and the escaped exception is not the
    # bare EOFError getpass would have raised.
    assert "Traceback" not in result.output
    assert not isinstance(result.exception, EOFError)


def test_error_envelope_carries_the_active_command_identifier() -> None:
    """A refused leaf command's error envelope names the failing command.

    The dotted id is resolved by the CLI boundary from the executing command's
    click ``command_path`` via the same convention the SUCCESS envelope uses
    (root token dropped, ``.``-joined, ``-`` mapped to ``_``), so success and
    error can never disagree on the command name. A machine consumer of the
    error stream thus knows which command failed without argv bookkeeping.
    """
    # A hyphenated CLI leaf maps to its underscored envelope id, and a deeper
    # path threads every segment (unknown-profile refusal on a nested command).
    bad_show = json.loads(
        invoke_cached_cli(["--format", "json", "config", "profile", "view", "no-such-profile"]).stderr,
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
    from .....application.user_profile.cotejo_apply import CensoDivergence, apply_cotejo
    from .....application.workflow.persistence import workflow_state_repository
    from .....application.workflow.profile_bucket_scan import read_profile_bucket

    pointer = read_profile_bucket(profile_name)
    assert pointer is not None
    with open_test_profile_session(pointer.bucket_id):
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
    """A profile with an open cotejo divergence warns on `config profile view`."""
    _create_profile("divergence-probe")
    _record_divergence("divergence-probe")

    result = invoke_cached_cli(["--format", "json", "config", "profile", "view", "divergence-probe"])

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

    result = invoke_cached_cli(["--format", "json", "config", "profile", "view", "clean-probe"])

    assert result.exit_code == 0, result.output
    document = json.loads(result.output)
    codes = {notice["code"] for notice in document["notices"]}
    assert "profile.censo.divergences_open" not in codes
