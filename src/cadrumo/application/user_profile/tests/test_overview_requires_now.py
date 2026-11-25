"""The overview decides which fields setup requires now; surfaces ask it rather than re-deriving the rule.

A field is required now when the overview lists it as missing, or when it is
required and already answered. A repeatable section's template row is marked
required but owes nothing until the operator adds a row, so an unanswered
required field the overview does not list as missing is not required now.
"""

from __future__ import annotations

import uuid

import pytest

from ....domain.user_profile.values import ProfileSetupState
from ..overview import ProfileFieldView, ProfileOverview, ProfileSectionView

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _field(path: str, *, required: bool, value: str | None) -> ProfileFieldView:
    return ProfileFieldView(path=path, label=path, value=value, masked=False, required=required)


_MISSING = _field("identidad.nif", required=True, value=None)
_ANSWERED = _field("identidad.nombre", required=True, value="Ana")
_TEMPLATE = _field("socios.nif", required=True, value=None)
_OPTIONAL = _field("identidad.alias", required=False, value="A")


def _overview() -> ProfileOverview:
    return ProfileOverview(
        profile_id=str(uuid.uuid4()),
        record_revision=1,
        content_digest="0" * 64,
        label="perfil",
        setup_state=ProfileSetupState.INCOMPLETE,
        sections=(
            ProfileSectionView(
                key="identidad",
                title="Identidad",
                summary="",
                repeatable=False,
                fields=(_MISSING, _ANSWERED, _OPTIONAL),
            ),
            ProfileSectionView(key="socios", title="Socios", summary="", repeatable=True, fields=(_TEMPLATE,)),
        ),
        missing_required=(_MISSING.path,),
    )


@pytest.mark.parametrize(
    ("field", "expected"),
    [(_MISSING, True), (_ANSWERED, True), (_TEMPLATE, False), (_OPTIONAL, False)],
    ids=["missing", "answered-required", "repeatable-template", "optional"],
)
def test_the_overview_says_which_fields_setup_requires_now(field: ProfileFieldView, expected: bool) -> None:
    assert _overview().requires_now(field) is expected
