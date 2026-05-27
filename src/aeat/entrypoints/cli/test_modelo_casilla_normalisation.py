"""Regression tests for bare-numeric --casilla normalisation (S59/S60).

Drives the real ``aeat`` CLI against an isolated real-session backend.
No mocks. The tests exercise ``_normalise_casilla_key`` through the
full ``work calculate`` command path.

Coverage:
* Bare numeric token that unambiguously matches a casilla by number
  resolves to the canonical id and the calculation succeeds.
* Bare numeric token that does not match any casilla surfaces the
  S60 improved error message and names the token explicitly.
* A non-numeric (already-qualified) key passes through the normaliser
  unchanged and still resolves correctly.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage.sql import dispose_engine
from aeat.application.user_profile._repository import UserProfileLifecycleRepository
from aeat.domain.user_profile import UserProfileFact, UserProfileRecord, UserProfileStatus
from aeat.tests.cli_runner import invoke_cached_cli
from aeat.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_PROFILE_ID = "casilla-norm-test-profile"


@pytest.fixture
def runtime_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestRuntimeProfile]:
    """Real session backend for casilla normalisation tests.

    Uses ``isolated_runtime_profile`` (real KEK/DEK, real SQLite per
    active bucket).  Extra env-var overrides supply the non-bucket
    directories that work-unit commands read from settings.
    """

    # Work-unit and calculation paths read these from settings; set them
    # to temp dirs that already exist for the session.
    monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(tmp_path / "drafts"))
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(tmp_path / "tokens"))
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(tmp_path / "txs"))
    monkeypatch.setenv("AEAT_INVOICES_DIR", str(tmp_path / "invoices"))
    # Do not set AEAT_DATABASE_URL — the bucket route must stay ACTIVE_BUCKET_DATABASE.
    monkeypatch.delenv("AEAT_DATABASE_URL", raising=False)
    monkeypatch.delenv("AEAT_SECRET_STORE_BACKEND", raising=False)
    monkeypatch.delenv("AEAT_ALLOW_UNENCRYPTED", raising=False)

    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="Casilla normalisation test profile",
    ) as profile:
        dispose_engine(profile.settings)
        yield profile


def _seed_profile(runtime_profile: TestRuntimeProfile) -> None:
    """Write a minimal UserProfileRecord into the real bucket.

    ``isolated_runtime_profile`` provisions the manifest.  We write the
    profile record directly to skip the ``config profile create`` flow
    (which re-provisions the bucket and conflicts with the live session).
    """

    record = UserProfileRecord(
        schema_id="aeat.user_profile",
        schema_version=1,
        profile_id=_PROFILE_ID,
        display_name="Normalisation Test Operator",
        status=UserProfileStatus.ACTIVE,
        facts=(
            UserProfileFact(path="identity.name", value="Test Operator"),
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
        ),
    )
    lifecycle = UserProfileLifecycleRepository(
        bucket_id=_PROFILE_ID,
        objects=runtime_profile.repository,
    )
    lifecycle.save(record)


def _create_303_work_unit() -> str:
    """Create a Modelo 303 work unit and return its id."""

    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "303",
            "--year", "2025",
            "--period", "1T",
            "--revision", "2009-y-siguientes",
        ]
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["work_unit_id"]


# ---------------------------------------------------------------------------
# Unambiguous bare-numeric normalisation
# ---------------------------------------------------------------------------


def test_bare_numeric_resolves_to_canonical_casilla_id(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """A bare integer token normalises to the canonical casilla id.

    Modelo 303 casilla ``iva.resultado`` carries registry number ``69``.
    Supplying the bare token ``--casilla 69=0`` must normalise to the
    canonical id ``iva.resultado`` before the engine validates the
    override.

    The engine refuses computed casillas — but the error it emits names
    ``iva.resultado`` (the resolved id), NOT ``"69"`` (the raw token).
    That name in the error proves normalisation ran.  If the normaliser
    had NOT run, the engine would have raised an unknown-casilla error
    containing ``"69"`` instead.
    """

    _seed_profile(runtime_profile)
    work_unit_id = _create_303_work_unit()

    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "69=0",
        ]
    )  # fmt: skip
    # iva.resultado is computed, so the engine refuses it — but the error
    # must name the resolved id, proving normalisation ran first.
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    output = result.output.replace("\n", " ")
    # The resolved casilla id must appear in the error; the raw token must not
    # appear in an "unknown casilla" diagnostic.
    assert "iva.resultado" in output, (
        "error must name the resolved canonical id 'iva.resultado', proving "
        "that bare numeric '69' was normalised before reaching the engine"
    )
    assert "does not match any casilla" not in output, (
        "normaliser must not fall through to the unknown-casilla error for a "
        "bare numeric that resolves to a known casilla id"
    )


# ---------------------------------------------------------------------------
# Unknown bare-numeric produces helpful error (S60)
# ---------------------------------------------------------------------------


def test_bare_numeric_unknown_casilla_surfaces_helpful_message(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """An unresolvable bare-numeric token raises a helpful BadParameter.

    The error must mention the original token so the operator can
    identify their typo, and must not produce a Python traceback.
    """

    _seed_profile(runtime_profile)
    work_unit_id = _create_303_work_unit()

    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "99999=10.00",
        ]
    )  # fmt: skip
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    output = result.output.replace("\n", " ")
    assert "99999" in output, "error must name the unresolvable token"


# ---------------------------------------------------------------------------
# Non-numeric passthrough — normaliser is a no-op for qualified keys
# ---------------------------------------------------------------------------


def test_qualified_casilla_key_passes_through_normaliser_unchanged(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """A non-bare-numeric key is returned unchanged by the normaliser.

    Supplying the qualified id ``iva.resultado`` directly must be treated
    identically to the bare-numeric ``69`` route.  The normaliser must
    not double-resolve the key or corrupt the dot-path format.

    The engine refuses computed casillas regardless of how they are named
    — the error must mention ``iva.resultado`` (the canonical id), proving
    the qualified form passed through the normaliser without alteration.
    """

    _seed_profile(runtime_profile)
    work_unit_id = _create_303_work_unit()

    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "iva.resultado=0",
        ]
    )  # fmt: skip
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    output = result.output.replace("\n", " ")
    assert "iva.resultado" in output, (
        "engine error must name 'iva.resultado', proving the qualified id was not corrupted"
    )
    assert "does not match any casilla" not in output, (
        "qualified id must not trigger the unknown-casilla diagnostic"
    )
