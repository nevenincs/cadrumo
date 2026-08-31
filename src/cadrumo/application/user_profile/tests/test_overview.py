"""Proofs for the profile overview projection.

Two claims carry weight here.

The first is that the walk is schema-driven, not fact-driven: a field the
operator has never filled in must still appear, as a visible blank. That
is the whole difference between "here is your profile" and "here is what
you happen to have answered", and a fact-driven implementation would pass
every other test in this file while silently hiding every empty field.

The second is that a secret-classed value never leaves the projection in
the clear. That is asserted by searching the serialised view for the
secret itself, so a future refactor that adds a field carrying the raw
value somewhere else in the model still fails.
"""

from __future__ import annotations

import pytest

from ....core.classification.policies import SensitivityClass
from ....domain.user_profile.schema import (
    ProfileFieldDefinition,
    ProfileFieldType,
    ProfileRemovePolicy,
    ProfileSchemaDefinition,
    ProfileSectionDefinition,
    ProfileSnapshotPolicy,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ..overview import MASKED_PLACEHOLDER, build_profile_overview

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "11111111-1111-4111-8111-111111111111"
_SECRET_VALUE = "a-distinctive-secret-value"  # noqa: S105 - synthetic test fixture


def _schema() -> ProfileSchemaDefinition:
    """A two-section schema: one required field, one optional, one secret."""
    return ProfileSchemaDefinition(
        id="test.overview",
        version=1,
        title="Overview test schema",
        snapshot_policy=ProfileSnapshotPolicy.IMMUTABLE_SECURE_SNAPSHOT_HASH,
        remove_policy=ProfileRemovePolicy.LIVE_PROFILE_TOMBSTONE_RETAIN_SNAPSHOTS,
        sections=(
            ProfileSectionDefinition(
                key="identity",
                title="Identity",
                sensitivity=SensitivityClass.IDENTITY,
                fields=(
                    ProfileFieldDefinition(
                        key="tax_id",
                        type=ProfileFieldType.STRING,
                        required=True,
                        sensitivity=SensitivityClass.IDENTITY,
                        description="Tax identifier",
                    ),
                    ProfileFieldDefinition(
                        key="nickname",
                        type=ProfileFieldType.STRING,
                        required=False,
                        sensitivity=SensitivityClass.IDENTITY,
                        description="Nickname",
                    ),
                ),
            ),
            ProfileSectionDefinition(
                key="access",
                title="Access",
                sensitivity=SensitivityClass.SECRET,
                fields=(
                    ProfileFieldDefinition(
                        key="portal_token",
                        type=ProfileFieldType.STRING,
                        required=False,
                        sensitivity=SensitivityClass.SECRET,
                        description="Portal token",
                    ),
                ),
            ),
        ),
    )


def _record(*facts: UserProfileFact) -> UserProfileRecord:
    return UserProfileRecord(
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.INCOMPLETE,
        facts=facts,
    )


def test_every_declared_field_appears_even_when_never_filled_in() -> None:
    """A schema field with no fact is a visible blank row, not an omission.

    The operator needs to see what is still empty. A fact-driven walk would
    render only the one populated row and hide the other two entirely.
    """
    overview = build_profile_overview(
        _record(UserProfileFact(path="identity.tax_id", value="12345678Z")),
        schema=_schema(),
    )

    paths = {field.path for section in overview.sections for field in section.fields}
    assert paths == {"identity.tax_id", "identity.nickname", "access.portal_token"}

    by_path = {field.path: field for section in overview.sections for field in section.fields}
    assert by_path["identity.tax_id"].present
    assert not by_path["identity.nickname"].present
    assert by_path["identity.nickname"].value is None


def test_a_secret_value_never_appears_in_the_projection() -> None:
    """The raw secret must not survive anywhere in the serialised view."""
    overview = build_profile_overview(
        _record(UserProfileFact(path="access.portal_token", value=_SECRET_VALUE)),
        schema=_schema(),
    )

    token = next(
        field for section in overview.sections for field in section.fields if field.path == "access.portal_token"
    )
    assert token.masked
    assert token.value == MASKED_PLACEHOLDER
    assert _SECRET_VALUE not in overview.model_dump_json()


def test_a_blank_secret_field_is_not_masked_into_looking_populated() -> None:
    """An unset secret renders empty, not as dots.

    Masking a blank would read as "something is set here" and send the
    operator looking for a value that does not exist.
    """
    overview = build_profile_overview(_record(), schema=_schema())
    token = next(
        field for section in overview.sections for field in section.fields if field.path == "access.portal_token"
    )
    assert token.masked, "the field is still secret-classed"
    assert token.value is None
    assert not token.present


def test_missing_required_names_only_required_blanks() -> None:
    """Completeness tracks required fields; optional blanks are not missing."""
    overview = build_profile_overview(_record(), schema=_schema())
    assert overview.missing_required == ("identity.tax_id",)
    assert not overview.complete

    filled = build_profile_overview(
        _record(UserProfileFact(path="identity.tax_id", value="12345678Z")),
        schema=_schema(),
    )
    assert filled.missing_required == ()
    assert filled.complete, "optional fields left blank still count as complete"


def test_counts_reflect_populated_versus_declared_fields() -> None:
    overview = build_profile_overview(
        _record(UserProfileFact(path="identity.tax_id", value="12345678Z")),
        schema=_schema(),
    )
    assert overview.total_count == 3
    assert overview.present_count == 1

    identity = next(section for section in overview.sections if section.key == "identity")
    assert identity.total_count == 2
    assert identity.present_count == 1


def test_sections_keep_their_schema_declaration_order() -> None:
    """Order is the schema's, so the page reads the way the schema declares."""
    overview = build_profile_overview(_record(), schema=_schema())
    assert [section.key for section in overview.sections] == ["identity", "access"]


def _shipped_decisions() -> dict[str, bool]:
    """Masking decision for every field the real shipped schema declares."""
    from ....domain.user_profile.loader import load_user_profile_schema
    from ..overview import mask_profile_field

    return {
        f"{section.key}.{field.key}": mask_profile_field(
            path=f"{section.key}.{field.key}",
            label=field.description,
            sensitivity=field.sensitivity,
        )
        for section in load_user_profile_schema().sections
        for field in section.fields
    }


def test_a_shipped_field_masks_exactly_when_the_schema_says_secret() -> None:
    """Masking a declared field is its classification and nothing else.

    DISCRIMINATING, and the property rather than today's masked set --
    pinning the set would re-freeze the accident it replaces. Every field
    the schema declares must mask if and only if it is classed
    ``secret``, so the assertion is derived per field instead of listed.

    It failed before the declaration became authoritative: no field
    declared ``secret`` at all, yet five masked, each of them through the
    keyword arm reading its own description. It fails again the day that
    arm is widened back over classified fields.
    """
    from ....domain.user_profile.loader import load_user_profile_schema
    from ..overview import mask_profile_field

    schema = load_user_profile_schema()
    divergent = {
        f"{section.key}.{field.key}": (decision, field.sensitivity.value)
        for section in schema.sections
        for field in section.fields
        if (
            decision := mask_profile_field(
                path=f"{section.key}.{field.key}",
                label=field.description,
                sensitivity=field.sensitivity,
            )
        )
        is not (field.sensitivity is SensitivityClass.SECRET)
    }
    assert not divergent, f"masking disagrees with the declaration for: {divergent}"


def _mask_keywords() -> frozenset[str]:
    from ..overview import _MASK_KEYWORDS

    return _MASK_KEYWORDS


@pytest.mark.parametrize("keyword", sorted(_mask_keywords()))
def test_no_wording_can_mask_a_field_the_schema_declares_non_secret(keyword: str) -> None:
    """A field's wording carries no authority over its classification.

    DISCRIMINATING, and the sharpest form of the guarantee: it re-asks
    the decision under a label built to contain each masking keyword in
    turn, and requires a field declared non-``secret`` to stay clear.
    Every one of these labels masked before the fix.

    It is written against a constructed label rather than the shipped
    descriptions on purpose. Reading the real prose would re-couple this
    proof to wording that is now inert -- the test would then break on an
    editorial change, which is the very dependency the fix removed. The
    shipped side is covered by the whole-schema gate above.

    The ``secret`` half is the positive control. Without it a
    ``mask_profile_field`` that simply never masked would satisfy the
    first assertion while protecting nothing.
    """
    from ..overview import mask_profile_field

    label = f"mentions a {keyword} only to say that none is stored here"

    assert not mask_profile_field(path="auth.provider", label=label, sensitivity=SensitivityClass.IDENTITY), (
        f"a label mentioning {keyword!r} masks a field the schema declares non-secret"
    )
    assert mask_profile_field(path="auth.provider", label=label, sensitivity=SensitivityClass.SECRET)


def test_no_shipped_field_depends_on_the_keyword_arm() -> None:
    """Emptying the keywords must change no shipped field's masking.

    DISCRIMINATING. Every field the schema declares is decided by its
    declaration, so removing the keyword set entirely must be inert over
    the shipped schema. Under the previous behaviour it was not:
    ``auth.provider`` and ``censo.divergencia`` masked only through the
    keywords, so both would flip here.

    The undeclared path is the positive control, and it does double duty.
    It proves the mutation actually took -- without it, a run where
    nothing changed would be indistinguishable from a monkeypatch that
    silently missed -- and it pins the keyword arm's remaining purpose,
    which is the one case it is for: a fact arriving under a path no
    schema field declares. A fix over-applied into "never mask anything
    unclassified" would pass the first assertion and fail here.
    """
    from .. import overview
    from ..overview import mask_profile_field

    stray = "unknown.api_credential"
    before = _shipped_decisions()
    assert mask_profile_field(path=stray, label=stray, sensitivity=None), (
        "the keyword arm must cover an undeclared credential-shaped fact before the mutation"
    )

    original_keywords = overview._MASK_KEYWORDS
    overview._MASK_KEYWORDS = frozenset()
    try:
        changed = {path: (was, now) for path, was in before.items() if (now := _shipped_decisions()[path]) is not was}
        assert not changed, f"these shipped fields mask through the keyword arm, not their declaration: {changed}"
        assert not mask_profile_field(path=stray, label=stray, sensitivity=None), (
            "the keyword arm was not actually removed, so the assertion above proves nothing"
        )
    finally:
        overview._MASK_KEYWORDS = original_keywords
