"""Read-only Textual projection of the canonical modelo work review.

The application layer owns every join represented here.  This entrypoint projection accepts
one already-built :class:`ModeloWorkReview` from the defining public
``application.modelo.work_review_projection`` module and renders it without consulting repositories,
the registry, CLI payloads, or private application modules.  Consequently the
screen cannot derive a competing readiness verdict or mutate modelo work.

The casilla table keeps declared, concrete, and realised origins in distinct
columns.  Progress counts appear only beside their named completeness-manifest
denominator; an undefined denominator renders the closed ``undefined`` state
without manufacturing a zero. Facets inspect only closed enum and presence
facts already carried by the frozen record; they never derive domain state.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import ClassVar, cast, get_args, override

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingsMap
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Collapsible, Footer, Label, Select, Static

from .....application.modelo.work_review_projection import (
    BlockerRef,
    ModeloWorkOriginAnomaly,
    ModeloWorkProgressDenominator,
    ModeloWorkReview,
    ModeloWorkReviewCasilla,
)
from .....core import BindingSourceKind, EstadoCasillaOficial, ModeloWorkProgressState, OperatorActionAxis
from .....core.i18n import tr
from .....domain.calculations.registry import InputKind, RelationConsumptionChannel
from .....domain.filing import ModeloValueKind
from .....domain.modelos import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...components.theme import (
    BASE_CSS,
    install_cadrumo_themes,
    toggle_appearance,
)
from ...components.widgets import ContentDataTable, ContentScroll

_PRESENT = "present"
_ABSENT = "absent"


def _option_label(axis: str, value: str) -> str:
    """Resolve one localized label while preserving its canonical payload."""
    return tr("flows.modelo_review.filter.option." + f"{axis}.{value}")


def _enum_options[EnumT: StrEnum](enum_type: type[EnumT], *, axis: str) -> tuple[tuple[str, str], ...]:
    """Return localized labels paired with every canonical enum member value."""
    return tuple((_option_label(axis, member.value), member.value) for member in enum_type)


def _relation_channel_options() -> tuple[tuple[str, str], ...]:
    """Return the registry-owned Literal's exact localized option set."""
    options: list[tuple[str, str]] = []
    for channel in get_args(RelationConsumptionChannel):
        if not isinstance(channel, str):
            raise TypeError("relation consumption channel literal must be text")
        options.append((_option_label("relation_channel", channel), channel))
    return tuple(options)


def _presence_options() -> tuple[tuple[str, str], ...]:
    """Return the localized closed choices for a nullable/presence fact."""
    return (
        (tr("flows.modelo_review.filter.present"), _PRESENT),
        (tr("flows.modelo_review.filter.absent"), _ABSENT),
    )


def _resolved_options() -> tuple[tuple[str, bool], ...]:
    """Return localized labels paired with the canonical resolved boolean."""
    return (
        (tr("flows.modelo_review.filter.resolved"), True),
        (tr("flows.modelo_review.filter.unresolved"), False),
    )


