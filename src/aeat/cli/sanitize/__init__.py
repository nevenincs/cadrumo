"""``aeat sanitize`` sub-app — PDF PII redaction CLI (#239).

Subcommands:

- ``aeat sanitize pdf <input> --mapping <yaml> --output <out>`` —
  apply a TokenMap to a captured PDF and write the sanitised
  result.
- ``aeat sanitize prepare-map <input> --output <yaml>`` — scaffold
  a per-capture mapping YAML by running the existing justificante
  parser; the operator fills in the cleartext locally.
- ``aeat sanitize verify <output> --against <yaml>`` — adversarial
  absence check; exits non-zero if any ``real:`` value leaks into
  the sanitised output.
- ``aeat sanitize check <output>`` — structural-integrity check
  (re-opens with pikepdf, runs the justificante parser).

Every subcommand is strictly read-only on AEAT — no auth, no HTTP,
no env-var reads under ``AEAT_*``. The forbidden-flag guard
mirrors :mod:`aeat.cli.filing._reconcile`: any flag named
``--write`` / ``--submit`` / ``--send`` / ``--enviar`` / ... exits
with code 2 before Typer dispatch.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Annotated

import pikepdf
import typer
import yaml
from pydantic import SecretStr
from rich.console import Console

from ...justificante import JustificanteError, parse_justificante
from ...logging import get_logger
from ...sanitizer import (
    AddressReplacement,
    AlreadySanitizedError,
    ArbitraryReplacement,
    CsvReplacement,
    ExpedienteReplacement,
    IbanReplacement,
    ImporteReplacement,
    NameReplacement,
    NifReplacement,
    NrcReplacement,
    SanitizationError,
    SanitizationResult,
    TokenMap,
    sanitize_pdf,
)

log = get_logger(__name__)

app = typer.Typer(
    name="sanitize",
    help="PDF sanitiser — redact PII for fixture commits (#239).",
    no_args_is_help=True,
)

_CONSOLE = Console()
_ERR_CONSOLE = Console(stderr=True)


# Forbidden flags — parsed before Typer dispatch; any match hard-
# exits with code 2. Same defence-in-depth pattern as
# ``aeat filing reconcile``: the sanitiser never writes to AEAT,
# never submits, never modifies live state. Any flag whose name
# implies mutation is refused.
_FORBIDDEN_FLAGS: tuple[str, ...] = (
    "--write",
    "--submit",
    "--send",
    "--commit",
    "--enviar",
    "--presentar",
    "--firmar",
    "--modificar",
    "--anular",
    "--cancelar",
    "--rechazar",
    "--radicar",
    "--remitir",
)


def reject_forbidden_flags(argv: tuple[str, ...]) -> None:
    """Exit 2 on any write-implying flag before it reaches Typer.

    Args:
        argv: The raw CLI argument tuple to inspect.

    Raises:
        typer.Exit: If any token's head matches a forbidden flag.
    """
    for token in argv:
        head = token.split("=", 1)[0]
        if head in _FORBIDDEN_FLAGS:
            _ERR_CONSOLE.print(
                f"[red]Refused: {head!r} implies an AEAT mutation. "
                "`aeat sanitize` is strictly read-only on AEAT and never writes back.[/red]"
            )
            raise typer.Exit(code=2)


@app.command("pdf", help="Apply a TokenMap to a captured PDF and write the sanitised result.")
def pdf_command(
    ctx: typer.Context,
    input_path: Annotated[Path, typer.Argument(help="Path to the captured source PDF.")],
    mapping_path: Annotated[
        Path,
        typer.Option("--mapping", "-m", help="Path to the per-capture mapping YAML."),
    ],
    output_path: Annotated[
        Path,
        typer.Option("--output", "-o", help="Where to write the sanitised PDF."),
    ],
    report_path: Annotated[
        Path | None,
        typer.Option(
            "--report",
            help="Optional path for the JSON SanitizationResult report (audit log).",
        ),
    ] = None,
    allow_already_sanitized: Annotated[
        bool,
        typer.Option(
            "--allow-already-sanitized",
            help="Bypass the refuse-if-already-sanitised guard. Use with care.",
        ),
    ] = False,
) -> None:
    """Sanitise ``input_path`` against ``mapping_path`` and write to ``output_path``."""
    reject_forbidden_flags(tuple(ctx.args or ()))

    if not input_path.is_file():
        _ERR_CONSOLE.print(f"[red]Input PDF not found: {input_path}[/red]")
        raise typer.Exit(code=2)
    if not mapping_path.is_file():
        _ERR_CONSOLE.print(f"[red]Mapping YAML not found: {mapping_path}[/red]")
        raise typer.Exit(code=2)

    mapping = _load_mapping_yaml(mapping_path)

    try:
        result = sanitize_pdf(
            input_path,
            mapping,
            refuse_if_already_sanitized=not allow_already_sanitized,
        )
    except AlreadySanitizedError as exc:
        _ERR_CONSOLE.print(
            f"[red]Refused: source SHA-256 {exc.source_sha256} is already a known sanitised "
            f"fixture. Pass --allow-already-sanitized to override.[/red]"
        )
        raise typer.Exit(code=2) from exc
    except SanitizationError as exc:
        _ERR_CONSOLE.print(f"[red]Sanitisation failed: {exc}[/red]")
        raise typer.Exit(code=2) from exc

    output_path.write_bytes(result.output_bytes)
    _CONSOLE.print(
        f"[green]Wrote sanitised PDF:[/green] {output_path} "
        f"(source_sha256={result.source_sha256[:16]}…, "
        f"output_sha256={result.output_sha256[:16]}…, "
        f"replacements={len(result.replacements_applied)})"
    )

    if report_path is not None:
        _write_report(result, report_path)


@app.command(
    "prepare-map",
    help="Scaffold a per-capture mapping YAML for an unprocessed source PDF.",
)
def prepare_map_command(
    ctx: typer.Context,
    input_path: Annotated[Path, typer.Argument(help="Path to the captured source PDF.")],
    output_path: Annotated[
        Path,
        typer.Option("--output", "-o", help="Where to write the scaffold YAML."),
    ],
) -> None:
    """Run the justificante parser and emit a YAML scaffold with synthetic values pre-filled."""
    reject_forbidden_flags(tuple(ctx.args or ()))

    if not input_path.is_file():
        _ERR_CONSOLE.print(f"[red]Input PDF not found: {input_path}[/red]")
        raise typer.Exit(code=2)

    try:
        justificante = parse_justificante(input_path)
    except JustificanteError as exc:
        _ERR_CONSOLE.print(
            f"[yellow]Could not parse {input_path} as a justificante: {exc}. "
            f"Scaffolding an empty mapping anyway — fill in the real values manually.[/yellow]"
        )
        scaffold = _empty_scaffold()
    else:
        scaffold = _scaffold_from_justificante(justificante)

    output_path.write_text(
        yaml.safe_dump(scaffold, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    _CONSOLE.print(
        f"[green]Wrote mapping scaffold:[/green] {output_path}\n"
        "[yellow]Edit the file to fill in `real:` cleartext values before running "
        "`aeat sanitize pdf`.[/yellow]"
    )


@app.command(
    "verify",
    help="Adversarial absence check: assert no real value leaks into a sanitised PDF.",
)
def verify_command(
    ctx: typer.Context,
    output_pdf: Annotated[Path, typer.Argument(help="Sanitised PDF to verify.")],
    mapping_path: Annotated[
        Path,
        typer.Option("--against", help="Path to the per-capture mapping YAML."),
    ],
) -> None:
    """Verify ``output_pdf`` carries no ``real:`` value from ``mapping_path``."""
    reject_forbidden_flags(tuple(ctx.args or ()))

    if not output_pdf.is_file():
        _ERR_CONSOLE.print(f"[red]Sanitised PDF not found: {output_pdf}[/red]")
        raise typer.Exit(code=2)
    if not mapping_path.is_file():
        _ERR_CONSOLE.print(f"[red]Mapping YAML not found: {mapping_path}[/red]")
        raise typer.Exit(code=2)

    mapping = _load_mapping_yaml(mapping_path)
    raw_bytes = output_pdf.read_bytes()
    decompressed = _decompressed_content_bytes(raw_bytes)

    leaks: list[tuple[str, str]] = []
    for category, entries in _iter_token_map_entries(mapping):
        for entry in entries:
            real = entry.real.get_secret_value()
            real_bytes = real.encode("utf-8")
            if real_bytes in raw_bytes or real_bytes in decompressed:
                leaks.append((category, entry.surface_label))

    if leaks:
        for category, label in leaks:
            _ERR_CONSOLE.print(f"[red]LEAK: real value for {category}/{label!r} found in {output_pdf}[/red]")
        raise typer.Exit(code=1)

    _CONSOLE.print(
        f"[green]No leaks detected in {output_pdf}.[/green] "
        f"Checked {sum(len(entries) for _, entries in _iter_token_map_entries(mapping))} "
        f"replacement entries."
    )


@app.command("check", help="Structural integrity check on a sanitised PDF.")
def check_command(
    ctx: typer.Context,
    output_pdf: Annotated[Path, typer.Argument(help="Sanitised PDF to inspect.")],
) -> None:
    """Re-open ``output_pdf`` with pikepdf and run the justificante parser."""
    reject_forbidden_flags(tuple(ctx.args or ()))

    if not output_pdf.is_file():
        _ERR_CONSOLE.print(f"[red]Sanitised PDF not found: {output_pdf}[/red]")
        raise typer.Exit(code=2)

    try:
        pikepdf.Pdf.open(output_pdf)
    except pikepdf._core.PdfError as exc:
        _ERR_CONSOLE.print(f"[red]pikepdf could not parse {output_pdf}: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    try:
        justificante = parse_justificante(output_pdf)
    except JustificanteError as exc:
        _ERR_CONSOLE.print(f"[red]Justificante parser failed on {output_pdf}: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    _CONSOLE.print(
        f"[green]Structural check passed:[/green] {output_pdf}\n"
        f"  modelo={justificante.modelo} period={justificante.period} "
        f"csv={justificante.csv} tax_id={justificante.tax_id}"
    )


_REPLACEMENT_CATEGORIES: dict[str, type] = {
    "nif": NifReplacement,
    "name": NameReplacement,
    "address": AddressReplacement,
    "expediente": ExpedienteReplacement,
    "csv": CsvReplacement,
    "nrc": NrcReplacement,
    "iban": IbanReplacement,
    "importe": ImporteReplacement,
    "arbitrary": ArbitraryReplacement,
}


def _load_mapping_yaml(path: Path) -> TokenMap:
    """Loads a TokenMap from ``path``; exits with a message on validation error."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        _ERR_CONSOLE.print(f"[red]Mapping YAML must be a mapping at the top level: {path}[/red]")
        raise typer.Exit(code=2)

    constructed: dict[str, tuple] = {}
    for category, entries in raw.items():
        if category not in _REPLACEMENT_CATEGORIES:
            _ERR_CONSOLE.print(f"[red]Unknown TokenMap category: {category!r}[/red]")
            raise typer.Exit(code=2)
        if entries is None:
            constructed[category] = ()
            continue
        cls = _REPLACEMENT_CATEGORIES[category]
        records = []
        for entry in entries:
            if not isinstance(entry, dict):
                _ERR_CONSOLE.print(
                    f"[red]Each entry in {category!r} must be a mapping; got {type(entry).__name__}[/red]"
                )
                raise typer.Exit(code=2)
            real_raw = entry.get("real")
            if not real_raw:
                _ERR_CONSOLE.print(f"[red]Entry under {category!r} is missing `real:` (cleartext value).[/red]")
                raise typer.Exit(code=2)
            try:
                records.append(
                    cls(
                        real=SecretStr(str(real_raw)),
                        synthetic=str(entry["synthetic"]),
                        surface_label=str(entry.get("surface_label", category)),
                    )
                )
            except Exception as exc:
                _ERR_CONSOLE.print(f"[red]Validation failed for {category!r} entry: {exc}[/red]")
                raise typer.Exit(code=2) from exc
        constructed[category] = tuple(records)

    return TokenMap(**constructed)


