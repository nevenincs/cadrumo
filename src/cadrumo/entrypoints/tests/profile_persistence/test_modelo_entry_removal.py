"""A filer takes their own value out of a box, and the declaration's history names the edit as an edit.

A box the filer types holds what the declaration gives until the filer enters
a value or clears it. Either one can be taken out again, and the box then holds
exactly what it held before the filer touched it: an optional box goes back to
its default rather than keeping a zero the filer typed. Every applied edit is
recorded as a calculation, and the history says it was the filer's changes,
not a plain recalculation.

Real behaviour throughout: an isolated encrypted profile, the bundled
authority, the production admission, edit executor, form and history reader.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.declarations_workspace_contracts import DeclarationsLifecycleKind
from ....application.modelo.edit_models import (
    ModeloEditHeldKind,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloScalarEditIntentV1,
)
from ....application.modelo.history import assemble_work_unit_history
from ....application.modelo.history_ports import ModeloHistoryPorts
from ....application.modelo.work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloWorkForm,
)
from ....application.modelo.work_form_rebase import accepts
from ....application.modelo.work_form_service import load_modelo_work_form
from ....application.modelo.work_history_read import worded_history
from ....core.casilla_id import CasillaId
from ....core.external_constants import OutputLanguage
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SEEDED_AT, SeededOperatorWork, seeded_operator_work

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _form(work: SeededOperatorWork) -> ModeloWorkForm:
    unit = work.work_unit
    return load_modelo_work_form(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=work.operation,
        work_unit_repository=work.ports.work_unit_repository,
        calculation_repository=work.ports.calculation_repository,
        verification_repository=work.ports.verification_repository,
        admission=work.admit(),
        language=OutputLanguage.ES,
    ).form


def _box(work: SeededOperatorWork, casilla_id: CasillaId) -> ModeloFormField:
    return next(
        field
        for field in _form(work).fields()
        if field.edit_address == ModeloFormCasillaAddressV1(casilla_id=casilla_id)
    )


def _scalar(
    casilla_id: CasillaId, kind: ModeloEditScalarIntentKind, value: Decimal | None = None
) -> ModeloScalarEditIntentV1:
    return ModeloScalarEditIntentV1(address=ModeloEditScalarAddressV1(casilla_id=casilla_id), kind=kind, value=value)


def _calculated_303(work: SeededOperatorWork) -> None:
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work.work_unit_id,
        ports=work.ports,
        filing_instance_evidence=work.m303_filing_evidence(),
        record_operator_layer=True,
        clock=SEEDED_AT,
    )


def _optional_untouched_box(work: SeededOperatorWork) -> ModeloFormField:
    """A box the filer types that the declaration does not require and nobody has entered."""
    return next(
        field
        for field in _form(work).fields()
        if isinstance(field.edit_address, ModeloFormCasillaAddressV1)
        and field.editability is ModeloFormEditability.EDITABLE_VALUE
        and field.data_type == "money"
        and not field.required
        and field.origin not in {ModeloFormOrigin.ENTERED, ModeloFormOrigin.CLEARED}
    )


def _standing(field: ModeloFormField) -> tuple[object, ...]:
    return (field.origin, field.origin_words, field.value, field.removable)


def test_a_value_the_filer_entered_or_cleared_can_be_taken_out_and_the_box_holds_what_it_held_before(
    tmp_path: Path,
) -> None:
    with profile_adapter_composition(), seeded_operator_work(tmp_path, modelo="303") as work:
        _calculated_303(work)
        untouched = _optional_untouched_box(work)
        assert isinstance(untouched.edit_address, ModeloFormCasillaAddressV1)
        casilla_id = untouched.edit_address.casilla_id
        assert untouched.removable is False

        assert (
            work.apply(scalar=(_scalar(casilla_id, ModeloEditScalarIntentKind.SET_TYPED_VALUE, Decimal("10")),)).refusal
            is None
        )
        entered = _box(work, casilla_id)
        assert entered.origin is ModeloFormOrigin.ENTERED
        assert entered.removable is True
        assert accepts(entered, ModeloEditHeldKind.REMOVE)
        # The value typed is the filer's own, with no source to give it back to.
        assert entered.restorable is False

        assert (
            work.apply(scalar=(_scalar(casilla_id, ModeloEditScalarIntentKind.RESTORE_SOURCE_VALUE),)).refusal is None
        )
        removed = _box(work, casilla_id)
        assert _standing(removed) == _standing(untouched)
        assert not accepts(removed, ModeloEditHeldKind.REMOVE)

        # A clear is the filer's statement too, and it is taken out the same way.
        assert (
            work.apply(scalar=(_scalar(casilla_id, ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE),)).refusal is None
        )
        cleared = _box(work, casilla_id)
        assert cleared.origin is ModeloFormOrigin.CLEARED
        assert cleared.removable is True
        assert (
            work.apply(scalar=(_scalar(casilla_id, ModeloEditScalarIntentKind.RESTORE_SOURCE_VALUE),)).refusal is None
        )
        assert _standing(_box(work, casilla_id)) == _standing(untouched)


def test_the_history_names_an_applied_edit_as_the_filers_changes_and_a_calculation_as_a_calculation(
    tmp_path: Path,
) -> None:
    with profile_adapter_composition(), seeded_operator_work(tmp_path, modelo="303") as work:
        _calculated_303(work)
        untouched = _optional_untouched_box(work)
        assert isinstance(untouched.edit_address, ModeloFormCasillaAddressV1)
        casilla_id = untouched.edit_address.casilla_id
        assert (
            work.apply(scalar=(_scalar(casilla_id, ModeloEditScalarIntentKind.SET_TYPED_VALUE, Decimal("10")),)).refusal
            is None
        )
        history = assemble_work_unit_history(
            work.work_unit_id,
            ports=ModeloHistoryPorts(
                work_unit_repository=work.ports.work_unit_repository,
                calculation_repository=work.ports.calculation_repository,
                filing_repository=ModeloRecordCatalogueRepository(),
                verification_repository=work.ports.verification_repository,
                bucket_event_repository=work.ports.bucket_event_repository,
            ),
            operation=work.operation,
        )

    spanish = worded_history(history, OutputLanguage.ES)
    english = worded_history(history, OutputLanguage.EN)
    kinds = [entry.kind for entry in spanish]
    # Newest first: the edit, then the calculation the declaration started from.
    assert kinds.index(DeclarationsLifecycleKind.EDITED) < kinds.index(DeclarationsLifecycleKind.CALCULATED)
    edited = {entry.words for entry in spanish if entry.kind is DeclarationsLifecycleKind.EDITED}
    calculated = {entry.words for entry in spanish if entry.kind is DeclarationsLifecycleKind.CALCULATED}
    assert len(edited) == 1
    assert edited.isdisjoint(calculated)
    assert edited.isdisjoint(entry.words for entry in english if entry.kind is DeclarationsLifecycleKind.EDITED)
