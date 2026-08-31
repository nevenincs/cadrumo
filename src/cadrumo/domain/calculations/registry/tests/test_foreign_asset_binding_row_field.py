"""``foreign_asset_binding_row_field`` reads the typed selector, and refuses drift.

``application/calculations/foreign_asset_redeclaration.py`` (M720 row-field
lookup) used to read a ``foreign_asset`` binding's ``row_field`` via
``selector_as_dict(binding).get("row_field") == row_field``. Every
``foreign_asset`` binding's selector is validated against
:class:`_ForeignAssetSelector` at registry build time -- and that model's own
build-time invariant (``_validate_detail_record_row_field``) refuses a
``row_field``-less selector for the only ``fact`` the family accepts -- so a
raw ``.get()`` returning ``None`` in production could ONLY mean a RENAMED
field, never a legitimately absent one. The raw read could not tell that
apart from "this binding declares a different row_field", silently making
every foreign-asset row-field binding unmatchable on a rename, with no error
at all.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..detail_record_bindings import foreign_asset_binding_row_field
from ..errors import RegistryValidationError
from ..schema import DataBindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _m720_asset_class_binding() -> DataBindingDefinition:
    """The real Modelo 720 2013-y-siguientes asset-class row binding."""
    return DataBindingDefinition.model_validate(
        {
            "id": "modelo-720-asset-row-class",
            "source": "foreign_asset",
            "selector": {
                "fact": "row_field",
                "row_field": "asset_class_code",
                "grouping": "per_foreign_asset",
                "record": "bien",
                "data_type": "text",
            },
            "aggregation": {"op": "rows"},
            "legal_refs": ("ley-58-2003:disposicion-adicional-decimoctava",),
            "source_refs": ("aeat-dr-720-2013",),
        },
    )


def test_a_real_foreign_asset_binding_returns_its_row_field() -> None:
    assert foreign_asset_binding_row_field(_m720_asset_class_binding()) == "asset_class_code"


def test_a_non_matching_row_field_binding_is_distinguishable() -> None:
    """Anti-tautology companion: the accessor reads the ACTUAL declared field.

    Without this, an accessor that always returned a fixed string would pass
    the test above and look correct.
    """
    country_binding = DataBindingDefinition.model_validate(
        {
            "id": "modelo-720-asset-row-country",
            "source": "foreign_asset",
            "selector": {
                "fact": "row_field",
                "row_field": "country_code",
                "grouping": "per_foreign_asset",
                "record": "bien",
                "data_type": "text",
            },
            "aggregation": {"op": "rows"},
            "legal_refs": ("ley-58-2003:disposicion-adicional-decimoctava",),
            "source_refs": ("aeat-dr-720-2013",),
        },
    )

    assert foreign_asset_binding_row_field(country_binding) == "country_code"
    assert foreign_asset_binding_row_field(country_binding) != "asset_class_code"


def test_a_non_foreign_asset_binding_is_not_applicable() -> None:
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

    assert foreign_asset_binding_row_field(profile) is None


def test_a_renamed_row_field_key_is_refused_not_silently_read_as_absent() -> None:
    """The bite proof: a selector shape the model rejects must raise, not vanish.

    ``DataBindingDefinition.model_validate`` already dispatches through
    ``_ForeignAssetSelector`` at construction time, so a genuinely malformed
    selector cannot reach this function via the normal constructor -- proven
    by the companion assertion below. The residual risk this fix closes is
    DRIFT: a raw ``dict.get("row_field")`` reads a string literal with no tie
    to the model's own field name, so if ``_ForeignAssetSelector`` ever
    renamed ``row_field``, construction-time validation would keep passing
    (it would just validate the NEW name) while a raw-dict reader silently,
    permanently read every foreign-asset binding as having no row_field at
    all. ``model_construct`` bypasses the constructor's own validators,
    standing in for that drifted-schema selector so the fixed function's OWN
    validation (not the constructor's) is what is under test.
    """
    with pytest.raises(ValidationError, match="violates _ForeignAssetSelector") as excinfo:
        DataBindingDefinition.model_validate(
            {
                "id": "modelo-720-asset-row-class",
                "source": "foreign_asset",
                "selector": {
                    "fact": "row_field",
                    "rowfield": "asset_class_code",  # deliberate typo of "row_field"
                    "grouping": "per_foreign_asset",
                    "record": "bien",
                    "data_type": "text",
                },
                "aggregation": {"op": "rows"},
                "legal_refs": ("ley-58-2003:disposicion-adicional-decimoctava",),
                "source_refs": ("aeat-dr-720-2013",),
            },
        )
    assert "_ForeignAssetSelector" in str(excinfo.value), (
        "construction-time gate must be the one refusing the typo -- confirms the "
        "residual risk this fix closes is drift, not malformed-data construction"
    )

    from .....core.aggregation import BindingSourceKind

    drifted = DataBindingDefinition.model_construct(
        id="modelo-720-asset-row-class",
        source=BindingSourceKind.FOREIGN_ASSET,
        selector={
            "fact": "row_field",
            "rowfield": "asset_class_code",  # the field _ForeignAssetSelector no longer names "row_field"
            "grouping": "per_foreign_asset",
            "record": "bien",
            "data_type": "text",
        },
        aggregation={"op": "rows"},
        legal_refs=("ley-58-2003:disposicion-adicional-decimoctava",),
        source_refs=("aeat-dr-720-2013",),
    )

    with pytest.raises(RegistryValidationError, match="malformed foreign-asset selector"):
        foreign_asset_binding_row_field(drifted)
