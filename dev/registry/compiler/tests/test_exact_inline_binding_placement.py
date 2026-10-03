"""A source-complete binding field and its exact selector claim one wire slot."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition

from ..loader import load_modelo_directory
from ..validate_export_field_placement import (
    PlacedSpan,
    binding_export_spans,
    record_placed_spans,
    validate_export_record_field_placement,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _real_dpa_selector() -> tuple[ExportRecordDefinition, PlacedSpan, dict[str, tuple[PlacedSpan, ...]]]:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "131"))
    revision = modelo.revisions["2024"]
    record = next(record for record in revision.export_layouts[0].records if record.binding_record == "DPA")
    spans = dict(binding_export_spans(revision))
    selector = next(span for span in spans["DPA"] if span.offset == 13)
    return record, selector, spans


def _inline_binding(record: ExportRecordDefinition, selector: PlacedSpan) -> ExportFieldDefinition:
    payload = record.fields[0].model_dump(mode="python")
    payload.update(
        id="modelo-131-2024-dpa.modelo-131.dpa.epigrafe-iae",
        offset=selector.offset,
        length=selector.length,
        kind=CasillaFieldKind.BINDING,
        binding=selector.origin,
        literal=None,
        data_type=selector.data_type,
        decimals=selector.decimals,
        signed=selector.signed,
        padding="right_space",
        justification="left",
    )
    return ExportFieldDefinition.model_validate(payload)


def test_exact_inline_binding_matches_the_real_selector_once() -> None:
    record, selector, spans = _real_dpa_selector()
    field = _inline_binding(record, selector)
    candidate = record.model_copy(update={"fields": (*record.fields, field)})

    assert len(record_placed_spans(candidate, spans)) == len(record_placed_spans(record, spans))
    assert validate_export_record_field_placement(prefix="modelo 131", record=candidate, binding_spans=spans) == []
    assert candidate.repeat == "binding_rows"
    assert candidate.binding_record == "DPA"


@pytest.mark.parametrize(
    ("mutate", "changed"),
    (
        (lambda field: field.model_copy(update={"offset": 600}), "position"),
        (lambda field: field.model_copy(update={"length": 5}), "length"),
        (lambda field: field.model_copy(update={"data_type": CasillaDataType.INTEGER}), "type"),
        (lambda field: field.model_copy(update={"decimals": 1}), "decimals"),
        (lambda field: field.model_copy(update={"signed": True}), "signed"),
    ),
)
def test_same_binding_identity_refuses_changed_selector_shape(
    mutate: Callable[[ExportFieldDefinition], ExportFieldDefinition], changed: str
) -> None:
    record, selector, spans = _real_dpa_selector()
    candidate = record.model_copy(update={"fields": (*record.fields, mutate(_inline_binding(record, selector)))})

    failures = validate_export_record_field_placement(prefix="modelo 131", record=candidate, binding_spans=spans)
    assert any("does not match its fixed selector" in failure for failure in failures)
    assert any(changed in failure for failure in failures)


def test_inline_binding_for_another_record_refuses_even_without_a_matching_dpa_selector() -> None:
    record, selector, spans = _real_dpa_selector()
    did_selector = next(span for span in spans["DID"] if span.offset == 12)
    wrong = _inline_binding(record, selector).model_copy(
        update={"binding": did_selector.origin, "offset": 600, "length": did_selector.length}
    )
    candidate = record.model_copy(update={"fields": (*record.fields, wrong)})

    failures = validate_export_record_field_placement(prefix="modelo 131", record=candidate, binding_spans=spans)
    assert any("belongs to fixed selector record 'DID', not 'DPA'" in failure for failure in failures)


def test_two_inline_fields_for_one_selector_refuse_ambiguity() -> None:
    record, selector, spans = _real_dpa_selector()
    field = _inline_binding(record, selector)
    second = field.model_copy(update={"id": "modelo-131-2024-dpa-duplicate-epigrafe-iae"})
    candidate = record.model_copy(update={"fields": (*record.fields, field, second)})

    failures = validate_export_record_field_placement(prefix="modelo 131", record=candidate, binding_spans=spans)
    assert any("does not match its fixed selector" in failure for failure in failures)
    assert any("OVERLAP" in failure for failure in failures)
