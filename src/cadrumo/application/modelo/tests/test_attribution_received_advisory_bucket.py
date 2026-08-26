"""Integration coverage for the attribution-received advisory's load-from-bucket branch.

Every unit test in ``test_attribution_received_advisory`` passes ``profile_record=``
explicitly; this file exercises the PRODUCTION branch that loads the
:class:`UserProfileRecord` from a real encrypted bucket via
:class:`ProfileRecordRepository` (the ``profile_record=None`` default),
plus the :class:`ProfileNotFoundError` guard. Real secure store, no mocks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Modelo, Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos import ModeloCode, WorkUnit, derive_work_unit_id
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from .._attribution_received_advisory import _attribution_received_omission_advisory_findings

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET = "20000000-0000-4000-8000-000000000184"
_CLOCK = datetime(2026, 7, 9, tzinfo=UTC)
_FILING_YEAR = 2024


def _work_unit() -> WorkUnit:
    period = Period.from_year_and_code(_FILING_YEAR, "0A")
    revision_id = "r" + "0" * 63
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET,
            modelo=ModeloCode(Modelo.M100.value),
            filing_year=_FILING_YEAR,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET,
        modelo=ModeloCode(Modelo.M100.value),
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=revision_id,
        name="100-2024",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _received_facts() -> tuple[UserProfileFact, ...]:
    return (
        UserProfileFact(path="attribution_received.0.entity_nif", value="B12345678"),
        UserProfileFact(path="attribution_received.0.entity_name", value="Sociedad Civil Ejemplo"),
        UserProfileFact(path="attribution_received.0.share_pct", value=Decimal("50")),
        UserProfileFact(path="attribution_received.0.base_imponible_attributed", value=Decimal("58100.00")),
        UserProfileFact(path="attribution_received.0.filing_year", value=str(_FILING_YEAR)),
    )


def test_advisory_loads_attribution_facts_from_real_bucket(tmp_path: Path) -> None:
    snapshot = bundled_authority().snapshot("100", filing_year=_FILING_YEAR, period="0A")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label="Socio atribucion"):
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET,
                facts=_received_facts(),
                created_at=_CLOCK,
                updated_at=_CLOCK,
            ),
        )
        # profile_record omitted: the advisory loads the record from the active bucket.
        findings = _attribution_received_omission_advisory_findings(
            work_unit=_work_unit(),
            snapshot=snapshot,
            casilla_values={},
        )
    assert len(findings) == 1
    # The advisory loaded the attribution_received facts from the real encrypted
    # bucket (profile_record was not passed) and fired on the empty casilla.
    assert findings[0].message_facts["total_base"] == Decimal("58100.00")


def test_advisory_missing_profile_returns_no_finding(tmp_path: Path) -> None:
    snapshot = bundled_authority().snapshot("100", filing_year=_FILING_YEAR, period="0A")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label="Sin perfil"):
        # No profile saved: the load raises ProfileNotFoundError, guarded to no finding.
        findings = _attribution_received_omission_advisory_findings(
            work_unit=_work_unit(),
            snapshot=snapshot,
            casilla_values={},
        )
    assert findings == ()
