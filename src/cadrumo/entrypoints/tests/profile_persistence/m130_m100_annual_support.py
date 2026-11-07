"""Shared fixtures for the ledger-to-Modelo-130-to-Modelo-100 annual-return tests.

One synthetic autonomo filer: identity constants, the thin wrappers that run the real
calculate, verify and export actions on a test store, and the seeded prior filings the
annual return reads.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.justificante_metadata import persist_justificante_metadata
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.aggregation.source_precedence import CallerOverrideDisposition, precedence_ladder_sources
from cadrumo.application.modelo.calculation_bucket_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.export import export_modelo_revision
from cadrumo.application.modelo.external_import_actions import import_external_filing_evidence
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.tests.registry_observations import (
    registry_grounded_observations,
)
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.contribuyente.entity_type import EntityType
from cadrumo.domain.deadlines.models import IrpfEstimationRegime, IrpfIncomeCategory, IVARegime, TaxpayerProfile
from cadrumo.domain.modelos.filing_record import ExternalEvidenceKind
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.models import Transaction
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from cadrumo.entrypoints.adapter_composition_work_ports import build_calculation_action_ports

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from .observation_seeding_support import save_stamped_observation
from .verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

OPERATOR_SCOPE_PORTS = build_operator_scope_ports()


def calculate_revision_from_bucket_aggregation(
    work_unit_id: str,
    **kwargs: Any,
) -> BucketAggregationCalculationResult:
    repository = kwargs.pop("work_unit_repository", None)
    for key in ("calculation_repository", "transaction_repository", "invoice_repository", "bucket_event_repository"):
        kwargs.pop(key, None)
    with bundled_indexed_authority().operation() as operation:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit_id,
            ports=build_calculation_action_ports(bucket_id=repository.bucket_id, operation=operation),
            **kwargs,
        )


def verify_revision_for_test(calculation_revision_id: str, **kwargs: Any) -> Any:
    for key in (
        "work_unit_repository",
        "calculation_repository",
        "filing_repository",
        "verification_repository",
        "bucket_event_repository",
    ):
        kwargs.pop(key, None)
    kwargs.setdefault("certificate_secret_backend_factory", build_test_certificate_secret_backend_factory())
    kwargs.setdefault("verification_repositories", build_test_verification_repository_bundle())
    with bundled_indexed_authority().operation() as operation:
        return verify_modelo_revision_with_preconditions(calculation_revision_id, operation=operation, **kwargs).report


def export_revision_for_test(command: Any, **kwargs: Any) -> Any:
    with bundled_indexed_authority().operation() as operation:
        return export_modelo_revision(command, operation=operation, **kwargs)


def import_filing_evidence_for_test(**kwargs: Any) -> Any:
    kwargs.setdefault("observation_repository", CalculationObservationRepository())
    return import_external_filing_evidence(**kwargs)


BUCKET_ID = "13010000-0000-4000-8000-000000000100"

TAX_ID = "12345678Z"

YEAR = 2024

T0 = datetime(2024, 1, 10, 10, 0, tzinfo=UTC)

FILE_AT = datetime(2024, 4, 6, 12, 0, tzinfo=UTC)

M100_ANNUAL_PERIOD = "0A"

_RELATION_PREFILL_SOURCE = "relation_prefill"

#: Sources the caller must not supply. The bucket-locked half is DERIVED from the
#: caller-override ladder rather than hand-listed: a literal copy is correct only
#: until the next resolver is enrolled, and omitting `inventory` is what made the
#: lock reject this calculation outright.
_MESH_RESOLVED_OR_LOCKED_SOURCES = frozenset(
    {
        # Mesh-resolved rather than locked.
        "profile",
        _RELATION_PREFILL_SOURCE,
        # The register-resolved sale rows hold dates and marks a zero cannot stand for.
        BindingSourceKind.ACTIVITY_ASSET_DISPOSAL.value,
        # The withholding credits come from the taxpayer's payer records.
        BindingSourceKind.RETENCION_SOPORTADA.value,
    },
) | {kind.value for kind in precedence_ladder_sources(CallerOverrideDisposition.LOCK)}


M130_PRIOR_RETURN_RESULT_CASILLA: CasillaId = validated_casilla_id("18")

M130_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("19")

M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: CasillaId = validated_casilla_id("0224")

M100_RENDIMIENTO_SOURCE_1479_CASILLA: CasillaId = validated_casilla_id("1479")

M100_RENDIMIENTO_SOURCE_1553_CASILLA: CasillaId = validated_casilla_id("1553")

M100_RENDIMIENTO_SOURCE_1577_CASILLA: CasillaId = validated_casilla_id("1577")

M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: CasillaId = validated_casilla_id("1391")
#: The prior return's remainders that open this year's older Anexo C rows (1380, 1382, 1385).
PRIOR_ANEXO_C_REMAINDERS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(box, surface="PRIOR_ANEXO_C_REMAINDERS") for box in ("1384", "1387", "1390")
)

# Prior-year (2023) actividad-económica net income. M130's casilla-13 minoración
# reads ``irpf.previous_year_economic_activity_net_income`` — a previous_filing
# binding summing the prior annual M100's net-income casillas. The bucket
# previous_filing resolver HARD-RAISES once any prior observation exists and the
# prior-year M100 is absent, so the prior annual filing must be observed (the
# caller channel does not pre-empt the resolver). Set well above the minoración
# income ceiling so the minoración resolves to zero and each quarter's casilla 19
# is the clean incremental pago fraccionado — keeps the four computed c19 distinct
# and positive without this test depending on the minoración schedule.
PRIOR_YEAR = YEAR - 1

PRIOR_YEAR_NET_INCOME = Decimal("50000")

# One coherent year of business income, booked one distinct transaction per
# quarter. Cumulative-YTD (RD 439/2007 art. 110.2) windows then make each
# quarter's casilla 01 the running sum: 1T=4000, 2T=7500, 3T=9500, 4T=12000.
_QUARTER_INCOME: dict[str, tuple[date, Decimal]] = {
    "1T": (date(YEAR, 2, 15), Decimal("4000.00")),
    "2T": (date(YEAR, 5, 20), Decimal("3500.00")),
    "3T": (date(YEAR, 8, 10), Decimal("2000.00")),
    "4T": (date(YEAR, 11, 5), Decimal("2500.00")),
}


def income_transaction(period: str) -> Transaction:
    value_date, amount = _QUARTER_INCOME[period]
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=f"income-{period}",
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency="EUR",
                counterparty="Cliente SA",
                description=f"factura {period}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="a" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=T0,
                    provider_name="CSV provider",
                ),
                raw_fields={"Concepto": f"factura {period}"},
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            # The autonoma's activity receipts are IRPF-ready taxable-base rows. They
            # deliberately carry no IVA amount/rate facts: M130 already consumes
            # this base-only substrate and M100 must not demand IVA-only facts
            # unless its revision owns IVA ledger bindings.
            "taxable_base": amount,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": T0,
            "classified_by": "manual",
        },
    )


def expense_transaction(
    transaction_id: str,
    *,
    value_date: date,
    category: SpendingCategory,
    taxable_base: Decimal,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=transaction_id,
                booked_date=value_date,
                value_date=value_date,
                amount=taxable_base,
                currency="EUR",
                counterparty="Proveedor",
                description=f"gasto {category.value}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="b" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=T0,
                    provider_name="CSV provider",
                ),
                raw_fields={"Concepto": f"gasto {category.value}"},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "attachment_ids": (f"receipt-{transaction_id}",),
            "category_id": category.value,
            "taxable_base": taxable_base,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": T0,
            "classified_by": "manual",
        },
    )


def import_official_m130_result_observation(
    secure_objects: SecureObjectRepository,
    *,
    period: str,
    c19_value: Decimal,
    observed_also: Mapping[CasillaId, Decimal] | None = None,
) -> None:
    """Persist the autonoma's filed M130 result as AEAT-attested local evidence.

    ``observed_also`` are further figures of the same return, for a caller whose next
    quarter reads them.
    """
    # An original autoliquidación: no earlier filing of the quarter, so casilla 18 is zero.
    import_official_quarter_observation(
        secure_objects,
        modelo="130",
        period=period,
        casilla_values={
            M130_RESULTADO_FINAL_CASILLA: c19_value,
            M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
            **(observed_also or {}),
        },
    )


def import_official_quarter_observation(
    secure_objects: SecureObjectRepository,
    *,
    modelo: str,
    period: str,
    casilla_values: Mapping[CasillaId, Decimal],
) -> None:
    """Persist one filed quarterly return of the ejercicio as AEAT-attested local evidence."""
    wu_repo = WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    filing_repo = ModeloRecordCatalogueRepository(objects=secure_objects)
    bucket_events = BucketEventHistoryRepository(objects=secure_objects)
    observation_repo = CalculationObservationRepository(objects=secure_objects)
    snapshot = published_authority_operation().snapshot(modelo, filing_year=YEAR, period=period)
    with bundled_indexed_authority().operation() as operation:
        work_unit = create_work_unit(
            bucket_id=BUCKET_ID,
            modelo=modelo,
            filing_year=YEAR,
            period=Period.from_year_and_code(YEAR, period),
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=wu_repo,
                bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
            ),
            operation=operation,
            clock=FILE_AT,
        )
    # The reference id IS the justificante CSV, and a codigo seguro de
    # verificacion is uppercase alphanumeric: the model pins
    # ``^[A-Z0-9]{8,32}$``. The readable hyphenated spelling this replaced
    # was not a shape AEAT ever issues, so it could not survive the pattern.
    evidence_reference_id = f"JUST{modelo}{YEAR}{period}AUTONOMA"
    persist_justificante_metadata(
        evidence_reference_id,
        modelo=modelo,
        filing_year=YEAR,
        period=period,
        captured_at=FILE_AT,
        tax_id=TAX_ID,
    )
    import_filing_evidence_for_test(
        work_unit_id=work_unit.work_unit_id,
        casilla_values=casilla_values,
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id=evidence_reference_id,
        actor="aeat-import-test",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=filing_repo,
        bucket_event_repository=bucket_events,
        expected_tax_id=TAX_ID,
        clock=FILE_AT,
    )
    observation_repo.save(
        observation_repo.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo=modelo,
                filing_year=YEAR,
                period=period,
                observations=registry_grounded_observations(
                    modelo=modelo,
                    filing_year=YEAR,
                    period=period,
                    casilla_values=casilla_values,
                ),
            ),
            source_kind="aeat_sede_justificante",
            captured_at=FILE_AT,
            stamped_revision_id=snapshot.revision.id,
            source_metadata={
                "aeat_register_status": "ALTA",
                "aeat_expediente_id": f"EXP-{modelo}-{YEAR}-{period}",
                "aeat_justificante_csv": evidence_reference_id,
                "authenticated_identity": TAX_ID,
            },
        )
    )


def seed_prior_year_m100(secure_objects: SecureObjectRepository) -> None:
    """Observe the prior-year annual Renta (M100 2023) net-income casillas.

    Carries every prior-year casilla a 2024 ``previous_filing`` binding reads:
    M130's casilla-13 minoración sums M100 0224/1479/1553/1577 (net income in
    0224, the rest zero for a pure actividad-económica filer), and M100/2024's
    base-liquidable-negativa-general carry copies casilla 1391 (no prior BIN, so
    zero). Net income is set above the minoración ceiling so the minoración
    resolves to zero.
    """
    save_stamped_observation(
        CalculationObservationRepository(objects=secure_objects),
        RegistryModeloObservation(
            modelo="100",
            filing_year=PRIOR_YEAR,
            period=M100_ANNUAL_PERIOD,
            observations=registry_grounded_observations(
                modelo="100",
                filing_year=PRIOR_YEAR,
                period=M100_ANNUAL_PERIOD,
                casilla_values={
                    M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: PRIOR_YEAR_NET_INCOME,
                    M100_RENDIMIENTO_SOURCE_1479_CASILLA: Decimal("0"),
                    M100_RENDIMIENTO_SOURCE_1553_CASILLA: Decimal("0"),
                    M100_RENDIMIENTO_SOURCE_1577_CASILLA: Decimal("0"),
                    M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: Decimal("0"),
                    **dict.fromkeys(PRIOR_ANEXO_C_REMAINDERS, Decimal("0")),
                },
            ),
        ),
        source_kind="app_filing",
        captured_at=FILE_AT,
    )


def autonomaworkflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=TAX_ID,
        entity_type=EntityType.from_registry("natural_person"),
        irpf_income_categories=frozenset({IrpfIncomeCategory.from_registry("actividad_economica")}),
        irpf_estimation_regime=IrpfEstimationRegime.from_registry("directa_normal"),
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_professionals_with_retencion=False,
        pays_rent_with_retencion=False,
        pays_capital_income_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
        monedas_virtuales_extranjero_above_threshold=False,
    )


def m100_non_relation_zero_bindings() -> dict[BindingId, Decimal]:
    """Zero-default every M100/2024 binding that is neither profile- nor relation-sourced."""
    snapshot = published_authority_operation().snapshot("100", filing_year=YEAR, period=M100_ANNUAL_PERIOD)
    values = {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.source not in _MESH_RESOLVED_OR_LOCKED_SOURCES
    }
    return values
