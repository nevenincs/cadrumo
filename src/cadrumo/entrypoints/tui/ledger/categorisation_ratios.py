"""Usage ratios: the eligible categories, the profile's overrides, their validation, set and unset.

A ratio override replaces the statutory default share of business use for one
category. The eligible categories and the overrides are read for one filing
year; an override is set from typed values after review, and removing one asks
once more before it is sent.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast, override

from textual.widget import Widget
from textual.widgets import DataTable, Input

from ....application.ledger.ratios_contracts import (
    LedgerRatiosEligibleRequest,
    LedgerRatiosEligibleRow,
    LedgerRatiosListRequest,
    LedgerRatiosListRow,
    LedgerRatiosSetRequest,
    LedgerRatiosUnsetRequest,
    LedgerRatiosValidateProjection,
    LedgerRatiosValidateRequest,
)
from ....core.i18n.render import tr
from ....core.time.clock import now
from ..components.widgets import ContentDataTable
from .categorisation_common import CategorisationScreen, StagedChangeV1, action, action_row, field, heading
from .categorisation_doors import (
    LedgerRatiosEligibleDoorV1,
    LedgerRatiosListDoorV1,
    LedgerRatiosSetDoorV1,
    LedgerRatiosUnsetDoorV1,
    LedgerRatiosValidateDoorV1,
)
from .controller import LedgerWorkspaceController


def validation_text(report: LedgerRatiosValidateProjection) -> str:
    """Say what the validation of the stored overrides found."""
    lines = [
        tr(
            "tui.ledger.categorisation.ratios.validation_counts",
            eligible=report.eligible_count,
            overrides=report.overrides_count,
        )
    ]
    if not report.profile_present:
        lines.append(tr("tui.ledger.categorisation.ratios.validation_no_profile"))
    if report.missing_overrides:
        lines.append(
            tr("tui.ledger.categorisation.ratios.validation_missing", categories=", ".join(report.missing_overrides))
        )
    lines.extend(
        tr(
            "tui.ledger.categorisation.ratios.validation_finding",
            category=finding.category,
            kind=finding.kind,
            detail=finding.detail or "-",
        )
        for finding in report.findings
    )
    if report.profile_present and not report.missing_overrides and not report.findings:
        lines.append(tr("tui.ledger.categorisation.ratios.validation_clean"))
    return "\n".join(lines)


class LedgerRatiosScreen(CategorisationScreen):
    """Read, validate, set and unset the profile's usage ratio overrides."""

    TITLE_KEY = "tui.ledger.categorisation.ratios.title"
    PROMPT_KEY = "tui.ledger.categorisation.ratios.prompt"

    def __init__(
        self,
        controller: LedgerWorkspaceController,
        *,
        list_door: LedgerRatiosListDoorV1,
        eligible_door: LedgerRatiosEligibleDoorV1,
        validate_door: LedgerRatiosValidateDoorV1,
        set_door: LedgerRatiosSetDoorV1,
        unset_door: LedgerRatiosUnsetDoorV1,
    ) -> None:
        """Keep the five profile-bound ratio doors."""
        super().__init__(controller, id="ledger-categorisation-ratios-screen")
        self.list_door = list_door
        self.eligible_door = eligible_door
        self.validate_door = validate_door
        self.set_door = set_door
        self.unset_door = unset_door
        self.year: int | None = None
        self.overrides: tuple[LedgerRatiosListRow, ...] = ()
        self.eligible: tuple[LedgerRatiosEligibleRow, ...] = ()

    @override
    def compose_body(self) -> Iterator[Widget]:
        yield field("tui.ledger.categorisation.ratios.year", id="categorisation-ratios-year", max_length=4)
        yield action_row(
            action("tui.ledger.categorisation.ratios.read", id="categorisation-ratios-read"),
            action("tui.ledger.categorisation.ratios.validate", id="categorisation-ratios-validate"),
        )
        yield heading("tui.ledger.categorisation.ratios.overrides_heading")
        yield ContentDataTable[str](id="categorisation-ratios-overrides", cursor_type="row", zebra_stripes=True)
        yield heading("tui.ledger.categorisation.ratios.eligible_heading")
        yield ContentDataTable[str](id="categorisation-ratios-eligible", cursor_type="row", zebra_stripes=True)
        yield heading("tui.ledger.categorisation.ratios.set_heading")
        yield field("tui.ledger.categorisation.ratios.category", id="categorisation-ratios-category", max_length=96)
        yield field("tui.ledger.categorisation.ratios.ratio", id="categorisation-ratios-ratio", max_length=32)
        yield action_row(
            action("tui.ledger.categorisation.ratios.review_set", id="categorisation-ratios-set"),
            action("tui.ledger.categorisation.ratios.review_unset", id="categorisation-ratios-unset"),
        )

    @override
    def staged_controls(self) -> tuple[str, ...]:
        return (
            "#categorisation-ratios-year",
            "#categorisation-ratios-read",
            "#categorisation-ratios-validate",
            "#categorisation-ratios-category",
            "#categorisation-ratios-ratio",
            "#categorisation-ratios-set",
            "#categorisation-ratios-unset",
        )

    @override
    def mount_body(self) -> None:
        self.query_one("#categorisation-ratios-year", Input).value = str(now().year)
        self.run_read(self._read)

    @override
    def paint_tables(self) -> None:
        overrides = cast("DataTable[str]", self.query_one("#categorisation-ratios-overrides", DataTable))
        if not overrides.columns:
            overrides.add_columns(
                tr("tui.ledger.categorisation.ratios.column.category"),
                tr("tui.ledger.categorisation.ratios.column.ratio"),
            )
        overrides.clear()
        for row in self.overrides:
            overrides.add_row(row.category, row.ratio, key=row.category)
        eligible = cast("DataTable[str]", self.query_one("#categorisation-ratios-eligible", DataTable))
        if not eligible.columns:
            eligible.add_columns(
                tr("tui.ledger.categorisation.ratios.column.category"),
                tr("tui.ledger.categorisation.ratios.column.kind"),
                tr("tui.ledger.categorisation.ratios.column.default"),
                tr("tui.ledger.categorisation.ratios.column.override"),
            )
        eligible.clear()
        for row in self.eligible:
            eligible.add_row(
                row.category,
                row.proportionality_kind,
                row.default_ratio or "-",
                tr(
                    "tui.ledger.categorisation.ratios.override_present"
                    if row.override_present
                    else "tui.ledger.categorisation.ratios.override_absent"
                ),
                key=row.category,
            )

    def _typed_year(self) -> int:
        text = self.query_one("#categorisation-ratios-year", Input).value.strip()
        if not text.isdigit():
            raise ValueError(tr("tui.ledger.categorisation.ratios.year_invalid"))
        return int(text)

    async def _read(self) -> None:
        year = self._typed_year()
        listed = await self.list_door(LedgerRatiosListRequest(profile_id=self.list_door.profile_id, year=year))
        eligible = await self.eligible_door(
            LedgerRatiosEligibleRequest(profile_id=self.eligible_door.profile_id, year=year)
        )
        self.year = year
        self.overrides = listed.rows
        self.eligible = eligible.rows
        self.paint_tables()
        if listed.outcome == "censo_mismatch":
            self.show_outcome(lambda: tr("tui.ledger.categorisation.ratios.censo_mismatch", year=year))
        elif not listed.rows:
            self.show_outcome(lambda: tr("tui.ledger.categorisation.ratios.no_overrides", year=year))
        else:
            self.show_outcome(None)

    async def _validate(self) -> None:
        report = await self.validate_door(LedgerRatiosValidateRequest(profile_id=self.validate_door.profile_id))
        self.show_outcome(lambda: validation_text(report))

    @override
    def on_tool_button(self, button_id: str) -> None:
        if button_id == "categorisation-ratios-read":
            try:
                self._typed_year()
            except ValueError as error:
                self.refuse_error(error)
                return
            self.run_read(self._read)
        elif button_id == "categorisation-ratios-validate":
            self.run_read(self._validate)
        elif button_id == "categorisation-ratios-set":
            self.stage_from(self._stage_set)
        elif button_id == "categorisation-ratios-unset":
            self.stage_from(self._stage_unset)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Fill the form from the chosen override or eligible category."""
        if self.handle_navigation_selection(event) or self.busy or event.row_key.value is None:
            return
        category = str(event.row_key.value)
        table_id = event.data_table.id
        if table_id not in {"categorisation-ratios-overrides", "categorisation-ratios-eligible"}:
            return
        self.query_one("#categorisation-ratios-category", Input).value = category
        current = next((row for row in self.overrides if row.category == category), None)
        self.query_one("#categorisation-ratios-ratio", Input).value = "" if current is None else current.ratio

    def _category(self) -> str:
        category = self.query_one("#categorisation-ratios-category", Input).value.strip()
        if not category:
            raise ValueError(tr("tui.ledger.categorisation.ratios.category_required"))
        return category

    def _stage_set(self) -> StagedChangeV1:
        request = LedgerRatiosSetRequest(
            profile_id=self.set_door.profile_id,
            category=self._category(),
            ratio=self.query_one("#categorisation-ratios-ratio", Input).value.strip(),
            year=self._typed_year(),
        )

        async def write() -> bool:
            result = await self.set_door(request)
            prior = result.prior_ratio or "-"
            self.show_outcome(
                lambda: tr(
                    "tui.ledger.categorisation.ratios.set_done",
                    category=result.category,
                    ratio=result.ratio,
                    prior=prior,
                )
            )
            await self._reread(request.year)
            return True

        return StagedChangeV1(
            summary=lambda: tr(
                "tui.ledger.categorisation.ratios.stage_set",
                category=request.category,
                ratio=request.ratio,
                year=request.year,
            ),
            write=write,
        )

    def _stage_unset(self) -> StagedChangeV1:
        request = LedgerRatiosUnsetRequest(profile_id=self.unset_door.profile_id, category=self._category())
        year = self.year

        async def write() -> bool:
            result = await self.unset_door(request)
            cleared = result.outcome == "cleared"
            prior = result.prior_ratio or "-"
            self.show_outcome(
                lambda: tr(
                    "tui.ledger.categorisation.ratios.unset_done"
                    if cleared
                    else "tui.ledger.categorisation.ratios.unset_nothing",
                    category=result.category,
                    prior=prior,
                )
            )
            if cleared and year is not None:
                await self._reread(year)
            return cleared

        return StagedChangeV1(
            summary=lambda: tr("tui.ledger.categorisation.ratios.stage_unset", category=request.category),
            write=write,
            destructive=True,
        )

    async def _reread(self, year: int) -> None:
        listed = await self.list_door(LedgerRatiosListRequest(profile_id=self.list_door.profile_id, year=year))
        eligible = await self.eligible_door(
            LedgerRatiosEligibleRequest(profile_id=self.eligible_door.profile_id, year=year)
        )
        self.year = year
        self.overrides = listed.rows
        self.eligible = eligible.rows
        self.paint_tables()

    @override
    def clear_private_view(self) -> None:
        super().clear_private_view()
        self.overrides = ()
        self.eligible = ()
        self.paint_tables()


__all__ = ["LedgerRatiosScreen", "validation_text"]
