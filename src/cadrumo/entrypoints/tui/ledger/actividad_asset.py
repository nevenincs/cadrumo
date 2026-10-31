"""Host-neutral activity-asset actions for the Ledger TUI."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Protocol, override

from pydantic import TypeAdapter
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Button, Input, Static

from ....application.actividad_asset.activity_asset_contracts import ActivityAssetSupersedingClaim
from ....application.actividad_asset.activity_asset_projections import (
    ActivityAssetListProjection,
    ActivityAssetPlanProjection,
)
from ....application.actividad_asset.activity_asset_read_models import (
    ActivityAssetAcquisitionCandidate,
    ActivityAssetDisposalCalculationView,
    ActivityAssetFormOptionsView,
    ActivityAssetTimelineEvent,
)
from ....application.actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from ....application.actividad_asset.operation_dtos import ActivityAssetDisposalSnapshot
from ....application.actividad_asset.operations import ActivityAssetFilingHandoff
from ....application.operations.public_scalar import PublicDecimal
from ....application.operator_actions.models import PreconditionVerdict
from ....core.decimal.coercion import coerce_finite_european_decimal
from ....core.errors.error_codes import resolve_error_message
from ....core.errors.hierarchy import CadrumoError, InternalInvariantError
from ....core.i18n.render import tr
from ....core.parsing.dates import require_iso8601_date
from ....core.period import Period
from ....domain.renta.actividad_asset.disposal import ActivityAssetDisposalReason, PriorFreeDepreciationRegime
from ....domain.renta.actividad_asset.election import ActivityAssetAmortizationElection, AmortizationMethod
from ....domain.renta.actividad_asset.errors import ActividadAssetIncompleteError
from ....domain.renta.actividad_asset.lifecycle import ActivityAssetBasis, ActivityAssetRevision, AssetKind
from ....domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from ....domain.renta.actividad_asset.schedule import ScheduledAmortizationCharge, parse_requested_free_amount
from ..account import AccountSessionExpiredError
from ..components.language import localized
from ..operations.outcome import OperationOutcomeUnknownError, unknown_outcome_of
from .actividad_asset_words import (
    form_options_text,
    limits_line,
    list_row_line,
    plan_row_line,
    reason_text,
    timeline_line,
)
from .controller import LedgerWorkspaceController
from .models_actividad_asset import (
    ActivityAssetClaimRequestV1,
    ActivityAssetCorrectionRequestV1,
    ActivityAssetCreationRequestV1,
    ActivityAssetFilingRequestV1,
    ActivityAssetForecastRequestV1,
    ActivityAssetInspectionV1,
)
from .workspace_screen import LedgerWorkspaceScreen

#: The actions that change records; an unknown outcome withholds them until the asset is read again.
_WRITE_BUTTONS = ("#asset-create", "#asset-correct", "#asset-claim", "#asset-describe", "#asset-dispose")

_SUPERSEDING_CLAIMS = TypeAdapter(tuple[ActivityAssetSupersedingClaim, ...])

#: The facts a new element states with typed fields; a field left empty states nothing, never zero.
_FACT_INPUT_LOCALE_KEYS = {
    "asset-price": "tui.ledger.activity_asset.price",
    "asset-non-deductible-iva": "tui.ledger.activity_asset.non_deductible_iva",
    "asset-in-service-date": "tui.ledger.activity_asset.in_service_date",
    "asset-method": "tui.ledger.activity_asset.method",
}

#: The baja's inputs with literal keys, shared by rendering, clearing and locale discovery.
_DISPOSAL_INPUT_LOCALE_KEYS = {
    "asset-disposal-date": "tui.ledger.activity_asset.disposal_date",
    "asset-disposal-reason": "tui.ledger.activity_asset.disposal_reason",
    "asset-disposal-proceeds": "tui.ledger.activity_asset.disposal_proceeds",
    "asset-disposal-costs": "tui.ledger.activity_asset.disposal_costs",
    "asset-disposal-market-value": "tui.ledger.activity_asset.disposal_market_value",
    "asset-disposal-prior-regime": "tui.ledger.activity_asset.disposal_prior_regime",
    "asset-disposal-later-affectation": "tui.ledger.activity_asset.disposal_later_affectation",
}

#: Closed read controls with literal keys, shared by rendering and locale discovery.
_READ_BUTTON_LOCALE_KEYS = {
    "asset-list": "tui.ledger.activity_asset.list",
    "asset-plan": "tui.ledger.activity_asset.plan",
    "asset-timeline": "tui.ledger.activity_asset.timeline",
    "asset-disposal-calculate": "tui.ledger.activity_asset.disposal_calculate",
    "asset-acquisition-candidates": "tui.ledger.activity_asset.acquisition_candidates",
}


#: The inputs the served reads fill, each worded by the catalogue key that names it.
_OPEN_INPUT_LOCALE_KEYS = {
    "asset-covered-from": "desktop.ledger.assets.from",
    "asset-covered-until": "desktop.ledger.assets.until",
    "asset-filing-tax-year": "desktop.ledger.assets.year",
    "asset-filing-m130-period": "desktop.ledger.assets.quarter",
}


@dataclass(frozen=True, slots=True)
class _ActivityAssetScreenResult:
    """One shared-operation response projected into public screen controls."""

    message: str
    current_revision_id: str | None = None
    inspected_asset_id: str | None = None
    """The asset an inspection read, when the action was one."""
    fills: tuple[tuple[str, str], ...] = ()
    """The inputs a read's served defaults fill, as input id and text."""


