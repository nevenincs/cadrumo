"""Hand-curated synthetic casilla schema for the Modelo 130 PoC.

This module exists because the real casilla DB (#23) and the
formula AST extractor (#9) are not on ``main`` yet. The shape
defined here matches the :class:`aeat.filing._protocols.CasillaSchema`
Protocol so that swapping in the real upstream subpackages later
is a search-replace on the import lines, not a rewrite of the
builder.

The casilla numbering is illustrative and intentionally
simplified — the production builder will read its schema from
the casilla DB once that subpackage lands.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .._schema import SCHEMA_VERSION_DEFAULT


class StaticCasillaSchema(BaseModel):
    """A frozen, strict pydantic record describing one casilla.

    Conforms structurally to
    :class:`aeat.filing._protocols.CasillaSchema`.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    id: str
    value_type: str
    required: bool = False
    formula_inputs: tuple[str, ...] = Field(default_factory=tuple)
    min_value: float | int | None = None
    max_value: float | int | None = None
    default: Decimal | int | str | bool | None = None
    description: str = ""


class StaticCasillaCollection(BaseModel):
    """A frozen collection of :class:`StaticCasillaSchema` records.

    Conforms structurally to
    :class:`aeat.filing._protocols.CasillaCollection`.
    """

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
        """Return every casilla in this collection in declaration order."""
        return self.casillas

    def __iter__(self):  # type: ignore[override]
        return iter(self.casillas)


# Synthetic-but-plausible Modelo 130 casilla schema for the PoC.
MODELO_130_SCHEMA = StaticCasillaCollection(
    schema_version=SCHEMA_VERSION_DEFAULT,
    casillas=(
        StaticCasillaSchema(
            id="01",
            value_type="decimal",
            required=True,
            min_value=0,
            description="Ingresos computables del período",
        ),
        StaticCasillaSchema(
            id="02",
            value_type="decimal",
            required=True,
            min_value=0,
            description="Gastos deducibles del período",
        ),
        StaticCasillaSchema(
            id="03",
            value_type="decimal",
            formula_inputs=("01", "02"),
            description="Rendimiento neto = casilla 01 - casilla 02",
        ),
        StaticCasillaSchema(
            id="04",
            value_type="decimal",
            formula_inputs=("03",),
            description="Pago fraccionado bruto = 20% de la casilla 03",
        ),
        StaticCasillaSchema(
            id="05",
            value_type="decimal",
            required=True,
            min_value=0,
            default=Decimal("0"),
            description="Retenciones soportadas en el período",
        ),
        StaticCasillaSchema(
            id="06",
            value_type="decimal",
            required=True,
            min_value=0,
            default=Decimal("0"),
            description="Pagos fraccionados de períodos anteriores",
        ),
        StaticCasillaSchema(
            id="07",
            value_type="decimal",
            formula_inputs=("04", "05", "06"),
            min_value=0,
            description="Resultado a ingresar = max(0, 04 - 05 - 06)",
        ),
    ),
)


class StaticCasillaSchemaProvider(BaseModel):
    """A frozen :class:`CasillaSchemaProvider` for the PoC.

    Maps a small set of modelo IDs to baked-in casilla
    collections.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    collections: dict[str, StaticCasillaCollection]

    def get_collection(self, modelo: str) -> StaticCasillaCollection:
        """Return the casilla collection registered for ``modelo``.

        Raises:
            KeyError: When the modelo has no registered collection.
        """
        return self.collections[modelo]


def default_schema_provider() -> StaticCasillaSchemaProvider:
    """Return a provider seeded with the synthetic Modelo 130 schema."""
    return StaticCasillaSchemaProvider(collections={"130": MODELO_130_SCHEMA})
