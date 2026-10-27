"""Plain wording for setup items: one sentence per state or failure, one label per button.

Every surface renders setup status through this module, so the person reads
the same sentence everywhere and never a category, an operation id or an
internal term. The sentences live once in the ``application.provisioning``
subtree of the locale catalogues, in every supported language.

The native component engine emits only closed codes; each Python surface
words them here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..core.i18n.render import tr
from .dependency_contracts import (
    DependencyBlockedReason,
    DependencyItemDeclaration,
    DependencyRecoveryAction,
    DependencyStaleReason,
    DependencyState,
    DependencyStatusRow,
)
from .operator_actions.models import PreconditionVerdict
from .provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID

__all__ = [
    "DEPENDENCY_WORDING_ROOT",
    "DependencyRowWording",
    "column_reader_refusal_reason",
    "dependency_action_key",
    "dependency_desktop_pointer",
    "dependency_failure_key",
    "dependency_held_sentence",
    "dependency_name_key",
    "dependency_row_wording",
    "dependency_sentence_key",
    "dependency_space_sentence",
    "statement_reader_refusal_reason",
]

DEPENDENCY_WORDING_ROOT: Final = "application.provisioning"

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
    """What a surface shows for one item: its name, its sentence and its button label."""

    name: str
    sentence: str
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
        action=None if row.recovery is None else tr(dependency_action_key(row.recovery), locale=locale),
    )


def dependency_desktop_pointer(*, locale: str | None = None) -> str:
    """Render the sentence that sends the person to the desktop app, where the local AI is set up."""
    return tr(_key("in_desktop"), locale=locale)


def dependency_held_sentence(
    row: DependencyStatusRow, declaration: DependencyItemDeclaration, *, locale: str | None = None
) -> str:
    """Say what holds an item a surface cannot offer to set up: its name, then its row's own sentence.

    A surface shows this where a refusal names the item's setup but the row's
    button cannot set it up now, so the person reads why instead of an offer.
    A row whose setup only the desktop performs ends with the pointer to it.
    """
    wording = dependency_row_wording(row, declaration, locale=locale)
    held = f"{wording.name}: {wording.sentence}"
    if row.recovery is DependencyRecoveryAction.SET_UP_IN_DESKTOP:
        return f"{held} {dependency_desktop_pointer(locale=locale)}"
    return held


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
