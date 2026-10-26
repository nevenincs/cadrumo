"""The printed alphabetic IBAN country component is not a numeric-policy slot."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ...compiler.loader import load_shared_catalogues
from ..record_design_intermediate import load_record_design_intermediate
from ..render_profile_eligibility import source_iban_country_text_field

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_m181_iban_country_text_is_bound_to_exact_official_row() -> None:
    root = Path("src/cadrumo/_data")
    source = load_record_design_intermediate(
        root,
        load_shared_catalogues(root / "registry/aeat").sources,
        source_ref="aeat-dr-181-2022",
        filing_year=2022,
        design_epoch="2022",
    )
    country = next(
        field
        for sheet in source.sheets
        for field in sheet.fields
        if field.sheet == "Tipo 2 - Registro Del Declarado" and field.source_row == 302
    )
    control = next(
        field
        for sheet in source.sheets
        for field in sheet.fields
        if field.sheet == country.sheet and field.source_row == 303
    )
    context = {"source_ref": str(source.source.source_ref), "source_sha256": source.source.source_sha256}
    assert source_iban_country_text_field(country, **context)
    assert not source_iban_country_text_field(control, **context)
    for changed in (
        country.model_copy(update={"offset": 80}),
        country.model_copy(update={"normalized_description": "CÓDIGO PAIS ISO"}),
    ):
        with pytest.raises(RegistryValidationError, match="text or geometry"):
            source_iban_country_text_field(changed, **context)
    with pytest.raises(RegistryValidationError, match="stale"):
        source_iban_country_text_field(country, source_ref=str(source.source.source_ref), source_sha256="0" * 64)
