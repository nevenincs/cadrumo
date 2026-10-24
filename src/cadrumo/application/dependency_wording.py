"""Plain wording for setup items: one sentence per state or failure, one label per button.

Every surface renders setup status through this module, so the person reads
the same sentence everywhere and never a category, an operation id or an
internal term. The sentences live once in the ``application.provisioning``
subtree of the locale catalogues, in every supported language.

``dependency_copy_details`` is the one technical view: a redacted report a
person can paste into a support request. It names categories, versions,
phases, hosts and the operation id, and carries no token, no file path and no
profile value.

``dependency_wording_view`` is the worded part of every setup result and
review: each row's words, every item's name, every failure's sentence, the
retry notice and the details, in one language. A frontend that cannot call
``tr()`` shows these words as they come, so every surface reads the same.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

from pydantic import BaseModel

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..core.i18n.render import tr
from ..core.model_catalogue import ModelRole
from ..core.models import STRICT_FROZEN_CONFIG
from .dependency_contracts import (
    DependencyBlockedReason,
    DependencyItemDeclaration,
    DependencyItemId,
    DependencyNote,
    DependencyRecoveryAction,
    DependencyStaleReason,
    DependencyState,
    DependencyStatusRow,
)
from .operator_actions.models import PreconditionVerdict
from .provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID

__all__ = [
    "DEPENDENCY_RETRY_PLACEHOLDERS",
    "DEPENDENCY_WORDING_ROOT",
    "DependencyFailureWordingV1",
    "DependencyItemNameV1",
    "DependencyRowWording",
    "DependencyRowWordingV1",
    "DependencyWordingV1",
    "column_reader_refusal_reason",
    "dependency_action_key",
    "dependency_copy_details",
    "dependency_failure_key",
    "dependency_name_key",
    "dependency_note_key",
    "dependency_part_name",
    "dependency_retry_sentence",
    "dependency_row_wording",
    "dependency_sentence_key",
    "dependency_space_sentence",
    "dependency_wording_view",
    "statement_reader_refusal_reason",
]

DEPENDENCY_WORDING_ROOT: Final = "application.provisioning"
DEPENDENCY_RETRY_PLACEHOLDERS: Final = ("{attempt}", "{seconds}")
"""The two markers the worded retry notice keeps for a frontend to replace with the attempt and the wait."""

_STATE_KEYS: Final = {
    DependencyState.READY: "state.ready",
    DependencyState.ABSENT: "state.absent",
    DependencyState.PROVISIONING: "state.provisioning",
    DependencyState.VERIFYING: "state.verifying",
    DependencyState.UNKNOWN: "state.unknown",
    DependencyState.STALE: "state.stale",
    DependencyState.BLOCKED: "state.blocked",
    DependencyState.FAILED: "state.failed",
}


def _key(suffix: str) -> str:
    return f"{DEPENDENCY_WORDING_ROOT}.{suffix}"


def dependency_name_key(declaration: DependencyItemDeclaration) -> str:
    """Return the catalogue key of an item's plain name."""
    return f"application.{declaration.display_key}"


def dependency_failure_key(category: DependencyFailureCategory) -> str:
    """Return the catalogue key of a failure category's sentence."""
    return _key(f"failure.{category.value}")


def dependency_action_key(action: DependencyRecoveryAction) -> str:
    """Return the catalogue key of a recovery button's label."""
    return _key(f"action.{action.value}")


def dependency_note_key(note: DependencyNote) -> str:
    """Return the catalogue key of a usable item's note."""
    return _key(f"note.{note.value}")


def _stale_key(reason: DependencyStaleReason) -> str:
    return _key(f"stale.{reason.value}")


def _blocked_key(reason: DependencyBlockedReason) -> str:
    return _key(f"blocked.{reason.value}")


