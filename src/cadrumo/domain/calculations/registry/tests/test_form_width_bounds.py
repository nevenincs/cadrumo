"""Models that read a form width from the registry refuse a value that does not have it."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from .....core.errors.hierarchy import CoreValidationError
from ....contribuyente.family_types import RentaAscendantProfile
from ....filing.software_identity import AeatProductSoftwareIdentity, development_mock_software_identity
from ....modelos.calculation_revision import CalculationRevision
from ....modelos.ledger_filing_snapshot import LedgerEvidenceRow
from ....modelos.perceptor_clave_scope import ClaveScopeToken
from ....prorrata_register.register import ProrrataActivityRow
from ....transactions.m210_income_classification import M210IncomeClassification
from ..authority import bundled_indexed_authority
from ..detail_record_bindings import AtributionMemberObservation
from ..errors import RegistryValidationError
from ..form_codes import require_form_fit, require_form_width, resolve_form_codes_leased
from ..withholding_bindings import WithholdingObservation

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _declared(key: str) -> int:
    return int(resolve_form_codes_leased("form-row-codes").code(key))


def _refused_field(model: type[BaseModel], field: str, value: object) -> bool:
    """Return whether validating ``field`` alone refuses ``value`` with that field's own error."""
    try:
        model.model_validate({field: value})
    except ValidationError as exc:
        return any(error["loc"][0] == field for error in exc.errors())
    return False


def test_a_width_outside_the_declared_set_is_refused() -> None:
    width = _declared("m210.tipo_renta_digits")
    assert require_form_width("1" * width, "m210.tipo_renta_digits") == "1" * width
    assert require_form_width(None, "m210.tipo_renta_digits") is None
    with pytest.raises(CoreValidationError, match=r"m210\.tipo_renta_digits"):
        require_form_width("1" * (width + 1), "m210.tipo_renta_digits")


def test_a_value_longer_than_the_declared_field_is_refused() -> None:
    limit = _declared("withholding.subclave_max")
    assert require_form_fit("1" * limit, "withholding.subclave_max") == "1" * limit
    with pytest.raises(CoreValidationError, match=r"withholding\.subclave_max"):
        require_form_fit("1" * (limit + 1), "withholding.subclave_max")


@pytest.mark.parametrize(
    ("model", "field", "key"),
    [
        (AtributionMemberObservation, "subclave", "m184.row.subclave_digits"),
        (AtributionMemberObservation, "codigo_provincia", "m184.row.provincia_digits"),
        (WithholdingObservation, "subclave", "withholding.subclave_max"),
        (WithholdingObservation, "codigo_emisor", "withholding.codigo_emisor_max"),
        (M210IncomeClassification, "official_tipo_renta_code", "m210.tipo_renta_digits"),
        (LedgerEvidenceRow, "m210_official_tipo_renta_code", "m210.tipo_renta_digits"),
        (CalculationRevision, "m210_official_tipo_renta_code", "m210.tipo_renta_digits"),
    ],
)
def test_a_binding_row_refuses_a_code_past_the_declared_width(model: type[BaseModel], field: str, key: str) -> None:
    limit = _declared(key)
    assert not _refused_field(model, field, "1" * limit)
    assert _refused_field(model, field, "1" * (limit + 1))


def test_an_ascendant_past_the_declared_descendant_count_is_refused() -> None:
    limit = _declared("m100.ascendant_cohabiting_descendants_max")
    assert not _refused_field(RentaAscendantProfile, "cohabiting_descendant_count", limit)
    assert _refused_field(RentaAscendantProfile, "cohabiting_descendant_count", limit + 1)


@pytest.mark.parametrize(
    ("field", "key"),
    [
        ("program_identifier", "aeat.aux.program_identifier_width"),
        ("developer_tax_id", "aeat.aux.developer_tax_id_width"),
    ],
)
def test_a_software_identifier_of_another_width_is_refused(field: str, key: str) -> None:
    with bundled_indexed_authority().operation():
        identity = development_mock_software_identity()
        assert len(getattr(identity, field)) == _declared(key)
        with pytest.raises(ValidationError):
            AeatProductSoftwareIdentity.model_validate(
                {**dict(identity), field: getattr(identity, field) + "0"},
            )


def test_a_perceptor_scope_subclave_of_another_width_is_refused() -> None:
    width = _declared("perceptor.subclave_digits")
    assert ClaveScopeToken.parse("A." + "1" * width).subclave == "1" * width
    with pytest.raises(RegistryValidationError, match="perceptor clave scope"):
        ClaveScopeToken.parse("A." + "1" * (width + 1))


def test_a_prorrata_cnae_of_another_width_is_refused() -> None:
    widths = resolve_form_codes_leased("form-row-codes").codes("m303.prorrata.cnae_digits")
    for width in widths:
        assert not _refused_field(ProrrataActivityRow, "cnae_code", "1" * int(width))
    assert _refused_field(ProrrataActivityRow, "cnae_code", "1" * (max(int(width) for width in widths) + 1))
