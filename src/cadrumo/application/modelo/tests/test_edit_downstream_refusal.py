"""An edit refused after its values were admitted settles under the refusal that stopped it.

When the recalculation reads a Modelo 200 revision whose published authority
cannot satisfy a filing snapshot, the registry gate refuses. The edit carries
that refusal's code, a key no value completes and its door with every value
taken out, and settles as that refusal, never as "state the value again". A
refusal whose sentence names only public registry coordinates keeps exactly
those and is served finished; a sentence needing anything else names the code.
Real registry gate, real published authority, real refusal translation.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from pydantic import ValidationError

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
from ...operations.error_detail import UNWORDED_REGISTERED_ERROR_LOCALE_KEY
from ..action_errors import ModeloProfileReadinessError, modelo_edit_refusal_error
from ..edit_downstream_models import ModeloEditDownstreamContextEntryV1, ModeloEditDownstreamRefusalV1
from ..edit_downstream_refusal import downstream_refusal, downstream_refusal_error
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


_BINDING_KEY = "errors.calc.bound_casilla_binding_value_missing"
_BINDING = "prior-general-loss"
#: Synthetic private values; none may reach the refusal record or its words.
_AMOUNT = "4321.98"
_NAME_AND_TAX_ID = "Ana Ejemplo 00000000T"
_READINESS_KEY = "application.modelo.errors.profile_readiness_missing"


def _binding_error(binding_id: str) -> RegistryValidationError:
    return RegistryValidationError(
        f"private exception sentence {_AMOUNT}",
        translated_message=_BINDING_KEY,
        context={"binding_id": binding_id, "amount": _AMOUNT},
    )


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_a_sentence_naming_only_public_coordinates_is_served_finished(language: OutputLanguage) -> None:
    refusal = downstream_refusal(_binding_error(_BINDING))

    assert refusal.message_key == _BINDING_KEY
    assert refusal.context == (ModeloEditDownstreamContextEntryV1(key="binding_id", value=_BINDING),)
    words = resolve_error_message(downstream_refusal_error(refusal), locale=language.value)
    assert words == tr(_BINDING_KEY, locale=language.value, binding_id=_BINDING)
    assert _BINDING in words
    assert not extract_placeholders(words)
    assert _AMOUNT not in words
    assert _AMOUNT not in refusal.model_dump_json()


def test_a_sentence_needing_a_private_value_falls_back_to_the_code() -> None:
    support = published_supported_filing_years()
    assert support is not None
    error = ModeloProfileReadinessError(
        translated_message=_READINESS_KEY,
        context={
            "modelo": "130",
            "filing_year": support.horizon,
            "period": "1T",
            "profile_requirements": _NAME_AND_TAX_ID,
        },
    )
    refusal = downstream_refusal(error)

    assert refusal.message_key is None
    assert refusal.context == ()
    dumped = refusal.model_dump_json()
    assert _NAME_AND_TAX_ID not in dumped
    assert "profile_requirements" not in dumped
    settled = downstream_refusal_error(refusal)
    for language in OutputLanguage:
        words = resolve_error_message(settled, locale=language.value)
        assert words == tr(UNWORDED_REGISTERED_ERROR_LOCALE_KEY, locale=language.value, error_code=refusal.error_code)
        assert _NAME_AND_TAX_ID not in words


@pytest.mark.parametrize("binding_id", [_NAME_AND_TAX_ID, _AMOUNT + " EUR", "x" * 200, "C:/private/path"])
def test_a_public_key_whose_value_is_not_a_coordinate_is_dropped(binding_id: str) -> None:
    refusal = downstream_refusal(_binding_error(binding_id))

    assert refusal.message_key is None
    assert refusal.context == ()
    assert binding_id not in refusal.model_dump_json()
    words = resolve_error_message(downstream_refusal_error(refusal), locale=OutputLanguage.EN.value)
    assert binding_id not in words


def test_a_record_written_before_the_context_still_validates_and_keeps_its_shape() -> None:
    record = {"error_code": "ERROR_CALCULATIONS_REGISTRY_VALIDATION", "message_key": _BINDING_KEY}

    refusal = ModeloEditDownstreamRefusalV1.model_validate(record)

    assert refusal.context == ()
    assert "context" not in refusal.model_dump(mode="json")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("profile_requirements", "irpf.estimation_regime"),
        ("amount", "100"),
        ("binding_id", _NAME_AND_TAX_ID),
        ("modelo", "13O"),
        ("period", "first quarter"),
        ("filing_year", "1T"),
        ("casilla_ids", "0001,0002"),
    ],
)
def test_the_contract_refuses_a_key_or_value_outside_the_public_context(key: str, value: str) -> None:
    with pytest.raises(ValidationError) as raised:
        ModeloEditDownstreamContextEntryV1(key=key, value=value)
    assert value not in str(raised.value)


def test_the_contract_carries_context_only_with_its_sentence_each_key_once_in_order() -> None:
    modelo = ModeloEditDownstreamContextEntryV1(key="modelo", value="130")
    period = ModeloEditDownstreamContextEntryV1(key="period", value="1T")
    code = "ERROR_CALCULATIONS_REGISTRY_VALIDATION"

    with pytest.raises(ValidationError):
        ModeloEditDownstreamRefusalV1(error_code=code, context=(modelo,))
    with pytest.raises(ValidationError):
        ModeloEditDownstreamRefusalV1(error_code=code, message_key=_BINDING_KEY, context=(period, modelo))
    with pytest.raises(ValidationError):
        ModeloEditDownstreamRefusalV1(error_code=code, message_key=_BINDING_KEY, context=(modelo, modelo))
    kept = ModeloEditDownstreamRefusalV1(error_code=code, message_key=_BINDING_KEY, context=(modelo, period))
    assert tuple(entry.key for entry in kept.context) == ("modelo", "period")
