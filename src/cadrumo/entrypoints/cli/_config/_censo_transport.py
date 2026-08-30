"""``aeat config profile censo`` — the two censal ingestion doors.

Both transports of the CLI pull-and-file standard live here: ``pull``
reads the taxpayer's censal state live from AEAT's *Mis Datos Censales*
consulta, and ``file --file PATH`` reads a Certificado de Situación
Censal (procedure G313) the operator downloaded from Sede themselves.
They differ in transport and evidence tier. Certificate files commit through
the single cotejo apply authority
(:func:`~cadrumo.application.user_profile.apply_cotejo`, which delegates
to the manual-enrolment write path and emits exactly one
``CENSO_APPLIED`` per apply-commit; no parallel write route). The live pull is
preview-only until its frontend can complete the canonical
``user-profile.censo-review`` interaction; ``--apply`` fails before acquisition
instead of bypassing that reviewed operation.

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
from typing import TYPE_CHECKING

import typer

from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
from .._common import _state, emit_envelope
from ._censo_payloads import CensoFactPayload, CensoFileIngestResult, CensoPullDivergencePayload, CensoPullResult

# The divergence helper selects one of these keys by data rather than passing a
# literal directly to ``tr()``. Keep the bounded selection scanner-visible so
# catalogue scaffold and parity cannot prune a live warning.
_LOCALE_KEYS: tuple[str, ...] = (
    "cli.config.profile.censo.pull_divergences_notice",
    "cli.config.profile.censo.pull_withheld_notice",
    "cli.config.profile.censo.pull_cleared_notice",
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ....application.user_profile.censo_sync import CensalReconciliation
    from ....domain.user_profile.values import UserProfileFact


def censo_import(
    ctx: typer.Context,
    file: Path,
    apply: bool = False,
) -> None:
    """Parse the certificate and preview — or with ``--apply``, enroll — its censal facts."""
    from ....adapters.inbound.censo import parse_certificado_censal_bytes
    from ....application.user_profile.cotejo_apply import apply_cotejo
    from ....application.workflow.persistence import workflow_state_repository
    from ....domain.censo import censo_facts_from_certificado

    certificado = parse_certificado_censal_bytes(file.read_bytes())
    facts = censo_facts_from_certificado(certificado)

    if apply:
        # The file door is the adopt-all shape of the cotejo apply: every
        # mapped censo fact is adopted, none deferred. Route it through the
        # single current-record apply authority (never a parallel fact writer)
        # write) so a censal artefact-apply always emits exactly one
        # ``CENSO_APPLIED`` event, at the non-official evidence tier.
        # Declaring zero deferred means the namespace-replace clears every
        # pre-existing open divergence: a full adopt-all reconciliation
        # cannot coherently leave a prior deferral standing.
        repository = workflow_state_repository()
        state = repository.load()
        repository.save(apply_cotejo(state, adopted=facts, divergences=()))

    rows = tuple(CensoFactPayload(path=fact.path, value=str(fact.value), source=fact.source) for fact in facts)
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
    emit_envelope(ctx, command="config.profile.censo.import", result=result, lines=lines, notices=notices)


def censo_pull(
    ctx: typer.Context,
    apply: bool = False,
) -> None:
    """Preview the censal consulta, refusing legacy direct apply before acquisition."""
    import asyncio

    from ....application.live.censo import pull_censal_datos
    from ....application.user_profile.censal_operation import CensalFieldIntent
    from ....application.user_profile.censo_sync import (
        CENSAL_ADOPTABLE_PATHS,
        CENSO_SOURCE_TAG,
        censal_facts_from_read,
        reconcile_censal_read,
    )
    from ....application.user_profile.projections import record_to_effective_facts
    from ....domain.user_profile.values import UserProfileFact
    from ....entrypoints.censal_review import run_censal_review
    from ._censo_review_cli import confirm_censal_review

    # Refuse an absent active profile before the read, not after: the live
    # navigation can trigger a Cl@ve push, and asking the operator to
    # authenticate for a reconciliation that has no profile to land on
    # would spend their second factor on nothing.
    state = _state()
    record = state.active_profile_record()

    # Read the EFFECTIVE facts, not the value projection: a path the
    # operator cleared survives here as ``value=None`` where the value
    # projection drops it entirely. That distinction is the whole
    # difference between "they declared something else" and "they deleted
    # this", and the two must not render alike.
    effective = record_to_effective_facts(record)

    if apply:
        from ....core.config import Settings

        reviewed = run_censal_review(actor_ref="operator:cli-censo", decide=confirm_censal_review)
        projected = tuple(
            UserProfileFact(path=field.path, value=field.observed_value, source=CENSO_SOURCE_TAG)
            for field in reviewed.projection.fields
            if field.observed_value is not None
        )
        adopted = tuple(
            CensoFactPayload(path=field.path, value=field.observed_value, source=CENSO_SOURCE_TAG)
            for field in reviewed.projection.fields
            if field.intent is CensalFieldIntent.ADOPT and field.observed_value is not None
        )
        divergences = tuple(
            CensoPullDivergencePayload(
                path=field.path,
                profile_value=(current.value if (current := effective.get(field.path)) is not None else None),
                aeat_value=field.observed_value,
            )
            for field in reviewed.projection.fields
            if field.intent is CensalFieldIntent.PRESERVE
            and field.observed_value is not None
            and ((current := effective.get(field.path)) is None or current.value != field.observed_value)
        )
        unchanged = tuple(
            CensoFactPayload(path=field.path, value=field.observed_value, source=CENSO_SOURCE_TAG)
            for field in reviewed.projection.fields
            if field.intent is CensalFieldIntent.PRESERVE
            and field.observed_value is not None
            and (current := effective.get(field.path)) is not None
            and current.value == field.observed_value
        )
        source_url = str(Settings.external_constants().aeat.domains.sede) + str(
            Settings.external_constants().aeat.sede_paths.censal_datos
        )
    else:
        read = asyncio.run(pull_censal_datos())
        projected = censal_facts_from_read(read)
        reconciliation = reconcile_censal_read(record, projected, incoming_identity=read.identity.nif)
        adopted = tuple(
            CensoFactPayload(path=fact.path, value=str(fact.value), source=fact.source)
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
        unchanged = _unchanged_facts(
            projected=projected,
            reconciliation=reconciliation,
            adoptable_paths=CENSAL_ADOPTABLE_PATHS,
        )
        source_url = str(read.source_url)

    result = CensoPullResult(
        applied=apply,
        source_url=source_url,
        adopted=adopted,
        unchanged=unchanged,
        divergences=divergences,
    )
    lines = _pull_lines(
        applied=apply,
        source_url=source_url,
        adopted=adopted,
        unchanged=unchanged,
        divergences=divergences,
    )
    # Fold every notice into the text output too. The envelope renders
    # `notices` only in JSON mode, so a diagnostic left off `lines` is
    # invisible to an operator running the verb plainly - and the warning
    # that AEAT disagrees with them is the last thing that should be
    # visible only to automation. Rebuilding both from one notice list is
    # what keeps the two renderings from drifting apart.
    notices = _pull_notices(applied=apply, adopted=adopted, divergences=divergences)
    lines.extend(f"{notice.severity.value.upper()}\t{notice.message}" for notice in notices)
    emit_envelope(
        ctx,
        command="config.profile.censo.pull",
        result=result,
        lines=lines,
        notices=notices,
    )


def _unchanged_facts(
    *,
    projected: Iterable[UserProfileFact],
    reconciliation: CensalReconciliation,
    adoptable_paths: Iterable[str],
) -> tuple[CensoFactPayload, ...]:
    """Project the read's third outcome: paths already at the authority's value.

    The reconciliation emits a path the profile already holds at AEAT's value
    as neither an adoption nor a disagreement, because it is a no-op to WRITE.
    It is not a no-op to REPORT. This derives that set from the projection
    rather than re-deciding it, so the split stays the authority's.

    Scoped to the adoptable paths, because the projection also carries the
    fiscal identity, which the reconciliation consumes to decide whether the
    read belongs to this profile at all and then skips. It is not an outcome
    of the reconciliation, so it belongs in none of the three lists: calling
    it unchanged would tell an operator whose profile carries no identity yet
    — the ordinary first-read case, which the ownership guard deliberately
    allows — that AEAT agrees with a value they never recorded.
    """
    adoptable = frozenset(adoptable_paths)
    decided = {fact.path for fact in reconciliation.adopted} | {path for path, _ in reconciliation.divergences}
    return tuple(
        CensoFactPayload(path=fact.path, value=str(fact.value), source=fact.source)
        for fact in projected
        if fact.path in adoptable and fact.path not in decided
    )


def _pull_lines(
    *,
    applied: bool,
    source_url: str,
    adopted: tuple[CensoFactPayload, ...],
    unchanged: tuple[CensoFactPayload, ...],
    divergences: tuple[CensoPullDivergencePayload, ...],
) -> list[str]:
    """Render the pull's tab-separated text rows, one per outcome."""
    lines = [f"applied\t{str(applied).lower()}", f"source_url\t{source_url}"]
    lines.extend(f"adopted\t{row.path}\t{row.value}" for row in adopted)
    lines.extend(f"unchanged\t{row.path}\t{row.value}" for row in unchanged)
    lines.extend(
        f"divergence\t{row.path}\tprofile={'<cleared>' if row.profile_value is None else row.profile_value}"
        f"\taeat={row.aeat_value}"
        for row in divergences
    )
    return lines


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


