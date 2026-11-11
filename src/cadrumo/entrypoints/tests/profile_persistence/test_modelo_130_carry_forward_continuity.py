"""E2E continuity: Modelo 130 prior-quarter negative-result carry-forward.

The autónomo's full-year experience spans four quarterly Modelo 130
pago-fraccionado filings. RD 439/2007 art. 110 and the AEAT M130
instructions define a cross-quarter carry-forward: when a quarter's
liquidation result (casilla 19) is negative, its absolute value flows
into the *next* quarter's casilla 15 ("Resultados negativos de
trimestres anteriores") and is subtracted there. Casilla 15 is bound
via ``source = "previous_filing"`` (binding
``modelo-130-resultados-negativos-anteriores``), an ``op=copy`` of the
prior quarter's ``saldo-negativo-fin-periodo``.

The 303->390 annual reconciliation carry-forward is covered by
``test_binding_prefill``; the M130 quarter-to-quarter carry-forward —
the autónomo's most common continuity path — had no end-to-end coverage.
This module closes that gap.

The test drives the real continuity contract with real adapters (real
encrypted SQLite repos, the real registry authority, the real
``previous_filing`` resolver — no mocks): it computes a loss-making Q1,
records it as a prior-period observation, and asserts that Q2's
casilla 15 auto-resolves to Q1's carried saldo with no manual re-entry.

Grounding (non-tautological): the Q1 saldo is _produced by the engine
from the loss scenario, not hand-computed; the assertion is the
*wiring* invariant — Q2's casilla 15 equals Q1's persisted
``saldo-negativo-fin-periodo`` — which the AEAT instruction defines as
the prior-quarter negative result carried forward "sin signo".
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.justificante_metadata import persist_justificante_metadata
from ....adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    open_test_profile_session,
    seed_test_profile_record,
)
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.calculations.binding_prefill import resolve_bindings_from_local_store
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.calculation_note_gate import blocking_calculation_issues
from ....application.modelo.export import export_modelo_revision
from ....application.modelo.export_contracts import ModeloExportCommand
from ....application.modelo.external_import_actions import import_external_filing_evidence
from ....application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.tests.published_authority import leased_profile_create_context
from ....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_modelo_observation,
    revision_id_for_coordinates,
)
from ....domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.invoices.tests.catalogue_support import build_invoice_catalogue
from ....domain.iva.schema import InvoiceKind, IvaCategory
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.filing_record import ExternalEvidenceKind
from ....domain.modelos.verification_report import VerificationCompletenessStatus
from ....domain.transactions.enums import (
    BusinessClassification,
    TransactionDirection,
    TransactionLifecycleState,
)
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.transactions.service import link_invoice
from ....domain.user_profile.tests.imputation_criterion_facts import cash_criterion_facts
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ....tests.env_scope import ready_clave_settings
from ...adapter_composition_work_ports import build_calculation_action_ports
from .file_flow_test_support import seed_m130_activity
from .observation_seeding_support import save_stamped_observation
from .verification_substance_support import general_iva_workflow_profile

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]


def _calculate_modelo_revision(work_unit_id: str, **kwargs: Any) -> Any:
    repository = kwargs.pop("work_unit_repository", None)
    for key in ("calculation_repository", "bucket_event_repository"):
        kwargs.pop(key, None)
    with bundled_indexed_authority().operation() as operation:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit_id,
            ports=build_calculation_action_ports(bucket_id=repository.bucket_id, operation=operation),
            **kwargs,
        ).revision


def _verify_modelo_revision(calculation_revision_id: str, **kwargs: Any) -> Any:
    for key in (
        "work_unit_repository",
        "calculation_repository",
        "filing_repository",
        "verification_repository",
        "bucket_event_repository",
    ):
        kwargs.pop(key, None)
    with bundled_indexed_authority().operation() as operation:
        kwargs.setdefault("certificate_secret_backend_factory", build_test_certificate_secret_backend_factory())
        kwargs.setdefault("verification_repositories", build_test_verification_repository_bundle())
        return verify_modelo_revision_with_preconditions(calculation_revision_id, operation=operation, **kwargs).report


def _import_external_filing_evidence(**kwargs: Any) -> Any:
    kwargs.setdefault("observation_repository", CalculationObservationRepository())
    return import_external_filing_evidence(**kwargs)


def _resolve_bindings_from_local_store(snapshot: Any, **kwargs: Any) -> Any:
    with bundled_indexed_authority().operation() as operation:
        return resolve_bindings_from_local_store(snapshot, operation=operation, **kwargs)


_Repos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    BucketEventHistoryRepository,
    CalculationObservationRepository,
    VerificationReportCatalogueRepository,
    ModeloRecordCatalogueRepository,
]

_CLOCK = datetime(2026, 7, 15, 9, 0, 0, tzinfo=UTC)
_PROFILE_ID = "13013013-0130-4130-8130-130130130130"
_BUCKET_ID = _PROFILE_ID

_CARRY_FORWARD_BINDING: BindingId = "modelo-130-resultados-negativos-anteriores"
_PREV_YEAR_BINDING: BindingId = "irpf.previous_year_economic_activity_net_income"
_PRIOR_YEAR_NET_INCOME = Decimal("5000")


_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02")
_M130_PREVIOUS_PAYMENTS_CASILLA: CasillaId = validated_casilla_id("05")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06")
_M130_PAGO_FRACCIONADO_CASILLA: CasillaId = validated_casilla_id("07")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10")
_M130_DIFERENCIA_PREVIA_CASILLA: CasillaId = validated_casilla_id("14")
_M130_CARRY_FORWARD_CASILLA: CasillaId = validated_casilla_id("15")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16")
_M130_DIFERENCIA_CASILLA: CasillaId = validated_casilla_id("17")
_M130_PRIOR_RETURN_RESULT_CASILLA: CasillaId = validated_casilla_id("18")
_M130_SALDO_NEGATIVO_CASILLA: CasillaId = validated_casilla_id("saldo-negativo-fin-periodo")
_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: CasillaId = validated_casilla_id("0224")
_M100_RENDIMIENTO_SOURCE_1479_CASILLA: CasillaId = validated_casilla_id("1479")
_M100_RENDIMIENTO_SOURCE_1553_CASILLA: CasillaId = validated_casilla_id("1553")
_M100_RENDIMIENTO_SOURCE_1577_CASILLA: CasillaId = validated_casilla_id("1577")

# Loss-making Q1 scenario, derived by hand from RD 439/2007 art. 110:
#   ledger ingresos 3000, gastos 3000 -> rendimiento neto 0
#   casilla 04 = 20% * 0 = 0 (art. 110.1.a) -> casilla 07 = 0 -> casilla 12 = 0
#   prior-year net income 5000 (<= 9000) -> minoración casilla 13 = 100 (art. 110.3.c)
#   casilla 14 = 0 - 100 = -100 -> casilla 17 = -100 -> casilla 19 = -100
#   saldo-negativo-fin-periodo = max(0, -(-100)) = 100  <-- carried into Q2
# Casillas 01, 02 and 06 are the year-to-date ledger totals, so the activity is
# recorded as ledger rows rather than entered.
_Q1_INCOME = Decimal("3000")
_Q1_EXPENSE = Decimal("3000")
_Q1_INPUTS: dict[CasillaId, Decimal] = {
    _M130_PREVIOUS_PAYMENTS_CASILLA: Decimal("0"),
    _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
    _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
}
_Q1_BINDINGS: dict[BindingId, Decimal] = {
    _PREV_YEAR_BINDING: _PRIOR_YEAR_NET_INCOME,
    _CARRY_FORWARD_BINDING: Decimal("0"),  # Q1 has no prior quarter.
}
_EXPECTED_Q1_SALDO = Decimal("100.00")

_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = persona_facts_beneath(
    (
        UserProfileFact(path="identity.tax_id", value="00000000T"),
        UserProfileFact(path="identity.name", value="Sofia"),
        UserProfileFact(path="identity.surnames", value="Operator"),
        UserProfileFact(path="activities.description", value="professional services"),
        UserProfileFact(path="iva.oss_enrolled", value=False),
        UserProfileFact(path="censo.activity_start_date", value=date(2025, 1, 1)),
        # The regime holds in every ejercicio, the prior year's net income included; the dated cash election
        # below states the same regime for 2026 only.
        UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
        # The operator declares the cobros y pagos criterion for the quarters this module calculates,
        # under the normal modality: the expected carry assumes no art. 30.2.4.a provision in box 02.
        *cash_criterion_facts(2026, estimation_regime="directa_normal"),
    )
)


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    """Real encrypted SQLite repos over an isolated profile — no mocks."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        _seed_ready_profile(profile_id=_PROFILE_ID)
        yield (
            WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
            CalculationRevisionCatalogueRepository(objects=objects),
            BucketEventHistoryRepository(objects=objects),
            CalculationObservationRepository(objects=objects),
            VerificationReportCatalogueRepository(objects=objects),
            ModeloRecordCatalogueRepository(objects=objects),
        )


