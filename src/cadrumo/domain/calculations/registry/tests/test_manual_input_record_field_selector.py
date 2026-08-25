"""Typed record-field projection for ``manual_input`` bindings, and its bite proof.

``application/modelo/_calculation_modelo_adjustments.py`` (M131 datos-base
projection) used to read a ``manual_input`` binding's record-field shape via
``selector = selector_as_dict(binding); record = selector.get("record")``.
``_ManualInputSelector`` already enforces both shapes at registry build time,
so in production the ``None`` default meant "this is a casilla-shape
manual_input binding" -- correct and legitimate. But the raw ``.get()`` cannot
tell that apart from a genuinely malformed/renamed selector, so if the field
were ever renamed, every M131 record-field binding would silently stop
projecting with no error at all -- indistinguishable from "there are no
record-field bindings this revision".

:func:`manual_input_record_field_selector` closes that: it validates through
the same :class:`_ManualInputSelector` the registry build gate already uses,
so a genuinely malformed selector raises, and ``None`` means only "not
applicable" (non-manual_input, or the casilla shape), never "couldn't read
it".
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingSourceKind
from .._binding_selector_utils import (
    ManualInputRecordFieldSelector,
    manual_input_record_field_selector,
)
from ..errors import RegistryValidationError
from .._schema import DataBindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _m131_discapacidad_binding() -> DataBindingDefinition:
    """The real Modelo 131 2025 page-1 discapacidad-33 record-field binding."""
    return DataBindingDefinition.model_validate(
        {
            "id": "modelo-131-2025.page1.109-109.discapacidad-33",
            "source": "manual_input",
            "selector": {
                "record": "page_1",
                "field": "discapacidad-33",
                "offset": 109,
                "length": 1,
                "data_type": "boolean",
            },
            "legal_refs": ("rd-439-2007:art-110",),
            "source_refs": ("aeat-dr-131-2025",),
        },
    )


def test_a_record_field_manual_input_binding_projects_its_typed_selector() -> None:
    """The real M131 record-field binding round-trips through the typed accessor."""
    selector = manual_input_record_field_selector(_m131_discapacidad_binding())

    assert selector == ManualInputRecordFieldSelector(
        record="page_1",
        field="discapacidad-33",
        offset=109,
        length=1,
        decimals=None,
    )


def test_a_casilla_shape_manual_input_binding_is_not_applicable() -> None:
    """A casilla-shape manual_input binding is a real, DIFFERENT selector shape.

    Not a defect and not malformed -- a caller collecting record-field
    projections is meant to skip it, same as a non-manual_input binding.
    """
    casilla_shape = DataBindingDefinition.model_validate(
        {
            "id": "renta-2025-modelo-100-estimacion-directa-es-normal",
            "source": "manual_input",
            "selector": {
                "casilla_id": "0168",
                "data_type": "boolean",
                "true_value": "N",
                "false_value": "S",
            },
            "aggregation": {"op": "copy"},
            "typed_enum": "EstimacionDirectaModalidad",
            "legal_refs": ("ley-35-2006:art-30",),
            "source_refs": ("aeat-dr-100-2025-dictionary",),
        },
    )

    assert manual_input_record_field_selector(casilla_shape) is None


def test_a_non_manual_input_binding_is_not_applicable() -> None:
    """A profile-sourced binding is never a record-field manual_input selector."""
    profile = DataBindingDefinition.model_validate(
        {
            "id": "renta-2025-profile-tax-residence-ccaa",
            "source": "profile",
            "selector": {
                "profile_model": "TaxResidenceProfile",
                "field": "ccaa",
                "xsd_attribute": "codigoCADeclaracion",
                "dictionary_field": "ZCCAD",
            },
            "aggregation": {"op": "copy"},
            "typed_enum": "CCAA",
            "legal_refs": ("orden-hac-277-2026:art-3",),
            "source_refs": ("aeat-dr-100-2025-dictionary",),
        },
    )

    assert manual_input_record_field_selector(profile) is None


def test_a_renamed_record_field_key_is_refused_not_silently_read_as_casilla_shape() -> None:
    """The bite proof: a selector shape the model rejects must raise, not vanish.

    ``DataBindingDefinition.model_validate`` already dispatches through
    ``_ManualInputSelector`` at construction time, so a genuinely malformed
    selector cannot reach this function via the normal constructor -- proven
    by the companion assertion below. The residual risk this closes is DRIFT:
    a raw ``dict.get("record")`` reads a string literal with no tie to the
    model's own field name, so if ``_ManualInputSelector`` ever renamed
    ``record``, construction-time validation would keep passing (it would
    just validate the NEW name) while a raw-dict reader silently, permanently
    read every record-field binding as "casilla shape, not applicable" --
    indistinguishable from a revision with no record-field bindings at all.
    ``model_construct`` bypasses the constructor's own validators, standing in
    for that drifted-schema selector so the fixed function's OWN validation
    (not the constructor's) is what is under test.
    """
    with pytest.raises(ValidationError, match="violates _ManualInputSelector") as excinfo:
        DataBindingDefinition.model_validate(
            {
                "id": "modelo-131-2025.page1.109-109.discapacidad-33",
                "source": "manual_input",
                "selector": {
                    "recrd": "page_1",  # deliberate typo of "record"
                    "field": "discapacidad-33",
                    "offset": 109,
                    "length": 1,
                    "data_type": "boolean",
                },
                "legal_refs": ("rd-439-2007:art-110",),
                "source_refs": ("aeat-dr-131-2025",),
            },
        )
    assert "_ManualInputSelector" in str(excinfo.value), (
        "construction-time gate must be the one refusing the typo -- confirms the "
        "residual risk this fix closes is drift, not malformed-data construction"
    )

    drifted = DataBindingDefinition.model_construct(
        id="modelo-131-2025.page1.109-109.discapacidad-33",
        source=BindingSourceKind.MANUAL_INPUT,
        selector={
            "recrd": "page_1",  # the field _ManualInputSelector no longer names "record"
            "field": "discapacidad-33",
            "offset": 109,
            "length": 1,
            "data_type": "boolean",
        },
        legal_refs=("rd-439-2007:art-110",),
        source_refs=("aeat-dr-131-2025",),
    )

    with pytest.raises(RegistryValidationError, match="malformed manual_input selector"):
        manual_input_record_field_selector(drifted)
