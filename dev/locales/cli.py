"""Developer CLI for shared locale-catalogue audits and scaffolding."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from cadrumo.core.external_constants import UTF_8_ENCODING, OutputLanguage

from ._colanding import LAST_CHANGE, STAGED_CHANGE, ColandingResult, check_colanding
from ._paths import DOCS_SRC_DIR, HARNESS_SRC_DIR, LOCALES_DIR, SRC_DIR
from ._status import CatalogueStatusRecord, catalogue_status
from .manager import (
    LocaleAuditResult,
    LocaleError,
    LocaleFileAudit,
    LocaleManager,
    LocalePlaceholderMismatch,
)

app = typer.Typer(name="locales", help="Audit and scaffold locale catalogues", no_args_is_help=True)


def _default_manager() -> LocaleManager:
    return LocaleManager(SRC_DIR, LOCALES_DIR, extra_src_dirs=(DOCS_SRC_DIR, HARNESS_SRC_DIR))


@app.command("audit")
def audit(ctx: typer.Context) -> None:
    """Print production scalar, key, placeholder, and codebase audit findings."""
    manager = ctx.obj if isinstance(ctx.obj, LocaleManager) else _default_manager()
    result = manager.audit()
    _echo_audit(result)
    if not result.ok:
        raise typer.Exit(code=1)


def _echo_audit(result: LocaleAuditResult) -> None:
    """Render a structured manager audit without owning validation policy."""
    for file_result in result.files:
        _echo_file_audit(file_result)
    for mismatch in result.placeholder_mismatches:
        _echo_placeholder_mismatch(mismatch)


def _echo_file_audit(file_result: LocaleFileAudit) -> None:
    """Echo one catalogue's key-set and scalar findings."""
    if file_result.ok:
        typer.echo(f"{file_result.locale_file}: ok")
        return
    if file_result.codebase_missing or file_result.codebase_extra:
        typer.echo(
            f"{file_result.locale_file}: missing={len(file_result.codebase_missing)} "
            f"extra={len(file_result.codebase_extra)}",
        )
    for key in file_result.codebase_missing:
        typer.echo(f"  missing {key}")
    for key in file_result.codebase_extra:
        typer.echo(f"  extra {key}")
    for key in file_result.inter_locale_missing:
        typer.echo(f"inter-locale missing file={file_result.locale_file} key={key}")
    for violation in file_result.scalar_violations:
        typer.echo(
            f"non-string leaf file={violation.locale_file} key={violation.key} type={violation.value_type}",
        )


def _echo_placeholder_mismatch(mismatch: LocalePlaceholderMismatch) -> None:
    """Echo one placeholder-parity mismatch row across catalogues."""
    rendered_variants = ", ".join(
        f"{variant.locale_file}={sorted(variant.placeholders)!r}" for variant in mismatch.variants
    )
    typer.echo(f"placeholder mismatch key={mismatch.key} {rendered_variants}")


@app.command("status")
def status(
    ctx: typer.Context,
) -> None:
    """Print the honest per-leaf state partition for every locale surface.

    Catalogue rows partition required keys into authored, key-echo,
    unbindable, identical-to-source, and absent states. Generic keys use
    English as the source; Modelo schema keys use the mandatory Spanish
    source.
    """
    manager = ctx.obj if isinstance(ctx.obj, LocaleManager) else _default_manager()
    for record in catalogue_status(manager):
        _echo_catalogue_status(record)


def _echo_catalogue_status(record: CatalogueStatusRecord) -> None:
    """Echo one catalogue's honest state partition as a greppable row."""
    typer.echo(
        f"catalogue file={record.locale_file} required={record.required} authored={record.authored} "
        f"key_echo={record.key_echo} blank={record.blank} unbindable={record.unbindable} "
        f"identical_allowlisted={record.identical_allowlisted} "
        f"identical_pending={record.identical_pending} absent={record.absent} extra={record.extra} "
        f"namespace_exempted={record.namespace_exempted}",
    )


@app.command("scaffold")
def scaffold(
    ctx: typer.Context,
    check: Annotated[
        bool,
        typer.Option("--check", help="Report drift without writing locale files"),
    ] = False,
) -> None:
    """Update locale files so they match concrete codebase translation keys."""
    if check:
        audit(ctx)
        return
    manager = ctx.obj if isinstance(ctx.obj, LocaleManager) else _default_manager()
    manager.scaffold()
    typer.echo("locale scaffold updated")


@app.command("set")
def set_value(
    locale: Annotated[
        str,
        typer.Argument(help="Locale code to update (e.g. en, es, ca)."),
    ],
    key: Annotated[
        str,
        typer.Argument(help="Dotted locale key to set."),
    ],
    value: Annotated[
        str,
        typer.Argument(help="Replacement locale value."),
    ],
) -> None:
    """Set one locale string leaf."""
    try:
        path = _default_manager().set_locale_value(locale, key, value)
    except LocaleError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"updated {path.name}:{key}")