def dependency_sentence_key(row: DependencyStatusRow) -> str:
    """Return the catalogue key of the one sentence that states a row's state and reason."""
    if row.state is DependencyState.STALE and row.stale_reason is not None:
        return _stale_key(row.stale_reason)
    if row.state is DependencyState.BLOCKED and row.blocked_reason is not None:
        return _blocked_key(row.blocked_reason)
    if row.state is DependencyState.FAILED and row.failure_category is not None:
        return dependency_failure_key(row.failure_category)
    return _key(_STATE_KEYS[row.state])


@dataclass(frozen=True, slots=True)
class DependencyRowWording:
    """What a surface shows for one item: its name, its sentence, an optional note and button label."""

    name: str
    sentence: str
    note: str | None
    action: str | None


def dependency_row_wording(
    row: DependencyStatusRow, declaration: DependencyItemDeclaration, *, locale: str | None = None
) -> DependencyRowWording:
    """Render one row's plain wording in ``locale`` (the configured output language by default)."""
    if declaration.item_id != row.item_id:
        raise ValueError("wording declaration belongs to another setup item")
    return DependencyRowWording(
        name=tr(dependency_name_key(declaration), locale=locale),
        sentence=tr(dependency_sentence_key(row), locale=locale),
        note=None if row.note is None else tr(dependency_note_key(row.note), locale=locale),
        action=None if row.recovery is None else tr(dependency_action_key(row.recovery), locale=locale),
    )


_PROGRAM_PART: Final = "program"


def dependency_part_name(part_id: str, *, locale: str | None = None) -> str:
    """Render the plain name of one part of an item's plan: the local AI program, or one role's model."""
    if part_id == _PROGRAM_PART:
        return tr(_key("dependency.local_ai.program"), locale=locale)
    role = tr(f"provisioning.role.{ModelRole(part_id).value}", locale=locale)
    return tr(_key("dependency.local_ai.model"), role=role, locale=locale)


def dependency_retry_sentence(*, attempt: int, delay_s: int, locale: str | None = None) -> str:
    """Render the notice shown before a retry's wait."""
    return tr(_key("retry"), attempt=attempt, seconds=delay_s, locale=locale)


def dependency_space_sentence(*, required: str, free: str, locale: str | None = None) -> str:
    """Render the sentence naming both sizes of a full disk; the caller formats the sizes."""
    return tr(_key("space_needed"), required=required, free=free, locale=locale)


def column_reader_refusal_reason(verdict: PreconditionVerdict, *, locale: str | None = None) -> str:
    """Word why a file whose column names only the local AI reads was not read.

    Every import lane that needs the column-naming model gives this one reason,
    so the person reads the same sentence whichever lane refused. It names the
    local AI, and says to set it up only when ``verdict`` names that setup; a
    role this computer cannot run is told so without an action.
    """
    if verdict.action is not None and verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID:
        return tr("application.provisioning.refusal.column_names_local_ai_not_ready", locale=locale)
    return tr("application.provisioning.refusal.column_names_local_ai_unavailable", locale=locale)


def statement_reader_refusal_reason(verdict: PreconditionVerdict, *, locale: str | None = None) -> str:
    """Word why a PDF statement that only the local AI reads was not read.

    One reason whether the text or the scanned-page reader could not be asked,
    because the person meets one statement, not two readers. It says to set the
    local AI up only when ``verdict`` names that setup; a role this computer
    cannot run is told so without an action.
    """
    if verdict.action is not None and verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID:
        return tr("application.provisioning.refusal.statement_local_ai_not_ready", locale=locale)
    return tr("application.provisioning.refusal.statement_local_ai_unavailable", locale=locale)


