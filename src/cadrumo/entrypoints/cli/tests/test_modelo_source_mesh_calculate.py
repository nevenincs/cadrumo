"""CLI roundtrip coverage for source mesh-backed modelo calculation."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.profile.usage_ratios import save_usage_ratios
from ....core import (
    STR_KEYED_MAPPING_ADAPTER,
    IvaDeductionEvidenceAuthority,
    IvaDeductionFactKind,
    Period,
)
from ....core.errors import ERROR_REGISTRY
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.categories.spending_category import SpendingCategory
from ....domain.invoices import InvoiceCatalogue
from ....domain.iva import EUMemberState, IvaCategory, IvaDeductionClassificationProvenance
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.usage_ratios import UsageRatioProfile
from ....domain.user_profile.values import UserProfileFact
from ....tests.cli_envelope import unwrap_envelope_notices
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from ....tests.user_profile import register_cli_profile
from ._m303_filing_evidence_support import write_m303_filing_evidence

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_IVA_WALLET_DECIDED_AT = datetime(2026, 5, 28, 16, 10, tzinfo=UTC)


def _create_profile(**extra_facts: str) -> None:
    """Register the profile through the shared CLI registration door.

    ``extra_facts`` carries per-modelo attestations that readiness demands of
    that modelo alone, so the shared profile stays minimal.
    """
    facts = {
        "identity.tax_id": "12345678Z",
        "taxpayer_type.entity_type": "natural_person",
        "identity.name": "Operator",
        "identity.surnames": "Operator",
        "activities.description": "design",
        "taxpayer_type.irpf_income_categories": "actividad_economica",
    }
    facts.update(extra_facts)
    register_cli_profile(label="operator", facts=facts)


def _create_work_unit(*, modelo: str, year: int, period: str) -> dict[str, str]:
    """Create a work unit and let the registry authority pick the revision.

    No ``--revision`` is injected. AEAT binds each ``(modelo, filing_year,
    period)`` triple to exactly one revision by published orden, so the
    revision is a derived fact and creation accepts an explicit id only when
    it equals that resolution. Pinning a literal here buys nothing and goes
    stale the moment a new revision opens: these fixtures previously pinned
    M303 to an obsolete revision for 2026, which began refusing outright
    once the 2026 revision shipped and capped that window at 2025-12-31.
    """
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            modelo,
            "--year",
            str(year),
            "--period",
            period,
        ],
    )
    assert result.exit_code == 0, result.output
    payload = STR_KEYED_MAPPING_ADAPTER.validate_python(_payload(result.output))
    work_unit_id = payload["work_unit_id"]
    assert isinstance(work_unit_id, str)
    return {"work_unit_id": work_unit_id}


def _create_303_work_unit() -> dict[str, str]:
    return _create_work_unit(modelo="303", year=2026, period="1T")


def _create_115_work_unit() -> dict[str, str]:
    return _create_work_unit(modelo="115", year=2026, period="1T")


def _create_111_work_unit() -> dict[str, str]:
    return _create_work_unit(modelo="111", year=2025, period="2T")


def _create_180_work_unit() -> dict[str, str]:
    return _create_work_unit(modelo="180", year=2026, period="0A")


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(2026, 2, 10),
    amount: Decimal,
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente o proveedor",
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 2, 11, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    amount: Decimal,
    taxable_base: Decimal,
    iva_amount: Decimal,
    # Defaults to the general tipo, which every rate-bearing row in this file
    # declares. A category whose cuota is zero by law takes an explicit ZERO
    # tipo rather than an absent one: the missing-fact screen refuses a row with
    # no iva_rate at all, and the zero-cuota guard refuses any tipo that is not
    # exactly 0, so Decimal("0") is the one value satisfying both. (That the
    # other rows here rely on the default is a fact about the file today, not a
    # contract.)
    iva_rate: Decimal | None = Decimal("0.21"),
    iva_category: IvaCategory | None = None,
    deduction_fact_kind: IvaDeductionFactKind | None = None,
    deduction_locator: str | None = None,
    counterparty_country: str | None = None,
    counterparty_identification_state: EUMemberState | None = None,
) -> Transaction:
    fields: dict[str, object] = {
        "raw": _raw_transaction(provider_id, amount=amount),
        "direction": direction,
        "business_classification": BusinessClassification.BUSINESS,
        "source_jurisdiction": "ES",
        "group_label": None,
        "category_id": "test_iva_operation",
        "taxable_base": taxable_base,
        "iva_rate": iva_rate,
        "iva_amount": iva_amount,
        "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
        "classified_by": "manual",
    }
    if iva_category is not None:
        fields["iva_category"] = iva_category
    if deduction_fact_kind is not None:
        # LIVA art. 97: the factura confers the right to deduct, so an input
        # row only reaches a soportado binding once it carries its
        # invoice-evidence deduction authority.
        fields["deduction_fact_kind"] = deduction_fact_kind
        fields["deduction_provenance"] = IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
            source_locator=deduction_locator or "invoice:test-purchase",
            evidence_digest="a" * 64,
        )
    if counterparty_country is not None:
        fields["counterparty_country"] = counterparty_country
    if counterparty_identification_state is not None:
        fields["counterparty_identification_state"] = counterparty_identification_state
    return Transaction.model_validate(fields)


def _classified_rent_transaction() -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                "rent-net-withholding",
                booked_date=date(2026, 3, 15),
                amount=Decimal("2754.00"),
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "category_id": "arrendamiento_local",
            "taxable_base": Decimal("2700.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("567.00"),
            "irpf_category": "arrendamiento_local",
            "classified_at": datetime(2026, 3, 15, 12, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _m100_activity_income_transaction() -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                "m100-activity-income",
                booked_date=date(2024, 3, 15),
                amount=Decimal("12000.00"),
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "taxable_base": Decimal("12000.00"),
            "iva_rate": Decimal("0"),
            "iva_amount": Decimal("0"),
            "classified_at": datetime(2024, 3, 15, 12, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _m100_activity_expense_transaction(
    transaction_id: str,
    *,
    value_date: date,
    category: SpendingCategory,
    taxable_base: Decimal,
) -> Transaction:
    iva_amount = (taxable_base * Decimal("0.21")).quantize(Decimal("0.01"))
    gross_amount = taxable_base + iva_amount
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                transaction_id,
                booked_date=value_date,
                amount=gross_amount,
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "category_id": category.value,
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            "classified_at": datetime(2024, 3, 15, 12, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _seed_m100_profile_facts(bucket_id: str) -> None:
    from ....tests.profile_capsule import load_test_profile_record, replace_test_profile_record

    record = load_test_profile_record(bucket_id)
    additions = (
        UserProfileFact(path="tax_residence.ccaa", value="madrid"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="iva.regime", value="GENERAL"),
        UserProfileFact(path="iva.m303_regime_composition", value="general"),
        UserProfileFact(path="iva.redeme_enrolled", value=False),
        UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
        UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
        UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
        UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
        UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
        UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
        UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
        UserProfileFact(path="renta_taxpayer.sex", value="H"),
        UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
        UserProfileFact(path="renta_taxpayer.marriage_full_year", value=Decimal("0")),
        UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
        UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
        UserProfileFact(path="renta_filing.declaration_type", value="1"),
        UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
        UserProfileFact(path="renta_family.descendientes_count", value=Decimal("0")),
        UserProfileFact(path="renta_family.cotizaciones_ss_madre_2024", value=Decimal("0")),
        UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
    )
    facts_by_path = {fact.path: fact for fact in record.facts}
    facts_by_path.update({fact.path: fact for fact in additions})
    replace_test_profile_record(
        record.model_copy(
            update={
                "facts": tuple(facts_by_path[path] for path in sorted(facts_by_path)),
                "updated_at": record.created_at,
            },
        ),
    )


def _seed_prior_m100_zero_carry() -> None:
    from ....application.calculations import CalculationObservationRepository

    CalculationObservationRepository().save(
        CalculationObservationRepository().prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="100",
                filing_year=2023,
                period="0A",
                observations=registry_grounded_observations(
                    modelo="100",
                    filing_year=2023,
                    period="0A",
                    casilla_values={
                        "0224": Decimal("0"),
                        "1388": Decimal("0"),
                        "1391": Decimal("0"),
                        "1479": Decimal("0"),
                        "1553": Decimal("0"),
                        "1577": Decimal("0"),
                    },
                ),
            ),
            source_kind="app_filing",
            captured_at=datetime(2024, 6, 30, 12, 0, tzinfo=UTC),
        )
    )


def test_work_calculate_modelo_115_uses_retenciones_aggregation_observation() -> None:
    """M115 CLI calculation consumes persisted URBAN_RENTAL retención evidence."""

    _create_profile()
    work_unit = _create_115_work_unit()
    observation = json.dumps(
        {
            "source_kind": "ledger_transaction",
            "source_object_id": "rent-ledger-row-001",
            "perceptor_nif": "B12345678",
            "perceptor_name": "Arrendador Ejemplo SL",
            "scheme": "arrendamiento_urbano",
            "taxable_base": "2700.00",
            "retencion_amount": "513.00",
            "accrued_on": "2026-03-15",
        },
    )

    aggregated = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "aggregate",
            "--modelo",
            "115",
            "--year",
            "2026",
            "--period",
            "1T",
            "--retencion-observation",
            observation,
        ],
    )
    assert aggregated.exit_code == 0, aggregated.output
    assert _payload(aggregated.output)["observation_count"] == 1

    calculated = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
            "--casilla",
            "04=0",
        ],
    )
    assert calculated.exit_code == 0, calculated.output
    casilla_values = _payload(calculated.output)["casilla_values"]
    assert Decimal(casilla_values["01"]) == Decimal("1")
    assert Decimal(casilla_values["02"]) == Decimal("2700.00")
    assert Decimal(casilla_values["03"]) == Decimal("513.00")
    assert Decimal(casilla_values["05"]) == Decimal("513.00")


def test_work_calculate_modelo_100_routes_autonoma_auto_ledger_expenses() -> None:
    """An operator's public CLI M100 path carries ledger income through 0171/0180/0224."""
    from ....core.bucket_pointer import resolve_active_bucket_id

    _create_profile()
    work_unit = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "100",
            "--year",
            "2024",
            "--period",
            "0A",
            "--revision",
            "2024",
        ],
    )
    assert work_unit.exit_code == 0, work_unit.output
    work_unit_payload = _payload(work_unit.output)
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "profile create must install an active-profile pointer"

    expense_rows = (
        _m100_activity_expense_transaction(
            "m100-expense-office",
            value_date=date(2024, 2, 20),
            category=SpendingCategory.MATERIAL_OFICINA,
            taxable_base=Decimal("500.00"),
        ),
        _m100_activity_expense_transaction(
            "m100-expense-software",
            value_date=date(2024, 5, 22),
            category=SpendingCategory.SOFTWARE_SUSCRIPCION,
            taxable_base=Decimal("700.00"),
        ),
        _m100_activity_expense_transaction(
            "m100-expense-phone",
            value_date=date(2024, 8, 12),
            category=SpendingCategory.TELEFONIA_MOVIL,
            taxable_base=Decimal("300.00"),
        ),
        _m100_activity_expense_transaction(
            "m100-expense-advisory",
            value_date=date(2024, 11, 8),
            category=SpendingCategory.ASESORIA_FISCAL,
            taxable_base=Decimal("900.00"),
        ),
    )
    with open_test_profile_session(bucket_id):
        _seed_m100_profile_facts(bucket_id)
        _seed_prior_m100_zero_carry()
        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions((_m100_activity_income_transaction(), *expense_rows)),
        )
        InvoiceCatalogueRepository(bucket_id=bucket_id).save(InvoiceCatalogue())
        save_usage_ratios(
            UsageRatioProfile(ratios={SpendingCategory.TELEFONIA_MOVIL: Decimal("1")}),
            bucket_id=bucket_id,
        )

    calculated = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit_payload["work_unit_id"]),
            "--binding",
            "renta-2024-modelo-100-estimacion-directa-es-normal=1",
        ],
    )
    assert calculated.exit_code == 0, calculated.output
    casilla_values = _payload(calculated.output)["casilla_values"]

    assert Decimal(casilla_values["0171"]) == Decimal("12000.00")
    assert Decimal(casilla_values["0180"]) == Decimal("12000.00")
    assert Decimal(casilla_values["0218"]) == Decimal("2400.00")
    assert Decimal(casilla_values["0220"]) == Decimal("2400.00")
    assert Decimal(casilla_values["0224"]) == Decimal("9600.00")


