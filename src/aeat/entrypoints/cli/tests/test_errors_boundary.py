"""Real-CLI boundary tests: stored-data drift vs. input-time validation (contract).

Two scenarios exercise the ``command_error_boundary`` discriminator added in contract:

1. A drifted stored profile — the on-disk profile record is mutated to be
   schema-incompatible, then a CLI verb that loads the profile is run.
   The boundary must surface ``CliStoredDataValidationBoundaryError`` with
   the ``errors.storage.stored_data_validation_boundary`` locale key, which
   contains repair-oriented prose distinct from the input-time refusal.

2. A malformed CLI input flag (invalid date format) — the boundary must
   surface ``CliValidationBoundaryError`` (input-time path), not the
   stored-data variant.  The operator-facing text must be distinct.

No mocks. Uses ``isolated_runtime_profile`` so the session carries a real
(non-unsecured) bucket session and ``require_ready()`` passes.  The payload
is manipulated directly through the injected ``SecureObjectRepository``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....adapters.persistence.storage import SensitivityClass
from ....application.user_profile._repository import (
    USER_PROFILE_VALUE_NAMESPACE,
    UserProfileLifecycleRepository,
    user_profile_value_object_key,
)
from ....domain.user_profile import UserProfileFact, UserProfileRecord, UserProfileStatus
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RUNNER = CliRunner()

# Profile id / bucket id used throughout; must be a valid bucket identifier.
_PROFILE_ID = "test-boundary-profile"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Provision a real active-profile bucket runtime for the boundary tests.

    Uses ``isolated_runtime_profile`` (real KEK/DEK, real SQLite engine)
    so ``require_ready()`` passes without the unsecured-backend guard.
    CLI invocations via ``CliRunner`` run in the same thread, inheriting
    the active ``_active_session`` and ``load_settings`` ContextVars.
    """
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="Test boundary profile",
    ) as profile:
        yield profile


def _seed_profile(runtime_profile: TestRuntimeProfile) -> str:
    """Write a minimal UserProfileRecord into the active bucket; return the profile_id.

    ``isolated_runtime_profile`` already provisions the bucket manifest.
    This function writes only the encrypted profile record via the
    injected repository, bypassing ``ProfileRepository.create`` which
    would reject the already-present manifest.
    """
    record = UserProfileRecord(
        schema_id="aeat.user_profile",
        schema_version=1,
        profile_id=_PROFILE_ID,
        display_name=_PROFILE_ID,
        status=UserProfileStatus.ACTIVE,
        facts=(
            UserProfileFact(path="identity.name", value="Test Operator"),
            UserProfileFact(path="identity.tax_id", value="00000000T"),
        ),
    )
    lifecycle = UserProfileLifecycleRepository(
        bucket_id=_PROFILE_ID,
        objects=runtime_profile.repository,
    )
    lifecycle.save(record)
    return _PROFILE_ID


def _corrupt_stored_profile(profile_id: str, runtime_profile: TestRuntimeProfile) -> None:
    """Stamp an illegal lifecycle invariant into the persisted profile JSON.

    Loads the encrypted envelope from the runtime repository, injects
    ``removed_at`` while leaving ``status = active``, and writes the
    mutated payload back.  The ``UserProfileRecord`` model_validator
    rejects ACTIVE + removed_at on the next load, triggering
    ``StoredProfileDriftError``.
    """
    repo = runtime_profile.repository
    stored = repo.load(
        USER_PROFILE_VALUE_NAMESPACE,
        user_profile_value_object_key(profile_id),
        expected_class=SensitivityClass.IDENTITY,
        max_supported_version=1,
    )
    assert stored is not None, "profile record must exist before corruption"
    envelope = json.loads(stored.payload.decode("utf-8"))
    payload = envelope["payload"]
    assert payload.get("status") == "active", f"fixture must persist ACTIVE status; got {payload.get('status')!r}"
    # Stamp removed_at while keeping ACTIVE — this violates the lifecycle
    # invariant and is the canonical drift scenario.
    payload["removed_at"] = "2024-12-15T10:00:00+00:00"
    repo.save(
        namespace=stored.namespace,
        object_key=user_profile_value_object_key(profile_id),
        classification=stored.classification,
        schema_version=stored.schema_version,
        written_at=stored.written_at,
        payload=json.dumps(envelope).encode("utf-8"),
    )


