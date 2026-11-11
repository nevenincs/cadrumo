"""Every readiness surface owes the IVA regime exactly when the taxpayer has economic activity.

The schema marks the regime required on its one unconditional axis, while a
natural person without economic activity has no regime to declare. The setup
promotion's validation relaxed it and the overview page did not, so the page
listed the regime as missing on a pensioner's profile and the CLI refused to
complete a setup the operation itself accepts. These tests read every surface
through its real owner against one pair of profiles that differ only in the
activity category.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.irpf_income_categories import (
    irpf_income_category_actividad_economica_token,
    irpf_income_category_choices,
)
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context,
    published_profile_schema,
)
from ....domain.contribuyente.entity_type import entity_type_natural_person_token
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ..completeness import (
    ENTITY_TYPE_PATH,
    IRPF_INCOME_CATEGORIES_PATH,
    IVA_REGIME_PATH,
    missing_required_field_paths,
    schema_requirement_applies,
)
from ..overview import build_profile_overview
from ..validation import REQUIRED_FIELD_MISSING_CODE, ProfileValidationService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_PROFILE_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def _values(*, economic_activity: bool) -> dict[str, str]:
    with bundled_indexed_authority().operation():
        activity = irpf_income_category_actividad_economica_token().value
        category = (
            activity
            if economic_activity
            else next(choice.value for choice in irpf_income_category_choices() if choice.value != activity)
        )
        return {
            ENTITY_TYPE_PATH: entity_type_natural_person_token().value,
            IRPF_INCOME_CATEGORIES_PATH: category,
        }


def _surfaces_owing_the_regime(values: Mapping[str, str]) -> dict[str, bool]:
    """Whether each readiness surface reports the blank IVA regime as missing."""
    schema = published_profile_schema()
    with bundled_indexed_authority().operation():
        record = create_user_profile_record(
            setup_state=ProfileSetupState.INCOMPLETE,
            profile_id=_PROFILE_ID,
            facts=tuple(UserProfileFact(path=path, value=value) for path, value in values.items()),
            context=leased_profile_create_context(),
        )
        overview = build_profile_overview(record, schema=schema)
        field = next(view for section in overview.sections for view in section.fields if view.path == IVA_REGIME_PATH)
        validation = ProfileValidationService(schema=schema).validate_record(record)
        return {
            "requirement": schema_requirement_applies(IVA_REGIME_PATH, values),
            "completeness": IVA_REGIME_PATH in missing_required_field_paths(schema, values),
            "overview_missing": IVA_REGIME_PATH in overview.missing_required,
            "overview_marked_required": field.required,
            "setup_validation": any(
                issue.code == REQUIRED_FIELD_MISSING_CODE and issue.path == IVA_REGIME_PATH
                for issue in validation.issues
            ),
        }


def test_a_profile_without_economic_activity_is_complete_without_an_iva_regime() -> None:
    surfaces = _surfaces_owing_the_regime(_values(economic_activity=False))

    assert not any(surfaces.values()), surfaces


def test_a_profile_with_economic_activity_still_owes_its_iva_regime() -> None:
    surfaces = _surfaces_owing_the_regime(_values(economic_activity=True))

    assert all(surfaces.values()), surfaces
