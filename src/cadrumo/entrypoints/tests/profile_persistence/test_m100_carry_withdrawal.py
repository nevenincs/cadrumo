"""A filer withdraws the statement that no earlier-ejercicio carry is pending on a Modelo 100.

Before the statement the declaration could not be calculated: the carries are
unknown, never zero. Withdrawing the statement returns it there: the work unit
has no current calculation, every revision stays stored, calculating again is
refused as before, and the form offers the statement again. The four carries
are one statement, so withdrawing one withdraws them all. A calculation that
also holds the filer's other values is not withdrawn, and neither is one
recorded as filed.

Real behaviour throughout: an isolated encrypted profile, the bundled
authority, the production admission and edit executor, every Modelo 100 year
the registry's support envelope admits.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

import pytest

from ....adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....application.ledger.models import LedgerStatusReport
from ....application.modelo.action_errors import (
    ModeloEditCarryWithdrawalFiledError,
    ModeloEditCarryWithdrawalKeepsEntriesError,
)
from ....application.modelo.carry_family_selection import prior_carry_binding_ids
from ....application.modelo.declarations_portfolio import project_declarations_portfolio
from ....application.modelo.declarations_workspace_contracts import (
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneObservationV1,
)
from ....application.modelo.edit_carry_withdrawal import calculation_refusing_carry_bindings
from ....application.modelo.edit_contract import ModeloEditMutationFamily
from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditFindingSeverity,
    ModeloEditPreflightEvaluatedV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSubmissionV1,
    ModeloScalarEditIntentV1,
)
from ....application.modelo.edit_preflight import CALCULATION_WITHDRAWN, preflight_modelo_edit
from ....application.modelo.edit_review_wording import review_findings
from ....application.modelo.export import load_exportable_revision_target
from ....application.modelo.operation_definitions import ModeloWorkFileExecutor, ModeloWorkVerifyExecutor
from ....application.modelo.operation_shared import resolve_active_workflow_profile
from ....application.modelo.selectors import (
    ModeloCalculationRevisionSelectorNotFoundError,
    select_exportable_revision,
)
from ....application.modelo.work_filing_contracts import ModeloWorkFileApproval, ModeloWorkFileRequest
from ....application.modelo.work_form_models import ModeloWorkForm
from ....application.modelo.work_form_service import load_modelo_work_form
from ....application.modelo.work_missing_input import ModeloPriorCarryAbsenceUnstatedError
from ....application.modelo.work_verification_contracts import ModeloWorkVerifyRequest
from ....application.operations.models import OperationRequest
from ....application.operations.owner import OperationExecutorContext
from ....application.operator_actions.models import PreconditionVerdict
from ....application.overview.pipeline_health import ModeloReadinessState, build_pipeline_health_report
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.errors.error_codes import get_registered_error_code, resolve_error_message
from ....core.errors.hierarchy import CadrumoError, RecordedRegisteredError
from ....core.external_constants import OutputLanguage
from ....core.operations import OperationEffect
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ....domain.modelos.filing_record import ModeloRecordCatalogue
from ....domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from ....domain.user_profile.values import UserProfileFact
from ...adapter_composition import profile_adapter_composition
from ...adapter_composition_ports import build_modelo_export_ports
from ...adapter_composition_work_ports import build_filing_action_ports, build_verification_repository_bundle
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work
from ..operation_contract_support import unavailable, unavailable_operator_scope_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PENDING_CARRIES: tuple[BindingId, ...] = (
    "renta-base-liquidable-negativa-general-anterior",
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio",
)
#: The negative savings balances still pending, whose own statements the calculation also needs.
_SAVINGS_CARRIES: tuple[BindingId, ...] = tuple(
    f"renta-saldo-negativo-{kind}-ahorro-{origin}-pendiente-inicio"
    for kind in ("gyp", "rcm")
    for origin in ("em1", "em2", "em3", "em4")
)
_FACTS = (UserProfileFact(path="tax_residence.ccaa", value="madrid"), *RENTA_UNMARRIED_TAXPAYER_FACTS)
_FAMILY = AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING
_LANGUAGES = (OutputLanguage.ES, OutputLanguage.CA, OutputLanguage.EN, OutputLanguage.HU)
#: A box the filer may type on any Modelo 100, the disability increase of work expenses.
_TYPED_BOX = "0021"
_TYPED_AMOUNT = "1234.56"


def _renta_years() -> tuple[int, ...]:
    """The Modelo 100 years the envelope admits at calculation grade."""
    support = published_supported_filing_years()
    assert support is not None
    admitted: list[int] = []
    for year in sorted(support.years):
        try:
            published_authority_operation().snapshot(
                "100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
            )
        except FilingYearOutsideSupportEnvelopeError:
            continue
        admitted.append(year)
    return tuple(admitted)


def _attest(binding_id: BindingId) -> ModeloBindingEditIntentV1:
    return ModeloBindingEditIntentV1(
        address=ModeloEditBindingAddressV1(binding_id=binding_id), kind=ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT
    )


def _withdraw(binding_id: BindingId) -> ModeloBindingEditIntentV1:
    return ModeloBindingEditIntentV1(
        address=ModeloEditBindingAddressV1(binding_id=binding_id), kind=ModeloEditBindingIntentKind.REMOVE_OVERRIDE
    )


def _typed() -> ModeloScalarEditIntentV1:
    return ModeloScalarEditIntentV1(
        address=ModeloEditScalarAddressV1(casilla_id=_TYPED_BOX),
        kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
        value=_TYPED_AMOUNT,
    )


def _form(work: SeededOperatorWork, language: OutputLanguage = OutputLanguage.EN) -> ModeloWorkForm:
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
        language=language,
    ).form


def _stated(work: SeededOperatorWork) -> str:
    """State every pending carry and return the calculation the statement made."""
    applied = work.apply(binding=tuple(_attest(binding_id) for binding_id in (*_PENDING_CARRIES, *_SAVINGS_CARRIES)))
    assert applied.refusal is None
    assert applied.calculation_revision_id is not None
    return applied.calculation_revision_id


def _assert_returned_to_no_calculation(work: SeededOperatorWork, withdrawn_id: str) -> None:
    """The work unit holds no calculation, the withdrawn one is kept, and the declaration is as before the statement."""
    assert work.head() is None
    assert work.ports.calculation_repository.load().get(withdrawn_id) is not None
    with pytest.raises(ModeloPriorCarryAbsenceUnstatedError) as refused:
        work.recalculate()
    verdict = refused.value.terminal_precondition_verdict
    assert isinstance(verdict, PreconditionVerdict)
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.attest_prior_carries"
    form = _form(work)
    assert form.calculation_revision_id is None
    (offered,) = [item for item in form.carry_attestations if item.family is _FAMILY]
    assert set(_PENDING_CARRIES) <= set(offered.binding_ids)


@pytest.mark.parametrize("year", _renta_years())
def test_withdrawing_one_carry_withdraws_the_statement_and_the_calculation(tmp_path: Path, year: int) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        stated = _stated(renta)

        withdrawn = renta.apply(binding=(_withdraw(_PENDING_CARRIES[0]),))

        assert withdrawn.refusal is None
        assert withdrawn.effects[-1] is OperationEffect.UPDATED
        assert withdrawn.calculation_revision_id is None
        _assert_returned_to_no_calculation(renta, stated)

        # Stating the carries again calculates the declaration again.
        assert _stated(renta) == stated


@pytest.mark.parametrize("year", _renta_years())
def test_withdrawing_every_carry_returns_the_declaration_to_no_calculation(tmp_path: Path, year: int) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        stated = _stated(renta)

        withdrawn = renta.apply(binding=tuple(_withdraw(binding_id) for binding_id in _PENDING_CARRIES))

        assert withdrawn.refusal is None
        assert withdrawn.effects[-1] is OperationEffect.UPDATED
        _assert_returned_to_no_calculation(renta, stated)


@pytest.mark.parametrize("year", _renta_years())
def test_a_withdrawal_that_would_discard_a_typed_value_is_refused_and_keeps_it(tmp_path: Path, year: int) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        _stated(renta)
        assert renta.apply(scalar=(_typed(),)).refusal is None
        head = renta.require_head()

        refused = renta.apply(binding=(_withdraw(_PENDING_CARRIES[0]),))

        assert isinstance(refused.refusal, ModeloEditCarryWithdrawalKeepsEntriesError)
        assert refused.effects[-1] is OperationEffect.NONE
        assert get_registered_error_code(refused.refusal).code == "REFUSED_MODELO_EDIT_CARRY_WITHDRAWAL_KEEPS_ENTRIES"
        verdict = refused.refusal.terminal_precondition_verdict
        assert isinstance(verdict, PreconditionVerdict)
        assert verdict.action is not None
        assert verdict.action.action_id == "operator.modelo.work.attest_prior_value"
        english = resolve_error_message(refused.refusal, locale="en")
        assert "other values" in english
        for language in _LANGUAGES:
            words = resolve_error_message(refused.refusal, locale=language.value)
            assert words and not words.startswith("errors."), words
            assert "1234" not in words
        # The typed value and the statement stay where they were.
        assert renta.require_head() == head
        layer = head.operator_layer
        assert layer is not None
        assert str(_TYPED_BOX) in {str(casilla_id) for casilla_id in layer.decimal_casilla_inputs}
        assert set(_PENDING_CARRIES) <= set(layer.attested_binding_ids)


@pytest.mark.parametrize("year", _renta_years())
def test_a_withdrawal_from_a_declaration_recorded_as_filed_is_refused_with_the_amendment(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        _stated(renta)
        # Recorded as filed: the head's lifecycle moves in place, as verification and a local filing move it.
        catalogue = renta.ports.calculation_repository.load()
        head = renta.require_head()
        moved_at = head.updated_at
        filed = head.model_copy(
            update={
                "state": CalculationRevisionState.PRESENTADO,
                "verified_at": moved_at,
                "verified_by": "operator:test",
                "filed_at": moved_at,
                "filed_by": "operator:test",
            }
        )
        renta.ports.calculation_repository.save(upsert_calculation_revision(catalogue, filed))

        refused = renta.apply(binding=(_withdraw(_PENDING_CARRIES[0]),))

        assert isinstance(refused.refusal, ModeloEditCarryWithdrawalFiledError)
        assert refused.effects[-1] is OperationEffect.NONE
        verdict = refused.refusal.terminal_precondition_verdict
        assert isinstance(verdict, PreconditionVerdict)
        assert verdict.action is not None
        assert verdict.action.action_id == "operator.modelo.work.amend"
        for language in _LANGUAGES:
            words = resolve_error_message(refused.refusal, locale=language.value)
            assert words and not words.startswith("errors."), words
        assert renta.require_head() == filed


@pytest.mark.parametrize("year", _renta_years())
def test_the_preview_of_a_carry_withdrawal_says_the_calculation_is_withdrawn(tmp_path: Path, year: int) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        _stated(renta)
        baseline = renta.baseline()
        submission = ModeloEditSubmissionV1(
            baseline=baseline,
            mutation_family=ModeloEditMutationFamily.CALCULATE,
            binding_intents=(_withdraw(_PENDING_CARRIES[-1]),),
        )
        revision = renta.operation.snapshot(
            "100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
        ).revision
        outcome = preflight_modelo_edit(
            submission,
            work_catalogue=renta.ports.work_unit_repository.load(),
            calculation_catalogue=renta.ports.calculation_repository.load(),
            tax_id_format=runtime_tax_id_format(authority=renta.operation),
            prior_carry_bindings=prior_carry_binding_ids(renta.operation, submission),
            carry_bindings=calculation_refusing_carry_bindings(revision),
        )

        assert isinstance(outcome, ModeloEditPreflightEvaluatedV1)
        (withdrawn,) = [finding for finding in outcome.findings if finding.code == CALCULATION_WITHDRAWN]
        # The whole statement is withdrawn, so the finding concerns the submission, not the one carry named.
        assert withdrawn.address is None
        assert withdrawn.severity is ModeloEditFindingSeverity.WARNING
        worded = {language: review_findings(outcome.findings, language) for language in _LANGUAGES}
        for language, findings in worded.items():
            (finding,) = [item for item in findings if item.code == CALCULATION_WITHDRAWN]
            assert not finding.blocking
            assert finding.words and not finding.words.startswith("workspace."), (language, finding.words)
        assert len({next(f.words for f in found if f.code == CALCULATION_WITHDRAWN) for found in worded.values()}) == 4


@pytest.mark.parametrize("year", _renta_years())
def test_an_edit_that_leaves_the_carries_unstated_names_their_refusal_and_statement(tmp_path: Path, year: int) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        refused = renta.apply(scalar=(_typed(),))

        error = refused.refusal
        assert isinstance(error, RecordedRegisteredError)
        assert refused.effects[-1] is OperationEffect.NONE
        assert renta.head() is None
        assert get_registered_error_code(error).code == "REFUSED_MODELO_PRIOR_CARRY_ABSENCE_UNSTATED"
        verdict = error.terminal_precondition_verdict
        assert isinstance(verdict, PreconditionVerdict)
        assert verdict.action is not None
        assert verdict.action.action_id == "operator.modelo.work.attest_prior_carries"
        # No amount, box or binding travels with it.
        assert "1234" not in verdict.model_dump_json()
        assert error.context is None or error.context == {}
        for language in _LANGUAGES:
            words = resolve_error_message(error, locale=language.value)
            assert words and not words.startswith("application."), words
            assert "1234" not in words
            assert not any(binding_id in words for binding_id in _PENDING_CARRIES)


class _Events:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    async def phase(self, phase_code: str) -> None:
        del phase_code

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Cancellation:
    @asynccontextmanager
    async def irreversible_section(self) -> AsyncGenerator[None]:
        yield


class _Context:
    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        self.authority_operation = operation
        self.events = _Events()
        self.cancellation = _Cancellation()
        self.operands = operation_secure_reference_repository()


def _refused_verification(operation: PinnedAuthorityOperation, work_unit_id: str, revision_id: str) -> CadrumoError:
    """Verify a calculation by its exact id through the production executor; it must refuse without effect."""
    executor = ModeloWorkVerifyExecutor(
        certificate_secret_backend_factory=unavailable,
        profile_resolver=resolve_active_workflow_profile,
        operator_scope_ports=unavailable_operator_scope_ports(),
        verification_repository_bundle_factory=build_verification_repository_bundle,
    )
    context = _Context(operation)
    request = OperationRequest(
        definition_id="modelo.work.verify",
        subject_ref=work_unit_id,
        payload=ModeloWorkVerifyRequest(calculation_revision_id=revision_id, actor="operator"),
    )
    with pytest.raises(CadrumoError) as refused:
        asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))
    assert context.events.effects == []
    return refused.value


def _refused_filing(operation: PinnedAuthorityOperation, work_unit_id: str, revision_id: str) -> CadrumoError:
    """File a calculation under an approval naming it through the production executor; it must refuse without effect."""
    executor = ModeloWorkFileExecutor(
        profile_resolver=resolve_active_workflow_profile,
        operator_scope_ports=unavailable_operator_scope_ports(),
        filing_action_ports_factory=build_filing_action_ports,
        certificate_secret_backend_factory=unavailable,
    )
    context = _Context(operation)
    request = OperationRequest(
        definition_id="modelo.work.file",
        subject_ref=work_unit_id,
        payload=ModeloWorkFileRequest(
            approval=ModeloWorkFileApproval(calculation_revision_id=revision_id, verification_report_id="0" * 64),
            actor="operator",
        ),
    )
    with pytest.raises(CadrumoError) as refused:
        asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))
    assert context.events.effects == []
    return refused.value


def _assert_names_calculating(error: CadrumoError) -> None:
    """The refusal of a lifecycle step on a work unit with no calculation: calculate it first."""
    assert isinstance(error, ModeloCalculationRevisionSelectorNotFoundError), error
    verdict = error.terminal_precondition_verdict
    assert isinstance(verdict, PreconditionVerdict)
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.calculate"


def _verified_then_withdrawn(renta: SeededOperatorWork) -> CalculationRevision:
    """State the carries, record the calculation as verified, withdraw it, and return it as stored."""
    _stated(renta)
    head = renta.require_head()
    verified = head.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": head.updated_at,
            "verified_by": "operator:test",
        }
    )
    renta.ports.calculation_repository.save(
        upsert_calculation_revision(renta.ports.calculation_repository.load(), verified)
    )
    assert renta.apply(binding=(_withdraw(_PENDING_CARRIES[0]),)).refusal is None
    # Nothing is deleted: the withdrawn calculation keeps its verified state.
    assert renta.ports.calculation_repository.load().get(verified.calculation_revision_id) == verified
    return verified


@pytest.mark.parametrize("year", _renta_years())
def test_no_lifecycle_step_takes_a_withdrawn_verified_calculation_as_the_declarations(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        withdrawn = _verified_then_withdrawn(renta)
        withdrawn_id = withdrawn.calculation_revision_id
        unit = renta.ports.work_unit_repository.load().get(renta.work_unit_id)
        assert unit is not None
        assert unit.current_calculation_revision_id is None

        # Verifying the withdrawn calculation by its exact id, and filing it under an approval naming it.
        _assert_names_calculating(_refused_verification(renta.operation, renta.work_unit_id, withdrawn_id))
        _assert_names_calculating(_refused_filing(renta.operation, renta.work_unit_id, withdrawn_id))

        # The default export choice, which falls back to a lone verified revision when one is current.
        with pytest.raises(ModeloCalculationRevisionSelectorNotFoundError) as default_export_refused:
            select_exportable_revision(
                unit, calculation_repository=renta.ports.calculation_repository, operation=renta.operation
            )
        _assert_names_calculating(default_export_refused.value)

        # Exporting it by its exact id.
        with pytest.raises(ModeloCalculationRevisionSelectorNotFoundError) as export_refused:
            load_exportable_revision_target(
                withdrawn_id,
                active_bucket_id=unit.bucket_id,
                export_ports=build_modelo_export_ports(
                    bucket_id=unit.bucket_id,
                    m303_rectificativa_taxpayer_tax_id=resolve_active_workflow_profile(renta.operation).tax_id,
                    operation=renta.operation,
                ),
                operation=renta.operation,
            )
        _assert_names_calculating(export_refused.value)
        assert renta.ports.calculation_repository.load().get(withdrawn_id) == withdrawn


def _empty_ledger(bucket_id: str, period: Period) -> LedgerStatusReport:
    return LedgerStatusReport(
        bucket_id=bucket_id,
        period=period,
        business_income_total="0.00",
        business_expense_total="0.00",
        business_net_total="0.00",
        total_count=0,
        active_count=0,
        archived_count=0,
        stashed_count=0,
        pending_review_count=0,
        reviewed_count=0,
        skipped_count=0,
        ready=None,
    )


@pytest.mark.parametrize("year", _renta_years())
def test_the_declaration_lists_and_overview_show_no_current_calculation_after_a_withdrawal(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        withdrawn = _verified_then_withdrawn(renta)
        units = renta.ports.work_unit_repository.load()
        (unit,) = units.values()

        portfolio = project_declarations_portfolio(
            operation=renta.operation,
            bucket_id=unit.bucket_id,
            work_units=units,
            calculation_revisions=renta.ports.calculation_repository.load(),
            filing_records=ModeloRecordCatalogue(),
            lifecycle_facts=(),
            zone_observations=tuple(
                DeclarationsWorkspaceZoneObservationV1(
                    zone=zone, availability=DeclarationsWorkspaceAvailability.AVAILABLE, observed_at=unit.updated_at
                )
                for zone in DeclarationsWorkspaceZone
            ),
            profile=None,
        )
        (declaration,) = portfolio.declarations
        assert not declaration.has_current_calculation
        assert declaration.settled_result is None
        # The withdrawn calculation stays in the history, not as the current one.
        (listed,) = [
            ref
            for ref in portfolio.calculation_revisions
            if ref.calculation_revision_id == withdrawn.calculation_revision_id
        ]
        assert not listed.is_current
        assert listed.state is CalculationRevisionState.VERIFICADO_COMPLETO

        period = Period.from_year_and_code(year, "0A")
        health = build_pipeline_health_report(
            bucket_id=str(unit.bucket_id),
            filing_year=year,
            period=period,
            ledger_report=_empty_ledger(str(unit.bucket_id), period),
            work_units=(unit,),
            # Even handed the withdrawn calculation, the overview reads only the work unit's own pointer.
            revisions_by_id={withdrawn.calculation_revision_id: withdrawn},
            reports_by_revision_id={},
        )
        (row,) = health.modelos
        assert row.state is ModeloReadinessState.NOT_STARTED
        assert row.next_action is not None
        assert row.next_action.action.action_id == "operator.modelo.work.calculate"
        assert not health.ready
