"""``aeat config profile censo`` — the two censal ingestion doors.

Both transports of the CLI pull-and-import standard live here: ``pull``
reads the taxpayer's censal state live from AEAT's *Mis Datos Censales*
consulta, and ``import --file PATH`` reads a Certificado de Situación
Censal (procedure G313) the operator downloaded from Sede themselves.
They differ in transport and evidence tier. Certificate files commit through
the single cotejo apply authority
(:func:`~cadrumo.application.user_profile.cotejo_apply.apply_cotejo`, which delegates
to the manual-enrolment write path and emits exactly one
``CENSO_APPLIED`` per apply-commit; no parallel write route). The file
``--apply`` path runs an exact-profile registered operation around that
authority. The live pull's ``--apply`` path completes the canonical
``user-profile.censo-review`` interaction through the authenticated runtime.

``import`` parses through the inbound censo adapter — today structure-only,
so every document meets an instructive refusal — and enrolls at the
non-official artefact evidence tier, leaving the calendar's
``censo.enrolment_unverified`` advisory standing. ``pull`` reads the
authority itself, so its facts carry the AEAT-verified censal-read token.
It writes only where the operator has declared nothing to lose: a path
never set, or one whose current value a previous censal read wrote and
the authority has since changed. A value the operator declared, and a
path they deliberately cleared, are reported for them to adjudicate.

The live observation includes identity, addresses, activities, premises,
tax status and obligations. Profile adoption uses the existing supported
address mappings; captured regime rows are evidence, not inferred profile
settings. The read is always of the authenticated session's own
record — there is no option to aim it at another taxpayer, because the
product does not support acting as a representative. Its result reports
all three outcomes, adopted, unchanged and diverging: a path the profile
already holds at the authority's value is a no-op to write but not a
no-op to report, and hiding it would leave an operator unable to tell a
corroborated field from one the read never covered.

Core types:
:class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import typer

from ....core.i18n.render import tr
from ....core.json_contract import Notice, NoticeSeverity
from ..common import emit_envelope
from ._censo_payloads import (
    CensoFactPayload,
    CensoFileIngestResult,
    CensoPullDivergencePayload,
    CensoPullResult,
    CensoStoredResult,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from ....application.user_profile.censal_operation import CensalReviewFieldProjectionV1, CensalReviewProjectionV1
    from ....application.user_profile.censal_prepare_operation import CensalPrepareOperationProjection
    from ....application.user_profile.censal_preview_operation import CensalPreviewOperationResult


class _EffectiveValue(Protocol):
    @property
    def value(self) -> str | None: ...


class _ReviewedCensalResult(Protocol):
    @property
    def projection(self) -> CensalReviewProjectionV1: ...

    @property
    def applied(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class _PreparedEffectiveValue:
    value: str | None


def _effective_from_prepare(projection: CensalPrepareOperationProjection) -> dict[str, _EffectiveValue]:
    """Retain explicit clears while omitting only genuinely unset paths."""
    from ....application.user_profile.censal_prepare_operation import CensalPrepareFieldState

    return {
        field.path: _PreparedEffectiveValue(field.effective_value)
        for field in projection.effective_fields
        if field.state is not CensalPrepareFieldState.UNSET
    }


def censo_import(
    ctx: typer.Context,
    file: Path,
    apply: bool = False,
) -> None:
    """Parse the certificate and preview — or with ``--apply``, enroll — its censal facts."""
    from ....adapters.inbound.censo.parser import parse_certificado_censal_bytes
    from ....domain.censo.certificado import censo_facts_from_certificado

    certificado = parse_certificado_censal_bytes(file.read_bytes())
    facts = censo_facts_from_certificado(certificado)

    if apply:
        from .runtime_censal_file_import import import_censal_file_facts

        receipt = import_censal_file_facts(ctx, facts)
        apply = receipt.applied

    rows = tuple(CensoFactPayload(path=fact.path, value=str(fact.value), source=fact.source) for fact in facts)
    result = CensoFileIngestResult(applied=apply, certificate=certificado, facts=rows)
    lines = _file_import_preview_lines(result)
    notices = [
        Notice(
            code="config.profile.censo.non_official_tier",
            severity=NoticeSeverity.INFO,
            message=tr("cli.config.profile.censo.non_official_notice"),
        ),
    ]
    emit_envelope(ctx, command="config.profile.censo.import", result=result, lines=lines, notices=notices)


def _file_import_preview_lines(result: CensoFileIngestResult) -> list[str]:
    """Keep all six certified axes visible alongside the separately adoptable facts."""
    return [
        f"applied\t{str(result.applied).lower()}",
        result.certificate.model_dump_json(indent=2),
        *(f"fact\t{row.path}\t{row.value}" for row in result.facts),
    ]


def censo_pull(
    ctx: typer.Context,
    apply: bool = False,
) -> None:
    """Preview the censal consulta or complete its registered reviewed apply."""
    from ..runtime_profile_binding import bound_profile_client
    from ._censo_review_cli import confirm_censal_review
    from .runtime_censal_prepare import prepare_censal_review
    from .runtime_censal_preview import preview_censal_with_runtime
    from .runtime_censal_review import review_censal_with_runtime

    if apply:
        prepared = prepare_censal_review(ctx)
        reviewed = review_censal_with_runtime(
            bound_profile_client(ctx),
            prepared.operation_request,
            decide=confirm_censal_review,
        )
        effective = _effective_from_prepare(prepared)
        adopted, unchanged, divergences, source_url = _reviewed_pull_outcomes(
            reviewed=reviewed,
            effective=effective,
        )
        # A rejected REVIEW exposes a proposal, not committed adoptions.
        # Report the operation's terminal decision rather than the CLI flag.
        apply = reviewed.applied
        if not apply:
            adopted = ()
        # The review result identifies its exact proposal. A separate latest
        # capture read could race another pull and misattribute its evidence.
        observation = None
    else:
        preview = preview_censal_with_runtime(ctx)
        adopted, unchanged, divergences, source_url = _projected_preview_outcomes(preview)
        observation = preview.observation

    result = CensoPullResult(
        applied=apply,
        source_url=source_url,
        adopted=adopted,
        unchanged=unchanged,
        divergences=divergences,
        observation=observation,
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


def censo_show(ctx: typer.Context) -> None:
    """Read the latest saved census through the existing exact-profile runtime door."""
    from .runtime_censal_prepare import prepare_censal_review

    observation = prepare_censal_review(ctx).observation
    result = CensoStoredResult(observation=observation)
    lines = ["captured\tfalse"] if observation is None else [observation.model_dump_json(indent=2)]
    emit_envelope(ctx, command="config.profile.censo.show", result=result, lines=lines)


def _reviewed_adopted_payloads(
    fields: Iterable[CensalReviewFieldProjectionV1],
) -> tuple[CensoFactPayload, ...]:
    from ....application.user_profile.censal_operation import CensalFieldIntent
    from ....application.user_profile.censo_sync import CENSO_SOURCE_TAG

    return tuple(
        CensoFactPayload(path=field.path, value=field.observed_value, source=CENSO_SOURCE_TAG)
        for field in fields
        if field.intent is CensalFieldIntent.ADOPT and field.observed_value is not None
    )


def _reviewed_divergence_payloads(
    fields: Iterable[CensalReviewFieldProjectionV1],
    effective: Mapping[str, _EffectiveValue],
) -> tuple[CensoPullDivergencePayload, ...]:
    from ....application.user_profile.censal_operation import CensalFieldIntent

    return tuple(
        CensoPullDivergencePayload(
            path=field.path,
            profile_value=(current.value if (current := effective.get(field.path)) is not None else None),
            aeat_value=field.observed_value,
        )
        for field in fields
        if field.intent is CensalFieldIntent.PRESERVE
        and field.observed_value is not None
        and not _reviewed_values_match((current := effective.get(field.path)), field.observed_value)
    )


def _reviewed_values_match(current: _EffectiveValue | None, observed: str) -> bool:
    """Use the canonical censal comparison: trim surrounding whitespace only."""
    return current is not None and current.value is not None and current.value.strip() == observed.strip()


def _reviewed_unchanged_payloads(
    fields: Iterable[CensalReviewFieldProjectionV1],
    effective: Mapping[str, _EffectiveValue],
) -> tuple[CensoFactPayload, ...]:
    from ....application.user_profile.censal_operation import CensalFieldIntent
    from ....application.user_profile.censo_sync import CENSO_SOURCE_TAG

    return tuple(
        CensoFactPayload(path=field.path, value=field.observed_value, source=CENSO_SOURCE_TAG)
        for field in fields
        if field.intent is CensalFieldIntent.PRESERVE
        and field.observed_value is not None
        and _reviewed_values_match(effective.get(field.path), field.observed_value)
    )


def _reviewed_pull_outcomes(
    *,
    reviewed: _ReviewedCensalResult,
    effective: Mapping[str, _EffectiveValue],
) -> tuple[
    tuple[CensoFactPayload, ...],
    tuple[CensoFactPayload, ...],
    tuple[CensoPullDivergencePayload, ...],
    str,
]:
    from ....core.config import Settings

    fields = reviewed.projection.fields
    adopted = _reviewed_adopted_payloads(fields)
    divergences = _reviewed_divergence_payloads(fields, effective)
    unchanged = _reviewed_unchanged_payloads(fields, effective)
    source_url = str(Settings.external_constants().aeat.domains.sede) + str(
        Settings.external_constants().aeat.sede_paths.censal_datos
    )
    return adopted, unchanged, divergences, source_url


def _projected_preview_outcomes(
    projection: CensalPreviewOperationResult,
) -> tuple[
    tuple[CensoFactPayload, ...],
    tuple[CensoFactPayload, ...],
    tuple[CensoPullDivergencePayload, ...],
    str,
]:
    """Render the worker's complete reconciliation without redeciding it."""
    adopted = tuple(CensoFactPayload(path=row.path, value=row.value, source=row.source) for row in projection.adopted)
    unchanged = tuple(
        CensoFactPayload(path=row.path, value=row.value, source=row.source) for row in projection.unchanged
    )
    divergences = tuple(
        CensoPullDivergencePayload(
            path=row.path,
            profile_value=row.profile_value,
            aeat_value=row.aeat_value,
        )
        for row in projection.divergences
    )
    return adopted, unchanged, divergences, str(projection.source_url)


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
    from ....core.redaction.rules import redact_for_cli_output

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


__all__ = ["censo_import", "censo_pull", "censo_show"]