def _json(value: object) -> str:
    """Render typed model facts deterministically without interpreting them."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


class ModeloWorkReviewScreen(Screen[None]):
    """Full review of one canonical modelo work record."""

    BINDINGS: ClassVar = [
        Binding("q", "quit_review", ""),
        Binding("escape", "quit_review", ""),
        Binding("f3", "toggle_appearance", "", show=False),
    ]

    @override
    def compose(self) -> ComposeResult:
        yield Static(id="modelo-review-header", classes="cadrumo-banner")
        with (
            ContentScroll(id="modelo-review-body", classes="cadrumo-scroll"),
            Vertical(
                classes="cadrumo-column",
            ),
        ):
            yield Static(id="modelo-review-summary", classes="cadrumo-panel")
            with (
                Collapsible(
                    title=tr("flows.modelo_review.filter.filters"),
                    collapsed=True,
                    id="modelo-review-filter-disclosure",
                    classes="cadrumo-panel",
                ),
                Vertical(id="modelo-review-filters"),
            ):
                yield Label(tr("flows.modelo_review.filter.input_kind"), classes="modelo-review-filter-label")
                yield Select[str](
                    _enum_options(InputKind, axis="input_kind"),
                    prompt=tr("flows.modelo_review.filter.all"),
                    id="modelo-review-filter-input-kind",
                )
                yield Label(tr("flows.modelo_review.filter.binding_source"), classes="modelo-review-filter-label")
                yield Select[str](
                    _enum_options(BindingSourceKind, axis="binding_source"),
                    prompt=tr("flows.modelo_review.filter.all"),
                    id="modelo-review-filter-binding-source",
                )
                yield Label(tr("flows.modelo_review.filter.binding_presence"), classes="modelo-review-filter-label")
                yield Select[str](
                    _presence_options(),
                    prompt=tr("flows.modelo_review.filter.all"),
                    id="modelo-review-filter-binding-presence",
                )
                yield Label(tr("flows.modelo_review.filter.binding_resolved"), classes="modelo-review-filter-label")
                yield Select[bool](
                    _resolved_options(),
                    prompt=tr("flows.modelo_review.filter.all"),
                    id="modelo-review-filter-binding-resolved",
                )
                yield Label(tr("flows.modelo_review.filter.formula_presence"), classes="modelo-review-filter-label")
                yield Select[str](
                    _presence_options(),
                    prompt=tr("flows.modelo_review.filter.all"),
                    id="modelo-review-filter-formula-presence",
                )
                yield Label(tr("flows.modelo_review.filter.relation_presence"), classes="modelo-review-filter-label")
                yield Select[str](
                    _presence_options(),
                    prompt=tr("flows.modelo_review.filter.all"),
                    id="modelo-review-filter-relation-presence",
                )
                yield Label(tr("flows.modelo_review.filter.relation_channel"), classes="modelo-review-filter-label")
                yield Select[str](
                    _relation_channel_options(),
                    prompt=tr("flows.modelo_review.filter.all"),
                    id="modelo-review-filter-relation-channel",
                )
                yield Label(tr("flows.modelo_review.filter.realised_kind"), classes="modelo-review-filter-label")
                yield Select[str](
                    _enum_options(ModeloValueKind, axis="realised_kind"),
                    prompt=tr("flows.modelo_review.filter.all"),
                    id="modelo-review-filter-realised-kind",
                )
                yield Label(tr("flows.modelo_review.filter.origin_anomaly"), classes="modelo-review-filter-label")
                yield Select[str](
                    _enum_options(ModeloWorkOriginAnomaly, axis="origin_anomaly"),
                    prompt=tr("flows.modelo_review.filter.all"),
                    id="modelo-review-filter-origin-anomaly",
                )
                yield Label(
                    tr("flows.modelo_review.filter.origin_anomaly_presence"),
                    classes="modelo-review-filter-label",
                )
                yield Select[str](
                    _presence_options(),
                    prompt=tr("flows.modelo_review.filter.all"),
                    id="modelo-review-filter-origin-anomaly-presence",
                )
                yield Label(
                    tr("flows.modelo_review.filter.estado_casilla_oficial"),
                    classes="modelo-review-filter-label",
                )
                yield Select[str](
                    _enum_options(EstadoCasillaOficial, axis="estado_casilla_oficial"),
                    prompt=tr("flows.modelo_review.filter.all"),
                    id="modelo-review-filter-estado-casilla-oficial",
                )
                yield Label(tr("flows.modelo_review.filter.casilla_blocker"), classes="modelo-review-filter-label")
                yield Select[str](
                    _enum_options(OperatorActionAxis, axis="operator_action"),
                    prompt=tr("flows.modelo_review.filter.all"),
                    id="modelo-review-filter-casilla-blocker",
                )
                yield Label(
                    tr("flows.modelo_review.filter.casilla_blocker_presence"),
                    classes="modelo-review-filter-label",
                )
                yield Select[str](
                    _presence_options(),
                    prompt=tr("flows.modelo_review.filter.all"),
                    id="modelo-review-filter-casilla-blocker-presence",
                )
                yield Label(tr("flows.modelo_review.filter.finding_kind"), classes="modelo-review-filter-label")
                yield Select[str](
                    _enum_options(ModeloVerificationFindingKind, axis="finding_kind"),
                    prompt=tr("flows.modelo_review.filter.all"),
                    id="modelo-review-filter-finding-kind",
                )
                yield Label(tr("flows.modelo_review.filter.finding_severity"), classes="modelo-review-filter-label")
                yield Select[str](
                    _enum_options(ModeloVerificationFindingSeverity, axis="finding_severity"),
                    prompt=tr("flows.modelo_review.filter.all"),
                    id="modelo-review-filter-finding-severity",
                )
                yield Label(tr("flows.modelo_review.filter.record_blocker"), classes="modelo-review-filter-label")
                yield Select[str](
                    _enum_options(OperatorActionAxis, axis="operator_action"),
                    prompt=tr("flows.modelo_review.filter.all"),
                    id="modelo-review-filter-record-blocker",
                )
                yield Button(tr("flows.modelo_review.filter.reset"), id="modelo-review-filter-reset")
            yield Static(id="modelo-review-casillas", classes="cadrumo-panel")
            yield Static(id="modelo-review-findings", classes="cadrumo-panel")
            yield Static(id="modelo-review-blockers", classes="cadrumo-panel")
        yield Footer()

    def on_mount(self) -> None:
        """Render the immutable review when the screen enters the application."""
        self._localize_bindings()
        review = self.review_app.review
        self.query_one("#modelo-review-header", Static).update(
            tr(
                "flows.modelo_review.title",
                modelo=review.modelo,
                filing_year=review.filing_year,
                period=review.period.registry_token,
            ),
        )
        self._mount_summary(review)
        self._mount_casillas(review)
        self._mount_findings(review)
        self._mount_blockers(review)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Re-project visible rows when any closed facet changes."""
        if event.select.id is not None and event.select.id.startswith("modelo-review-filter-"):
            self._refresh_filtered_rows()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Restore every facet to the canonical unfiltered projection."""
        if event.button.id != "modelo-review-filter-reset":
            return
        for chooser in self.query("#modelo-review-filters Select"):
            cast("Select[str]", chooser).clear()
        self._refresh_filtered_rows()

    @property
    def review_app(self) -> ModeloWorkReviewApp:
        """Return the one owning application, refusing a foreign screen host."""
        return _require_review_app(cast(object, self.app))

    def _localize_bindings(self) -> None:
        self._bindings = BindingsMap(
            [
                Binding("q", "quit_review", tr("flows.status.binding_quit")),
                Binding("escape", "quit_review", tr("flows.status.binding_quit")),
                Binding("f3", "toggle_appearance", "", show=False),
            ],
        )
        self.refresh_bindings()

    def _selected(self, selector: str) -> str | None:
        value = cast("Select[str]", self.query_one(selector, Select)).value
        return value if isinstance(value, str) else None

    def _selected_bool(self, selector: str) -> bool | None:
        value = cast("Select[bool]", self.query_one(selector, Select)).value
        return value if isinstance(value, bool) else None

    @staticmethod
    def _matches_presence(selected: str | None, present: bool) -> bool:
        return selected is None or (selected == _PRESENT) is present

    def _casilla_matches(self, row: ModeloWorkReviewCasilla) -> bool:
        return (
            self._casilla_matches_binding_filters(row)
            and self._casilla_matches_presence_filters(row)
            and self._casilla_matches_realised_filters(row)
        )

    def _casilla_matches_binding_filters(self, row: ModeloWorkReviewCasilla) -> bool:
        input_kind = self._selected("#modelo-review-filter-input-kind")
        binding_source = self._selected("#modelo-review-filter-binding-source")
        binding_resolved = self._selected_bool("#modelo-review-filter-binding-resolved")
        return all(
            (
                input_kind is None or row.declared_input_kind.value == input_kind,
                binding_source is None
                or any(binding.source.value == binding_source for binding in row.concrete_bindings),
                binding_resolved is None
                or any(binding.resolved is binding_resolved for binding in row.concrete_bindings),
            ),
        )

    def _casilla_matches_presence_filters(self, row: ModeloWorkReviewCasilla) -> bool:
        relation_channel = self._selected("#modelo-review-filter-relation-channel")
        return all(
            (
                self._matches_presence(
                    self._selected("#modelo-review-filter-binding-presence"),
                    bool(row.concrete_bindings),
                ),
                self._matches_presence(
                    self._selected("#modelo-review-filter-formula-presence"),
                    row.concrete_formula is not None,
                ),
                self._matches_presence(
                    self._selected("#modelo-review-filter-relation-presence"),
                    bool(row.relation_consumption),
                ),
                relation_channel is None
                or any(relation_channel in relation.channels for relation in row.relation_consumption),
            ),
        )

    def _casilla_matches_realised_filters(self, row: ModeloWorkReviewCasilla) -> bool:
        realised_kind = self._selected("#modelo-review-filter-realised-kind")
        anomaly = self._selected("#modelo-review-filter-origin-anomaly")
        estado_casilla_oficial = self._selected("#modelo-review-filter-estado-casilla-oficial")
        blocker_axis = self._selected("#modelo-review-filter-casilla-blocker")
        return all(
            (
                realised_kind is None or row.realised_kind.value == realised_kind,
                anomaly is None or (row.origin_anomaly is not None and row.origin_anomaly.value == anomaly),
                self._matches_presence(
                    self._selected("#modelo-review-filter-origin-anomaly-presence"),
                    row.origin_anomaly is not None,
                ),
                estado_casilla_oficial is None or row.estado_casilla_oficial.value == estado_casilla_oficial,
                blocker_axis is None or any(blocker.axis.value == blocker_axis for blocker in row.blocked_by),
                self._matches_presence(
                    self._selected("#modelo-review-filter-casilla-blocker-presence"),
                    bool(row.blocked_by),
                ),
            ),
        )

    def _finding_matches(self, finding: ModeloVerificationFinding) -> bool:
        kind = self._selected("#modelo-review-filter-finding-kind")
        severity = self._selected("#modelo-review-filter-finding-severity")
        return (kind is None or finding.kind.value == kind) and (severity is None or finding.severity.value == severity)

    def _blocker_matches(self, blocker: BlockerRef) -> bool:
        axis = self._selected("#modelo-review-filter-record-blocker")
        return axis is None or blocker.axis.value == axis

    def _refresh_filtered_rows(self) -> None:
        review = self.review_app.review
        casillas = tuple(row for row in review.casillas if self._casilla_matches(row))
        self._populate_casillas(casillas)
        if review.findings:
            findings = tuple(finding for finding in review.findings if self._finding_matches(finding))
            self._populate_findings(findings)
        if review.blockers:
            blockers = tuple(blocker for blocker in review.blockers if self._blocker_matches(blocker))
            self._populate_blockers(blockers)

    def _mount_summary(self, review: ModeloWorkReview) -> None:
        progress = review.progress
        if progress.state is ModeloWorkProgressState.UNDEFINED:
            progress_line = progress.state.value
        else:
            denominator = cast(ModeloWorkProgressDenominator, progress.denominator)
            materialised_count = cast(int, progress.materialised_count)
            target_count = cast(int, progress.target_count)
            progress_line = " · ".join(
                (
                    progress.state.value,
                    f"{materialised_count}/{target_count}",
                    denominator.kind,
                    str(denominator.source_ref),
                    str(denominator.registry_revision_id),
                ),
            )
        lines = (
            f"{tr('flows.modelo_review.summary.work_unit')}\t{review.work_unit_id}",
            f"{tr('flows.modelo_review.summary.registry_revision')}\t{review.registry_revision_id}",
            f"{tr('flows.modelo_review.summary.calculation_revision')}\t{review.calculation_revision_id or ''}",
            f"{tr('flows.modelo_review.summary.lifecycle_state')}\t"
            f"{review.lifecycle_state.value if review.lifecycle_state is not None else ''}",
            f"{tr('flows.modelo_review.summary.verification_outcome')}\t"
            f"{review.verification_outcome.value if review.verification_outcome is not None else ''}",
            f"{tr('flows.modelo_review.summary.progress')}\t{progress_line}",
        )
        self.query_one("#modelo-review-summary", Static).mount(
            Static("\n".join(lines), id="modelo-review-summary-lines", markup=False),
        )

    def _mount_casillas(self, review: ModeloWorkReview) -> None:
        panel = self.query_one("#modelo-review-casillas", Static)
        table: ContentDataTable[str] = ContentDataTable(
            id="modelo-review-casillas-table",
            cursor_type="row",
            zebra_stripes=True,
        )
        panel.mount(table)
        panel.mount(
            Static(
                tr("flows.modelo_review.filter.no_matching_casillas"),
                id="modelo-review-casillas-empty",
                classes="modelo-review-filter-empty",
            ),
        )
        table.add_columns(
            tr("flows.modelo_review.column.casilla"),
            tr("flows.modelo_review.column.label"),
            tr("flows.modelo_review.column.schema"),
            tr("flows.modelo_review.column.official"),
            tr("flows.modelo_review.column.declared"),
            tr("flows.modelo_review.column.concrete"),
            tr("flows.modelo_review.column.realised"),
            tr("flows.modelo_review.column.grounding"),
            tr("flows.modelo_review.column.blocked_by"),
        )
        self._populate_casillas(review.casillas)

    def _populate_casillas(self, rows: tuple[ModeloWorkReviewCasilla, ...]) -> None:
        table = cast(
            "ContentDataTable[str]",
            self.query_one("#modelo-review-casillas-table", ContentDataTable),
        )
        table.clear()
        for row in rows:
            table.add_row(
                *_casilla_row_values(row),
                key=str(row.casilla_id),
            )
        self.query_one("#modelo-review-casillas-empty", Static).display = not rows

    def _mount_findings(self, review: ModeloWorkReview) -> None:
        panel = self.query_one("#modelo-review-findings", Static)
        if not review.findings:
            panel.remove()
            return
        table: ContentDataTable[str] = ContentDataTable(
            id="modelo-review-findings-table",
            cursor_type="none",
            zebra_stripes=True,
        )
        panel.mount(table)
        panel.mount(
            Static(
                tr("flows.modelo_review.filter.no_matching_findings"),
                id="modelo-review-findings-empty",
                classes="modelo-review-filter-empty",
            ),
        )
        table.add_columns(
            tr("flows.modelo_review.column.severity"),
            tr("flows.modelo_review.column.kind"),
            tr("flows.modelo_review.column.casilla_id"),
            tr("flows.modelo_review.column.expectation_id"),
            tr("flows.modelo_review.column.message"),
            tr("flows.modelo_review.column.facts"),
            tr("flows.modelo_review.column.grounding"),
        )
        self._populate_findings(review.findings)

    def _populate_findings(self, findings: tuple[ModeloVerificationFinding, ...]) -> None:
        table = cast(
            "ContentDataTable[str]",
            self.query_one("#modelo-review-findings-table", ContentDataTable),
        )
        table.clear()
        for index, finding in enumerate(findings):
            table.add_row(
                finding.severity.value,
                finding.kind.value,
                "" if finding.casilla_id is None else str(finding.casilla_id),
                "" if finding.expectation_id is None else str(finding.expectation_id),
                tr(finding.message_locale_key, **finding.message_facts),
                _json(dict(finding.message_facts)),
                _json(
                    {
                        "legal_refs": finding.legal_refs,
                        "source_refs": finding.source_refs,
                    },
                ),
                key=f"finding-{index}",
            )
        self.query_one("#modelo-review-findings-empty", Static).display = not findings

    def _mount_blockers(self, review: ModeloWorkReview) -> None:
        panel = self.query_one("#modelo-review-blockers", Static)
        if not review.blockers:
            panel.remove()
            return
        table: ContentDataTable[str] = ContentDataTable(
            id="modelo-review-blockers-table",
            cursor_type="none",
            zebra_stripes=True,
        )
        panel.mount(table)
        panel.mount(
            Static(
                tr("flows.modelo_review.filter.no_matching_blockers"),
                id="modelo-review-blockers-empty",
                classes="modelo-review-filter-empty",
            ),
        )
        table.add_columns(
            tr("flows.modelo_review.column.action"),
            tr("flows.modelo_review.column.code"),
            tr("flows.modelo_review.column.facts"),
        )
        self._populate_blockers(review.blockers)

    def _populate_blockers(self, blockers: tuple[BlockerRef, ...]) -> None:
        table = cast(
            "ContentDataTable[str]",
            self.query_one("#modelo-review-blockers-table", ContentDataTable),
        )
        table.clear()
        for index, blocker in enumerate(blockers):
            table.add_row(
                blocker.axis.value,
                blocker.native_code,
                _json(dict(blocker.facts)),
                key=f"blocker-{index}",
            )
        self.query_one("#modelo-review-blockers-empty", Static).display = not blockers

    def action_quit_review(self) -> None:
        """Exit the standalone review host without changing the work record."""
        self.review_app.exit(None)

    def action_toggle_appearance(self) -> None:
        """Toggle the shared presentation theme for the review host."""
        toggle_appearance(self.review_app)


def _casilla_row_values(row: ModeloWorkReviewCasilla) -> tuple[str, ...]:
    """Render one review casilla into the table's stable text columns."""
    return (
        f"{row.number} · {row.casilla_id}" + ("" if row.segmento is None else f" · {row.segmento}"),
        row.label,
        _casilla_schema_text(row),
        _casilla_official_text(row),
        row.declared_input_kind.value,
        _casilla_concrete_text(row),
        _casilla_realised_text(row),
        _casilla_grounding_text(row),
        _casilla_blockers_text(row),
    )


