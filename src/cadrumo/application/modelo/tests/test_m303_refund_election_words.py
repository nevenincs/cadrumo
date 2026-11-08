"""What a negative Modelo 303 says it settles to, and whether the export offers the refund.

Built by the real form builder from the published registry and its published
layout, read through the real header and the real export offer. No expectation
is copied from a run: the periods that open the annual refund are the ones the
registry's refund-eligibility policy declares, and the words are looked up from
the catalogue by key, so a translation change cannot make a test pass that the
served sentence would fail.

The rule under test is LIVA art. 115: the balance a filer cannot deduct is
asked back "en la autoliquidación correspondiente al último período de
liquidación de dicho año" (Uno), and only a filer on the Registro de devolución
mensual may ask at the end of every period (Dos, with art. 116 and RIVA art.
30). Outside those cases the credit is carried forward, so neither the served
words nor the export may offer a refund.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.refund_eligibility import resolve_refund_eligibility_policy_for_period
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.filing.schema import ModeloValueKind
from ....domain.iva.refund_eligibility import RedemeEnrolmentState, RefundEligibilityOutcome
from ....domain.modelos.codes import ModeloCode
from ..work_form import build_modelo_work_form
from ..work_form_declaration_facts import ModeloFormResultDirection
from ..work_form_export_offer import (
    ModeloFormElection,
    ModeloFormElectionQuestion,
    ModeloFormElectionReason,
    ModeloFormElectionState,
    form_export_offer,
)
from ..work_form_header import ModeloFormResultState, form_header
from ..work_form_models import ModeloWorkForm
from ..work_form_service import modelo_form_snapshot
from ..work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "303"
#: The settlement box of the periodic IVA declaration, "Resultado final".
_RESULT_BOX = "71"
_NEGATIVE = Decimal("-325.50")
#: Any revision id makes the form state a calculated result; its value is never read here.
_CALCULATION_REVISION_ID = "f" * 64

_CARRY_FORWARD_HELP_KEY = "workspace.modelo.header.result.carry_forward_only_help"
_REDEME_UNSTATED_HELP_KEY = "workspace.modelo.header.result.redeme_unstated_help"
_CHOICE_PENDING_KEY = "workspace.modelo.header.result.choice_pending"
_TO_CARRY_FORWARD_KEY = "workspace.modelo.header.result.to_carry_forward"


def _supported_years(operation: PinnedAuthorityOperation) -> tuple[int, ...]:
    """Every filing year the registry's one support envelope declares."""
    return tuple(sorted(operation.supported_filing_years().years))


def _final_period_tokens(year: int, code: str) -> frozenset[str]:
    """The period tokens the registry declares final, read for this coordinate."""
    return resolve_refund_eligibility_policy_for_period(Period.from_year_and_code(year, code)).final_period_tokens


def _snapshot(operation: PinnedAuthorityOperation, year: int, code: str) -> RegistrySnapshot:
    period = Period.from_year_and_code(year, code)
    revision_id = str(operation.revision_for_context(_MODELO, filing_year=year, period=code).id)
    return modelo_form_snapshot(operation, ModeloCode(_MODELO), year, period, revision_id)


def _form(
    operation: PinnedAuthorityOperation,
    year: int,
    code: str,
    *,
    redeme: RedemeEnrolmentState,
    language: OutputLanguage = OutputLanguage.ES,
) -> ModeloWorkForm:
    snapshot = _snapshot(operation, year, code)
    rows = build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation)
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000453",
        modelo=_MODELO,
        filing_year=year,
        period=Period.from_year_and_code(year, code),
        registry_revision_id=snapshot.revision.id,
        work_unit_id="d" * 64,
        calculation_revision_id=_CALCULATION_REVISION_ID,
        lifecycle_state=None,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=tuple(
            row.model_copy(update={"value": _NEGATIVE, "realised_kind": ModeloValueKind.LITERAL})
            if str(row.casilla_id) == _RESULT_BOX
            else row
            for row in rows
        ),
        findings=(),
        blockers=(),
    )
    return build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=operation.form_layout(_MODELO, snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=frozenset(),
        overridden_binding_ids=frozenset(),
        language=language,
        redeme=redeme,
    )


