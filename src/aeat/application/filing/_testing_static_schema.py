"""Application-local synthetic casilla schemas for filing tests.

These records exist only for repository fixture tests and public testing
helpers. They are not filing-grade modelo definitions and they do not replace
validated registry snapshots.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ...domain.filing._schema import SCHEMA_VERSION_DEFAULT


class CasillaSource(BaseModel):
    """Provenance citation for one synthetic casilla schema record."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    kind: Literal["boe", "manual", "interactive_form_xml", "printed_form_pdf"]
    citation: str = Field(min_length=1)
    url: str | None = None
    retrieved_at: date | None = None
    snapshot_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class StaticCasillaSchema(BaseModel):
    """Strict synthetic record matching the filing schema protocol."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    id: str
    value_type: str
    required: bool = False
    formula_inputs: tuple[str, ...] = Field(default_factory=tuple)
    min_value: float | int | None = None
    max_value: float | int | None = None
    default: Decimal | int | str | bool | None = None
    description: str = ""
    sources: tuple[CasillaSource, ...] = Field(default_factory=tuple)
    valid_from: date | None = None
    valid_to: date | None = None


class StaticCasillaCollection(BaseModel):
    """Frozen collection used by synthetic filing fixtures."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: str
    casillas: tuple[StaticCasillaSchema, ...]

    def get(self, casilla_id: str) -> StaticCasillaSchema | None:
        """Return the casilla schema for ``casilla_id`` or ``None``."""
        for casilla in self.casillas:
            if casilla.id == casilla_id:
                return casilla
        return None

    def all(self) -> Sequence[StaticCasillaSchema]:
        """Return every casilla in declaration order."""
        return self.casillas

    def __iter__(self):  # type: ignore[override]
        return iter(self.casillas)