def _seed_ready_profile(*, profile_id: str) -> None:
    seed_test_profile_record(
        create_user_profile_record(
            context=leased_profile_create_context(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=profile_id,
            facts=_READY_PROFILE_FACTS,
            created_at=_CLOCK,
            updated_at=_CLOCK,
        ),
    )


def _calculate_quarter(
    repos: _Repos,
    *,
    period: str,
    casilla_inputs: Mapping[CasillaId, Decimal],
    binding_values: Mapping[BindingId, Decimal],
    operation: PinnedAuthorityOperation,
    income: Decimal = Decimal("0"),
    expense: Decimal = Decimal("0"),
) -> CalculationRevision:
    """Calculate one 2026 quarter over a ledger whose year-to-date activity reads ``income`` and ``expense``."""
    wu_repo, cr_repo, bv_repo, _obs_repo, _vr_repo, _filing_repo = repos
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, period),
        revision_id="2019-y-siguientes",
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
        clock=_CLOCK,
        operation=operation,
    )
    seed_m130_activity(work_unit, income=income, expense=expense)
    revision = _calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values=binding_values,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_CLOCK,
    )
    assert isinstance(revision, CalculationRevision)
    return revision


def _observation_from_revision(revision: CalculationRevision, *, period: str) -> RegistryModeloObservation:
    if not revision.observations:
        raise AssertionError("calculation revision must carry typed CasillaObservation provenance")
    return RegistryModeloObservation(
        modelo="130",
        filing_year=2026,
        period=period,
        observations=revision.observations,
    )


