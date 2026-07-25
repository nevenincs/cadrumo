"""``aeat config profile censo`` — the two censal ingestion doors.

Both transports of the CLI pull-and-file standard live here: ``pull``
reads the taxpayer's censal state live from AEAT's *Mis Datos Censales*
consulta, and ``file --file PATH`` reads a Certificado de Situación
Censal (procedure G313) the operator downloaded from Sede themselves.
They differ in transport and evidence tier, never in how they reconcile:
both commit through the single cotejo apply authority
(:func:`~cadrumo.application.user_profile.apply_cotejo`, which delegates
to the manual-enrolment write path and emits exactly one
``CENSO_APPLIED`` per apply-commit; no parallel write route), and both
default to preview with ``--apply`` as the commit door.

``file`` parses through the inbound censo adapter — today structure-only,
so every document meets an instructive refusal — and enrolls at the
non-official artefact evidence tier, leaving the calendar's
``censo.enrolment_unverified`` advisory standing. ``pull`` reads the
authority itself, so its facts carry the AEAT-verified censal-read token.
It writes only where the operator has declared nothing to lose: a path
never set, or one whose current value a previous censal read wrote and
the authority has since changed. A value the operator declared, and a
path they deliberately cleared, are reported for them to adjudicate.

What ``pull`` fills is identity and address, and only that: the censal
regime fields have no working read route, so the verb neither promises
nor writes them. The read is always of the authenticated session's own
record — there is no option to aim it at another taxpayer, because the
product does not support acting as a representative. Its result reports
all three outcomes, adopted, unchanged and diverging: a path the profile
already holds at the authority's value is a no-op to write but not a
no-op to report, and hiding it would leave an operator unable to tell a
corroborated field from one the read never covered.
"""

from __future__ import annotations

from pathlib import Path

import typer

from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
from .._common import _emit_envelope, _state
from ._censo_payloads import CensoPullDivergencePayload, CensoPullFactPayload, CensoPullResult

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


@censo_app.command(
    "pull",
    help=tr(
        "cli.config.profile.censo.pull_help",
        default=(
            "Read your identity and address from AEAT's censal record and "
            "preview or enroll them onto the active profile."
        ),
    ),
)
def censo_pull(
    ctx: typer.Context,
    apply: bool = typer.Option(
        False,
        "--apply",
        help=tr(
            "cli.config.profile.censo.apply_help",
            default="Enroll the parsed censal facts onto the active profile (default is preview only).",
        ),
    ),
) -> None:
    """Read the censal consulta and preview — or with ``--apply``, enroll — its facts."""
    import asyncio

    from ....application.live import pull_censal_datos
    from ....application.user_profile import (
        apply_censal_read,
        censal_facts_from_read,
        reconcile_censal_read,
        record_to_effective_facts,
    )
    from ....application.workflow import workflow_state_repository

    # Refuse an absent active profile before the read, not after: the live
    # navigation can trigger a Cl@ve push, and asking the operator to
    # authenticate for a reconciliation that has no profile to land on
    # would spend their second factor on nothing.
    state = _state()
    record = state.active_profile_record()

    read = asyncio.run(pull_censal_datos())
    projected = censal_facts_from_read(read)
    reconciliation = reconcile_censal_read(record, projected)
    # Read the EFFECTIVE facts, not the value projection: a path the
    # operator cleared survives here as ``value=None`` where the value
    # projection drops it entirely. That distinction is the whole
    # difference between "they declared something else" and "they deleted
    # this", and the two must not render alike.
    effective = record_to_effective_facts(record)

    if apply:
        # The live door adopts only the blank paths and defers every
        # disagreement, but it commits through the SAME single apply
        # authority the artefact door uses, so one ``CENSO_APPLIED`` marks
        # the commit and the deferred axes land in the one
        # ``censo.divergencia`` namespace an operator reviews.
        workflow_state_repository().save(apply_censal_read(state, read))

    adopted = tuple(
        CensoPullFactPayload(path=fact.path, value=str(fact.value), source=fact.source)
        for fact in reconciliation.adopted
    )
    divergences = tuple(
        CensoPullDivergencePayload(
            path=path,
            profile_value=(fact.value if (fact := effective.get(path)) is not None else None),
            aeat_value=value,
        )
        for path, value in reconciliation.divergences
    )
    # The read's third outcome. The reconciliation emits a path the profile
    # already holds at the authority's value as neither an adoption nor a
    # disagreement, because it is a no-op to WRITE; it is not a no-op to
    # REPORT. Derived here from the projection rather than re-decided, so
    # the split stays the authority's.
    decided = {fact.path for fact in reconciliation.adopted} | {path for path, _ in reconciliation.divergences}
    unchanged = tuple(
        CensoPullFactPayload(path=fact.path, value=str(fact.value), source=fact.source)
        for fact in projected
        if fact.path not in decided
    )
    result = CensoPullResult(
        applied=apply,
        source_url=str(read.source_url),
        adopted=adopted,
        unchanged=unchanged,
        divergences=divergences,
    )
    lines = [f"applied\t{str(apply).lower()}", f"source_url\t{read.source_url}"]
    lines.extend(f"adopted\t{row.path}\t{row.value}" for row in adopted)
    lines.extend(f"unchanged\t{row.path}\t{row.value}" for row in unchanged)
    lines.extend(
        f"divergence\t{row.path}\tprofile={'<cleared>' if row.profile_value is None else row.profile_value}"
        f"\taeat={row.aeat_value}"
        for row in divergences
    )
    # Fold every notice into the text output too. The envelope renders
    # `notices` only in JSON mode, so a diagnostic left off `lines` is
    # invisible to an operator running the verb plainly - and the warning
    # that AEAT disagrees with them is the last thing that should be
    # visible only to automation. Rebuilding both from one notice list is
    # what keeps the two renderings from drifting apart.
    notices = _pull_notices(applied=apply, adopted=adopted, divergences=divergences)
    lines.extend(f"{notice.severity.value.upper()}\t{notice.message}" for notice in notices)
    _emit_envelope(
        ctx,
        command="config.profile.censo.pull",
        result=result,
        lines=lines,
        notices=notices,
    )


