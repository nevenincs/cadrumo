"""Real-behavior tests: `required` on a repeatable row-field binds, per row.

Two findings share one fix and are covered together here, because there is
one rule underneath: a repeatable section is validated PER ROW.

The enforcing validator skipped repeatable sections wholesale, so 13 of the
15 fields the schema declares `required = true` were never reached and the
declaration bound nothing. The overview did not skip them but tested the
unindexed `section.field` while rows live at `section.INDEX.field`, so it
reported those fields missing on every profile forever - the completeness
count an operator reads was permanently wrong.

The obvious repair is wrong in both directions at once, which is the reason
these tests are shaped around rows rather than around the two call sites.
Because the presence set drops the row index, simply enabling the skipped
check would make an empty section raise (demanding every taxpayer hold an
attribution entity) while letting a second, incomplete row pass.

A section with no rows is silent by design: a taxpayer with no attribution
entities is not incomplete for lacking one.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.user_profile import UserProfileFact, load_user_profile_schema
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...workflow import workflow_state_repository
from .. import ProfileRepository, build_lifecycle_service, build_profile_overview, profile_create_storage_span
from .._completeness import missing_required_field_paths

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_TAX_ID = "12345678Z"
_SOCIOS = "attribution_entity_socios"


def _register_active() -> None:
    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id=_BUCKET_ID,
            display_name="per-row-operator",
            overrides={"identity.tax_id": _TAX_ID},
        ),
    )


def _append_facts(*facts: UserProfileFact) -> None:
    repository = ProfileRepository()
    aggregate = repository.load(_BUCKET_ID)
    record = aggregate.record
    repository.save(
        aggregate.model_copy(
            update={"record": record.model_copy(update={"facts": (*record.facts, *facts)})},
        ),
    )


def _complete_socio_row(index: int) -> tuple[UserProfileFact, ...]:
    return (
        UserProfileFact(path=f"{_SOCIOS}.{index}.nif", value="B12345678"),
        UserProfileFact(path=f"{_SOCIOS}.{index}.name", value="Socio Ejemplo"),
        UserProfileFact(path=f"{_SOCIOS}.{index}.share_pct", value=Decimal("50")),
        UserProfileFact(path=f"{_SOCIOS}.{index}.base_imponible_assigned", value=Decimal("1000")),
        UserProfileFact(path=f"{_SOCIOS}.{index}.role", value="socio"),
    )


def test_an_ordinary_taxpayer_is_complete_without_any_repeatable_rows() -> None:
    """The operator-facing regression: a valid profile must not read as incomplete.

    Every repeatable required field was reported missing on every profile,
    on the one screen whose purpose is saying whether the profile is ready.
    An indicator that always fires teaches the operator to stop reading it.
    """

    _register_active()
    overview = build_profile_overview(build_lifecycle_service(bucket_id=_BUCKET_ID).read(_BUCKET_ID))

    assert overview.missing_required == ()
    assert overview.complete


def test_a_row_that_exists_must_carry_every_required_field() -> None:
    """The enforcing half: `required` on a row-field now binds.

    Asserted on a SECOND row while the first is complete, because that is
    the case the index-dropping presence set would wave through - the
    first row's value satisfies the unindexed path for both.
    """

    _register_active()
    _append_facts(
        *_complete_socio_row(0),
        UserProfileFact(path=f"{_SOCIOS}.1.nif", value="B87654321"),
    )
    record = build_lifecycle_service(bucket_id=_BUCKET_ID).read(_BUCKET_ID)
    missing = build_profile_overview(record).missing_required

    assert f"{_SOCIOS}.1.name" in missing, (
        f"an incomplete second row was accepted; missing={missing}. The first row's "
        "value satisfies the unindexed path, which is why this is asserted on row 1."
    )
    assert not any(path.startswith(f"{_SOCIOS}.0.") for path in missing), (
        f"the complete first row was reported incomplete; missing={missing}"
    )


def test_the_enforcing_and_displayed_surfaces_agree() -> None:
    """They disagreed about repeatable rows, so agreement is asserted rather than assumed.

    One helper backs both; this fails if a future edit gives either its
    own copy of the rule.
    """

    _register_active()
    _append_facts(UserProfileFact(path=f"{_SOCIOS}.0.nif", value="B12345678"))
    record = build_lifecycle_service(bucket_id=_BUCKET_ID).read(_BUCKET_ID)

    displayed = set(build_profile_overview(record).missing_required)
    values = {fact.path: str(fact.value) for fact in record.facts if fact.value is not None}
    enforced = set(missing_required_field_paths(load_user_profile_schema(), values))

    assert displayed == enforced, (
        f"surfaces disagree: displayed-only={displayed - enforced}, enforced-only={enforced - displayed}"
    )


def test_presence_is_not_whitespace_stripped_here() -> None:
    """Pins the deliberate looseness so a future edit does not tighten it silently.

    These surfaces treat a whitespace-only value as present; the censal
    read strips before comparing and would refuse it. That divergence is
    real and tracked separately - it fails safe, since the strict surface
    is the one guarding a live AEAT read. Tightening it here would break
    the agreement the previous test locks in, so it must be a decision
    rather than a side effect.
    """

    _register_active()
    _append_facts(
        *_complete_socio_row(0)[:4],
        UserProfileFact(path=f"{_SOCIOS}.0.role", value="   "),
    )
    record = build_lifecycle_service(bucket_id=_BUCKET_ID).read(_BUCKET_ID)

    assert f"{_SOCIOS}.0.role" not in build_profile_overview(record).missing_required


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_BUCKET_ID),
    ):
        yield
