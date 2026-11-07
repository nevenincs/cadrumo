"""A payer fact only an exclusion reads is a gating fact on the calendar.

Modelo 130's Art. 109 RIRPF coverage fact is authored as an applicability
``exclusion`` rather than as the rule's ``required_payer_fact``: a declared yes
lifts the pago-fraccionado duty. The calendar's gating readers took the
required fact alone, so such a fact only reached the operator when a deadline
window happened to name the same field. Modelo 130's windows do name it, which
masked the gap; these tests remove that second source and read the
applicability rules alone, so the exclusion reader is what has to answer.

The censo side is read here as well. ``calendar_censo_enrolment_state``
intersects the modelo's key set with the censo-stamped paths, so widening the
key set can only change its verdict for a payer fact whose profile field is
itself a censo axis. Modelo 347's SII and enrolment flags are not, so its
enrolment verdict stays what it was while its key set grows.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

import pytest

from ....domain.calculations.registry.applicability import iter_modelo_applicability_rules
from ....domain.calculations.registry.applicability_payer_facts import payer_fact_profile_keys
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from ...user_profile.projections import projection_for_taxpayer, record_to_path_values, record_to_values
from ...user_profile.tests.payer_fact_record_support import DECLARED_TAXPAYER_FACTS
from ..calendar import build_overview_calendar
from ..calendar_models import OverviewCalendar, OverviewCalendarRange, OverviewCensoEnrolmentState
from ..calendar_warnings import (
    calendar_applicability_profile_keys_for_modelo,
    calendar_censo_enrolment_state,
    derive_gating_fields,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "5aa00000-0000-4000-8000-0000000000ab"
_ART109_SELECTOR = "art109_activity_income_withholding_ge_70pct"
_ART109_PATH = f"irpf.{_ART109_SELECTOR}"
_PAGO_FRACCIONADO_MODELO = "130"
_THIRD_PARTY_MODELO = "347"
_TODAY = date(2026, 10, 19)
_RANGE = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2027, 2, 1))
_PROJECTION_SHAPES = ("path", "selector")


def _art109_record(operation: PinnedAuthorityOperation, *, answer: bool | None) -> UserProfileRecord:
    """Return a declared autónomo in estimación directa whose Art. 109 answer varies."""
    art109 = () if answer is None else (UserProfileFact(path=_ART109_PATH, value=answer),)
    return create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=_PROFILE_ID,
        facts=(*DECLARED_TAXPAYER_FACTS, *art109),
        setup_state=ProfileSetupState.COMPLETE,
    )


def _calendar(
    operation: PinnedAuthorityOperation,
    *,
    answer: bool | None,
    shape: str,
) -> OverviewCalendar:
    record = _art109_record(operation, answer=answer)
    schema = operation.profile_schema()
    raw: Mapping[str, object] = (
        record_to_path_values(record) if shape == "path" else record_to_values(record, schema=schema)
    )
    return build_overview_calendar(
        projection_for_taxpayer(record, schema=schema),
        _RANGE,
        operation=operation,
        today=_TODAY,
        raw_values=raw,
    )


def test_the_art109_fact_is_read_by_an_exclusion_and_required_by_no_rule(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The premise of these tests: no rule names the fact as its required one."""
    rules = list(iter_modelo_applicability_rules(operation=authority_operation))
    required = {
        key
        for rule in rules
        if rule.required_payer_fact is not None
        for key in payer_fact_profile_keys(rule.required_payer_fact)
    }
    excluding = {
        rule.modelo
        for rule in rules
        for exclusion in rule.exclusions
        if exclusion.payer_fact is not None and _ART109_SELECTOR in payer_fact_profile_keys(exclusion.payer_fact)
    }

    assert _ART109_SELECTOR not in required
    assert {str(modelo) for modelo in excluding} == {_PAGO_FRACCIONADO_MODELO}


def test_an_exclusion_only_payer_fact_gates_without_a_deadline_window(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """With no deadline window contributing, the applicability rules carry the fact."""
    gating = derive_gating_fields(operation=authority_operation, modelos=())

    assert _ART109_SELECTOR in gating
    affected_modelos, _message_key, _action_id = gating[_ART109_SELECTOR]
    assert affected_modelos == (_PAGO_FRACCIONADO_MODELO,)


def test_the_modelo_key_set_names_an_exclusion_only_payer_fact(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """An empty revision inventory leaves the applicability rules as the only source."""
    keys = calendar_applicability_profile_keys_for_modelo(
        _PAGO_FRACCIONADO_MODELO,
        operation=authority_operation,
        revision_inventory=(),
    )

    assert _ART109_SELECTOR in keys


@pytest.mark.parametrize("shape", _PROJECTION_SHAPES)
def test_an_unanswered_exclusion_payer_fact_warns_on_the_calendar(
    shape: str,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    calendar = _calendar(authority_operation, answer=None, shape=shape)

    warnings = [warning for warning in calendar.warnings if warning.code == _ART109_SELECTOR]
    assert len(warnings) == 1
    assert _PAGO_FRACCIONADO_MODELO in warnings[0].affected_modelos
    assert _ART109_SELECTOR in calendar.completeness.defaulted_keys


@pytest.mark.parametrize("shape", _PROJECTION_SHAPES)
@pytest.mark.parametrize("answer", [True, False])
def test_an_answered_exclusion_payer_fact_raises_no_calendar_warning(
    shape: str,
    answer: bool,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A stated yes lifts the duty and a stated no confirms it; neither is a gap."""
    calendar = _calendar(authority_operation, answer=answer, shape=shape)

    assert not [warning for warning in calendar.warnings if warning.code == _ART109_SELECTOR]
    assert _ART109_SELECTOR in calendar.completeness.explicitly_set_keys


def test_exclusion_payer_fact_keys_do_not_become_censo_requirements(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Modelo 347 gains its SII and enrolment keys without changing its censo verdict.

    The widened key set reaches ``calendar_censo_enrolment_state`` too, where
    only censo-stamped paths are required. Verifying the censo axes alone still
    witnesses enrolment, which is what proves the added flags were not promoted
    into censo requirements.
    """
    keys = calendar_applicability_profile_keys_for_modelo(
        _THIRD_PARTY_MODELO,
        operation=authority_operation,
        revision_inventory=(),
    )
    assert "iva.sii_enrolled" in keys

    state = calendar_censo_enrolment_state(
        modelo=_THIRD_PARTY_MODELO,
        live_censo_verified_profile_keys=("taxpayer_type.entity_type",),
        operation=authority_operation,
        revision_inventory=(),
    )

    assert state is OverviewCensoEnrolmentState.VERIFIED
