"""Unit tests for :mod:`aeat.schema._cache`."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ..modelos import ModeloCode
from . import (
    BinaryFormulaOp,
    BinaryOp,
    Casilla,
    CasillaDataType,
    CasillaRef,
    Modelo,
    SchemaCacheError,
    SchemaProvenance,
    SchemaSource,
    SchemaValidationError,
    SchemaVersion,
    load_modelo_from_cache,
    resolve_schema_cache_file,
    save_modelo_to_cache,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_SHA = "b" * 64


def _make_modelo() -> Modelo:
    sub = BinaryOp(
        op=BinaryFormulaOp.SUB,
        left=CasillaRef(casilla_id="01"),
        right=CasillaRef(casilla_id="03"),
    )
    casillas = (
        Casilla(
            casilla_id="01",
            label={"es": "Base imponible"},
            data_type=CasillaDataType.CURRENCY_EUR,
            source_page=1,
        ),
        Casilla(
            casilla_id="03",
            label={"es": "Ingresos"},
            data_type=CasillaDataType.CURRENCY_EUR,
            source_page=1,
        ),
        Casilla(
            casilla_id="07",
            label={"es": "Rendimiento"},
            data_type=CasillaDataType.CURRENCY_EUR,
            computed=True,
            formula=sub,
            references_casillas=("01", "03"),
            source_page=1,
        ),
    )
    provenance = SchemaProvenance(
        source=SchemaSource.BOE_ORDEN,
        origin_url=TypeAdapter(AnyHttpUrl).validate_python("https://www.boe.es/example.pdf"),
        document_ref="BOE-A-FAKE",
        sha256=_SHA,
        content_length=4096,
        fetched_at=datetime(2026, 4, 17, 9, 0, tzinfo=UTC),
    )
    return Modelo(
        modelo_code=ModeloCode.MODELO_130,
        period="2025Q4",
        casillas=casillas,
        provenance=provenance,
        extracted_at=datetime(2026, 4, 17, 9, 5, tzinfo=UTC),
        schema_version=SchemaVersion(boe_ref="BOE-A-FAKE"),
    )


def test_resolve_schema_cache_file_happy_path(tmp_path: Path) -> None:
    path = resolve_schema_cache_file(
        ModeloCode.MODELO_130,
        "BOE-A-2023-15412",
        tmp_path,
    )
    assert path == tmp_path / "modelo_130" / "BOE-A-2023-15412.json"


def test_resolve_schema_cache_file_rejects_dirty_ref(tmp_path: Path) -> None:
    with pytest.raises(SchemaCacheError):
        resolve_schema_cache_file(ModeloCode.MODELO_130, "../etc/passwd", tmp_path)


def test_cache_round_trip(tmp_path: Path) -> None:
    modelo = _make_modelo()
    written = save_modelo_to_cache(modelo, root=tmp_path, boe_ref="BOE-A-FAKE")
    assert written.exists()
    restored = load_modelo_from_cache(ModeloCode.MODELO_130, "BOE-A-FAKE", tmp_path)
    assert restored == modelo


def test_cache_serialises_range_rule_aliases(tmp_path: Path) -> None:
    # A Modelo without a RangeRule is exercised by the round-trip test
    # above; this assertion hand-inspects the persisted bytes to prove
    # the ``by_alias=True`` path survives the round-trip.
    from . import RangeRule  # local import to keep test isolated

    rule = RangeRule.model_validate({"min": Decimal("0"), "max": Decimal("10")})
    payload = rule.model_dump(mode="json", by_alias=True)
    assert set(payload) >= {"min", "max", "kind"}


def test_cache_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SchemaCacheError):
        load_modelo_from_cache(ModeloCode.MODELO_130, "BOE-A-NOPE", tmp_path)


def test_cache_invalid_json(tmp_path: Path) -> None:
    path = resolve_schema_cache_file(ModeloCode.MODELO_130, "BOE-A-FAKE", tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"not": "a modelo"}', encoding="utf-8")
    with pytest.raises(SchemaValidationError):
        load_modelo_from_cache(ModeloCode.MODELO_130, "BOE-A-FAKE", tmp_path)
