"""Developer CLI for locale catalogue audits and scaffolding."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from aeat.core.i18n import tr

from .manager import LocaleManager

app = typer.Typer(name="locales", help=tr("cli.locales.app_help"), no_args_is_help=True)


def _default_manager() -> LocaleManager:
    locales_dir = Path(__file__).parent
    return LocaleManager(locales_dir.parent, locales_dir)


@app.command("audit")
def audit() -> None:
    """Print codebase-to-locale drift for every locale file."""

    manager = _default_manager()
    codebase_keys = manager.get_codebase_keys()
    namespace_prefixes = tuple(
        marker.rstrip("*").rstrip(".") for marker in manager.get_codebase_namespaces() if marker.rstrip("*").rstrip(".")
    )
    failed = False
    for locale_path in sorted(manager.locales_dir.glob("*.yml")):
        keys = manager.get_yaml_keys(manager.load_locale(locale_path))
        missing = sorted(codebase_keys - keys)
        extra = sorted(key for key in keys - codebase_keys if not _covered_by_namespace(key, namespace_prefixes))
        if missing or extra:
            failed = True
            typer.echo(
                tr(
                    "cli.locales.audit.summary",
                    default="%{file}: missing=%{missing} extra=%{extra}",
                    file=locale_path.name,
                    missing=len(missing),
                    extra=len(extra),
                )
            )
            for key in missing:
                typer.echo(tr("cli.locales.audit.missing", default="  missing %{key}", key=key))
            for key in extra:
                typer.echo(tr("cli.locales.audit.extra", default="  extra %{key}", key=key))
        else:
            typer.echo(tr("cli.locales.audit.ok", default="%{file}: ok", file=locale_path.name))
    parity_keys = manager.get_parity_keys()
    for locale_path in sorted(manager.locales_dir.glob("*.yml")):
        keys = manager.get_yaml_keys(manager.load_locale(locale_path))
        missing = sorted(parity_keys - keys)
        extra = sorted(keys - parity_keys)
        if missing or extra:
            failed = True
            typer.echo(
                tr(
                    "cli.locales.audit.parity_summary",
                    default="%{file}: parity-missing=%{missing} parity-extra=%{extra}",
                    file=locale_path.name,
                    missing=len(missing),
                    extra=len(extra),
                )
            )
            for key in missing:
                typer.echo(tr("cli.locales.audit.parity_missing", default="  parity missing %{key}", key=key))
            for key in extra:
                typer.echo(tr("cli.locales.audit.parity_extra", default="  parity extra %{key}", key=key))
    if failed:
        raise typer.Exit(code=1)


@app.command("scaffold")
def scaffold(
    check: Annotated[
        bool,
        typer.Option("--check", help=tr("cli.locales.scaffold_check_help")),
    ] = False,
    sync_locale_parity: Annotated[
        bool,
        typer.Option("--sync-locale-parity", help=tr("cli.locales.scaffold_sync_locale_parity_help")),
    ] = False,
) -> None:
    """Update locale files so they match concrete codebase translation keys."""

    if check:
        audit()
        return
    _default_manager().scaffold(sync_locale_parity=sync_locale_parity)
    typer.echo(tr("cli.locales.scaffold.updated", default="locale scaffold updated"))


def _covered_by_namespace(key: str, namespace_prefixes: tuple[str, ...]) -> bool:
    return any(f".{prefix}." in f".{key}." for prefix in namespace_prefixes)


__all__ = ["app"]
