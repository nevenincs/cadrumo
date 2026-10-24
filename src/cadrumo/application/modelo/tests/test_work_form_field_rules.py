"""What a form field derives from itself, and that it cannot be told otherwise.

A field says where an edit of it is submitted, whether it holds an assumed
value the filer can confirm, and whether it holds an amount of zero. Each is
worked out from the field's own address, origin, value, editability and
bindings; a field given a value that contradicts its own state is refused,
and a revised copy derives them again.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import validated_casilla_id
from ..source_policy import SourceFamily, SourceOverridePolicy, SourcePolicyV1, SourceSurface
from ..work_form_models import (
    ModeloFormBinding,
    ModeloFormBindingAddressV1,
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormScalar,
    ModeloFormStanding,
    ModeloFormText,
    ModeloFormTextDisclosure,
    revised_field,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BOX = ModeloFormCasillaAddressV1(casilla_id=validated_casilla_id("05"))


def _binding(policy: SourceOverridePolicy) -> ModeloFormBinding:
    return ModeloFormBinding(
        binding_id="modelo-130-pagos-fraccionados-anteriores",
        policy=SourcePolicyV1(
            source_kind=BindingSourceKind.PREVIOUS_FILING,
            family=SourceFamily.EARLIER_FILINGS,
            override_policy=policy,
            surface=SourceSurface.DECLARATIONS,
        ),
        resolved=True,
    )


def _field(
    *,
    origin: ModeloFormOrigin = ModeloFormOrigin.DEFAULT_TO_CONFIRM,
    editability: ModeloFormEditability = ModeloFormEditability.EDITABLE_VALUE,
    value: ModeloFormScalar = Decimal("120.00"),
    bindings: tuple[ModeloFormBinding, ...] = (),
) -> ModeloFormField:
    return ModeloFormField(
        address=_BOX,
        box="05",
        label=ModeloFormText(text="Prior fractional payments", disclosure=ModeloFormTextDisclosure.LOCALIZED),
        help=None,
        data_type="money",
        value=value,
        origin=origin,
        editability=editability,
        required=False,
        bindings=bindings,
    )


def test_an_assumed_value_the_filer_types_is_confirmable_and_nothing_else_is() -> None:
    assert _field().confirmable
    assert not _field(origin=ModeloFormOrigin.ENTERED).confirmable
    assert not _field(value=None).confirmable
    assert not _field(editability=ModeloFormEditability.NO_ADMISSION).confirmable
    # A value a source supplies is replaced, never confirmed as the filer's own.
    assert not _field(bindings=(_binding(SourceOverridePolicy.OVERRIDE_WITH_REASON),)).confirmable
    assert _field(bindings=(_binding(SourceOverridePolicy.ENTER),)).confirmable
    # An override is submitted to its binding, so it is not confirmable at the box.
    override = _field(
        editability=ModeloFormEditability.EDITABLE_OVERRIDE, bindings=(_binding(SourceOverridePolicy.ENTER),)
    )
    assert not override.confirmable


def test_a_replaced_source_value_is_submitted_to_its_binding() -> None:
    fed = _field(
        origin=ModeloFormOrigin.IMPORTED,
        editability=ModeloFormEditability.OVERRIDABLE_SOURCE,
        bindings=(_binding(SourceOverridePolicy.OVERRIDE_WITH_REASON),),
    )
    assert fed.edit_address == ModeloFormBindingAddressV1(binding_id="modelo-130-pagos-fraccionados-anteriores")
    assert _field().edit_address == _BOX


def test_zero_is_a_held_amount_and_nothing_is_not() -> None:
    assert _field(value=Decimal("0")).held_zero
    assert _field(value=0).held_zero
    assert not _field(value=None).held_zero
    assert not _field(value=False).held_zero
    assert not _field(value=Decimal("0.01")).held_zero


@pytest.mark.parametrize(
    "contradiction",
    [
        {"confirmable": False},
        {"held_zero": True},
        {"edit_address": ModeloFormBindingAddressV1(binding_id="another-binding")},
    ],
)
def test_a_field_told_otherwise_than_its_own_state_is_refused(contradiction: dict[str, object]) -> None:
    data = {name: getattr(_field(), name) for name in ModeloFormField.model_fields} | contradiction
    with pytest.raises(ValidationError):
        ModeloFormField.model_validate(data)


def test_a_revised_copy_derives_again_and_keeps_its_standing_unless_told() -> None:
    assumed = _field()
    fixed = revised_field(
        assumed,
        origin=ModeloFormOrigin.INFORMATIONAL,
        editability=ModeloFormEditability.DESIGN_CONSTANT,
        value=Decimal("0"),
        standing=ModeloFormStanding.DONE,
    )
    assert not fixed.confirmable
    assert fixed.held_zero
    assert fixed.standing is ModeloFormStanding.DONE
    kept = revised_field(assumed, editability=ModeloFormEditability.INFORMATIONAL)
    assert kept.standing is assumed.standing is ModeloFormStanding.NEEDS_YOU
    assert not kept.confirmable
