"""A requirement the design states for natural persons only is judged per filing.

Modelo 390 marks the sujeto pasivo nombre "OBLIGATORIO (persona fisica)". A
layout cannot know the filer, so the field declares ``required_for`` and the
header renderer evaluates it against the filing's own taxpayer: a natural person
must supply the value, an entity has none to supply, and a taxpayer whose form
cannot be read is refused rather than given the benefit of the doubt.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.filing_producer_key import FilingProducerKey
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition
from ....domain.filing.errors import FilingExportValidationError
from .._record_field_renderer import _header_field_value
from ..producer_snapshot import TaxpayerIdentityFacts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _nombre_field(**overrides: object) -> ExportFieldDefinition:
    payload: dict[str, object] = {
        "id": "sujeto-pasivo-nombre",
        "offset": 83,
        "length": 20,
        "kind": "header",
        "producer_key": FilingProducerKey.TAXPAYER_GIVEN_NAME,
        "data_type": "text",
        "required": False,
        "required_for": "natural_person",
        "padding": "right_space",
        "justification": "left",
        "signed": False,
        "legal_refs": ("orden-eha-3111-2009:art-1",),
        "source_refs": ("aeat-dr-390-2025",),
    }
    payload.update(overrides)
    return ExportFieldDefinition.model_validate(payload)


def _headers(**values: object) -> dict[FilingProducerKey, object]:
    return {FilingProducerKey(key.replace("__", ".")): value for key, value in values.items()}


def test_a_natural_person_without_a_given_name_is_refused() -> None:
    headers = _headers(taxpayer__legal_name=None, taxpayer__surnames="Prueba", taxpayer__given_name=None)

    with pytest.raises(FilingExportValidationError, match="is required"):
        _header_field_value(_nombre_field(), headers)


def test_a_natural_person_with_a_given_name_renders_it() -> None:
    headers = _headers(taxpayer__legal_name=None, taxpayer__surnames="Prueba", taxpayer__given_name=" Ana ")

    assert _header_field_value(_nombre_field(), headers) == "Ana"


def test_an_entity_has_no_given_name_to_supply() -> None:
    headers = _headers(taxpayer__legal_name="EJEMPLO SL", taxpayer__given_name=None)

    assert _header_field_value(_nombre_field(), headers) is None


def test_a_taxpayer_whose_legal_form_cannot_be_read_is_refused() -> None:
    with pytest.raises(FilingExportValidationError, match="is required"):
        _header_field_value(_nombre_field(), _headers(taxpayer__given_name=None))


def test_a_field_without_the_condition_still_admits_a_blank() -> None:
    field = _nombre_field(required_for=None)

    assert _header_field_value(field, _headers(taxpayer__legal_name=None, taxpayer__given_name=None)) is None


@pytest.mark.parametrize(
    ("overrides", "message"),
    (
        ({"required": True}, "cannot also declare required_for"),
        (
            {"kind": "literal", "producer_key": None, "literal": "X", "padding": "none", "justification": "none"},
            "only on a header field",
        ),
        ({"required_for": "entity"}, "required_for"),
    ),
)
def test_the_schema_admits_the_condition_only_where_the_export_evaluates_it(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _nombre_field(**overrides)


def test_identity_facts_refuse_an_entity_name_beside_personal_names() -> None:
    """The legal form is read from which names are present, so they must be exclusive."""
    with pytest.raises(ValidationError, match="both an entity legal name and personal names"):
        TaxpayerIdentityFacts(legal_name="EJEMPLO SL", given_name="Ana", surnames=None, full_name="EJEMPLO SL")
