"""``previous_filing_binding_source_casilla_ids`` reads the typed selector, and refuses drift.

``application/calculations/_foreign_asset_redeclaration.py`` (M720 prior-year
baseline observation) used to read a ``previous_filing`` binding's target
casilla via ``selector_as_dict(binding).get("source_casilla_id")`` -- the
SINGULAR key only. :class:`PreviousModeloSelector` declares TWO mutually
exclusive shapes for this fact: the singular ``source_casilla_id`` and the
plural ``source_casilla_ids``, normalised by the shared
:func:`_previous_filing_source_ids` every other consumer of this selector
already uses. The raw single-key read could not distinguish three states
that need to stay distinct: "this binding legitimately uses the plural
shape" (real, not a defect), "this binding targets no casilla at all" (also
real), and "the field was renamed" (drift) -- all three produced the
identical ``None`` and silently dropped the binding from the M720
re-declaration baseline with no error.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._bindings_previous_filing import previous_filing_binding_source_casilla_ids
from .._errors import RegistryValidationError
from .._schema import DataBindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _m720_cuentas_valoracion_binding() -> DataBindingDefinition:
    """The real Modelo 720 prior-year cuentas valoracion baseline binding."""
    return DataBindingDefinition.model_validate(
        {
            "id": "modelo-720-prior-year-cuentas-valoracion",
            "source": "previous_filing",
            "selector": {
                "source_modelo": "720",
                "filing_year_delta": -1,
                "period": "0A",
                "source_casilla_id": "cuentas.valoracion",
            },
            "aggregation": {"op": "copy"},
            "legal_refs": ("ley-58-2003:disposicion-adicional-decimoctava",),
            "source_refs": ("aeat-dr-720-2013",),
        },
    )


def test_a_real_singular_shape_binding_returns_its_one_casilla_id() -> None:
    result = previous_filing_binding_source_casilla_ids(_m720_cuentas_valoracion_binding())

    assert result == ("cuentas.valoracion",)


def test_a_plural_shape_binding_returns_every_declared_casilla_id() -> None:
    """The plural ``source_casilla_ids`` shape is a real, DIFFERENT declaration.

    A raw single-key ``.get("source_casilla_id")`` read is structurally blind
    to this shape -- it would return ``None`` for every plural-shaped
    binding, indistinguishable from "targets no casilla". This is the
    anti-tautology companion: without it, an accessor that only ever
    recognised the singular key would pass the test above and look correct.
    """
    plural = DataBindingDefinition.model_validate(
        {
            "id": "modelo-720-prior-year-multi-casilla",
            "source": "previous_filing",
            "selector": {
                "source_modelo": "720",
                "filing_year_delta": -1,
                "period": "0A",
                "source_casilla_ids": ("cuentas.valoracion", "valores.valoracion"),
            },
            "aggregation": {"op": "copy"},
            "legal_refs": ("ley-58-2003:disposicion-adicional-decimoctava",),
            "source_refs": ("aeat-dr-720-2013",),
        },
    )

    result = previous_filing_binding_source_casilla_ids(plural)

    assert result == ("cuentas.valoracion", "valores.valoracion")


def test_a_non_previous_filing_binding_returns_empty() -> None:
    """A different source family's binding is never this accessor's business."""
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

    assert previous_filing_binding_source_casilla_ids(profile) == ()


def test_a_renamed_source_casilla_id_key_is_refused_not_silently_read_as_empty() -> None:
    """The bite proof: a selector shape the model rejects must raise, not vanish.

    ``DataBindingDefinition.model_validate`` already dispatches through
    ``PreviousModeloSelector`` at construction time, so a genuinely malformed
    selector cannot reach this function via the normal constructor -- proven
    by the companion assertion below. The residual risk this fix closes is
    DRIFT: a raw ``dict.get("source_casilla_id")`` reads a string literal
    with no tie to the model's own field name, so if ``PreviousModeloSelector``
    ever renamed that field, construction-time validation would keep passing
    (it would just validate the NEW name) while a raw-dict reader silently,
    permanently read every singular-shape previous_filing binding as
    targeting no casilla at all. ``model_construct`` bypasses the
    constructor's own validators, standing in for that drifted-schema
    selector so the fixed function's OWN validation (not the constructor's)
    is what is under test.
    """
    with pytest.raises(ValidationError, match="violates PreviousModeloSelector") as excinfo:
        DataBindingDefinition.model_validate(
            {
                "id": "modelo-720-prior-year-cuentas-valoracion",
                "source": "previous_filing",
                "selector": {
                    "source_modelo": "720",
                    "filing_year_delta": -1,
                    "period": "0A",
                    "source_casillaid": "cuentas.valoracion",  # deliberate typo
                },
                "aggregation": {"op": "copy"},
                "legal_refs": ("ley-58-2003:disposicion-adicional-decimoctava",),
                "source_refs": ("aeat-dr-720-2013",),
            },
        )
    assert "PreviousModeloSelector" in str(excinfo.value), (
        "construction-time gate must be the one refusing the typo -- confirms the "
        "residual risk this fix closes is drift, not malformed-data construction"
    )

    from .....core.aggregation import BindingSourceKind

    drifted = DataBindingDefinition.model_construct(
        id="modelo-720-prior-year-cuentas-valoracion",
        source=BindingSourceKind.PREVIOUS_FILING,
        selector={
            "source_modelo": "720",
            "filing_year_delta": -1,
            "period": "0A",
            "source_casillaid": "cuentas.valoracion",  # the field PreviousModeloSelector no longer names
        },
        aggregation={"op": "copy"},
        legal_refs=("ley-58-2003:disposicion-adicional-decimoctava",),
        source_refs=("aeat-dr-720-2013",),
    )

    with pytest.raises(RegistryValidationError, match="malformed previous-filing selector"):
        previous_filing_binding_source_casilla_ids(drifted)