def test_work_calculate_modelo_100_autonoma_visible_target_uses_registered_error_boundary() -> None:
    """An operator's public M100 calculate shape must not degrade into an internal crash."""

    _create_profile()
    work_unit = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "100",
            "--year",
            "2024",
            "--period",
            "0A",
            "--revision",
            "2024",
        ],
    )
    assert work_unit.exit_code == 0, work_unit.output

    calculated = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            "--modelo",
            "100",
            "--year",
            "2024",
            "--period",
            "0A",
            "--casilla",
            "0003=30000.00",
            "--casilla",
            "0596=4500.00",
            "--by",
            "autonoma",
        ],
    )

    assert "Traceback" not in calculated.output
    assert "missing a declared ErrorCode registry entry" not in calculated.output
    assert "Internal. El comando fall" not in calculated.output
    envelope = json.loads(calculated.output)
    if calculated.exit_code == 0:
        payload = _payload(calculated.output)
        assert payload["work_unit_id"] == _payload(work_unit.output)["work_unit_id"]
        assert payload["calculation_revision_id"]
        return

    error = envelope["error"]
    assert error["code"] in ERROR_REGISTRY
    assert error["category"] == ERROR_REGISTRY[error["code"]].category.value


def test_work_calculate_modelo_111_no_retenciones_quarter_names_profile_attestation_path() -> None:
    """A no-observation M111 quarter is not filed blank; the CLI names the attestation path."""

    # Modelo 111 readiness demands an explicit colegio-concertado attestation
    # (preflight.py:280), and the export producer refuses without it
    # (_producer_snapshot.py:1548). Declare it so the run reaches the
    # no-retenciones attestation path this test is about.
    _create_profile(**{"withholding.colegio_concertado": "false"})
    _create_111_work_unit()

    calculated = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            "--modelo",
            "111",
            "--year",
            "2025",
            "--period",
            "2T",
            "--by",
            "Javier",
        ],
    )

    assert calculated.exit_code != 0, calculated.output
    envelope = json.loads(calculated.output)
    assert envelope["error"]["code"] == "ERROR_FINANCIAL_AGGREGATION_VALIDATION"
    assert envelope["error"]["context"]["modelo"] == "111"
    assert envelope["error"]["context"]["period"] == "2T"
    assert envelope["error"]["context"]["source_kind"] == "retenciones_aggregation"
    # The free-text ``suggestion`` field is gone -- ``suggestion`` is a reserved
    # action-context key. The attestation steer now rides the localised message,
    # following the Modelo 180 precedent, because the wizard setup command
    # projects no inputs for the typed action channel to bind against.
    message = envelope["error"]["message"]
    assert "--retencion-observation" in message
    assert "all-blank Modelo 111" in message
    assert "--modelo-111-no-retenciones-periods 2025:2T" in message

    attested = invoke_cached_cli(
        [
            "config",
            "profile",
            "edit",
            "operator",
            "--quiet",
            "--modelo-111-no-retenciones-periods",
            "2025:2T,2025:3T,2025:4T",
        ],
    )
    assert attested.exit_code == 0, attested.output
    shown = invoke_cached_cli(("config", "profile", "view", "operator"))
    assert shown.exit_code == 0, shown.output
    assert "withholding.modelo_111_no_retenciones_periods\t2025:2T,2025:3T,2025:4T" in shown.output


