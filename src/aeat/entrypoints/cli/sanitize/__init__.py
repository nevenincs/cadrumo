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

import io
import json
import re
from pathlib import Path
from typing import Annotated

import pikepdf
import typer
import yaml
from pydantic import SecretStr
from rich.console import Console

from ....adapters.inbound.sanitizer import (
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
from ....core.logging import get_logger
from ....domain.justificante import JustificanteError, parse_justificante

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
    """Run the justificante parser and emit a YAML scaffold with synthetic values pre-filled.

    The scaffold pre-fills:

    * ``nif`` from the parsed ``tax_id``.
    * ``csv`` from the parsed ``csv``.
    * ``name`` placeholder (operator must fill the real value).
    * ``importe`` from every Spanish-shape decimal token detected
      in the PDF's text — covers the ~80 monetary casillas of a
      Modelo 100 declaration without operator enumeration.
    * ``arbitrary`` from every catastral reference, NRC, and date
      token detected.

    The operator only needs to fill in the real taxpayer name and
    review the auto-detected entries before running ``aeat
    sanitize pdf``.
    """
    reject_forbidden_flags(tuple(ctx.args or ()))

    if not input_path.is_file():
        _ERR_CONSOLE.print(f"[red]Input PDF not found: {input_path}[/red]")
        raise typer.Exit(code=2)

    pdf_text = _extract_pdf_text(input_path)

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

    auto_detected = _detect_pii_surfaces(pdf_text)
    for category, entries in auto_detected.items():
        existing_reals = {e.get("real") for e in scaffold.get(category, [])}
        scaffold.setdefault(category, [])
        for entry in entries:
            if entry["real"] in existing_reals:
                continue
            scaffold[category].append(entry)
            existing_reals.add(entry["real"])

    output_path.write_text(
        yaml.safe_dump(scaffold, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    counts = ", ".join(f"{cat}={len(entries)}" for cat, entries in scaffold.items() if entries)
    _CONSOLE.print(
        f"[green]Wrote mapping scaffold:[/green] {output_path}\n"
        f"  detected: {counts}\n"
        "[yellow]Edit the file to fill in any blank `real:` cleartext values "
        "(taxpayer name, anything the auto-detector missed) before running "
        "`aeat sanitize pdf`.[/yellow]"
    )


def _extract_pdf_text(path: Path) -> str:
    """Return the concatenated text of every page in ``path``.

    Uses pdfplumber (already a project dependency); silently
    returns an empty string when the PDF cannot be opened so the
    scaffold falls back to the structural fields only.
    """
    try:
        import pdfplumber
    except ImportError:
        return ""
    try:
        with pdfplumber.open(path) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception:
        return ""


_IMPORTE_RE = re.compile(
    # Spanish decimal: optional thousands dotted, comma decimal,
    # 2 decimal digits. Examples: "1.234,56", "549,52", "8.422,62".
    # Reject standalone integers (would catch noise like page
    # numbers).
    r"(?<![A-Za-z0-9])-?\d{1,3}(?:\.\d{3})*,\d{2}(?![A-Za-z0-9])",
)
# DD-MM-YYYY or DD/MM/YYYY date tokens — common across receipts.
_DATE_RE = re.compile(r"(?<![A-Za-z0-9])\d{2}[-/]\d{2}[-/](?:19|20)\d{2}(?![A-Za-z0-9])")
# Catastral references (Spanish ``Referencia catastral``, 20 chars):
# 7 digits + 2 letters + 4 digits + 1 letter + 4 digits + 2 letters.
# Sample ``9561760DF2896B0011HW``. No hyphens or whitespace.
_CATASTRAL_RE = re.compile(r"(?<![A-Z0-9])[0-9]{7}[A-Z]{2}[0-9]{4}[A-Z][0-9]{4}[A-Z]{2}(?![A-Z0-9])")
# NRC: 22 alphanumeric chars; AEAT prints these next to "NRC:"
# but the shape alone is distinctive enough to detect inline.
_NRC_RE = re.compile(r"(?<![A-Z0-9])[0-9]{13,14}[A-Z][A-Z0-9]{6,8}(?![A-Z0-9])")
# Spanish IBAN shape: ES + 2 check digits + 20 alphanumeric. AEAT
# prints these in space-separated 4-char groups (``ES76 2100 0418
# 4012 3456 7891``) — strip whitespace before matching so the
# bare 24-char form is what we record.
_IBAN_ES_RE = re.compile(
    r"(?<![A-Z0-9])ES\d{2}(?:\s?[A-Z0-9]{4}){5}(?![A-Z0-9])",
)
# Spanish phone numbers: optional +34 / 0034 prefix, then 9 digits
# starting 6/7/8/9 (mobile + landline + premium). AEAT-printed
# helpline numbers (``901 33 55 33`` / ``915 548 770``) match this
# shape and would otherwise pollute fixtures.
_PHONE_ES_RE = re.compile(
    r"(?<![0-9])(?:(?:\+34|0034)\s?)?[6789]\d{2}[\s-]?\d{2}[\s-]?\d{2}[\s-]?\d{2}(?![0-9])",
)


def _detect_pii_surfaces(text: str) -> dict[str, list[dict[str, str]]]:
    """Return per-category entries auto-detected in ``text``.

    The detection is conservative: it returns categories the
    operator should review, never categories where false positives
    would corrupt the sanitiser's output. The synthetic values are
    deterministic placeholders the operator can override before
    sanitising.
    """
    importes: list[str] = sorted({m.group(0) for m in _IMPORTE_RE.finditer(text)})
    dates: list[str] = sorted({m.group(0) for m in _DATE_RE.finditer(text)})
    catastrales: list[str] = sorted({m.group(0) for m in _CATASTRAL_RE.finditer(text)})
    nrcs: list[str] = sorted({m.group(0) for m in _NRC_RE.finditer(text)})
    ibans_raw: list[str] = sorted({m.group(0) for m in _IBAN_ES_RE.finditer(text)})
    phones: list[str] = sorted({m.group(0) for m in _PHONE_ES_RE.finditer(text)})
    # AEAT helpline numbers are public + universally hardcoded; do
    # not redact them. Strip from the phone candidates before
    # building the scaffold so the operator's mapping stays focused
    # on actually-private numbers.
    _aeat_helplines_normalised = {
        "901335533",
        "915548770",
    }

    def _normalise(phone: str) -> str:
        return phone.replace(" ", "").replace("-", "").replace("+34", "").replace("0034", "")

    phones = [p for p in phones if _normalise(p) not in _aeat_helplines_normalised]

    return {
        "importe": [
            {
                "real": value,
                "synthetic": "1.000,00",
                "surface_label": f"importe {idx}",
            }
            for idx, value in enumerate(importes)
        ],
        "nrc": [
            {
                "real": value,
                "synthetic": _synthesise_nrc(idx),
                "surface_label": f"nrc {idx}",
            }
            for idx, value in enumerate(nrcs)
        ],
        "iban": [
            {
                "real": value,
                # ES80 2310 0001 1800 0001 2345 — known-valid
                # mod-97 sample. Reused across all detected IBANs;
                # the operator can override per-fixture if a
                # collision is undesirable.
                "synthetic": "ES8023100001180000012345",
                "surface_label": f"iban {idx}",
            }
            for idx, value in enumerate(ibans_raw)
        ],
        "arbitrary": [
            *(
                {
                    "real": value,
                    "synthetic": _synthesise_catastral(idx),
                    "surface_label": f"catastral reference {idx}",
                }
                for idx, value in enumerate(catastrales)
            ),
            *(
                {
                    "real": value,
                    # Preserve the dash-or-slash separator the
                    # source uses so downstream parsers (which
                    # bind on ``DD-MM-YYYY`` vs ``DD/MM/YYYY``)
                    # don't lose their match. "01-01-1900" maps
                    # to a placeholder year + January 1st.
                    "synthetic": ("01/01/1900" if "/" in value else "01-01-1900"),
                    "surface_label": f"date token {idx}",
                }
                for idx, value in enumerate(dates)
            ),
            *(
                {
                    "real": value,
                    # 600 000 000 — Spanish mobile shape,
                    # universally non-allocated.
                    "synthetic": "600000000",
                    "surface_label": f"phone {idx}",
                }
                for idx, value in enumerate(phones)
            ),
        ],
    }


def _synthesise_nrc(index: int) -> str:
    """Return a deterministic synthetic NRC of canonical 22-char shape."""
    base = f"0000000000000{index:09d}"
    # Replace the leading 14th char with a letter so the shape
    # matches AEAT's "<13 digits><letter><8 chars>" pattern.
    return f"{base[:13]}X{base[14:21]}"[:22].ljust(22, "X")


def _synthesise_catastral(index: int) -> str:
    """Return a deterministic synthetic 20-char catastral reference."""
    base = f"00000XX0000X{index:04d}XX"
    return base[:20].ljust(20, "X")


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

    # Mask every synthetic value from the byte streams BEFORE
    # searching for real values. Without this, a real like ``0,00``
    # would falsely match the synthetic ``1.000,00`` that contains
    # it as a substring. Mask longest-first so nested overlaps
    # collapse cleanly: ``1.000,00`` is replaced with NULs before
    # the inner ``0,00`` is matched against the residual bytes.
    synthetic_values: list[str] = [
        str(entry.synthetic) for _, entries in _iter_token_map_entries(mapping) for entry in entries
    ]
    masked_raw = raw_bytes
    masked_decompressed = decompressed
    # Mask longest-first so nested overlaps collapse cleanly.
    # ``sorted(..., key=len, ...)`` widens the element type to
    # ``Sized`` for ty; the explicit ``str(...)`` cast forces the
    # narrow type back so ``encode`` resolves cleanly.
    for raw_synthetic in sorted(set(synthetic_values), key=len, reverse=True):
        synthetic = str(raw_synthetic)
        encoded = synthetic.encode("utf-8")
        marker = b"\x00" * len(synthetic)
        masked_raw = masked_raw.replace(encoded, marker)
        masked_decompressed = masked_decompressed.replace(encoded, marker)

    leaks: list[tuple[str, str]] = []
    for category, entries in _iter_token_map_entries(mapping):
        for entry in entries:
            real = entry.real.get_secret_value()
            real_bytes = real.encode("utf-8")
            if real_bytes in masked_raw or real_bytes in masked_decompressed:
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
    except pikepdf.PdfError as exc:
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
    csv_synthetic = _synthesise_csv_for(
        getattr(justificante, "modelo", "000"),
        ejercicio=str(getattr(justificante, "ejercicio", "") or ""),
    )
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


def _synthesise_csv_for(modelo: str, *, ejercicio: str = "") -> str:
    """Returns a 16-character synthetic CSV deterministically derived from ``modelo``.

    The synthetic conforms to the 16-char base32-like shape AEAT
    publishes. It is intentionally *not* random: the same
    ``(modelo, ejercicio)`` pair always yields the same synthetic
    so a fixture's CSV is auditable across runs.

    When ``ejercicio`` is supplied, the embed shape is
    ``SANITIZED{modelo}{ejercicio}`` (matches the existing
    fixture corpus, e.g. ``SANITIZED1302024`` for M130 / 2024).
    Otherwise the helper falls back to ``SANITIZED{modelo}XXXX``
    padding so the result still hits the 16-char target.

    Args:
        modelo: AEAT modelo code (typically 3 digits).
        ejercicio: Optional tax year (4 digits). When provided
            and ``len("SANITIZED" + modelo + ejercicio) <= 16``,
            the year is embedded directly. Out-of-bounds inputs
            silently fall back to padding to keep the helper
            shape-conforming.

    Returns:
        A 16-character uppercase synthetic CSV.
    """
    embed = f"SANITIZED{modelo}{ejercicio}"
    if 1 <= len(embed) <= 16:
        return (embed + "X" * 16)[:16].upper()
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
