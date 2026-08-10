"""Locale-neutral identity coverage for modelo verification findings."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core import CasillaId, validated_casilla_id
from ....core.config import override_settings
from ....core.resources import resources
from ....domain.calculations.registry import CasillaDefinition
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...user_profile import UserProfileLifecycleRepository
from .._verification_actions import missing_required_casilla_finding

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "13000000-0000-4000-8000-000000000293"
_CASILLA_01: CasillaId = validated_casilla_id("01", surface="missing-required language test")
_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _m130_casilla_definition(casilla_id: CasillaId) -> CasillaDefinition:
    snapshot = resources().modelos.authority.snapshot("130", filing_year=2026, period="1T")
    return next(item for item in snapshot.revision.casillas if item.id == casilla_id)


def _save_active_profile_language(runtime: TestRuntimeProfile, language: str) -> None:
    UserProfileLifecycleRepository(bucket_id=runtime.bucket_id, objects=runtime.repository).save(
        UserProfileRecord(
            profile_id=runtime.bucket_id,
            display_name="Language regression operator",
            facts=(
                UserProfileFact(path="identity.tax_id", value="00000000T"),
                UserProfileFact(path="preferences.output_language", value=language),
            ),
            created_at=_NOW,
            updated_at=_NOW,
        ),
    )


def _missing_required_finding_identity() -> tuple[str, dict[str, str | int | bool]]:
    finding = missing_required_casilla_finding(
        _CASILLA_01,
        casilla_def=_m130_casilla_definition(_CASILLA_01),
    )
    return finding.message_locale_key, dict(finding.message_facts)


def test_missing_required_casilla_finding_is_independent_of_active_profile_language(tmp_path: Path) -> None:
    """Active profile language does not alter the finding's durable identity or facts."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        _save_active_profile_language(runtime, "ca")
        with override_settings(cadrumo_output_language=None):
            catalan_identity = _missing_required_finding_identity()

        _save_active_profile_language(runtime, "es")
        with override_settings(cadrumo_output_language=None):
            spanish_identity = _missing_required_finding_identity()

    expected = ("application.modelo.findings.missing_required_casilla", {"casilla_id": str(_CASILLA_01)})
    assert catalan_identity == expected
    assert spanish_identity == expected