def test_work_calculate_modelo_115_classified_rent_row_requires_perceptor_evidence() -> None:
    """A classified rent ledger row alone must hard-stop instead of producing zeros."""
    from ....core.bucket_pointer import resolve_active_bucket_id

    _create_profile()
    work_unit = _create_115_work_unit()
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    with open_test_profile_session(bucket_id):
        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions((_classified_rent_transaction(),)),
        )

    calculated = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
            "--casilla",
            "04=0",
        ],
    )

    assert calculated.exit_code != 0, calculated.output
    envelope = json.loads(calculated.output)
    assert envelope["error"]["code"] == "ERROR_FINANCIAL_AGGREGATION_VALIDATION"
    assert envelope["error"]["context"]["modelo"] == "115"
    assert envelope["error"]["context"]["period"] == "1T"
    assert envelope["error"]["context"]["source_kind"] == "retenciones_aggregation"
    # The free-text ``suggestion`` field is gone: ``suggestion`` is a reserved
    # action-context key, and guidance now rides the typed action projection.
    # Assert that projection rather than prose -- it names the failed condition
    # exactly, and records that no mechanical recovery exists for it.
    action = envelope["error"]["action"]
    assert action["failed_condition_id"] == "aggregation.retenciones.observations.present"
    assert action["no_recovery_outcome"] == "operator_decision"
    assert action["action"] is None
    assert "retention observations" in envelope["error"]["message"]
    assert "115" in envelope["error"]["message"]