def dependency_copy_details(
    rows: Iterable[DependencyStatusRow],
    *,
    operation_id: str | None = None,
    phases: Iterable[str] = (),
    hosts: Iterable[str] = (),
) -> str:
    """Return the redacted technical report "Copy details" puts on the clipboard.

    Only closed values and identifiers go in: item ids, states, reasons,
    categories, versions, the operation id, phase codes and host names. Facts
    are left out on purpose, because a fact can carry a path or a profile value.
    """
    lines = ["Cadrumo setup details"]
    if operation_id is not None:
        lines.append(f"operation: {operation_id}")
    for row in rows:
        reason = row.failure_category or row.blocked_reason or row.stale_reason
        parts = [f"item: {row.item_id}", f"state: {row.state.value}", f"check: {row.mode.value}"]
        if reason is not None:
            parts.append(f"reason: {reason.value}")
        if row.version is not None:
            parts.append(f"version: {row.version}")
        if row.note is not None:
            parts.append(f"note: {row.note.value}")
        lines.append("; ".join(parts))
    seen_phases = list(dict.fromkeys(phases))
    if seen_phases:
        lines.append("phases: " + ", ".join(seen_phases))
    seen_hosts = sorted(set(hosts))
    if seen_hosts:
        lines.append("hosts: " + ", ".join(seen_hosts))
    return "\n".join(lines) + "\n"


class DependencyItemNameV1(BaseModel):
    """One item's plain name."""

    model_config = STRICT_FROZEN_CONFIG

    item_id: DependencyItemId
    name: str


class DependencyRowWordingV1(BaseModel):
    """One row's words: its item's name, its sentence, an optional note and button label."""

    model_config = STRICT_FROZEN_CONFIG

    item_id: DependencyItemId
    name: str
    sentence: str
    note: str | None
    action: str | None


class DependencyFailureWordingV1(BaseModel):
    """One failure category's sentence."""

    model_config = STRICT_FROZEN_CONFIG

    category: DependencyFailureCategory
    sentence: str


class DependencyWordingV1(BaseModel):
    """Everything a setup result or review says, already in one language.

    ``retry`` keeps the markers of :data:`DEPENDENCY_RETRY_PLACEHOLDERS`: a
    retry is announced while the operation runs, and only the attempt and the
    wait change between announcements.
    """

    model_config = STRICT_FROZEN_CONFIG

    names: tuple[DependencyItemNameV1, ...]
    rows: tuple[DependencyRowWordingV1, ...]
    failures: tuple[DependencyFailureWordingV1, ...]
    retry: str
    details: str


def dependency_wording_view(
    rows: Iterable[DependencyStatusRow],
    declarations: Iterable[DependencyItemDeclaration],
    *,
    locale: str | None = None,
    operation_id: str | None = None,
    phases: Iterable[str] = (),
    hosts: Iterable[str] = (),
) -> DependencyWordingV1:
    """Word ``rows``, every declared item's name and every failure in ``locale``, with the details report."""
    declared = {declaration.item_id: declaration for declaration in declarations}
    settled = tuple(rows)
    worded: list[DependencyRowWordingV1] = []
    for row in settled:
        declaration = declared.get(row.item_id)
        if declaration is None:
            continue
        wording = dependency_row_wording(row, declaration, locale=locale)
        worded.append(
            DependencyRowWordingV1(
                item_id=row.item_id,
                name=wording.name,
                sentence=wording.sentence,
                note=wording.note,
                action=wording.action,
            )
        )
    attempt, seconds = DEPENDENCY_RETRY_PLACEHOLDERS
    return DependencyWordingV1(
        names=tuple(
            DependencyItemNameV1(item_id=item_id, name=tr(dependency_name_key(declaration), locale=locale))
            for item_id, declaration in declared.items()
        ),
        rows=tuple(worded),
        failures=tuple(
            DependencyFailureWordingV1(category=category, sentence=tr(dependency_failure_key(category), locale=locale))
            for category in DependencyFailureCategory
        ),
        retry=tr(_key("retry"), attempt=attempt, seconds=seconds, locale=locale),
        details=dependency_copy_details(settled, operation_id=operation_id, phases=phases, hosts=hosts),
    )
