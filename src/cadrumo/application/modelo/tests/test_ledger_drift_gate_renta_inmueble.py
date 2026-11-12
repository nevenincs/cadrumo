"""The verify-time drift gate compares each let property's recorded row with the row its records give now.

A draft records one identity and fingerprint per let property. Verification
resolves the properties again through the real resolver, from the current
profile, ledger and suffered-withholding records, and refuses the draft when a
row moved, appeared or disappeared, with the door that calculates again. An
unreadable store refuses too, without a door: an unread record is not one that
did not move.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.operator_action_enums import ActionEvidenceProvenance
from ....core.period import Period
from ....core.retencion_soportada import RetencionSoportadaClase
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from ....domain.calculations.registry.renta_inmueble_bindings import renta_inmueble_columns
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.calculations.row_source_identity import RowSourceIdentity
from ....domain.contribuyente.inmueble_record import ValorCatastral
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.verification_report import ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.renta.retencion_soportada import RetencionSoportadaOrigen, RetencionSoportadaRecord
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...aggregation.ledger_membership import LedgerMembershipPorts, observe_renta_inmueble_rows
from ...aggregation.renta_inmueble_source import RentaInmuebleRowField
from ...aggregation.retencion_soportada_repository import RetencionSoportadaPorts
from ...aggregation.tests.ledger_source_mesh_support import (
    BUCKET_ID,
    EmptyActivityAssetHistoryRepository,
    EmptyInventoryRepository,
    EmptyInvestmentRegisterRepository,
    InMemoryTransactionCatalogueRepository,
    catalogue_read_ports,
    empty_invoice_repository,
    empty_prorrata_repository,
)
from ...aggregation.tests.renta_inmueble_support import (
    TENANT_NIF,
    expense,
    inmueble,
    lease,
    monthly_rent,
    profile_facts,
)
from ...aggregation.tests.usage_ratio_support import no_stored_usage_ratios
from ..ledger_drift_gate import renta_inmueble_drift_finding
from ..preconditions import build_modelo_precondition_failure_for_scenario
from ..work_profile import ModeloWorkProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEAR = filing_year_envelope().horizon
_AT = datetime(_YEAR + 1, 4, 20, 12, 0, tzinfo=UTC)
_DRIFT = "application.modelo.findings.renta_inmueble_rows_drift"
_UNAVAILABLE = "application.modelo.findings.renta_inmueble_rows_unavailable"
_RENT = Decimal(900)


class _Withholding:
    def __init__(self, *records: RetencionSoportadaRecord) -> None:
        self._records = records

    def load_records(self, ejercicio: int) -> tuple[RetencionSoportadaRecord, ...]:
        return tuple(record for record in self._records if record.ejercicio == ejercicio)


def _withheld(amount: str) -> RetencionSoportadaRecord:
    return RetencionSoportadaRecord.model_validate(
        {
            "ejercicio": _YEAR,
            "payer_tax_id": TENANT_NIF,
            "payer_ref": "e" * 64,
            "income_class": RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO,
            "importe_integro_dinerario": _RENT * 12,
            "valoracion_especie": Decimal("0.00"),
            "retencion": Decimal(amount),
            "ingreso_a_cuenta": Decimal("0.00"),
            "ingreso_a_cuenta_repercutido": Decimal("0.00"),
            "origin": RetencionSoportadaOrigen.OPERATOR_DECLARATION,
            "captured_at": _AT,
        }
    )


def _facts(*, lease_end: date | None = None) -> dict[str, str]:
    record = inmueble(
        ejercicio=_YEAR,
        importe_adquisicion=Decimal(150000),
        gastos_tributos_adquisicion=Decimal(10000),
        valores_catastrales=(ValorCatastral(year=_YEAR, total=Decimal(100000), construccion=Decimal(60000)),),
    )
    return profile_facts((record,), (lease(start=date(_YEAR - 3, 1, 1), end=lease_end),))


def _ledger(*extra: Transaction) -> tuple[Transaction, ...]:
    return (
        *monthly_rent(_YEAR, amount=_RENT),
        expense("comunidad", concept="comunidad", amount=Decimal(600), booked=date(_YEAR, 2, 1)),
        *extra,
    )


def _profile(facts: dict[str, str]) -> ModeloWorkProfile:
    operation = governed_facts_in_scope()
    assert isinstance(operation, PinnedAuthorityOperation)
    return ModeloWorkProfile(
        record=create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="X0001500M"),
                *(UserProfileFact(path=path, value=value) for path, value in facts.items()),
            ),
            context=operation.profile_create_context(),
        ),
        profile_decode_context=operation.profile_decode_context(),
    )


def _ports(rows: tuple[Transaction, ...], withholding: RetencionSoportadaPorts | None) -> LedgerMembershipPorts:
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    repository.save(TransactionCatalogue.from_transactions(rows))
    return LedgerMembershipPorts(
        transaction_repository=repository,
        invoice_catalogue_read_ports=catalogue_read_ports(
            invoice_repository=empty_invoice_repository(), transaction_repository=repository
        ),
        prorrata_register_repository=empty_prorrata_repository(),
        bienes_inversion_repository=EmptyInvestmentRegisterRepository(),
        activity_asset_history_repository=EmptyActivityAssetHistoryRepository(),
        usage_ratio_profile_loader=no_stored_usage_ratios,
        inventory_repository=EmptyInventoryRepository(),
        retencion_soportada_ports=withholding,
    )


def _work_unit() -> WorkUnit:
    snapshot = published_snapshot("100", filing_year=_YEAR, period="0A")
    period = Period.from_year_and_code(_YEAR, "0A")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=BUCKET_ID, modelo="100", filing_year=_YEAR, period=period, revision_id=snapshot.revision.id
        ),
        bucket_id=BUCKET_ID,
        modelo=ModeloCode("100"),
        filing_year=_YEAR,
        period=period,
        revision_id=snapshot.revision.id,
        name=f"100-{_YEAR}-0A",
        created_at=_AT,
        updated_at=_AT,
    )


def _observe(
    work_unit: WorkUnit,
    target: CalculationRevision,
    *,
    facts: dict[str, str],
    rows: tuple[Transaction, ...],
    withholding: RetencionSoportadaPorts | None,
) -> frozenset[tuple[str, str]] | None:
    operation = governed_facts_in_scope()
    assert isinstance(operation, PinnedAuthorityOperation)
    return observe_renta_inmueble_rows(
        target=target,
        work_unit=work_unit,
        revision=published_snapshot("100", filing_year=_YEAR, period="0A").revision,
        profile=_profile(facts),
        ports=_ports(rows, withholding),
        operation=operation,
    )


def _draft(work_unit: WorkUnit, rows: frozenset[tuple[str, str]]) -> CalculationRevision:
    """Store a draft recording ``rows`` on the gross-income column, as calculation keeps them."""
    snapshot = published_snapshot("100", filing_year=_YEAR, period="0A")
    column = next(
        binding.id
        for binding, provider in renta_inmueble_columns(snapshot.revision)
        if provider.row_field == RentaInmuebleRowField.INGRESOS_INTEGROS.value
    )
    ordered = sorted(rows)
    identities = {
        (column, index): RowSourceIdentity(
            source_kind=BindingSourceKind.RENTA_INMUEBLE, source_row_identity=identity, fingerprint=fingerprint
        )
        for index, (identity, fingerprint) in enumerate(ordered, start=1)
    }
    values = {column: {str(index): "10800" for index in range(1, len(ordered) + 1)}} if ordered else {}
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            row_binding_values=values,
            row_source_identities=identities,
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        observations=(),
        created_at=_AT,
        updated_at=_AT,
        filing_instance_evidence=None,
        source_provenance=(),
        row_binding_values=values,
        row_source_identities=identities,
    )


def _calculated(work_unit: WorkUnit) -> CalculationRevision:
    """The draft as calculation left it: the property's row as the records gave it then."""
    empty = _draft(work_unit, frozenset())
    rows = _observe(
        work_unit, empty, facts=_facts(), rows=_ledger(), withholding=RetencionSoportadaPorts(repository=_Withholding())
    )
    assert rows is not None and len(rows) == 1
    return _draft(work_unit, rows)


