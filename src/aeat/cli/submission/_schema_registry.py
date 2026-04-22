"""Shared fichero-BOE schema registry for ``aeat submission`` commands.

EPIC #305 wave 97. Factored out of :mod:`export` so that :mod:`verify`
(and any future siblings like ``aeat submission diff``) can share the
same ``(modelo, ejercicio) → schema module + CLI adapters`` dispatch
without reaching across files into private underscore-prefixed names.

Registry entries are immutable ``dataclass(frozen=True)`` pairs that
couple a schema module with:

- ``kind``: ``"record"`` (single fixed-width, Modelo 130 style) or
  ``"envelope"`` (multi-segment XML-wrapped, Modelo 303 / 390 style).
- ``build_headers``: translates the canonical :class:`CliInputs` into
  the per-schema header dict keyed by field_id.

Adding a new modelo means registering its module here, plus a header
builder if the schema's field IDs diverge from the 130-style canonical
names.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import ModuleType
from typing import Literal

from ...submission._formats import (
    modelo_130_2024,
    modelo_130_2025,
    modelo_303_2024,
    modelo_303_2025,
)


@dataclass(frozen=True, slots=True)
class CliInputs:
    """Canonical CLI-supplied filing-identification inputs.

    ``iban`` / ``swift`` are only consulted for modelos with a SEPA
    devolución page (e.g., Modelo 303 DP303DID) and only when the
    filing is a devolución (``tipo_declaracion='D'``). Both default
    to ``None`` so the vast majority of ingreso / negativa filings
    never have to populate them.
    """

    ejercicio: str
    periodo: str
    nif: str
    apellidos: str
    nombre: str
    tipo_declaracion: str
    iban: str | None = None
    swift: str | None = None


@dataclass(frozen=True, slots=True)
class SchemaEntry:
    """Registry entry pairing a schema module with its CLI adapters.

    ``kind`` dispatches the driver to either :func:`serialise` (single
    fixed-width record) or :func:`serialise_envelope` (multi-segment
    XML-wrapped pages).
    """

    module: ModuleType
    kind: Literal["record", "envelope"]
    build_headers: Callable[[CliInputs], dict[str, str]]


def build_130_headers(inputs: CliInputs) -> dict[str, str]:
    """Modelo 130 uses the canonical CLI header names 1:1."""
    return {
        "EJERCICIO": inputs.ejercicio,
        "PERIODO": inputs.periodo,
        "NIF_DECLARANTE": inputs.nif,
        "APELLIDOS": inputs.apellidos,
        "NOMBRE": inputs.nombre,
        "TIPO_DECLARACION": inputs.tipo_declaracion,
    }


def build_303_headers(inputs: CliInputs) -> dict[str, str]:
    """Modelo 303 keys headers by the DR303 field IDs.

    DP30301 carries the per-page identification fields; DP30300 is
    the envelope wrapper with AEAT-reserved slots we leave blank.
    APELLIDOS and NOMBRE share a single 80-byte field (``APELLIDOS
    NOMBRE`` convention).
    """
    apellidos_y_nombre = (f"{inputs.apellidos} {inputs.nombre}").strip()
    # AEAT-reserved and developer-identifier slots pass a single space
    # so the serialiser space-pads to field length while the required-
    # field check (which rejects truly empty strings) still succeeds.
    admin = " "
    headers: dict[str, str] = {
        # Envelope header (DP30300).
        "DP30300_F004_EJERCICIO_DE_DEVENGO": inputs.ejercicio,
        "DP30300_F008_RESERVADO_PARA_LA_ADMINISTRA": admin,
        "DP30300_F009_VERSI_N_DEL_PROGRAMA": admin,
        "DP30300_F010_RESERVADO_PARA_LA_ADMINISTRA": admin,
        "DP30300_F011_NIF_EMPRESA_DESARROLLO": admin,
        "DP30300_F012_RESERVADO_PARA_LA_ADMINISTRA": admin,
        # Per-page identification (DP30301).
        "DP30301_F006_TIPO_DECLARACI_N": inputs.tipo_declaracion,
        "DP30301_F007_IDENTIFICACI_N_NIF": inputs.nif,
        "DP30301_F008_IDENTIFICACI_N_APELLIDOS_Y_N": apellidos_y_nombre,
        "DP30301_F009_DEVENGO_EJERCICIO": inputs.ejercicio,
        "DP30301_F010_DEVENGO_PER_ODO": inputs.periodo,
    }
    # SEPA devolución page (DP303DID) — only stamped when Kent supplies
    # banking details. For ingreso / negativa filings these slots stay
    # space-padded via the serialiser default.
    if inputs.iban:
        headers["DP303DID_F006_DOMICILIACI_N_DEVOLUCI_N_IBA"] = inputs.iban
        headers["DP303DID_F011_DEVOLUCI_N_MARCA_SEPA"] = "1"
    if inputs.swift:
        headers["DP303DID_F005_DEVOLUCI_N_SWIFT_BIC"] = inputs.swift
    return headers


SCHEMA_REGISTRY: dict[tuple[str, str], SchemaEntry] = {
    ("130", "2024"): SchemaEntry(modelo_130_2024, "record", build_130_headers),
    ("130", "2025"): SchemaEntry(modelo_130_2025, "record", build_130_headers),
    ("303", "2024"): SchemaEntry(modelo_303_2024, "envelope", build_303_headers),
    ("303", "2025"): SchemaEntry(modelo_303_2025, "envelope", build_303_headers),
}


__all__ = [
    "SCHEMA_REGISTRY",
    "CliInputs",
    "SchemaEntry",
    "build_130_headers",
    "build_303_headers",
]