def _casilla_concrete_text(row: ModeloWorkReviewCasilla) -> str:
    return _json(
        {
            "bindings": tuple(binding.model_dump(mode="json") for binding in row.concrete_bindings),
            "formula": None if row.concrete_formula is None else row.concrete_formula.model_dump(mode="json"),
            "relations": tuple(relation.model_dump(mode="json") for relation in row.relation_consumption),
        },
    )


def _casilla_schema_text(row: ModeloWorkReviewCasilla) -> str:
    return " · ".join(
        (
            row.data_type,
            "/".join(row.section_path),
            _json(None if row.constraints is None else row.constraints.model_dump(mode="json")),
        ),
    )


def _casilla_official_text(row: ModeloWorkReviewCasilla) -> str:
    return ":".join(part for part in (row.estado_casilla_oficial.value, row.official_reference) if part is not None)


def _casilla_realised_text(row: ModeloWorkReviewCasilla) -> str:
    return ":".join(
        part
        for part in (
            row.realised_kind.value,
            _json(row.value),
            None if row.origin_anomaly is None else row.origin_anomaly.value,
        )
        if part is not None
    )


def _casilla_grounding_text(row: ModeloWorkReviewCasilla) -> str:
    return _json(
        {
            "formula_id": row.formula_id,
            "legal_refs": row.legal_refs,
            "source_refs": row.source_refs,
        },
    )