def _divergence_notice(
    rows: tuple[CensoPullDivergencePayload, ...],
    *,
    code: str,
    locale_key: str,
) -> Notice | None:
    """Build one divergence warning, or ``None`` when no row falls in its class.

    The three divergence classes render the same way — count the rows, name
    their paths, carry both on the notice context — and differ only in which
    rows they select and what they tell the operator to do about them. They
    deliberately carry no typed action: a disagreement is evidence for an
    operator's own adjudication, not authority to change a profile value.
    """
    if not rows:
        return None
    axes = ", ".join(row.path for row in rows)
    return Notice(
        severity=NoticeSeverity.WARNING,
        code=code,
        message=tr(locale_key, count=len(rows), axes=axes),
        context={"count": str(len(rows)), "axes": axes},
    )


def _pull_notices(
    *,
    applied: bool,
    adopted: tuple[CensoFactPayload, ...],
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
    return [*_divergence_notices(divergences), *_tier_notices(applied=applied, adopted=adopted)]


def _divergence_notices(divergences: tuple[CensoPullDivergencePayload, ...]) -> list[Notice]:
    """Warn about each class of disagreement the read surfaced.

    A disagreement over a VALUE and a disagreement over a DELETION read
    differently to the operator, so they are separate notices. Someone who
    deliberately emptied a field and sees it named again deserves to be told
    it was not re-added, rather than to guess from a message about values
    they never declared.
    """
    notices: list[Notice] = []
    for rows, code, locale_key in (
        (
            tuple(row for row in divergences if row.profile_value is not None),
            "config.profile.censo.pull.divergences",
            "cli.config.profile.censo.pull_divergences_notice",
        ),
        (
            tuple(row for row in divergences if _values_are_withheld(row)),
            "config.profile.censo.pull.values_withheld",
            "cli.config.profile.censo.pull_withheld_notice",
        ),
        (
            tuple(row for row in divergences if row.profile_value is None),
            "config.profile.censo.pull.cleared",
            "cli.config.profile.censo.pull_cleared_notice",
        ),
    ):
        notice = _divergence_notice(rows, code=code, locale_key=locale_key)
        if notice is not None:
            notices.append(notice)
    return notices


def _tier_notices(*, applied: bool, adopted: tuple[CensoFactPayload, ...]) -> list[Notice]:
    """State what the run actually did: enrolled at the verified tier, or previewed.

    Preview is intentionally actionless. Applying requires the canonical
    reviewed operation; this success notice cannot claim approval from its
    diagnostic payload.
    """
    notices: list[Notice] = []
    if applied and adopted:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="config.profile.censo.pull.verified_tier",
                message=tr(
                    "cli.config.profile.censo.pull_verified_tier_notice",
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
                ),
            ),
        )
    return notices


__all__ = ["censo_import", "censo_pull"]
