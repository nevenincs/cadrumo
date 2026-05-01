"""Shared fichero-BOE schema registry for ``aeat submission`` commands.

Centralises the ``(modelo, ejercicio) -> schema module + CLI adapters``
dispatch so that :mod:`.export`, :mod:`.verify`, :mod:`.diff`, and
:mod:`.schemas` all share the same source of truth without reaching
across files into private underscore-prefixed names.

Registry entries are immutable :class:`SchemaEntry` instances that
couple a schema module with:

- ``kind``: ``"record"`` (single fixed-width, Modelo 130 style) or
  ``"envelope"`` (multi-segment XML-wrapped, Modelo 303 / 390 style).
- ``build_headers``: translates the canonical :class:`CliInputs` into
  the per-schema header dict keyed by field id.

Adding a new modelo means registering its module here, plus a header
builder if the schema's field IDs diverge from the 130-style canonical
names. The flag-validator helpers (:func:`validate_modelo_flag`,
:func:`validate_ejercicio_flag`, :func:`validate_iban_flag`,
:func:`validate_swift_flag`) round out the CLI input boundary.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from types import ModuleType
from typing import Literal

import typer

from ....adapters.outbound.aeat.export._formats import (
    modelo_130_2024,
    modelo_130_2025,
    modelo_303_2024,
    modelo_303_2025,
)


@dataclass(frozen=True, slots=True)
class CliInputs:
    """Canonical CLI-supplied filing-identification inputs.

    ``iban`` and ``swift`` are only consulted for modelos with a SEPA
    devolución page (e.g. Modelo 303 ``DP303DID``) and only when the
    filing is a devolución (``tipo_declaracion='D'``). Both default to
    ``None`` so the vast majority of ingreso and negativa filings never
    have to populate them.

    Attributes:
        ejercicio: Tax year (e.g. ``"2024"``).
        periodo: Period token (``"1T"`` to ``"4T"``, ``"01"`` to
            ``"12"``, or ``"0A"`` for annual).
        nif: Declarant NIF.
        apellidos: Declarant surnames.
        nombre: Declarant first name.
        tipo_declaracion: Declaration type letter (``"I"`` ingreso,
            ``"N"`` negativa, ``"D"`` devolución, etc.).
        iban: Optional IBAN for the SEPA devolución slot.
        swift: Optional SWIFT/BIC for the SEPA devolución slot.
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

    ``kind`` dispatches the driver to either
    :func:`aeat.adapters.outbound.aeat.export._formats._serialise.serialise`
    (single fixed-width record) or
    :func:`aeat.adapters.outbound.aeat.export._formats._serialise.serialise_envelope`
    (multi-segment XML-wrapped pages).

    Attributes:
        module: The schema module exporting ``ENCODING``,
            ``RECORD_LENGTH`` / ``ENVELOPE``, ``RECORD_SPECS``, and
            ``REQUIRED_HEADER_FIELDS``.
        kind: Either ``"record"`` (Modelo 130 style) or ``"envelope"``
            (Modelo 303 / 390 style).
        build_headers: Callable translating :class:`CliInputs` into the
            schema's per-field header dict.
    """

    module: ModuleType
    kind: Literal["record", "envelope"]
    build_headers: Callable[[CliInputs], dict[str, str]]


def build_130_headers(inputs: CliInputs) -> dict[str, str]:
    """Build Modelo 130 header values from the canonical :class:`CliInputs`.

    Modelo 130's field IDs match the canonical CLI header names 1:1, so
    the mapping is direct.

    Args:
        inputs: Canonical CLI inputs.

    Returns:
        Mapping of Modelo 130 field id to string value.
    """
    return {
        "EJERCICIO": inputs.ejercicio,
        "PERIODO": inputs.periodo,
        "NIF_DECLARANTE": inputs.nif,
        "APELLIDOS": inputs.apellidos,
        "NOMBRE": inputs.nombre,
        "TIPO_DECLARACION": inputs.tipo_declaracion,
    }


def build_303_headers(inputs: CliInputs) -> dict[str, str]:
    """Build Modelo 303 header values keyed by the DR303 field IDs.

    ``DP30301`` carries the per-page identification fields; ``DP30300``
    is the envelope wrapper with AEAT-reserved slots that are left
    blank. ``APELLIDOS`` and ``NOMBRE`` share a single 80-byte field
    (``APELLIDOS NOMBRE`` convention).

    Args:
        inputs: Canonical CLI inputs. ``inputs.iban`` and
            ``inputs.swift`` populate the ``DP303DID`` SEPA devolución
            slots when present; otherwise those slots are left to the
            serialiser default (space-padded).

    Returns:
        Mapping of Modelo 303 field id to string value.
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