def test_work_calculate_modelo_180_refuses_string_perceptor_casilla_with_detail_guidance() -> None:
    """M180 perceptor string fields are refused before the decimal casilla parser."""

    _create_profile()
    work_unit = _create_180_work_unit()

    calculated = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
            "--casilla",
            "perc.nif=B12345678",
        ],
    )

    assert calculated.exit_code != 0, calculated.output
    envelope = json.loads(calculated.output)
    assert envelope["error"]["code"] == "REFUSED_MODELO_CALCULATE_CASILLA_INPUT"
    assert envelope["error"]["context"]["key"] == "perc.nif"
    assert "perceptor/property detail rows are not supported" in envelope["error"]["message"]
    assert "--retencion-observation" in envelope["error"]["message"]


def test_work_calculate_persists_ledger_source_mesh_observations(tmp_path: Path) -> None:
    from ....core.bucket_pointer import resolve_active_bucket_id

    _create_profile()
    work_unit = _create_303_work_unit()
    evidence_path = write_m303_filing_evidence(
        tmp_path / "m303-filing-evidence.json",
        Period.from_year_and_code(2026, "1T"),
    )
    # The CLI JSON output redacts ``bucket_id`` to the literal placeholder
    # ``"<bucket-id>"``; that placeholder is not a valid filesystem path
    # segment on Windows (``<`` / ``>`` are reserved). Resolve the real
    # bucket id from the active-profile pointer the freshly-created
    # profile installed.
    resolved = resolve_active_bucket_id()
    assert resolved is not None, "profile create must install an active-profile pointer"
    bucket_id = resolved
    sale = _transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    purchase = _transaction(
        "purchase-general",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("60.50"),
        taxable_base=Decimal("50.00"),
        iva_amount=Decimal("10.50"),
        deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
        deduction_locator="invoice:purchase-general-2026-1T",
    )

    # Seed ledger data and a zero-amount IVA wallet decision via a live
    # profile session.  The CLI runner resets the ContextVar on each
    # invocation exit so direct repository calls that depend on an active
    # bucket session must enter their own session block.
    # The IVA wallet decision is required by the Modelo 303 reconciliation
    # guard: it blocks calculation when ``compensacion-pendiente-anteriores``
    # is supplied without a persisted decision, even when the amount is zero.
    # A local_recurrence decision with selected_amount=0 satisfies the guard
    # while leaving the ledger mesh assertions meaningful.
    with open_test_profile_session(bucket_id):
        from ....application.calculations import IvaWalletDecisionRepository
        from ....domain.iva_compensation import IvaCompensationReconciliationDecision

        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions((sale, purchase)),
        )
        decision = IvaCompensationReconciliationDecision(
            taxpayer_nif="12345678Z",
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "1T"),
            selected_authority="local_recurrence",
            selected_amount=Decimal("0"),
            wallet_amount=None,
            local_recurrence_amount=Decimal("0"),
            override_amount=None,
            divergence="wallet_missing",
            blocked=False,
            stale_wallet=False,
            reason_identity="first_period_zero_aeat_wallet",
            decided_at=_IVA_WALLET_DECIDED_AT,
        )
        IvaWalletDecisionRepository().save_decision(decision)

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
            "--m303-filing-evidence",
            str(evidence_path),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    revision_id = payload["calculation_revision_id"]

    with open_test_profile_session(bucket_id):
        persisted = CalculationRevisionCatalogueRepository().load().revisions[revision_id]

    assert persisted.source_transaction_ids == tuple(sorted((sale.transaction_id, purchase.transaction_id)))
    assert Decimal(persisted.binding_overrides["modelo-303-iva-repercutido-general-cuota"]) == sale.iva_amount
    assert Decimal(persisted.binding_overrides["modelo-303-iva-soportado-interiores-cuota"]) == purchase.iva_amount
    observations = {observation.casilla_id: observation for observation in persisted.observations}
    output_observation = observations["iva.repercutido.general"]
    input_observation = observations["iva.soportado.interiores"]
    assert output_observation.formula_id is None
    assert input_observation.formula_id is None
    assert output_observation.legal_refs
    assert input_observation.legal_refs
    assert output_observation.source_refs
    assert input_observation.source_refs
    payload_observations = {observation["casilla_id"]: observation for observation in payload["observations"]}
    assert payload_observations["iva.repercutido.general"]["source_refs"] == list(output_observation.source_refs)
    assert payload_observations["iva.soportado.interiores"]["source_refs"] == list(input_observation.source_refs)

    observations_result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "observations",
            revision_id,
        ],
    )
    assert observations_result.exit_code == 0, observations_result.output
    observations_payload = _payload(observations_result.output)
    assert observations_payload["operation"] == "modelo.work.observations"
    assert observations_payload["calculation_revision_id"] == revision_id
    assert observations_payload["work_unit_id"] == work_unit["work_unit_id"]
    assert observations_payload["observation_count"] == len(payload["observations"])
    command_observations = {
        observation["casilla_id"]: observation for observation in observations_payload["observations"]
    }
    assert command_observations["iva.repercutido.general"]["legal_refs"] == list(output_observation.legal_refs)
    assert command_observations["iva.repercutido.general"]["source_refs"] == list(output_observation.source_refs)
    assert command_observations["iva.soportado.interiores"]["legal_refs"] == list(input_observation.legal_refs)
    assert command_observations["iva.soportado.interiores"]["source_refs"] == list(input_observation.source_refs)

    text_observations = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "observations",
            revision_id,
        ],
    )
    assert text_observations.exit_code == 0, text_observations.output
    assert "operation\tmodelo.work.observations" in text_observations.output
    assert f"calculation_revision_id\t{revision_id}" in text_observations.output
    assert "iva.repercutido.general" in text_observations.output
    assert output_observation.legal_refs[0] in text_observations.output
    assert output_observation.source_refs[0] in text_observations.output


