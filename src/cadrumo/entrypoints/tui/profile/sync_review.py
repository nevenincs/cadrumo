"""Census field review and public operation-result projection for the TUI.

Every row and outcome rendered here is either a value the application layer
already computed (the suggested per-field intent, the AEAT-observed value
once a censal-review operation is under REVIEW) or a value legitimately read
through a public application door (the profile's own effective fact at a
path). Nothing here re-derives the adopt/preserve merge decision the
application layer owns, and nothing dispatches anything but the exact typed
public requests those doors declare.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, override

from pydantic import BaseModel
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, SelectionList, Static

from ....application.live.filed_history_operation import FiledHistoryPublicResultV1
from ....application.operations.events import OperationEventCode
from ....application.operations.frontend_contracts import (
    OperationPublicProjectionV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionResultV1,
)
from ....application.operations.models import OperationDiagnosticReference, OperationReference
from ....application.user_profile.censal_operation import (
    CensalFieldIntent,
    CensalOperationRequest,
    CensalProfileBaseline,
    CensalReviewedFieldIntent,
    CensalReviewProjectionV1,
)
from ....application.user_profile.presentation import ProfileFieldSourceClass, profile_field_source_class
from ....application.user_profile.projections import record_to_effective_facts
from ....core import STRICT_FROZEN_CONFIG
from ....core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ....domain.user_profile.values import UserProfileRecord
from ..components.theme import tokenised
from ..operations.controller import OperationController

_ADOPT = CensalFieldIntent.ADOPT
_PRESERVE = CensalFieldIntent.PRESERVE


@dataclass(frozen=True, slots=True)
class CensalFieldReviewRowV1:
    """One field's suggested disposition alongside its currently-declared value.

    ``observed_value`` is populated only once a submitted operation reaches
    its REVIEW interaction and the AEAT read is known; before submission it
    is always ``None`` — there is nothing to compare against yet.

    ``source`` is the persisted value's own provenance class, read through
    the same :func:`~application.user_profile.presentation.profile_field_source_class`
    authority the settled D6 presentation projection uses -- never a locally
    invented classification. ``has_conflict`` is a pure equality check, the
    same shape as :func:`censal_baseline_is_stale`: it names a divergence,
    it does not decide which side wins.
    """

    path: str
    persisted_value: str | None
    suggested_intent: CensalFieldIntent
    observed_value: str | None
    source: ProfileFieldSourceClass | None
    has_conflict: bool


def censal_field_review_rows(
    request: CensalOperationRequest,
    record: UserProfileRecord,
    *,
    projection: CensalReviewProjectionV1 | None = None,
) -> tuple[CensalFieldReviewRowV1, ...]:
    """Build display rows from an already-built request and the live record.

    ``request`` supplies the suggested per-path intent the application layer
    already computed (:func:`build_censal_operation_request`); this function
    only reads the profile's own current value at each path and, once given,
    matches the operation's REVIEW projection's observed value by path. It
    decides nothing about which intent is correct.
    """
    effective = record_to_effective_facts(record)
    observed_by_path = {} if projection is None else {item.path: item.observed_value for item in projection.fields}
    rows: list[CensalFieldReviewRowV1] = []
    for intent in request.field_intents:
        current = effective.get(intent.path)
        persisted_value = None if current is None else current.value
        observed_value = observed_by_path.get(intent.path)
        rows.append(
            CensalFieldReviewRowV1(
                path=intent.path,
                persisted_value=persisted_value,
                suggested_intent=intent.intent,
                observed_value=observed_value,
                source=None if current is None or current.value is None else profile_field_source_class(current.source),
                has_conflict=(
                    persisted_value is not None and observed_value is not None and persisted_value != observed_value
                ),
            )
        )
    return tuple(rows)


def censal_baseline_is_stale(baseline: CensalProfileBaseline, record: UserProfileRecord) -> bool:
    """Report whether the record has moved since the reviewed baseline was captured.

    A pure equality check on the same revision axis the backend itself
    re-confirms; it decides nothing about how to reconcile the divergence,
    only whether one exists.
    """
    return baseline.record_revision != record.record_revision


def censal_operation_request_from_selection(
    baseline: CensalProfileBaseline,
    rows: tuple[CensalFieldReviewRowV1, ...],
    selected_paths: frozenset[str],
) -> CensalOperationRequest:
    """Rebuild the typed request from the operator's per-field selection.

    ``selected_paths`` names every path the operator marked ADOPT; every
    other declared path is PRESERVE. The baseline is carried through
    unchanged — this function never mints a new one.
    """
    return CensalOperationRequest(
        baseline=baseline,
        field_intents=tuple(
            CensalReviewedFieldIntent(
                path=row.path,
                intent=_ADOPT if row.path in selected_paths else _PRESERVE,
            )
            for row in rows
        ),
    )


_FIELD_REVIEW_CSS = tokenised("""
#censal-field-review {
    border: $cadrumo-radius-overlay $accent;
    background: $surface;
    padding: $cadrumo-space-0 $cadrumo-space-1;
    width: 100%;
    height: auto;
}
#censal-field-review-title { text-style: bold; margin: $cadrumo-space-0; }
#censal-field-review-stale { color: $warning; margin: $cadrumo-space-0; }
#censal-field-review-actions {
    height: auto;
    align-horizontal: right;
    margin: $cadrumo-stack $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0;
}
#censal-field-review-actions Button { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap; }
""")


class CensalFieldReviewScreen(ModalScreen[CensalOperationRequest | None]):
    """Let the operator pick per-field ADOPT/PRESERVE, then dispatch the request.

    Dismisses with a rebuilt :class:`CensalOperationRequest` on accept, or
    ``None`` on reject. Never submits it: submission stays with the caller
    holding the composed operation services.
    """

    DEFAULT_CSS = _FIELD_REVIEW_CSS
    BINDINGS: ClassVar = []

    def __init__(
        self,
        baseline: CensalProfileBaseline,
        rows: tuple[CensalFieldReviewRowV1, ...],
        *,
        stale: bool,
        title: str,
        stale_message: str,
        apply_all_label: str,
        reject_label: str,
        confirm_label: str,
    ) -> None:
        """Store already-localized copy and the rows this dialog renders."""
        super().__init__()
        self._baseline = baseline
        self._rows = rows
        self._stale = stale
        self._title = title
        self._stale_message = stale_message
        self._apply_all_label = apply_all_label
        self._reject_label = reject_label
        self._confirm_label = confirm_label

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="censal-field-review"):
            yield Label(self._title, id="censal-field-review-title")
            if self._stale:
                yield Static(self._stale_message, id="censal-field-review-stale")
            yield SelectionList[str](
                *[(_row_label(row), row.path, row.suggested_intent is _ADOPT) for row in self._rows],
                id="censal-field-review-choices",
            )
            with Horizontal(id="censal-field-review-actions"):
                yield Button(self._reject_label, id="btn-censal-reject")
                yield Button(self._apply_all_label, id="btn-censal-apply-all")
                yield Button(self._confirm_label, id="btn-censal-confirm", classes="-primary")

    def on_mount(self) -> None:
        """Focus the field list as soon as the dialog opens."""
        self.query_one("#censal-field-review-choices", SelectionList).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch the rebuilt request, restore suggestions, or reject."""
        if event.button.id == "btn-censal-reject":
            self.dismiss(None)
            return
        choices = self.query_one("#censal-field-review-choices", SelectionList)
        if event.button.id == "btn-censal-apply-all":
            # SelectionList.select/deselect key on the option's VALUE (each
            # row's own path), never its list position -- passing the loop
            # index here silently no-ops, since no option's value is an int.
            for row in self._rows:
                if row.suggested_intent is _ADOPT:
                    choices.select(row.path)
                else:
                    choices.deselect(row.path)
            return
        selected_paths = frozenset(str(token) for token in choices.selected)
        self.dismiss(censal_operation_request_from_selection(self._baseline, self._rows, selected_paths))


