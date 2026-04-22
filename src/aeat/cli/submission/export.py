"""``aeat submission export`` — produce an AEAT-importable fichero-BOE file.

EPIC #201 C3c (wave 81). Kent's happy path for self-filing:

    produce (ruleset engine) → review → approve → **export** → self-upload

This command reads a draft JSON, selects the per-modelo schema, and
writes a byte-exact fichero-BOE file ready to upload to the AEAT
portal's "importar datos" surface.

Gating per EPIC #201 C3i (``FilingDraftStatus.APPROVED``) is deferred
until the draft-status lifecycle lands. Until then, the command
refuses any draft whose CLI ``status`` field is explicitly
``"rejected"`` or ``"superseded"``; otherwise it produces output
with a prominent BORRADOR banner in the console.

Wave 92 adds Modelo 303 2024 via the multi-segment envelope path;
the schema registry now carries a per-modelo CLI header builder and
a dispatch tag so single-record (130) and envelope (303) filings
share the same driver.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Literal

import typer
from rich.console import Console

from ...submission import DraftStatus
from ...submission._formats import (
    modelo_130_2024,
    modelo_130_2025,
    modelo_303_2024,
    modelo_303_2025,
)
from ...submission._formats._serialise import serialise, serialise_envelope
from ._helpers import load_draft

_CONSOLE = Console()

_NIF_RE = re.compile(r"^[A-Z0-9]{9}$")


@dataclass(frozen=True, slots=True)
class _CliInputs:
    """Canonical CLI-supplied filing-identification inputs."""

    ejercicio: str
    periodo: str
    nif: str
    apellidos: str
    nombre: str
    tipo_declaracion: str


@dataclass(frozen=True, slots=True)
class _SchemaEntry:
    """Registry entry pairing a schema module with its CLI adapters.

    ``kind`` dispatches the driver to either :func:`serialise` (single
    fixed-width record, Modelo 130 style) or :func:`serialise_envelope`
    (multi-segment XML-wrapped pages, Modelo 303 / 390 style).
    """

    module: ModuleType
    kind: Literal["record", "envelope"]
    build_headers: Callable[[_CliInputs], dict[str, str]]


def _build_130_headers(inputs: _CliInputs) -> dict[str, str]:
    """Modelo 130 uses the canonical CLI header names 1:1."""
    return {
        "EJERCICIO": inputs.ejercicio,
        "PERIODO": inputs.periodo,
        "NIF_DECLARANTE": inputs.nif,
        "APELLIDOS": inputs.apellidos,
        "NOMBRE": inputs.nombre,
        "TIPO_DECLARACION": inputs.tipo_declaracion,
    }


def _build_303_headers(inputs: _CliInputs) -> dict[str, str]:
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
    _admin = " "
    return {
        # Envelope header (DP30300).
        "DP30300_F004_EJERCICIO_DE_DEVENGO": inputs.ejercicio,
        "DP30300_F008_RESERVADO_PARA_LA_ADMINISTRA": _admin,
        "DP30300_F009_VERSI_N_DEL_PROGRAMA": _admin,
        "DP30300_F010_RESERVADO_PARA_LA_ADMINISTRA": _admin,
        "DP30300_F011_NIF_EMPRESA_DESARROLLO": _admin,
        "DP30300_F012_RESERVADO_PARA_LA_ADMINISTRA": _admin,
        # Per-page identification (DP30301).
        "DP30301_F006_TIPO_DECLARACI_N": inputs.tipo_declaracion,
        "DP30301_F007_IDENTIFICACI_N_NIF": inputs.nif,
        "DP30301_F008_IDENTIFICACI_N_APELLIDOS_Y_N": apellidos_y_nombre,
        "DP30301_F009_DEVENGO_EJERCICIO": inputs.ejercicio,
        "DP30301_F010_DEVENGO_PER_ODO": inputs.periodo,
    }


_SCHEMA_REGISTRY: dict[tuple[str, str], _SchemaEntry] = {
    ("130", "2024"): _SchemaEntry(modelo_130_2024, "record", _build_130_headers),
    ("130", "2025"): _SchemaEntry(modelo_130_2025, "record", _build_130_headers),
    ("303", "2024"): _SchemaEntry(modelo_303_2024, "envelope", _build_303_headers),
    ("303", "2025"): _SchemaEntry(modelo_303_2025, "envelope", _build_303_headers),
}


def _period_token(period: str) -> str:
    """Normalise a draft's ``period`` to the fichero-BOE ``PERIODO`` token.

    AEAT accepts ``"1T"..."4T"`` (quarterly) or ``"01".."12"`` (monthly).
    The draft's period field carries an ISO-ish form like ``"2024Q1"``
    or ``"2024-Q1"``; extract the trimester suffix.
    """
    upper = period.upper()
    m = re.search(r"Q([1-4])", upper)
    if m:
        return f"{m.group(1)}T"
    # Already a canonical BOE token?
    if re.match(r"^[1-4]T$", upper) or re.match(r"^(0[1-9]|1[0-2])$", upper):
        return upper
    raise typer.BadParameter(f"cannot translate period {period!r} into a fichero-BOE token (expected 1T-4T or 01-12)")


def _ejercicio_token(period: str) -> str:
    """Extract the 4-digit ejercicio from a draft period."""
    m = re.match(r"^(\d{4})", period)
    if not m:
        raise typer.BadParameter(f"cannot extract ejercicio from period {period!r}; expected YYYY prefix")
    return m.group(1)


def export_cmd(
    draft_path: Path = typer.Argument(..., help="Path to a CLI-format draft JSON."),
    output_dir: Path = typer.Option(
        Path("var/exports"),
        "--output-dir",
        "-o",
        help="Directory where the exported fichero-BOE file is written.",
    ),
    nombre: str = typer.Option(..., "--nombre", help="Declarant first name (Kent's NOMBRE field)."),
    apellidos: str = typer.Option(..., "--apellidos", help="Declarant surnames (Kent's APELLIDOS field)."),
    tipo_declaracion: str = typer.Option(
        "I", "--tipo", help="Declaration type: I (ingreso), N (negativa), U (domiciliación única), etc."
    ),
) -> None:
    """Export the filing draft to an AEAT-importable fichero-BOE file.

    Raises :class:`typer.Exit(code=2)` for unsupported modelos (303/390
    still pending architectural work). Raises ``code=3`` for draft-
    status rejection.
    """
    draft = load_draft(draft_path)

    # The DraftStatus enum exposes DRAFT / INCOMPLETE / READY_TO_SUBMIT
    # today (see `aeat.submission._protocols.DraftStatus`). Export refuses
    # INCOMPLETE outright (validation not yet passed). DRAFT exports emit
    # a BORRADOR banner; READY_TO_SUBMIT is the approved-enough state
    # until C3i (FilingDraftStatus.APPROVED) lands.
    status = draft.status if isinstance(draft.status, DraftStatus) else None
    if status is DraftStatus.INCOMPLETE:
        _CONSOLE.print(
            f"[red]export REFUSED:[/red] draft {draft.draft_id} status is "
            f"INCOMPLETE; finish validation before exporting."
        )
        raise typer.Exit(code=3)

    ejercicio = _ejercicio_token(draft.period)
    periodo = _period_token(draft.period)
    key = (draft.modelo, ejercicio)
    entry = _SCHEMA_REGISTRY.get(key)
    if entry is None:
        _CONSOLE.print(
            f"[red]export UNSUPPORTED:[/red] modelo {draft.modelo} "
            f"ejercicio {ejercicio} has no fichero-BOE schema yet. "
            f"Available: {sorted(_SCHEMA_REGISTRY.keys())}"
        )
        raise typer.Exit(code=2)

    # Validate NIF format early.
    nif = draft.profile_tax_id.upper()
    if not _NIF_RE.match(nif):
        raise typer.BadParameter(f"NIF {nif!r} does not match the 9-character AEAT pattern")

    # Translate draft values to Decimal casilla_values. The protocol
    # type permits either a Mapping or an Iterable; CLI drafts always
    # supply a str->str dict (see `_CliDraftLoader`).
    draft_values = draft.values
    if not isinstance(draft_values, Mapping):
        raise typer.BadParameter("draft values must be a Mapping[str, str] for CLI export")
    casilla_values: dict[str, Decimal] = {}
    for cid, raw in draft_values.items():
        if not isinstance(cid, str) or not isinstance(raw, str):
            raise typer.BadParameter(
                f"casilla mapping must use str keys and str values; "
                f"got {type(cid).__name__}={cid!r}, {type(raw).__name__}={raw!r}"
            )
        try:
            casilla_values[cid] = Decimal(raw)
        except Exception as exc:
            raise typer.BadParameter(f"casilla {cid!r} value {raw!r} is not a valid Decimal") from exc

    inputs = _CliInputs(
        ejercicio=ejercicio,
        periodo=periodo,
        nif=nif,
        apellidos=apellidos,
        nombre=nombre,
        tipo_declaracion=tipo_declaracion.upper(),
    )
    headers = entry.build_headers(inputs)

    if entry.kind == "record":
        payload = serialise(
            casilla_values=casilla_values,
            headers=headers,
            specs=entry.module._RECORD_SPECS,
            encoding=entry.module.ENCODING,
            total_length=entry.module.RECORD_LENGTH,
            required_field_ids=entry.module.REQUIRED_HEADER_FIELDS,
        )
    else:
        payload = serialise_envelope(
            casilla_values=casilla_values,
            headers=headers,
            segments=entry.module.ENVELOPE,
            encoding=entry.module.ENCODING,
            required_field_ids=entry.module.REQUIRED_HEADER_FIELDS,
        )

    # AEAT filename convention per dr130.09.pdf: {NIF}{EJERCICIO}{PERIODO}.{modelo}
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{nif}{ejercicio}{periodo}.{draft.modelo}"
    output_path = output_dir / filename
    output_path.write_bytes(payload)

    _CONSOLE.print(
        f"[yellow]BORRADOR — SOLO REFERENCIA[/yellow]\n"
        f"[green]export OK[/green] modelo={draft.modelo} ejercicio={ejercicio} "
        f"periodo={periodo}\n"
        f"wrote {len(payload)} bytes to [bold]{output_path}[/bold]\n"
        f"Upload manually via https://sede.agenciatributaria.gob.es "
        f"'importar datos' surface."
    )