@app.command("set-batch")
def set_batch(
    manifest: Annotated[
        Path,
        typer.Argument(
            help="JSON object mapping locale codes to dotted-key scalar maps.",
        ),
    ],
) -> None:
    """Apply a generated locale migration manifest through the catalogue authority."""
    try:
        payload = json.loads(manifest.read_text(encoding=UTF_8_ENCODING))
    except (OSError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(f"Cannot read locale batch manifest: {exc}", param_hint="manifest") from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter("Locale batch manifest must contain an object", param_hint="manifest")
    manager = _default_manager()
    updated: list[str] = []
    try:
        for locale, raw_values in sorted(payload.items()):
            if not isinstance(locale, str) or not isinstance(raw_values, dict):
                raise LocaleError("Locale batch entries must map one locale code to an object")
            values: dict[str, str | None] = {}
            for key, value in raw_values.items():
                if not isinstance(key, str) or not (isinstance(value, str) or value is None):
                    raise LocaleError("Locale batch leaves must be string keys with string or null values")
                values[key] = value
            updated.append(manager.set_locale_values(locale, values).name)
    except LocaleError as exc:
        raise typer.BadParameter(str(exc), param_hint="manifest") from exc
    typer.echo(f"updated {len(updated)} locale catalogues: {', '.join(updated)}")


@app.command("allow-identical")
def allow_identical(
    locale: Annotated[
        str,
        typer.Argument(help="Locale code to update."),
    ],
    key: Annotated[
        str,
        typer.Argument(help="Dotted locale key to exempt."),
    ],
    reason: Annotated[
        str,
        typer.Argument(
            help="Why this string is legitimately identical to its canonical source.",
        ),
    ],
) -> None:
    """Record one key as deliberately identical to its canonical source."""
    try:
        path = _default_manager().allow_identical(locale, key, reason)
    except LocaleError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"recorded {path.name}:{locale}:{key}")


@app.command("canonicalize-product-identity")
def canonicalize_product_identity(
    ctx: typer.Context,
    locale: Annotated[
        OutputLanguage | None,
        typer.Option("--locale", help="Update only this supported locale catalogue."),
    ] = None,
) -> None:
    """Normalize stale command prefixes in selected catalogues."""
    manager = ctx.obj if isinstance(ctx.obj, LocaleManager) else _default_manager()
    try:
        updated_paths = manager.canonicalize_product_identity_references(locale=locale)
    except LocaleError as exc:
        raise typer.BadParameter(str(exc), param_hint="--locale") from exc
    typer.echo(f"canonicalized product identity references in {len(updated_paths)} locale catalogue(s)")


@app.command("remove")
def remove_value(
    locale: Annotated[
        str,
        typer.Argument(help="Locale code to update."),
    ],
    key: Annotated[
        str,
        typer.Argument(help="Dotted locale key to remove."),
    ],
) -> None:
    """Remove one locale string leaf."""
    try:
        path = _default_manager().remove_locale_value(locale, key)
    except LocaleError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"removed {path.name}:{key}")


@app.command("co-landing")
def co_landing(
    ctx: typer.Context,
    change: Annotated[
        str,
        typer.Option(
            "--change",
            help=(
                f"Change to compare: {STAGED_CHANGE!r} (the index, falling back to "
                f"{LAST_CHANGE!r} when nothing is staged), {LAST_CHANGE!r} (HEAD~1..HEAD), or a BASE..HEAD range."
            ),
        ),
    ] = STAGED_CHANGE,
) -> None:
    """Refuse a change that separates a catalogue key from the code consuming it.

    Every other locale command compares the tree's current state. This one
    compares the change itself, which is the only moment at which a key and its
    call site can still be made to land together.
    """
    manager = ctx.obj if isinstance(ctx.obj, LocaleManager) else _default_manager()
    try:
        result = check_colanding(manager, change)
    except LocaleError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _echo_colanding(result)
    if not result.ok:
        raise typer.Exit(code=1)


def _echo_colanding(result: ColandingResult) -> None:
    """Echo the compared change, then every finding as a greppable row."""
    typer.echo(
        f"co-landing change={result.change} modules={result.inspected_modules} "
        f"added={len(result.added_keys)} removed={len(result.removed_keys)} "
        f"held={len(result.held_keys)} findings={len(result.findings)}",
    )
    for key in result.held_keys:
        typer.echo(f"  held {key} (owning command family is declared unimplemented)")
    for finding in result.findings:
        typer.echo(f"  {finding.render()}")


__all__ = ["app"]