_MODELO_FLAG_RE = re.compile(r"^\d{3}$")
_EJERCICIO_FLAG_RE = re.compile(r"^\d{4}$")
#: IBAN: ISO-13616 basic shape — 2-letter country + 2 check digits + 11-30
#: alphanumeric BBAN characters, total 15-34. We normalise by removing
#: internal whitespace (Kent may paste "ES91 2100 0418 4502 0005 1332").
_IBAN_FLAG_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")
#: SWIFT/BIC: ISO-9362 — 8 or 11 alphanumeric chars; 4-letter bank, 2-letter
#: country, 2-alphanumeric location, optional 3-char branch.
_SWIFT_FLAG_RE = re.compile(r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$")


def validate_modelo_flag(value: str | None) -> str | None:
    """Typer callback rejecting obviously-malformed ``--modelo`` values.

    Accepts ``None`` unchanged so auto-detection remains possible when
    the flag is omitted. Non-``None`` values must be a 3-digit numeric
    string matching AEAT's canonical modelo numbering (``100``, ``130``,
    ``303``, ``390``, etc.); anything else produces a
    :exc:`typer.BadParameter` with a clean operator-facing message before
    the registry lookup surfaces a generic ``UNSUPPORTED`` error.

    Args:
        value: Raw flag value as supplied by the operator, or ``None``.

    Returns:
        The validated value, or ``None`` when the flag was omitted.

    Raises:
        typer.BadParameter: When ``value`` is not 3 numeric digits.
    """
    if value is None:
        return None
    if not _MODELO_FLAG_RE.match(value):
        raise typer.BadParameter(
            f"--modelo {value!r} must be a 3-digit numeric string "
            "(e.g. 130, 303, 390). AEAT modelo numbers are always three digits."
        )
    return value


def validate_ejercicio_flag(value: str | None) -> str | None:
    """Typer callback rejecting obviously-malformed ``--ejercicio`` values.

    Accepts ``None`` unchanged so filename auto-detection can still fire.
    Non-``None`` values must be a 4-digit numeric year (``2024``,
    ``2025``, ...); letters or short-year forms (e.g. ``24``, ``2k24``)
    fail with a clean message instead of hitting the registry's
    ``UNSUPPORTED`` path.

    Args:
        value: Raw flag value as supplied by the operator, or ``None``.

    Returns:
        The validated value, or ``None`` when the flag was omitted.

    Raises:
        typer.BadParameter: When ``value`` is not 4 numeric digits.
    """
    if value is None:
        return None
    if not _EJERCICIO_FLAG_RE.match(value):
        raise typer.BadParameter(
            f"--ejercicio {value!r} must be a 4-digit year (e.g. 2024, 2025). "
            "Short-year forms (24) or mixed alphanumeric values are not accepted."
        )
    return value


def validate_iban_flag(value: str | None) -> str | None:
    """Typer callback validating ``--iban`` against the ISO-13616 basic shape.

    Operators often copy-paste an IBAN with spaces between 4-char groups
    (e.g. ``"ES91 2100 0418 4502 0005 1332"``); the value is normalised
    by removing whitespace and hyphens before validation, and the
    normalised canonical form (no separators, upper-case) is returned so
    the header builder stamps the clean value into
    ``DP303DID_F006``.

    Does NOT perform the mod-97 check-digit verification (that would
    require the full letter-to-digit expansion and an extra dependency
    on the flag boundary). Shape-only: 2 letters + 2 digits + 11 to 30
    alphanumerics.

    Args:
        value: Raw flag value as supplied by the operator, or ``None``.

    Returns:
        The normalised canonical IBAN, or ``None`` when the flag was
        omitted.

    Raises:
        typer.BadParameter: When ``value`` does not match the ISO-13616
            basic shape.
    """
    if value is None:
        return None
    normalised = value.replace(" ", "").replace("-", "").upper()
    if not _IBAN_FLAG_RE.match(normalised):
        raise typer.BadParameter(
            f"--iban {value!r} does not match the ISO-13616 IBAN shape "
            "(2-letter country, 2 check digits, 11-30 alphanumeric BBAN "
            "chars). Example: ES9121000418450200051332."
        )
    return normalised


def validate_swift_flag(value: str | None) -> str | None:
    """Typer callback validating ``--swift`` against the ISO-9362 BIC shape.

    Whitespace is stripped and the value upper-cased before the shape
    check; the normalised form (8 or 11 alphanumeric characters: 4-letter
    bank, 2-letter country, 2-char location, optional 3-char branch) is
    returned for stamping into the SEPA fields.

    Args:
        value: Raw flag value as supplied by the operator, or ``None``.

    Returns:
        The normalised canonical BIC, or ``None`` when the flag was
        omitted.

    Raises:
        typer.BadParameter: When ``value`` does not match the ISO-9362
            BIC shape.
    """
    if value is None:
        return None
    normalised = value.replace(" ", "").upper()
    if not _SWIFT_FLAG_RE.match(normalised):
        raise typer.BadParameter(
            f"--swift {value!r} does not match the ISO-9362 BIC shape "
            "(8 or 11 alphanumeric characters: 4-letter bank + 2-letter country "
            "+ 2-char location, optional 3-char branch). Example: CAIXESBBXXX."
        )
    return normalised


SCHEMA_REGISTRY: dict[tuple[str, str], SchemaEntry] = {
    ("130", "2024"): SchemaEntry(modelo_130_2024, "record", build_130_headers),
    ("130", "2025"): SchemaEntry(modelo_130_2025, "record", build_130_headers),
    ("303", "2024"): SchemaEntry(modelo_303_2024, "envelope", build_303_headers),
    ("303", "2025"): SchemaEntry(modelo_303_2025, "envelope", build_303_headers),
}
"""Registered ``(modelo, ejercicio) -> :class:`SchemaEntry``` dispatch table."""


__all__ = [
    "SCHEMA_REGISTRY",
    "CliInputs",
    "SchemaEntry",
    "build_130_headers",
    "build_303_headers",
    "validate_ejercicio_flag",
    "validate_iban_flag",
    "validate_modelo_flag",
    "validate_swift_flag",
]