def _casilla_blockers_text(row: ModeloWorkReviewCasilla) -> str:
    return " | ".join(
        f"{blocker.axis.value}:{blocker.native_code}:{_json(dict(blocker.facts))}" for blocker in row.blocked_by
    )


def _require_review_app(app: object) -> ModeloWorkReviewApp:
    """Narrow a screen host without leaving an unknown generic App type."""
    if not isinstance(app, ModeloWorkReviewApp):
        raise TypeError(
            f"{ModeloWorkReviewScreen.__name__} requires {ModeloWorkReviewApp.__name__}, got {type(app).__name__}",
        )
    return app


class ModeloWorkReviewApp(App[None]):
    """Standalone host for a canonical modelo work review screen."""

    CSS = (
        BASE_CSS
        + """
    #modelo-review-body { width: 100%; height: 1fr; }
    #modelo-review-summary-lines { height: auto; }
    #modelo-review-filters {
        height: auto;
        layout: grid;
        grid-size: 2;
        grid-columns: 2fr 3fr;
        grid-rows: auto;
        grid-gutter: 0 1;
    }
    .modelo-review-filter-label,
    .modelo-review-filter-empty { height: auto; }
    #modelo-review-casillas DataTable,
    #modelo-review-findings DataTable,
    #modelo-review-blockers DataTable { width: 100%; height: auto; background: $surface; }
    """
    )

    def __init__(self, review: ModeloWorkReview) -> None:
        """Bind the one immutable application review rendered by this host."""
        super().__init__()
        self.review = review

    def on_mount(self) -> None:
        """Install shared themes and open the canonical review screen."""
        install_cadrumo_themes(self)
        self.push_screen(ModeloWorkReviewScreen())


__all__ = ["ModeloWorkReviewApp", "ModeloWorkReviewScreen"]
