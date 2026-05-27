"""Developer CLI for locale catalogue audits and scaffolding."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from aeat.core.i18n import tr

from .manager import LocaleError, LocaleManager

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
            typer.echo(f"{locale_path.name}: missing={len(missing)} extra={len(extra)}")
            for key in missing:
                typer.echo(f"  missing {key}")
            for key in extra:
                typer.echo(f"  extra {key}")
        else:
            typer.echo(f"{locale_path.name}: ok")
    if failed:
        raise typer.Exit(code=1)


@app.command("scaffold")
def scaffold(
    check: Annotated[
        bool,
        typer.Option("--check", help=tr("cli.locales.scaffold_check_help")),
    ] = False,
) -> None:
    """Update locale files so they match concrete codebase translation keys."""

    if check:
        audit()
        return
    _default_manager().scaffold()
    typer.echo("locale scaffold updated")


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
    typer.echo(f"updated {path.name}:{key}")


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
    typer.echo(f"removed {path.name}:{key}")


def _covered_by_namespace(key: str, namespace_prefixes: tuple[str, ...]) -> bool:
    return any(f".{prefix}." in f".{key}." for prefix in namespace_prefixes)


__all__ = ["app"]
