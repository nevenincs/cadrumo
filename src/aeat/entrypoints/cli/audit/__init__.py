"""``aeat audit`` subcommand surface.

The legacy ruleset audit path is disabled while registry-backed
verification becomes the only filing-grade calculation authority.
"""

from __future__ import annotations

import sys

import typer

from .._i18n import t, tr

audit_app = typer.Typer(
    name="audit",
    help="Audit helpers.",
    no_args_is_help=True,
    add_completion=False,
)
rulesets_app = typer.Typer(
    name="rulesets",
    help="Ruleset audit subcommands.",
    no_args_is_help=True,
    add_completion=False,
)
audit_app.add_typer(rulesets_app, name="rulesets")


def _reconfigure_utf8() -> None:
    """Reconfigure :data:`sys.stdout` and :data:`sys.stderr` to UTF-8 if possible.

    The audit reports render Spanish article fragments verbatim
    ("artículo 110.1.c", "agrícolas, ganaderas, forestales y
    pesqueras") and modelo names with diacritics. On Windows the
    default console encoding is cp1252, which crashes on non-ASCII
    output. Reconfiguring to UTF-8 at command entry is the documented
    Python 3.7+ workaround. Streams that don't support ``reconfigure``
    (for example when stdout has been replaced with a buffered I/O
    object during testing) are left alone —
    :class:`typer.testing.CliRunner` substitutes its own capturing
    stream that handles arbitrary text.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            continue


@rulesets_app.command(
    "citations",
    help=(
        "Report per-modelo coverage of the mandatory-citation invariant "
        "over every registered ruleset. Exits non-zero on any gap."
    ),
)
def citations_cmd() -> None:
    """Reject legacy ruleset citation audits."""
    _reconfigure_utf8()
    typer.echo(
        tr(
            t(
                "las auditorías de rulesets heredados están deshabilitadas; usa el registro",
                "legacy ruleset audits are disabled; use the registry",
                "les auditories de rulesets heretats estan deshabilitades; usa el registre",
                "a regi ruleset auditok le vannak tiltva; hasznald a registryt",
            )
        ),
        err=True,
    )
    raise typer.Exit(code=1)


__all__ = [
    "audit_app",
]
