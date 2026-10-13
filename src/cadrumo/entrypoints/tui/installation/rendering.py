"""Turn how an act settled into what the person reads.

Every reply renders through one derived path: its members as labelled lines,
the way the command line prints a result. A few replies also get a table or a
one-word verdict, which adds to the derived lines and never replaces the path.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from ....application.operator_output.runtime_remedies import runtime_unavailable_remedy
from ....application.runtime.installation_requests import (
    InstallationAct,
    InstallationActContract,
    RuntimeInstallationCompleted,
    RuntimeInstallationRefused,
    RuntimeProfileListReply,
    RuntimeReportVerifyDocumentReply,
    RuntimeReviewPackageVerifyReceiptReply,
    RuntimeReviewPackageVerifyReply,
    RuntimeReviewPackageVerifySignatureReply,
    RuntimeStorageInventoryReply,
)
from ....core.i18n.render import tr
from ..components.status import StatusTone
from ..operations.refusal_explanation import operation_error_explanation, recorded_remedy_line
from .door import ActCompleted, ActFailed, ActOutcome, ActRefused, ActSecretDeclined, ActUnreachable
from .texts import yes_no

#: Reply members that correlate the exchange and say nothing about the act.
_COORDINATES = frozenset({"request_id", "runtime_boot_id", "connection_id", "kind"})


@dataclass(frozen=True, slots=True)
class ResultTable:
    """Rows a reply is easier to read as a table."""

    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class ActPresentation:
    """One settled act as the screen shows it."""

    tone: StatusTone
    status: str
    lines: tuple[str, ...]
    table: ResultTable | None = None
    outcome_read_by: InstallationAct | None = None
    """The read that says how this act ended, when nobody was told."""


def _scalar_text(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return yes_no(value)
    return str(value)


def _is_scalar(value: object) -> bool:
    return not isinstance(value, Mapping | list)


def _sequence_lines(key: str, values: Sequence[object], pad: str, width: int) -> Iterator[str]:
    if not values:
        yield f"{pad}{key:<{width}}  -"
        return
    yield f"{pad}{key}:"
    for item in values:
        if isinstance(item, Mapping):
            nested = list(_mapping_lines(item, pad + "    "))
            yield f"{pad}  - {nested[0].strip()}" if nested else f"{pad}  -"
            yield from nested[1:]
        else:
            yield f"{pad}  {_scalar_text(item)}"


def _mapping_lines(document: Mapping[str, object], pad: str) -> Iterator[str]:
    width = max((len(key) for key, value in document.items() if _is_scalar(value)), default=0)
    for key, value in document.items():
        if isinstance(value, Mapping):
            yield f"{pad}{key}:"
            yield from _mapping_lines(value, pad + "  ")
        elif isinstance(value, list):
            yield from _sequence_lines(key, value, pad, width)
        else:
            yield f"{pad}{key:<{width}}  {_scalar_text(value)}"


def reply_lines(reply: RuntimeInstallationCompleted) -> tuple[str, ...]:
    """Render every member of a reply as labelled lines, nested members indented."""
    document = reply.model_dump(mode="json", exclude=set(_COORDINATES))
    return tuple(_mapping_lines(document, ""))


def _verdict(reply: RuntimeInstallationCompleted) -> bool | None:
    """Read the yes-or-no answer a verification reply gives, when it gives one."""
    if isinstance(reply, RuntimeReviewPackageVerifySignatureReply | RuntimeReviewPackageVerifyReceiptReply):
        return reply.is_valid
    if isinstance(reply, RuntimeReviewPackageVerifyReply):
        return reply.is_clean
    return None


def _table(reply: RuntimeInstallationCompleted) -> ResultTable | None:
    if isinstance(reply, RuntimeStorageInventoryReply):
        return ResultTable(
            columns=(
                tr("cli.config.storage.labels.area"),
                tr("cli.config.storage.labels.lifecycle"),
                tr("cli.config.storage.labels.occupancy"),
                tr("cli.config.storage.labels.entries"),
                tr("cli.config.storage.labels.footprint"),
                tr("cli.config.storage.labels.reclaimable"),
            ),
            rows=tuple(
                (
                    row.area.value,
                    row.disposition.value,
                    row.occupancy.value,
                    str(row.entry_count),
                    f"{row.footprint_bytes} B",
                    yes_no(row.reclaimable),
                )
                for row in ([reply.area] if reply.area is not None else reply.areas or [])
            ),
        )
    if isinstance(reply, RuntimeProfileListReply):
        return ResultTable(
            columns=(
                tr("tui.installation.profiles.column.label"),
                tr("tui.installation.profiles.column.id"),
                tr("tui.installation.profiles.column.active"),
            ),
            rows=tuple((profile.name, profile.bucket_id, yes_no(profile.active)) for profile in reply.profiles),
        )
    return None


def _completed(outcome: ActCompleted, *, preview: bool) -> ActPresentation:
    reply = outcome.reply
    lines = list(reply_lines(reply))
    tone: StatusTone = "success"
    status = tr("tui.installation.status.preview") if preview else tr("tui.installation.status.completed")
    verdict = _verdict(reply)
    if verdict is not None:
        status = tr("tui.installation.verdict.valid") if verdict else tr("tui.installation.verdict.invalid")
        tone = "success" if verdict else "error"
    elif isinstance(reply, RuntimeReportVerifyDocumentReply):
        status = tr("tui.installation.verdict.outcome", outcome=reply.outcome)
    return ActPresentation(tone=tone, status=status, lines=tuple(lines), table=_table(reply))


def _refused(reply: RuntimeInstallationRefused, *, preview: bool) -> ActPresentation:
    detail = reply.detail
    code = detail.error_code or detail.kind.value
    lines: list[str] = []
    explanation = operation_error_explanation(detail)
    if explanation is not None and explanation:
        lines.append(explanation)
    lines.extend(_mapping_lines(detail.context_mapping(), ""))
    verdict = detail.precondition_verdict()
    if verdict is not None and verdict.action is not None:
        lines.append(tr("tui.installation.result.remedy", action=verdict.action.action_id))
    remedy = recorded_remedy_line(detail)
    if remedy is not None:
        lines.append(remedy)
    return ActPresentation(
        tone="warning" if preview else "error",
        status=tr("tui.installation.status.refused", code=code),
        lines=tuple(lines),
    )


def _failed(outcome: ActFailed, contract: InstallationActContract) -> ActPresentation:
    key_status = (
        tr("tui.installation.status.failed_unknown", act=outcome.reply.act.value)
        if outcome.may_have_changed_records
        else tr("tui.installation.status.failed", act=outcome.reply.act.value)
    )
    return ActPresentation(
        tone="error",
        status=key_status,
        lines=(),
        outcome_read_by=contract.outcome_read_by if outcome.may_have_changed_records else None,
    )


def _unreachable(outcome: ActUnreachable, contract: InstallationActContract) -> ActPresentation:
    status = (
        tr("tui.installation.status.effect_unknown", code=outcome.code)
        if outcome.effect_unknown
        else tr("tui.installation.status.unreachable", code=outcome.code)
    )
    remedy = runtime_unavailable_remedy(outcome.code)
    return ActPresentation(
        # An act that may have run has not failed: its outcome is unknown, and is shown as that.
        tone="warning" if outcome.effect_unknown else "error",
        status=status,
        lines=() if remedy is None else (remedy,),
        outcome_read_by=contract.outcome_read_by if outcome.effect_unknown else None,
    )


def present_outcome(
    outcome: ActOutcome, contract: InstallationActContract, *, preview: bool = False
) -> ActPresentation:
    """Render one settled act.

    Args:
        outcome: How the act settled.
        contract: The act's row of the runtime's table.
        preview: Whether the act was sent without confirmation to show what a
            confirmed one would do. A refusal is then information, not an error.
    """
    if isinstance(outcome, ActCompleted):
        return _completed(outcome, preview=preview)
    if isinstance(outcome, ActRefused):
        return _refused(outcome.reply, preview=preview)
    if isinstance(outcome, ActFailed):
        return _failed(outcome, contract)
    if isinstance(outcome, ActSecretDeclined):
        return ActPresentation(tone="warning", status=tr("tui.installation.status.recovery_declined"), lines=())
    return _unreachable(outcome, contract)


__all__ = ["ActPresentation", "ResultTable", "present_outcome", "reply_lines"]
