"""The withholding credits of the Renta lead to the withholding register and never offer to be typed.

Boxes 0596, 0597 and 0603 of the 2025 Modelo 100 are supplied by the withholding
register. The form is built by the real builder over the published registry,
and every line the check view lists about one of them names that register as
the place to correct it, in whichever way the line arises. A box another area
owns names that area, and a line about no box names none.
"""

from __future__ import annotations

import pytest

from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ..calculation_notes import RECORDS_REASONS, UNWORKED_BOX_REASONS, note_attention
from ..edit_models import (
    ModeloEditBindingIntentKind,
    ModeloEditPermittedSurfaceEntryV1,
    ModeloEditScalarIntentKind,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
)
from ..edit_value_grammar import binding_value_grammar, casilla_value_grammar
from ..source_policy import SourceSurface
from ..work_form_declaration_facts import ModeloFormCalculationNote
from ..work_form_field_vocabulary import ModeloFormEditability
from ..work_form_findings import ModeloFormIssue
from ..work_form_issue_lines import form_issue_lines
from ..work_form_models import ModeloWorkForm
from .work_form_fixture import built_form, form_casilla, form_snapshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_CREDITS = {
    "0596": "renta-retencion-soportada-trabajo",
    "0597": "renta-retencion-soportada-capital-mobiliario",
    "0603": "renta-retencion-soportada-ganancia-patrimonial",
}
_LEDGER_FED_BOX = "0599"
_RESULT_BOX = "0670"


def _form(
    operation: PinnedAuthorityOperation, permitted_surface: tuple[ModeloEditPermittedSurfaceEntryV1, ...] | None = None
) -> ModeloWorkForm:
    return built_form(operation, "100", _YEAR, "0A", language=OutputLanguage.EN, permitted_surface=permitted_surface)


@pytest.mark.parametrize(("box", "binding_id"), sorted(_CREDITS.items()))
def test_a_credit_is_fed_by_the_register_and_carries_it_as_the_area_to_correct_it_in(
    operation: PinnedAuthorityOperation, box: str, binding_id: str
) -> None:
    revision = form_snapshot(operation, "100", _YEAR, "0A").revision
    declared = next(item for item in revision.bindings if item.id == binding_id)
    assert declared.provider.kind == "retencion_soportada"

    field = form_casilla(_form(operation), box)

    assert [item.binding_id for item in field.bindings] == [binding_id]
    assert field.bindings[0].policy.surface is SourceSurface.WITHHOLDING


@pytest.mark.parametrize("box", sorted(_CREDITS))
def test_a_credit_is_never_offered_for_typing_even_when_an_admission_wrongly_allows_it(
    operation: PinnedAuthorityOperation, box: str
) -> None:
    revision = form_snapshot(operation, "100", _YEAR, "0A").revision
    casilla = next(item for item in revision.casillas if item.id == box)
    binding = next(item for item in revision.bindings if item.id == _CREDITS[box])
    admitted = (
        ModeloEditWritableScalarSurfaceEntryV1(
            casilla_id=box,
            data_type=casilla.data_type,
            allowed_intents=(ModeloEditScalarIntentKind.SET_TYPED_VALUE,),
            grammar=casilla_value_grammar(casilla),
        ),
        ModeloEditWritableBindingOverrideSurfaceEntryV1(
            binding_id=binding.id,
            allowed_intents=(ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,),
            grammar=binding_value_grammar(binding, revision=revision),
        ),
    )

    for surface in (None, admitted):
        field = form_casilla(_form(operation, surface), box)
        assert field.editability is ModeloFormEditability.LOCKED_SOURCE
        assert not field.takes_typed_value
        assert not field.clearable


def _finding_on(box: str | None) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=box,
        message_locale_key="application.modelo.findings.oss_evidence_missing",
        legal_refs=("ley-37-1992:art-99",),
    )


@pytest.mark.parametrize("box", sorted(_CREDITS))
def test_a_finding_about_a_credit_leads_to_the_register(operation: PinnedAuthorityOperation, box: str) -> None:
    form = _form(operation).model_copy(
        update={
            "verification": VerificationCompletenessStatus.BLOCKED,
            "issues": (ModeloFormIssue(finding=_finding_on(box)),),
        }
    )

    (line,) = form_issue_lines(form, OutputLanguage.EN)

    assert line.surface is SourceSurface.WITHHOLDING
    assert line.address == form_casilla(form, box).address


@pytest.mark.parametrize("reason", sorted(UNWORKED_BOX_REASONS))
@pytest.mark.parametrize("box", sorted(_CREDITS))
def test_a_calculation_note_about_a_credit_leads_to_the_register(
    operation: PinnedAuthorityOperation, box: str, reason: str
) -> None:
    note = ModeloFormCalculationNote(reason=reason, attention=note_attention(reason, box=box), casilla_id=box, box=box)
    form = _form(operation).model_copy(update={"calculation_notes": (note,)})

    (line,) = form_issue_lines(form, OutputLanguage.EN)

    assert line.from_calculation
    assert line.surface is SourceSurface.WITHHOLDING


def test_a_note_about_records_keeps_leading_to_the_ledger_whichever_box_it_names(
    operation: PinnedAuthorityOperation,
) -> None:
    reason = sorted(RECORDS_REASONS)[0]
    note = ModeloFormCalculationNote(
        reason=reason, attention=note_attention(reason, box="0596"), casilla_id="0596", box="0596"
    )
    form = _form(operation).model_copy(update={"calculation_notes": (note,)})

    (line,) = form_issue_lines(form, OutputLanguage.EN)

    assert line.surface is SourceSurface.LEDGER


def test_a_note_names_the_area_that_owns_its_box_and_none_when_no_area_does(
    operation: PinnedAuthorityOperation,
) -> None:
    reason = sorted(UNWORKED_BOX_REASONS)[0]

    def surface_of(box: str | None) -> SourceSurface | None:
        note = ModeloFormCalculationNote(
            reason=reason, attention=note_attention(reason, box=box), casilla_id=box, box=box
        )
        (line,) = form_issue_lines(
            _form(operation).model_copy(update={"calculation_notes": (note,)}), OutputLanguage.EN
        )
        return line.surface

    assert surface_of(_LEDGER_FED_BOX) is SourceSurface.LEDGER
    assert surface_of(_RESULT_BOX) is None
    assert surface_of(None) is None
