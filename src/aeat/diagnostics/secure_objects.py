"""Engineer-only ``secure-objects list NAMESPACE`` verb.

Inventories the secure-object index for one namespace, optionally
filtering to undecryptable rows. Lives under
``python -m aeat.diagnostics`` so the operator CLI never advertises
it. The previous home (``aeat config repair list NAMESPACE``) was
removed in the same commit that introduced this module.

The implementation delegates to
:func:`aeat.application.repair_integrity.build_repair_list_report`
so the report shape stays consistent with whatever the
application layer publishes.
"""

from __future__ import annotations

import typer

from ..application.repair_integrity import build_repair_list_report


def register(app: typer.Typer) -> None:
    """Mount the ``secure-objects`` sub-app onto ``app``."""

    sub = typer.Typer(
        name="secure-objects",
        help="Inventory the secure-object index by namespace.",
        no_args_is_help=True,
    )

    @sub.command("list", help="List secure-object keys stored under one namespace.")
    def _list(
        namespace: str = typer.Argument(..., help="Namespace to inventory."),
        include_all: bool = typer.Option(
            False, "--all", help="Return every key, including unreadable rows."
        ),
        only_unreadable: bool = typer.Option(
            False, "--unreadable", help="Restrict the listing to undecryptable rows."
        ),
    ) -> None:
        if include_all and only_unreadable:
            raise typer.BadParameter(
                "--all and --unreadable cannot be combined; pass one or neither.",
            )
        report = build_repair_list_report(
            namespace=namespace,
            include_all=include_all,
            only_unreadable=only_unreadable,
        )
        typer.echo(f"namespace\t{namespace}")
        typer.echo(f"count\t{len(report.rows)}")
        for row in report.rows:
            typer.echo(f"{row.namespace}\t{row.object_key_digest}")

    app.add_typer(sub)
