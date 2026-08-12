"""Read-only Textual projection of the canonical modelo work review.

The application layer owns every join represented here.  This adapter accepts
one already-built :class:`ModeloWorkReview` through the public
``application.modelo`` facade and renders it without consulting repositories,
the registry, CLI payloads, or private application modules.  Consequently the
screen cannot derive a competing readiness verdict or mutate modelo work.

The casilla table keeps declared, concrete, and realised origins in distinct
columns.  Progress counts appear only beside their named completeness-manifest
denominator; an undefined denominator renders the closed ``undefined`` state
without manufacturing a zero.  Filtering is intentionally absent: faceted
filtering belongs to the following plan step.
"""

from __future__ import annotations

import json
from typing import ClassVar, cast, override

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingsMap
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from ....application.modelo import ModeloWorkProgressDenominator, ModeloWorkReview
from ....core import ModeloWorkProgressState
from ....core.i18n import tr
from ._theme import BASE_CSS, ContentDataTable, ContentScroll, install_cadrumo_themes, toggle_appearance


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
            yield Static(id="modelo-review-casillas", classes="cadrumo-panel")
            yield Static(id="modelo-review-findings", classes="cadrumo-panel")
            yield Static(id="modelo-review-blockers", classes="cadrumo-panel")
        yield Footer()

    def on_mount(self) -> None:
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
        for row in review.casillas:
            concrete = _json(
                {
                    "bindings": tuple(binding.model_dump(mode="json") for binding in row.concrete_bindings),
                    "formula": None if row.concrete_formula is None else row.concrete_formula.model_dump(mode="json"),
                    "relations": tuple(relation.model_dump(mode="json") for relation in row.relation_consumption),
                },
            )
            schema = " · ".join(
                (
                    row.data_type,
                    "/".join(row.section_path),
                    _json(None if row.constraints is None else row.constraints.model_dump(mode="json")),
                ),
            )
            official = ":".join(
                part for part in (row.official_box_status.value, row.official_reference) if part is not None
            )
            realised = ":".join(
                part
                for part in (
                    row.realised_kind.value,
                    _json(row.value),
                    None if row.origin_anomaly is None else row.origin_anomaly.value,
                )
                if part is not None
            )
            grounding = _json(
                {
                    "formula_id": row.formula_id,
                    "legal_refs": row.legal_refs,
                    "source_refs": row.source_refs,
                },
            )
            blocked_by = " | ".join(
                f"{blocker.axis.value}:{blocker.native_code}:{_json(dict(blocker.facts))}" for blocker in row.blocked_by
            )
            table.add_row(
                f"{row.number} · {row.casilla_id}" + ("" if row.segmento is None else f" · {row.segmento}"),
                row.label,
                schema,
                official,
                row.declared_input_kind.value,
                concrete,
                realised,
                grounding,
                blocked_by,
                key=str(row.casilla_id),
            )

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
        table.add_columns(
            tr("flows.modelo_review.column.severity"),
            tr("flows.modelo_review.column.kind"),
            tr("flows.modelo_review.column.casilla_id"),
            tr("flows.modelo_review.column.expectation_id"),
            tr("flows.modelo_review.column.message"),
            tr("flows.modelo_review.column.facts"),
            tr("flows.modelo_review.column.grounding"),
        )
        for index, finding in enumerate(review.findings):
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
        table.add_columns(
            tr("flows.modelo_review.column.action"),
            tr("flows.modelo_review.column.code"),
            tr("flows.modelo_review.column.facts"),
        )
        for index, blocker in enumerate(review.blockers):
            table.add_row(
                blocker.axis.value,
                blocker.native_code,
                _json(dict(blocker.facts)),
                key=f"blocker-{index}",
            )

    def action_quit_review(self) -> None:
        self.review_app.exit(None)

    def action_toggle_appearance(self) -> None:
        toggle_appearance(self.review_app)


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
    #modelo-review-casillas DataTable,
    #modelo-review-findings DataTable,
    #modelo-review-blockers DataTable { width: 100%; height: auto; background: $surface; }
    """
    )

    def __init__(self, review: ModeloWorkReview) -> None:
        super().__init__()
        self.review = review

    def on_mount(self) -> None:
        install_cadrumo_themes(self)
        self.push_screen(ModeloWorkReviewScreen())


__all__ = ["ModeloWorkReviewApp", "ModeloWorkReviewScreen"]
