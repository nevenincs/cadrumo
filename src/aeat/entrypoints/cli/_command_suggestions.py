"""Command-resolution suggestions for the AEAT CLI.

Typer's built-in :class:`~typer.core.TyperGroup` suggests a near-miss
command via :func:`difflib.get_close_matches`. That covers typos
(``overvew`` -> ``overview``) but misses two operator-facing cases:

* **Semantic synonyms** — a different word for the same verb, e.g.
  ``config profile modify`` for ``config profile edit``. The edit
  distance is too large for ``get_close_matches`` to relate them.
* **Cross-path commands** — a command that exists, but under a
  different group, e.g. ``app status`` for ``app overview status``.

:class:`AeatTyperGroup` keeps Typer's typo suggestions and layers a
per-group synonym table on top so both cases produce a translated
"did you mean" hint instead of a bare "No such command".
"""

from __future__ import annotations

import click
from typer.core import TyperGroup

from ...core.i18n import tr

#: Per-group synonym tables keyed by the group's command ``name``.
#: Each inner mapping projects an unknown command token onto the
#: canonical command path an operator most likely intended.
_COMMAND_SYNONYMS: dict[str, dict[str, str]] = {
    "profile": {
        "modify": "edit",
        "update": "edit",
        "change": "edit",
        "remove": "delete",
    },
    "app": {
        "status": "overview status",
        "overview-status": "overview status",
    },
}


class AeatTyperGroup(TyperGroup):
    """:class:`TyperGroup` with semantic-synonym command suggestions.

    Typo-distance suggestions from the base class are preserved; the
    synonym table only adds a hint when the base class produced none
    (or when the synonym is a stronger match than a fuzzy typo guess).
    """

    def resolve_command(
        self,
        ctx: click.Context,
        args: list[str],
    ) -> tuple[str | None, click.Command | None, list[str]]:
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError as exc:
            if args:
                hint = _synonym_hint(self.name, args[0])
                if hint is not None and "Did you mean" not in (exc.message or ""):
                    message = (exc.message or "").rstrip(".")
                    exc.message = f"{message}. {hint}"
            raise


def _synonym_hint(group_name: str | None, token: str) -> str | None:
    """Return a translated suggestion for ``token`` under ``group_name``.

    Returns :data:`None` when the group declares no synonym table or
    the token is not a known synonym.
    """

    if group_name is None:
        return None
    table = _COMMAND_SYNONYMS.get(group_name)
    if table is None:
        return None
    canonical = table.get(token.strip().lower())
    if canonical is None:
        return None
    return tr("cli.root.errors.did_you_mean_command", command=canonical)


__all__ = ["AeatTyperGroup"]