def _import_official_filing_evidence(
    repos: _Repos,
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_values: Mapping[CasillaId, Decimal],
    operation: PinnedAuthorityOperation,
) -> tuple[str, dict[str, str]]:
    wu_repo, cr_repo, bv_repo, _obs_repo, _vr_repo, filing_repo = repos
    source_snapshot = published_authority_operation().snapshot(modelo, filing_year=filing_year, period=period)
    source_work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        revision_id=source_snapshot.revision.id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
        clock=_CLOCK,
        operation=operation,
    )
    evidence_reference_id = f"JUST{modelo}{filing_year}{period}"
    persist_justificante_metadata(
        evidence_reference_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        captured_at=_CLOCK,
    )
    _import_external_filing_evidence(
        work_unit_id=source_work_unit.work_unit_id,
        casilla_values=casilla_values,
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id=evidence_reference_id,
        actor="aeat-import-test",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=filing_repo,
        bucket_event_repository=bv_repo,
        expected_tax_id="X0001500M",
        clock=_CLOCK,
    )
    return source_snapshot.revision.id, {
        "aeat_register_status": "ALTA",
        "aeat_expediente_id": f"EXP-{modelo}-{filing_year}-{period}",
        "aeat_justificante_csv": evidence_reference_id,
        "authenticated_identity": "X0001500M",
    }