class ActivityAssetTuiActionsV1(Protocol):
    """Typed action door backed by the installed session's runtime operations."""

    def create(self, request: ActivityAssetCreationRequestV1) -> ActivityAssetInspectionV1:
        """Create an asset and return its persisted revision chain."""
        ...

    def inspect(self, asset_id: str) -> ActivityAssetInspectionV1:
        """Inspect one asset's immutable revision chain."""
        ...

    def correct(self, request: ActivityAssetCorrectionRequestV1) -> ActivityAssetInspectionV1:
        """Append a correction and return the resulting chain."""
        ...

    def forecast(self, request: ActivityAssetForecastRequestV1) -> ScheduledAmortizationCharge:
        """Preview a schedule through the application boundary."""
        ...

    def record_claim(self, request: ActivityAssetClaimRequestV1) -> ActivityAssetHistoryClaimResult:
        """Record an explicit claim through the application boundary."""
        ...

    def describe(self, asset_id: str, descriptor: ActivityAssetDescriptorFacts) -> ActivityAssetHistory:
        """Append an element's descriptive facts."""
        ...

    def dispose(self, asset_id: str, disposal: ActivityAssetDisposalSnapshot) -> ActivityAssetHistory:
        """Record an element's baja and the claims it supersedes."""
        ...

    def disposal_calculate(
        self,
        asset_id: str,
        disposal: ActivityAssetDisposalSnapshot | None,
    ) -> ActivityAssetDisposalCalculationView:
        """Work out a baja's figures: the stated one as a preview, or else the recorded one."""
        ...

    def list_elements(self) -> ActivityAssetListProjection:
        """Summarise the register, with the year it opens on."""
        ...

    def plan(self, asset_id: str) -> ActivityAssetPlanProjection:
        """Read one element's amortization plan."""
        ...

    def timeline(self, asset_id: str) -> tuple[ActivityAssetTimelineEvent, ...]:
        """Read one element's ordered history."""
        ...

    def form_options(self, asset_kind: AssetKind, tax_year: int) -> ActivityAssetFormOptionsView:
        """Read what the registry admits for an asset kind and tax year."""
        ...

    def acquisition_candidates(self) -> tuple[ActivityAssetAcquisitionCandidate, ...]:
        """List the ledger payments an element could name as its acquisition."""
        ...

    def filing_handoff(self, request: ActivityAssetFilingRequestV1) -> ActivityAssetFilingHandoff:
        """Build non-consuming filing projections."""
        ...