def test_a_draft_whose_property_resolves_to_the_same_row_is_current() -> None:
    work_unit = _work_unit()
    draft = _calculated(work_unit)
    current = _observe(
        work_unit, draft, facts=_facts(), rows=_ledger(), withholding=RetencionSoportadaPorts(repository=_Withholding())
    )

    assert renta_inmueble_drift_finding(target=draft, work_unit=work_unit, current=current) is None


@pytest.mark.parametrize(
    "moved",
    ["ledger", "lease", "withholding"],
)
def test_a_moved_property_lease_ledger_row_or_withholding_blocks_with_counts_only(moved: str) -> None:
    work_unit = _work_unit()
    draft = _calculated(work_unit)
    facts = _facts(lease_end=date(_YEAR, 12, 31)) if moved == "lease" else _facts()
    rows = (
        _ledger(expense("seguro", concept="primas_seguro", amount=Decimal(200), booked=date(_YEAR, 5, 1)))
        if moved == "ledger"
        else _ledger()
    )
    withholding = _Withholding(_withheld("2052.00")) if moved == "withholding" else _Withholding()
    current = _observe(
        work_unit, draft, facts=facts, rows=rows, withholding=RetencionSoportadaPorts(repository=withholding)
    )
    finding = renta_inmueble_drift_finding(target=draft, work_unit=work_unit, current=current)

    assert finding is not None
    assert finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_locale_key == _DRIFT
    assert finding.message_facts["rows_recorded"] == 1
    assert finding.message_facts["rows_current"] == 1
    assert finding.message_facts["rows_changed"] == 1
    assert "inmueble" not in str(finding.message_facts)


