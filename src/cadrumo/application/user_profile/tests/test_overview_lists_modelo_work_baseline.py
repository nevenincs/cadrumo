"""The manager lists the profile facts the modelo-work gate refuses without.

An economically active natural person owes an activity description before any
filing-grade declaration can be created. The field lives in the repeatable
``activities`` section, so a profile holding no activity row had nothing at all
to show for it: the header counted every required detail as filled and
Declaraciones refused creating a Modelo 303 for want of that very field. The
overview now reads the requirement from the gate that refuses on it, and the
blank row a section with no rows stands for carries the required mark.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.calculations.registry.irpf_income_categories import irpf_income_category_actividad_economica_token
from ....domain.contribuyente.entity_type import entity_type_natural_person_token
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...modelo.profile_readiness_gate import modelo_work_profile_baseline_missing_paths
from ..overview import build_profile_overview

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "33333333-3333-4333-8333-333333333333"
_ACTIVITY_DESCRIPTION = "activities.description"


def _overview(income_category: str):
    """Build the manager's view of a natural person declaring ``income_category``.

    Everything but the activity description is in place: a tax id, the entity
    type, and the income the taxpayer declares. The activity section holds no
    row at all, which is the profile shape the defect was reported on.
    """
    with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
        facts = (
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="taxpayer_type.entity_type", value=entity_type_natural_person_token().value),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value=income_category),
        )
        record = create_user_profile_record(
            context=operation.profile_create_context(),
            profile_id=_PROFILE_ID,
            setup_state=ProfileSetupState.INCOMPLETE,
            facts=facts,
        )
        return record, build_profile_overview(record, label="Perfil", schema=operation.profile_schema())


def _economic_activity() -> str:
    with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
        return irpf_income_category_actividad_economica_token().value


def test_an_active_profile_without_an_activity_row_reports_the_description_missing() -> None:
    """DISCRIMINATING: the field the work-create gate refuses on is reported missing."""
    record, overview = _overview(_economic_activity())

    # The gate's own answer, so the two surfaces cannot disagree about it.
    with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
        assert _ACTIVITY_DESCRIPTION in modelo_work_profile_baseline_missing_paths(record)
    assert _ACTIVITY_DESCRIPTION in overview.missing_required


def test_the_blank_activity_row_carries_the_required_mark() -> None:
    """REGRESSION: the entry the filer fills in stays an offered, required one."""
    _record, overview = _overview(_economic_activity())

    rows = {field.path: field for section in overview.sections for field in section.fields}
    assert rows[_ACTIVITY_DESCRIPTION].required


def test_the_description_is_reported_once_per_unfilled_detail() -> None:
    """DISCRIMINATING: one blank detail is one outstanding entry, not two."""
    _record, overview = _overview(_economic_activity())

    reported = [path for path in overview.missing_required if path.endswith(".description")]
    assert reported == [_ACTIVITY_DESCRIPTION]


def test_a_salaried_profile_is_not_asked_for_an_activity() -> None:
    """ANTI-VACUITY: a profile declaring no economic activity owes no description."""
    record, overview = _overview("trabajo")

    with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
        assert _ACTIVITY_DESCRIPTION not in modelo_work_profile_baseline_missing_paths(record)
    assert _ACTIVITY_DESCRIPTION not in overview.missing_required
