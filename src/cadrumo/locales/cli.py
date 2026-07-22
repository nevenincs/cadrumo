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
from ._status import CatalogueStatusRecord, catalogue_status
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

_LocaleArg = Annotated[
    OutputLanguage,
    typer.Argument(help=tr("cli.locales.modelo.locale_help", default="Locale code to update.")),
]
_ModeloIdArg = Annotated[
    str,
    typer.Argument(help=tr("cli.locales.modelo.modelo_help", default="Modelo id to update.")),
]
_RevisionIdArg = Annotated[
    str,
    typer.Argument(help=tr("cli.locales.modelo.revision_help", default="Revision id to update.")),
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


_MODELO_STATUS_LOCALES = (OutputLanguage.EN, OutputLanguage.CA, OutputLanguage.HU)


@app.command("status")
def status(
    ctx: typer.Context,
    modelos: Annotated[
        bool,
        typer.Option("--modelos", help="Include the schema-local state of every directory-mode modelo."),
    ] = False,
    modelo_id: Annotated[
        str | None,
        typer.Option("--modelo", help="Restrict the schema-local scan to one modelo id."),
    ] = None,
    revision_id: Annotated[
        str | None,
        typer.Option("--revision", help="Restrict the schema-local scan to one revision id."),
    ] = None,
    locales: Annotated[
        list[OutputLanguage] | None,
        typer.Option("--locale", help="Restrict the schema-local scan to selected locales."),
    ] = None,
    registry_root: RegistryRootOpt = None,
) -> None:
    """Print the honest per-leaf state partition for every locale surface.

    Catalogue rows partition the required codebase keys into authored,
    key-echo, identical-to-en (allowlisted or pending), and absent. Modelo
    rows report the same discipline per revision and locale, with mirrored
    help counted separately from authored help.
    """
    if revision_id is not None and modelo_id is None:
        raise typer.BadParameter("--revision requires --modelo", param_hint="--revision")
    manager = ctx.obj if isinstance(ctx.obj, LocaleManager) else _default_manager()
    for record in catalogue_status(manager):
        _echo_catalogue_status(record)
    if not modelos and modelo_id is None:
        return
    modelo_manager = _modelo_manager(registry_root)
    scan_locales = tuple(locales) if locales else _MODELO_STATUS_LOCALES
    modelo_ids = (modelo_id,) if modelo_id is not None else modelo_manager.modelo_ids()
    try:
        for scanned_modelo_id in modelo_ids:
            for record in modelo_manager.coverage_records(
                scanned_modelo_id,
                revision_id=revision_id,
                locales=scan_locales,
            ):
                _echo_modelo_status(record)
    except ModeloLocaleError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _echo_catalogue_status(record: CatalogueStatusRecord) -> None:
    """Echo one catalogue's honest state partition as a greppable row."""
    typer.echo(
        f"catalogue file={record.locale_file} required={record.required} authored={record.authored} "
        f"key_echo={record.key_echo} identical_allowlisted={record.identical_allowlisted} "
        f"identical_pending={record.identical_pending} absent={record.absent} extra={record.extra}",
    )


def _echo_modelo_status(record: ModeloLocaleCoverageRecord) -> None:
    """Echo one modelo revision's honest state partition as a greppable row."""
    typer.echo(
        f"modelo locale={record.locale.value} modelo={record.modelo_id} revision={record.revision_id} "
        f"label_authored={record.label_translated}/{record.label_required} "
        f"label_key_echo={record.label_key_echo} label_absent={record.label_absent} "
        f"help_authored={record.help_translated}/{record.help_required} "
        f"help_key_echo={record.help_key_echo} help_mirrored={record.help_mirrored} "
        f"help_absent={record.help_absent} complete={str(record.complete).lower()}",
    )


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


@app.command("allow-identical")
def allow_identical(
    locale: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.allow_identical_locale_help", default="Locale code to update.")),
    ],
    key: Annotated[
        str,
        typer.Argument(help=tr("cli.locales.allow_identical_key_help", default="Dotted locale key to exempt.")),
    ],
    reason: Annotated[
        str,
        typer.Argument(
            help=tr(
                "cli.locales.allow_identical_reason_help",
                default="Why this string is legitimately identical to English.",
            )
        ),
    ],
) -> None:
    """Record one key as deliberately identical to English."""
    try:
        path = _default_manager().allow_identical(locale, key, reason)
    except LocaleError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(tr("locales.cli.allow_identical.recorded", allowlist_file=path.name, locale=locale, key=key))


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
    locale: _LocaleArg,
    modelo_id: _ModeloIdArg,
    revision_id: _RevisionIdArg,
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
    locale: _LocaleArg,
    modelo_id: _ModeloIdArg,
    revision_id: _RevisionIdArg,
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
    typer.echo(
        f"states locale={record.locale.value} modelo={record.modelo_id} revision={record.revision_id} "
        f"label_key_echo={record.label_key_echo} label_absent={record.label_absent} "
        f"help_key_echo={record.help_key_echo} help_mirrored={record.help_mirrored} "
        f"help_absent={record.help_absent}",
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
