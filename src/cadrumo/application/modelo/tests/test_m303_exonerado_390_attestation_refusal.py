"""Every refusal of a Modelo 390 applicability attestation is a REFUSED code with served words and an honest door.

The operator's attestation request, or the evidence it names, is refused for a
fixed set of causes. None is a custody integrity fault: each says what was
refused in the operator's language and either names the action that puts it
right or states that none does.
"""

from __future__ import annotations

import pytest

from ....core.errors.error_codes import ErrorCategory, get_registered_error_code, resolve_error_message
from ....core.i18n.render import lookup_translation
from ....core.operator_action_enums import ActionArgumentStatus, ActionConditionality, NoRecoveryOutcome
from ....core.period import Period
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...operations.error_detail import build_operation_error_detail
from ...operator_surface.action_targets import resolve_recorded_precondition_action
from ..action_errors import M303Exonerado390AttestationUnadmissibleError
from ..m303_exonerado_390_applicability_attestation import m303_exonerado_390_filing_evidence_reference
from ..m303_exonerado_390_attestation_refusal import (
    PeriodAttestationRefusal,
    RequestAttestationRefusal,
    period_attestation_unadmissible,
    request_attestation_unadmissible,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("en", "es", "ca", "hu")
_CODE = "REFUSED_MODELO_M303_EXONERADO_390_ATTESTATION_UNADMISSIBLE"
_REPLACEABLE_PERIOD_CAUSES = {
    PeriodAttestationRefusal.OBSERVATION_TIMING,
    PeriodAttestationRefusal.STORED_OBSERVATION_TIMING,
    PeriodAttestationRefusal.EVIDENCE_OTHER_PROFILE,
    PeriodAttestationRefusal.EVIDENCE_NOT_ATTESTATION,
    PeriodAttestationRefusal.EVIDENCE_REFERENCE_INVALID,
    PeriodAttestationRefusal.EVIDENCE_COORDINATE_MISMATCH,
    PeriodAttestationRefusal.UNKNOWN_ATTACHMENT,
    PeriodAttestationRefusal.EVIDENCE_UNUSABLE,
}


def _period() -> Period:
    return Period.from_year_and_code(filing_year_envelope().horizon, "4T")


def _assert_served(error: M303Exonerado390AttestationUnadmissibleError) -> None:
    registered = get_registered_error_code(error)
    assert registered.code == _CODE
    assert registered.category is ErrorCategory.REFUSED
    key = error.translated_message
    assert key is not None
    for locale in _LOCALES:
        words_template = lookup_translation(key, locale=locale)
        assert words_template is not None and words_template.strip(), (key, locale)
        words = resolve_error_message(error, locale=locale)
        assert words
        assert "%{" not in words and "{" not in words
        assert "application.modelo" not in words and "errors." not in words
    detail = build_operation_error_detail(error)
    assert detail is not None
    assert detail.message_key == key
    assert detail.refusal_words is not None
    assert "{" not in detail.refusal_words
    assert _CODE not in detail.refusal_words
    assert detail.refusal_words_language is not None


@pytest.mark.parametrize("reason", list(PeriodAttestationRefusal))
def test_a_period_cause_is_served_and_names_its_door(reason: PeriodAttestationRefusal) -> None:
    period = _period()
    error = period_attestation_unadmissible(reason, period)

    _assert_served(error)
    detail = build_operation_error_detail(error)
    assert detail is not None
    assert detail.context_mapping()["reason"] == reason.value
    assert detail.context_mapping()["period"] == period.registry_token
    verdict = detail.precondition_verdict()
    assert verdict is not None
    if reason in _REPLACEABLE_PERIOD_CAUSES:
        assert verdict.action is not None
        assert verdict.action.action_id == "operator.modelo.work.attest_m303_exonerado_390"
        assert verdict.no_recovery_outcome is None
        assert verdict.conditionality is ActionConditionality.REQUIRES_ARGUMENTS
        assert verdict.missing_argument_names == ("observed_at",)
        resolved_values = {
            item.argument_name: item.value
            for item in verdict.argument_bindings
            if item.status is ActionArgumentStatus.RESOLVED
        }
        assert resolved_values == {"year": period.filing_year, "period": period.registry_token}
        resolved = resolve_recorded_precondition_action(verdict)
        assert resolved.action is not None and resolved.action.cli_path is not None
        assert resolved.action.cli_path[-3:] == ("modelo", "work", "attest-m303-exonerado-390")
        assert set(resolved.missing_argument_names) == {"observed_at"}
    else:
        assert verdict.action is None
        assert verdict.no_recovery_outcome is (
            NoRecoveryOutcome.TERMINAL
            if reason
            in {PeriodAttestationRefusal.COORDINATE_UNSUPPORTED, PeriodAttestationRefusal.APPLICABLE_UNSUPPORTED}
            else NoRecoveryOutcome.OPERATOR_DECISION
        )


@pytest.mark.parametrize("reason", list(RequestAttestationRefusal))
def test_a_request_cause_is_served_and_names_its_door(reason: RequestAttestationRefusal) -> None:
    error = request_attestation_unadmissible(
        reason, work_unit_id="w" * 64 if reason is RequestAttestationRefusal.NOT_MODELO_303_WORK_UNIT else None
    )

    _assert_served(error)
    detail = build_operation_error_detail(error)
    assert detail is not None
    assert detail.context_mapping()["reason"] == reason.value
    verdict = detail.precondition_verdict()
    assert verdict is not None
    if reason is RequestAttestationRefusal.PROFILE_NOT_CURRENT:
        assert verdict.action is not None and verdict.action.action_id == "operator.profile.status"
    else:
        assert verdict.action is None
        assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_malformed_identity_pair_is_refused_by_the_real_reference_builder() -> None:
    with pytest.raises(M303Exonerado390AttestationUnadmissibleError) as refused:
        m303_exonerado_390_filing_evidence_reference(attachment_id="not-a-digest", sha256="a" * 64)

    assert dict(refused.value.context or {})["reason"] == RequestAttestationRefusal.MALFORMED_IDENTITY.value
    _assert_served(refused.value)