# ---------------------------------------------------------------------------
# contract.1 — drifted stored profile surfaces CliStoredDataValidationBoundaryError
# ---------------------------------------------------------------------------


def test_drifted_stored_profile_surfaces_stored_data_boundary_message(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """A drifted stored profile must produce the repair-oriented stored-data
    boundary message, not the generic validation or unexpected-error text.

    The ``command_error_boundary`` contract discriminator routes
    ``StoredProfileDriftError`` → ``CliStoredDataValidationBoundaryError``,
    whose registered locale key is ``errors.storage.stored_data_validation_boundary``.
    The English text reads:
      "A stored profile or workflow record no longer matches the expected
       schema ... Run `aeat config repair` to diagnose and recover."

    This test verifies:
    - exit code is non-zero (an error was emitted)
    - the output contains the "config repair" repair action
    - the output does NOT contain the input-time boundary text
      ("command input failed validation") that ``CliValidationBoundaryError``
      emits, confirming the two paths are distinct."""

    profile_id = _seed_profile(runtime_profile)
    _corrupt_stored_profile(profile_id, runtime_profile)

    # Invoke with no <name> argument so the CLI resolves the active profile
    # from settings (the ContextVar set by isolated_runtime_profile).
    result = _RUNNER.invoke(app, ["config", "profile", "show"])

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    # The stored-data boundary message mentions repair.
    assert "config repair" in combined, f"expected 'config repair' in boundary output;\ngot: {combined!r}"
    # Must NOT be the input-time validation boundary message.
    assert "command input failed validation" not in combined, (
        f"stored-data drift triggered input-time boundary instead;\ngot: {combined!r}"
    )


def test_drifted_stored_profile_boundary_is_distinct_from_unexpected_error(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The stored-data boundary path must not fall through to the
    ``CliUnexpectedBoundaryError`` path (which emits generic recovery guidance).

    If ``StoredProfileDriftError`` were not caught before the broad
    ``Exception`` arm, the operator would see a diagnostics suggestion
    rather than a simple repair instruction."""

    profile_id = _seed_profile(runtime_profile)
    _corrupt_stored_profile(profile_id, runtime_profile)

    result = _RUNNER.invoke(app, ["config", "profile", "show"])

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "config repair integrity" not in combined, (
        f"stored-data drift triggered unexpected-error boundary;\ngot: {combined!r}"
    )


# ---------------------------------------------------------------------------
# contract.2 — malformed CLI input surfaces CliValidationBoundaryError (distinct)
# ---------------------------------------------------------------------------


def test_malformed_cli_input_surfaces_input_time_validation_boundary(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Malformed input-time pydantic validation must produce the
    ``CliValidationBoundaryError`` boundary path, not the stored-data variant.

    ``ledger add --date not-a-date ...`` triggers a pydantic validation error
    inside the command (not from loading a stored record).  The boundary
    wraps it as ``CliValidationBoundaryError`` whose message is the
    input-time refusal (``errors.refused.refused_cli_validation_boundary``),
    distinct from the stored-data message.
    """

    _seed_profile(runtime_profile)

    # ``--date not-a-date`` is not a valid ISO date; pydantic's date
    # parser raises ValidationError inside the command.  This test does
    # not assert on the exact pydantic message (which is internal) but
    # checks the CLI boundary path is the input-time one.
    result = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "add",
            "--date",
            "not-a-date",
            "--amount",
            "50.00",
            "--direction",
            "OUTGOING",
            "--description",
            "test entry",
        ],
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    # The stored-data boundary message is absent from input-time errors.
    assert "no longer matches the expected schema" not in combined, (
        f"malformed input triggered stored-data boundary instead;\ngot: {combined!r}"
    )
    # M4 honesty: config repair must NOT be suggested for input-time validation
    # failures.  config repair diagnoses local configuration state and cannot
    # fix an invalid CLI argument or an application schema mismatch; pointing
    # the operator at it is a no-op-recovery path.  The fix is in
    # CliValidationBoundaryError.suggestion and the refused_cli_validation_boundary
    # locale string — both now say "aeat --help" instead of "aeat config repair".
    assert "config repair" not in combined, (
        f"input-time validation boundary must not suggest 'config repair' (no-op "
        f"recovery for a CLI argument error); got: {combined!r}"
    )
    # The command must fail — it did not silently succeed on bad input.
    assert result.exit_code != 0
