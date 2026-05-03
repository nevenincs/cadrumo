"""Tests for binding, relation, and export layout registry resolution."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from typing import cast

import pytest

from ._bindings import resolve_bound_casilla_inputs
from ._errors import RegistryValidationError
from ._export import export_fields_for_casilla, resolve_export_layout
from ._relations import resolve_relation_values
from ._schema import (
    CasillaDefinition,
    DataBindingDefinition,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    LegalReference,
    ModeloDefinition,
    ModeloRevision,
    PeriodSelector,
    RegistrySnapshot,
    RelationDefinition,
    SourceReference,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _legal_reference() -> LegalReference:
    return LegalReference(
        id="ley-37-1992:art-90",
        authority="boe",
        kind="ley",
        corpus_ref="corpus/normatives/ley-37-1992.json#art-90",
        document_id="BOE-A-1992-28740",
        article="90",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a90",
        effective_from=date(1992, 12, 29),
        review_status="reviewed",
    )


def _source_reference() -> SourceReference:
    return SourceReference(
        id="aeat-dr-303",
        authority="aeat",
        kind="record_design",
        corpus_path="corpus/source.xlsx",
        sha256=hashlib.sha256(b"x").hexdigest(),
        bytes=1,
        retrieved_at=date(2026, 5, 3),
        source_url="https://sede.agenciatributaria.gob.es/source.xlsx",
        review_status="reviewed",
    )


def _field(field_id: str, casilla: str, *, offset: int = 0, length: int = 12) -> ExportFieldDefinition:
    return ExportFieldDefinition(
        id=field_id,
        offset=offset,
        length=length,
        kind="casilla",
        casilla=casilla,
        data_type="money",
        required=True,
        padding="left_zero",
        justification="right",
        signed=False,
        legal_refs=("ley-37-1992:art-90",),
        source_refs=("aeat-dr-303",),
    )


def _snapshot(
    *,
    casilla: CasillaDefinition | None = None,
    export_layouts: tuple[ExportLayoutDefinition, ...] | None = None,
) -> RegistrySnapshot:
    legal_ref = _legal_reference()
    source_ref = _source_reference()
    bound_casilla = casilla or CasillaDefinition(
        id="01",
        number="01",
        label="Base imponible",
        section=("iva",),
        data_type="money",
        required=True,
        input_kind="bound",
        binding="ledger.base",
        export_refs=("field.01",),
        legal_refs=("ley-37-1992:art-90",),
        source_refs=("aeat-dr-303",),
    )
    revision = ModeloRevision(
        id="2026",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(years=(2026,), periods=("1T",)),
        legal_refs=("ley-37-1992:art-90",),
        source_refs=("aeat-dr-303",),
        casillas=(bound_casilla,),
        bindings=(
            DataBindingDefinition(
                id="ledger.base",
                source="ledger",
                selector={"account": "477"},
                aggregation={"op": "sum"},
                legal_refs=("ley-37-1992:art-90",),
                source_refs=("aeat-dr-303",),
            ),
        ),
        relations=(
            RelationDefinition(
                id="prev.output",
                kind="previous_period",
                source_modelo="303",
                source_revision_selector={"year": 2026},
                source_output="01",
                target_binding="ledger.base",
                period_alignment={"previous": 1},
                aggregation={"op": "sum"},
                legal_refs=("ley-37-1992:art-90",),
                source_refs=("aeat-dr-303",),
            ),
        ),
        export_layouts=export_layouts
        or (
            ExportLayoutDefinition(
                id="dr-303",
                legal_refs=("ley-37-1992:art-90",),
                source_refs=("aeat-dr-303",),
                records=(
                    ExportRecordDefinition(
                        id="record.1",
                        record_type="1",
                        order=0,
                        encoding="iso-8859-1",
                        line_ending="crlf",
                        fields=(_field("field.01", "01"),),
                    ),
                ),
            ),
        ),
    )
    modelo = ModeloDefinition(
        id="303",
        title="IVA",
        official_name="IVA",
        tax_domain="iva",
        cadence="quarterly",
        jurisdiction="ES-AEAT",
        legal_refs=("ley-37-1992:art-90",),
        source_refs=("aeat-dr-303",),
        revisions={"2026": revision},
    )
    return RegistrySnapshot(
        modelo=modelo,
        revision=revision,
        legal={legal_ref.id: legal_ref},
        sources={source_ref.id: source_ref},
    )


def test_resolve_bound_casilla_inputs_maps_factual_bindings() -> None:
    snapshot = _snapshot()

    resolved = resolve_bound_casilla_inputs(snapshot.revision, {"ledger.base": Decimal("123.45")})

    assert resolved == {"01": Decimal("123.45")}


def test_resolve_bound_casilla_inputs_rejects_non_decimal_values() -> None:
    snapshot = _snapshot()

    with pytest.raises(RegistryValidationError, match="must be a Decimal"):
        resolve_bound_casilla_inputs(snapshot.revision, cast("dict[str, Decimal]", {"ledger.base": 123}))


def test_resolve_relation_values_sums_previous_period_outputs() -> None:
    snapshot = _snapshot()

    resolved = resolve_relation_values(snapshot.revision, {"prev.output": (Decimal("1.50"), Decimal("2.25"))})

    assert resolved == {"prev.output": Decimal("3.75")}


def test_resolve_relation_values_rejects_unknown_relation() -> None:
    snapshot = _snapshot()

    with pytest.raises(RegistryValidationError, match="unknown relation ids"):
        resolve_relation_values(snapshot.revision, {"other": Decimal("1")})


def test_resolve_export_layout_returns_ordered_fields_and_casilla_index() -> None:
    snapshot = _snapshot()

    resolved = resolve_export_layout(snapshot)

    assert resolved.layout.id == "dr-303"
    assert tuple(resolved.fields_by_id) == ("field.01",)
    assert export_fields_for_casilla(resolved, "01")[0].id == "field.01"


def test_resolve_export_layout_rejects_ambiguous_default() -> None:
    first = ExportLayoutDefinition(
        id="dr-303-a",
        legal_refs=("ley-37-1992:art-90",),
        source_refs=("aeat-dr-303",),
    )
    second = first.model_copy(update={"id": "dr-303-b"})
    snapshot = _snapshot(export_layouts=(first, second))

    with pytest.raises(RegistryValidationError, match="export layout id is required"):
        resolve_export_layout(snapshot)


def test_resolve_export_layout_rejects_missing_casilla_backlink() -> None:
    casilla = CasillaDefinition(
        id="01",
        number="01",
        label="Base imponible",
        section=("iva",),
        data_type="money",
        required=True,
        input_kind="bound",
        binding="ledger.base",
        legal_refs=("ley-37-1992:art-90",),
        source_refs=("aeat-dr-303",),
    )
    snapshot = _snapshot(casilla=casilla)

    with pytest.raises(RegistryValidationError, match="does not declare the export ref"):
        resolve_export_layout(snapshot)


def test_resolve_export_layout_rejects_overlapping_fixed_width_fields() -> None:
    casilla = CasillaDefinition(
        id="01",
        number="01",
        label="Base imponible",
        section=("iva",),
        data_type="money",
        required=True,
        input_kind="bound",
        binding="ledger.base",
        export_refs=("field.01", "field.01b"),
        legal_refs=("ley-37-1992:art-90",),
        source_refs=("aeat-dr-303",),
    )
    layout = ExportLayoutDefinition(
        id="dr-303",
        legal_refs=("ley-37-1992:art-90",),
        source_refs=("aeat-dr-303",),
        records=(
            ExportRecordDefinition(
                id="record.1",
                record_type="1",
                order=0,
                encoding="iso-8859-1",
                line_ending="crlf",
                fields=(
                    _field("field.01", "01", offset=0, length=12),
                    _field("field.01b", "01", offset=10, length=4),
                ),
            ),
        ),
    )
    snapshot = _snapshot(casilla=casilla, export_layouts=(layout,))

    with pytest.raises(RegistryValidationError, match="overlap"):
        resolve_export_layout(snapshot)
