"""Module entrypoint for ``python -m aeat.diagnostics``.

Exposes engineer-only verbs that previously lived on the operator
CLI as ``aeat config repair list`` (and a future home for
``profile get/set/unset`` field-at-a-time access and the
``profile activity`` audit-log walker once those move off the
operator surface). The operator CLI does not advertise these
verbs and does not import this module.
"""

from __future__ import annotations

import typer

from ..core.i18n import tr
from .profile import register as register_profile
from .secure_objects import register as register_secure_objects

app = typer.Typer(
    name="diagnostics",
    help=tr("cli.diagnostics.app_help"),
    no_args_is_help=True,
)

register_secure_objects(app)
register_profile(app)


def main() -> None:
    """Run the diagnostics Typer app."""

    app()


if __name__ == "__main__":
    main()
