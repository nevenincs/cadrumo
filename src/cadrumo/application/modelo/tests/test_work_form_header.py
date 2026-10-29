"""The header states the same counts, result, deadline, file and hold for every frontend.

Every form is built by the real builder over the published registry; a test
then states the one lifecycle fact it is about. The counts are the next step's
own, the deadline grows urgent at the same thresholds the calendar shows, the
result reads from the declared direction and never the sign, and the file for
the AEAT is held back exactly where the next step does not offer it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.modelos.verification_report import VerificationCompletenessStatus
from ..calculation_notes import CALCULATION_NOTE_ATTENTION, GATE_REFUSED_REASONS
from ..edit_admission import RESPONSIBLE_OWNER
from ..edit_models import ModeloEditDomainRefusalV1, ModeloEditRefusalCode, ModeloEditRefusedV1
from ..work_form_findings import ModeloFormAttention
from ..work_form_header import (
    ModeloFormDeadlineTone,
    ModeloFormExportHoldReason,
    ModeloFormResultState,
    attention_counts,
    deadline_view,
    export_hold,
    file_view,
    form_header,
    result_view,
)
from ..work_form_models import (
    ModeloFormCalculationNote,
    ModeloFormDeadline,
    ModeloFormExport,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormResultDirection,
    ModeloWorkForm,
    map_form_fields,
    revised_field,
)
from ..work_form_next_step import (
    ModeloFormNextAction,
    blocking_count,
    confirm_count,
    form_next_step,
    is_result_field,
    missing_count,
)
from ..work_form_service import ModeloWorkFormLoadV1
from ..workbench_projection import project_modelo_workbench_form, restore_modelo_workbench_form
from ..workbench_read import ModeloWorkbenchFormReadV1
from .work_form_fixture import built_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EN = OutputLanguage.EN
_ES = OutputLanguage.ES
_INCOME = "rendimientos_integros"
_KIND = "tipo_renta"
_HELD: dict[str, Decimal | str] = {_INCOME: Decimal("1200.00"), _KIND: "01"}
_CALCULATION = "c" * 64
_EXPORTED_AT = datetime(2026, 4, 2, 9, tzinfo=UTC)
_TODAY = date(2026, 4, 8)
_FILE_ACTIONS = frozenset(
    {ModeloFormNextAction.EXPORT, ModeloFormNextAction.EXPORT_AGAIN, ModeloFormNextAction.RECORD_AFTER_FILE}
)


def _entered(operation: PinnedAuthorityOperation) -> ModeloWorkForm:
    """The income and its kind entered by the filer, so nothing is missing or assumed."""
    return built_form(operation, "210", 2025, "0A", held=_HELD, entered=frozenset(_HELD))


def _calculated(form: ModeloWorkForm, **update: object) -> ModeloWorkForm:
    return form.model_copy(update={"calculation_revision_id": _CALCULATION, **update})


def _deadline(days: int, *, shifted: bool = False) -> ModeloFormDeadline:
    closes = _TODAY + timedelta(days=days)
    return ModeloFormDeadline(
        closes_on=closes,
        nominal_closes_on=closes - timedelta(days=2) if shifted else closes,
        holiday_coverage=DeadlineHolidayCoverage.NATIONAL_AND_TERRITORY,
        reference_on=_TODAY,
        days_remaining=days if days >= 0 else None,
        days_overdue=-days if days < 0 else None,
    )


def _result_box(form: ModeloWorkForm, change: ModeloFormOrigin) -> ModeloWorkForm:
    def changed(field: ModeloFormField) -> ModeloFormField:
        return revised_field(field, origin=change) if is_result_field(form, field) else field

    return map_form_fields(form, changed)


def test_the_counts_are_the_next_steps_own_said_in_the_forms_language(operation: PinnedAuthorityOperation) -> None:
    empty = built_form(operation, "210", 2025, "0A", entered=frozenset())
    assumed = built_form(operation, "210", 2025, "0A", held=_HELD, entered=frozenset({_KIND}))

    english = {count.level: count for count in attention_counts(empty, _EN, recorded=False)}
    spanish = {count.level: count for count in attention_counts(empty, _ES, recorded=False)}

    assert english[ModeloFormAttention.MISSING].count == missing_count(empty) > 0
    assert english[ModeloFormAttention.MISSING].words != spanish[ModeloFormAttention.MISSING].words
    assert ModeloFormAttention.BLOCKS not in english
    confirmed = {count.level: count.count for count in attention_counts(assumed, _EN, recorded=False)}
    assert confirmed[ModeloFormAttention.CONFIRM] == confirm_count(assumed) == 1
    assert attention_counts(empty, _EN, recorded=True) == ()


@pytest.mark.parametrize(
    ("days", "tone"),
    [
        (21, ModeloFormDeadlineTone.NORMAL),
        (8, ModeloFormDeadlineTone.NORMAL),
        (7, ModeloFormDeadlineTone.SOON),
        (4, ModeloFormDeadlineTone.SOON),
        (3, ModeloFormDeadlineTone.URGENT),
        (0, ModeloFormDeadlineTone.URGENT),
        (-1, ModeloFormDeadlineTone.URGENT),
    ],
)
def test_the_deadline_grows_urgent_as_it_nears_and_once_it_passed(
    operation: PinnedAuthorityOperation, days: int, tone: ModeloFormDeadlineTone
) -> None:
    form = _entered(operation).model_copy(update={"deadline": _deadline(days)})

    view = deadline_view(form, _EN, recorded=False)

    assert view is not None
    assert view.tone is tone
    assert view.help is None
    if days > 0:
        assert str(days) in view.text
    assert deadline_view(form, _EN, recorded=True) is None


def test_no_deadline_reads_muted_with_fewer_words_and_a_moved_one_says_why(
    operation: PinnedAuthorityOperation,
) -> None:
    form = _entered(operation)
    missing = deadline_view(form.model_copy(update={"deadline": None}), _EN, recorded=False)
    moved = deadline_view(form.model_copy(update={"deadline": _deadline(10, shifted=True)}), _EN, recorded=False)

    assert missing is not None and missing.tone is ModeloFormDeadlineTone.MUTED
    assert len(missing.short_text) < len(missing.text)
    assert moved is not None and moved.help is not None
    assert "16/04/2026" in moved.help and "18/04/2026" in moved.help, moved.help


def test_the_result_is_stated_once_calculated_and_otherwise_says_why_it_has_no_figure(
    operation: PinnedAuthorityOperation,
) -> None:
    form = _calculated(_entered(operation))
    selected = result_view(form, _EN, recorded=False)
    assert selected is not None, form.result_addresses

    uncalculated = result_view(form.model_copy(update={"calculation_revision_id": None}), _EN, recorded=False)
    failed = result_view(_result_box(form, ModeloFormOrigin.CALCULATION_FAILED), _EN, recorded=False)

    assert uncalculated is not None and uncalculated.state is ModeloFormResultState.NOT_CALCULATED
    assert (
        uncalculated.text == uncalculated.brief_text == tr("workspace.modelo.header.result.not_calculated", locale="en")
    )
    assert uncalculated.words is None and "[" not in uncalculated.text
    assert failed is not None and failed.state is ModeloFormResultState.FAILED
    assert failed.text == tr("workspace.modelo.header.result.failed", locale="en")
    assert failed.help
    assert failed.casilla_id == selected.casilla_id


def _settled(form: ModeloWorkForm, direction: ModeloFormResultDirection, value: Decimal) -> ModeloWorkForm:
    if form.result is None:
        pytest.fail("Modelo 130 declares its settlement box")
    held = form.model_copy(
        update={
            "calculation_revision_id": _CALCULATION,
            "result": form.result.model_copy(update={"value": value, "direction": direction}),
        }
    )
    return _result_box(held, ModeloFormOrigin.CALCULATED)


def test_a_settled_result_reads_its_declared_direction_and_never_the_sign(operation: PinnedAuthorityOperation) -> None:
    form = built_form(operation, "130", 2026, "1T", entered=frozenset())

    refund = result_view(_settled(form, ModeloFormResultDirection.TO_REFUND, Decimal("-250.00")), _EN, recorded=False)
    unknown = result_view(_settled(form, ModeloFormResultDirection.UNKNOWN, Decimal("-250.00")), _EN, recorded=False)

    assert refund is not None and refund.settles and refund.state is ModeloFormResultState.STATED
    assert refund.text is not None and "250.00" in refund.text and "−" not in refund.text, refund
    assert refund.box is not None and f"[{refund.box}]" in refund.text
    assert refund.short_text is not None and f"[{refund.box}]" not in refund.short_text
    assert any("−250.00" in line for line in refund.help), refund.help
    assert unknown is not None and unknown.amount_text is not None and unknown.amount_text.startswith("−")


def test_the_file_is_said_in_words_and_one_from_an_earlier_calculation_is_out_of_date(
    operation: PinnedAuthorityOperation,
) -> None:
    form = _calculated(_entered(operation))
    current = form.model_copy(
        update={
            "last_export": ModeloFormExport(
                exported_at=_EXPORTED_AT, calculation_revision_id=_CALCULATION, current=True
            )
        }
    )
    earlier = form.model_copy(
        update={
            "last_export": ModeloFormExport(exported_at=_EXPORTED_AT, calculation_revision_id="d" * 64, current=False)
        }
    )

    made = file_view(current, _EN, recorded=False)
    stale = file_view(earlier, _EN, recorded=False)

    assert made is not None and made.current and made.created_on in made.words
    assert stale is not None and not stale.current
    assert stale.words == tr("workspace.modelo.header.file_out_of_date", date=stale.created_on, locale="en")
    assert file_view(current, _EN, recorded=True) is None
    assert file_view(form, _EN, recorded=False) is None


def _note(reason: str) -> ModeloFormCalculationNote:
    return ModeloFormCalculationNote(reason=reason, attention=CALCULATION_NOTE_ATTENTION[reason])


def test_the_file_is_held_back_exactly_where_the_next_step_does_not_offer_it(
    operation: PinnedAuthorityOperation,
) -> None:
    entered = _entered(operation)
    verified = _calculated(entered, verification=VerificationCompletenessStatus.COMPLETE)
    assumed = _calculated(
        built_form(operation, "210", 2025, "0A", held=_HELD, entered=frozenset({_KIND})),
        verification=VerificationCompletenessStatus.COMPLETE,
    )
    blocked = verified.model_copy(update={"calculation_notes": (_note(sorted(GATE_REFUSED_REASONS)[0]),)})
    # What blocks filing is said first, whatever still waits to be confirmed.
    blocked_and_assumed = assumed.model_copy(update={"calculation_notes": blocked.calculation_notes})
    table = [
        (entered, False, ModeloFormExportHoldReason.VERIFY, 0),
        (_calculated(entered), False, ModeloFormExportHoldReason.VERIFY, 0),
        (assumed, True, ModeloFormExportHoldReason.CONFIRM, 1),
        (blocked, True, ModeloFormExportHoldReason.BLOCKS, blocking_count(blocked)),
        (blocked_and_assumed, True, ModeloFormExportHoldReason.BLOCKS, blocking_count(blocked_and_assumed)),
        (verified, True, None, 0),
    ]
    for form, is_verified, reason, count in table:
        hold = export_hold(form, _EN, verified=is_verified, recorded=False)
        offered = form_next_step(form, verified=is_verified, filed=False).action in _FILE_ACTIONS
        assert (None if hold is None else (hold.reason, hold.count)) == (None if reason is None else (reason, count)), (
            reason,
            hold,
        )
        assert offered == (hold is None), (reason, hold)
    filed = built_form(operation, "210", 2025, "0A", entered=frozenset(), lifecycle=CalculationRevisionState.PRESENTADO)
    assert export_hold(filed, _EN, verified=False, recorded=True) is None


def test_a_recorded_declaration_states_its_result_and_nothing_left_to_do(operation: PinnedAuthorityOperation) -> None:
    filed = built_form(operation, "210", 2025, "0A", entered=frozenset(), lifecycle=CalculationRevisionState.PRESENTADO)
    header = form_header(filed.model_copy(update={"deadline": _deadline(3)}), _EN, verified=True, filed=True)

    assert header.attention == ()
    assert header.deadline is None and header.file is None and header.export_hold is None


def test_the_public_read_carries_the_header_in_the_forms_language(operation: PinnedAuthorityOperation) -> None:
    form = built_form(operation, "210", 2025, "0A", entered=frozenset(), language=_ES)
    read = ModeloWorkbenchFormReadV1(
        load=ModeloWorkFormLoadV1(form=form, verified=False, filed=False),
        admission=ModeloEditRefusedV1(
            refusal=ModeloEditDomainRefusalV1(
                code=ModeloEditRefusalCode.ADMISSION_DENIED,
                facts=("current_calculation_revision_id",),
                responsible_owner=RESPONSIBLE_OWNER,
                reconsideration_condition="calculate the declaration before editing it",
            )
        ),
        calculation_revision_id=None,
        verification_report_id=None,
        asks_m303_evidence=False,
        asks_modelo_390=False,
        registry_revision_id=form.registry_revision_id,
        tax_id_format=runtime_tax_id_format(authority=operation),
    )

    projection = project_modelo_workbench_form(UUID("13000000-0000-4000-8000-000000000455"), form.work_unit_id, read)

    assert projection.header == form_header(form, _ES, verified=False, filed=False)
    assert projection.header.attention
    assert restore_modelo_workbench_form(projection).header == projection.header
