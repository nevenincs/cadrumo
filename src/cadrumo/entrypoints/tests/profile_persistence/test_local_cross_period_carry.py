"""Automatic local cross-period previous_filing carry.

These tests exercise the local ``file`` -> next-period ``calculate`` carry seam end
to end with real encrypted-SQLite repositories and the real registry — no mocks,
stubs, skips, or xfail.

The carry vehicle is Modelo 130 (IRPF pago fraccionado, estimación directa). Casilla
15 ("Resultados negativos de trimestres anteriores") is bound via
``source = "previous_filing"`` to the prior quarter's computed
``saldo-negativo-fin-periodo`` (AEAT instructions under the RD 439/2007
art. 110 pago-fraccionado framework). When a quarter's Diferencia (casilla
17) is negative the absolute value seeds the next quarter's casilla 15.

The four behaviours under test:

* E2E (carry): filing 1T with a negative Diferencia persists an ``app_filing``
  observation; calculating 2T then auto-fills casilla 15 from it WITHOUT any manual
  ``--casilla`` / ``--binding``.
* D1 (clean-state non-official): the ``app_filing`` observation does NOT satisfy the
  cross-period clean-state gate for FILING a dependent period — it still blocks with
  ``LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE``.
* D2 (override precedence): a caller ``--binding`` beats the auto-carried value and is
  NOT rejected as a source-owned collision; a caller value that differs from the carried
  one is persisted as a tier divergence and blocks verify.
* D3 (303 exclusion): the carry resolver never emits the M303 IVA-compensation
  binding (the iva-wallet decision owns it).
* D4 (grupo fan-in non-goal): documented as out of scope in
  :mod:`cadrumo.application.modelo.filed_revision_observation`; no test asserts member
  fan-in for the local-filing flow.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.calculations.tests.cross_period_verdict_support import has_non_official_local_chain
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.user_profile.tests.imputation_criterion_facts import cash_criterion_facts
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.credit_resolution_records import CreditResolutionRepositoryAdapter
from ....adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.ledger_action_create_support import ledger_ports_for_test
from ....adapters.persistence.profile.tests.modelo_303_filed_disposition import modelo_303_filed_disposition
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.relation_prefill_support import empty_profile_read_ports
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.calculations.observations_repository import APP_FILING_SOURCE_KIND, ResultDispositionProjection
from ....application.calculations.tests.filing_evidence import general_m303_filing_evidence
from ....application.ledger.models import ManualLedgerTransactionCommand
from ....application.ledger.tests.manual_transaction_support import create_manual_transaction
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.calculation_note_gate import (
    SOURCE_DISAGREEMENT_FINDING_ID_LENGTH,
    ModeloCalculationBlockedError,
)
from ....application.modelo.calculation_source_mesh_actions import resolve_bucket_source_mesh
from ....application.modelo.credit_resolution import credit_resolution_for_finding, find_finding
from ....application.modelo.credit_resolution_repository import store_credit_resolution
from ....application.modelo.iva_wallet_refusal import ModeloIvaWalletReconciliationBlocked
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....core.result_disposition import ResultDisposition
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.iva_wallet_carry_targets import (
    MODELO_303_IVA_COMPENSATION_BINDING_ID,
    iva_wallet_owned_binding_ids_for_revision,
)
from ....domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    newest_authored_edition,
    open_ended_revision,
    revision_serving_period,
)
from ....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_observations,
    revision_id_for_observation,
)
from ....domain.modelos.source_disagreement import DisagreementDecimalValue, SourceDisagreementRole
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from .file_flow_test_support import (
    FILE_FLOW_DEFAULT_130_BINDING_VALUES,
    FILE_FLOW_M130_CARRY_FORWARD_CASILLA,
    FILE_FLOW_M130_HOME_DEDUCTION_CASILLA,
    FILE_FLOW_M130_INCOME_CASILLA,
    FILE_FLOW_M130_PRIOR_RETURN_RESULT_CASILLA,
    FILE_FLOW_M130_SALDO_NEGATIVO_CASILLA,
    FILE_FLOW_M130_WITHHELD_CASILLA,
    M130_PREVIOUS_PAYMENTS_CASILLA,
    FileFlowRepos,
    calculation_ports_for_test,
    file_flow_file_revision,
    file_flow_verify_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_YEAR = filing_year_envelope().horizon
_PRIOR_YEAR = _YEAR - 1
_T1 = datetime(_YEAR, 4, 10, 9, 0, 0, tzinfo=UTC)
_T2 = datetime(_YEAR, 4, 11, 9, 0, 0, tzinfo=UTC)
_T3 = datetime(_YEAR, 4, 12, 9, 0, 0, tzinfo=UTC)
_T4 = datetime(_YEAR, 7, 10, 9, 0, 0, tzinfo=UTC)
_BUCKET_ID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[FileFlowRepos]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        yield (
            WorkUnitCatalogueRepository(objects=objects),
            CalculationRevisionCatalogueRepository(objects=objects),
            ModeloRecordCatalogueRepository(objects=objects),
            VerificationReportCatalogueRepository(objects=objects),
            BucketEventHistoryRepository(objects=objects),
        )


_M303_COMPENSACION_DISPONIBLE_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-disponible-fin-periodo")
_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores"
)
_M130_DIFERENCIA_PREVIA_CASILLA: CasillaId = validated_casilla_id("14")

# The M130 carry binding feeds computed casilla 15. Calculation caps the raw
# previous_filing saldo-negativo at the current positive C14 before it flows through.
_CARRY_BINDING_ID = "modelo-130-resultados-negativos-anteriores"

# No withholding is declared: no source states one, so box 06 is the ledger's
# own zero and no operator value competes with it. A first-year filer's
# previous-year net income is zero, so the art. 110.3.c minoración (box 13)
# exceeds 1T's zero partial result and makes the Diferencia negative. Home
# deduction stays zero, so the subsequent prior-payments aggregation cannot
# manufacture a negative Casilla05. The carry seed is read from the actually
# saved/filed revision, rather than derived here from the formulas.
_NEGATIVE_1T_INPUTS: dict[CasillaId, Decimal] = {
    FILE_FLOW_M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
    FILE_FLOW_M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
}
# Income/gastos remain resolver-owned. A real Q2 income receipt funds a
# positive current C14 below the saved carry: its 20 % partial result exceeds
# the quarter's minoración by less than the 1T seed. Casillas05/15 still come
# only from previous_filing, never from manual inputs.
_2T_INPUTS_WITHOUT_15: dict[CasillaId, Decimal] = dict(_NEGATIVE_1T_INPUTS)
_2T_INCOME = Decimal("750")


def _seed_130(
    repos_: FileFlowRepos,
    *,
    period: str,
    clock: datetime,
    operation: PinnedAuthorityOperation,
):
    wu_repo = repos_[0]
    return create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period),
        revision_id=str(open_ended_revision("130").id),
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=BucketEventHistoryRepository()),
        clock=clock,
        operation=operation,
    )


def _seed_2t_130_income(repos_: FileFlowRepos) -> str:
    """Fund positive 2T through the real manual ledger writer and isolated store."""
    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos_
    transactions = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=bv_repo.secure_object_repository)
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=bv_repo.secure_object_repository,
        transaction_repository=transactions,
        bucket_event_repository=bv_repo,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
    ) as ports:
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(_YEAR, 5, 15),
                value_date=date(_YEAR, 5, 15),
                amount=_2T_INCOME,
                direction=TransactionDirection.INCOMING,
                counterparty="Cliente SA",
                description="Q2 economic activity income for cross-period carry",
                business_classification=BusinessClassification.BUSINESS,
                taxable_base=_2T_INCOME,
                irpf_category="actividad_economica",
                actor="operator-A",
                idempotency_key="m130-carry-q2-income",
            ),
            ports=ports,
            occurred_at=_T4,
        )
    persisted = transactions.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.raw.value_date == date(_YEAR, 5, 15)
    assert persisted.raw.amount == _2T_INCOME
    assert persisted.taxable_base == _2T_INCOME
    return persisted.transaction_id


def _file_1t_with_negative_result(repos_: FileFlowRepos, *, operation: PinnedAuthorityOperation) -> Decimal:
    """File Modelo 130 1T with a negative Diferencia; return its saldo-negativo seed.

    Returns the value the 1T revision actually computed for
    ``saldo-negativo-fin-periodo`` (read back from the persisted revision, never
    hand-derived from the formula — anti-tautology).
    """
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos_
    work_unit = _seed_130(repos_, period="1T", clock=_T1, operation=operation)
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_190:
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            casilla_inputs=_NEGATIVE_1T_INPUTS,
            binding_values=FILE_FLOW_DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_190,
            clock=_T1,
        ).revision
    assert Decimal(revision.casilla_values[FILE_FLOW_M130_WITHHELD_CASILLA]) == Decimal("0")
    assert Decimal(revision.casilla_values[FILE_FLOW_M130_HOME_DEDUCTION_CASILLA]) == Decimal("0")
    assert Decimal(revision.casilla_values[M130_PREVIOUS_PAYMENTS_CASILLA]) == Decimal("0")
    saldo = Decimal(revision.casilla_values[FILE_FLOW_M130_SALDO_NEGATIVO_CASILLA])
    assert saldo > 0, "1T inputs must produce a positive carry-forward seed for the test to be meaningful"
    # 1T's casilla-05 expanding-span and casilla-15 single-offset previous_filing
    # bindings are both absent-by-design at 1T (max_year_delta=0, no prior quarter),
    # but the M100 prior-year minoración relation is a real cross-period dependency,
    # so the direct mark-complete shortcut is refused and the full verify pipeline
    # is required. _verify_revision seeds the clean M100 prior-year evidence and
    # marks the 1T revision VERIFICADO_COMPLETO so filing can proceed.
    file_flow_verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )
    # Filing then succeeds because the M100 dependency is clean and the M130
    # same-ejercicio bindings have no prior quarter at 1T.
    # _file_revision threads the workflow gate and lets file_modelo_revision use its
    # default CalculationObservationRepository(), which binds to the active bucket and
    # persists the app_filing carry observation co-emitted with MODELO_FILED.
    file_flow_file_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T3,
    )
    return saldo


def _seed_first_year_activity_profile(repos_: FileFlowRepos) -> None:
    profile = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Autonomo"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="provenance.source", value="manual_cli"),
                UserProfileFact(path="censo.activity_start_date", value=date(_YEAR, 1, 1).isoformat()),
                *cash_criterion_facts(_YEAR),
            )
        ),
        created_at=_T1,
        updated_at=_T1,
        context=profile_creation_context_for_test(),
    )
    seed_test_profile_record(profile)


def _seed_existing_303_activity_profile(repos_: FileFlowRepos) -> None:
    profile = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value="B00015016"),
                UserProfileFact(path="identity.legal_name", value="Test Company SL"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Company"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="provenance.source", value="manual_cli"),
                UserProfileFact(path="censo.activity_start_date", value=date(1990, 1, 1).isoformat()),
            ),
            persona_id="sociedad-limitada",
        ),
        created_at=_T1,
        updated_at=_T1,
        context=profile_creation_context_for_test(),
    )
    seed_test_profile_record(profile)


def _seed_first_303_activity_profile(
    repos_: FileFlowRepos, *, activity_start_date: str = date(_YEAR, 1, 1).isoformat()
) -> None:
    profile = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value="B00015016"),
                UserProfileFact(path="identity.legal_name", value="Test Company SL"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Company"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="provenance.source", value="manual_cli"),
                UserProfileFact(path="censo.activity_start_date", value=activity_start_date),
            ),
            persona_id="sociedad-limitada",
        ),
        created_at=_T1,
        updated_at=_T1,
        context=profile_creation_context_for_test(),
    )
    seed_test_profile_record(profile)


def test_local_file_then_next_period_calculate_carries_previous_filing_value(
    repos: FileFlowRepos,
    operation: PinnedAuthorityOperation,
) -> None:
    """E2E: filing 1T auto-carries its saldo-negativo into 2T's casilla 15 on calculate.

    No manual ``--casilla 15`` / ``--binding`` is supplied for 2T. The carry contract:
    2T's casilla 15 equals the value the 1T revision actually computed for
    ``saldo-negativo-fin-periodo`` (read back from the filed revision, not hand-derived
    from the formula — anti-tautology).
    """
    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos
    _seed_first_year_activity_profile(repos)
    carried_seed = _file_1t_with_negative_result(repos, operation=operation)

    income_id = _seed_2t_130_income(repos)
    work_unit_2t = _seed_130(repos, period="2T", clock=_T4, operation=operation)
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_341:
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit_2t.work_unit_id,
            casilla_inputs=_2T_INPUTS_WITHOUT_15,
            binding_values=FILE_FLOW_DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_341,
            clock=_T4,
        )

    assert income_id in result.revision.source_transaction_ids
    assert Decimal(result.revision.casilla_values[FILE_FLOW_M130_INCOME_CASILLA]) == _2T_INCOME
    assert Decimal(result.revision.casilla_values[FILE_FLOW_M130_WITHHELD_CASILLA]) == Decimal("0")
    assert Decimal(result.revision.casilla_values[M130_PREVIOUS_PAYMENTS_CASILLA]) == Decimal("0")
    carried_casilla_15 = Decimal(result.revision.casilla_values[FILE_FLOW_M130_CARRY_FORWARD_CASILLA])
    c14 = Decimal(result.revision.casilla_values[_M130_DIFERENCIA_PREVIA_CASILLA])
    assert Decimal(result.revision.binding_overrides[_CARRY_BINDING_ID]) == carried_seed
    assert carried_seed > c14 > Decimal("0")
    assert carried_casilla_15 == c14


def test_first_year_activity_start_calculate_scopes_prior_year_m100_binding(
    repos: FileFlowRepos,
    operation: PinnedAuthorityOperation,
) -> None:
    """2T calculation reaches same-year carry without a manual prior-year M100 binding."""
    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos
    _seed_first_year_activity_profile(repos)
    carried_seed = _file_1t_with_negative_result(repos, operation=operation)

    _seed_2t_130_income(repos)
    work_unit_2t = _seed_130(repos, period="2T", clock=_T4, operation=operation)
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_365:
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit_2t.work_unit_id,
            casilla_inputs=_2T_INPUTS_WITHOUT_15,
            binding_values={},
            ports=_calculation_ports_365,
            clock=_T4,
        )

    assert Decimal(result.revision.binding_overrides["irpf.previous_year_economic_activity_net_income"]) == Decimal(
        "0",
    )
    c14 = Decimal(result.revision.casilla_values[_M130_DIFERENCIA_PREVIA_CASILLA])
    assert Decimal(result.revision.binding_overrides[_CARRY_BINDING_ID]) == carried_seed
    assert carried_seed > c14 > Decimal("0")
    assert Decimal(result.revision.casilla_values[FILE_FLOW_M130_CARRY_FORWARD_CASILLA]) == c14


def test_app_filing_source_kind_is_not_official_evidence() -> None:
    """D1 (structural): the local-filing source_kind is NOT in the official-evidence set.

    The cross-period clean-state guard grants filing only when the upstream observation
    carries an official source_kind. ``app_filing`` must never join that set, or an
    unevidenced local chain would launder past the filing gate.
    """
    assert APP_FILING_SOURCE_KIND == "app_filing"
    assert not APP_FILING_SOURCE_KIND.is_official_aeat


def test_same_year_locally_filed_upstream_admitted_with_advisory(
    repos: FileFlowRepos,
    operation: PinnedAuthorityOperation,
) -> None:
    """Same-year admission: a same-year locally-filed 1T lets 2T FILE with a disclosing advisory.

    Filing 1T persists an ``app_filing`` carry observation. A SAME-FILING-YEAR dependent
    period (2T) is admitted: the clean-state guard clears the official-evidence-delta
    blockers for the present, value-consistent app_filing chain and flags a non-blocking
    ``non_official_local_chain_advisory`` so the non-official basis is surfaced
    (``no-silent-under-declaration``). The ``app_filing`` source stays non-official, and a
    cross-YEAR non-official prior still blocks. The within-year reconstruction can reach
    export; the operator files every period with AEAT externally.
    """
    from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
    from ....application.calculations.cross_period_models import CrossPeriodCleanStateBlocker
    from ....application.modelo.verification_cross_period import cross_period_clean_state_verdict_for_work_unit
    from ....domain.modelos.calculation_repository import upsert_calculation_revision
    from ....domain.modelos.calculation_revision import CalculationRevisionState

    wu_repo, cr_repo, fr_repo, _vr_repo, bv_repo = repos
    _seed_first_year_activity_profile(repos)
    _file_1t_with_negative_result(repos, operation=operation)
    local_filing = fr_repo.load().current_for(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "1T"),
    )
    assert local_filing is not None
    assert local_filing.aeat_accepted is False
    assert local_filing.external_evidence is None
    # Confirm the carry observation was persisted under the non-official source_kind.
    stored = CalculationObservationRepository().load_observation("130", Period.from_year_and_code(_YEAR, "1T"))
    assert stored is not None
    assert stored.source_kind == APP_FILING_SOURCE_KIND

    _seed_2t_130_income(repos)
    work_unit_2t = _seed_130(repos, period="2T", clock=_T4, operation=operation)
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_431:
        revision_2t = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit_2t.work_unit_id,
            casilla_inputs=_2T_INPUTS_WITHOUT_15,
            binding_values=FILE_FLOW_DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_431,
            clock=_T4,
        ).revision
    # The 2T cross-period state is deliberately UNCLEAN (the only upstream 1T
    # evidence is the non-official app_filing carry), so the verify pipeline cannot
    # legitimately grant VERIFICADO_COMPLETO and the direct mark-complete shortcut is
    # refused for a cross-period revision. To exercise the FILE gate's own
    # cross-period refusal, force the revision into VERIFICADO_COMPLETO directly
    # through the catalogue - this is fixture setup for the file-transition assertion
    # below, not a test of the mark path.
    verificado_2t = revision_2t.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": _T4,
            "verified_by": "operator-A",
            "updated_at": _T4,
        },
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), verificado_2t))
    revision_2t = verificado_2t

    # Same-year scope: the same-year 1T (M130 same-year) previous_filing
    # dependency is admitted - its official-evidence-delta blockers are cleared (the row
    # is clean) and it carries the disclosing non-official-local-chain advisory. A
    # cross-YEAR dependency (the M100 prior-year minoración evidence) is NOT relaxed, so
    # the anti-laundering scope holds. The app_filing source stays non-official.
    verdict = cross_period_clean_state_verdict_for_work_unit(
        work_unit_2t,
        observation_repository=CalculationObservationRepository(),
        filing_repository=ModeloRecordCatalogueRepository(objects=bv_repo.secure_object_repository),
        calculation_repository=cr_repo,
        verification_repository=VerificationReportCatalogueRepository(objects=bv_repo.secure_object_repository),
        justificante_repository=JustificanteRepository(objects=bv_repo.secure_object_repository),
    )
    assert verdict is not None
    same_year = [
        d for d in verdict.dependencies if d.requirement.source_modelo == "130" and d.requirement.filing_year == _YEAR
    ]
    assert same_year, "expected the same-year M130 same-year carry dependency"
    assert all(d.clean for d in same_year)
    assert all(d.non_official_local_chain_advisory for d in same_year)
    assert all(CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE not in d.blockers for d in same_year)
    assert has_non_official_local_chain(verdict)
    # The cross-YEAR dependency is NOT relaxed - the same-year scope is the safety boundary.
    cross_year = [d for d in verdict.dependencies if d.requirement.filing_year != _YEAR]
    assert all(not d.non_official_local_chain_advisory for d in cross_year)


def test_caller_binding_override_beats_auto_carried_previous_filing(
    repos: FileFlowRepos,
    operation: PinnedAuthorityOperation,
) -> None:
    """D2: a caller ``--binding`` of the carry binding overrides the auto-carried value.

    After filing 1T with a positive saldo-negativo carry, calculating 2T while supplying
    the carry binding id explicitly must (a) NOT be rejected as a source-owned collision
    and (b) drive casilla 15 to the caller's value, not the carried one. The carried
    value is read back from the filed 1T revision so the override case is proven to
    actually differ. Because the two values differ on a filed figure, the calculation
    persists the divergence with both values, and verify refuses until it is resolved.
    """
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    _seed_first_year_activity_profile(repos)
    carried_seed = _file_1t_with_negative_result(repos, operation=operation)
    assert carried_seed > Decimal("0")

    override_value = carried_seed + Decimal("250")
    _seed_2t_130_income(repos)
    work_unit_2t = _seed_130(repos, period="2T", clock=_T4, operation=operation)
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_500:
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit_2t.work_unit_id,
            casilla_inputs=_2T_INPUTS_WITHOUT_15,
            binding_values={**FILE_FLOW_DEFAULT_130_BINDING_VALUES, _CARRY_BINDING_ID: override_value},
            ports=_calculation_ports_500,
            clock=_T4,
        )

    casilla_15 = Decimal(result.revision.casilla_values[FILE_FLOW_M130_CARRY_FORWARD_CASILLA])
    c14 = Decimal(result.revision.casilla_values[_M130_DIFERENCIA_PREVIA_CASILLA])
    assert Decimal(result.revision.binding_overrides[_CARRY_BINDING_ID]) == override_value
    assert override_value > c14 > Decimal("0")
    assert casilla_15 == c14

    divergences = [
        issue
        for issue in result.revision.source_issues
        if issue.reason == "precedence_tier_divergence"
        and issue.disagreement is not None
        and issue.disagreement.key == _CARRY_BINDING_ID
    ]
    assert len(divergences) == 1
    finding = divergences[0].disagreement
    assert finding is not None
    held = {entry.role: entry.value for entry in finding.sources}
    assert held == {
        SourceDisagreementRole.BACKEND: DisagreementDecimalValue.of(carried_seed),
        SourceDisagreementRole.CALLER: DisagreementDecimalValue.of(override_value),
    }
    assert finding.selected_role is SourceDisagreementRole.CALLER
    assert FILE_FLOW_M130_CARRY_FORWARD_CASILLA in finding.reached_casillas
    backend, caller = finding.sources
    # The carried value is named by its declared source, the caller's by the
    # operator channel; neither names a source object. A previous-filing carry
    # records no content fingerprint, so its value has no evidence digest.
    assert (backend.source_family, backend.source_ref) == (
        "previous_filing",
        f"previous_filing:binding:{_CARRY_BINDING_ID}",
    )
    assert backend.evidence_ref is None
    assert (caller.source_family, caller.source_ref) == (
        "operator_input",
        f"operator_input:binding:{_CARRY_BINDING_ID}",
    )
    assert caller.evidence_ref is None

    with pytest.raises(ModeloCalculationBlockedError) as refused:
        file_flow_verify_revision(
            result.revision.calculation_revision_id,
            revision=result.revision,
            work_unit=work_unit_2t,
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            verification_repository=vr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )
    context = refused.value.context
    assert context is not None
    assert "precedence_tier_divergence" in str(context["reasons"]).split(",")
    assert context["finding_ids"] == finding.finding_key[:SOURCE_DISAGREEMENT_FINDING_ID_LENGTH]

    # Accepting the divergence by the id verify named answers exactly that finding; the value in use does not change.
    objects = secure_object_repository_for_active_bucket()
    resolution_repository = CreditResolutionRepositoryAdapter(objects=objects)
    issue = find_finding(result.revision, str(context["finding_ids"]))
    store_credit_resolution(
        credit_resolution_for_finding(issue, reason="Synthetic reason: the carry was checked.", at=_T4, by_session="s"),
        repository=resolution_repository,
        expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
    )
    assert Decimal(result.revision.casilla_values[FILE_FLOW_M130_CARRY_FORWARD_CASILLA]) == casilla_15
    report = file_flow_verify_revision(
        result.revision.calculation_revision_id,
        revision=result.revision,
        work_unit=work_unit_2t,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )
    assert report.granted_verificado_completo


@pytest.mark.parametrize(
    ("period_code", "prior_year", "prior_period"),
    (("1T", _PRIOR_YEAR, "4T"), ("2T", _YEAR, "1T")),
)
def test_carry_resolver_excludes_303_iva_compensation_binding(
    repos: FileFlowRepos,
    operation: PinnedAuthorityOperation,
    period_code: str,
    prior_year: int,
    prior_period: str,
) -> None:
    """D3: the previous_filing resolver does not emit the M303 IVA-compensation binding.

    A prior 303 filing whose observation carries the compensation casillas is persisted
    locally. The carry resolver's raw output DOES surface the
    ``modelo-303-compensacion-pendiente-anteriores`` binding (proven first), but
    the enrolled resolver receives the registry-declared iva-wallet-owned set as
    ``excluded_binding_ids`` so the iva-wallet decision remains the sole owner.
    """
    from ....application.aggregation.source_mesh import CalculationSourceContext
    from ....application.calculations.multi_year import PreviousFilingSourceResolver
    from ....core.period import Period

    revision_id = str(revision_serving_period("303", _YEAR, period_code).id)
    wu_repo = repos[0]
    _seed_existing_303_activity_profile(repos)
    work_unit_303 = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period_code),
        revision_id=revision_id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=BucketEventHistoryRepository()),
        clock=_T4,
        operation=operation,
    )
    _persist_prior_303(CalculationObservationRepository(), filing_year=prior_year, period_code=prior_period)

    snapshot = published_authority_operation().snapshot("303", filing_year=_YEAR, period=period_code)
    assert snapshot.revision.id == revision_id
    context = CalculationSourceContext(
        bucket_id=work_unit_303.bucket_id,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period_code),
        revision=snapshot.revision,
    )
    raw = PreviousFilingSourceResolver(
        operation=operation,
        registry_snapshot=snapshot,
        repository=CalculationObservationRepository(),
        iva_history_repository=IvaCompensationHistoryRepository(),
        profile_read_ports=empty_profile_read_ports(),
    ).resolve(context)
    assert MODELO_303_IVA_COMPENSATION_BINDING_ID in raw.binding_values, (
        "test precondition: the raw resolver must surface the 303 compensation binding "
        "so the exclusion has something to strip"
    )
    # The revision's self-referential dependency classification
    # (modelo-303-dep-self-prior-quarter, source_modelo="303") declares this carry
    # a fact to reconcile against, not a settling figure; that real, non-default
    # treatment must survive the resolver join onto the provenance trace rather
    # than default to the undeclared empty string.
    compensation_provenance = [
        item for item in raw.provenance if item.source_ref.endswith(f":{MODELO_303_IVA_COMPENSATION_BINDING_ID}")
    ]
    assert compensation_provenance, "test precondition: the compensation binding must carry a provenance row"
    assert all(item.dependency_treatment == "factual_evidence" for item in compensation_provenance)

    filtered = PreviousFilingSourceResolver(
        operation=operation,
        registry_snapshot=snapshot,
        excluded_binding_ids=iva_wallet_owned_binding_ids_for_revision(
            modelo_id=str(snapshot.modelo.id),
            revision_id=str(snapshot.revision.id),
        ),
        repository=CalculationObservationRepository(),
        iva_history_repository=IvaCompensationHistoryRepository(),
        profile_read_ports=empty_profile_read_ports(),
    ).resolve(context)
    assert MODELO_303_IVA_COMPENSATION_BINDING_ID not in filtered.binding_values
    assert all(
        not item.source_ref.endswith(f":{MODELO_303_IVA_COMPENSATION_BINDING_ID}") for item in filtered.provenance
    )
    # Every other binding the raw resolver carried survives the exclusion untouched.
    for binding_id, value in raw.binding_values.items():
        if binding_id == MODELO_303_IVA_COMPENSATION_BINDING_ID:
            continue
        assert filtered.binding_values[binding_id] == value


@pytest.mark.parametrize(
    ("period_code", "prior_year", "prior_period"),
    (("1T", _PRIOR_YEAR, "4T"), ("2T", _YEAR, "1T")),
)
def test_source_mesh_excludes_303_iva_compensation_relation_binding(
    repos: FileFlowRepos,
    operation: PinnedAuthorityOperation,
    period_code: str,
    prior_year: int,
    prior_period: str,
) -> None:
    """D3: relation-prefill must not bypass the IVA-wallet owner for M303 casilla 110."""

    revision_id = str(revision_serving_period("303", _YEAR, period_code).id)
    wu_repo = repos[0]
    _seed_existing_303_activity_profile(repos)
    work_unit_303 = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period_code),
        revision_id=revision_id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=BucketEventHistoryRepository()),
        clock=_T4,
        operation=operation,
    )
    _persist_prior_303(CalculationObservationRepository(), filing_year=prior_year, period_code=prior_period)

    snapshot = published_authority_operation().snapshot("303", filing_year=_YEAR, period=period_code)
    assert snapshot.revision.id == revision_id
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=wu_repo,
        bucket_event_repository=BucketEventHistoryRepository(),
    ) as _calculation_ports_609:
        resolution = resolve_bucket_source_mesh(
            snapshot,
            work_unit_303,
            ports=_calculation_ports_609,
            foreign_asset_observations=(),
            foreign_asset_row_observations=(),
        )

    assert MODELO_303_IVA_COMPENSATION_BINDING_ID not in resolution.binding_values
    assert "modelo-303-compensacion-pendiente-anteriores" not in resolution.relation_values
    assert all("modelo-303-compensacion-pendiente-anteriores" not in item.source_ref for item in resolution.provenance)


def test_source_resolution_keeps_reused_wallet_binding_outside_m303_coordinate() -> None:
    """The wallet carve-out is scoped to the exact M303 revision coordinate."""

    snapshot = published_authority_operation().snapshot("100", filing_year=newest_authored_edition("100"), period="0A")
    reused_binding_id = MODELO_303_IVA_COMPENSATION_BINDING_ID
    assert (
        iva_wallet_owned_binding_ids_for_revision(
            modelo_id=snapshot.modelo.id,
            revision_id=snapshot.revision.id,
        )
        == frozenset()
    )
    assert reused_binding_id not in iva_wallet_owned_binding_ids_for_revision(
        modelo_id=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
    )


def test_existing_activity_m303_1t_missing_prior_filing_blocks_wallet_zero(
    repos: FileFlowRepos,
    operation: PinnedAuthorityOperation,
) -> None:
    """An existing activity with no local 4T filing cannot invent a first-period zero."""
    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos
    _seed_existing_303_activity_profile(repos)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "1T"),
        revision_id=str(revision_serving_period("303", _YEAR, "1T").id),
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
        clock=_T1,
        operation=operation,
    )

    with (
        pytest.raises(ModeloIvaWalletReconciliationBlocked),
        calculation_ports_for_test(
            bucket_id=_BUCKET_ID,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
        ) as _calculation_ports_656,
    ):
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=_calculation_ports_656,
            clock=_T1,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit.period,
                reference="test:m303-local-cross-period-carry",
                operation=operation,
            ),
        )


def test_first_iva_period_m303_1t_uses_wallet_first_period_zero(
    repos: FileFlowRepos,
    operation: PinnedAuthorityOperation,
) -> None:
    """A true first IVA period proven by activity start may use a zero prior compensation."""
    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos
    _seed_first_303_activity_profile(repos)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "1T"),
        revision_id=str(revision_serving_period("303", _YEAR, "1T").id),
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
        clock=_T1,
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_682:
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=_calculation_ports_682,
            clock=_T1,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit.period,
                reference="test:m303-local-cross-period-carry",
                operation=operation,
            ),
        )
    revision = result.revision
    assert Decimal(revision.binding_overrides[MODELO_303_IVA_COMPENSATION_BINDING_ID]) == Decimal("0")
    assert revision.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("0")


_SEED_OPENING_BALANCE_WITH_ZERO_REFUSAL = "application.modelo.errors.iva_wallet_not_seeded"


def _local_m303_observation(
    *, filing_year: int, period_code: str, available: Decimal
) -> tuple[RegistryModeloObservation, ResultDispositionProjection]:
    """A locally filed M303 whose negative result requested compensation."""
    casilla_values, _ = modelo_303_filed_disposition(
        {_M303_COMPENSACION_DISPONIBLE_CASILLA: available},
        source_locator=f"local-filing:{filing_year}:{period_code}:declaration-type",
    )
    observation = RegistryModeloObservation(
        modelo="303",
        filing_year=filing_year,
        period=period_code,
        observations=registry_grounded_observations(
            modelo="303",
            filing_year=filing_year,
            period=period_code,
            casilla_values=casilla_values,
        ),
    )
    disposition = ResultDispositionProjection(
        disposition=ResultDisposition.COMPENSACION,
        provenance_kind="app_filing",
        provenance_locator=f"filed-revision:{filing_year}:{period_code}",
    )
    return observation, disposition


def _persist_unreadable_prior_303(period_code: str = "4T", filing_year: int = _PRIOR_YEAR) -> None:
    """Store a prior-period Modelo 303 observation the carry gate cannot interpret.

    Canonical writes refuse such a row, so it is the stored shape of a corrupted
    write: a valid local filing whose revision stamp names a design that does not
    govern its period, so this build cannot interpret it.
    """
    repository = CalculationObservationRepository()
    observation, disposition = _local_m303_observation(
        filing_year=filing_year, period_code=period_code, available=Decimal("850.00")
    )
    envelope = repository.prepare_observation_envelope(
        observation,
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=_T1,
        result_disposition=disposition,
        stamped_revision_id=revision_id_for_observation(observation),
    )
    repository.save(
        envelope.model_copy(update={"stamped_revision_id": str(revision_serving_period("303", _YEAR, "2T").id)})
    )


def test_unreadable_prior_303_observation_cannot_prove_a_first_period_zero(
    repos: FileFlowRepos,
    operation: PinnedAuthorityOperation,
) -> None:
    """A stored prior observation this build cannot read must block, never prove zero.

    The profile carries first-period activity-start evidence, so the activity-start
    proof holds and the gate would previously have produced ``first_period_zero``.
    But an observation for the prior period IS stored -- which is itself proof the
    taxpayer had a prior Modelo 303 period, the exact fact that proof asserts did
    not exist. The carry consumer cannot interpret the envelope and must surface
    that as a refusal rather than as an absence, or a taxpayer's carried credit is
    laundered into a zero on the compensación with no signal.
    """
    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos
    _seed_first_303_activity_profile(repos, activity_start_date=date(_YEAR, 1, 1).isoformat())
    _persist_unreadable_prior_303()
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "1T"),
        revision_id=str(revision_serving_period("303", _YEAR, "1T").id),
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
        clock=_T1,
        operation=operation,
    )

    with (
        pytest.raises(ModeloIvaWalletReconciliationBlocked) as blocked,
        calculation_ports_for_test(
            bucket_id=_BUCKET_ID,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
        ) as _calculation_ports_764,
    ):
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=_calculation_ports_764,
            clock=_T1,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit.period,
                reference="test:m303-local-cross-period-carry",
                operation=operation,
            ),
        )

    surfaced_key = blocked.value.translated_message
    assert surfaced_key is not None, "the refusal reached the operator with no locale key at all"
    assert surfaced_key != _SEED_OPENING_BALANCE_WITH_ZERO_REFUSAL, (
        "a taxpayer whose stored prior-period evidence could not be read was told to seed the "
        "opening balance with zero and confirm it, which reconstructs by hand the under-declaration "
        "that blocking this case exists to prevent, and stamps it as an operator decision. "
        f"Surfaced refusal: {surfaced_key}"
    )


def _persist_prior_303(
    repository: CalculationObservationRepository, *, filing_year: int = _YEAR, period_code: str = "1T"
) -> None:
    """Persist a prior-period 303 observation carrying the compensation carry casilla.

    Stored under the requested prior period so the snapshot's previous_filing
    compensation binding (``source_casilla_id = iva.compensacion-disponible-fin-periodo``,
    offset -1) discovers it and the raw resolver emits the
    ``modelo-303-compensacion-pendiente-anteriores`` binding the D3 exclusion strips.
    """
    observation, disposition = _local_m303_observation(
        filing_year=filing_year, period_code=period_code, available=Decimal("1200.00")
    )
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T1,
            result_disposition=disposition,
            stamped_revision_id=revision_id_for_observation(observation),
        )
    )


def test_first_filer_same_year_chain_is_fully_reachable(
    repos: FileFlowRepos,
    operation: PinnedAuthorityOperation,
) -> None:
    """Reachability proof: with first-year activity-start, the M130 2T verdict is fully clean.

    Adversarial check of the end-to-end reachability claim. The M130 minoración binding
    (``irpf.previous_year_economic_activity_net_income``, source_modelo 100,
    filing_year_delta -1) creates a CROSS-YEAR M100 prior-year dependency that same-year
    admission deliberately does NOT relax. For a first-year autónomo (activity-start in the filing
    year) that cross-year M100 dep is strictly pre-activity, so the first-filer suppression
    scopes it out; the same-year 1T dep is admitted under same-year scope. Both handled => the
    verdict is clean => the quarter is reachable to verify/export. If suppression did NOT
    cover the previous_filing M100 dep, this verdict would be unclean (a real gap).
    """
    from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
    from ....application.modelo.verification_cross_period import cross_period_clean_state_verdict_for_work_unit

    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos
    _seed_first_year_activity_profile(repos)
    _file_1t_with_negative_result(repos, operation=operation)
    _seed_2t_130_income(repos)
    work_unit_2t = _seed_130(repos, period="2T", clock=_T4, operation=operation)
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_847:
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit_2t.work_unit_id,
            casilla_inputs=_2T_INPUTS_WITHOUT_15,
            binding_values=FILE_FLOW_DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_847,
            clock=_T4,
        )

    verdict = cross_period_clean_state_verdict_for_work_unit(
        work_unit_2t,
        observation_repository=CalculationObservationRepository(),
        filing_repository=ModeloRecordCatalogueRepository(objects=bv_repo.secure_object_repository),
        calculation_repository=cr_repo,
        verification_repository=VerificationReportCatalogueRepository(objects=bv_repo.secure_object_repository),
        justificante_repository=JustificanteRepository(objects=bv_repo.secure_object_repository),
        activity_start_date=date(_YEAR, 1, 1),
    )
    assert verdict is not None
    # The cross-year M100 prior-year minoración dep is suppressed (pre-activity).
    cross_year = [d for d in verdict.dependencies if d.requirement.filing_year != _YEAR]
    assert cross_year, "expected the cross-year M100 prior-year minoración dependency"
    assert all(d.suppressed_pre_activity for d in cross_year)
    # The same-year M130 same-year dep is admitted with the disclosing advisory.
    same_year = [
        d for d in verdict.dependencies if d.requirement.source_modelo == "130" and d.requirement.filing_year == _YEAR
    ]
    assert same_year and all(d.non_official_local_chain_advisory for d in same_year)
    # Both handled -> the verdict is clean -> the quarter is reachable.
    assert verdict.clean