def _seed_zero_iva_wallet_decision(bucket_id: str) -> None:
    """Persist a zero-amount local-recurrence IVA wallet decision for bucket.

    The Modelo 303 reconciliation guard blocks calculation when
    ``compensacion-pendiente-anteriores`` is supplied without a persisted
    decision, even when the amount is zero. A ``local_recurrence`` decision
    with ``selected_amount=0`` satisfies the guard while leaving the source-mesh
    advisory assertions meaningful.
    """
    from ....application.calculations import IvaWalletDecisionRepository
    from ....domain.iva_compensation import IvaCompensationReconciliationDecision

    with open_test_profile_session(bucket_id):
        decision = IvaCompensationReconciliationDecision(
            taxpayer_nif="12345678Z",
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "1T"),
            selected_authority="local_recurrence",
            selected_amount=Decimal("0"),
            wallet_amount=None,
            local_recurrence_amount=Decimal("0"),
            override_amount=None,
            divergence="wallet_missing",
            blocked=False,
            stale_wallet=False,
            reason_identity="first_period_zero_aeat_wallet",
            decided_at=_IVA_WALLET_DECIDED_AT,
        )
        IvaWalletDecisionRepository().save_decision(decision)


def test_work_calculate_suppresses_advisory_for_cuota_less_intra_community_supply(tmp_path: Path) -> None:
    """An INTRA_COMMUNITY_SUPPLY observation is cuota-less, so it raises NO advisory.

    Per the ``aeat-ledger-contract`` rule, an
    exempt entrega intracomunitaria (Ley 37/1992 art. 25) is base-only with no
    cuota to route: it is a member of ``CUOTA_LESS_M303_IVA_CATEGORIES`` and
    MUST NEVER fire the unconsumed-declarable-IVA advisory. Flagging it would be
    a false positive that trains operators to ignore the alert, so the advisory
    only earns trust if every fire is a genuine unrouted cuota. This test pins
    that suppression on the operator-facing calculate surface across both the
    JSON ``notices`` channel and the human text output.
    """
    from ....core.bucket_pointer import resolve_active_bucket_id

    _create_profile()
    work_unit = _create_303_work_unit()
    evidence_path = write_m303_filing_evidence(
        tmp_path / "m303-filing-evidence.json",
        Period.from_year_and_code(2026, "1T"),
    )
    resolved = resolve_active_bucket_id()
    assert resolved is not None, "profile create must install an active-profile pointer"
    bucket_id = resolved

    # A consumed domestic sale (matches the repercutido-general binding) ...
    domestic_sale = _transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    # ... plus a cuota-less intra-community supply (exempt, base-only) that no
    # M303 cuota binding selects and that must NOT raise a source advisory.
    cuota_less_supply = _transaction(
        "intra-community-supply",
        direction=TransactionDirection.INCOMING,
        # Base-only, as an exempt supply is: LIVA art. 25 exempts the operation,
        # so no cuota arises and the invoice total IS the base. The fixture
        # previously declared 242,00 against a 200,00 base with 42,00 of cuota at
        # the default 0,21 tipo -- a row the law does not admit, which the
        # aggregation guard correctly refused. The advisory was right; the data
        # was wrong.
        amount=Decimal("200.00"),
        taxable_base=Decimal("200.00"),
        iva_rate=Decimal("0"),
        iva_amount=Decimal("0"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        counterparty_country="DE",
        # Established AND IVA-identified in Germany, which is the ordinary case.
        # Art. 25 exempts on the IDENTIFICATION, so the supply is refused at
        # preflight without it however clear the establishment is; declaring
        # only the establishment is what this fixture used to do.
        counterparty_identification_state=EUMemberState.DE,
    )
    with open_test_profile_session(bucket_id):
        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions((domestic_sale, cuota_less_supply)),
        )
    _seed_zero_iva_wallet_decision(bucket_id)

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
            "--m303-filing-evidence",
            str(evidence_path),
        ],
    )
    assert result.exit_code == 0, result.output

    notices = unwrap_envelope_notices(result.output)
    source_advisories = [notice for notice in notices if notice["code"] == "modelo.work.calculate.source_advisory"]
    assert source_advisories == [], (
        f"INTRA_COMMUNITY_SUPPLY is cuota-less and must not raise a source advisory; got {source_advisories}"
    )

    # Text mode likewise emits no source ADVISORY line for the cuota-less supply.
    # Re-run in text mode against the same seeded bucket; the calculate verb is
    # idempotent over the ledger substrate (it persists a new draft revision but
    # the cuota-less supply stays advisory-free on both transports).
    text_result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
            "--m303-filing-evidence",
            str(evidence_path),
        ],
    )
    assert text_result.exit_code == 0, text_result.output
    assert "ADVISORY:" not in text_result.output


