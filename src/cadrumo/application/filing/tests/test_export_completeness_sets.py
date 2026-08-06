"""Derivation of the fichero-BOE representable and rendered casilla sets.

These are the two set primitives the export completeness gate compares against
the calculation-completeness manifest: ``boe_representable_casilla_ids`` (the
casillas the official record design files a slot for, for a given disposition)
and ``rendered_casilla_ids`` (the representable casillas whose value actually
reaches disk). The gate refuses a draft that omits a required, representable
casilla, so these sets must be derived from the real layout, not approximated.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry import CasillaFieldKind, CasillaId
from .._export_parity import _did_page_suppressed, boe_representable_casilla_ids, rendered_casilla_ids
from ._export_support import (
    _approved_registry_draft,
    _modelo_130_export_headers,
    _schema_provider,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DID_PAGE_RECORD_TYPE = "page_did"


def _modelo_130_layout():
    provider = _schema_provider(modelos=("130",))
    return provider, provider.get_subview("130").export_layouts[0]


def test_representable_set_covers_fixed_width_casilla_fields() -> None:
    provider, layout = _modelo_130_layout()
    headers = _modelo_130_export_headers()

    representable = boe_representable_casilla_ids(layout, headers=headers, schema_provider=provider)

    normalized_headers = {key.lower(): value for key, value in headers.items()}
    casilla_field_ids = {
        field.casilla_id
        for record in layout.records
        if not _did_page_suppressed(record, headers=normalized_headers)
        for field in record.fields
        if field.kind == CasillaFieldKind.CASILLA and field.casilla_id is not None
    }
    assert casilla_field_ids
    # Every direct CASILLA field in a non-suppressed record is representable;
    # binding-row casillas may add more.
    assert casilla_field_ids.issubset(representable)


def test_rendered_set_is_representable_intersect_draft_values() -> None:
    provider, layout = _modelo_130_layout()
    draft = _approved_registry_draft()
    headers = _modelo_130_export_headers()

    representable = boe_representable_casilla_ids(layout, headers=headers, schema_provider=provider)
    rendered = rendered_casilla_ids(layout, draft=draft, headers=headers, schema_provider=provider)
    draft_casillas = {value.casilla_id for value in draft.values}

    assert rendered == representable & draft_casillas
    assert rendered.issubset(representable)


def test_dropping_a_required_casilla_removes_it_from_the_rendered_set() -> None:
    # The thin-file signal at the derivation level: a representable casilla the
    # draft no longer carries drops out of the rendered set, so the gate can see
    # the shortfall.
    provider, layout = _modelo_130_layout()
    draft = _approved_registry_draft()
    headers = _modelo_130_export_headers()

    rendered_full = rendered_casilla_ids(layout, draft=draft, headers=headers, schema_provider=provider)
    assert rendered_full

    dropped = sorted(rendered_full)[0]
    thin_draft = draft.model_copy(
        update={"values": tuple(value for value in draft.values if value.casilla_id != dropped)}
    )
    rendered_thin = rendered_casilla_ids(layout, draft=thin_draft, headers=headers, schema_provider=provider)

    assert dropped not in rendered_thin
    assert rendered_thin == rendered_full - {dropped}


def test_representable_set_excludes_disposition_suppressed_did_page() -> None:
    # The Modelo 303 refund (DID) page is emitted only for a refund disposition;
    # a non-refund filing suppresses it, so its casillas are not representable.
    provider = _schema_provider(modelos=("303",), filing_year=2025, period="1T")
    layout = provider.get_subview("303").export_layouts[0]

    did_casillas: set[CasillaId] = set()
    for record in layout.records:
        if record.record_type != _DID_PAGE_RECORD_TYPE:
            continue
        did_casillas.update(
            field.casilla_id
            for field in record.fields
            if field.kind == CasillaFieldKind.CASILLA and field.casilla_id is not None
        )
        did_casillas.update(record.row_field_casilla_ids.values())

    refund_headers = {"declaration_type": "D"}
    nonrefund_headers = {"declaration_type": "I"}
    representable_refund = boe_representable_casilla_ids(layout, headers=refund_headers, schema_provider=provider)
    representable_nonrefund = boe_representable_casilla_ids(layout, headers=nonrefund_headers, schema_provider=provider)

    # Suppression only ever removes casillas, never adds.
    assert representable_nonrefund.issubset(representable_refund)
    if did_casillas:
        assert did_casillas & representable_refund
        assert not (did_casillas & representable_nonrefund)