def _seed_prior_year_m100(
    obs_repo: CalculationObservationRepository,
    *,
    net_income: Decimal = _PRIOR_YEAR_NET_INCOME,
    source_kind: str = "app_filing",
    stamped_revision_id: str,
    source_metadata: Mapping[str, str] | None = None,
) -> None:
    """Record the prior-year annual Renta (M100 2025) net-income observation.

    M130's casilla-13 minoración reads ``irpf.previous_year_economic_activity_net_income``
    — a ``previous_filing`` binding summing M100 casillas 0224/1479/1553/1577 of
    the prior ejercicio. The quarterly pipeline therefore depends on the prior
    annual filing being observed; seeding it here exercises the full continuity
    (prior-year Renta + prior-quarter 130 both feeding the current quarter).
    """
    # The binding sums whichever of M100 casillas 0224/1479/1553/1577 apply.
    # This full-filing scenario records net income in 0224 and explicit zeros
    # for its non-applicable rendimiento sources.
    obs_repo.save(
        obs_repo.prepare_observation_envelope(
            registry_grounded_modelo_observation(
                modelo="100",
                filing_year=2025,
                period="0A",
                casilla_values={
                    _M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: net_income,
                    _M100_RENDIMIENTO_SOURCE_1479_CASILLA: Decimal("0"),
                    _M100_RENDIMIENTO_SOURCE_1553_CASILLA: Decimal("0"),
                    _M100_RENDIMIENTO_SOURCE_1577_CASILLA: Decimal("0"),
                },
            ),
            source_kind=source_kind,
            captured_at=_CLOCK,
            stamped_revision_id=stamped_revision_id,
            source_metadata=source_metadata,
        )
    )


