"""Real-behavior tests for the classify-path censo business_pct stamping.

Locks that :func:`cadrumo.entrypoints.cli._ledger_support.resolve_business_pct_with_censo`
derives the HOME_OFFICE business_pct from the operator-declared
``vivienda_office`` m² facts (the re-seated ``bound_raw_afectacion_ratio``
source) when the operator omits an explicit percentage, and leaves an
operator-supplied value untouched.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest
from dev.registry.compiler.fact_providers import compile_authored_fact_catalogue
from dev.registry.tests.profile_schema_support import load_user_profile_schema

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record

from ....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ....core.resources.bundled_data import bundled_path
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.authority_artifact import GovernedFactComponentQuery, ProfileSchemaComponentQuery
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.calculations.registry.tests.authority_fakes import FakeAuthorityComponentReader
from ....domain.categories.spending_category import SpendingCategory
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from .._ledger_support import resolve_business_pct_with_censo

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "36363636-3636-4636-8636-363636363636"
_SUMINISTROS = SpendingCategory.from_registry("suministros_home_office_internet").value

runtime = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime")


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    """Expose canonical authored facts through one pinned component reader."""
    facts = compile_authored_fact_catalogue(bundled_path("registry", "aeat"))
    reader = FakeAuthorityComponentReader(
        {
            **{GovernedFactComponentQuery(str(fact_id)): fact for fact_id, fact in facts.facts.items()},
            ProfileSchemaComponentQuery(): load_user_profile_schema(),
        }
    )
    pinned = PinnedAuthorityOperation(reader, reader.pin())
    with validating_governed_facts(pinned):
        yield pinned


def _declare_vivienda_office(operation: PinnedAuthorityOperation) -> None:
    seed_test_profile_record(
        create_user_profile_record(
            context=operation.profile_create_context(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="vivienda_office.total_m2", value=Decimal("100")),
                UserProfileFact(path="vivienda_office.office_m2", value=Decimal("20")),
            ),
        ),
        label="Classify censo pct profile",
    )


def test_classify_stamps_derived_business_pct_from_operator_declared_facts(
    runtime: TestRuntimeProfile,
    operation: PinnedAuthorityOperation,
) -> None:
    _declare_vivienda_office(operation)
    resolved = resolve_business_pct_with_censo(
        bucket_id=_BUCKET_ID,
        active_profile=_BUCKET_ID,
        category_id=_SUMINISTROS,
        operator_supplied=None,
        year=2025,
        operation=operation,
    )
    # raw afectación 20/100 = 0.20; suministros deduct at raw * 0.30 (LIRPF Art. 30.2 rule 5).
    assert resolved == Decimal("0.060")


def test_classify_leaves_operator_supplied_pct_untouched(
    runtime: TestRuntimeProfile,
    operation: PinnedAuthorityOperation,
) -> None:
    _declare_vivienda_office(operation)
    resolved = resolve_business_pct_with_censo(
        bucket_id=_BUCKET_ID,
        active_profile=_BUCKET_ID,
        category_id=_SUMINISTROS,
        operator_supplied=Decimal("0.42"),
        year=2025,
        operation=operation,
    )
    assert resolved == Decimal("0.42")


def test_classify_returns_none_when_no_vivienda_office_facts(
    runtime: TestRuntimeProfile,
    operation: PinnedAuthorityOperation,
) -> None:
    resolved = resolve_business_pct_with_censo(
        bucket_id=_BUCKET_ID,
        active_profile=_BUCKET_ID,
        category_id=_SUMINISTROS,
        operator_supplied=None,
        year=2025,
        operation=operation,
    )
    assert resolved is None
