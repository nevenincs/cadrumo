"""Authored member bindings project typed facts into the real Modelo 156 revision."""

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.domain.calculations.registry.afiliado_contribution_bindings import AfiliadoContributionProvider
from cadrumo.domain.calculations.registry.binding_provider_registration import registration_for
from cadrumo.domain.calculations.registry.binding_selector_utils import binding_row_set_selector
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_field_casilla import export_field_casilla_id
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.modelos.m156_rows import Modelo156AfiliadoRow, Modelo156MonthlyContribution

from ..compiler.loader import load_modelo_directory
from ..m156_row_materialisation import materialize_m156_member_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _revision() -> ModeloRevision:
    return load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/156")).revisions["2003-y-siguientes"]


def _member(number="001234567890", amount=Decimal("12.50")):
    return Modelo156AfiliadoRow(
        nif="12345678Z",
        numero_afiliacion=number,
        cotizaciones=tuple(
            Modelo156MonthlyContribution(month=m, status="N" if m == 1 else None, amount=amount if m == 1 else None)
            for m in range(1, 13)
        ),
    )


def test_all_member_fields_have_typed_row_selectors() -> None:
    revision = _revision()
    assert len(revision.bindings) == 27
    for binding in revision.bindings:
        selector = binding_row_set_selector(binding)
        assert selector is not None and selector.record == "afiliado" and selector.grouping == "per_member"
    assert registration_for(BindingSourceKind.AFILIADO_COTIZACION).disposition == "deferred"


def test_two_members_keep_independent_facts_unknowns_and_stable_indices() -> None:
    revision = _revision()
    first, second = _member(), _member("001234567891", Decimal("0"))
    values = materialize_m156_member_bindings(revision, (second, first))
    assert values == materialize_m156_member_bindings(revision, (first, second))
    assert values["modelo-156-row-numero-afiliacion", 1] == "001234567890"
    assert values["modelo-156-row-numero-afiliacion", 2] == "001234567891"
    assert values["modelo-156-row-cotizacion-01-importe", 1] == Decimal("12.50")
    assert values["modelo-156-row-cotizacion-01-importe", 2] == Decimal("0")
    assert values["modelo-156-row-cotizacion-01-situacion", 1] == "N"
    assert ("modelo-156-row-nombre", 1) not in values
    assert ("modelo-156-row-cotizacion-02-importe", 1) not in values
    assert ("modelo-156-row-cotizacion-02-situacion", 2) not in values


def test_unknown_allocation_and_duplicate_members_refuse() -> None:
    with pytest.raises(RegistryValidationError, match="no affiliate row bindings"):
        materialize_m156_member_bindings(_revision().model_copy(update={"bindings": ()}), (_member(),))
    for duplicate in (_member(), _member(amount=Decimal("99"))):
        with pytest.raises(RegistryValidationError, match="duplicate member identity"):
            materialize_m156_member_bindings(_revision(), (_member(), duplicate))


@pytest.mark.parametrize("field", ["cotizacion_00_importe", "cotizacion_13_importe", "cotizacion_01_total", "secret"])
def test_provider_refuses_unknown_source_fields(field) -> None:
    with pytest.raises(ValidationError):
        AfiliadoContributionProvider(
            target_casilla_id="cotizacion-enero",
            row_field=field,
            data_type="money",
            fact="row_field",
            grouping="per_member",
            record="afiliado",
        )


def test_provider_refuses_disguising_amounts_as_text() -> None:
    with pytest.raises(ValidationError, match="scalar type disagree"):
        AfiliadoContributionProvider(
            target_casilla_id="cotizacion-enero",
            row_field="cotizacion_01_importe",
            data_type="text",
            fact="row_field",
            grouping="per_member",
            record="afiliado",
        )


def test_binding_targets_and_months_match_the_official_record_positions() -> None:
    revision = _revision()
    record = next(
        record for layout in revision.export_layouts for record in layout.records if record.id == "modelo-156-afiliado"
    )
    bindings = {binding.id: binding for binding in revision.bindings}
    fields = {
        target: field
        for field in record.fields
        if (target := export_field_casilla_id(record, field, bindings=bindings)) is not None
    }
    targets = set()
    for binding in revision.bindings:
        provider = binding.provider
        assert isinstance(provider, AfiliadoContributionProvider)
        targets.add(provider.target_casilla_id)
        field = fields[provider.target_casilla_id]
        assert "enrolled-modelo-156-layout" in binding.source_refs
        if provider.row_field.startswith("cotizacion_"):
            _, month, component = provider.row_field.split("_")
            assert field.offset == 88 + 9 * (int(month) - 1) + (component == "importe")
            assert field.length == (8 if component == "importe" else 1)
        else:
            assert (field.offset, field.length) == {
                "nif": (18, 9),
                "nombre": (36, 40),
                "numero_afiliacion": (76, 12),
            }[provider.row_field]
    assert targets == set(fields)