def _refund_question(
    operation: PinnedAuthorityOperation, form: ModeloWorkForm, year: int, code: str
) -> ModeloFormElectionQuestion | None:
    offer = form_export_offer(
        _MODELO,
        _snapshot(operation, year, code),
        OutputLanguage.ES,
        form=form,
        verified=False,
        filed=False,
    )
    return next((question for question in offer.elections if question.election is ModeloFormElection.REFUND), None)


def _non_final_quarter(year: int) -> str:
    """A quarter the registry does not declare final, so only compensación is lawful there."""
    final = _final_period_tokens(year, "1T")
    return next(code for code in ("3T", "2T", "1T") if code not in final)


def _final_quarter(year: int) -> str:
    final = _final_period_tokens(year, "4T")
    return next(code for code in ("4T", "3T", "2T", "1T") if code in final)


# -- a filer outside REDEME, outside the year's last period ------------------


def test_a_negative_result_outside_the_last_period_is_carried_forward_only(
    operation: PinnedAuthorityOperation,
) -> None:
    """LIVA art. 115.Uno: the refund is not this period's to ask, so the words say carried forward."""
    for year in _supported_years(operation):
        code = _non_final_quarter(year)
        result = _form(operation, year, code, redeme=RedemeEnrolmentState.NOT_ENROLLED).result

        assert result is not None, (year, code)
        assert result.box == _RESULT_BOX, (year, code)
        assert result.disposition is ResultDisposition.COMPENSACION, (year, code)
        assert result.direction is ModeloFormResultDirection.TO_CARRY_FORWARD, (year, code)
        assert not result.election_may_change, (year, code)
        assert result.refund_eligibility is not None, (year, code)
        assert result.refund_eligibility.outcome is RefundEligibilityOutcome.CARRY_FORWARD_ONLY, (year, code)


