"""The joint-versus-individual comparison runs on the declaration's own held values.

Each case seeds a synthetic 2025 married taxpayer in an isolated encrypted
profile, saves a Modelo 100 calculation through the production calculation
service with the operator's entries recorded, and then runs the registered
``modelo.work.compare_taxation`` executor over the production calculation
ports. The comparison replays what the calculation held and evaluates both
modes through the same source mesh, saving nothing; it refuses only when a box
the compared results read has no value, and names those boxes in served words.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Generator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.retencion_soportada_seed import seed_payer_certificate
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.modelo.calculation_action_ports import CalculationActionPorts
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.calculation_operation import build_modelo_work_calculate_definition
from ....application.modelo.calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES
from ....application.modelo.operation_shared import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from ....application.modelo.taxation_comparison import (
    TaxationComparisonError,
    TaxationComparisonRefusal,
    TaxationRecommendation,
)
from ....application.modelo.taxation_comparison_operation import (
    MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,
    ModeloTaxationComparisonProjection,
    ModeloTaxationComparisonRequest,
    build_modelo_taxation_comparison_definition,
)
from ....application.modelo.work_addressing import law_selected_revision_for_work_target
from ....application.modelo.work_calculation_contracts import (
    ModeloWorkCalculatePublicResultV3,
    ModeloWorkCalculateRequest,
)
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....application.operations.error_detail import build_operation_error_detail
from ....application.operations.models import OperationRequest
from ....application.operations.owner import OperationExecutorContext
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import CasillaId
from ....core.config import override_settings
from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ....core.operations import OperationEffect, profile_operation_subject
from ....core.period import Period
from ....core.retencion_soportada import RetencionSoportadaClase
from ....domain.attachments.protocols import AttachmentStoreProtocol
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_targets import casillas_by_binding
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ....domain.calculations.registry.tests.authored_editions import (
    newest_authored_edition,
    projected_exercise,
    supported_exercises_with_projection,
)
from ....domain.contribuyente.renta_codes import RentaDeclaracionType, RentaMaritalStatus
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from .file_flow_test_support import calculation_ports_for_test

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "31111111-1111-4111-8111-111111111111"
_PROFILE_ID = UUID(_BUCKET_ID)
_TAX_ID = "12345678Z"
_SPOUSE_TAX_ID = "00001005Q"
_YEAR = 2025
_COMPARED_YEARS = supported_exercises_with_projection("100")
"""Every authored Modelo 100 exercise from the support floor up, then the first year projected from the newest edition."""
_YEAR_OPERATOR_FACTS: dict[int, tuple[UserProfileFact, ...]] = {
    2024: (UserProfileFact(path="renta_family.cotizaciones_ss_madre_2024", value=Decimal("0")),),
}
"""The operator inputs a year's own design adds, which the 2024 nursery-cap term reads and no profile derives."""
_RESIDENCE: BindingId = "renta-profile-tax-residence-ccaa"
_WORK_INCOME: CasillaId = "0003"
_SAVINGS_INCOME: CasillaId = "0429"
"""The net positive movable-capital yield integrated in the savings base, which the operator keys."""
_WORK_CREDIT: BindingId = "renta-retencion-soportada-trabajo"


def _single_parent_facts(*, convive_con_otro_progenitor: bool | None) -> tuple[UserProfileFact, ...]:
    facts = [
        UserProfileFact(path="renta_taxpayer.birth_date", value=datetime(1980, 3, 15, tzinfo=UTC).date()),
        UserProfileFact(path="renta_taxpayer.marital_status", value=RentaMaritalStatus.SOLTERO.code),
        UserProfileFact(path="renta_filing.declaration_type", value=RentaDeclaracionType.INDIVIDUAL.code),
        UserProfileFact(path="renta_family.situacion_familiar", value="soltero"),
        UserProfileFact(path="renta_family.minor_children_in_unit", value=True),
    ]
    if convive_con_otro_progenitor is not None:
        facts.append(
            UserProfileFact(path="renta_family.convive_con_otro_progenitor", value=convive_con_otro_progenitor)
        )
    return tuple(facts)


