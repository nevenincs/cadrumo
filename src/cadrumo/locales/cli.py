"""Developer CLI for locale catalogue audits and scaffolding.

Catalogue-wide commands delegate YAML maintenance to
:class:`locales.manager.LocaleManager`, while ``modelo`` subcommands
route schema-local TOML translations through
:class:`locales._modelo_manager.ModeloLocaleManager`. Typer arguments
that name runtime languages use :class:`core.external_constants.OutputLanguage`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ..core.external_constants import OutputLanguage
from ..core.i18n import tr
from ._modelo_manager import (
    ModeloLocaleCoverageRecord,
    ModeloLocaleDriftKind,
    ModeloLocaleDriftRecord,
    ModeloLocaleError,
    ModeloLocaleFieldKind,
    ModeloLocaleManager,
)
from .manager import (
    LocaleAuditResult,
    LocaleError,
    LocaleFileAudit,
    LocaleManager,
    LocalePlaceholderMismatch,
)

app = typer.Typer(name="locales", help=tr("cli.locales.app_help"), no_args_is_help=True)
modelo_app = typer.Typer(
    name="modelo",
    help=tr("cli.locales.modelo.app_help", default="Manage modelo schema-local translations."),
    no_args_is_help=True,
)
app.add_typer(modelo_app)


def _default_manager() -> LocaleManager:
    locales_dir = Path(__file__).parent
    return LocaleManager(locales_dir.parent, locales_dir)


def _modelo_manager(registry_root: Path | None) -> ModeloLocaleManager:
    return ModeloLocaleManager(registry_root)


RegistryRootOpt = Annotated[
    Path | None,
    typer.Option(
        "--registry-root",
        help=tr("cli.locales.modelo.registry_root_help", default="AEAT registry root override."),
    ),
]


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
        typer.echo(tr("locales.cli.audit.file_ok", locale_file=file_result.locale_file))
        return
    if file_result.codebase_missing or file_result.codebase_extra:
        typer.echo(
            tr(
                "locales.cli.audit.file_drift",
                locale_file=file_result.locale_file,
                missing_count=len(file_result.codebase_missing),
                extra_count=len(file_result.codebase_extra),
            ),
        )
    for key in file_result.codebase_missing:
        typer.echo(tr("locales.cli.audit.key_missing", key=key))
    for key in file_result.codebase_extra:
        typer.echo(tr("locales.cli.audit.key_extra", key=key))
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


@app.command("scaffold")
def scaffold(
    ctx: typer.Context,
    check: Annotated[
        bool,
        typer.Option("--check", help=tr("cli.locales.scaffold_check_help")),
    ] = False,
) -> None:
    """Update locale files so they match concrete codebase translation keys."""
    if check:
        audit(ctx)
        return
    manager = ctx.obj if isinstance(ctx.obj, LocaleManager) else _default_manager()
    manager.scaffold()
    typer.echo(tr("locales.cli.scaffold_updated"))


@app.command("set")
def set_value(
    locale: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.set_locale_help", default="Locale code to update.")),
    ],
    key: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.set_key_help", default="Dotted locale key to update.")),
    ],
    value: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.set_value_help", default="Replacement locale value.")),
    ],
) -> None:
    """Set one locale string leaf."""
    try:
        path = _default_manager().set_locale_value(locale, key, value)
    except LocaleError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(tr("locales.cli.set.updated", locale_file=path.name, key=key))


@app.command("canonicalize-product-identity")
def canonicalize_product_identity(
    ctx: typer.Context,
    locale: Annotated[
        OutputLanguage | None,
        typer.Option("--locale", help=tr("cli.locales.canonicalize_product_identity.locale_help")),
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
        typer.Argument(help=tr("cli.locales.remove_locale_help", default="Locale code to update.")),
    ],
    key: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.remove_key_help", default="Dotted locale key to remove.")),
    ],
) -> None:
    """Remove one locale string leaf."""
    try:
        path = _default_manager().remove_locale_value(locale, key)
    except LocaleError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(tr("locales.cli.remove.removed", locale_file=path.name, key=key))


@modelo_app.command("audit", help=tr("cli.locales.modelo.audit_help", default="Audit modelo schema translations."))
def modelo_audit(
    locale: Annotated[
        OutputLanguage,
        typer.Argument(help=tr("cli.locales.modelo.locale_help", default="Locale code to audit.")),
    ],
    modelo_id: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.modelo.modelo_help", default="Modelo id to audit.")),
    ],
    revision_id: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.modelo.revision_help", default="Revision id to audit.")),
    ],
    registry_root: RegistryRootOpt = None,
) -> None:
    """Audit modelo schema-local translation coverage and drift."""
    try:
        record = _modelo_manager(registry_root).coverage_record(locale, modelo_id, revision_id)
    except ModeloLocaleError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _echo_modelo_coverage(record)
    for drift in record.drift:
        _echo_modelo_drift(drift)
    if not record.complete:
        raise typer.Exit(code=1)


@modelo_app.command(
    "scaffold",
    help=tr("cli.locales.modelo.scaffold_help", default="Scaffold modelo schema translation files."),
)
def modelo_scaffold(
    locale: Annotated[
        OutputLanguage,
        typer.Argument(help=tr("cli.locales.modelo.locale_help", default="Locale code to scaffold.")),
    ],
    modelo_id: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.modelo.modelo_help", default="Modelo id to scaffold.")),
    ],
    revision_id: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.modelo.revision_help", default="Revision id to scaffold.")),
    ],
    check: Annotated[
        bool,
        typer.Option("--check", help=tr("cli.locales.modelo.scaffold_check_help", default="Check without writing.")),
    ] = False,
    registry_root: RegistryRootOpt = None,
) -> None:
    """Scaffold modelo schema-local translation TOML files."""
    manager = _modelo_manager(registry_root)
    if check:
        try:
            record = manager.coverage_record(locale, modelo_id, revision_id)
        except ModeloLocaleError as exc:
            raise typer.BadParameter(str(exc)) from exc
        _echo_modelo_coverage(record)
        for drift in record.drift:
            _echo_modelo_drift(drift)
        if not record.complete:
            raise typer.Exit(code=1)
        return
    try:
        changed = manager.scaffold_revision(locale, modelo_id, revision_id)
    except ModeloLocaleError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if changed:
        for path in changed:
            typer.echo(tr("locales.cli.modelo.scaffold.updated", path=str(path)))
    else:
        typer.echo(
            tr(
                "locales.cli.modelo.scaffold.no_changes",
                default="Modelo locale scaffold already aligned.",
            ),
        )


@modelo_app.command("set", help=tr("cli.locales.modelo.set_help", default="Set one modelo schema translation."))
def modelo_set_value(
    locale: Annotated[
        OutputLanguage,
        typer.Argument(help=tr("cli.locales.modelo.locale_help", default="Locale code to update.")),
    ],
    modelo_id: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.modelo.modelo_help", default="Modelo id to update.")),
    ],
    revision_id: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.modelo.revision_help", default="Revision id to update.")),
    ],
    field: Annotated[
        ModeloLocaleFieldKind,
        typer.Argument(help=tr("cli.locales.modelo.field_help", default="Translation field to update.")),
    ],
    key: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.modelo.key_help", default="Schema key to update.")),
    ],
    value: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.modelo.value_help", default="Translated value.")),
    ],
    registry_root: RegistryRootOpt = None,
) -> None:
    """Set one modelo schema-local translation leaf."""
    try:
        path = _modelo_manager(registry_root).set_translation_value(locale, modelo_id, revision_id, field, key, value)
    except ModeloLocaleError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(tr("locales.cli.modelo.set.updated", path=str(path), field=field.value, key=key))


@modelo_app.command(
    "remove",
    help=tr("cli.locales.modelo.remove_help", default="Remove one modelo schema translation."),
)
def modelo_remove_value(
    locale: Annotated[
        OutputLanguage,
        typer.Argument(help=tr("cli.locales.modelo.locale_help", default="Locale code to update.")),
    ],
    modelo_id: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.modelo.modelo_help", default="Modelo id to update.")),
    ],
    revision_id: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.modelo.revision_help", default="Revision id to update.")),
    ],
    field: Annotated[
        ModeloLocaleFieldKind,
        typer.Argument(help=tr("cli.locales.modelo.field_help", default="Translation field to remove.")),
    ],
    key: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.modelo.key_help", default="Schema key to remove.")),
    ],
    registry_root: RegistryRootOpt = None,
) -> None:
    """Remove one modelo schema-local translation leaf."""
    try:
        path = _modelo_manager(registry_root).remove_translation_value(locale, modelo_id, revision_id, field, key)
    except ModeloLocaleError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(tr("locales.cli.modelo.remove.removed", path=str(path), field=field.value, key=key))


@modelo_app.command("coverage", help=tr("cli.locales.modelo.coverage_help", default="Print modelo schema coverage."))
def modelo_coverage(
    locale: Annotated[
        OutputLanguage,
        typer.Argument(help=tr("cli.locales.modelo.locale_help", default="Locale code to inspect.")),
    ],
    modelo_id: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.modelo.modelo_help", default="Modelo id to inspect.")),
    ],
    revision_id: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.modelo.revision_help", default="Revision id to inspect.")),
    ],
    registry_root: RegistryRootOpt = None,
) -> None:
    """Print modelo schema-local translation coverage."""
    try:
        record = _modelo_manager(registry_root).coverage_record(locale, modelo_id, revision_id)
    except ModeloLocaleError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _echo_modelo_coverage(record)


def _echo_modelo_coverage(record: ModeloLocaleCoverageRecord) -> None:
    typer.echo(
        tr(
            "locales.cli.modelo.coverage.row",
            default=(
                "locale={locale_code} modelo={modelo} revision={revision} "
                "labels={label_translated}/{label_required} help={help_translated}/{help_required}"
            ),
            locale_code=record.locale.value,
            modelo=record.modelo_id,
            revision=record.revision_id,
            label_translated=record.label_translated,
            label_required=record.label_required,
            help_translated=record.help_translated,
            help_required=record.help_required,
        ),
    )


def _echo_modelo_drift(drift: ModeloLocaleDriftRecord) -> None:
    if drift.kind is ModeloLocaleDriftKind.STALE:
        typer.echo(
            tr(
                "locales.cli.modelo.audit.stale",
                default=(
                    "stale locale={locale_code} modelo={modelo} revision={revision} "
                    "scope={scope} field={field} key={key}"
                ),
                locale_code=drift.target.locale.value,
                modelo=drift.target.modelo_id,
                revision=drift.target.revision_id or "",
                scope=drift.target.scope.value,
                field=drift.field.value,
                key=drift.key,
            ),
        )
        return
    typer.echo(
        tr(
            "locales.cli.modelo.audit.missing",
            default=(
                "missing locale={locale_code} modelo={modelo} revision={revision} scope={scope} field={field} key={key}"
            ),
            locale_code=drift.target.locale.value,
            modelo=drift.target.modelo_id,
            revision=drift.target.revision_id or "",
            scope=drift.target.scope.value,
            field=drift.field.value,
            key=drift.key,
        ),
    )


__all__ = ["app", "modelo_app"]