def test_q1_loss_produces_carry_forward_saldo(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    """A loss-making Q1 produces a positive ``saldo-negativo-fin-periodo``.

    This is the seed the next quarter carries forward. The value is
    _produced by the engine from the loss scenario (retenciones exceed the
    20% pago fraccionado, with a minoración that cannot be absorbed),
    never hand-computed against the formula under test.
    """
    revision = _calculate_quarter(
        repos,
        period="1T",
        casilla_inputs=_Q1_INPUTS,
        binding_values=_Q1_BINDINGS,
        operation=operation,
        income=_Q1_INCOME,
        expense=_Q1_EXPENSE,
    )
    assert Decimal(revision.casilla_values[_M130_DIFERENCIA_CASILLA]) == Decimal("-100.00")
    assert Decimal(revision.casilla_values[_M130_SALDO_NEGATIVO_CASILLA]) == _EXPECTED_Q1_SALDO


def test_q2_casilla_15_auto_resolves_from_prior_quarter_filing(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """Q2's carry-forward binding auto-resolves to Q1's persisted saldo.

    The cross-period continuity contract: once Q1 is recorded as a
    prior-period observation, the ``previous_filing`` resolver populates
    Q2's casilla-15 binding with Q1's ``saldo-negativo-fin-periodo`` —
    the operator does not re-key the prior-quarter loss by hand.
    """
    _wu_repo, _cr_repo, _bv_repo, obs_repo, _vr_repo, _filing_repo = repos
    q1 = _calculate_quarter(
        repos,
        period="1T",
        casilla_inputs=_Q1_INPUTS,
        binding_values=_Q1_BINDINGS,
        operation=operation,
        income=_Q1_INCOME,
        expense=_Q1_EXPENSE,
    )
    save_stamped_observation(
        obs_repo, _observation_from_revision(q1, period="1T"), source_kind="app_filing", captured_at=_CLOCK
    )
    _seed_prior_year_m100(
        obs_repo,
        stamped_revision_id=revision_id_for_coordinates(modelo="100", filing_year=2025, period="0A"),
    )

    q2_snapshot = published_authority_operation().snapshot("130", filing_year=2026, period="2T")
    report = _resolve_bindings_from_local_store(
        q2_snapshot, repository=obs_repo, iva_history_repository=IvaCompensationHistoryRepository()
    )

    # Both M130 previous_filing bindings auto-resolve from the local store:
    # the prior-quarter carry-forward and the prior-year Renta net income.
    assert report.binding_values.get(_CARRY_FORWARD_BINDING) == _EXPECTED_Q1_SALDO
    assert report.binding_values.get(_PREV_YEAR_BINDING) == _PRIOR_YEAR_NET_INCOME


def test_q2_carry_forward_flows_into_casilla_15_value(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    """The resolved carry-forward lands in Q2's casilla 15 through a real calculate.

    End-to-end: Q1 recorded -> Q2 prefill -> Q2 calculate with the
    resolved binding (no manual casilla-15 entry). Casilla 15 must equal
    Q1's saldo (100), confirming the loss propagates to the next quarter
    exactly as the AEAT instruction prescribes ("importe sin signo de los
    resultados negativos de trimestres anteriores").
    """
    _wu_repo, _cr_repo, _bv_repo, obs_repo, _vr_repo, _filing_repo = repos
    q1 = _calculate_quarter(
        repos,
        period="1T",
        casilla_inputs=_Q1_INPUTS,
        binding_values=_Q1_BINDINGS,
        operation=operation,
        income=_Q1_INCOME,
        expense=_Q1_EXPENSE,
    )
    save_stamped_observation(
        obs_repo, _observation_from_revision(q1, period="1T"), source_kind="app_filing", captured_at=_CLOCK
    )
    _seed_prior_year_m100(
        obs_repo,
        stamped_revision_id=revision_id_for_coordinates(modelo="100", filing_year=2025, period="0A"),
    )

    # Q2 cumulative (Jan-Jun): ingresos 8000, gastos 3000 -> rendimiento 5000,
    # casilla 04 = 1000, casilla 14 = 1000 - 100 = 900, which leaves room for the
    # whole Q1 saldo. The calculation resolves the carry-forward casilla 15, the
    # prior payments and the prior-year net income from the local store itself;
    # nothing is re-keyed by hand.
    q2 = _calculate_quarter(
        repos,
        period="2T",
        casilla_inputs={
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
        },
        binding_values={},
        operation=operation,
        income=Decimal("8000"),
        expense=Decimal("3000"),
    )
    assert Decimal(q2.casilla_values[_M130_CARRY_FORWARD_CASILLA]) == _EXPECTED_Q1_SALDO


# Sofia's quarters, hand-derived from the M130 formulas (RD 439/2007 art. 110):
#   Q1: one invoice, base 1000,00 with 210,00 IVA, states a 162,00 retención, so
#       1000,00 + 210,00 - 162,00 = 1048,00 is banked. Casilla 04 = 20 % * 1000 = 200,
#       casilla 07 = 200 - 162 = 38, prior-year net income 5000 gives a minoración of
#       100, so casilla 14 = 38 - 100 = -62 and the saldo carried into Q2 is 62.
#   Q2: a further 187,00 receipt with nothing withheld makes the year-to-date income
#       1187,00. Casilla 04 = 237,40, casilla 05 = Q1's 38 and casilla 06 = 162, so
#       casilla 07 = 37,40; the prior-year net income now read from the filed M100 is
#       20000, so no minoración, and casilla 14 = 37,40. Casilla 15 takes the carry
#       capped at that positive 37,40, leaving casilla 17 at 0.
_SOFIA_Q1_BASE = Decimal("1000.00")
_SOFIA_Q1_IVA = Decimal("210.00")
_SOFIA_Q1_RETENCION = Decimal("162.00")
_SOFIA_Q2_UNWITHHELD_INCOME = Decimal("187.00")


def _seed_sofia_q1_invoiced_receipt() -> None:
    """Book Q1's receipt with its linked issued invoice, which states the retención."""
    with bundled_indexed_authority().operation():
        rate = iva_rate_percentage(IvaRate.from_registry("RATE_21"), date(2026, 1, 1))
        assert rate is not None
        receipt = Transaction.model_validate(
            {
                "raw": RawTransaction(
                    provider_transaction_id="sofia-q1-cobro",
                    booked_date=date(2026, 2, 10),
                    value_date=date(2026, 2, 10),
                    amount=_SOFIA_Q1_BASE + _SOFIA_Q1_IVA - _SOFIA_Q1_RETENCION,
                    currency="EUR",
                    counterparty="Cliente SL",
                    description="cobro factura",
                    provenance=RawProvenance(
                        source_path=Path(__file__),
                        source_sha256="d" * 64,
                        source_row_index=1,
                        source_format=SourceFormat.CSV,
                        ingested_at=_CLOCK,
                        provider_name="CSV provider",
                    ),
                    raw_fields={},
                ),
                "direction": TransactionDirection.INCOMING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "irpf_category": "actividad_economica",
                "taxable_base": None,
                "iva_rate": None,
                "iva_amount": None,
                "lifecycle_state": TransactionLifecycleState.ACTIVE,
                "classified_at": _CLOCK,
                "classified_by": "manual",
            },
        )
        line = InvoiceLine(
            description="Servicios profesionales",
            quantity=Decimal("1"),
            unit_price=_SOFIA_Q1_BASE,
            subtotal=_SOFIA_Q1_BASE,
            iva_rate=IvaRate.from_registry("RATE_21"),
            iva_amount=_SOFIA_Q1_BASE * rate,
        )
        assert line.iva_amount == _SOFIA_Q1_IVA
        invoice = Invoice.model_validate(
            {
                "kind": InvoiceKind.ISSUED,
                "invoice_number": "F-2026-S01",
                "issued_at": date(2026, 2, 10),
                "counterparty_name": "Cliente SL",
                "counterparty_tax_id": "B00015016",
                "counterparty_country": "ES",
                "bucket_id": _BUCKET_ID,
                "base_total": _SOFIA_Q1_BASE,
                "iva_total": _SOFIA_Q1_IVA,
                "grand_total": _SOFIA_Q1_BASE + _SOFIA_Q1_IVA,
                "currency": "EUR",
                "lines": (line,),
                "payment_status": PaymentStatus.PAID,
                "iva_category": IvaCategory("domestic_general"),
                "retention_amount": _SOFIA_Q1_RETENCION,
                "linked_transaction_ids": (receipt.transaction_id,),
            },
        )
        with open_test_profile_session(_BUCKET_ID):
            catalogue = link_invoice(
                TransactionCatalogue.from_transactions((receipt,)), receipt.transaction_id, invoice.invoice_id
            )
            TransactionCatalogueRepository(bucket_id=_BUCKET_ID).save(catalogue)
            InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).save(build_invoice_catalogue((invoice,)))


def test_sofia_q2_carry_forward_caps_to_positive_c14_and_verifies(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """Q1's carried saldo is capped at Q2's positive casilla 14, leaving casilla 17 at zero.

    The declared cobros y pagos criterion grounds boxes 01, 02 and the 162,00 activity
    withholding Q1 carries in box 06, so Q2 verifies complete.
    """
    _wu_repo, _cr_repo, _bv_repo, obs_repo, _vr_repo, _filing_repo = repos
    _seed_sofia_q1_invoiced_receipt()
    q1 = _calculate_quarter(
        repos,
        period="1T",
        casilla_inputs=_Q1_INPUTS,
        binding_values=_Q1_BINDINGS,
        operation=operation,
    )
    assert Decimal(q1.casilla_values[_M130_RETENCIONES_CASILLA]) == _SOFIA_Q1_RETENCION
    assert Decimal(q1.casilla_values[_M130_SALDO_NEGATIVO_CASILLA]) == Decimal("62.00")
    q1_revision_stamp, q1_source_metadata = _import_official_filing_evidence(
        repos,
        modelo="130",
        filing_year=2026,
        period="1T",
        casilla_values=q1.casilla_values,
        operation=operation,
    )
    obs_repo.save(
        obs_repo.prepare_observation_envelope(
            _observation_from_revision(q1, period="1T"),
            source_kind="aeat_sede_justificante",
            captured_at=_CLOCK,
            stamped_revision_id=q1_revision_stamp,
            source_metadata=q1_source_metadata,
        )
    )
    m100_values = {
        _M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: Decimal("20000"),
        _M100_RENDIMIENTO_SOURCE_1479_CASILLA: Decimal("0"),
        _M100_RENDIMIENTO_SOURCE_1553_CASILLA: Decimal("0"),
        _M100_RENDIMIENTO_SOURCE_1577_CASILLA: Decimal("0"),
    }
    m100_revision_stamp, m100_source_metadata = _import_official_filing_evidence(
        repos,
        modelo="100",
        filing_year=2025,
        period="0A",
        casilla_values=m100_values,
        operation=operation,
    )
    _seed_prior_year_m100(
        obs_repo,
        net_income=Decimal("20000"),
        source_kind="aeat_sede_justificante",
        stamped_revision_id=m100_revision_stamp,
        source_metadata=m100_source_metadata,
    )

    q2_snapshot = published_authority_operation().snapshot("130", filing_year=2026, period="2T")
    resolved = _resolve_bindings_from_local_store(
        q2_snapshot, repository=obs_repo, iva_history_repository=IvaCompensationHistoryRepository()
    ).binding_values
    assert resolved.get(_CARRY_FORWARD_BINDING) == Decimal("62.00")
    assert resolved.get(_PREV_YEAR_BINDING) == Decimal("20000")

    q2 = _calculate_quarter(
        repos,
        period="2T",
        casilla_inputs={
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
        },
        binding_values={},
        operation=operation,
        income=_SOFIA_Q2_UNWITHHELD_INCOME,
    )

    assert Decimal(q2.casilla_values[_M130_INGRESOS_CASILLA]) == _SOFIA_Q1_BASE + _SOFIA_Q2_UNWITHHELD_INCOME
    assert Decimal(q2.casilla_values[_M130_RETENCIONES_CASILLA]) == _SOFIA_Q1_RETENCION
    assert Decimal(q2.casilla_values[_M130_DIFERENCIA_PREVIA_CASILLA]) == Decimal("37.40")
    assert Decimal(q2.casilla_values[_M130_CARRY_FORWARD_CASILLA]) == Decimal("37.40")
    assert Decimal(q2.casilla_values[_M130_DIFERENCIA_CASILLA]) == Decimal("0.00")

    report = _verify_modelo_revision(
        q2.calculation_revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        verification_repositories=build_test_verification_repository_bundle(),
        actor="operator-test",
        workflow_profile=general_iva_workflow_profile(),
        settings=ready_clave_settings("X0001500M"),
        clock=_CLOCK,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    assert report.completeness_status is VerificationCompletenessStatus.COMPLETE, report


def _seed_sofia_prior_year(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    """Record the 2025 Renta from its official evidence, with the prior-year activity net income Q1 reads."""
    obs_repo = repos[3]
    m100_values = {
        _M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: _PRIOR_YEAR_NET_INCOME,
        _M100_RENDIMIENTO_SOURCE_1479_CASILLA: Decimal("0"),
        _M100_RENDIMIENTO_SOURCE_1553_CASILLA: Decimal("0"),
        _M100_RENDIMIENTO_SOURCE_1577_CASILLA: Decimal("0"),
    }
    stamp, metadata = _import_official_filing_evidence(
        repos, modelo="100", filing_year=2025, period="0A", casilla_values=m100_values, operation=operation
    )
    _seed_prior_year_m100(
        obs_repo,
        net_income=_PRIOR_YEAR_NET_INCOME,
        source_kind="aeat_sede_justificante",
        stamped_revision_id=stamp,
        source_metadata=metadata,
    )


def test_sofia_q1_with_activity_withholding_verifies_complete_and_exports(
    repos: _Repos, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """1.000,00 of activity income with 162,00 withheld: box 06 credits it, and the quarter verifies and exports.

    The 62,00 saldo is the Q1 figure the Q2 continuity case above already states.
    """
    _seed_sofia_q1_invoiced_receipt()
    _seed_sofia_prior_year(repos, operation=operation)
    q1 = _calculate_quarter(
        repos,
        period="1T",
        casilla_inputs=_Q1_INPUTS,
        binding_values={_CARRY_FORWARD_BINDING: Decimal("0")},
        operation=operation,
    )
    assert Decimal(q1.casilla_values[_M130_RETENCIONES_CASILLA]) == _SOFIA_Q1_RETENCION
    assert Decimal(q1.casilla_values[_M130_SALDO_NEGATIVO_CASILLA]) == Decimal("62.00")
    assert not blocking_calculation_issues(q1), q1.source_issues

    report = _verify_modelo_revision(
        q1.calculation_revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        verification_repositories=build_test_verification_repository_bundle(),
        actor="operator-test",
        workflow_profile=general_iva_workflow_profile(),
        settings=ready_clave_settings("X0001500M"),
        clock=_CLOCK,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    assert report.completeness_status is VerificationCompletenessStatus.COMPLETE, report

    output = tmp_path / "modelo-130-1T.txt"
    export_modelo_revision(
        ModeloExportCommand(calculation_revision_id=q1.calculation_revision_id, output_path=output, actor="operator"),
        workflow_profile=general_iva_workflow_profile(),
        export_ports=modelo_export_ports_for_test(bucket_id=_BUCKET_ID),
        clock=_CLOCK,
        operation=operation,
    )
    assert output.read_bytes()


# Shared parity-fixture inputs (named so the expected casilla-05 identity is
# derived from the same constants the fixture seeds, never a hand-summed literal).
_PRIOR_07_1T = Decimal("500")
_PRIOR_16_1T = Decimal("60")
_PRIOR_07_2T = Decimal("300")
_PRIOR_16_2T = Decimal("40")
_PRIOR_2T_SALDO = Decimal("150")


def test_casilla_15_copy_and_casilla_05_sum_carries_resolve_on_shared_fixture(repos: _Repos) -> None:
    """Parity: the casilla-15 op=copy carry and the casilla-05 op=sum carry coexist.

    The casilla-15 single-offset op=copy carry (binding
    ``modelo-130-resultados-negativos-anteriores``) and the casilla-05
    expanding-span op=sum carry (binding ``modelo-130-pagos-fraccionados-anteriores``)
    both resolve from the same multi-quarter local store on a 3T target, proving the
    expanding-span selector extension does not regress the single-offset carry
    (the modelo-130-relation-regression guarantee).

    Shared fixture (prior 1T/2T observations, engine-independent for this wiring gate):
      1T: casilla 07 = +500 (a real pago fraccionado), casilla 16 = 60, casilla 19 = 0
      2T: casilla 07 = +300, casilla 16 = 40, casilla 19 = -150 (a loss carried to 3T)

    At 3T:
      casilla-15 = the earlier negative casilla 19 none of them has deducted = 150
      casilla-05 (op=sum, expanding span {1T, 2T}) = Σ max(0, 07) − Σ 16,
                computed in-test from the seeded fixture inputs (not a hand-summed literal).
    """
    _wu_repo, _cr_repo, _bv_repo, obs_repo, _vr_repo, _filing_repo = repos
    _seed_prior_year_m100(
        obs_repo,
        stamped_revision_id=revision_id_for_coordinates(modelo="100", filing_year=2025, period="0A"),
    )

    save_stamped_observation(
        obs_repo,
        registry_grounded_modelo_observation(
            modelo="130",
            filing_year=2026,
            period="1T",
            casilla_values={
                _M130_PAGO_FRACCIONADO_CASILLA: _PRIOR_07_1T,
                _M130_HOME_DEDUCTION_CASILLA: _PRIOR_16_1T,
                validated_casilla_id("19"): Decimal("0"),
            },
        ),
        source_kind="app_filing",
        captured_at=_CLOCK,
    )
    save_stamped_observation(
        obs_repo,
        registry_grounded_modelo_observation(
            modelo="130",
            filing_year=2026,
            period="2T",
            casilla_values={
                _M130_PAGO_FRACCIONADO_CASILLA: _PRIOR_07_2T,
                _M130_HOME_DEDUCTION_CASILLA: _PRIOR_16_2T,
                validated_casilla_id("19"): -_PRIOR_2T_SALDO,
            },
        ),
        source_kind="app_filing",
        captured_at=_CLOCK,
    )

    snapshot_3t = published_authority_operation().snapshot("130", filing_year=2026, period="3T")
    resolved = _resolve_bindings_from_local_store(
        snapshot_3t, repository=obs_repo, iva_history_repository=IvaCompensationHistoryRepository()
    ).binding_values

    # Independent identity (a different code path than the span binding): the
    # positive part of each prior 07 minus each prior 16, computed here from the
    # seeded fixture inputs rather than asserted against a hand-summed literal.
    expected_casilla_05 = (max(Decimal("0"), _PRIOR_07_1T) + max(Decimal("0"), _PRIOR_07_2T)) - (
        _PRIOR_16_1T + _PRIOR_16_2T
    )
    assert resolved.get("modelo-130-pagos-fraccionados-anteriores") == expected_casilla_05
    # The carry folds both quarters' casilla 19 and 15.
    assert resolved.get(_CARRY_FORWARD_BINDING) == _PRIOR_2T_SALDO
