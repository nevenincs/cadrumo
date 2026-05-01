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
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .._schema import SCHEMA_VERSION_DEFAULT


class CasillaSource(BaseModel):
    """Provenance citation for one casilla (#305 cluster B).

    Every casilla SHOULD carry at least one source citation so the
    legal authority behind the schema is auditable. Phase-1 introduces
    the field as optional (``tuple[CasillaSource, ...] = ()``) to
    preserve backwards compatibility; cluster B phase-2 tightens the
    invariant to ``≥1 entry`` per casilla.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    kind: Literal["boe", "manual", "interactive_form_xml", "printed_form_pdf"]
    citation: str = Field(min_length=1)
    url: str | None = None
    retrieved_at: date | None = None
    snapshot_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class StaticCasillaSchema(BaseModel):
    """A frozen, strict pydantic record describing one casilla.

    Conforms structurally to
    :class:`aeat.filing._protocols.CasillaSchema`. Provenance fields
    (``sources``, ``valid_from``, ``valid_to``) are optional today and
    tighten in cluster-B phase-2 as the corpus completes.
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
    sources: tuple[CasillaSource, ...] = Field(default_factory=tuple)
    valid_from: date | None = None
    valid_to: date | None = None


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
        # Apartado II — actividad agrícola / ganadera / forestal / pesquera.
        # Added in #305 cluster B phase 2 to close the schema/ruleset gap
        # that silently orphaned computed casillas 09 / 11 / 12 / 14 / 17 / 19.
        StaticCasillaSchema(
            id="08",
            value_type="decimal",
            required=True,
            min_value=0,
            default=Decimal("0"),
            description="Volumen de ingresos del trimestre — actividades agrícolas/ganaderas/pesqueras",
        ),
        StaticCasillaSchema(
            id="09",
            value_type="decimal",
            formula_inputs=("08",),
            description="Pago fraccionado agraria = 2% de la casilla 08",
        ),
        StaticCasillaSchema(
            id="10",
            value_type="decimal",
            required=True,
            min_value=0,
            default=Decimal("0"),
            description="Retenciones e ingresos a cuenta en actividades agrarias",
        ),
        StaticCasillaSchema(
            id="11",
            value_type="decimal",
            formula_inputs=("09", "10"),
            description="Resultado apartado II = casilla 09 - casilla 10",
        ),
        # Apartado III — suma parcial + minoración de deducción art. 110.3.c LIRPF.
        StaticCasillaSchema(
            id="12",
            value_type="decimal",
            formula_inputs=("07", "11"),
            min_value=0,
            description="Suma parcial = max(0, casilla 07 + casilla 11)",
        ),
        StaticCasillaSchema(
            id="13",
            value_type="decimal",
            required=True,
            min_value=0,
            default=Decimal("0"),
            description="Minoración por deducción de la cuota (art. 110.3.c LIRPF)",
        ),
        StaticCasillaSchema(
            id="14",
            value_type="decimal",
            formula_inputs=("12", "13"),
            description="Resultado tras minoración = casilla 12 - casilla 13",
        ),
        # Apartado IV — deducciones por vivienda habitual / familia numerosa.
        StaticCasillaSchema(
            id="15",
            value_type="decimal",
            required=True,
            min_value=0,
            default=Decimal("0"),
            description="Deducción por adquisición o rehabilitación de vivienda habitual",
        ),
        StaticCasillaSchema(
            id="16",
            value_type="decimal",
            required=True,
            min_value=0,
            default=Decimal("0"),
            description="Resultados negativos de trimestres anteriores del mismo ejercicio",
        ),
        StaticCasillaSchema(
            id="17",
            value_type="decimal",
            formula_inputs=("14", "15", "16"),
            description="Diferencia = casilla 14 - casilla 15 - casilla 16",
        ),
        # Apartado V — ingreso complementario / domiciliación.
        StaticCasillaSchema(
            id="18",
            value_type="decimal",
            required=True,
            min_value=0,
            default=Decimal("0"),
            description="Ingreso efectuado en declaración anterior (complementaria)",
        ),
        StaticCasillaSchema(
            id="19",
            value_type="decimal",
            formula_inputs=("17", "18"),
            description="Resultado final a ingresar = casilla 17 - casilla 18",
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
