"""The internal-fault projection must not carry the value that broke the rule.

``internal_record_fault_context`` withholds pydantic's ``input`` on a stated
privacy ground: a validated record on this path holds taxpayer data, and the
value that breached a constraint is exactly the value that must not cross an
output boundary. Withholding ``input`` did not achieve that.

A ``value_error`` -- pydantic's wrapper for a ``ValueError`` raised inside a
validator -- carries its message verbatim, and formatting the offending value
into the refusal is how domain validators are normally written. So the guarantee
was defeated by the COMMONEST validator shape, not an exotic one, on a helper
whose docstring asserted the protection.

These cases pin both directions. The leak must not reappear, and pydantic's own
constraint messages must keep coming through: those are composed from the
declared rule and name no value, and dropping them would trade a privacy defect
for an unreportable one.

The redaction funnel is deliberately not relied on. Its tax-identity matchers
have been Spanish-shaped, so a prefixed intra-community identifier passed it
raw; the two protections are independent and each must hold alone.
"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, Field, ValidationError, field_validator

from ..errors import internal_record_fault_context

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: An intra-community IVA identifier: real taxpayer data, and the exact shape the
#: CLI redaction funnel has historically passed through unaltered.
_TAXPAYER_VALUE = "SE556677889901"


class _RecordWithADomainRule(BaseModel):
    """A record whose validator formats the offending value into its refusal."""

    tax_id: str
    amount: int = 0

    @field_validator("tax_id")
    @classmethod
    def _exactly_nine_characters(cls, value: str) -> str:
        if len(value) != 9:
            raise ValueError(f"tax identifier {value!r} must be exactly 9 characters, got {len(value)}")
        return value


class _RecordWithDeclaredConstraints(BaseModel):
    """A record whose failures pydantic itself composes the message for."""

    code: str = Field(pattern=r"^[A-Z]{2}$")
    amount: int


def _fault_of(model: type[BaseModel], **payload: object) -> dict[str, object]:
    """Project a failure of *model*, naming the model as a real caller does.

    The model is supplied because these cases assert what an operator SEES, and
    a caller that knows which record it validated passes it. The fail-safe path
    -- no model, every path component redacted -- is asserted on its own below
    rather than made the default here, which would quietly weaken every
    field-name assertion into a redaction assertion.
    """
    try:
        model(**payload)
    except ValidationError as exc:
        return internal_record_fault_context(exc, record=model)
    raise AssertionError("the fixture must fail validation, or the case proves nothing")


def test_the_value_does_not_reach_the_context_through_a_domain_message() -> None:
    """The measured leak, asserted over the whole serialised context.

    Checked against the rendered JSON rather than one field, because the context
    is emitted wholesale by both renderers and a later field would reintroduce
    the leak somewhere this assertion still had to catch.
    """
    context = _fault_of(_RecordWithADomainRule, tax_id=_TAXPAYER_VALUE)

    assert _TAXPAYER_VALUE not in json.dumps(context, default=str)


def test_the_fixture_really_would_have_leaked() -> None:
    """Anti-tautology: the validator must put the value in its own message.

    Without this the case above passes against a fixture whose message never
    contained the value, and the protection would be untested.
    """
    with pytest.raises(ValidationError) as raised:
        _RecordWithADomainRule(tax_id=_TAXPAYER_VALUE)

    assert any(_TAXPAYER_VALUE in item["msg"] for item in raised.value.errors()), (
        "pydantic no longer carries the validator's prose; this suite's premise has changed"
    )


def test_the_withheld_message_still_names_the_field_and_the_rule() -> None:
    """A redaction that reports nothing would be a different defect.

    The fault has to stay reportable: the field says where, and the error type
    plus the raising exception's class says which contract broke. Both are
    identifiers from the source tree and neither can carry taxpayer data.
    """
    violations = str(_fault_of(_RecordWithADomainRule, tax_id=_TAXPAYER_VALUE)["violations"])

    assert violations.startswith("tax_id: ")
    assert "value_error" in violations
    assert "ValueError" in violations


def test_a_withheld_message_is_counted_rather_than_dropped_silently() -> None:
    """An engineer reading a thin report must know detail was suppressed.

    Otherwise a withheld message is indistinguishable from a validator that
    said nothing, and the error log holding the unredacted payload goes
    unconsulted.
    """
    context = _fault_of(_RecordWithADomainRule, tax_id=_TAXPAYER_VALUE)

    assert context["violation_messages_withheld"] == 1


def test_a_declared_constraint_message_still_comes_through() -> None:
    """The bound. Pydantic composes these from the RULE and they name no value.

    Without this the change is indistinguishable from withholding every message,
    which would leave every internal fault reported as a bare error type.
    """
    violations = str(_fault_of(_RecordWithDeclaredConstraints, code="lower", amount="x")["violations"])

    assert "String should match pattern" in violations
    assert "valid integer" in violations


def test_nothing_is_counted_as_withheld_when_nothing_was() -> None:
    """The counter must track the actual suppression, not the call."""
    context = _fault_of(_RecordWithDeclaredConstraints, code="lower", amount="x")

    assert "violation_messages_withheld" not in context


class _Row(BaseModel):
    quantity: int


class _RecordWithAKeyedMapping(BaseModel):
    """A record whose mapping is keyed by a party identifier.

    The second vector on the same helper. A violation under such a key puts the
    key into pydantic's ``loc``, and the projection joined ``loc`` verbatim --
    so the docstring calling the field path non-sensitive was false for exactly
    this shape.
    """

    by_party: dict[str, int]
    rows: list[_Row]


def _keyed_fault(*, record: type[BaseModel] | None = None) -> dict[str, object]:
    try:
        _RecordWithAKeyedMapping.model_validate(
            {"by_party": {_TAXPAYER_VALUE: "x"}, "rows": [{"quantity": "y"}]},
        )
    except ValidationError as exc:
        return internal_record_fault_context(exc, record=record)
    raise AssertionError("the fixture must fail validation, or the case proves nothing")


def test_a_mapping_key_does_not_reach_the_context_without_the_model() -> None:
    """Fail safe: with no model to check against, no string component is trusted.

    A caller that cannot say which model failed -- several raise sites guard a
    block validating more than one -- must not have its path guessed at.
    """
    assert _TAXPAYER_VALUE not in json.dumps(_keyed_fault(), default=str)


def test_a_mapping_key_does_not_reach_the_context_with_the_model() -> None:
    """And supplying the model must not re-admit it.

    This is the case that would silently regress if the allowlist were ever
    built from the input rather than from the declared fields.
    """
    assert _TAXPAYER_VALUE not in json.dumps(_keyed_fault(record=_RecordWithAKeyedMapping), default=str)


def test_the_fixture_really_would_have_leaked_through_the_path() -> None:
    """Anti-tautology for the path vector: the key must be in ``loc``."""
    with pytest.raises(ValidationError) as raised:
        _RecordWithAKeyedMapping.model_validate({"by_party": {_TAXPAYER_VALUE: "x"}, "rows": []})

    assert any(_TAXPAYER_VALUE in item["loc"] for item in raised.value.errors()), (
        "pydantic no longer reproduces the mapping key in loc; this suite's premise has changed"
    )


def test_the_model_buys_back_the_declared_field_names() -> None:
    """The whole point of the parameter, and the bound on the redaction.

    Without this the change is indistinguishable from redacting every path, and
    the diagnostic that makes an internal fault reportable would be gone.
    """
    violations = str(_keyed_fault(record=_RecordWithAKeyedMapping)["violations"])

    assert "by_party." in violations, "a declared field name must survive"
    assert "rows.0.quantity" in violations, "an index and a nested field name must both survive"


def test_the_redaction_keeps_the_paths_depth() -> None:
    """Replaced, never elided.

    Dropping the component would make a mapping indistinguishable from a plain
    nested field, hiding the presence of a mapping exactly where an engineer
    needs to see one.
    """
    violations = str(_keyed_fault(record=_RecordWithAKeyedMapping)["violations"])

    assert "by_party.<key>" in violations
