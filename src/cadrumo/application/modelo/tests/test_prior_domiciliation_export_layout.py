"""Byte-level M303 prior-domiciliation marker coverage across record designs."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....application.filing import build_runtime_schema_provider, render_layout
from ....application.filing._export_parity import boe_representable_casilla_ids, rendered_casilla_ids
from ....core import Period, PriorDomiciliationElection, ResultDisposition, validated_casilla_id
from ....domain.calculations.registry import CasillaFieldKind, RegistrySnapshotRef
from ....domain.filing import ModeloDraft, ModeloValue, ModeloValueKind
from ....domain.submission import ModeloDraftStatus

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_M303_CASILLA_111 = validated_casilla_id("111", surface="M303 Nota 3 layout test")


def _approved_m303_draft(
    *,
    filing_year: int,
    revision_id: str,
    period: Period,
    schema_version: str,
    casilla_111: Decimal | None = None,
) -> ModeloDraft:
    """Build the real export input envelope with no invented casilla data."""
    return ModeloDraft(
        draft_id="d" + "0" * 63,
        modelo="303",
        period=period,
        profile_tax_id="X1234567L",
        subject_tax_id="X1234567L",
        snapshot_ref=RegistrySnapshotRef(
            modelo="303",
            revision_id=revision_id,
            modelo_year=filing_year,
            period=period.registry_token,
        ),
        status=ModeloDraftStatus.APROBADO,
        values=(
            ModeloValue(
                casilla_id=_M303_CASILLA_111,
                value=casilla_111,
                kind=ModeloValueKind.LITERAL,
                source="operator-declared Nota 3 amount",
            ),
        )
        if casilla_111 is not None
        else (),
        created_at=datetime(filing_year, 5, 21, 12, 3, tzinfo=UTC),
        updated_at=datetime(filing_year, 5, 21, 12, 3, tzinfo=UTC),
        schema_version=schema_version,
    )


@pytest.mark.parametrize(
    ("filing_year", "revision_id", "marker_offset", "casilla_111_offset", "source_ref"),
    [
        (2025, "2025", 406, 424, "aeat-dr-303-2025"),
        (2026, "2026-y-siguientes", 440, 441, "aeat-dr-303-2026"),
    ],
)
def test_prior_domiciliation_marker_is_rendered_at_the_official_page_three_byte_offset(
    filing_year: int,
    revision_id: str,
    marker_offset: int,
    casilla_111_offset: int,
    source_ref: str,
) -> None:
    """The active registry layout, not Python offsets, emits the selected ``X``."""
    period = Period.from_year_and_code(filing_year, "1T")
    provider = build_runtime_schema_provider(filing_year=filing_year, period=period, modelos=("303",))
    subview = provider.get_subview("303")
    layout = subview.export_layouts[0]
    page_three = next(record for record in layout.records if record.record_type == "page_03")
    fields = {field.header_key: field for field in page_three.fields if field.header_key is not None}

    assert fields["prior_domiciliation_action"].offset == marker_offset
    assert next(field for field in page_three.fields if field.casilla_id == "111").offset == casilla_111_offset
    assert source_ref in fields["prior_domiciliation_action"].source_refs

    payload = render_layout(
        layout,
        draft=_approved_m303_draft(
            filing_year=filing_year,
            revision_id=revision_id,
            period=period,
            schema_version=subview.schema_version,
        ),
        headers={
            "declaration_type": ResultDisposition.INGRESO.value,
            "full_name": "Layout Operator",
            "surnames": "Layout",
            "name": "Operator",
            "entity_type": "",
            "fecha_inicio_periodo": f"0101{filing_year}",
            "fecha_fin_periodo": f"3103{filing_year}",
            "devengo_start_date": f"0101{filing_year}",
            "tax_id": "X1234567L",
            "presenter_nif": "X1234567L",
            "program_version": "A001",
            "redeme": "2",
            "prior_domiciliation_action": "X",
        },
    )

    start = payload.index(b"<T30303000>")
    rendered_page_three = payload[start : start + 1017]
    assert rendered_page_three[marker_offset - 1 : marker_offset] == b"X"


@pytest.mark.parametrize(
    ("filing_year", "revision_id"),
    [
        (2025, "2025"),
        (2026, "2026-y-siguientes"),
    ],
)
def test_nota_three_did_page_and_parity_share_the_keep_vs_cancel_predicate(
    filing_year: int,
    revision_id: str,
) -> None:
    """A zero c111 still triggers Nota 3, while X suppresses only that page."""
    period = Period.from_year_and_code(filing_year, "1T")
    provider = build_runtime_schema_provider(filing_year=filing_year, period=period, modelos=("303",))
    subview = provider.get_subview("303")
    layout = subview.export_layouts[0]
    draft = _approved_m303_draft(
        filing_year=filing_year,
        revision_id=revision_id,
        period=period,
        schema_version=subview.schema_version,
        casilla_111=Decimal("0"),
    )
    headers = {
        "declaration_type": ResultDisposition.COMPENSACION.value,
        "autoliq_rectificativa": "1",
        "full_name": "Nota Three Operator",
        "surnames": "Nota",
        "name": "Three",
        "entity_type": "",
        "fecha_inicio_periodo": f"0101{filing_year}",
        "fecha_fin_periodo": f"3103{filing_year}",
        "devengo_start_date": f"0101{filing_year}",
        "tax_id": "X1234567L",
        "presenter_nif": "X1234567L",
        "program_version": "A001",
        "redeme": "2",
    }

    keep_payload = render_layout(
        layout,
        draft=draft,
        headers=headers,
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
    )
    keep_representable = boe_representable_casilla_ids(
        layout,
        draft=draft,
        headers=headers,
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        schema_provider=provider,
    )
    keep_rendered = rendered_casilla_ids(
        layout,
        draft=draft,
        headers=headers,
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        schema_provider=provider,
    )

    cancel_headers = {**headers, "prior_domiciliation_action": "X"}
    cancel_payload = render_layout(
        layout,
        draft=draft,
        headers=cancel_headers,
        prior_domiciliation_election=PriorDomiciliationElection.CANCEL_OR_MODIFY,
    )
    cancel_representable = boe_representable_casilla_ids(
        layout,
        draft=draft,
        headers=cancel_headers,
        prior_domiciliation_election=PriorDomiciliationElection.CANCEL_OR_MODIFY,
        schema_provider=provider,
    )
    cancel_rendered = rendered_casilla_ids(
        layout,
        draft=draft,
        headers=cancel_headers,
        prior_domiciliation_election=PriorDomiciliationElection.CANCEL_OR_MODIFY,
        schema_provider=provider,
    )

    assert b"<T303DID00>" in keep_payload
    assert b"<T303DID00>" not in cancel_payload
    assert _M303_CASILLA_111 in keep_representable
    assert _M303_CASILLA_111 in cancel_representable
    assert keep_rendered == cancel_rendered == {_M303_CASILLA_111}

    did_casillas = {
        field.casilla_id
        for record in layout.records
        if record.record_type == "page_did"
        for field in record.fields
        if field.kind is CasillaFieldKind.CASILLA and field.casilla_id is not None
    }
    assert not did_casillas, "M303 DID is header-only, so record-order parity owns its suppression"
