"""Typer commands for :mod:`aeat.schema`.

Mounted under ``aeat schema``. Commands:

- ``refresh`` — fetch a BOE PDF, run :class:`BoeOrdenExtractor`,
  persist the resulting :class:`Modelo` as sorted JSON under the
  schema cache root.
- ``show`` — pretty-print the cached JSON for a modelo / BOE ref.

The ``refresh`` command accepts a hidden ``--_pdf-path-override``
option used exclusively by the colocated unit tests to skip the
network fetch. The option is not exposed through any env var and
is not listed in ``env/.env.example``.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import typer
from pydantic import AnyHttpUrl

from ..config import load_settings
from ..models import ModeloCode
from ..schema import (
    BOE_ORDEN_SOURCES,
    BoeOrdenExtractor,
    FetchedSchemaSource,
    SchemaCacheError,
    SchemaError,
    SchemaValidationError,
    fetch_boe_pdf,
    load_modelo_from_cache,
    save_modelo_to_cache,
    validate_period_for_modelo,
)

app = typer.Typer(
    name="schema",
    no_args_is_help=True,
    add_completion=False,
    help="Programmatic AEAT modelo schema extraction.",
)


def _resolve_modelo_code(value: str) -> ModeloCode:
    """Accept either the enum name (``MODELO_130``) or the value (``130``)."""
    stripped = (value or "").strip()
    if not stripped:
        raise typer.BadParameter("--modelo is required")
    try:
        return ModeloCode(stripped)
    except ValueError:
        try:
            return ModeloCode[stripped]
        except KeyError as exc:
            raise typer.BadParameter(
                f"unknown modelo code: {stripped!r}",
            ) from exc


def _resolve_origin_url(code: ModeloCode, boe_ref: str) -> AnyHttpUrl:
    """Look up the BOE origin URL for ``(code, boe_ref)`` in the public table."""
    for entry in BOE_ORDEN_SOURCES:
        if entry.modelo_code == code and entry.boe_ref == boe_ref:
            return entry.origin_url
    raise typer.BadParameter(
        f"no BOE_ORDEN_SOURCES entry for ({code.value}, {boe_ref})",
    )


@app.command(
    name="refresh",
    help="Fetch a BOE Orden PDF, extract its schema, and cache it.",
)
def refresh(
    modelo: str = typer.Option(
        ...,
        "--modelo",
        help="Modelo code — either the enum name (MODELO_130) or value (130).",
    ),
    boe_ref: str = typer.Option(
        ...,
        "--boe-ref",
        help="BOE-A identifier of the Orden, e.g. BOE-A-2023-15412.",
    ),
    period: str = typer.Option(
        ...,
        "--period",
        help="Filing period string (2025Q4, 2025, 2025-03).",
    ),
    pdf_path_override: Path | None = typer.Option(
        None,
        "--_pdf-path-override",
        hidden=True,
        help="Test-only override to skip the network fetch.",
    ),
) -> None:
    """Refresh the cache for ``(modelo, boe_ref)``."""
    settings = load_settings()
    code = _resolve_modelo_code(modelo)
    period = period.strip()
    boe_ref = boe_ref.strip()
    try:
        validate_period_for_modelo(code, period)
    except SchemaValidationError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    try:
        if pdf_path_override is not None:
            if not pdf_path_override.exists():
                raise typer.BadParameter(
                    f"--_pdf-path-override: file not found: {pdf_path_override}",
                )
            pdf_bytes = pdf_path_override.read_bytes()
            sha256 = hashlib.sha256(pdf_bytes).hexdigest()
            content_length = len(pdf_bytes)
            origin_url = _resolve_origin_url(code, boe_ref)
            source = FetchedSchemaSource(
                modelo_code=code,
                boe_ref=boe_ref,
                origin_url=origin_url,
                pdf_path=pdf_path_override,
                sha256=sha256,
                content_length=content_length,
                fetched_at=datetime.now(tz=UTC),
            )
        else:
            source = fetch_boe_pdf(code, boe_ref, settings=settings)
        extractor = BoeOrdenExtractor(
            source=source,
            modelo_code=code,
            period=period,
        )
        modelo_record = extractor.extract()
        destination = save_modelo_to_cache(
            modelo_record,
            root=settings.aeat_schema_cache_dir,
            boe_ref=boe_ref,
        )
    except SchemaError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(str(destination))


@app.command(
    name="show",
    help="Pretty-print a cached modelo schema as JSON.",
)
def show(
    modelo: str = typer.Option(
        ...,
        "--modelo",
        help="Modelo code — either the enum name (MODELO_130) or value (130).",
    ),
    boe_ref: str = typer.Option(
        ...,
        "--boe-ref",
        help="BOE-A identifier of the Orden to look up.",
    ),
) -> None:
    """Load ``<cache>/modelo_<code>/<boe_ref>.json`` and emit it as JSON."""
    settings = load_settings()
    code = _resolve_modelo_code(modelo)
    try:
        record = load_modelo_from_cache(
            code,
            boe_ref,
            root=settings.aeat_schema_cache_dir,
        )
    except SchemaCacheError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(record.model_dump_json(indent=2, by_alias=True))
