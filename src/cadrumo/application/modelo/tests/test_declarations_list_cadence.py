"""The new-declaration choices follow the filing cadence the profile's facts select.

Modelo 303's registry declares a monthly and a quarterly filing schedule: RIVA
art. 71.3 makes the IVA period monthly for a REDEME enrolee or a gran empresa
and quarterly otherwise. The list read through the real capture door offers
only the family the profile selects, keeps both visibly waiting on the fact
while the gran empresa question is unanswered, leaves a modelo whose schedule
no profile fact splits untouched, and suggests one next return per modelo.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, cast
from uuid import UUID

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.user_profile.labels import profile_field_label_key
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...tests.workbench_generation_support import PROFILE_ID, Repository, plain_generation_door
from ..declaration_targets import declaration_targets
from ..declarations_list_operation import (
    ModeloDeclarationsListProjectionV1,
    ModeloDeclarationsListRequest,
    project_declarations_list,
)
from ..declarations_list_projection import ModeloDeclarationCreationTargetV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LARGE_COMPANY = "censo.large_company"
_REDEME = "iva.redeme_enrolled"
_FACTS: dict[str, object] = {
    "identity.tax_id": "12345678Z",
    "taxpayer_type.entity_type": "natural_person",
    "taxpayer_type.irpf_income_categories": "actividad_economica",
    "activities.description": "Servicios profesionales",
    "censo.activity_start_date": date(filing_year_envelope().floor, 1, 10).isoformat(),
    "irpf.estimation_regime": "directa_simplificada",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": False,
    "iva.sii_enrolled": False,
    "iva.cash_accounting_regime_enrolled": False,
    "iva.voluntary_sii_enrolled": False,
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": False,
    "tax_residence.jurisdiction_scope": "common_regime",
    "tax_residence.autonomous_community": "madrid",
}


def _list(operation: PinnedAuthorityOperation, **answers: object) -> ModeloDeclarationsListProjectionV1:
    facts = {**_FACTS, **{path.replace("__", "."): value for path, value in answers.items()}}
    record = create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=tuple(UserProfileFact(path=path, value=value) for path, value in facts.items() if value is not None),
    )
    door = plain_generation_door(operation, profile=cast(Any, Repository(record)))
    inputs = door.read_declaration_list_inputs()
    assert inputs.workspace is not None
    request = ModeloDeclarationsListRequest(profile_id=UUID(PROFILE_ID), output_language=OutputLanguage.EN)
    return project_declarations_list(request, inputs.workspace, inputs.calendar)


def _periods_by_kind(operation: PinnedAuthorityOperation, modelo: str) -> dict[str, frozenset[str]]:
    """Each schedule family's period codes, as the registry declares them for ``modelo``."""
    kinds: dict[str, set[str]] = defaultdict(set)
    for revision in operation.modelo_directory(modelo).revisions:
        for schedule in revision.filing_schedules:
            kinds[schedule.period_kind].update(schedule.periods)
    return {kind: frozenset(codes) for kind, codes in kinds.items()}


def _targets(listed: ModeloDeclarationsListProjectionV1, modelo: str) -> tuple[ModeloDeclarationCreationTargetV1, ...]:
    return tuple(target for target in listed.creation_targets if target.modelo == modelo)


def _kinds_offered(operation: PinnedAuthorityOperation, listed: ModeloDeclarationsListProjectionV1) -> set[str]:
    families = _periods_by_kind(operation, "303")
    return {
        kind for target in _targets(listed, "303") for kind, codes in families.items() if target.period_code in codes
    }


def test_the_registry_splits_modelo_303_into_a_monthly_and_a_quarterly_family(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    families = _periods_by_kind(authority_operation, "303")
    assert set(families) == {"monthly", "quarterly"}
    assert not families["monthly"] & families["quarterly"]


@pytest.mark.parametrize(
    "answers",
    [{"iva__redeme_enrolled": True}, {"censo__large_company": True}],
    ids=["redeme", "gran_empresa"],
)
def test_a_monthly_filer_is_offered_only_monthly_303_periods(
    authority_operation: PinnedAuthorityOperation, answers: dict[str, object]
) -> None:
    listed = _list(authority_operation, **answers)

    assert _targets(listed, "303")
    assert _kinds_offered(authority_operation, listed) == {"monthly"}
    assert all(not target.profile_requirements for target in _targets(listed, "303"))


def test_a_quarterly_filer_is_offered_only_quarterly_303_periods(authority_operation: PinnedAuthorityOperation) -> None:
    listed = _list(authority_operation, censo__large_company=False)

    assert _targets(listed, "303")
    assert _kinds_offered(authority_operation, listed) == {"quarterly"}
    assert all(target.profile_requirements_words is None for target in _targets(listed, "303"))


def test_an_unanswered_gran_empresa_question_keeps_both_families_naming_the_fact(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    listed = _list(authority_operation)
    section, field = _LARGE_COMPANY.split(".")
    label = tr(profile_field_label_key(section, field), locale=OutputLanguage.EN.value)

    assert _kinds_offered(authority_operation, listed) == {"monthly", "quarterly"}
    for target in _targets(listed, "303"):
        assert target.profile_requirements == (label,)
        assert target.profile_requirements_words == tr(
            "workspace.declarations.list.new.profile_requirements", locale=OutputLanguage.EN.value
        )
        assert not target.suggested


def test_a_modelo_whose_schedule_no_profile_fact_splits_is_offered_unchanged(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    unfiltered = {
        (target.period.filing_year, str(target.period.code))
        for target in declaration_targets(authority_operation, profile=None)
        if target.modelo == "130"
    }
    assert unfiltered
    for answers in ({"censo__large_company": False}, {"iva__redeme_enrolled": True}, {}):
        listed = _list(authority_operation, **answers)
        offered = {(target.filing_year, target.period_code) for target in _targets(listed, "130")}
        assert offered == unfiltered
        assert all(not target.profile_requirements for target in _targets(listed, "130"))


def test_each_modelo_suggests_its_own_first_return_due(authority_operation: PinnedAuthorityOperation) -> None:
    listed = _list(authority_operation, censo__large_company=False, iva__redeme_enrolled=False)
    offered = {(target.modelo, target.filing_year, target.period_code) for target in listed.creation_targets}
    due: dict[str, list[tuple[date, int, str]]] = defaultdict(list)
    for row in listed.rows:
        if (
            row.state == "not_started"
            and row.filing_year is not None
            and row.period_code is not None
            and (row.modelo, row.filing_year, row.period_code) in offered
        ):
            due[row.modelo].append((row.deadline or date.max, row.filing_year, row.period_code))
    suggested: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for target in listed.creation_targets:
        if target.suggested:
            assert not target.profile_requirements
            suggested[target.modelo].append((target.filing_year, target.period_code))

    assert len(due) > 1, "the profile has returns due for more than one modelo"
    decided = {target.modelo for target in listed.creation_targets if not target.profile_requirements}
    assert set(suggested) == decided
    assert all(len(addresses) == 1 for addresses in suggested.values())
    for modelo, rows in due.items():
        earliest = min(deadline for deadline, _year, _code in rows)
        assert suggested[modelo][0] in {(year, code) for deadline, year, code in rows if deadline == earliest}