@pytest.mark.parametrize("language", [OutputLanguage.ES, OutputLanguage.EN])
def test_the_header_says_the_credit_is_carried_forward_and_why(
    operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    """The served sentence must not promise a choice that the period does not allow."""
    for year in _supported_years(operation):
        code = _non_final_quarter(year)
        form = _form(operation, year, code, redeme=RedemeEnrolmentState.NOT_ENROLLED, language=language)
        header = form_header(form, language, verified=False, filed=False)

        assert header.result is not None, (year, code)
        assert header.result.state is ModeloFormResultState.STATED, (year, code)
        assert header.result.words == lookup_translation(_TO_CARRY_FORWARD_KEY, locale=language.value), (year, code)
        assert lookup_translation(_CARRY_FORWARD_HELP_KEY, locale=language.value) in header.result.help, (year, code)
        choice_pending = lookup_translation(_CHOICE_PENDING_KEY, locale=language.value)
        assert choice_pending not in header.result.text, (year, code)
        assert choice_pending not in header.result.help, (year, code)


def test_the_export_does_not_offer_the_refund_outside_the_last_period(
    operation: PinnedAuthorityOperation,
) -> None:
    """The file cannot be created as a devolución where the law does not admit one."""
    for year in _supported_years(operation):
        code = _non_final_quarter(year)
        form = _form(operation, year, code, redeme=RedemeEnrolmentState.NOT_ENROLLED)
        question = _refund_question(operation, form, year, code)

        assert question is not None, (year, code)
        assert question.state is not ModeloFormElectionState.AVAILABLE, (year, code)
        assert question.reason is ModeloFormElectionReason.CARRY_FORWARD_ONLY, (year, code)
        assert question.choices == (), (year, code)
        assert question.default is None, (year, code)
        assert question.state_words == lookup_translation(
            "workspace.modelo.export.election.carry_forward_only", locale=OutputLanguage.ES.value
        ), (year, code)


# -- the year's last period, and a REDEME filer ------------------------------


def test_the_last_period_of_the_year_still_offers_both(operation: PinnedAuthorityOperation) -> None:
    """LIVA art. 115.Uno admits the annual refund, so the choice stands as before."""
    for year in _supported_years(operation):
        code = _final_quarter(year)
        form = _form(operation, year, code, redeme=RedemeEnrolmentState.NOT_ENROLLED)
        result = form.result

        assert result is not None, (year, code)
        assert result.election_may_change, (year, code)
        assert result.refund_eligibility is not None, (year, code)
        assert result.refund_eligibility.outcome is RefundEligibilityOutcome.REFUND_ALLOWED, (year, code)

        header = form_header(form, OutputLanguage.ES, verified=False, filed=False)
        assert header.result is not None, (year, code)
        assert header.result.state is ModeloFormResultState.CHOICE_PENDING, (year, code)

        question = _refund_question(operation, form, year, code)
        assert question is not None, (year, code)
        assert question.state is ModeloFormElectionState.AVAILABLE, (year, code)
        assert question.choices, (year, code)


def test_a_redeme_filer_keeps_the_choice_in_a_non_final_month(operation: PinnedAuthorityOperation) -> None:
    """LIVA art. 115.Dos: the monthly procedure opens the refund at the end of each period."""
    for year in _supported_years(operation):
        code = next(month for month in ("05", "04", "03") if month not in _final_period_tokens(year, "05"))
        form = _form(operation, year, code, redeme=RedemeEnrolmentState.ENROLLED)
        result = form.result

        assert result is not None, (year, code)
        assert result.election_may_change, (year, code)
        assert result.refund_eligibility is not None, (year, code)
        assert result.refund_eligibility.outcome is RefundEligibilityOutcome.REFUND_ALLOWED, (year, code)

        question = _refund_question(operation, form, year, code)
        assert question is not None, (year, code)
        assert question.state is ModeloFormElectionState.AVAILABLE, (year, code)


# -- the inscription the profile has not stated ------------------------------


def test_an_unstated_redeme_answer_names_the_fact_the_refund_needs(
    operation: PinnedAuthorityOperation,
) -> None:
    """Neither a silent assumption nor a bare refusal: the missing fact is named and only carry is offered."""
    for year in _supported_years(operation):
        code = _non_final_quarter(year)
        form = _form(operation, year, code, redeme=RedemeEnrolmentState.UNSTATED)
        result = form.result

        assert result is not None, (year, code)
        assert not result.election_may_change, (year, code)
        assert result.refund_eligibility is not None, (year, code)
        assert result.refund_eligibility.outcome is RefundEligibilityOutcome.UNDETERMINED_REDEME_UNSTATED, (year, code)

        header = form_header(form, OutputLanguage.ES, verified=False, filed=False)
        assert header.result is not None, (year, code)
        assert lookup_translation(_REDEME_UNSTATED_HELP_KEY, locale=OutputLanguage.ES.value) in header.result.help, (
            year,
            code,
        )

        question = _refund_question(operation, form, year, code)
        assert question is not None, (year, code)
        assert question.state is not ModeloFormElectionState.AVAILABLE, (year, code)
        assert question.reason is ModeloFormElectionReason.REDEME_UNSTATED, (year, code)
        assert question.choices == (), (year, code)


def test_a_form_built_without_a_profile_read_offers_only_what_is_certain(
    operation: PinnedAuthorityOperation,
) -> None:
    """The default must not be a stated no: a caller that read no profile may not open the refund."""
    for year in _supported_years(operation):
        code = _non_final_quarter(year)
        snapshot = _snapshot(operation, year, code)
        rows = build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation)
        review = ModeloWorkReview(
            bucket_id="13000000-0000-4000-8000-000000000453",
            modelo=_MODELO,
            filing_year=year,
            period=Period.from_year_and_code(year, code),
            registry_revision_id=snapshot.revision.id,
            work_unit_id="e" * 64,
            calculation_revision_id=_CALCULATION_REVISION_ID,
            lifecycle_state=None,
            verification_outcome=None,
            progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
            casillas=tuple(
                row.model_copy(update={"value": _NEGATIVE, "realised_kind": ModeloValueKind.LITERAL})
                if str(row.casilla_id) == _RESULT_BOX
                else row
                for row in rows
            ),
            findings=(),
            blockers=(),
        )
        result = build_modelo_work_form(
            review=review,
            snapshot=snapshot,
            layout=operation.form_layout(_MODELO, snapshot.revision.id),
            revision=None,
            permitted_surface=None,
            entered_casilla_ids=frozenset(),
            overridden_binding_ids=frozenset(),
            language=OutputLanguage.ES,
        ).result

        assert result is not None, (year, code)
        assert not result.election_may_change, (year, code)
        assert result.refund_eligibility is not None, (year, code)
        assert result.refund_eligibility.outcome is RefundEligibilityOutcome.UNDETERMINED_REDEME_UNSTATED, (year, code)
