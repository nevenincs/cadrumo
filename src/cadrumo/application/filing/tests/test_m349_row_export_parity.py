"""Completeness parity for repeated Modelo 349 operator-record bindings."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.filing.errors import FilingExportError
from .._export_parity import assert_export_mirrors_manifest
from ..draft_construction import build_draft
from ..runtime import ModeloOperatorProfile, build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _m349_draft(*, operation: PinnedAuthorityOperation):
    period = Period.from_year_and_code(2026, "1T")
    schema_provider = build_runtime_schema_provider(
        filing_year=2026,
        period=period,
        modelos=("349",),
        operation=operation,
    )
    draft = build_draft(
        modelo="349",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Ana Operadora"),
        inputs={
            "iva-349-declarante-numero-operadores": Decimal("1"),
            "iva-349-declarante-importe-operaciones": Decimal("1000"),
            "iva-349-declarante-numero-rectificaciones": Decimal("0"),
            "iva-349-declarante-importe-rectificaciones": Decimal("0"),
            "iva-349-operador-row-codigo-pais": {"1": "DE"},
            "iva-349-operador-row-nif": {"1": "123456789"},
            "iva-349-operador-row-apellidos": {"1": "Kunde GmbH"},
            "iva-349-operador-row-clave": {"1": "E"},
            "iva-349-operador-row-base": {"1": Decimal("1000")},
        },
        schema_provider=schema_provider,
    )
    return draft, schema_provider


def test_m349_populated_operator_rows_are_rendered_and_missing_required_nif_refuses(
    operation: PinnedAuthorityOperation,
) -> None:
    """The parity guard admits a complete row and refuses the same row without its NIF."""
    draft, schema_provider = _m349_draft(operation=operation)
    snapshot = schema_provider.get_snapshot("349")
    (layout,) = snapshot.revision.export_layouts
    subview = schema_provider.get_subview("349")
    assert subview.completeness_manifest is not None

    assert_export_mirrors_manifest(
        layout,
        draft=draft,
        headers={},
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        schema_provider=schema_provider,
        manifest=subview.completeness_manifest,
        casilla_metadata=subview.casilla_record_metadata,
    )

    incomplete_draft = draft.model_copy(
        update={
            "binding_values": tuple(
                value for value in draft.binding_values if value.binding_id != "iva-349-operador-row-nif"
            ),
        },
    )
    with pytest.raises(FilingExportError) as refusal:
        assert_export_mirrors_manifest(
            layout,
            draft=incomplete_draft,
            headers={},
            prior_domiciliation_election=PriorDomiciliationElection.KEEP,
            schema_provider=schema_provider,
            manifest=subview.completeness_manifest,
            casilla_metadata=subview.casilla_record_metadata,
        )

    assert refusal.value.translated_message == "application.filing.export_parity.errors.required_casillas_omitted"
    assert {item["casilla_id"] for item in refusal.value.context["missing_casillas"]} == {"op.nif-comunitario"}