def test_work_calculate_emits_no_advisory_when_all_iva_consumed(tmp_path: Path) -> None:
    """#64 converse: an all-consumed IVA observation set surfaces ZERO advisories.

    Anti-tautology guard for the advisory test above: only observations no
    binding selects produce a diagnostic. A domestic sale matched by the
    repercutido-general binding must leave ``source_advisories`` empty and emit
    no ADVISORY line.
    """
    from ....core.bucket_pointer import resolve_active_bucket_id

    _create_profile()
    work_unit = _create_303_work_unit()
    evidence_path = write_m303_filing_evidence(
        tmp_path / "m303-filing-evidence.json",
        Period.from_year_and_code(2026, "1T"),
    )
    resolved = resolve_active_bucket_id()
    assert resolved is not None, "profile create must install an active-profile pointer"
    bucket_id = resolved

    domestic_sale = _transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    with open_test_profile_session(bucket_id):
        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions((domestic_sale,)),
        )
    _seed_zero_iva_wallet_decision(bucket_id)

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
            "--m303-filing-evidence",
            str(evidence_path),
        ],
    )
    assert result.exit_code == 0, result.output

    notices = unwrap_envelope_notices(result.output)
    assert [n for n in notices if n["code"] == "modelo.work.calculate.source_advisory"] == []

    # Text mode emits no ADVISORY line either: only an unrouted declarable
    # observation produces one, and every observation here was consumed.
    text_result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
            "--m303-filing-evidence",
            str(evidence_path),
        ],
    )
    assert text_result.exit_code == 0, text_result.output
    assert "ADVISORY:" not in text_result.output
