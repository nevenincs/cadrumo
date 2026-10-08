"""Reproduce the complete M720 source and exercise its exact value channels."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.filing.draft_construction import build_draft
from cadrumo.application.filing.export_producer import filing_producer_values
from cadrumo.application.filing.producer_snapshot import (
    FilingElectionFacts,
    FilingProducerSnapshot,
    GeneralFilingProfileFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)
from cadrumo.application.filing.record_field_renderer import render_record
from cadrumo.application.filing.record_types import RecordRenderRow
from cadrumo.application.filing.runtime import ModeloOperatorProfile, schema_provider_from_authority
from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.core.modelo import Modelo
from cadrumo.core.payment_election import PaymentElection
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.refund_election import RefundElection
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_semantics import ExportDraftAttribute
from cadrumo.domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from cadrumo.domain.calculations.registry.fixed_width_parser import parse_fixed_width_export_field
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.filing.schema import ModeloDraft

from ...compiler.authority import compiled_bundled_authority
from ...compiler.validate_export_field_placement import binding_export_spans, validate_export_record_field_placement
from .._export_tree import render_complete_export_tree
from ..render_check import RevisionRenderInputs, revision_render_inputs
from ..render_profile import validate_render_profile
from ..render_profile_authority import _validate_signed_composite_source_agreement

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def inputs() -> RevisionRenderInputs:
    return revision_render_inputs(
        compiled_bundled_authority(),
        modelo="720",
        revision="2013-y-siguientes",
        source_ref="aeat-dr-720",
        filing_year=2024,
        period="0A",
        source_root=bundled_path(),
    )


def _public_record_context() -> tuple[ModeloDraft, FilingProducerSnapshot]:
    authority = compiled_bundled_authority()
    period = Period.from_year_and_code(2024, "0A")
    with validating_governed_facts(authority):
        draft = build_draft(
            modelo="720",
            period=period,
            profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="PERSONA PRUEBA"),
            inputs={
                "modelo-720.type_1.telefono-contacto": "012345678",
                "modelo-720.type_2.fecha-de-incorporacion": date(2024, 2, 29),
                "modelo-720.type_2.numero-de-valores": Decimal("12.34"),
                "modelo-720.type_2.porcentaje-de-participacion": Decimal("25.50"),
            },
            schema_provider=schema_provider_from_authority(
                authority, filing_year=2024, period=period, modelos=("720",)
            ),
        )
        producer = build_filing_producer_snapshot(
            modelo=Modelo("720"),
            taxpayer_tax_id=draft.profile_tax_id,
            taxpayer_identity=TaxpayerIdentityFacts(
                legal_name=None, given_name="PERSONA", surnames="PRUEBA", full_name="PERSONA PRUEBA"
            ),
            presenter=PresenterIdentity(tax_id="00000000T", full_name="PRESENTADOR PRUEBA"),
            model_profile=GeneralFilingProfileFacts(),
            elections=FilingElectionFacts(
                result_disposition=None,
                payment=PaymentElection.INGRESO,
                refund=RefundElection.COMPENSAR,
                prior_domiciliation=PriorDomiciliationElection.KEEP,
            ),
            amendment_evidence=None,
            refund_account=None,
            charge_account=None,
            m303_filing_facts=None,
        )
    return draft, producer


def test_complete_source_renders_two_500_position_records_with_exact_contact_and_decimal_values(
    inputs: RevisionRenderInputs, tmp_path: Path
) -> None:
    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=inputs.revision_id,
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
    )
    fields = {
        (record.record_type, field.offset): field for record in rendered.layout.records for field in record.fields
    }
    for record_type, record_tag in (("type_1", "1"), ("type_2", "2")):
        for offset, literal in ((1, record_tag), (2, "720")):
            field = fields[record_type, offset]
            assert field.kind.value == "literal"
            assert field.literal == literal
            assert field.binding is None
        year = fields[record_type, 5]
        taxpayer = fields[record_type, 9]
        assert year.kind.value == "draft"
        assert year.draft_attribute is ExportDraftAttribute.FILING_YEAR
        assert year.binding is None
        assert taxpayer.kind.value == "header"
        assert taxpayer.producer_key is FilingProducerKey.TAXPAYER_TAX_ID
        assert taxpayer.binding is None
    assert fields["type_1", 18].producer_key is FilingProducerKey.TAXPAYER_FULL_NAME
    assert fields["type_1", 18].binding is None
    phone = fields["type_1", 59]
    name = fields["type_1", 68]
    assert (phone.length, name.length) == (9, 40)
    assert str(phone.binding) == "modelo-720.type_1.telefono-contacto"
    assert str(name.binding) == "modelo-720.type_1.nombre-contacto"
    assert render_fixed_width_export_field(phone, "012345678") == "012345678"
    assert render_fixed_width_export_field(name, "PERSONA PRUEBA") == "PERSONA PRUEBA".ljust(40)
    for offset in (108, 123):
        identifier = fields["type_1", offset]
        assert render_fixed_width_export_field(identifier, "0000000000001") == "0000000000001"
    quantity_whole = fields["type_2", 463]
    quantity_fraction = fields["type_2", 473]
    assert quantity_whole.binding == quantity_fraction.binding
    assert render_fixed_width_export_field(quantity_whole, Decimal("12.34")) == "0000000012"
    assert render_fixed_width_export_field(quantity_fraction, Decimal("12.34")) == "34"
    assert render_fixed_width_export_field(fields["type_2", 476], Decimal("25.50")) == "02550"
    for offset in (415, 424):
        field = fields["type_2", offset]
        assert render_fixed_width_export_field(field, date(2024, 2, 29)) == "20240229"
    draft, producer = _public_record_context()
    for record in rendered.layout.records:
        assert all(field.offset is not None and field.length is not None for field in record.fields)
        assert record.line_ending == "crlf"
        boundary_values: dict[tuple[BindingId, int | None], object] = {
            (field.binding, None): int(field.allowed_values[0]) if field.allowed_values else None
            for field in record.fields
            if field.binding is not None
        }
        wire = render_record(
            record,
            draft=draft,
            producer_values=filing_producer_values(producer),
            producer_snapshot=producer,
            casilla_values={},
            binding_values=boundary_values,
            row=RecordRenderRow(
                row_index=None, active_binding_ids=frozenset(binding for binding, _ in boundary_values)
            ),
            render_context=None,
            projection_values={},
        )
        assert len(wire.encode(record.encoding)) == 500
        assert wire[:4] == {"type_1": "1720", "type_2": "2720"}[record.record_type]
        assert wire[4:8] == "2024"
        assert wire[8:17] == str(producer.taxpayer_tax_id)
        if record.record_type == "type_1":
            assert wire[17:57] == "PERSONA PRUEBA".ljust(40)
    for record_type, offset, whole in (
        ("type_1", 145, 15),
        ("type_1", 163, 15),
        ("type_2", 432, 12),
        ("type_2", 447, 12),
    ):
        field = fields[record_type, offset]
        for value, sign in ((Decimal("-1234.56"), "N"), (Decimal("1234.56"), " "), (Decimal(0), " ")):
            wire = render_fixed_width_export_field(field, value)
            assert wire == sign + str(abs(int(value * 100))).rjust(whole + 2, "0")
            assert parse_fixed_width_export_field(field, wire) == value


@pytest.mark.parametrize("row", (161, 196, 720, 785))
def test_signed_amount_requires_complete_exact_source_prose_and_geometry(
    inputs: RevisionRenderInputs, row: int
) -> None:
    rule = next(rule for rule in inputs.render_profile.signed_composite_rules if rule.anchor.source_row == row)
    field = next(field.parser_field for field in inputs.joined.fields if field.parser_field.source_row == row)
    identity = inputs.render_profile.design_identity
    _validate_signed_composite_source_agreement(rule, field, identity)
    assert "será un espacio" in (field.content or "")
    assert "sin coma decimal" in (field.content or "")
    for update in (
        {"content": (field.content or "").replace("será un espacio", "será un cero", 1)},
        {"content": (field.content or "").replace("sin coma decimal", "con coma decimal", 1)},
        {"content": (field.content or "") + " La parte decimal ocupa tres posiciones."},
        {"offset": field.offset + 1},
        {"length": field.length + 1},
        {"ordinal": "99"},
        {"record_identity": "other record"},
    ):
        with pytest.raises(RegistryValidationError, match="signed monetary composite"):
            _validate_signed_composite_source_agreement(rule, field.model_copy(update=update), identity)
    with pytest.raises(RegistryValidationError, match="unreviewed or stale"):
        _validate_signed_composite_source_agreement(
            rule, field, identity.model_copy(update={"source_sha256": "0" * 64})
        )
    with pytest.raises(RegistryValidationError, match="signed monetary composite"):
        _validate_signed_composite_source_agreement(
            rule.model_copy(update={"integer_digits": rule.integer_digits - 1}), field, identity
        )


def test_each_source_amount_and_numeric_anchor_requires_explicit_review(inputs: RevisionRenderInputs) -> None:
    for update in (
        {"signed_composite_rules": inputs.render_profile.signed_composite_rules[:-1]},
        {"singleton_rules": inputs.render_profile.singleton_rules[:-1]},
    ):
        with pytest.raises(RegistryValidationError, match="cover exactly"):
            validate_render_profile(
                inputs.render_profile.model_copy(update=update), inputs.joined, inputs.render_profile_source_evidence
            )


def test_reviewed_binding_channels_preserve_source_units_and_distinct_contact_facts() -> None:
    revision = compiled_bundled_authority().modelo("720").revisions["2013-y-siguientes"]
    by_id = {str(binding.id): binding for binding in revision.bindings}
    assert "modelo-720.type_1.persona-con-quien-relacionarse" not in by_id
    for field in (
        "telefono-contacto",
        "nombre-contacto",
        "numero-identificativo-de-la-declaracion",
        "numero-identificativo-de-la-declaracion-anterior",
    ):
        assert by_id[f"modelo-720.type_1.{field}"].value.channel.value == "text"
    for binding_id in (
        "modelo-720.type_1.suma-total-de-valoracion-1-saldo-o-valor-a-31-de-diciembre-s",
        "modelo-720.type_1.suma-total-de-valoracion-2-importe-o-valor-de-la-transmision",
        "modelo-720.type_2.valoracion-1-saldo-o-valor-a-31-de-diciembre-saldo-o-valor-e",
        "modelo-720.type_2.valoracion-2-importe-o-valor-de-la-transmision-saldo-medio-u",
    ):
        assert by_id[binding_id].value.data_type.value == "money"
        assert by_id[binding_id].value.channel.value == "decimal"
    for field in ("numero-de-valores", "porcentaje-de-participacion"):
        assert by_id[f"modelo-720.type_2.{field}"].value.data_type.value == "decimal"
    for field in ("fecha-de-incorporacion", "fecha-de-extincion"):
        assert by_id[f"modelo-720.type_2.{field}"].value.channel.value == "date"


def test_quantity_parts_reconcile_only_as_the_complete_declared_decimal_span(
    inputs: RevisionRenderInputs, tmp_path: Path
) -> None:
    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=inputs.revision_id,
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
    )
    revision = compiled_bundled_authority().modelo("720").revisions["2013-y-siguientes"]
    spans = binding_export_spans(revision)
    record = next(record for record in rendered.layout.records if record.record_type == "type_2")
    whole = next(field for field in record.fields if field.offset == 463)
    fraction = next(field for field in record.fields if field.offset == 473)
    assert validate_export_record_field_placement(prefix="modelo 720", record=record, binding_spans=spans) == []
    corrupt_fields = (
        tuple(field for field in record.fields if field is not fraction),
        tuple(whole.model_copy(update={"offset": 464}) if field is whole else field for field in record.fields),
        tuple(fraction.model_copy(update={"length": 1}) if field is fraction else field for field in record.fields),
        tuple(
            fraction.model_copy(update={"value_policy": None}) if field is fraction else field
            for field in record.fields
        ),
        (*record.fields, fraction.model_copy(update={"id": "duplicate-quantity-fraction"})),
    )
    for fields in corrupt_fields:
        failures = validate_export_record_field_placement(
            prefix="modelo 720",
            record=record.model_copy(update={"fields": fields}),
            binding_spans=spans,
        )
        assert any("does not match its fixed selector" in failure for failure in failures)
