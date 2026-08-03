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

from ....core.classification import SensitivityClass
from ....domain.user_profile import (
    ProfileFieldDefinition,
    ProfileFieldType,
    ProfileRemovePolicy,
    ProfileSchemaDefinition,
    ProfileSectionDefinition,
    ProfileSnapshotPolicy,
    UserProfileFact,
    UserProfileRecord,
    UserProfileStatus,
)
from .. import MASKED_PLACEHOLDER, build_profile_overview

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
        display_name="Overview Subject",
        status=UserProfileStatus.SETUP_INCOMPLETE,
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


def test_the_clave_credential_inputs_mask_without_the_keyword_arm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shipped Cl@ve inputs mask by DECLARATION, not by their wording.

    DISCRIMINATING, and against the schema really shipped rather than the
    stand-in above. The sibling gates show these three fields mask; none
    of them can show WHY, and for a long time the why was an accident.
    Not one profile schema field declared ``secret``, so every masked
    field reached the mask through the keyword arm — "credential" happens
    to sit in each description. The confidentiality of a Cl@ve credential
    was therefore a property of prose nobody was required to keep, and
    rewording a description would have unmasked it silently.

    The measurement empties the keyword set at runtime and re-asks. That
    mutates the policy DATA, not the decision under test: with no
    keywords left, ``mask_profile_field`` has only the declaration to go
    on, so a field that still masks masks because the schema says so.

    ``censo.divergencia`` is the positive control. It masks today only on
    the word "token" in "provenance token", so it MUST stop masking under
    the mutation. If both halves still masked, the mutation never took
    and the first half would prove nothing.
    """
    from ....domain.user_profile import load_user_profile_schema
    from .. import mask_profile_field
    from .._overview import _MASK_KEYWORDS

    schema = load_user_profile_schema()

    def decision(path: str) -> bool:
        field_def = schema.field(path)
        return mask_profile_field(
            path=path,
            label=field_def.description or path,
            sensitivity=field_def.sensitivity,
        )

    keyword_reliant = "censo.divergencia"
    assert _MASK_KEYWORDS, "the keyword arm must be non-empty before the mutation"
    assert decision(keyword_reliant), "the control field must mask before the mutation"

    monkeypatch.setattr("cadrumo.application.user_profile._overview._MASK_KEYWORDS", frozenset())

    for path in ("auth.dni_nie", "auth.numero_soporte", "auth.fecha_validez"):
        assert decision(path), f"credential input {path!r} masks on its wording, not on its declaration"
    assert not decision(keyword_reliant), (
        "the keyword arm was not actually removed, so the declared fields above prove nothing"
    )
