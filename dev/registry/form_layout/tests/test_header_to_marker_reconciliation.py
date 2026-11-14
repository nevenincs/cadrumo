"""An unseen blank-or-constant slot may change its feed from a producer fact to a computed marker."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_semantics import ExportComputedKey
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ...compiler.form_layout_integrity import form_layout_source_digest
from ...compiler.loader import load_modelo_directory
from ..reconciliation import reconcile_unreferenced_export_producers

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MARKER_KEY = "continuation_page_marker"


def _with_marker_fields(revision: ModeloRevision, **updates: object) -> ModeloRevision:
    layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    record.model_copy(
                        update={
                            "fields": tuple(
                                field.model_copy(update=updates) if field.computed_key == _MARKER_KEY else field
                                for field in record.fields
                            )
                        }
                    )
                    for record in layout.records
                )
            }
        )
        for layout in revision.export_layouts
    )
    return revision.model_copy(update={"export_layouts": layouts})


@pytest.fixture
def after() -> ModeloRevision:
    return load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/369")).revisions["esquema-exterior"]


def _header_feed(revision: ModeloRevision) -> ModeloRevision:
    layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    record.model_copy(
                        update={
                            "fields": tuple(
                                field.model_copy(
                                    update={
                                        "kind": CasillaFieldKind.HEADER,
                                        "computed_key": None,
                                        "producer_key": FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA,
                                    }
                                )
                                if field.computed_key == _MARKER_KEY
                                else field
                                for field in record.fields
                            )
                        }
                    )
                    for record in layout.records
                )
            }
        )
        for layout in revision.export_layouts
    )
    return revision.model_copy(update={"export_layouts": layouts})


def _sharing_the_old_form(before: ModeloRevision, after: ModeloRevision) -> tuple[ModeloRevision, ModeloRevision]:
    """Both sides hold the one form as it stood, stamped with the state before the change."""
    form = before.form_layouts[0].model_copy(update={"source_state_digest": form_layout_source_digest(before)})
    return (
        before.model_copy(update={"form_layouts": (form,)}),
        after.model_copy(update={"form_layouts": (form,)}),
    )


def test_the_form_follows_a_feed_change_that_keeps_every_byte_rule(after: ModeloRevision) -> None:
    old, new = _sharing_the_old_form(_header_feed(after), after)
    reconciled = reconcile_unreferenced_export_producers(old, new)
    assert reconciled.source_state_digest == form_layout_source_digest(new)
    assert reconciled.source_state_digest != form_layout_source_digest(old)


def test_a_required_slot_may_not_lose_its_requirement_through_the_feed_change(after: ModeloRevision) -> None:
    old, new = _sharing_the_old_form(_header_feed(after), _with_marker_fields(after, required=False))
    with pytest.raises(RegistryValidationError, match="beyond unreferenced header producers"):
        reconcile_unreferenced_export_producers(old, new)


def test_a_changed_constant_is_refused(after: ModeloRevision) -> None:
    old, new = _sharing_the_old_form(_header_feed(after), _with_marker_fields(after, presence_marker="X"))
    with pytest.raises(RegistryValidationError, match="marker-changing feed"):
        reconcile_unreferenced_export_producers(old, new)


def test_a_blank_slot_follows_the_continuation_marker_and_its_requirement(after: ModeloRevision) -> None:
    """A slot its design prints blank declared no constant, so the marker's own requirement replaces the header's."""
    blank = _with_marker_fields(after, presence_marker=None)
    old, new = _sharing_the_old_form(_header_feed(blank), _with_marker_fields(blank, required=False))

    reconciled = reconcile_unreferenced_export_producers(old, new)

    assert reconciled.source_state_digest == form_layout_source_digest(new)


def test_a_blank_slot_may_not_move_to_another_computed_value(after: ModeloRevision) -> None:
    blank = _with_marker_fields(after, presence_marker=None)
    other = _with_marker_fields(blank, computed_key=ExportComputedKey.M303_NO_ACTIVITY_MARKER)
    old, new = _sharing_the_old_form(_header_feed(blank), other)

    with pytest.raises(RegistryValidationError, match="marker-changing feed"):
        reconcile_unreferenced_export_producers(old, new)
