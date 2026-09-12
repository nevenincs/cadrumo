"""``previous_filing_binding_source_casilla_ids`` reads the typed selector, and refuses drift.

``application/calculations/foreign_asset_redeclaration.py`` (M720 prior-year
baseline observation) used to read a ``previous_filing`` binding's target
casilla via ``selector_as_dict(binding).get("source_casilla_id")`` -- the
SINGULAR key only. :class:`PreviousFilingProvider` declares TWO mutually
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

from ..binding_temporal import BindingTemporalKind, FilingYearOffset
from ..binding_value_contract import BindingDataType, BindingValueChannel, BindingValueContract
from ..bindings_previous_filing import PreviousFilingProvider, previous_filing_binding_source_casilla_ids
from ..errors import RegistryValidationError
from ..schema import BindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _m720_cuentas_valoracion_binding() -> BindingDefinition:
    """The real Modelo 720 prior-year cuentas valoracion baseline binding."""
    return BindingDefinition.model_validate(
        {
            "id": "modelo-720-prior-year-cuentas-valoracion",
            "provider": {
                "kind": "previous_filing",
                "source_modelo": "720",
                "source_casilla_id": "cuentas.valoracion",
                "temporal": {
                    "kind": "filing_year_offset",
                    "years": -1,
                    "source_periods": ["0A"],
                },
            },
            "value": {
                "data_type": "money",
                "channel": "decimal",
            },
            "aggregation": {
                "op": "copy",
            },
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
    plural = BindingDefinition.model_validate(
        {
            "id": "modelo-720-prior-year-multi-casilla",
            "provider": {
                "kind": "previous_filing",
                "source_modelo": "720",
                "source_casilla_ids": (
                    "cuentas.valoracion",
                    "valores.valoracion",
                ),
                "temporal": {
                    "kind": "filing_year_offset",
                    "years": -1,
                    "source_periods": ["0A"],
                },
            },
            "value": {
                "data_type": "money",
                "channel": "decimal",
            },
            "aggregation": {
                "op": "copy",
            },
            "legal_refs": ("ley-58-2003:disposicion-adicional-decimoctava",),
            "source_refs": ("aeat-dr-720-2013",),
        },
    )

    result = previous_filing_binding_source_casilla_ids(plural)

    assert result == ("cuentas.valoracion", "valores.valoracion")


def test_a_non_previous_filing_binding_returns_empty() -> None:
    """A different source family's binding is never this accessor's business."""
    profile = BindingDefinition.model_validate(
        {
            "id": "renta-2025-profile-tax-residence-ccaa",
            "provider": {
                "kind": "profile",
                "profile_model": "TaxResidenceProfile",
                "field": "ccaa",
                "xsd_attribute": "codigoCADeclaracion",
                "dictionary_field": "ZCCAD",
            },
            "value": {
                "data_type": "enum",
                "channel": "enum",
                "typed_enum": "CCAA",
            },
            "aggregation": {
                "op": "copy",
            },
            "legal_refs": ("orden-hac-277-2026:art-3",),
            "source_refs": ("aeat-dr-100-2025-dictionary",),
        },
    )

    assert previous_filing_binding_source_casilla_ids(profile) == ()


def test_a_renamed_source_casilla_id_key_is_refused_not_silently_read_as_empty() -> None:
    """The bite proof: a selector shape the model rejects must raise, not vanish.

    ``BindingDefinition.model_validate`` already dispatches through
    ``PreviousFilingProvider`` at construction time, so a genuinely malformed
    selector cannot reach this function via the normal constructor -- proven
    by the companion assertion below. The residual risk this fix closes is
    DRIFT: a raw ``dict.get("source_casilla_id")`` reads a string literal
    with no tie to the model's own field name, so if ``PreviousFilingProvider``
    ever renamed that field, construction-time validation would keep passing
    (it would just validate the NEW name) while a raw-dict reader silently,
    permanently read every singular-shape previous_filing binding as
    targeting no casilla at all. ``model_construct`` bypasses the
    constructor's own validators, standing in for that drifted-schema
    selector so the fixed function's OWN validation (not the constructor's)
    is what is under test.
    """
    with pytest.raises(ValidationError, match=r"provider\.previous_filing\.source_casillaid") as excinfo:
        BindingDefinition.model_validate(
            {
                "id": "modelo-720-prior-year-cuentas-valoracion",
                "provider": {
                    "kind": "previous_filing",
                    "source_modelo": "720",
                    "source_casillaid": "cuentas.valoracion",
                    "temporal": {
                        "kind": "filing_year_offset",
                        "years": -1,
                        "source_periods": ["0A"],
                    },
                },
                "value": {
                    "data_type": "money",
                    "channel": "decimal",
                },
                "aggregation": {
                    "op": "copy",
                },
                "legal_refs": ("ley-58-2003:disposicion-adicional-decimoctava",),
                "source_refs": ("aeat-dr-720-2013",),
            },
        )
    assert "Extra inputs are not permitted" in str(excinfo.value), (
        "construction-time gate must be the one refusing the typo -- confirms the "
        "residual risk this fix closes is drift, not malformed-data construction"
    )

    drifted = BindingDefinition.model_construct(
        id="modelo-720-prior-year-cuentas-valoracion",
        provider=PreviousFilingProvider.model_construct(
            source_modelo="720",
            temporal=FilingYearOffset(
                kind=BindingTemporalKind.FILING_YEAR_OFFSET,
                years=-1,
                source_periods=("0A",),
            ),
            # A value PreviousFilingProvider's own model refuses, standing in
            # for a member that no longer round-trips into its declaring model.
            source_casilla_id=123,
        ),
        value=BindingValueContract(data_type=BindingDataType.MONEY, channel=BindingValueChannel.DECIMAL),
        aggregation={"op": "copy"},
        legal_refs=("ley-58-2003:disposicion-adicional-decimoctava",),
        source_refs=("aeat-dr-720-2013",),
    )

    with pytest.raises(RegistryValidationError, match="malformed previous-filing selector"):
        previous_filing_binding_source_casilla_ids(drifted)
