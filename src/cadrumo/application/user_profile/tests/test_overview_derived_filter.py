"""The overview's derived-path filter, driven through the only route that reaches it.

The filter skips a declared field whose path falls inside a declared
derived-selector namespace, so the manager never renders an editable box the
write door would refuse. Measured against the shipped schema, ZERO declared
fields match any declared pattern -- the twenty year-suffixed declarations were
deleted, which is what makes the outcome correct. The consequence is that
"no derived row renders" is true by construction rather than by the filter, and
nothing distinguishes a working filter from an absent one.

The filter is still worth keeping and worth testing rather than deleting. It is
the guard that makes re-declaring one of these paths safe: the write door
refuses a derived path unconditionally, so a field re-declared without this
filter would render a box whose value the record then rejects -- the
two-surfaces-disagreeing failure the refusal exists to prevent, reintroduced at
the point of entry. A future filing year, or an operator-authored schema, can
put a matching declaration back; the cost of holding the guard is one branch
and the cost of dropping it is a silent regression at the worst boundary.

A synthetic schema is therefore the only way to reach the branch. Each
assertion carries its own discrimination: the SAME schema and record are
projected a second time with the derived namespace emptied, and the row appears.
That is the in-memory equivalent of deleting the filter, so a green result here
cannot come from the row being absent for some unrelated reason.
"""

from __future__ import annotations

import pytest

from cadrumo.application.user_profile.overview import build_profile_overview

from ....core.classification import SensitivityClass
from ....domain.user_profile.schema import ProfileDerivedSelectorDefinition, ProfileFieldDefinition, ProfileFieldType, ProfileRemovePolicy, ProfileSchemaDefinition, ProfileSectionDefinition, ProfileSnapshotPolicy, derived_selector_for_path
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....domain.user_profile.loader import load_user_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "11111111-1111-4111-8111-111111111112"
_DERIVED_PATH = "renta_family.descendientes_minimos_aggregate_2024"
_OPERATOR_PATH = "renta_family.minor_children_in_unit"


def _derived_selector() -> ProfileDerivedSelectorDefinition:
    return ProfileDerivedSelectorDefinition(
        pattern="renta_family.descendientes_minimos_aggregate_{filing_year}",
        derived_from=("renta_family.descendiente",),
        entry_surface="aeat config profile descendiente",
        description="Parte estatal del minimo por descendientes.",
    )


def _schema(*, derived: bool) -> ProfileSchemaDefinition:
    """A schema declaring one derived-matching field beside one operator field.

    ``derived=False`` empties the derived namespace while leaving the field
    declarations identical, which is the in-memory stand-in for removing the
    filter.
    """
    return ProfileSchemaDefinition(
        id="test.overview.derived",
        version=1,
        title="Derived filter test schema",
        snapshot_policy=ProfileSnapshotPolicy.IMMUTABLE_SECURE_SNAPSHOT_HASH,
        remove_policy=ProfileRemovePolicy.LIVE_PROFILE_TOMBSTONE_RETAIN_SNAPSHOTS,
        sections=(
            ProfileSectionDefinition(
                key="renta_family",
                title="Renta family",
                sensitivity=SensitivityClass.FINANCIAL,
                fields=(
                    ProfileFieldDefinition(
                        key="descendientes_minimos_aggregate_2024",
                        type=ProfileFieldType.DECIMAL,
                        required=False,
                        sensitivity=SensitivityClass.FINANCIAL,
                        description="Engine-computed Art. 58 aggregate.",
                    ),
                    ProfileFieldDefinition(
                        key="minor_children_in_unit",
                        type=ProfileFieldType.BOOLEAN,
                        required=False,
                        sensitivity=SensitivityClass.FINANCIAL,
                        description="Operator-entered flag.",
                    ),
                ),
            ),
        ),
        derived_selectors=(_derived_selector(),) if derived else (),
    )


def _record() -> UserProfileRecord:
    return UserProfileRecord(
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=(UserProfileFact(path=_OPERATOR_PATH, value=False),),
    )


def _rendered_paths(*, derived: bool) -> set[str]:
    overview = build_profile_overview(_record(), schema=_schema(derived=derived))
    return {view.path for section in overview.sections for view in section.fields}


def test_a_declared_field_inside_a_derived_namespace_renders_no_row() -> None:
    """The filter's whole job, driven through the only schema that reaches it."""
    assert _DERIVED_PATH not in _rendered_paths(derived=True)


def test_the_same_field_renders_once_the_derived_namespace_is_empty() -> None:
    """Discrimination: with the namespace emptied, the row comes back.

    Identical schema and record, differing only in whether the pattern is
    declared. Without this the assertion above would be satisfied just as well
    by a projection that dropped the field for an unrelated reason -- a
    mis-typed key, a sensitivity rule, a namespace-type branch.
    """
    assert _DERIVED_PATH in _rendered_paths(derived=False)


def test_the_filter_does_not_reach_an_operator_field_beside_it() -> None:
    """Scope: the neighbouring operator-entered field is untouched either way."""
    assert _OPERATOR_PATH in _rendered_paths(derived=True)
    assert _OPERATOR_PATH in _rendered_paths(derived=False)


def test_the_shipped_schema_declares_no_field_the_filter_would_catch() -> None:
    """Why a synthetic schema is required, asserted rather than described.

    If this ever fails, a declaration has been reintroduced into the shipped
    schema inside a derived namespace. That is precisely the case the filter
    exists for, and the write door now refuses writes to it -- so the pairing
    needs re-reading rather than the test being relaxed.
    """
    schema = load_user_profile_schema()
    matching = [
        f"{section.key}.{field.key}"
        for section in schema.sections
        for field in section.fields
        if derived_selector_for_path(f"{section.key}.{field.key}", schema.derived_selectors) is not None
    ]

    assert matching == [], matching
