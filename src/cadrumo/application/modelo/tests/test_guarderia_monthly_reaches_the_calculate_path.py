"""A malformed descendant record refuses by index on the guardería resolver path.

The Art. 81.2 increment (casilla 0613) is derived from the canonical
:class:`~domain.contribuyente.family_profile.RentaFamilyProfile`; its month and
spend rules are proved by the domain tests and its end-to-end outcomes by the
CLI entry-surface tests. What this module keeps is the resolver-level guarantee
that an unparseable stored birth date is named, never skipped: skipping the row
would silently drop that child from the increment.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache

import pytest

from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context as _profile_creation_context_for_test,
)
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ..profile_binding import ProfileBindingResolutionError, resolve_profile_sourced_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease one generation for each guardería resolver path."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


_BUCKET = "0de41ce4-0000-4000-8000-000000000613"
_T0 = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)
_YEAR = 2024


@lru_cache
def _snapshot() -> RegistrySnapshot:
    return published_snapshot("100", filing_year=_YEAR, period="0A")


def test_an_unparseable_stored_birth_date_still_refuses_by_index(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """An unparseable stored date is a data defect the operator can fix once told where it is."""
    record = _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=(
            UserProfileFact(path="renta_family.descendiente.0.birth_date", value="not-a-date"),
            UserProfileFact(path="renta_family.descendientes_count", value="1"),
        ),
        created_at=_T0,
        updated_at=_T0,
        context=_profile_creation_context_for_test(),
    )

    with pytest.raises(ProfileBindingResolutionError, match=re.escape("renta_family.descendiente.0.birth_date")):
        resolve_profile_sourced_bindings(
            _snapshot(),
            bucket_id=_BUCKET,
            profile_record=record,
            operation=authority_operation,
        )
