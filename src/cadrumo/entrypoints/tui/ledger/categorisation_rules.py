"""Classification rules: list them, add one, and apply them after a previewed dry run.

The rule list is read through the registered list operation and shown one page
at a time. Applying rules always previews first: the dry run names every entry
that would change, and only that reviewed run can be confirmed.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Final, cast, override

from textual.widget import Widget
from textual.widgets import DataTable, Input, Select, Static

from ....application.ledger.rule_contracts import (
    LedgerRuleAddRequest,
    LedgerRuleApplyMatchProjection,
    LedgerRuleApplyProjection,
    LedgerRuleApplyRequest,
    LedgerRuleListRequest,
    LedgerRuleRowProjection,
)
from ....core.i18n.render import tr
from ....domain.transactions.enums import BusinessClassification
from ..components.widgets import ContentDataTable
from .categorisation_common import (
    CategorisationScreen,
    StagedChangeV1,
    action,
    action_row,
    blank_to_none,
    classification_label,
    field,
    heading,
    page_label,
    short_id,
)
from .categorisation_doors import LedgerRuleAddDoorV1, LedgerRuleApplyDoorV1, LedgerRuleListDoorV1
from .controller import LedgerWorkspaceController

RULES_PAGE_SIZE: Final = 200
"""The most rules or previewed matches the screen renders at once."""

RULE_CLASSIFICATIONS: Final[tuple[BusinessClassification, ...]] = (
    BusinessClassification.BUSINESS,
    BusinessClassification.PERSONAL,
    BusinessClassification.MIXED,
    BusinessClassification.REVIEWED_EXCLUDED,
)
"""The decisions a rule can make for the entries it matches."""

_SCOPE_UNCLASSIFIED: Final = "unclassified"
_SCOPE_REAFFIRM: Final = "reaffirm"


class LedgerRulesScreen(CategorisationScreen):
    """List, add and apply the profile's classification rules."""

    TITLE_KEY = "tui.ledger.categorisation.rules.title"
    PROMPT_KEY = "tui.ledger.categorisation.rules.prompt"

    def __init__(
        self,
        controller: LedgerWorkspaceController,
        *,
        list_door: LedgerRuleListDoorV1,
        add_door: LedgerRuleAddDoorV1,
        apply_door: LedgerRuleApplyDoorV1,
    ) -> None:
        """Keep the three profile-bound rule doors."""
        super().__init__(controller, id="ledger-categorisation-rules-screen")
        self.list_door = list_door
        self.add_door = add_door
        self.apply_door = apply_door
        self.rules: tuple[LedgerRuleRowProjection, ...] = ()
        self.page_offset = 0
        self.preview: tuple[LedgerRuleApplyMatchProjection, ...] = ()

    @override
    def compose_body(self) -> Iterator[Widget]:
        yield heading("tui.ledger.categorisation.rules.list_heading")
        yield ContentDataTable[str](id="categorisation-rules", cursor_type="row", zebra_stripes=True)
        yield Static("", id="categorisation-rules-page", markup=False)
        yield action_row(
            action("tui.ledger.categorisation.page.previous", id="categorisation-rules-previous"),
            action("tui.ledger.categorisation.page.next", id="categorisation-rules-next"),
        )
        yield heading("tui.ledger.categorisation.rules.add_heading")
        yield field("tui.ledger.categorisation.rules.pattern", id="categorisation-rule-pattern")
        yield Select[str](
            tuple((classification_label(item.value), item.value) for item in RULE_CLASSIFICATIONS),
            value=BusinessClassification.BUSINESS.value,
            allow_blank=False,
            id="categorisation-rule-classification",
        )
        yield field("tui.ledger.categorisation.rules.category", id="categorisation-rule-category")
        yield field("tui.ledger.categorisation.rules.priority", id="categorisation-rule-priority", max_length=6)
        yield action_row(action("tui.ledger.categorisation.rules.review_add", id="categorisation-rule-review-add"))
        yield heading("tui.ledger.categorisation.rules.apply_heading")
        yield Select[str](
            (
                (tr("tui.ledger.categorisation.rules.scope_unclassified"), _SCOPE_UNCLASSIFIED),
                (tr("tui.ledger.categorisation.rules.scope_reaffirm"), _SCOPE_REAFFIRM),
            ),
            value=_SCOPE_UNCLASSIFIED,
            allow_blank=False,
            id="categorisation-rule-scope",
        )
        yield action_row(action("tui.ledger.categorisation.rules.preview", id="categorisation-rule-preview"))
        yield ContentDataTable[str](id="categorisation-rule-matches", cursor_type="row", zebra_stripes=True)

    @override
    def staged_controls(self) -> tuple[str, ...]:
        return (
            "#categorisation-rule-pattern",
            "#categorisation-rule-classification",
            "#categorisation-rule-category",
            "#categorisation-rule-priority",
            "#categorisation-rule-scope",
            "#categorisation-rule-review-add",
            "#categorisation-rule-preview",
        )

    @override
    def mount_body(self) -> None:
        self.query_one("#categorisation-rule-priority", Input).value = "100"
        self.query_one("#categorisation-rule-matches", DataTable).display = False
        self.run_read(self._load)

    @override
    def paint_tables(self) -> None:
        rules = cast("DataTable[str]", self.query_one("#categorisation-rules", DataTable))
        if not rules.columns:
            rules.add_columns(
                tr("tui.ledger.categorisation.rules.column.priority"),
                tr("tui.ledger.categorisation.rules.column.pattern"),
                tr("tui.ledger.categorisation.rules.column.classification"),
                tr("tui.ledger.categorisation.rules.column.category"),
            )
        rules.clear()
        page = self.rules[self.page_offset : self.page_offset + RULES_PAGE_SIZE]
        for rule in page:
            rules.add_row(
                str(rule.priority),
                rule.description_pattern,
                classification_label(rule.classification.value),
                rule.category_id or "-",
                key=rule.rule_id,
            )
        self.query_one("#categorisation-rules-page", Static).update(
            page_label(self.page_offset, len(page), len(self.rules))
        )
        matches = cast("DataTable[str]", self.query_one("#categorisation-rule-matches", DataTable))
        if not matches.columns:
            matches.add_columns(
                tr("tui.ledger.categorisation.column.entry"),
                tr("tui.ledger.categorisation.column.description"),
                tr("tui.ledger.categorisation.column.classification"),
            )
        matches.clear()
        for match in self.preview[:RULES_PAGE_SIZE]:
            matches.add_row(
                short_id(match.transaction_id),
                match.description,
                classification_label(match.classification.value),
                key=match.transaction_id,
            )

    async def _load(self) -> None:
        result = await self.list_door(LedgerRuleListRequest(profile_id=self.list_door.profile_id))
        self.rules = result.rules
        self.page_offset = min(self.page_offset, max(0, (len(self.rules) - 1) // RULES_PAGE_SIZE * RULES_PAGE_SIZE))
        self.paint_tables()
        if not self.rules:
            self.show_outcome(lambda: tr("tui.ledger.categorisation.rules.empty"))

    @override
    def on_tool_button(self, button_id: str) -> None:
        if button_id == "categorisation-rules-previous":
            self._turn(-RULES_PAGE_SIZE)
        elif button_id == "categorisation-rules-next":
            self._turn(RULES_PAGE_SIZE)
        elif button_id == "categorisation-rule-review-add":
            self.stage_from(self._stage_add)
        elif button_id == "categorisation-rule-preview":
            self.run_read(self._preview)

    def _turn(self, step: int) -> None:
        offset = self.page_offset + step
        if offset < 0 or offset >= len(self.rules):
            self.status("tui.ledger.categorisation.page.none")
            return
        self.page_offset = offset
        self.paint_tables()

    def _stage_add(self) -> StagedChangeV1:
        priority_text = self.query_one("#categorisation-rule-priority", Input).value.strip() or "100"
        if not priority_text.isdigit():
            raise ValueError(tr("tui.ledger.categorisation.rules.priority_invalid"))
        classification = BusinessClassification(
            str(cast("Select[str]", self.query_one("#categorisation-rule-classification", Select)).value)
        )
        request = LedgerRuleAddRequest(
            profile_id=self.add_door.profile_id,
            description_pattern=self.query_one("#categorisation-rule-pattern", Input).value,
            classification=classification,
            category_id=blank_to_none(self.query_one("#categorisation-rule-category", Input).value),
            priority=int(priority_text),
        )

        async def write() -> bool:
            result = await self.add_door(request)
            if result.outcome == "validation_error":
                messages = "; ".join(result.validation_messages)
                self.show_outcome(lambda: tr("tui.ledger.categorisation.rules.add_refused", messages=messages))
                return False
            self.query_one("#categorisation-rule-pattern", Input).value = ""
            self.show_outcome(lambda: tr("tui.ledger.categorisation.rules.added", pattern=request.description_pattern))
            await self._load()
            return True

        return StagedChangeV1(
            summary=lambda: tr(
                "tui.ledger.categorisation.rules.stage_add",
                pattern=request.description_pattern,
                classification=classification_label(classification.value),
                category=request.category_id or "-",
                priority=request.priority,
            ),
            write=write,
        )

    def _reaffirm(self) -> bool:
        return str(cast("Select[str]", self.query_one("#categorisation-rule-scope", Select)).value) == _SCOPE_REAFFIRM

    async def _preview(self) -> None:
        reaffirm = self._reaffirm()
        result = await self.apply_door(
            LedgerRuleApplyRequest(profile_id=self.apply_door.profile_id, reaffirm=reaffirm, dry_run=True)
        )
        if result.outcome == "validation_error":
            self._show_refused(result)
            return
        self.preview = result.would_match or ()
        self.paint_tables()
        self.query_one("#categorisation-rule-matches", DataTable).display = bool(self.preview)
        count = len(self.preview)
        if not count:
            self.show_outcome(lambda: tr("tui.ledger.categorisation.rules.nothing_matches"))
            return
        self.show_outcome(lambda: tr("tui.ledger.categorisation.rules.previewed", count=count))
        self.stage(
            lambda: tr(
                "tui.ledger.categorisation.rules.stage_apply_reaffirm"
                if reaffirm
                else "tui.ledger.categorisation.rules.stage_apply",
                count=count,
            ),
            lambda: self._apply(reaffirm),
            refreshes_workspace=True,
        )

    async def _apply(self, reaffirm: bool) -> bool:
        result = await self.apply_door(
            LedgerRuleApplyRequest(profile_id=self.apply_door.profile_id, reaffirm=reaffirm, dry_run=False)
        )
        self.preview = ()
        self.query_one("#categorisation-rule-matches", DataTable).display = False
        self.paint_tables()
        if result.outcome == "validation_error":
            self._show_refused(result)
            return False
        applied = result.matched or 0
        skipped = result.skipped_already_classified or 0
        unmatched = result.no_match or 0
        self.show_outcome(
            lambda: tr("tui.ledger.categorisation.rules.applied", applied=applied, skipped=skipped, unmatched=unmatched)
        )
        return True

    def _show_refused(self, result: LedgerRuleApplyProjection) -> None:
        messages = "; ".join(result.validation_messages)
        self.show_outcome(lambda: tr("tui.ledger.categorisation.rules.apply_refused", messages=messages))

    @override
    def clear_private_view(self) -> None:
        super().clear_private_view()
        self.rules = ()
        self.preview = ()
        self.page_offset = 0
        self.paint_tables()


__all__ = ["RULES_PAGE_SIZE", "RULE_CLASSIFICATIONS", "LedgerRulesScreen"]
