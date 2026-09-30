"""A real modelo 303 reads its rate boxes as the official form prints them, and a filed one asks for nothing.

The form is built by the real read model from the published authority, and the
rows come from the workbench's own page layout. Expected rates are the ones the
official 303 design prints for these rows: 4 % super-reduced, 10 % reduced and
the 2 % transitional rate.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ......application.modelo.work_form import build_modelo_work_form
from ......application.modelo.work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormOrigin,
    ModeloWorkForm,
    address_key,
)
from ......application.modelo.work_form_service import modelo_form_snapshot
from ......application.modelo.work_review import (
    ModeloWorkProgress,
    ModeloWorkReview,
    build_modelo_work_review_casillas,
)
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import lookup_translation
from ......core.modelo_work_progress_state import ModeloWorkProgressState
from ......core.period import Period
from ......domain.calculations.registry.authority import PinnedAuthorityOperation
from ......domain.filing.schema import ModeloValueKind
from ......domain.modelos.calculation_revision import CalculationRevisionState
from ......domain.modelos.codes import ModeloCode
from ..casilla_list import CasillaListEntry, CasillaListHeading, rate_note, row_value_text, value_text
from ..page_items import WorkbenchFilter, first_attention, page_items, section_nav_text, workbench_pages

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PERCENT = "\u00a0%"
_GROUNDED = {"02": f"4{_PERCENT}", "05": f"10{_PERCENT}", "166": f"2{_PERCENT}"}
_UNGROUNDED = ("08", "151", "154", "157", "17", "20", "23")


def _form(
    operation: PinnedAuthorityOperation,
    *,
    held: dict[str, Decimal] | None = None,
    lifecycle: CalculationRevisionState | None = None,
) -> ModeloWorkForm:
    period = Period.from_year_and_code(2026, "1T")
    revision_id = str(operation.revision_for_context("303", filing_year=2026, period="1T").id)
    snapshot = modelo_form_snapshot(operation, ModeloCode("303"), 2026, period, revision_id)
    values = held or {}
    rows = build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation)
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000455",
        modelo="303",
        filing_year=2026,
        period=period,
        registry_revision_id=snapshot.revision.id,
        work_unit_id="e" * 64,
        calculation_revision_id=None,
        lifecycle_state=lifecycle,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=tuple(
            row.model_copy(update={"value": values[str(row.casilla_id)], "realised_kind": ModeloValueKind.LITERAL})
            if str(row.casilla_id) in values
            else row
            for row in rows
        ),
        findings=(),
        blockers=(),
    )
    return build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=operation.form_layout("303", snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=None,
        overridden_binding_ids=None,
        language=OutputLanguage.EN,
    )


def _entries(form: ModeloWorkForm) -> dict[str, CasillaListEntry]:
    """Every row the workbench lays out, by its box number."""
    return {
        item.field.box: item
        for page in workbench_pages(form)
        for item in page_items(page, staged={})
        if isinstance(item, CasillaListEntry) and item.field.box is not None
    }


def test_a_grounded_rate_box_reads_the_rate_and_an_ungrounded_one_claims_none(
    operation: PinnedAuthorityOperation,
) -> None:
    entries = _entries(_form(operation))
    fixed = {
        lookup_translation("tui.modelo.workbench.value.fixed_by_design", locale=item.value) for item in OutputLanguage
    }

    with override_settings(cadrumo_output_language="en"):
        for box, rate in _GROUNDED.items():
            entry = entries[box]
            assert entry.rate_of_row, box
            assert row_value_text(entry, OutputLanguage.EN) == rate, box
            assert value_text(entry, OutputLanguage.EN) == rate, box
            assert rate_note(entry) is None, box
        assert row_value_text(entries["05"], OutputLanguage.ES) == f"10{_PERCENT}"
        for box in _UNGROUNDED:
            entry = entries[box]
            assert entry.rate_of_row, box
            assert entry.field.grounded_rate is None, box
            assert row_value_text(entry, OutputLanguage.EN) == "·", box
            assert value_text(entry, OutputLanguage.EN) not in fixed, box
            assert rate_note(entry) == lookup_translation("tui.modelo.workbench.rate.not_grounded", locale="en")
        # A box that is not a row's rate box never carries the note.
        assert rate_note(entries["01"]) is None
        assert not any(row_value_text(entry, OutputLanguage.EN) in fixed for entry in entries.values())


def test_a_declaration_recorded_as_filed_marks_nothing_to_do(operation: PinnedAuthorityOperation) -> None:
    unheld = _form(operation)
    optional = next(
        field
        for field in unheld.fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1)
        and field.origin is ModeloFormOrigin.OPTIONAL_EMPTY
        and field.data_type == "money"
    )
    address = optional.address
    assert isinstance(address, ModeloFormCasillaAddressV1)
    held = {str(address.casilla_id): Decimal("35.00")}
    draft = _form(operation, held=held)
    filed = _form(operation, held=held, lifecycle=CalculationRevisionState.PRESENTADO)
    assert filed.filing is not None

    key = address_key(optional.address)
    assumed = next(field for field in draft.fields() if address_key(field.address) == key)
    assert assumed.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
    # Filing keeps the box's origin; only the counts say nothing is left to confirm.
    still_assumed = next(field for field in filed.fields() if address_key(field.address) == key)
    assert still_assumed.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
    assert filed.counts.default_to_confirm == 0

    def to_do(form: ModeloWorkForm) -> set[tuple[str, str]]:
        return {
            item.key
            for page in workbench_pages(form)
            for item in page_items(page, staged={}, mode=WorkbenchFilter.ATTENTION)
            if isinstance(item, CasillaListEntry)
        }

    def marks(form: ModeloWorkForm) -> str:
        pages = workbench_pages(form)
        navigator = [section_nav_text(section, 60) for page in pages for section in page.sections]
        headings = [
            item.text for page in pages for item in page_items(page, staged={}) if isinstance(item, CasillaListHeading)
        ]
        return " | ".join((*navigator, *headings))

    assert key in to_do(draft)
    assert key not in to_do(filed)
    assert not any(
        address_key(field.address) in to_do(filed)
        for field in filed.fields()
        if field.origin in {ModeloFormOrigin.DEFAULT_TO_CONFIRM, ModeloFormOrigin.NEEDS_INPUT}
    )
    assert "◐" not in marks(filed)
    # Nothing on a filed declaration sends the filer to a missing or assumed value.
    attention = first_attention(workbench_pages(filed))
    if attention is not None:
        index, found = attention
        field = next(item for item in workbench_pages(filed)[index].fields() if address_key(item.address) == found)
        assert field.origin not in {ModeloFormOrigin.DEFAULT_TO_CONFIRM, ModeloFormOrigin.NEEDS_INPUT}, found