def _iter_token_map_entries(
    mapping: TokenMap,
) -> list[tuple[str, tuple]]:
    """Returns ``(category_name, entries)`` pairs for every populated category."""
    return [(name, getattr(mapping, name)) for name in _REPLACEMENT_CATEGORIES if getattr(mapping, name)]


def _empty_scaffold() -> dict[str, list[dict[str, str]]]:
    """Returns a YAML-ready scaffold with one placeholder entry per category."""
    return {
        category: [
            {
                "real": "REPLACE_WITH_REAL_CLEARTEXT",
                "synthetic": "REPLACE_WITH_SYNTHETIC",
                "surface_label": category,
            }
        ]
        for category in _REPLACEMENT_CATEGORIES
    }


def _scaffold_from_justificante(justificante: object) -> dict[str, list[dict[str, str]]]:
    """Returns a YAML-ready scaffold with synthetic values pre-filled from the parsed justificante.

    Args:
        justificante: A parsed :class:`aeat.justificante.Justificante`
            (typed as ``object`` here to dodge a circular-import
            cost; structural attribute access only).

    Returns:
        Dict in the shape consumable by :func:`_load_mapping_yaml`,
        with synthetic values pre-filled for nif / csv / name and
        empty real fields the operator must fill in.
    """
    nif_synthetic = "Y0000001S"
    csv_synthetic = _synthesise_csv_for(getattr(justificante, "modelo", "000"))
    name_synthetic = "APELLIDO APELLIDO NOMBRE"
    return {
        "nif": [
            {
                "real": str(getattr(justificante, "tax_id", "")),
                "synthetic": nif_synthetic,
                "surface_label": "taxpayer NIF/NIE",
            }
        ],
        "name": [
            {
                "real": "FILL_IN_REAL_TAXPAYER_NAME",
                "synthetic": name_synthetic,
                "surface_label": "taxpayer name",
            }
        ],
        "csv": [
            {
                "real": str(getattr(justificante, "csv", "")),
                "synthetic": csv_synthetic,
                "surface_label": "csv",
            }
        ],
        "address": [],
        "expediente": [],
        "nrc": [],
        "iban": [],
        "importe": [],
        "arbitrary": [],
    }