def _values_are_withheld(row: CensoPullDivergencePayload) -> bool:
    """Return whether the envelope will mask this row's values before the operator sees them.

    Asked of the redaction funnel itself rather than answered from a list
    of identifier-bearing paths here: a second list would be a second
    authority on what is sensitive, and would go stale the moment the
    first one changed. A row whose values are masked cannot be
    adjudicated from the output alone, and saying so is better than
    printing two hashes and leaving the operator to work out why.
    """
    from ....core.redaction import redact_for_cli_output

    sides = [row.aeat_value] + ([] if row.profile_value is None else [row.profile_value])
    return any(redact_for_cli_output(side) != side for side in sides)


def _pull_notices(
    *,
    applied: bool,
    adopted: tuple[CensoPullFactPayload, ...],
    divergences: tuple[CensoPullDivergencePayload, ...],
) -> list[Notice]:
    """Build the pull's diagnostics: divergence warnings, tier and preview hints.

    Every diagnostic rides the typed notices channel; none is smuggled
    into the result payload as a bespoke advisory field.

    A disagreement over a value and a disagreement over a DELETION read
    differently to the operator, so they are separate notices. Someone who
    deliberately emptied a field and sees it named again deserves to be
    told it was not re-added, rather than to guess from a message about
    values they never declared.
    """
    notices: list[Notice] = []
    contested = tuple(row for row in divergences if row.profile_value is not None)
    cleared = tuple(row for row in divergences if row.profile_value is None)
    if contested:
        axes = ", ".join(row.path for row in contested)
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="config.profile.censo.pull.divergences",
                message=tr(
                    "cli.config.profile.censo.pull_divergences_notice",
                    default=(
                        "AEAT reports {count} field(s) differently from your declared answer: {axes}. "
                        "Your answer stands; resolve each one yourself."
                    ),
                    count=len(contested),
                    axes=axes,
                ),
                suggestion="aeat config profile edit",
                context={"count": str(len(contested)), "axes": axes},
            ),
        )
    withheld = tuple(row for row in divergences if _values_are_withheld(row))
    if withheld:
        axes = ", ".join(row.path for row in withheld)
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="config.profile.censo.pull.values_withheld",
                message=tr(
                    "cli.config.profile.censo.pull_withheld_notice",
                    default=(
                        "The values for {count} field(s) are withheld from output: {axes}. "
                        "Compare them yourself against AEAT; this tool will not print them."
                    ),
                    count=len(withheld),
                    axes=axes,
                ),
                context={"count": str(len(withheld)), "axes": axes},
            ),
        )
    if cleared:
        axes = ", ".join(row.path for row in cleared)
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="config.profile.censo.pull.cleared",
                message=tr(
                    "cli.config.profile.censo.pull_cleared_notice",
                    default=(
                        "AEAT still holds a value for {count} field(s) you cleared: {axes}. "
                        "They were left empty; clearing them here does not change AEAT's record."
                    ),
                    count=len(cleared),
                    axes=axes,
                ),
                suggestion="aeat config profile edit",
                context={"count": str(len(cleared)), "axes": axes},
            ),
        )
    if applied and adopted:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="config.profile.censo.pull.verified_tier",
                message=tr(
                    "cli.config.profile.censo.pull_verified_tier_notice",
                    default="These facts were read from AEAT itself, so the censo enrolment counts as verified.",
                ),
            ),
        )
    if not applied:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="config.profile.censo.pull.preview",
                message=tr(
                    "cli.config.profile.censo.pull_preview_notice",
                    default=(
                        "Preview only: nothing was written to the profile. Re-run with --apply to enroll these facts."
                    ),
                ),
                suggestion="aeat config profile censo pull --apply",
            ),
        )
    return notices


__all__ = ["censo_app", "register_censo_commands"]
