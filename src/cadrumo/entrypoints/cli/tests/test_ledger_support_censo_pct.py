"""Real-behavior tests for the classify-path censo business_pct stamping.

Locks that :func:`cadrumo.entrypoints.cli._ledger_support._resolve_business_pct_with_censo`
derives the HOME_OFFICE business_pct from the operator-declared
``vivienda_office`` m² facts (the re-seated ``bound_raw_afectacion_ratio``
source) when the operator omits an explicit percentage, and leaves an
operator-supplied value untouched.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ....domain.categories import SpendingCategory
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import TestRuntimeProfile
from .._ledger_support import _resolve_business_pct_with_censo

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "36363636-3636-4636-8636-363636363636"
_SUMINISTROS = SpendingCategory.SUMINISTROS_HOME_OFFICE_INTERNET.value

runtime = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime")


def _declare_vivienda_office() -> None:
    seed_test_profile_record(
        UserProfileRecord(setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="vivienda_office.total_m2", value=Decimal("100")),
                UserProfileFact(path="vivienda_office.office_m2", value=Decimal("20")),
            ),
        ),
        label="Classify censo pct profile",
    )


def test_classify_stamps_derived_business_pct_from_operator_declared_facts(runtime: TestRuntimeProfile) -> None:
    _declare_vivienda_office()
    resolved = _resolve_business_pct_with_censo(
        bucket_id=_BUCKET_ID,
        active_profile=_BUCKET_ID,
        category_id=_SUMINISTROS,
        operator_supplied=None,
    )
    # raw afectación 20/100 = 0.20; suministros deduct at raw * 0.30 (LIRPF Art. 30.2 rule 5).
    assert resolved == Decimal("0.060")


def test_classify_leaves_operator_supplied_pct_untouched(runtime: TestRuntimeProfile) -> None:
    _declare_vivienda_office()
    resolved = _resolve_business_pct_with_censo(
        bucket_id=_BUCKET_ID,
        active_profile=_BUCKET_ID,
        category_id=_SUMINISTROS,
        operator_supplied=Decimal("0.42"),
    )
    assert resolved == Decimal("0.42")


def test_classify_returns_none_when_no_vivienda_office_facts(runtime: TestRuntimeProfile) -> None:
    resolved = _resolve_business_pct_with_censo(
        bucket_id=_BUCKET_ID,
        active_profile=_BUCKET_ID,
        category_id=_SUMINISTROS,
        operator_supplied=None,
    )
    assert resolved is None
