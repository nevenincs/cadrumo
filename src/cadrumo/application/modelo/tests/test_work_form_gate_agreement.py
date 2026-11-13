"""The form offers the file and the recording exactly where the application's own gates admit them.

Each case is a real calculation revision carrying one note, a Modelo 210 form
the real builder makes from it over the published registry, and the gate the
export and the local filing run on that same revision. Wherever the gate
refuses, the form holds the file back and never offers it next; wherever it
admits, a checked form offers the file. A declaration whose registry rules stop
short of calculation grade is halted through the read itself, and through its
public envelope.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import get_args
from uuid import UUID

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.calculation_revision_sources import DISAGREEMENT_REASONS, CalculationSourceIssue
from ....domain.modelos.calculation_screen_stamp import CalculationScreenStamp
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.source_disagreement import (
    DisagreementDecimalValue,
    SourceDisagreementEntry,
    SourceDisagreementFact,
    SourceDisagreementRole,
)
from ....domain.modelos.verification_report import VerificationCompletenessStatus
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..calculation_note_gate import (
    NO_SOURCE_DISAGREEMENT_RESOLUTIONS,
    SOURCE_DISAGREEMENT_FINDING_ID_LENGTH,
    ModeloCalculationBlockedError,
    SourceDisagreementResolutions,
    require_work_unit_calculation_unblocked,
)
from ..calculation_notes import CALCULATION_SCREEN_OUTDATED_REASON, PRINTED_BOX_REASONS, note_attention
from ..calculation_screen import calculation_screen_stamp
from ..declaration_summary import declaration_summary
from ..declarations_list import DeclarationListGroup, DeclarationListNextStep, DeclarationListRow, next_step
from ..declarations_workspace_contracts import DeclarationsWorkspaceDeclarationRefV1
from ..edit_admission import RESPONSIBLE_OWNER
from ..edit_models import ModeloEditDomainRefusalV1, ModeloEditRefusalCode, ModeloEditRefusedV1
from ..work_form_declaration_facts import ModeloFormCalculationNote
from ..work_form_field_vocabulary import ModeloFormCasillaAddressV1
from ..work_form_findings import ModeloFormAttention
from ..work_form_header import ModeloFormExportHoldReason, export_hold
from ..work_form_issue_lines import form_issue_lines
from ..work_form_models import ModeloWorkForm
from ..work_form_next_step import ModeloFormNextAction, check_count, form_next_step, missing_count, result_fields
from ..work_form_service import modelo_work_form_load
from ..workbench_projection import project_modelo_workbench_form
from ..workbench_read import ModeloWorkbenchFormReadV1
from .work_form_fixture import built_form, form_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "13000000-0000-4000-8000-000000000455"
_CLOCK = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
_HELD: dict[str, Decimal | str] = {"rendimientos_integros": Decimal("1200.00"), "tipo_renta": "01"}
_FILE_ACTIONS = frozenset(
    {ModeloFormNextAction.EXPORT, ModeloFormNextAction.EXPORT_AGAIN, ModeloFormNextAction.RECORD_AFTER_FILE}
)


def work_unit(operation: PinnedAuthorityOperation) -> WorkUnit:
    period = Period.from_year_and_code(2025, "0A")
    revision_id = str(form_snapshot(operation, "210", 2025, "0A").revision.id)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET, modelo="210", filing_year=2025, period=period, revision_id=revision_id
        ),
        bucket_id=_BUCKET,
        modelo=ModeloCode("210"),
        filing_year=2025,
        period=period,
        revision_id=revision_id,
        name="210-2025-0A",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def work_form_gate_agreement_revision(
    operation: PinnedAuthorityOperation,
    unit: WorkUnit,
    *issues: CalculationSourceIssue,
    stale: tuple[CalculationScreenStamp | None] | None = None,
) -> CalculationRevision:
    """A revision stamped with the screen a calculation under ``operation`` runs, so only its notes decide.

    ``stale`` holds the stamp of a revision screened otherwise, or of one never stamped.
    """
    stamp = (
        calculation_screen_stamp(form_snapshot(operation, "210", 2025, "0A"), operation=operation)
        if stale is None
        else stale[0]
    )
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            source_issues=issues,
            filing_instance_evidence=None,
            source_provenance=(),
            screen_stamp=stamp,
        ),
        work_unit_id=unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="210", revision_id=unit.revision_id, modelo_year=2025, period="0A"
        ),
        state=CalculationRevisionState.BORRADOR,
        casilla_values={},
        observations=(),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=None,
        source_provenance=(),
        source_issues=issues,
        screen_stamp=stamp,
    )


_PRINTED_BOX = "rendimientos_integros"
"""A box the Modelo 210 form prints, for the reasons that withhold filing only on a printed box."""


@dataclass(frozen=True, slots=True)
class Note:
    """One note the calculation persists: its reason, the box it names and the binding source that raised it."""

    reason: str
    casilla_id: str | None = None
    binding_source: BindingSourceKind | None = None

    def issue(self) -> CalculationSourceIssue:
        disagreement = {"disagreement": _disagreement()} if self.reason in DISAGREEMENT_REASONS else {}
        return CalculationSourceIssue.model_validate(
            {
                "reason": self.reason,
                "binding_source": self.binding_source,
                "message": f"the calculation noticed {self.reason}",
                "casilla_id": self.casilla_id,
                **disagreement,
            }
        )


def _disagreement() -> SourceDisagreementFact:
    """An operator value over a different carried one, on a figure the filed return carries."""
    return SourceDisagreementFact.of(
        modelo="210",
        filing_year=2025,
        period="0A",
        work_unit_id="e" * 64,
        registry_revision_id="test",
        inputs_digest="d" * 64,
        key="test-carried-binding",
        value_channel="decimal",
        reached_casillas=(),
        sources=(
            SourceDisagreementEntry(
                role=SourceDisagreementRole.BACKEND,
                source_family="previous_filing",
                value=DisagreementDecimalValue.of(Decimal("10.00")),
            ),
            SourceDisagreementEntry(
                role=SourceDisagreementRole.CALLER,
                source_family="operator_input",
                value=DisagreementDecimalValue.of(Decimal("12.00")),
            ),
        ),
        selected_role=SourceDisagreementRole.CALLER,
    )


def every_note() -> list[Note]:
    """Every reason a calculation persists, which is all the gates read, each on a printed box where that matters."""
    reasons = get_args(CalculationSourceIssue.model_fields["reason"].annotation)
    return [Note(reason, _PRINTED_BOX if reason in PRINTED_BOX_REASONS else None) for reason in sorted(reasons)]


def checked_form(
    operation: PinnedAuthorityOperation,
    revision: CalculationRevision,
    resolutions: SourceDisagreementResolutions = NO_SOURCE_DISAGREEMENT_RESOLUTIONS,
) -> ModeloWorkForm:
    """A checked form whose result boxes the calculation produced, so only the note can block it."""
    plain = built_form(operation, "210", 2025, "0A", held=_HELD, entered=frozenset(_HELD))
    results = {str(casilla_id): Decimal("0.00") for casilla_id in result_fields(plain)}
    form = built_form(
        operation,
        "210",
        2025,
        "0A",
        held={**_HELD, **results},
        entered=frozenset(_HELD),
        revision=revision,
        resolutions=resolutions,
    )
    return form.model_copy(update={"verification": VerificationCompletenessStatus.COMPLETE})


def _gate_admits(
    unit: WorkUnit,
    revision: CalculationRevision,
    operation: PinnedAuthorityOperation,
    resolutions: SourceDisagreementResolutions = NO_SOURCE_DISAGREEMENT_RESOLUTIONS,
) -> bool:
    try:
        for action in ("export", "file"):
            require_work_unit_calculation_unblocked(
                work_unit=unit, revision=revision, action=action, operation=operation, resolutions=resolutions
            )
    except ModeloCalculationBlockedError:
        return False
    return True


def _agrees(operation: PinnedAuthorityOperation, note: Note | None) -> None:
    unit = work_unit(operation)
    revision = (
        work_form_gate_agreement_revision(operation, unit)
        if note is None
        else work_form_gate_agreement_revision(operation, unit, note.issue())
    )
    form = checked_form(operation, revision)

    admitted = _gate_admits(unit, revision, operation)
    hold = export_hold(form, OutputLanguage.EN, verified=True, recorded=False)
    step = form_next_step(form, verified=True, filed=False)
    offered = step.action in _FILE_ACTIONS
    blocking_lines = [
        line for line in form_issue_lines(form, OutputLanguage.EN) if line.level is ModeloFormAttention.BLOCKS
    ]

    if not admitted:
        # What the gate refuses the form never offers: it holds the file, leads to resolving it and lists it.
        assert hold is not None and hold.reason is ModeloFormExportHoldReason.BLOCKS, (note, hold)
        assert step.action is ModeloFormNextAction.RESOLVE, (note, step)
        assert blocking_lines, note
        return
    attention = None if note is None else note_attention(note.reason, box=None if note.casilla_id is None else "x")
    if attention in {None, ModeloFormAttention.MISSING, ModeloFormAttention.CHECK, ModeloFormAttention.INFO}:
        # A verified declaration can still name information left out without withholding the file.
        assert hold is None and offered, (note, hold, step)
    else:
        # A note the check or the export decides on its own keeps the file back here too.
        assert not offered, (note, step)


def test_a_form_with_no_note_offers_the_file_the_gates_admit(operation: PinnedAuthorityOperation) -> None:
    _agrees(operation, None)


@pytest.mark.parametrize("note", every_note(), ids=lambda note: note.reason)
def test_every_note_kind_holds_the_file_exactly_where_the_export_and_filing_gates_refuse_it(
    operation: PinnedAuthorityOperation, note: Note
) -> None:
    _agrees(operation, note)


@pytest.mark.parametrize(
    "reason",
    ["activity_asset_foral_territory", "activity_asset_residence_unresolved", "ledger_amortization_row_unregistered"],
)
def test_omitted_amortization_is_shown_without_holding_a_checked_return(
    operation: PinnedAuthorityOperation, reason: str
) -> None:
    unit = work_unit(operation)
    revision = work_form_gate_agreement_revision(operation, unit, Note(reason).issue())
    form = checked_form(operation, revision)

    assert _gate_admits(unit, revision, operation)
    (note,) = form.calculation_notes
    assert note.reason == reason and note.attention is ModeloFormAttention.CHECK and not note.withholds_filing
    assert any(line.level is ModeloFormAttention.CHECK for line in form_issue_lines(form, OutputLanguage.EN))
    assert export_hold(form, OutputLanguage.EN, verified=True, recorded=False) is None
    assert form_next_step(form, verified=True, filed=False).action is ModeloFormNextAction.EXPORT


@pytest.mark.parametrize(
    "reason",
    [
        "activity_asset_foral_territory",
        "activity_asset_residence_unresolved",
        "ledger_amortization_row_unregistered",
        "activity_asset_claim_gap",
        "activity_asset_accrual_unavailable",
        "activity_asset_activity_undeclared",
        "activity_asset_residence_period_unknown",
        "activity_asset_disposal_finding",
    ],
)
def test_an_amortization_note_leaves_the_check_as_the_next_step_of_an_unchecked_return(
    operation: PinnedAuthorityOperation, reason: str
) -> None:
    """Nothing can clear such a note, so counting it as missing would offer a fill with nothing to fill."""
    unit = work_unit(operation)
    form = checked_form(operation, work_form_gate_agreement_revision(operation, unit)).model_copy(
        update={
            "verification": None,
            "calculation_notes": (
                ModeloFormCalculationNote(reason=reason, attention=note_attention(reason, box=None)),
            ),
        }
    )

    step = form_next_step(form, verified=False, filed=False)

    assert (step.action, step.count) == (ModeloFormNextAction.VERIFY, 0)
    assert missing_count(form) == 0
    assert check_count(form) == 1


def test_an_unresolved_working_figure_is_worth_checking_yet_held_as_the_gates_hold_it(
    operation: PinnedAuthorityOperation,
) -> None:
    form = built_form(operation, "210", 2025, "0A", entered=frozenset())
    unprinted = [
        str(field.address.casilla_id)
        for field in form.fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1) and (field.box is None or field.box == "")
    ]
    assert unprinted, "the Modelo 210 form keeps some figure it does not print"
    for note in (Note("unresolved_binding", unprinted[0]), Note("unresolved_binding")):
        unit = work_unit(operation)
        revision = work_form_gate_agreement_revision(operation, unit, note.issue())
        checked = checked_form(operation, revision)
        (shown,) = [item for item in checked.calculation_notes if item.reason == note.reason]

        assert not _gate_admits(unit, revision, operation), note
        assert shown.attention is ModeloFormAttention.CHECK and shown.withholds_filing, shown
        _agrees(operation, note)


def test_an_unrouted_one_stop_shop_row_is_the_modelo_369_checks_and_the_gates_admit_it(
    operation: PinnedAuthorityOperation,
) -> None:
    note = Note("unrouted_observation", binding_source=BindingSourceKind.LEDGER_OSS_AGGREGATION)
    unit = work_unit(operation)
    revision = work_form_gate_agreement_revision(operation, unit, note.issue())

    assert _gate_admits(unit, revision, operation)
    (shown,) = checked_form(operation, revision).calculation_notes
    assert not shown.withholds_filing
    _agrees(operation, note)


def _stale_stamps(operation: PinnedAuthorityOperation) -> list[CalculationScreenStamp | None]:
    current = calculation_screen_stamp(form_snapshot(operation, "210", 2025, "0A"), operation=operation)
    return [None, CalculationScreenStamp(contract_version=current.contract_version, digest="0" * 64)]


@pytest.mark.parametrize("stale", [0, 1], ids=["unstamped", "other_digest"])
@pytest.mark.parametrize("checked", [False, True], ids=["unchecked", "checked"])
def test_a_stale_screen_offers_recalculation_where_the_gates_refuse_it(
    operation: PinnedAuthorityOperation, stale: int, checked: bool
) -> None:
    """An unstamped or differently screened revision is refused by the gates, and the form offers a recalculation."""
    unit = work_unit(operation)
    revision = work_form_gate_agreement_revision(operation, unit, stale=(_stale_stamps(operation)[stale],))
    form = checked_form(operation, revision)
    if not checked:
        form = form.model_copy(update={"verification": None})

    assert not _gate_admits(unit, revision, operation)
    (note,) = [item for item in form.calculation_notes if item.reason == CALCULATION_SCREEN_OUTDATED_REASON]
    assert note.withholds_filing and note.attention is ModeloFormAttention.BLOCKS
    assert form.calculation_out_of_date
    step = form_next_step(form, verified=checked, filed=False)
    assert step.action is ModeloFormNextAction.RECALCULATE, step
    hold = export_hold(form, OutputLanguage.EN, verified=checked, recorded=False)
    assert hold is not None and hold.reason is ModeloFormExportHoldReason.BLOCKS, hold
    assert [line for line in form_issue_lines(form, OutputLanguage.EN) if line.level is ModeloFormAttention.BLOCKS]


def test_a_current_screen_carries_no_stale_note(operation: PinnedAuthorityOperation) -> None:
    """Teeth for the stale case: the same revision stamped as a calculation stamps it is not held for staleness."""
    unit = work_unit(operation)
    form = checked_form(operation, work_form_gate_agreement_revision(operation, unit))

    assert not [item for item in form.calculation_notes if item.reason == CALCULATION_SCREEN_OUTDATED_REASON]
    assert not form.calculation_out_of_date
    assert form_next_step(form, verified=True, filed=False).action is ModeloFormNextAction.EXPORT


def test_a_stale_screen_reaches_the_public_workbench_read(operation: PinnedAuthorityOperation) -> None:
    """The workbench read and its public projection, which the TUI and MCP consume, offer the same recalculation."""
    unit = work_unit(operation)
    form = checked_form(operation, work_form_gate_agreement_revision(operation, unit, stale=(None,))).model_copy(
        update={"verification": None}
    )
    read = _read(form, _refusal("current_calculation_revision_id"), operation)

    assert read.next_step is not None and read.next_step.action is ModeloFormNextAction.RECALCULATE
    public = project_modelo_workbench_form(UUID(_BUCKET), form.work_unit_id, read)
    assert public.next_step is not None and public.next_step.action is ModeloFormNextAction.RECALCULATE
    assert CALCULATION_SCREEN_OUTDATED_REASON in {note.reason for note in public.form.form.calculation_notes}


def _read(form: ModeloWorkForm, admission: ModeloEditRefusedV1, operation: PinnedAuthorityOperation):
    return ModeloWorkbenchFormReadV1(
        load=modelo_work_form_load(form, verified=False, filed=False),
        admission=admission,
        calculation_revision_id=form.calculation_revision_id,
        verification_report_id=None,
        asks_m303_evidence=False,
        asks_modelo_390=False,
        registry_revision_id=form.registry_revision_id,
        tax_id_format=runtime_tax_id_format(authority=operation),
    )


def _refusal(*facts: str) -> ModeloEditRefusedV1:
    return ModeloEditRefusedV1(
        refusal=ModeloEditDomainRefusalV1(
            code=ModeloEditRefusalCode.ADMISSION_DENIED,
            facts=facts,
            responsible_owner=RESPONSIBLE_OWNER,
            reconsideration_condition="edit a modelo revision whose registry authority reaches calculation grade",
        )
    )


def test_rules_short_of_calculation_grade_halt_the_next_step_through_the_read(
    operation: PinnedAuthorityOperation,
) -> None:
    form = built_form(operation, "210", 2025, "0A", entered=frozenset())
    profile = UUID(_BUCKET)

    halted = _read(form, _refusal("registry_authority_grade"), operation)
    refused_otherwise = _read(form, _refusal("current_calculation_revision_id"), operation)

    assert halted.next_step is None
    assert project_modelo_workbench_form(profile, form.work_unit_id, halted).next_step is None
    assert refused_otherwise.next_step is not None
    public = project_modelo_workbench_form(profile, form.work_unit_id, refused_otherwise).next_step
    assert public is not None and public.action is ModeloFormNextAction.FILL


def _listed_step(
    unit: WorkUnit, revision: CalculationRevision, operation: PinnedAuthorityOperation
) -> DeclarationListNextStep | None:
    declaration = DeclarationsWorkspaceDeclarationRefV1(
        work_unit_id=unit.work_unit_id,
        modelo=unit.modelo,
        filing_year=unit.filing_year,
        period=unit.period,
        state=unit.state,
        has_current_calculation=True,
        has_current_filing=False,
    )
    summary = declaration_summary(
        declaration, revisions={revision.calculation_revision_id: revision}, verification=None, operation=operation
    )
    row = DeclarationListRow(
        unit.work_unit_id,
        "210",
        unit.period,
        summary.state.value,
        DeclarationListGroup.IN_PROGRESS,
        declaration=declaration.model_copy(update={"summary": summary}),
    )
    return next_step(row)


@pytest.mark.parametrize("stale", [None, 0, 1], ids=["current", "unstamped", "other_digest"])
@pytest.mark.parametrize("note", [None, "advisory_binding_value"], ids=["no_note", "advisory"])
def test_the_declarations_list_and_the_form_agree_for_one_checked_revision(
    operation: PinnedAuthorityOperation, stale: int | None, note: str | None
) -> None:
    unit = work_unit(operation)
    issues = () if note is None else (Note(note).issue(),)
    stamp = None if stale is None else (_stale_stamps(operation)[stale],)
    revision = work_form_gate_agreement_revision(operation, unit, *issues, stale=stamp).model_copy(
        update={"state": CalculationRevisionState.VERIFICADO_COMPLETO}
    )
    form = checked_form(operation, revision)

    form_step = form_next_step(form, verified=True, filed=False).action
    listed = _listed_step(unit, revision, operation)

    if stale is not None:
        assert form_step is ModeloFormNextAction.RECALCULATE
        assert listed is DeclarationListNextStep.RECALCULATE
    elif note is not None:
        assert form_step is ModeloFormNextAction.RESOLVE
        assert listed is DeclarationListNextStep.FIX
    else:
        assert form_step in _FILE_ACTIONS
        assert listed is DeclarationListNextStep.CREATE_FILE
    assert (listed is DeclarationListNextStep.CREATE_FILE) is _gate_admits(unit, revision, operation)


_ANOTHER_FINDING_KEY = "f" * 64


@pytest.mark.parametrize("reason", sorted(DISAGREEMENT_REASONS))
@pytest.mark.parametrize(
    ("standing", "lifted"),
    [("open", False), ("resolved", True), ("resolved-another-finding", False), ("resolutions-unreadable", False)],
)
def test_a_source_disagreement_is_held_or_lifted_by_the_form_and_the_gates_alike(
    operation: PinnedAuthorityOperation, reason: str, standing: str, lifted: bool
) -> None:
    """An open, a resolved and a stale disagreement are judged identically by the gate and the form."""
    unit = work_unit(operation)
    issue = Note(reason).issue()
    assert issue.disagreement is not None
    key = issue.disagreement.finding_key
    resolutions = {
        "open": NO_SOURCE_DISAGREEMENT_RESOLUTIONS,
        "resolved": SourceDisagreementResolutions(finding_keys=frozenset({key})),
        "resolved-another-finding": SourceDisagreementResolutions(finding_keys=frozenset({_ANOTHER_FINDING_KEY})),
        "resolutions-unreadable": SourceDisagreementResolutions(finding_keys=frozenset({key}), unreadable=True),
    }[standing]
    revision = work_form_gate_agreement_revision(operation, unit, issue)
    form = checked_form(operation, revision, resolutions)

    admitted = _gate_admits(unit, revision, operation, resolutions)
    hold = export_hold(form, OutputLanguage.EN, verified=True, recorded=False)
    step = form_next_step(form, verified=True, filed=False)
    (note,) = form.calculation_notes

    assert admitted is lifted
    assert note.withholds_filing is not lifted
    assert note.finding_id == key[:SOURCE_DISAGREEMENT_FINDING_ID_LENGTH]
    if lifted:
        assert hold is None and step.action in _FILE_ACTIONS
    else:
        assert hold is not None and hold.reason is ModeloFormExportHoldReason.BLOCKS
        assert step.action is ModeloFormNextAction.RESOLVE


@pytest.mark.parametrize("reason", sorted(DISAGREEMENT_REASONS))
def test_the_refusal_names_the_finding_to_answer_and_says_when_the_resolutions_could_not_be_read(
    operation: PinnedAuthorityOperation, reason: str
) -> None:
    unit = work_unit(operation)
    issue = Note(reason).issue()
    assert issue.disagreement is not None
    finding_id = issue.disagreement.finding_key[:SOURCE_DISAGREEMENT_FINDING_ID_LENGTH]
    revision = work_form_gate_agreement_revision(operation, unit, issue)

    with pytest.raises(ModeloCalculationBlockedError) as open_refusal:
        require_work_unit_calculation_unblocked(work_unit=unit, revision=revision, action="export", operation=operation)
    with pytest.raises(ModeloCalculationBlockedError) as unreadable_refusal:
        require_work_unit_calculation_unblocked(
            work_unit=unit,
            revision=revision,
            action="export",
            operation=operation,
            resolutions=SourceDisagreementResolutions(unreadable=True),
        )

    assert open_refusal.value.context is not None
    assert open_refusal.value.context["finding_ids"] == finding_id
    assert "resolutions_unreadable" not in open_refusal.value.context
    assert unreadable_refusal.value.context is not None
    assert unreadable_refusal.value.context["finding_ids"] == finding_id
    assert unreadable_refusal.value.context["resolutions_unreadable"] == "true"


@pytest.mark.parametrize("reason", sorted(DISAGREEMENT_REASONS))
def test_the_check_lists_a_disagreement_with_the_finding_id_an_acceptance_answers_to(
    operation: PinnedAuthorityOperation, reason: str
) -> None:
    unit = work_unit(operation)
    issue = Note(reason).issue()
    assert issue.disagreement is not None
    finding_id = issue.disagreement.finding_key[:SOURCE_DISAGREEMENT_FINDING_ID_LENGTH]
    form = checked_form(operation, work_form_gate_agreement_revision(operation, unit, issue))

    (line,) = [line for line in form_issue_lines(form, OutputLanguage.EN) if reason in line.technical]

    assert finding_id in line.technical
    # The line names the finding in its own field and says to accept it; the command is the command line's.
    assert line.finding_id == finding_id
    assert "accept" in line.action and "accept-disagreement" not in line.action and finding_id not in line.action
