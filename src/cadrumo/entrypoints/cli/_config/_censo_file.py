"""``aeat config profile censo file`` — censal artefact ingestion.

The one file-transport door for the Certificado de Situación Censal
(procedure G313) the operator downloads from Sede themselves: `file
--file PATH` per the CLI pull-and-file standard (the `pull` sibling is
retired with the live censo scrape and returns only under a future
accepted ADR). Parsing routes through the inbound censo adapter — today
structure-only, so every document meets an instructive refusal — and the
``--apply`` commit routes through the single cotejo apply authority
(:func:`~cadrumo.application.user_profile.apply_cotejo`, which delegates
to the manual-enrolment write path and emits exactly one
``CENSO_APPLIED`` per apply-commit; no parallel write route). Preview is
the default posture; ``--apply`` enrolls, always at the non-official
artefact evidence tier, so the calendar's ``censo.enrolment_unverified``
advisory is unaffected.
"""

from __future__ import annotations

from pathlib import Path

import typer

from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
from .._common import _emit_envelope

censo_app = typer.Typer(
    help=tr(
        "cli.config.profile.censo.help",
        default="Censal artefact ingestion for the active profile.",
    ),
    no_args_is_help=True,
)


def register_censo_commands(profile_app: typer.Typer) -> None:
    """Attach the ``censo`` sub-surface to ``config profile``."""
    profile_app.add_typer(censo_app, name="censo")


@censo_app.command(
    "file",
    help=tr(
        "cli.config.profile.censo.file_help",
        default="Read a downloaded Certificado de Situación Censal and preview or enroll its censal facts.",
    ),
)
def censo_file(
    ctx: typer.Context,
    file: Path = typer.Option(
        ...,
        "--file",
        exists=True,
        dir_okay=False,
        readable=True,
        help=tr(
            "cli.config.profile.censo.file_option_help",
            default="Path to the Certificado de Situación Censal PDF downloaded from Sede (procedure G313).",
        ),
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help=tr(
            "cli.config.profile.censo.apply_help",
            default="Enroll the parsed censal facts onto the active profile (default is preview only).",
        ),
    ),
) -> None:
    """Parse the certificate and preview — or with ``--apply``, enroll — its censal facts."""
    from ....adapters.inbound.censo import parse_certificado_censal_bytes
    from ....application.user_profile import apply_cotejo
    from ....application.workflow import workflow_state_repository
    from ....domain.censo import censo_facts_from_certificado
    from .._config_payloads import CensoFileFactPayload, CensoFileIngestResult

    certificado = parse_certificado_censal_bytes(file.read_bytes())
    facts = censo_facts_from_certificado(certificado)

    if apply:
        # The file door is the adopt-all shape of the cotejo apply: every
        # mapped censo fact is adopted, none deferred. Route it through the
        # single apply authority (never a parallel ``set_active_fields``
        # write) so a censal artefact-apply always emits exactly one
        # ``CENSO_APPLIED`` event, at the non-official evidence tier.
        # Declaring zero deferred means the namespace-replace clears every
        # pre-existing open divergence: a full adopt-all reconciliation
        # cannot coherently leave a prior deferral standing.
        repository = workflow_state_repository()
        state = repository.load()
        repository.save(apply_cotejo(state, adopted=facts, divergences=()))

    rows = tuple(CensoFileFactPayload(path=fact.path, value=str(fact.value), source=fact.source) for fact in facts)
    result = CensoFileIngestResult(applied=apply, facts=rows)
    lines = [f"applied\t{str(apply).lower()}"]
    lines.extend(f"fact\t{row.path}\t{row.value}" for row in rows)
    notices = [
        Notice(
            code="config.profile.censo.non_official_tier",
            severity=NoticeSeverity.INFO,
            message=tr("cli.config.profile.censo.non_official_notice"),
        ),
    ]
    _emit_envelope(ctx, command="config.profile.censo.file", result=result, lines=lines, notices=notices)


__all__ = ["censo_app", "register_censo_commands"]