def _row_label(row: CensalFieldReviewRowV1) -> str:
    # Parentheses, never brackets: a SelectionList option renders through Rich
    # markup, and "[token]" is a style tag the renderer would try to parse.
    provenance = "" if row.source is None else f" ({row.source.value})"
    if row.observed_value is None:
        return f"{row.path}: {row.persisted_value or '-'}{provenance}"
    marker = " ⚠" if row.has_conflict else ""
    return f"{row.path}: {row.persisted_value or '-'}{provenance} -> {row.observed_value}{marker}"


class FiledHistoryProgressSummaryV1(BaseModel):
    """The generic filed-history facts every public projection carries.

    Stage, lifecycle, terminal condition, effect, and refusal/diagnostic
    references, pulled straight from :class:`OperationPublicProjectionV1`.
    Visible at every point in the operation's life, including before
    settlement; the domain-specific evidence, IVA-wallet, notification, and
    provenance facts settle later and are resolved separately, through
    :func:`resolve_filed_history_result`, once the operation reaches a
    settlement that carries one.
    """

    model_config = STRICT_FROZEN_CONFIG

    stage: OperationEventCode | None
    lifecycle: OperationLifecycle
    terminal_condition: OperationTerminalCondition | None
    effect: OperationEffect
    refusal_ref: OperationReference | None
    diagnostic_ref: OperationDiagnosticReference | None


def filed_history_progress_summary(projection: OperationPublicProjectionV1) -> FiledHistoryProgressSummaryV1:
    """Project the generic public facts a filed-history operation exposes."""
    return FiledHistoryProgressSummaryV1(
        stage=projection.phase_code,
        lifecycle=projection.lifecycle,
        terminal_condition=projection.terminal_condition,
        effect=projection.effect,
        refusal_ref=projection.refusal_ref,
        diagnostic_ref=projection.diagnostic_ref,
    )


async def resolve_filed_history_result(
    controller: OperationController,
    projection: OperationPublicProjectionV1,
) -> OperationResultProjectionResultV1[FiledHistoryPublicResultV1]:
    """Resolve the settled evidence, IVA-wallet, notification and provenance facts.

    Calls the generic public result-projection door
    (``OperationResultProjectionService``, registered against filed-history's
    own ``FiledHistoryPublicResultV1`` schema and projector) rather than
    reading any private result type. Only meaningful once ``projection``
    carries a settled result reference; a caller checks
    ``FiledHistoryProgressSummaryV1.terminal_condition`` first.
    """
    result_schema = projection.definition_contract.result_schema
    if result_schema is None:
        raise ValueError("filed-history projection does not declare a public result schema")
    return await controller.services.result.resolve(
        OperationResultProjectionRequestV1(
            operation_id=projection.operation_id,
            terminal_revision=projection.revision,
            definition_contract_digest=projection.definition_contract.definition_contract_digest,
            result_schema=result_schema,
        )
    )


__all__ = [
    "CensalFieldReviewRowV1",
    "CensalFieldReviewScreen",
    "FiledHistoryProgressSummaryV1",
    "censal_baseline_is_stale",
    "censal_field_review_rows",
    "censal_operation_request_from_selection",
    "filed_history_progress_summary",
    "resolve_filed_history_result",
]
