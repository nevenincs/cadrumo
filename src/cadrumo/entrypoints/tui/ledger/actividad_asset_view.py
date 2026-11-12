"""Widget composition for the activity-asset ledger screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Button, Input, Static

from ....core.i18n.render import tr
from ..components.language import localized
from ..refusal.panel import RefusalSlot

#: The facts a new element states with typed fields; a field left empty states nothing, never zero.
FACT_INPUT_LOCALE_KEYS = {
    "asset-price": "tui.ledger.activity_asset.price",
    "asset-non-deductible-iva": "tui.ledger.activity_asset.non_deductible_iva",
    "asset-in-service-date": "tui.ledger.activity_asset.in_service_date",
    "asset-method": "tui.ledger.activity_asset.method",
}

#: The baja's inputs with literal keys, shared by rendering, clearing and locale discovery.
DISPOSAL_INPUT_LOCALE_KEYS = {
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


def _open_input(input_id: str) -> Widget:
    """An input that opens empty, named by its catalogue word."""
    key = _OPEN_INPUT_LOCALE_KEYS[input_id]
    return localized(Input(placeholder=tr(key), id=input_id), key)


def compose_activity_asset() -> ComposeResult:
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
    for input_id, key in FACT_INPUT_LOCALE_KEYS.items():
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
    for input_id, key in DISPOSAL_INPUT_LOCALE_KEYS.items():
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
    yield _open_input("asset-covered-from")
    yield _open_input("asset-covered-until")
    yield localized(
        Input(placeholder=tr("tui.ledger.activity_asset.supersedes"), id="asset-supersedes-claim-id"),
        "tui.ledger.activity_asset.supersedes",
    )
    yield localized(
        Button(tr("tui.ledger.activity_asset.forecast"), id="asset-forecast"), "tui.ledger.activity_asset.forecast"
    )
    yield localized(Button(tr("tui.ledger.activity_asset.claim"), id="asset-claim"), "tui.ledger.activity_asset.claim")
    yield _open_input("asset-filing-tax-year")
    yield _open_input("asset-filing-m130-period")
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
    yield RefusalSlot(id="asset-recovery")