class ActivityAssetScreen(LedgerWorkspaceScreen):
    """Installed interaction surface over the shared asset operations."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain the injected action door and refuse direct construction without it."""
        super().__init__(controller, id="ledger-activity-asset-screen")
        if controller.activity_asset_actions is None:
            raise ValueError("activity-asset screen requires an injected application door")
        self._actions = controller.activity_asset_actions
        self._last_forecast: ScheduledAmortizationCharge | None = None
        self._last_forecast_supersedes: str | None = None
        self._busy = False
        self.writes_held = False
        """Whether a write ended with an unknown outcome, so no write is offered until the asset is read again."""
        self.held_asset_id: str | None = None
        """The asset the held action named; only an inspection of that asset releases the writes."""
        self._named_asset_id: str | None = None
        self._default_claim_years: dict[str, int] = {}
        """The year each listed element opens a claim on, as the last register read served it."""
        self._filled: dict[str, str] = {}
        """What the screen put in an input from a served default, so a later read renews it and a typed value stays."""

    @staticmethod
    def _open_input(input_id: str) -> Widget:
        """An input that opens empty, named by its catalogue word."""
        key = _OPEN_INPUT_LOCALE_KEYS[input_id]
        return localized(Input(placeholder=tr(key), id=input_id), key)

    def _fill(self, fills: tuple[tuple[str, str], ...]) -> None:
        """Put served defaults in the inputs they are for, leaving anything the operator typed."""
        for input_id, text in fills:
            field = self.query_one(f"#{input_id}", Input)
            if not field.value or field.value == self._filled.get(input_id):
                field.value = text
                self._filled[input_id] = text

    @property
    @override
    def in_flight(self) -> bool:
        """An asset action is out through the door."""
        return self._busy

    @override
    def compose(self) -> ComposeResult:
        """Render typed JSON boundaries while keeping all arithmetic in application code."""
        yield localized(
            Static(tr("tui.ledger.activity_asset.title"), classes="cadrumo-banner"), "tui.ledger.activity_asset.title"
        )
        # Where a refusal to leave while an action is out is said.
        yield Static("", id="ledger-flow-status", markup=False)
        yield localized(
            Input(placeholder=tr("tui.ledger.activity_asset.asset_id"), id="asset-id"),
            "tui.ledger.activity_asset.asset_id",
        )
        yield localized(
            Input(placeholder=tr("tui.ledger.activity_asset.revision"), id="asset-revision-json"),
            "tui.ledger.activity_asset.revision",
        )
        yield localized(
            Input(placeholder=tr("tui.ledger.activity_asset.name"), id="asset-name"),
            "tui.ledger.activity_asset.name",
        )
        yield localized(
            Input(placeholder=tr("tui.ledger.activity_asset.serial"), id="asset-serial"),
            "tui.ledger.activity_asset.serial",
        )
        for input_id, key in _FACT_INPUT_LOCALE_KEYS.items():
            yield localized(Input(placeholder=tr(key), id=input_id), key)
        yield localized(
            Button(tr("tui.ledger.activity_asset.create"), id="asset-create"), "tui.ledger.activity_asset.create"
        )
        yield localized(
            Button(tr("tui.ledger.activity_asset.describe"), id="asset-describe"),
            "tui.ledger.activity_asset.describe",
        )
        yield localized(
            Button(tr("tui.ledger.activity_asset.inspect"), id="asset-inspect"), "tui.ledger.activity_asset.inspect"
        )
        yield localized(
            Input(placeholder=tr("tui.ledger.activity_asset.superseding_claims"), id="asset-superseding-claims"),
            "tui.ledger.activity_asset.superseding_claims",
        )
        yield localized(
            Button(tr("tui.ledger.activity_asset.correct"), id="asset-correct"), "tui.ledger.activity_asset.correct"
        )
        for input_id, key in _DISPOSAL_INPUT_LOCALE_KEYS.items():
            yield localized(Input(placeholder=tr(key), id=input_id), key)
        yield localized(
            Button(tr("tui.ledger.activity_asset.dispose"), id="asset-dispose"),
            "tui.ledger.activity_asset.dispose",
        )
        for button_id, key in _READ_BUTTON_LOCALE_KEYS.items():
            yield localized(Button(tr(key), id=button_id), key)
        yield Static("", id="asset-current-revision-id", markup=False)
        yield localized(
            Input(placeholder=tr("tui.ledger.activity_asset.free_amount"), id="asset-free-amount"),
            "tui.ledger.activity_asset.free_amount",
        )
        # The dates, year and quarter open empty: reading the register, the plan and the form options fills them
        # from what those reads serve.
        yield self._open_input("asset-covered-from")
        yield self._open_input("asset-covered-until")
        yield localized(
            Input(placeholder=tr("tui.ledger.activity_asset.supersedes"), id="asset-supersedes-claim-id"),
            "tui.ledger.activity_asset.supersedes",
        )
        yield localized(
            Button(tr("tui.ledger.activity_asset.forecast"), id="asset-forecast"), "tui.ledger.activity_asset.forecast"
        )
        yield localized(
            Button(tr("tui.ledger.activity_asset.claim"), id="asset-claim"), "tui.ledger.activity_asset.claim"
        )
        yield self._open_input("asset-filing-tax-year")
        yield self._open_input("asset-filing-m130-period")
        yield localized(
            Button(tr("tui.ledger.activity_asset.filing"), id="asset-filing-handoff"),
            "tui.ledger.activity_asset.filing",
        )
        yield Input(value="material", id="asset-options-kind")
        yield localized(
            Button(tr("tui.ledger.activity_asset.form_options"), id="asset-form-options"),
            "tui.ledger.activity_asset.form_options",
        )
        yield Static("", id="asset-result", markup=False)
        yield Static("", id="asset-recovery", markup=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch every mutation through the injected shared operations, one action at a time."""
        if self._busy or (self.writes_held and f"#{event.button.id}" in _WRITE_BUTTONS):
            return
        # A visible neutral state prevents a following public action from being
        # mistaken for the previous result while its shared operation is still
        # running on the worker thread.  It has no accounting meaning and is
        # always replaced by either the operation result or a refusal below.
        self.query_one("#asset-result", Static).update(f"pending\t{event.button.id or 'unknown'}")
        self.query_one("#asset-recovery", Static).update("")
        self._busy = True
        self._named_asset_id = None
        # A worker rather than an await here: awaiting would hold this screen's
        # message queue for the whole action, so Back and the account keys
        # would wait behind it and act once it ended, instead of being refused.
        self.run_worker(self._run(event.button.id), group="activity-asset-action")

    async def _run(self, button_id: str | None) -> None:
        try:
            result = await asyncio.to_thread(self._dispatch, button_id)
        except AccountSessionExpiredError as exc:
            self._clear_private_view()
            if unknown_outcome_of(exc) is None:
                self.query_one("#asset-result", Static).update(f"refused\t{exc}")
            else:
                # Lost with the change perhaps saved: unknown, not refused. Signing in composes the screen again.
                self._hold_writes(self._named_asset_id)
                self.query_one("#asset-result", Static).update(f"unknown\t{resolve_error_message(exc)}")
            return
        except OperationOutcomeUnknownError as exc:
            # The change may be saved, so it is never reported as refused, and no write is offered over the
            # asset as last read: the writes return once an inspection reads that asset again.
            self._hold_writes(self._named_asset_id)
            self.query_one("#asset-result", Static).update(f"unknown\t{resolve_error_message(exc)}")
            return
        except (CadrumoError, ValueError) as exc:
            shown = resolve_error_message(exc) if isinstance(exc, CadrumoError) else str(exc)
            self.query_one("#asset-result", Static).update(f"refused\t{shown}")
            self._show_recovery(exc)
            return
        finally:
            # Cleared with no await before the outcome is on screen, so leaving never hides it.
            self._busy = False
        if self._inspection_releases_writes(result.inspected_asset_id):
            self._release_writes()
        self._fill(result.fills)
        self.query_one("#asset-result", Static).update(result.message)
        if result.current_revision_id is not None:
            self.query_one("#asset-current-revision-id", Static).update(
                f"current_revision_id\t{result.current_revision_id}"
            )

    def _hold_writes(self, asset_id: str | None) -> None:
        """Withhold every write until an inspection reads ``asset_id`` again, or any asset when none was named."""
        if not self.writes_held:
            self.held_asset_id = asset_id
        self.writes_held = True
        for selector in _WRITE_BUTTONS:
            self.query_one(selector, Button).disabled = True

    def _inspection_releases_writes(self, inspected_asset_id: str | None) -> bool:
        """Whether a successful inspection read the asset the held writes wait for.

        A hold whose action named no asset waits for any inspection. A typed
        refusal that the held asset does not exist would also prove a held
        creation did not land, but the inspect operation reports a missing
        asset only as a generic validation refusal, so a refusal never
        releases the writes.
        """
        if not self.writes_held or inspected_asset_id is None:
            return False
        return self.held_asset_id is None or self.held_asset_id == inspected_asset_id

    def _release_writes(self) -> None:
        """Offer the writes again over the asset an inspection has just read."""
        self.writes_held = False
        self.held_asset_id = None
        for selector in _WRITE_BUTTONS:
            self.query_one(selector, Button).disabled = False

    def _clear_private_view(self) -> None:
        """Discard screen-local financial facts when the retained session is lost."""
        self._last_forecast = None
        self._last_forecast_supersedes = None
        self._default_claim_years = {}
        self._filled = {}
        for selector in (
            "#asset-id",
            "#asset-revision-json",
            "#asset-free-amount",
            "#asset-covered-from",
            "#asset-covered-until",
            "#asset-supersedes-claim-id",
            "#asset-name",
            "#asset-serial",
            "#asset-superseding-claims",
            "#asset-options-kind",
            "#asset-filing-tax-year",
            "#asset-filing-m130-period",
            *(f"#{input_id}" for input_id in _DISPOSAL_INPUT_LOCALE_KEYS),
            *(f"#{input_id}" for input_id in _FACT_INPUT_LOCALE_KEYS),
        ):
            self.query_one(selector, Input).value = ""
        self.query_one("#asset-current-revision-id", Static).update("")
        self.query_one("#asset-recovery", Static).update("")

    def _show_recovery(self, exc: Exception) -> None:
        """Name a refusal's recovery action and move focus to the correction it needs."""
        if not isinstance(exc, ActividadAssetIncompleteError):
            return
        verdict: object = exc.terminal_precondition_verdict
        if not isinstance(verdict, PreconditionVerdict) or verdict.action is None:
            return
        facts = verdict.evidence[0].values
        self.query_one("#asset-recovery", Static).update(
            f"recovery\t{verdict.action.action_id}\tasset\t{facts.get('asset_id', '')}"
            f"\trevision\t{facts.get('revision_id', '')}",
        )
        self.query_one("#asset-correct", Button).focus()

    def _dispatch(self, button_id: str | None) -> _ActivityAssetScreenResult:
        """Delegate one public action, retaining no screen-local tax arithmetic."""
        asset_id = self.query_one("#asset-id", Input).value
        revision_json = self.query_one("#asset-revision-json", Input).value
        # Each action names its asset before it reaches the door, so an unknown outcome holds its writes.
        if button_id in ("asset-create", "asset-inspect", "asset-correct", "asset-forecast", "asset-claim"):
            return self._dispatch_record(button_id, asset_id, revision_json)
        if button_id in ("asset-filing-handoff", "asset-describe", "asset-dispose", "asset-disposal-calculate"):
            return self._dispatch_disposal(button_id, asset_id, revision_json)
        if button_id in ("asset-list", "asset-plan", "asset-timeline"):
            return self._dispatch_register(button_id, asset_id, revision_json)
        if button_id in ("asset-form-options", "asset-acquisition-candidates"):
            return self._dispatch_options(button_id, asset_id, revision_json)
        raise ValueError("unknown activity-asset action")

    def _dispatch_record(self, button_id: str | None, asset_id: str, revision_json: str) -> _ActivityAssetScreenResult:
        if button_id == "asset-create":
            creation = ActivityAssetCreationRequestV1(
                revision=self._stated_revision(revision_json),
                descriptor=self._descriptor(),
            )
            self._named_asset_id = creation.revision.asset_id
            return self._inspection_result(prefix="created", result=self._actions.create(creation))
        if button_id == "asset-inspect":
            self._named_asset_id = asset_id
            result = self._actions.inspect(asset_id)
            inspected = self._inspection_result(prefix="asset", result=result)
            return replace(inspected, inspected_asset_id=result.asset_id)
        if button_id == "asset-correct":
            superseding = self.query_one("#asset-superseding-claims", Input).value.strip()
            correction = ActivityAssetCorrectionRequestV1(
                revision=self._stated_revision(revision_json),
                superseding_claims=_SUPERSEDING_CLAIMS.validate_json(superseding) if superseding else (),
            )
            self._named_asset_id = correction.revision.asset_id
            return self._inspection_result(prefix="corrected", result=self._actions.correct(correction))
        if button_id == "asset-forecast":
            self._named_asset_id = asset_id
            supersedes_claim_id = self.query_one("#asset-supersedes-claim-id", Input).value.strip() or None
            self._last_forecast = self._actions.forecast(
                ActivityAssetForecastRequestV1(
                    asset_id=asset_id,
                    covered_from=require_iso8601_date(self.query_one("#asset-covered-from", Input).value),
                    covered_until=require_iso8601_date(self.query_one("#asset-covered-until", Input).value),
                    # An empty field elects no amount.
                    requested_free_amount=parse_requested_free_amount(
                        self.query_one("#asset-free-amount", Input).value.strip() or None
                    ),
                    supersedes_claim_id=supersedes_claim_id,
                ),
            )
            # The claim must replace exactly the claim this forecast left out.
            self._last_forecast_supersedes = supersedes_claim_id
            return _ActivityAssetScreenResult(
                message=f"forecast\t{self._last_forecast.amount}\t{self._last_forecast.source_reference}"
            )
        if button_id == "asset-claim":
            if self._last_forecast is None:
                raise ValueError("calculate a forecast before recording a claim")
            self._named_asset_id = self._last_forecast.asset_id
            result = self._actions.record_claim(
                ActivityAssetClaimRequestV1(
                    forecast=self._last_forecast,
                    supersedes_claim_id=self._last_forecast_supersedes,
                ),
            )
            return _ActivityAssetScreenResult(
                message=f"claim\t{result.claim.claim_id}\treused={str(result.reused_existing_claim).lower()}"
            )
        raise ValueError("unknown activity-asset action")

    def _dispatch_disposal(
        self, button_id: str | None, asset_id: str, _revision_json: str
    ) -> _ActivityAssetScreenResult:
        if button_id == "asset-filing-handoff":
            tax_year = self._stated_filing_year()
            m130_period = Period.from_year_and_code(
                tax_year,
                self.query_one("#asset-filing-m130-period", Input).value,
            )
            result = self._actions.filing_handoff(
                ActivityAssetFilingRequestV1(tax_year=tax_year, m130_period=m130_period),
            )
            if result.material_m130 is None or result.intangible_m130 is None:
                raise InternalInvariantError("activity-asset handoff for a Modelo 130 period omitted its accruals")
            return _ActivityAssetScreenResult(
                message=(
                    "filing_handoff"
                    f"\tm100_material={result.material_m100.amount}"
                    f"\tm100_intangible={result.intangible_m100.amount}"
                    f"\tm130_material={result.material_m130.amount}"
                    f"\tm130_intangible={result.intangible_m130.amount}"
                )
            )
        if button_id == "asset-describe":
            self._named_asset_id = asset_id
            history = self._actions.describe(asset_id, self._descriptor())
            return _ActivityAssetScreenResult(message=f"described\t{asset_id}\tdescriptors={len(history.descriptors)}")
        if button_id == "asset-dispose":
            self._named_asset_id = asset_id
            history = self._actions.dispose(asset_id, self._stated_disposal())
            return _ActivityAssetScreenResult(
                message=f"disposed\t{asset_id}\trevisions={len(history.revisions)}\tclaims={len(history.claims)}"
            )
        if button_id == "asset-disposal-calculate":
            self._named_asset_id = asset_id
            stated = self._stated_disposal() if self._disposal_text("asset-disposal-date") else None
            calculation = self._actions.disposal_calculate(asset_id, stated)
            return _ActivityAssetScreenResult(
                message=(
                    f"disposal\tnet_value={calculation.net_value.decimal}\texcess={calculation.excess.decimal}"
                    f"\tresult={calculation.result.decimal if calculation.result else ''}"
                ),
            )
        raise ValueError("unknown activity-asset action")

    def _dispatch_register(
        self, button_id: str | None, asset_id: str, _revision_json: str
    ) -> _ActivityAssetScreenResult:
        if button_id == "asset-list":
            register = self._actions.list_elements()
            rows = register.rows or ()
            self._default_claim_years = {
                row.asset_id: row.default_claim_year for row in rows if row.default_claim_year is not None
            }
            return _ActivityAssetScreenResult(
                message="\n".join(list_row_line(row) for row in rows) or tr("desktop.ledger.assets.list.empty"),
                fills=(
                    () if register.default_year is None else (("asset-filing-tax-year", str(register.default_year)),)
                ),
            )
        if button_id == "asset-plan":
            return self._plan_result(asset_id)
        if button_id == "asset-timeline":
            self._named_asset_id = asset_id
            return _ActivityAssetScreenResult(
                message="\n".join(timeline_line(event) for event in self._actions.timeline(asset_id))
                or tr("desktop.ledger.assets.timeline.empty"),
            )
        raise ValueError("unknown activity-asset action")

    def _plan_result(self, asset_id: str) -> _ActivityAssetScreenResult:
        self._named_asset_id = asset_id
        plan = self._actions.plan(asset_id)
        minimum_label = tr("tui.ledger.activity_asset.plan_minimum")
        minimum_incomplete = tr("tui.ledger.activity_asset.plan_minimum_incomplete")
        lines: list[str] = []
        if plan.limits is not None and (limits := limits_line(plan.limits)) is not None:
            lines.append(limits)
        lines.extend(
            plan_row_line(row, minimum_label=minimum_label, minimum_incomplete=minimum_incomplete)
            for row in plan.rows or ()
        )
        lines.extend(advisory for item in plan.advisories if (advisory := reason_text(item.label_key)) is not None)
        return _ActivityAssetScreenResult(
            message="\n".join(lines) or tr("desktop.ledger.assets.plan.empty"),
            fills=self._claim_period_fills(asset_id, plan),
        )

    def _claim_period_fills(self, asset_id: str, plan: ActivityAssetPlanProjection) -> tuple[tuple[str, str], ...]:
        """The first span the year the register opens a claim on can still record, when the list served that year."""
        year = self._default_claim_years.get(asset_id)
        for row in plan.rows or ():
            if row.tax_year == year and row.claimable_intervals:
                span = row.claimable_intervals[0]
                return (
                    ("asset-covered-from", span.covered_from.isoformat()),
                    ("asset-covered-until", span.covered_until.isoformat()),
                )
        return ()

    def _dispatch_options(
        self, button_id: str | None, _asset_id: str, _revision_json: str
    ) -> _ActivityAssetScreenResult:
        if button_id == "asset-form-options":
            options = self._actions.form_options(
                AssetKind(self.query_one("#asset-options-kind", Input).value),
                self._stated_filing_year(),
            )
            # The quarter stays the operator's choice: the served ones are listed, none is preselected.
            return _ActivityAssetScreenResult(message=form_options_text(options))
        if button_id == "asset-acquisition-candidates":
            return _ActivityAssetScreenResult(
                message="\n".join(
                    f"{item.transaction_id}\t{item.booked_date}\t{item.amount.decimal}"
                    for item in self._actions.acquisition_candidates()
                ),
            )
        raise ValueError("unknown activity-asset action")

    def _stated_filing_year(self) -> int:
        """Read the year the operator chose, or say that one is to be chosen."""
        text = self.query_one("#asset-filing-tax-year", Input).value.strip()
        if not text:
            raise ValueError(tr("desktop.ledger.assets.filing.choose_year"))
        return int(text)

    def _disposal_text(self, input_id: str) -> str:
        return self.query_one(f"#{input_id}", Input).value.strip()

    def _stated_disposal(self) -> ActivityAssetDisposalSnapshot:
        """Read the baja's inputs; the operation judges the reason and the amounts."""
        market_value = self._disposal_text("asset-disposal-market-value")
        prior_regime = self._disposal_text("asset-disposal-prior-regime")
        later_affectation = self._disposal_text("asset-disposal-later-affectation")
        return ActivityAssetDisposalSnapshot(
            disposal_date=require_iso8601_date(self._disposal_text("asset-disposal-date")),
            reason=ActivityAssetDisposalReason(self._disposal_text("asset-disposal-reason")),
            proceeds=PublicDecimal(decimal=self._disposal_text("asset-disposal-proceeds") or "0.00"),
            transmission_costs=PublicDecimal(decimal=self._disposal_text("asset-disposal-costs") or "0.00"),
            market_value=PublicDecimal(decimal=market_value) if market_value else None,
            prior_free_depreciation_regime=PriorFreeDepreciationRegime(prior_regime) if prior_regime else None,
            later_affectation_on=require_iso8601_date(later_affectation) if later_affectation else None,
        )

    def _stated_revision(self, revision_json: str) -> ActivityAssetRevision:
        """Read the revision, with each typed fact the operator stated in place of the one it carries."""
        revision = ActivityAssetRevision.model_validate_json(revision_json)
        price = self._fact_amount("asset-price")
        non_deductible_iva = self._fact_amount("asset-non-deductible-iva")
        in_service = self._disposal_text("asset-in-service-date")
        method = self._disposal_text("asset-method")
        updates: dict[str, object] = {}
        if price is not None or non_deductible_iva is not None:
            basis = dict(revision.basis)
            if price is not None:
                basis["basis_amount"] = price
            if non_deductible_iva is not None:
                basis["non_deductible_iva"] = non_deductible_iva
            updates["basis"] = ActivityAssetBasis.model_validate(basis)
        if in_service:
            updates["in_service_date"] = require_iso8601_date(in_service)
        if method:
            election = dict(revision.amortization)
            election["method"] = AmortizationMethod(method)
            updates["amortization"] = ActivityAssetAmortizationElection.model_validate(election)
        if not updates:
            return revision
        return ActivityAssetRevision.model_validate({**dict(revision), **updates})

    def _fact_amount(self, input_id: str) -> Decimal | None:
        """Read a stated amount; an empty field is no statement, and an ambiguous number is refused."""
        text = self._disposal_text(input_id)
        if not text:
            return None
        amount = coerce_finite_european_decimal(text)
        if amount is None:
            raise ValueError(f"{input_id} is not an unambiguous amount")
        return amount

    def _descriptor(self) -> ActivityAssetDescriptorFacts:
        return ActivityAssetDescriptorFacts(
            name=self.query_one("#asset-name", Input).value,
            serial_number=self.query_one("#asset-serial", Input).value.strip() or None,
        )

    @staticmethod
    def _inspection_result(*, prefix: str, result: ActivityAssetInspectionV1) -> _ActivityAssetScreenResult:
        """Project the current immutable revision identity alongside its count."""
        if not result.revisions:  # pragma: no cover - application inspection invariant
            raise InternalInvariantError("activity-asset inspection returned no current revision")
        return _ActivityAssetScreenResult(
            message=f"{prefix}\t{result.asset_id}\trevisions={len(result.revisions)}",
            current_revision_id=result.revisions[-1].revision_id,
        )


__all__ = ["ActivityAssetScreen", "ActivityAssetTuiActionsV1"]