def _married_facts(
    *,
    situacion: str | None = "casado",
    minor_children: bool | None = False,
    spouse_tax_id: str | None = _SPOUSE_TAX_ID,
    declaration_type: RentaDeclaracionType = RentaDeclaracionType.INDIVIDUAL,
) -> tuple[UserProfileFact, ...]:
    facts = [
        UserProfileFact(path="renta_taxpayer.birth_date", value=datetime(1980, 3, 15, tzinfo=UTC).date()),
        UserProfileFact(path="renta_taxpayer.marital_status", value=RentaMaritalStatus.CASADO.code),
        UserProfileFact(path="renta_taxpayer.marriage_full_year", value=True),
        UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("1")),
        UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("12")),
        UserProfileFact(path="renta_filing.declaration_type", value=declaration_type.code),
    ]
    if spouse_tax_id is not None:
        facts.append(UserProfileFact(path="renta_spouse.tax_id", value=spouse_tax_id))
    if situacion is not None:
        facts.append(UserProfileFact(path="renta_family.situacion_familiar", value=situacion))
    if minor_children is not None:
        facts.append(UserProfileFact(path="renta_family.minor_children_in_unit", value=minor_children))
    return tuple(facts)


_SALARIED_OMISSIONS = ("irpf.estimation_regime", "activities.", "censo.activity_start_date")
"""A salaried filer: work income only, so no economic-activity register is owed."""


def _seed_taxpayer(renta_facts: tuple[UserProfileFact, ...], *, economic_activity: bool) -> None:
    taxpayer_facts = (
        (UserProfileFact(path="activities.description", value="economic activity"),)
        if economic_activity
        else (UserProfileFact(path="taxpayer_type.irpf_income_categories", value="trabajo"),)
    )
    seed_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=persona_facts_beneath(
                (
                    UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                    UserProfileFact(path="identity.name", value="Test"),
                    UserProfileFact(path="identity.surnames", value="Operator"),
                    *taxpayer_facts,
                    *renta_facts,
                ),
                # These scenarios own the family situation: the persona's single status never fills a gap they leave.
                without=(*(() if economic_activity else _SALARIED_OMISSIONS), "renta_family.situacion_familiar"),
            ),
            created_at=datetime(2026, 4, 1, tzinfo=UTC),
            updated_at=datetime(2026, 4, 1, tzinfo=UTC),
            context=profile_creation_context_for_test(),
        ),
    )


