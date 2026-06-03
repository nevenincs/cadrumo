"""``aeat config init`` command skeleton (P05.S01).

Wires the typer command signature for the secure-backend passkey-bucket
``init`` verb per
:doc:`.vault/plan/2026-05-14-secure-backend-passkey-bucket-plan` Phase
P05.S01.  The wizard flow that walks the operator through passphrase
choice, BIP-39 recovery presentation, and bucket provisioning lands in
P06.S01; this module establishes the command shape and its
non-interactive refusal contract only.

Non-interactive contract (ADR-1 § 2, 4): the command refuses to mint a
bucket unless both ``AEAT_SECRET_PASSPHRASE`` is set in the environment
AND ``--accept-data-loss-risk`` is passed. The two-key gate matches the
data-loss surface a forgotten passphrase opens: an at-rest passphrase
that the application cannot recover is the operator's sole defence
against decryption-side compromise, and a passphrase chosen without
explicit risk acknowledgement is the canonical "bucket I cannot ever
read again" failure mode the gate exists to prevent.
"""

from __future__ import annotations

import os
import typing

import typer

from ....core.i18n import tr


def register(app: typer.Typer) -> None:
    """Mount the ``aeat config init`` verb onto ``app``."""

    @app.command(
        "init",
        help=tr(
            "cli.config.init.help",
            default="Mint a new passphrase-protected bucket and bind it to the workflow pointer.",
        ),
    )
    def _init(
        accept_data_loss_risk: typing.Annotated[
            bool,
            typer.Option(
                "--accept-data-loss-risk",
                help=tr(
                    "cli.config.init.accept_data_loss_risk_help",
                    default=(
                        "Acknowledge the operator-side data-loss risk: a forgotten "
                        "passphrase makes the bucket unreadable. Required for "
                        "non-interactive mint."
                    ),
                ),
            ),
        ] = False,
        persist_recovery_wrap: typing.Annotated[
            bool,
            typer.Option(
                "--persist-recovery-wrap",
                help=tr(
                    "cli.config.init.persist_recovery_wrap_help",
                    default=(
                        "Persist the BIP-39 recovery-wrapped DEK alongside the bucket "
                        "(ADR-1 § 4). Without this flag the recovery wrap is shown "
                        "once and not retained on disk."
                    ),
                ),
            ),
        ] = False,
    ) -> None:
        """Refuse non-interactive mint unless the two-key contract is satisfied.

        The wizard-driven interactive flow lands in P06.S01; this Step
        wires the command shape only. The current body refuses the
        non-interactive mint when the operator-side preconditions
        (`AEAT_SECRET_PASSPHRASE` environment variable AND
        ``--accept-data-loss-risk`` flag) are not both satisfied. The
        ``--persist-recovery-wrap`` flag is captured here and consumed by
        the P06 wizard body.
        """
        passphrase_present = bool(os.environ.get("AEAT_SECRET_PASSPHRASE", "").strip())
        if not passphrase_present or not accept_data_loss_risk:
            message = tr(
                "cli.config.init.errors.non_interactive_refused",
                default=(
                    "non-interactive mint refused: set AEAT_SECRET_PASSPHRASE "
                    "in the environment AND pass --accept-data-loss-risk. The "
                    "interactive wizard flow lands in P06.S01."
                ),
            )
            typer.echo(message, err=True)
            raise typer.Exit(code=2)
        # P06.S01 lands the wizard / mint body. Until then the
        # two-key gate refuses the non-interactive path and the
        # interactive path is not reachable, so this skeleton exits
        # without minting. The behaviour is explicitly tested for in
        # ``test_init_command_shape``: the command parses cleanly with
        # the new flags and the refusal is deterministic.
        del persist_recovery_wrap  # captured for P06 wizard body
        typer.echo(
            tr(
                "cli.config.init.errors.wizard_not_landed",
                default="bucket mint wizard body lands in P06.S01; non-interactive path is the only surface in P05.",
            ),
            err=True,
        )
        raise typer.Exit(code=2)


__all__ = ["register"]
