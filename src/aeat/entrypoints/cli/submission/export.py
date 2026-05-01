"""``aeat submission export`` — produce an AEAT-importable fichero-BOE file.

EPIC #201 C3c. Kent's happy path for self-filing:

    produce (ruleset engine) → review → approve → **export** → self-upload

This command reads a draft JSON, selects the per-modelo schema, and
writes a byte-exact fichero-BOE file ready to upload to the AEAT
portal's "importar datos" surface.

Gating per EPIC #201 C3i (``FilingDraftStatus.APPROVED``) is deferred
until the draft-status lifecycle lands. Until then, the command
refuses any draft whose CLI ``status`` field is explicitly
``"rejected"`` or ``"superseded"``; otherwise it produces output
with a prominent BORRADOR banner in the console.

Modelo 303 2024 via the multi-segment envelope path;
the schema registry now carries a per-modelo CLI header builder and
a dispatch tag so single-record (130) and envelope (303) filings
share the same driver.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import typer
from rich.console import Console

from ....adapters.outbound.aeat.export import DraftStatus
from ....adapters.outbound.aeat.export._formats._serialise import serialise, serialise_envelope
from ....core.identity import validate_spanish_tax_id
from ._helpers import load_draft
from ._schema_registry import SCHEMA_REGISTRY, CliInputs, validate_iban_flag, validate_swift_flag

_CONSOLE = Console()


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
    nombre: str = typer.Option(
        ...,
        "--nombre",
        help=(
            "Declarant first name (NOMBRE field). AEAT convention is upper-case "
            "but the CLI preserves your casing — type as it should appear on the filing."
        ),
    ),
    apellidos: str = typer.Option(
        ...,
        "--apellidos",
        help=(
            "Declarant surnames (APELLIDOS field). AEAT convention is upper-case "
            "but the CLI preserves your casing — type as it should appear on the filing."
        ),
    ),
    tipo_declaracion: str = typer.Option(
        "I", "--tipo", help="Declaration type: I (ingreso), N (negativa), D (devolución), U (domiciliación única), etc."
    ),
    iban: str | None = typer.Option(
        None,
        "--iban",
        help=(
            "IBAN for SEPA devolución (tipo=D). Stamped into DP303DID "
            "for envelope modelos that carry a direct-debit page."
        ),
        callback=validate_iban_flag,
    ),
    swift: str | None = typer.Option(
        None,
        "--swift",
        help="SWIFT/BIC for SEPA devolución (tipo=D). Optional for Spanish IBANs.",
        callback=validate_swift_flag,
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
    if status is DraftStatus.VALIDATED:
        _CONSOLE.print(
            f"[red]export REFUSED:[/red] draft {draft.draft_id} status is "
            f"VALIDATED; approve the draft before exporting."
        )
        raise typer.Exit(code=3)

    ejercicio = _ejercicio_token(draft.period)
    periodo = _period_token(draft.period)
    key = (draft.modelo, ejercicio)
    entry = SCHEMA_REGISTRY.get(key)
    if entry is None:
        _CONSOLE.print(
            f"[red]export UNSUPPORTED:[/red] modelo {draft.modelo} "
            f"ejercicio {ejercicio} has no fichero-BOE schema yet. "
            f"Available: {sorted(SCHEMA_REGISTRY.keys())}"
        )
        raise typer.Exit(code=2)

    # Validate NIF format and checksum early. validate_spanish_tax_id
    # covers DNI (8 digits + TRWAGMYFPDXBNJZSQVHLCKE letter), NIE
    # (X/Y/Z prefix → 0/1/2 before NIF rule), and CIF (entity id);
    # malformed strings or bad check-letters surface here before any
    # bytes hit disk.
    try:
        nif = validate_spanish_tax_id(draft.profile_tax_id)
    except ValueError as exc:
        raise typer.BadParameter(
            f"draft NIF {draft.profile_tax_id!r} failed the AEAT check-letter "
            f"algorithm: {exc}. Kent cannot upload a filing whose NIF fails "
            f"AEAT's validation — fix the draft and re-export."
        ) from exc

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

    tipo_upper = tipo_declaracion.upper()
    if tipo_upper == "D" and not iban:
        _CONSOLE.print(
            "[red]export REFUSED:[/red] tipo=D (devolución) requires --iban so AEAT "
            "can refund the cuota into Kent's account. Add --iban (and optionally --swift) "
            "or use tipo=I / tipo=N for filings without a refund."
        )
        raise typer.Exit(code=3)
    inputs = CliInputs(
        ejercicio=ejercicio,
        periodo=periodo,
        nif=nif,
        apellidos=apellidos,
        nombre=nombre,
        tipo_declaracion=tipo_upper,
        iban=iban,
        swift=swift,
    )
    headers = entry.build_headers(inputs)

    if entry.kind == "record":
        payload = serialise(
            casilla_values=casilla_values,
            headers=headers,
            specs=entry.module.RECORD_SPECS,
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