def _filler_binding_values(
    operation: PinnedAuthorityOperation, *, year: int, leave_unanswered: frozenset[BindingId] = frozenset()
) -> dict[BindingId, Decimal]:
    """The operator's zero answers for every binding no profile fact, record or ledger owns.

    The prior-period fold slots are answered on the binding channel, as the
    operator answers them, so the recorded operator layer replays them.
    """
    snapshot = operation.snapshot("100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION)
    revision = snapshot.revision
    alternates = {binding_id for casilla in revision.casillas for binding_id in casilla.alternate_bindings}
    targets = casillas_by_binding(revision)
    credit_boxes = set(targets.get(_WORK_CREDIT, ()))
    answers = {
        binding.id: Decimal("0")
        for binding in revision.bindings
        if binding.id not in {_WORK_CREDIT, _RESIDENCE, *alternates}
        and binding.source != "profile"
        and binding.source not in BUCKET_AGGREGATION_LOCK_SOURCES
        and binding.provider.kind != "retencion_soportada"
    }
    answers |= {
        binding.id: Decimal("0")
        for binding, _ in relation_prefill_bindings_for_period(revision)
        if not credit_boxes.intersection(targets.get(binding.id, ()))
    }
    return {binding_id: value for binding_id, value in answers.items() if binding_id not in leave_unanswered}


@dataclass(frozen=True, slots=True)
class _Profile:
    operation: PinnedAuthorityOperation
    work_units: WorkUnitCatalogueRepository
    calculations: CalculationRevisionCatalogueRepository
    events: BucketEventHistoryRepository
    year: int = _YEAR

    def create_work(self) -> str:
        period = Period.from_year_and_code(self.year, "0A")
        return create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=self.year,
            period=period,
            revision_id=law_selected_revision_for_work_target(
                modelo="100", filing_year=self.year, period=period, operation=self.operation
            ),
            ports=WorkLifecyclePorts(work_unit_repository=self.work_units, bucket_event_repository=self.events),
            operation=self.operation,
        ).work_unit_id

    def calculate(
        self,
        work_unit_id: str,
        *,
        work_income: Decimal,
        savings_income: Decimal | None = None,
        leave_unanswered: frozenset[BindingId] = frozenset(),
        record_operator_layer: bool = True,
    ) -> CalculationRevision:
        with calculation_ports_for_test(
            bucket_id=_BUCKET_ID,
            work_unit_repository=self.work_units,
            calculation_repository=self.calculations,
            bucket_event_repository=self.events,
        ) as ports:
            return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit_id,
                actor="operator-A",
                casilla_inputs={
                    _WORK_INCOME: work_income,
                    **({} if savings_income is None else {_SAVINGS_INCOME: savings_income}),
                },
                binding_values=_filler_binding_values(
                    self.operation, year=self.year, leave_unanswered=leave_unanswered
                ),
                enum_binding_values={_RESIDENCE: "madrid"},
                record_operator_layer=record_operator_layer,
                ports=ports,
            ).revision

    def calculate_through_operation(
        self, work_unit_id: str, *, monkeypatch: pytest.MonkeyPatch
    ) -> ModeloWorkCalculatePublicResultV3:
        """Run the registered calculate executor over the production ports, replaying the head, as the worker does."""
        monkeypatch.setattr("cadrumo.core.bucket_pointer.require_active_bucket_id", lambda: _BUCKET_ID)
        stored: list[BaseModel] = []
        effects: list[OperationEffect] = []
        request = OperationRequest[BaseModel](
            definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(_BUCKET_ID),
            payload=ModeloWorkCalculateRequest(work_unit_id=work_unit_id, actor="operator-A"),
        )

        def unavailable_attachments(bucket_id: str) -> object:
            raise AssertionError(f"no attachment store is read for a Modelo 100 calculation ({bucket_id})")

        with calculation_ports_for_test(
            bucket_id=_BUCKET_ID,
            work_unit_repository=self.work_units,
            calculation_repository=self.calculations,
            bucket_event_repository=self.events,
        ) as ports:

            def factory(*, bucket_id: str, operation: PinnedAuthorityOperation, profile_record: object | None = None):
                del operation, profile_record
                assert bucket_id == _BUCKET_ID
                return ports

            definition = build_modelo_work_calculate_definition(
                calculation_action_ports_factory=factory,
                attachment_store_factory=cast("Callable[[str], AttachmentStoreProtocol]", unavailable_attachments),
            )
            context = _executor_context(request, ports=ports, stored=stored, effects=effects)
            with override_settings(cadrumo_active_profile=_BUCKET_ID, cadrumo_output_language="en"):
                asyncio.run(definition.executor_factory.create().execute(request, context))
        (result,) = stored
        return ModeloWorkCalculatePublicResultV3.model_validate(result)

    def compare(self, work_unit_id: str) -> ModeloTaxationComparisonProjection:
        """Run the registered executor over the production calculation ports, as the worker does."""
        stored: list[BaseModel] = []
        effects: list[OperationEffect] = []
        request = OperationRequest[BaseModel](
            definition_id=MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(_BUCKET_ID),
            payload=ModeloTaxationComparisonRequest(profile_id=_PROFILE_ID, work_unit_id=work_unit_id),
        )
        with calculation_ports_for_test(
            bucket_id=_BUCKET_ID,
            work_unit_repository=self.work_units,
            calculation_repository=self.calculations,
            bucket_event_repository=self.events,
        ) as ports:

            def factory(*, bucket_id: str, operation: PinnedAuthorityOperation, profile_record: object | None = None):
                del operation, profile_record
                assert bucket_id == _BUCKET_ID
                return ports

            definition = build_modelo_taxation_comparison_definition(factory)
            context = _executor_context(request, ports=ports, stored=stored, effects=effects)
            with override_settings(cadrumo_active_profile=_BUCKET_ID, cadrumo_output_language="en"):
                asyncio.run(definition.executor_factory.create().execute(request, context))
        assert effects == [OperationEffect.NONE]
        (projection,) = stored
        return ModeloTaxationComparisonProjection.model_validate(projection)


