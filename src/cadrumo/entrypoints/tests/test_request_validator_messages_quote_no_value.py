"""No registered operation's request validator builds its refusal wording from a value.

A request that fails its model is refused with the model's own wording, and a
caller in another process receives it. The fault renderer replaces wording that
repeats the refused input verbatim, which misses a value the validator
reformatted, a value too short to match as a word, and another field's value
quoted by a validator of a different field. So the wording must never contain a
value to begin with: it names a field and the rule it broke.

The gate reads the code of every validator reachable from the request model of
each registered operation, and of the typed operator input that two operations
take in place of a registered request, and fails naming each message built from
a value. Isolated fixtures prove that it detects each way of building one and
that it accepts the wording the codebase uses for a field name or a constant.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import Annotated, Self

import pytest
from pydantic import AfterValidator, BaseModel, ValidationInfo, field_validator, model_validator

from cadrumo.core.identity.documents import IdentityError

from ...application.modelo.edit_operator_input import ModeloEditOperatorInputV2
from ...application.review.errors import FilterParseError
from ..operation_composition import build_production_operation_registry
from .request_validator_message_scan import MessageLeak, message_leaks, request_validators

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ALLOWED_KINDS = ("alpha", "beta")


@cache
def _registered_request_types() -> tuple[type[BaseModel], ...]:
    registry = build_production_operation_registry()
    requests = [
        registry.lookup(contract.definition_id).request_type for contract in registry.public_contract_set.definitions
    ]
    return (*requests, ModeloEditOperatorInputV2)


def _leaks_of(*models: type) -> tuple[MessageLeak, ...]:
    return message_leaks(request_validators(models))


def test_no_request_validator_of_a_registered_operation_builds_its_wording_from_a_value() -> None:
    validators = request_validators(_registered_request_types())

    assert validators, "the registry's request models declared no validator, so nothing was read"
    leaks = message_leaks(validators)

    assert not leaks, (
        "these refusal messages are built from a value; name the field and the rule instead:\n"
        + "\n".join(f"  {leak.describe()}" for leak in leaks)
    )


# Fixtures: each defective model builds a message from a value in one way the scan must find.


class _FStringOfTheValue(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def _shaped(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError(f"code {value!r} must be letters")
        return value


class _PercentFormatOfTheValue(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def _shaped(cls, value: str) -> str:
        template = "code %s must be letters"
        if not value.isalpha():
            raise ValueError(template % value)
        return value


class _FormatCallOfTheValue(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def _shaped(cls, value: str) -> str:
        template = "code {} must be letters"
        if not value.isalpha():
            raise ValueError(template.format(value))
        return value


class _ConcatenationOfTheValue(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def _shaped(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("code " + value + " must be letters")
        return value


class _AnotherFieldsValue(BaseModel):
    kind: str
    code: str

    @model_validator(mode="after")
    def _agree(self) -> Self:
        if self.code != self.kind:
            raise ValueError(f"code does not match kind {self.kind}")
        return self


class _MessageBuiltInAVariable(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def _shaped(cls, value: str) -> str:
        message = f"code {value} must be letters"
        if not value.isalpha():
            raise ValueError(message)
        return value


class _DerivedFromTheValue(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def _shaped(cls, value: str) -> str:
        shown = value.strip().upper()
        if not shown.isalpha():
            raise ValueError(f"code must be letters, not {shown}")
        return value


class _AssertionWithTheValue(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def _shaped(cls, value: str) -> str:
        assert value.isalpha(), f"code {value} must be letters"
        return value


def _demands_letters(text: str) -> None:
    if not text.isalpha():
        raise ValueError(f"{text} must be letters")


class _HelperThatQuotesTheValue(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def _shaped(cls, value: str) -> str:
        _demands_letters(value)
        return value


class _HelperThatPassesTheFailureOn(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def _shaped(cls, value: str) -> str:
        try:
            _demands_letters(value)
        except ValueError:
            raise
        return value


def _annotated_demand(text: str) -> str:
    if not text.isalpha():
        raise ValueError(f"{text} must be letters")
    return text


class _AnnotatedValidatorThatQuotesTheValue(BaseModel):
    code: Annotated[str, AfterValidator(_annotated_demand)]


@dataclass(frozen=True)
class _DataclassThatQuotesTheValue:
    code: str

    def __post_init__(self) -> None:
        if not self.code.isalpha():
            raise ValueError(f"code {self.code} must be letters")


class _HoldsADataclass(BaseModel):
    held: _DataclassThatQuotesTheValue


class _HoldsAModel(BaseModel):
    nested: tuple[_FStringOfTheValue, ...]


class _RegisteredErrorThatQuotesTheValue(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def _shaped(cls, value: str) -> str:
        if not value.isalpha():
            raise IdentityError(f"code {value} must be letters")
        return value


_DEFECTIVE = [
    (_FStringOfTheValue, "value"),
    (_PercentFormatOfTheValue, "value"),
    (_FormatCallOfTheValue, "value"),
    (_ConcatenationOfTheValue, "value"),
    (_AnotherFieldsValue, "self.kind"),
    (_MessageBuiltInAVariable, "value"),
    (_DerivedFromTheValue, "shown"),
    (_AssertionWithTheValue, "value"),
    (_HelperThatQuotesTheValue, "text"),
    (_HelperThatPassesTheFailureOn, "text"),
    (_AnnotatedValidatorThatQuotesTheValue, "text"),
    (_HoldsADataclass, "self.code"),
    (_HoldsAModel, "value"),
    (_RegisteredErrorThatQuotesTheValue, "value"),
]


@pytest.mark.parametrize(("model", "quoted"), _DEFECTIVE, ids=[model.__name__ for model, _quoted in _DEFECTIVE])
def test_the_scan_finds_a_message_built_from_a_value(model: type, quoted: str) -> None:
    leaks = _leaks_of(model)

    assert leaks, f"{model.__name__} builds a refusal message from a value and was not reported"
    assert any(leak.value == quoted for leak in leaks), [leak.describe() for leak in leaks]


# Fixtures: each clean model words its refusal without a value in a way the codebase uses.


class _NamesTheFieldAndTheRule(BaseModel):
    amount: str
    rate: str

    @field_validator("amount", "rate")
    @classmethod
    def _canonical(cls, value: str, info: ValidationInfo) -> str:
        if not value.isdigit():
            raise ValueError(f"{info.field_name} must use canonical digits")
        return value


class _NamesTheFieldByGetattr(BaseModel):
    amount: str

    @field_validator("amount")
    @classmethod
    def _canonical(cls, value: str, info: ValidationInfo) -> str:
        if not value.isdigit():
            raise ValueError(f"{getattr(info, 'field_name', 'amount')} must use canonical digits")
        return value


class _SaysOnlyConstants(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def _shaped(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("code must be letters; one of " + ", ".join(_ALLOWED_KINDS))
        return value


class _NamesAFieldFromAConstantList(BaseModel):
    alpha: str | None = None
    beta: str | None = None

    @model_validator(mode="after")
    def _one_of_them(self) -> Self:
        for field_name in _ALLOWED_KINDS:
            if getattr(self, field_name) == "":
                raise ValueError(f"{field_name} must not be blank; omit it instead")
        return self


class _NamesTheClass(BaseModel):
    code: str

    @model_validator(mode="after")
    def _always(self) -> Self:
        if not self.code.isalpha():
            raise ValueError(f"{type(self).__name__} takes letters only")
        return self


def _quoting_helper(text: str) -> str:
    if not text.isalpha():
        raise ValueError(f"{text} must be letters")
    return text


class _TranslatesTheHelpersFailure(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def _shaped(cls, value: str) -> str:
        try:
            return _quoting_helper(value)
        except ValueError:
            raise ValueError("code must be letters") from None


class _RaisesAnErrorThatKeepsTheValueApart(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def _shaped(cls, value: str) -> str:
        if not value.isalpha():
            # This error keeps the token it is given out of its own text.
            raise FilterParseError(f"code={value}", reason="invalid-value")
        return value


class _HelperThatTakesNoValue(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def _shaped(cls, value: str) -> str:
        _require_known_kinds(_ALLOWED_KINDS)
        return value


def _require_known_kinds(kinds: tuple[str, ...]) -> None:
    if not kinds:
        raise ValueError(f"no kind is declared: {', '.join(kinds)}")


_CLEAN = [
    _NamesTheFieldAndTheRule,
    _NamesTheFieldByGetattr,
    _SaysOnlyConstants,
    _NamesAFieldFromAConstantList,
    _NamesTheClass,
    _TranslatesTheHelpersFailure,
    _RaisesAnErrorThatKeepsTheValueApart,
    _HelperThatTakesNoValue,
]


@pytest.mark.parametrize("model", _CLEAN, ids=[model.__name__ for model in _CLEAN])
def test_the_scan_accepts_wording_that_names_a_field_a_class_or_a_constant(model: type) -> None:
    assert request_validators([model]), f"{model.__name__} declares a validator, so the scan must read it"
    assert _leaks_of(model) == ()