def _synthesise_csv_for(modelo: str) -> str:
    """Returns a 16-character synthetic CSV deterministically derived from ``modelo``.

    The synthetic conforms to the 16-char base32-like shape AEAT
    publishes. It is intentionally *not* random: the same modelo
    always yields the same synthetic so a fixture's CSV is
    auditable across runs.
    """
    base = f"SANITIZED{modelo:>3}"[:16]
    return (base + "X" * 16)[:16].upper()


def _decompressed_content_bytes(pdf_bytes: bytes) -> bytes:
    """Returns the concatenated decompressed content streams of every page."""
    pdf = pikepdf.Pdf.open(io.BytesIO(pdf_bytes))
    chunks: list[bytes] = []
    for page in pdf.pages:
        contents = page.obj.get("/Contents")
        if contents is None:
            continue
        if isinstance(contents, pikepdf.Array):
            for index in range(len(contents)):
                chunks.append(bytes(contents[index].read_bytes()))
        else:
            chunks.append(bytes(contents.read_bytes()))
    return b"\n".join(chunks)


def _write_report(result: SanitizationResult, path: Path) -> None:
    """Writes the SanitizationResult as JSON to ``path``.

    ``output_bytes`` is excluded — the PDF bytes are not UTF-8
    safe and the audit log already carries ``output_sha256`` for
    integrity, so a JSON-friendly digest is the right serialised
    shape.
    """
    payload = result.model_dump(mode="json", exclude={"output_bytes"})
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _hash_bytes(data: bytes) -> str:
    """Returns the lowercase hex sha-256 of ``data`` (helper for debugging)."""
    return hashlib.sha256(data).hexdigest()


# `sys` import is used by typer / Click internally but keep the
# binding alive for adversarial environments where lazy import
# resolution otherwise misses it.
_ = sys