def _executor_context(
    request: OperationRequest[BaseModel],
    *,
    ports: CalculationActionPorts,
    stored: list[BaseModel],
    effects: list[OperationEffect],
) -> OperationExecutorContext:
    class Cancellation:
        @asynccontextmanager
        async def irreversible_section(self) -> AsyncGenerator[None]:
            yield

    class Events:
        async def phase(self, phase_code: str) -> None:
            del phase_code

        async def effect(self, effect: OperationEffect) -> None:
            effects.append(effect)

    class Operands:
        async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
            del written_at
            stored.append(operand)
            return "f" * 64

    return cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=SimpleNamespace(definition_id=request.definition_id, subject_ref=request.subject_ref),
                authority_operation=ports.operation,
                cancellation=Cancellation(),
                events=Events(),
                operands=Operands(),
            ),
        ),
    )


@pytest.fixture
def profile_factory(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> Generator[object]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        objects = runtime.repository

        def build(
            renta_facts: tuple[UserProfileFact, ...] | None = None,
            *,
            economic_activity: bool = False,
            year: int = _YEAR,
        ) -> _Profile:
            _seed_taxpayer(
                (*(_married_facts() if renta_facts is None else renta_facts), *_YEAR_OPERATOR_FACTS.get(year, ())),
                economic_activity=economic_activity,
            )
            return _Profile(
                operation=operation,
                work_units=WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
                calculations=CalculationRevisionCatalogueRepository(objects=objects),
                events=BucketEventHistoryRepository(objects=objects),
                year=year,
            )

        yield build


def _credited(profile: _Profile) -> None:
    seed_payer_certificate(
        operation=profile.operation,
        taxpayer_tax_id=_TAX_ID,
        ejercicio=profile.year,
        payer_tax_id="B00015016",
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion=Decimal("1.00"),
    )


def _refused(profile: _Profile, work_unit_id: str) -> TaxationComparisonError:
    with pytest.raises(TaxationComparisonError) as refused:
        profile.compare(work_unit_id)
    return refused.value


@pytest.mark.parametrize("year", _COMPARED_YEARS)
def test_married_return_compares_on_its_held_values(profile_factory, year: int) -> None:
    """A calculated married return, in every year whose design carries the filing option, compares both modes from what it holds, saving nothing.

    Only box 0003 was entered: every other manual box is empty and unread, and
    reads as nothing entered rather than blocking the comparison, as it does in
    the calculation itself. Art. 84.2.3º LIRPF gives the married unit 3,400 EUR
    off the joint base, so with one earner the joint result is lower.
    """
    profile = profile_factory(year=year)
    _credited(profile)
    work_unit_id = profile.create_work()
    profile.calculate(work_unit_id, work_income=Decimal("52000"))
    saved = set(profile.calculations.load(operation=profile.operation).revisions)

    result = profile.compare(work_unit_id)

    assert result.recommendation is TaxationRecommendation.CONJUNTA
    conjunta, individual = Decimal(result.conjunta_resultado), Decimal(result.individual_resultado)
    assert conjunta < individual
    assert Decimal(result.delta_resultado) == individual - conjunta
    assert result.modelo == "100"
    assert result.filing_year == year
    assert set(profile.calculations.load(operation=profile.operation).revisions) == saved


@pytest.mark.parametrize("year", [newest_authored_edition("100"), projected_exercise("100")])
def test_calculate_work_completes_end_to_end_for_an_authored_and_a_projected_year(
    profile_factory, monkeypatch: pytest.MonkeyPatch, year: int
) -> None:
    """The calculate operation publishes its result for the newest authored year and for the year projected from it.

    A projected year's work unit holds the source edition's revision, and the
    law revision the published result is checked against is the one the same
    temporal selection gives, so the result is neither refused nor left
    unresolvable.
    """
    profile = profile_factory(year=year)
    _credited(profile)
    work_unit_id = profile.create_work()
    profile.calculate(work_unit_id, work_income=Decimal("52000"))

    result = profile.calculate_through_operation(work_unit_id, monkeypatch=monkeypatch)

    assert result.work_unit_id == work_unit_id
    assert result.calculation.filing_year == year
    assert result.calculation.registry_snapshot_ref.revision_id == str(newest_authored_edition("100"))


def test_unresolved_result_input_refuses_naming_the_boxes(profile_factory) -> None:
    """A box the results read with no value refuses by name in served words; it is never read as zero.

    An economic-activity filer with no inventory register leaves the Anexo D
    inventory boxes unresolved, and the results read them.
    """
    profile = profile_factory(economic_activity=True)
    _credited(profile)
    work_unit_id = profile.create_work()
    profile.calculate(work_unit_id, work_income=Decimal("52000"))

    refusal = _refused(profile, work_unit_id)

    assert refusal.refusal is TaxationComparisonRefusal.UNRESOLVED_BOXES
    assert {"0177", "0181", "0182"} <= set(refusal.casilla_ids)
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        with override_settings(cadrumo_output_language=language):
            detail = build_operation_error_detail(refusal)
        assert detail is not None
        assert detail.refusal_words is not None
        for casilla_id in refusal.casilla_ids:
            assert casilla_id in detail.refusal_words
        assert "52000" not in detail.refusal_words
        assert "52.000" not in detail.refusal_words


@pytest.mark.parametrize("year", _COMPARED_YEARS)
def test_single_parent_with_cohabitation_unstated_refuses_on_the_joint_reduction(profile_factory, year: int) -> None:
    """Art. 84.2.4º LIRPF: the 2,150 EUR depends on cohabitation, so an unstated fact leaves 0461 unresolved."""
    profile = profile_factory(_single_parent_facts(convive_con_otro_progenitor=None), year=year)
    _credited(profile)
    work_unit_id = profile.create_work()
    profile.calculate(work_unit_id, work_income=Decimal("30000"))

    refusal = _refused(profile, work_unit_id)

    assert refusal.refusal is TaxationComparisonRefusal.UNRESOLVED_BOXES
    assert "0461" in refusal.casilla_ids


@pytest.mark.parametrize("year", _COMPARED_YEARS)
def test_single_parent_without_spouse_compares(profile_factory, year: int) -> None:
    """A single-parent joint return has no spouse, so it compares without a spouse tax ID."""
    profile = profile_factory(_single_parent_facts(convive_con_otro_progenitor=False), year=year)
    _credited(profile)
    work_unit_id = profile.create_work()
    profile.calculate(work_unit_id, work_income=Decimal("30000"))

    result = profile.compare(work_unit_id)

    assert result.recommendation is TaxationRecommendation.CONJUNTA


def _spouse_unstated() -> tuple[UserProfileFact, ...]:
    return _married_facts(spouse_tax_id=None)


def _no_family_unit() -> tuple[UserProfileFact, ...]:
    return _married_facts(situacion="soltero", minor_children=False)


def _situation_unstated() -> tuple[UserProfileFact, ...]:
    return _married_facts(situacion=None)


@pytest.mark.parametrize(
    ("facts", "refusal"),
    [
        (_spouse_unstated, TaxationComparisonRefusal.SPOUSE_UNSTATED),
        (_no_family_unit, TaxationComparisonRefusal.NO_FAMILY_UNIT),
        (_situation_unstated, TaxationComparisonRefusal.FAMILY_SITUATION_UNSTATED),
    ],
    ids=["spouse-unstated", "no-family-unit", "situation-unstated"],
)
def test_profile_that_cannot_file_jointly_refuses(
    profile_factory, facts: Callable[[], tuple[UserProfileFact, ...]], refusal: TaxationComparisonRefusal
) -> None:
    profile = profile_factory(facts())
    _credited(profile)
    work_unit_id = profile.create_work()
    profile.calculate(work_unit_id, work_income=Decimal("52000"))

    assert _refused(profile, work_unit_id).refusal is refusal


def test_uncalculated_return_refuses(profile_factory) -> None:
    profile = profile_factory()
    work_unit_id = profile.create_work()

    assert _refused(profile, work_unit_id).refusal is TaxationComparisonRefusal.NOT_CALCULATED


def _state_cohabitation(profile: _Profile, answer: str, *, through: str) -> None:
    """State whether the single parent lives with the child's other parent, as a person does.

    ``through`` names the door: the wizard's revision-bound patch or the desktop's
    one-field writer. Both are given the revision and digest the profile was read at.
    """
    from ....application.user_profile.fact_write import apply_manager_profile_field_mutation
    from ....application.user_profile.profile_record_repository import ProfileRecordRepository
    from ....application.wizard.catalogue import build_setup_flow
    from ....application.wizard.patch_edit import apply_profile_patch

    context = profile.operation.profile_decode_context()
    read = ProfileRecordRepository.for_current_session(_BUCKET_ID, profile_decode_context=context).load(_BUCKET_ID)
    if through == "wizard":
        apply_profile_patch(
            flow=build_setup_flow(profile.operation),
            profile_id=_BUCKET_ID,
            expected_revision=read.record_revision,
            expected_content_digest=read.content_digest,
            supplied={"family-convive-con-otro-progenitor": answer},
            colegio_concertado=None,
            operation=profile.operation,
        )
    else:
        apply_manager_profile_field_mutation(
            profile_id=_BUCKET_ID,
            path="renta_family.convive_con_otro_progenitor",
            value=answer,
            expected_revision=read.record_revision,
            expected_content_digest=read.content_digest,
            profile_decode_context=context,
        )


@pytest.mark.parametrize("door", ["wizard", "desktop"])
def test_stating_the_cohabitation_lets_a_single_parent_compare(profile_factory, door: str) -> None:
    """Stating the fact through either door resolves box 0461, so the comparison stops refusing on it.

    Art. 84.2.4º LIRPF: the 2,150 EUR reduction does not apply while the single
    parent lives with the father or mother of a child in the unit, so living
    together leaves a higher joint result than living apart. Withdrawing the
    answer returns the refusal: not stated is not "no".
    """
    profile = profile_factory(_single_parent_facts(convive_con_otro_progenitor=None))
    _credited(profile)
    work_unit_id = profile.create_work()

    profile.calculate(work_unit_id, work_income=Decimal("30000"))
    assert "0461" in _refused(profile, work_unit_id).casilla_ids

    _state_cohabitation(profile, "false", through=door)
    profile.calculate(work_unit_id, work_income=Decimal("30000"))
    apart = profile.compare(work_unit_id)

    _state_cohabitation(profile, "true", through=door)
    profile.calculate(work_unit_id, work_income=Decimal("30000"))
    together = profile.compare(work_unit_id)

    assert Decimal(together.conjunta_resultado) > Decimal(apart.conjunta_resultado)
    assert together.individual_resultado == apart.individual_resultado

    _state_cohabitation(profile, "", through="desktop")
    profile.calculate(work_unit_id, work_income=Decimal("30000"))
    refusal = _refused(profile, work_unit_id)
    assert refusal.refusal is TaxationComparisonRefusal.UNRESOLVED_BOXES
    assert "0461" in refusal.casilla_ids


_JOINT_REDUCTION: CasillaId = "0461"
_GENERAL_TAXABLE_BASE: CasillaId = "0435"
_SAVINGS_TAXABLE_BASE: CasillaId = "0460"
_GENERAL_LIQUIDABLE_BASE: CasillaId = "0500"
_JOINT_REDUCTION_SAVINGS_REMAINDER: CasillaId = "0506"
_SAVINGS_LIQUIDABLE_BASE: CasillaId = "0510"
_MARRIED_UNIT_REDUCTION = Decimal("3400")
"""Art. 84.2.3º LIRPF: the married unit's joint reduction."""
_LOW_WORK_INCOME = Decimal("2000")
"""Work income the general base cannot carry the whole joint reduction on."""
_SAVINGS = Decimal("20000")


def _joint_values(
    year: int, profile_factory: Callable[..., _Profile], *, work_income: Decimal, savings_income: Decimal | None
) -> Mapping[CasillaId, Decimal]:
    """Calculate a married joint return and return the values it saved."""
    profile = profile_factory(_married_facts(declaration_type=RentaDeclaracionType.JOINT), year=year)
    _credited(profile)
    work_unit_id = profile.create_work()
    revision = profile.calculate(work_unit_id, work_income=work_income, savings_income=savings_income)
    return revision.casilla_values


@pytest.mark.parametrize("year", _COMPARED_YEARS)
def test_joint_reduction_the_general_base_cannot_absorb_reduces_the_savings_base(profile_factory, year: int) -> None:
    """Art. 84.2.3º LIRPF: the remainder of 0461 the general base cannot take reduces the savings base.

    The reduction goes first to the general base, which it may not make
    negative; box 0506 (JREDU21, "Remanente de la casilla [0461] que se
    aplica") carries the rest into the savings base 0510.
    """
    values = _joint_values(year, profile_factory, work_income=_LOW_WORK_INCOME, savings_income=_SAVINGS)

    general = max(Decimal("0"), values[_GENERAL_TAXABLE_BASE])
    assert values[_JOINT_REDUCTION] == _MARRIED_UNIT_REDUCTION
    assert general < _MARRIED_UNIT_REDUCTION
    assert values[_SAVINGS_TAXABLE_BASE] == _SAVINGS
    assert values[_GENERAL_LIQUIDABLE_BASE] == Decimal("0")
    assert values[_JOINT_REDUCTION_SAVINGS_REMAINDER] == _MARRIED_UNIT_REDUCTION - general
    assert values[_SAVINGS_LIQUIDABLE_BASE] == _SAVINGS - (_MARRIED_UNIT_REDUCTION - general)


@pytest.mark.parametrize("year", _COMPARED_YEARS)
def test_joint_reduction_the_general_base_absorbs_leaves_the_savings_base_whole(profile_factory, year: int) -> None:
    """A general base at least equal to 0461 takes all of it, so 0506 is zero and 0510 keeps all the savings."""
    values = _joint_values(year, profile_factory, work_income=Decimal("52000"), savings_income=_SAVINGS)

    assert values[_GENERAL_TAXABLE_BASE] >= _MARRIED_UNIT_REDUCTION
    assert values[_JOINT_REDUCTION_SAVINGS_REMAINDER] == Decimal("0")
    assert values[_SAVINGS_LIQUIDABLE_BASE] == _SAVINGS


@pytest.mark.parametrize("year", _COMPARED_YEARS)
def test_joint_reduction_without_savings_never_makes_the_savings_base_negative(profile_factory, year: int) -> None:
    """With no savings income the remainder has nothing to reduce: 0506 and 0510 stay at zero, never below it."""
    values = _joint_values(year, profile_factory, work_income=_LOW_WORK_INCOME, savings_income=None)

    assert max(Decimal("0"), values[_GENERAL_TAXABLE_BASE]) < _MARRIED_UNIT_REDUCTION
    assert values[_SAVINGS_TAXABLE_BASE] == Decimal("0")
    assert values[_JOINT_REDUCTION_SAVINGS_REMAINDER] == Decimal("0")
    assert values[_SAVINGS_LIQUIDABLE_BASE] == Decimal("0")


@pytest.mark.parametrize("year", _COMPARED_YEARS)
def test_comparison_credits_the_joint_reduction_remainder_against_savings(profile_factory, year: int) -> None:
    """The joint run applies the remainder of 0461 to the savings base, so it costs less than the individual run.

    The general base is too small for the reduction and the savings income
    exceeds the personal minimum, so the only difference between the two runs
    is the remainder taken off the taxed savings base.
    """
    profile = profile_factory(year=year)
    _credited(profile)
    work_unit_id = profile.create_work()
    profile.calculate(work_unit_id, work_income=_LOW_WORK_INCOME, savings_income=_SAVINGS)

    result = profile.compare(work_unit_id)

    assert Decimal(result.conjunta_resultado) < Decimal(result.individual_resultado)
    assert result.recommendation is TaxationRecommendation.CONJUNTA
