"""An edit refused after its values were admitted settles under the refusal that stopped it.

When the recalculation reads a Modelo 200 revision whose published authority
cannot satisfy a filing snapshot, the registry gate refuses. The edit carries
that refusal's code, a key no value completes and its door with every value
taken out, and settles as that refusal, never as "state the value again". Real
registry gate, real published authority, real refusal translation.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.errors.error_codes import get_registered_error_code, resolve_error_message
from ....core.errors.hierarchy import CadrumoError, RecordedRegisteredError
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import extract_placeholders, tr
from ....core.operator_action_enums import ActionArgumentStatus, ActionConditionality
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import (
    RegistryFailureClassification,
    RegistryFailureCondition,
    RegistryValidationError,
)
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ..action_errors import modelo_edit_refusal_error
from ..edit_execution import pre_effect_refusal
from ..edit_models import ModeloEditDomainRefusalV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REGISTRY_CODE = "ERROR_CALCULATIONS_REGISTRY_VALIDATION"
_PROFILE_LABEL = "Synthetic profile label"


def _filing_snapshot_refusal(operation: PinnedAuthorityOperation) -> RegistryValidationError:
    """The registry gate's refusal of a filing snapshot of a Modelo 200 year whose authority cannot give one."""
    support = published_supported_filing_years()
    assert support is not None
    for year in sorted(support.years):
        try:
            operation.snapshot("200", filing_year=year, period="0A", grade=RegistryAuthorityGrade.FILING)
        except RegistryValidationError as refused:
            if type(refused) is RegistryValidationError:
                return refused
    raise AssertionError("every supported Modelo 200 year reaches filing grade; no gate refusal to settle")


@dataclass(frozen=True, slots=True)
class _Settled:
    inner: RegistryValidationError
    refusal: ModeloEditDomainRefusalV1
    error: CadrumoError


@pytest.fixture
def settled(authority_operation: PinnedAuthorityOperation) -> _Settled:
    inner = _filing_snapshot_refusal(authority_operation)
    refusal = pre_effect_refusal(inner).refusal
    assert isinstance(refusal, ModeloEditDomainRefusalV1)
    return _Settled(inner=inner, refusal=refusal, error=modelo_edit_refusal_error(refusal))


def test_a_registry_refusal_after_admission_settles_under_its_own_code(settled: _Settled) -> None:
    assert isinstance(settled.error, RecordedRegisteredError)
    assert get_registered_error_code(settled.error).code == _REGISTRY_CODE


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_the_settled_refusal_serves_the_registry_refusals_words(settled: _Settled, language: OutputLanguage) -> None:
    registered = get_registered_error_code(settled.error)
    words = resolve_error_message(settled.error, locale=language.value)

    assert words == tr(registered.message_key, locale=language.value)
    assert words.strip()
    assert words != registered.message_key
    assert not extract_placeholders(words)


def test_the_settled_refusal_opens_the_registry_refusals_door(settled: _Settled) -> None:
    inner_door = nested_terminal_precondition_verdict(settled.inner)
    door = nested_terminal_precondition_verdict(settled.error)

    assert inner_door is not None
    assert door is not None
    assert door.failed_condition_id == inner_door.failed_condition_id
    assert door.no_recovery_outcome is inner_door.no_recovery_outcome
    assert door.action == inner_door.action


def test_nothing_the_registry_named_travels(settled: _Settled) -> None:
    """No modelo, revision or grade: no context, and the door states one value-free fact."""
    door = nested_terminal_precondition_verdict(settled.error)

    assert settled.error.context is None
    assert door is not None
    assert [dict(evidence.values) for evidence in door.evidence] == [{"edit_values_admitted": True}]
    assert set(settled.refusal.facts) == {_REGISTRY_CODE}


def test_a_door_keeps_its_action_and_argument_names_but_never_their_values() -> None:
    inner = RegistryValidationError(
        "private exception sentence must never travel",
        registry_failure=RegistryFailureClassification(
            condition=RegistryFailureCondition.TAXPAYER_MODEL_DECLARED,
            facts={"profile_name": _PROFILE_LABEL},
        ),
    )

    refusal = pre_effect_refusal(inner).refusal
    assert isinstance(refusal, ModeloEditDomainRefusalV1)
    error = modelo_edit_refusal_error(refusal)

    door = nested_terminal_precondition_verdict(error)
    assert door is not None and door.action is not None
    assert door.action.action_id == "operator.profile.edit"
    assert [(binding.argument_name, binding.status) for binding in door.argument_bindings] == [
        ("profile_name", ActionArgumentStatus.MISSING)
    ]
    assert door.conditionality is ActionConditionality.REQUIRES_ARGUMENTS
    assert _PROFILE_LABEL not in refusal.model_dump_json()
    assert "private exception" not in refusal.model_dump_json()
    for language in OutputLanguage:
        assert _PROFILE_LABEL not in resolve_error_message(error, locale=language.value)