class StaticCasillaSchemaProvider(BaseModel):
    """Frozen provider for synthetic fixture schemas."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    collections: dict[str, StaticCasillaCollection]

    def get_collection(self, modelo: str) -> StaticCasillaCollection:
        """Return the synthetic collection registered for ``modelo``."""
        return self.collections[modelo]


def _base(id_: str, description: str, *, defaulted: bool = True) -> StaticCasillaSchema:
    return StaticCasillaSchema(
        id=id_,
        value_type="decimal",
        required=True,
        min_value=0,
        default=Decimal("0") if defaulted else None,
        description=description,
    )


def _rate(id_: str, rate: Decimal, description: str) -> StaticCasillaSchema:
    return StaticCasillaSchema(
        id=id_,
        value_type="decimal",
        required=False,
        default=rate,
        description=description,
    )


def _formula(id_: str, inputs: tuple[str, ...], description: str) -> StaticCasillaSchema:
    return StaticCasillaSchema(
        id=id_,
        value_type="decimal",
        required=False,
        formula_inputs=inputs,
        description=description,
    )


def _quarterly_sum(id_: str, description: str) -> StaticCasillaSchema:
    return StaticCasillaSchema(
        id=id_,
        value_type="decimal",
        required=False,
        default=Decimal("0"),
        description=description,
    )


MODELO_130_SCHEMA = StaticCasillaCollection(
    schema_version=SCHEMA_VERSION_DEFAULT,
    casillas=(
        StaticCasillaSchema(id="01", value_type="decimal", required=True, min_value=0, description="Ingresos"),
        StaticCasillaSchema(id="02", value_type="decimal", required=True, min_value=0, description="Gastos"),
        StaticCasillaSchema(id="03", value_type="decimal", formula_inputs=("01", "02"), description="01 - 02"),
        StaticCasillaSchema(id="04", value_type="decimal", formula_inputs=("03",), description="20 percent of 03"),
        StaticCasillaSchema(
            id="05",
            value_type="decimal",
            required=True,
            min_value=0,
            default=Decimal("0"),
            description="Retenciones",
        ),
        StaticCasillaSchema(
            id="06",
            value_type="decimal",
            required=True,
            min_value=0,
            default=Decimal("0"),
            description="Previous period payments",
        ),
        StaticCasillaSchema(
            id="07",
            value_type="decimal",
            formula_inputs=("04", "05", "06"),
            min_value=0,
            description="max(0, 04 - 05 - 06)",
        ),
        StaticCasillaSchema(
            id="08",
            value_type="decimal",
            required=True,
            min_value=0,
            default=Decimal("0"),
            description="Agricultural income volume",
        ),
        StaticCasillaSchema(id="09", value_type="decimal", formula_inputs=("08",), description="2 percent of 08"),
        StaticCasillaSchema(
            id="10",
            value_type="decimal",
            required=True,
            min_value=0,
            default=Decimal("0"),
            description="Agricultural retentions",
        ),
        StaticCasillaSchema(id="11", value_type="decimal", formula_inputs=("09", "10"), description="09 - 10"),
        StaticCasillaSchema(
            id="12",
            value_type="decimal",
            formula_inputs=("07", "11"),
            min_value=0,
            description="max(0, 07 + 11)",
        ),
        StaticCasillaSchema(
            id="13",
            value_type="decimal",
            required=True,
            min_value=0,
            default=Decimal("0"),
            description="Quota deduction reduction",
        ),
        StaticCasillaSchema(id="14", value_type="decimal", formula_inputs=("12", "13"), description="12 - 13"),
        StaticCasillaSchema(
            id="15",
            value_type="decimal",
            required=True,
            min_value=0,
            default=Decimal("0"),
            description="Home acquisition deduction",
        ),
        StaticCasillaSchema(
            id="16",
            value_type="decimal",
            required=True,
            min_value=0,
            default=Decimal("0"),
            description="Prior negative quarters",
        ),
        StaticCasillaSchema(
            id="17",
            value_type="decimal",
            formula_inputs=("14", "15", "16"),
            description="14 - 15 - 16",
        ),
        StaticCasillaSchema(
            id="18",
            value_type="decimal",
            required=True,
            min_value=0,
            default=Decimal("0"),
            description="Complementaria previous payment",
        ),
        StaticCasillaSchema(id="19", value_type="decimal", formula_inputs=("17", "18"), description="17 - 18"),
    ),
)


MODELO_303_SCHEMA = StaticCasillaCollection(
    schema_version=SCHEMA_VERSION_DEFAULT,
    casillas=(
        _base("01", "Base 4 percent"),
        _rate("02", Decimal("4"), "Rate 4 percent"),
        _formula("03", ("01",), "01 x 0.04"),
        _base("04", "Base 10 percent"),
        _rate("05", Decimal("10"), "Rate 10 percent"),
        _formula("06", ("04",), "04 x 0.10"),
        _base("07", "Base 21 percent", defaulted=False),
        _rate("08", Decimal("21"), "Rate 21 percent"),
        _formula("09", ("07",), "07 x 0.21"),
        _base("28", "Deductible current domestic base"),
        _base("29", "Deductible current domestic quota"),
        _base("30", "Deductible investment domestic base"),
        _base("31", "Deductible investment domestic quota"),
        _base("32", "Import current goods base"),
        _base("33", "Import current goods quota"),
        _base("34", "Import investment goods base"),
        _base("35", "Import investment goods quota"),
        _base("36", "Intra-community current acquisitions base"),
        _base("37", "Intra-community current acquisitions quota"),
        _base("38", "Intra-community investment acquisitions base"),
        _base("39", "Intra-community investment acquisitions quota"),
        _base("40", "Deduction rectification"),
        _base("41", "Special regime compensation"),
        _base("42", "Investment goods adjustment"),
        _base("43", "Prorrata adjustment"),
        _formula("44", ("29", "31", "33", "35", "37", "39", "40", "41", "42", "43"), "Total deductible"),
        _formula("45", ("03", "06", "09", "44"), "General regime result"),
        _formula("64", ("45",), "Result sum"),
        StaticCasillaSchema(
            id="65",
            value_type="decimal",
            required=False,
            default=Decimal("100"),
            min_value=0,
            max_value=100,
            description="State administration percentage",
        ),
        StaticCasillaSchema(
            id="67",
            value_type="decimal",
            required=False,
            default=Decimal("0"),
            min_value=0,
            description="Prior compensation quotas",
        ),
        _formula("66", ("64", "65"), "64 x 65 / 100"),
        _formula("69", ("66", "67"), "66 - 67"),
        _formula("71", ("69",), "Self-assessment result"),
    ),
)


MODELO_390_SCHEMA = StaticCasillaCollection(
    schema_version=SCHEMA_VERSION_DEFAULT,
    casillas=(
        StaticCasillaSchema(
            id="01",
            value_type="int",
            required=True,
            min_value=2000,
            max_value=2100,
            description="Exercise year",
        ),
        _quarterly_sum("100", "Annual base at 4 percent"),
        _quarterly_sum("101", "Annual quota at 4 percent"),
        _quarterly_sum("104", "Annual base at 10 percent"),
        _quarterly_sum("105", "Annual quota at 10 percent"),
        _quarterly_sum("108", "Annual base at 21 percent"),
        _quarterly_sum("109", "Annual quota at 21 percent"),
        _quarterly_sum("190", "Annual current domestic base"),
        _quarterly_sum("191", "Annual current domestic quota"),
        _quarterly_sum("192", "Annual investment domestic base"),
        _quarterly_sum("193", "Annual investment domestic quota"),
        _formula("84", ("101", "105", "109"), "101 + 105 + 109"),
        _formula("85", ("191", "193"), "191 + 193"),
        _formula("86", ("84", "85"), "84 - 85"),
        _formula("95", ("86",), "86"),
    ),
)


__all__ = [
    "MODELO_130_SCHEMA",
    "MODELO_303_SCHEMA",
    "MODELO_390_SCHEMA",
    "CasillaSource",
    "StaticCasillaCollection",
    "StaticCasillaSchema",
    "StaticCasillaSchemaProvider",
]
