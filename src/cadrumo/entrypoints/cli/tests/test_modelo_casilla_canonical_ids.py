"""Regression tests for canonical ``--casilla`` id enforcement.

Drives the real ``cadrumo`` CLI against an isolated real-session backend.
No mocks. The tests exercise canonical casilla-id validation through the
full ``work calculate`` command path.

Coverage:
* Display/export metadata tokens that are not canonical casilla ids are refused.
* An unknown token surfaces a helpful error and names the token.
* A canonical semantic id reaches the engine unchanged.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile
from ._modelo_work_ux_support import _create_m303_work_unit

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "ca511a00-ca51-4ca5-8ca5-11a00ca511a0"


@pytest.fixture
def runtime_profile(
    tmp_path: Path,
) -> Iterator[TestRuntimeProfile]:
    """Real session backend for casilla canonical-id tests.

    Uses ``isolated_runtime_profile`` (real KEK/DEK, real SQLite per
    active bucket).  Extra env-var overrides supply the non-bucket
    directories that work-unit commands read from settings.
    """

    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="Casilla canonical-id test profile",
    ) as profile:
        yield profile


def _seed_profile(runtime_profile: TestRuntimeProfile) -> None:
    """Write a minimal UserProfileRecord into the real bucket.

    ``isolated_runtime_profile`` provisions the manifest.  We write the
    profile record directly to skip the ``config profile create`` flow
    (which re-provisions the bucket and conflicts with the live session).
    """

    record = UserProfileRecord(
        schema_id="cadrumo.user_profile",
        # Sourced from the schema, never pinned: a literal goes stale the moment
        # the profile schema is revised, and the record then refuses to validate
        # against its own canonical version.
        schema_version=load_user_profile_schema().version,
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=(
            UserProfileFact(path="identity.name", value="Test Operator"),
            UserProfileFact(path="identity.surnames", value="Test Operator"),
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        ),
    )
    seed_test_profile_record(record, root=runtime_profile.storage_root, label="Casilla canonical-id test profile")


# ---------------------------------------------------------------------------
# Printed-number metadata tokens are refused
# ---------------------------------------------------------------------------


def test_printed_number_metadata_token_is_refused(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """A printed number is not accepted when it differs from ``casilla.id``."""

    _seed_profile(runtime_profile)
    work_unit_id = _create_m303_work_unit()

    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "69=0",
        ],
    )  # fmt: skip
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    output = result.output.replace("\n", " ")
    assert "printed casilla number or form number" in output
    assert "iva.resultado" in output
    assert "69" in output


def test_export_ref_metadata_token_is_refused(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """An export field id is not accepted as an alternate casilla reference."""

    _seed_profile(runtime_profile)
    work_unit_id = _create_m303_work_unit()

    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "modelo-303-page-01-casilla-46=0",
        ],
    )  # fmt: skip
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    output = result.output.replace("\n", " ")
    assert "export reference" in output
    assert "iva.resultado-regimen-general" in output
    assert "modelo-303-page-01-casilla-46" in output


# ---------------------------------------------------------------------------
# Unknown canonical-id candidate produces helpful error (contract)
# ---------------------------------------------------------------------------


def test_bare_numeric_unknown_casilla_surfaces_helpful_message(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """An unresolvable token raises a helpful BadParameter.

    The error must mention the original token so the operator can
    identify their typo, and must not produce a Python traceback.
    """

    _seed_profile(runtime_profile)
    work_unit_id = _create_m303_work_unit()

    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "99999=10.00",
        ],
    )  # fmt: skip
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    output = result.output.replace("\n", " ")
    assert "99999" in output, "error must name the unresolvable token"
    assert "canonical casilla.id" in output


# ---------------------------------------------------------------------------
# Canonical id passthrough
# ---------------------------------------------------------------------------


def test_qualified_casilla_key_passes_validation_unchanged(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """A canonical semantic casilla id reaches the engine unchanged.

    The engine refuses computed casillas, so the error must mention
    ``iva.resultado`` (the canonical id), proving the id was not
    reinterpreted as a printed number or corrupted before engine validation.
    """

    _seed_profile(runtime_profile)
    work_unit_id = _create_m303_work_unit()

    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "iva.resultado=0",
        ],
    )  # fmt: skip
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    output = result.output.replace("\n", " ")
    assert "iva.resultado" in output, (
        "engine error must name 'iva.resultado', proving the canonical id was not corrupted"
    )
    assert "not a canonical casilla.id" not in output, "canonical id must not trigger the unknown-casilla diagnostic"
    assert "printed casilla number" not in output, "canonical id must not trigger the printed-number refusal"