def test_a_property_that_no_longer_resolves_drops_its_row() -> None:
    work_unit = _work_unit()
    draft = _calculated(work_unit)
    current = _observe(
        work_unit, draft, facts={}, rows=_ledger(), withholding=RetencionSoportadaPorts(repository=_Withholding())
    )
    finding = renta_inmueble_drift_finding(target=draft, work_unit=work_unit, current=current)

    assert finding is not None
    assert finding.message_facts["rows_current"] == 0


def test_an_unreadable_withholding_store_refuses_a_draft_with_let_properties_and_passes_one_without() -> None:
    work_unit = _work_unit()
    draft = _calculated(work_unit)
    current = _observe(work_unit, draft, facts=_facts(), rows=_ledger(), withholding=None)

    assert current is None
    finding = renta_inmueble_drift_finding(target=draft, work_unit=work_unit, current=current)
    assert finding is not None
    assert finding.message_locale_key == _UNAVAILABLE
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert (
        renta_inmueble_drift_finding(target=_draft(work_unit, frozenset()), work_unit=work_unit, current=None) is None
    )


def test_the_drift_refusal_opens_the_calculation_again_and_the_unavailable_one_has_no_door() -> None:
    work_unit = _work_unit()
    drift = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.work.verify",
        scenario_id="modelo.work.verify.renta_inmueble_rows.drift_detected",
        evidence_id="modelo.work.verify.renta_inmueble_rows",
        evidence_values={"work_unit_id": work_unit.work_unit_id, "rows_available": True},
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        action_argument_values={"work_unit_id": work_unit.work_unit_id},
    )
    unavailable = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.work.verify",
        scenario_id="modelo.work.verify.renta_inmueble_rows.unavailable",
        evidence_id="modelo.work.verify.renta_inmueble_rows",
        evidence_values={"work_unit_id": work_unit.work_unit_id, "rows_available": False},
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )

    assert drift.verdict.action is not None
    assert drift.verdict.action.action_id == "operator.modelo.work.calculate"
    (binding,) = drift.verdict.argument_bindings
    assert (binding.argument_name, binding.value) == ("work_unit_id", work_unit.work_unit_id)
    assert unavailable.verdict.action is None
