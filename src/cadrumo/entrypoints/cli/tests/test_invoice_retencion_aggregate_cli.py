"""Received-invoice retención reaches Modelo 111 through the aggregate CLI (#45).

``route_invoice_retenciones`` / ``project_received_invoice_retencion``
(``application/aggregation/_invoice_retencion.py``) had zero production callers:
the primitive was correct and covered by
``test_invoice_retencion_routing.py``, but nothing invoked it, so a received
invoice's retención never reached the per-perceptor store Modelo 111 reads. The
gates below assert the CLI wiring end to end -- that the Modelo 111 casilla
value MOVES after routing a real invoice through
``aeat app modelo aggregate --received-invoice-retencion`` -- not merely that
the routing primitive returns a value, which the pre-existing suite already
proved and which is exactly why this gap survived unnoticed.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.secure_sql import isolated_cli_runtime_profile, isolated_runtime_profile
from ....application.aggregation.errors import AggregationValidationError
from ....application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from ....application.aggregation.withholding_observation_service import WithholdingMutationMode
from ....application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from ....application.invoices.catalogue_creation import build_catalogue_invoice, create_catalogue_invoice
from ....application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.work_lifecycle import create_work_unit
from ....core.aggregation import RetencionClave
from ....core.period import Period
from ....core.storage_taxonomy import StorageCategory
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context as _profile_creation_context_for_test,
)
from ....domain.calculations.registry.withholding_bindings import WithholdingObservation
from ....domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....entrypoints.adapter_composition import build_calculation_action_ports, build_retencion_observation_ports
from ....tests.storage_scope import storage_overrides
from .cli_runner import invoke_cached_cli, invoke_uncached_typer_app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_BUCKET_ID = "00000000-0000-4000-8000-000000000452"
_T0 = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
_T1 = datetime(2026, 2, 1, 10, 0, tzinfo=UTC)


def _professional_services_invoice(
    *,
    bucket_id: str,
    kind: InvoiceKind = InvoiceKind.RECEIVED,
    number: str = "F-PROV-900",
    issued_at: date = date(2026, 3, 15),
) -> Invoice:
    subtotal = Decimal("1000.00")
    rate = iva_rate_percentage(IvaRate.from_registry("RATE_21"), date(2026, 1, 1))
    assert rate is not None
    line = InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=subtotal,
        subtotal=subtotal,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=subtotal * rate,
    )
    return Invoice.model_validate(
        {
            "bucket_id": bucket_id,
            "kind": kind,
            "invoice_number": number,
            "issued_at": issued_at,
            "counterparty_name": "Asesoría Profesional SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": subtotal,
            "iva_total": line.iva_amount,
            "grand_total": subtotal + line.iva_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": IvaCategory("domestic_general"),
            "retention_rate": Decimal("0.15"),
            "retention_amount": Decimal("150.00"),
        },
    )


def _withholding_evidence_payload(
    invoice: Invoice,
    *,
    allocation_id: str,
    payment_event_id: str,
    idempotency_key: str,
    mode: WithholdingMutationMode = WithholdingMutationMode.APPEND,
    baseline: dict[str, str] | None = None,
    reason: str | None = None,
    supersedes_generation_id: str | None = None,
) -> str:
    """Build one public CLI capture payload, including mandatory annual detail."""
    annual_detail = WithholdingObservation(
        source_id=invoice.invoice_id,
        perceptor_tax_id=invoice.counterparty_tax_id or "",
        perceptor_legal_name=invoice.counterparty_name,
        transaction_date=date(2025, 3, 31),
        clave=RetencionClave.from_registry("G"),
        percibido_dinerario=Decimal("1000.00"),
        retencion_practicada=Decimal("150.00"),
        incapacity_cash_perception=Decimal("0"),
        incapacity_cash_withholding=Decimal("0"),
        incapacity_kind_value=Decimal("0"),
        incapacity_kind_ingreso_a_cuenta=Decimal("0"),
        incapacity_kind_repercutido=Decimal("0"),
        foral_retention_estatal=Decimal("0"),
        foral_retention_navarra=Decimal("0"),
        foral_retention_araba=Decimal("0"),
        foral_retention_gipuzkoa=Decimal("0"),
        foral_retention_bizkaia=Decimal("0"),
        base_retenciones=Decimal("1000.00"),
        porcentaje_retencion=Decimal("15"),
    )
    request = InvoiceWithholdingEvidenceRequest(
        invoice_id=invoice.invoice_id,
        income_kind=WithholdingIncomeKind.PROFESSIONAL,
        scheme="actividades_profesionales",
        recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
        recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
        payment_event_id=payment_event_id,
        payment_occurred_on=date(2025, 3, 31),
        allocation_id=allocation_id,
        allocated_base=Decimal("1000.00"),
        allocated_withholding=Decimal("150.00"),
        allocated_settlement=Decimal("1060.00"),
        idempotency_key=idempotency_key,
        mode=mode,
        baseline=baseline,
        reason=reason,
        supersedes_generation_id=supersedes_generation_id,
        modelo_190_detail=annual_detail,
    )
    return request.model_dump_json()


def _seed_ready_profile(root: Path) -> None:
    seed_test_profile_record(
        _create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="withholding operator activity"),
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
                UserProfileFact(path="withholding.colegio_concertado", value=False),
            ),
            created_at=_T0,
            updated_at=_T0,
            context=_profile_creation_context_for_test(),
        ),
        root=root,
        label="M111 invoice retención routing",
    )


def _calculate_m111(objects: SecureObjectRepository, period: Period) -> dict[str, Decimal]:
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("111", filing_year=period.filing_year, period="1T")
        wu_repo = WorkUnitCatalogueRepository(objects=objects)
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="111",
            filing_year=period.filing_year,
            period=period,
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=wu_repo,
                bucket_event_repository=BucketEventHistoryRepository(),
            ),
            clock=_T0,
            operation=operation,
        )
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=_BUCKET_ID, operation=operation),
            clock=_T1,
        )
    return dict(result.revision.casilla_values)


def test_received_invoice_routes_through_aggregate_cli_into_m111(tmp_path: Path) -> None:
    """A CLI-routed received invoice's retención reaches the M111 calculate path.

    The per-perceptor store is populated ONLY by invoking
    ``aeat app modelo aggregate --received-invoice-retencion`` -- never by
    seeding ``RetencionObservationRepository`` directly, which is exactly what
    proves the production wiring rather than the pure projection.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M111 invoice retencion") as profile:
        objects: SecureObjectRepository = profile.repository
        _seed_ready_profile(profile.storage_root)
        invoice = _professional_services_invoice(bucket_id=_BUCKET_ID)
        InvoiceCatalogueRepository(objects=objects).save(build_invoice_catalogue([invoice]))

        result = invoke_cached_cli(
            [
                "--language",
                "en",
                "app",
                "modelo",
                "aggregate",
                "--modelo",
                "111",
                "--year",
                "2026",
                "--period",
                "1T",
                "--received-invoice-retencion",
                f'{{"invoice_id": "{invoice.invoice_id}", "scheme": "actividades_profesionales"}}',
            ],
        )
        assert result.exit_code == 0, result.output

        # The CLI resolves the active bucket independently of the injected
        # ``objects`` handle; reading back through the real store confirms the
        # write landed in the same encrypted namespace the calculate path reads.
        stored = build_retencion_observation_ports(bucket_id=_BUCKET_ID).repository.load_observations(
            "111",
            Period.from_year_and_code(2026, "1T"),
        )
        assert len(stored) == 1
        assert stored[0].source_object_id == invoice.invoice_id
        assert stored[0].retencion_amount == Decimal("150.00")

        values = _calculate_m111(objects, Period.from_year_and_code(2026, "1T"))

    assert values["07"] == Decimal("1")
    assert values["08"] == Decimal("1000.00")
    assert values["09"] == Decimal("150.00")
    assert values["28"] == Decimal("150.00")
    assert values["30"] == Decimal("150.00")


def test_aggregate_readback_survives_omission_and_supplies_replace_baseline(tmp_path: Path) -> None:
    """A new CLI command tree reads the exact baseline needed for replacement.

    The readback uses the public aggregate envelope, while the stored state is
    consulted only to prove an omitted invocation did not mutate it.  The
    replacement itself is another public aggregate capture guarded by the
    previously returned baseline, so this exercises the real producer and CAS
    boundary instead of reimplementing either in the test.
    """
    for directory in storage_overrides(
        tmp_path,
        StorageCategory.SECRETS,
        StorageCategory.TOKENS,
        StorageCategory.RUNS,
        StorageCategory.DRAFTS,
        StorageCategory.FINANCIAL_TRANSACTIONS,
        StorageCategory.INVOICES,
    ).values():
        directory.mkdir(parents=True, exist_ok=True)

    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M111 readback") as profile:
        invoice = _professional_services_invoice(
            bucket_id=_BUCKET_ID,
            number="F-PROV-READBACK",
            issued_at=date(2025, 3, 15),
        )
        InvoiceCatalogueRepository(objects=profile.repository).save(build_invoice_catalogue([invoice]))
        first = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "aggregate",
                "--modelo",
                "111",
                "--year",
                "2025",
                "--period",
                "1T",
                "--received-invoice-retencion",
                _withholding_evidence_payload(
                    invoice,
                    allocation_id="readback-first",
                    payment_event_id="readback-payment-first",
                    idempotency_key="readback-first",
                ),
            ]
        )
        assert first.exit_code == 0, first.output
        first_window = json.loads(first.output)["result"]["withholding_window"]
        first_baseline = first_window["baseline"]
        first_generation_id = first_baseline["generation_id"]
        assert first_window["generation"] == 1
        assert first_window["generation_audit"] == {
            "parent_generation_id": "0" * 64,
            "mode": "append",
            "supersedes_generation_id": None,
        }
        assert "1000.00" not in json.dumps(first_window)
        assert "150.00" not in json.dumps(first_window)

        replay = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "aggregate",
                "--modelo",
                "111",
                "--year",
                "2025",
                "--period",
                "1T",
                "--received-invoice-retencion",
                _withholding_evidence_payload(
                    invoice,
                    allocation_id="readback-first",
                    payment_event_id="readback-payment-first",
                    idempotency_key="readback-first",
                ),
            ]
        )
        assert replay.exit_code == 0, replay.output
        assert json.loads(replay.output)["result"]["withholding_window"] == first_window

        # A freshly materialised command tree shares no Click command cache
        # with the capture invocation. It omits all capture input and must
        # therefore read the persisted token without creating a generation.
        from ..main import app

        omitted = invoke_uncached_typer_app(
            app,
            [
                "--format",
                "json",
                "app",
                "modelo",
                "aggregate",
                "--modelo",
                "111",
                "--year",
                "2025",
                "--period",
                "1T",
            ],
        )
        assert omitted.exit_code == 0, omitted.output
        omitted_window = json.loads(omitted.output)["result"]["withholding_window"]
        assert omitted_window == first_window

        replaced = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "aggregate",
                "--modelo",
                "111",
                "--year",
                "2025",
                "--period",
                "1T",
                "--received-invoice-retencion",
                _withholding_evidence_payload(
                    invoice,
                    allocation_id="readback-replacement",
                    payment_event_id="readback-payment-replacement",
                    idempotency_key="readback-replacement",
                    mode=WithholdingMutationMode.REPLACE,
                    baseline=first_baseline,
                    reason="corrected allocation",
                    supersedes_generation_id=first_generation_id,
                ),
            ]
        )
        assert replaced.exit_code == 0, replaced.output
        replacement_window = json.loads(replaced.output)["result"]["withholding_window"]

        stale = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "aggregate",
                "--modelo",
                "111",
                "--year",
                "2025",
                "--period",
                "1T",
                "--received-invoice-retencion",
                _withholding_evidence_payload(
                    invoice,
                    allocation_id="readback-stale",
                    payment_event_id="readback-payment-stale",
                    idempotency_key="readback-stale",
                    mode=WithholdingMutationMode.REPLACE,
                    baseline=first_baseline,
                    reason="stale correction",
                    supersedes_generation_id=first_generation_id,
                ),
            ]
        )
        assert stale.exit_code != 0
        after_stale = invoke_uncached_typer_app(
            app,
            ["--format", "json", "app", "modelo", "aggregate", "--modelo", "111", "--year", "2025", "--period", "1T"],
        )
        assert after_stale.exit_code == 0, after_stale.output
        assert json.loads(after_stale.output)["result"]["withholding_window"] == replacement_window

    assert replacement_window["generation"] == 2
    assert replacement_window["baseline"]["generation_id"] != first_generation_id
    assert replacement_window["generation_audit"] == {
        "parent_generation_id": first_generation_id,
        "mode": "replace",
        "supersedes_generation_id": first_generation_id,
    }


def test_excluded_invoice_retencion_is_not_routed_and_surfaces_a_notice(tmp_path: Path) -> None:
    """An issued invoice's retención is a CREDIT, not a retenedor liability, and is refused routing.

    Excluding it must surface as a warning notice naming the invoice rather than
    silently dropping it -- an excluded retención is a liability the taxpayer
    may still owe.
    """
    issued = _professional_services_invoice(bucket_id=_BUCKET_ID, kind=InvoiceKind.ISSUED, number="F-CLI-002")

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M111 invoice retencion") as profile:
        objects: SecureObjectRepository = profile.repository
        InvoiceCatalogueRepository(objects=objects).save(build_invoice_catalogue([issued]))

        result = invoke_cached_cli(
            [
                "--language",
                "en",
                "app",
                "modelo",
                "aggregate",
                "--modelo",
                "111",
                "--year",
                "2026",
                "--period",
                "1T",
                "--received-invoice-retencion",
                f'{{"invoice_id": "{issued.invoice_id}", "scheme": "actividades_profesionales"}}',
            ],
        )

        assert result.exit_code == 0, result.output
        assert "not_a_retenedor_liability" in result.output
        assert issued.invoice_id in result.output

        stored = build_retencion_observation_ports(bucket_id=_BUCKET_ID).repository.load_observations(
            "111",
            Period.from_year_and_code(2026, "1T"),
        )
        assert stored == ()


def _producer_created_invoice(
    *,
    objects: SecureObjectRepository,
    number: str,
    retention_rate: Decimal | None,
    retention_amount: Decimal | None,
) -> Invoice:
    """Mint the invoice through the real application producer (#66).

    :func:`create_catalogue_invoice` is the exact function both
    ``catalogue create`` and ``catalogue wizard`` call, so exercising
    ``retention_rate``/``retention_amount`` through it -- rather than a
    hand-built ``Invoice.model_validate`` -- proves the producer this test
    wires, not merely that the model accepts the fields (which
    ``test_invoice_retencion_routing.py`` already proved at the model
    boundary).

    ``iva_category`` is supplied directly rather than through a CLI option:
    no shipped CLI verb can set a DOMESTIC IVA category on a catalogue
    invoice today (``catalogue create``/``wizard`` derive it only from an
    intra-community ``--operation-type``, which never resolves to a domestic
    category) -- a separate, already-tracked gap, not
    something this test's producer is responsible for.
    """
    catalogue_ports = build_catalogue_creation_ports(bucket_id=_BUCKET_ID)
    with bundled_indexed_authority().operation() as operation:
        invoice = build_catalogue_invoice(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            counterparty_name="Asesoría Profesional SL",
            counterparty_tax_id="B12345674",
            counterparty_country="ES",
            invoice_number=number,
            issued_at=date(2026, 3, 15),
            taxable_base=Decimal("1000.00"),
            iva_rate=Decimal("21"),
            currency="EUR",
            iva_category=IvaCategory("domestic_general"),
            retention_rate=retention_rate,
            retention_amount=retention_amount,
            rate_provider=catalogue_ports.rate_provider,
            operation=operation,
        )
    result = create_catalogue_invoice(invoice=invoice, ports=catalogue_ports)
    return result.invoice


def test_producer_created_invoice_routes_through_aggregate_cli_into_m111(tmp_path: Path) -> None:
    """The new retention_rate/retention_amount producer (#66) reaches M111.

    Mutation-proof companion:
    :func:`test_producer_without_retention_is_excluded_from_m111` builds the
    identical invoice through the identical producer call, differing only in
    ``retention_rate``/``retention_amount`` being ``None`` -- disabling the
    producer's output reddens the M111 casilla assertions below.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M111 producer retencion") as profile:
        objects: SecureObjectRepository = profile.repository
        _seed_ready_profile(profile.storage_root)
        invoice = _producer_created_invoice(
            objects=objects,
            number="F-PROV-CLI-901",
            retention_rate=Decimal("0.15"),
            retention_amount=Decimal("150.00"),
        )

        result = invoke_cached_cli(
            [
                "--language",
                "en",
                "app",
                "modelo",
                "aggregate",
                "--modelo",
                "111",
                "--year",
                "2026",
                "--period",
                "1T",
                "--received-invoice-retencion",
                f'{{"invoice_id": "{invoice.invoice_id}", "scheme": "actividades_profesionales"}}',
            ],
        )
        assert result.exit_code == 0, result.output

        stored = build_retencion_observation_ports(bucket_id=_BUCKET_ID).repository.load_observations(
            "111",
            Period.from_year_and_code(2026, "1T"),
        )
        assert len(stored) == 1
        assert stored[0].source_object_id == invoice.invoice_id
        assert stored[0].retencion_amount == Decimal("150.00")

        values = _calculate_m111(objects, Period.from_year_and_code(2026, "1T"))

    assert values["07"] == Decimal("1")
    assert values["08"] == Decimal("1000.00")
    assert values["09"] == Decimal("150.00")
    assert values["28"] == Decimal("150.00")
    assert values["30"] == Decimal("150.00")


def test_producer_without_retention_is_excluded_from_m111(tmp_path: Path) -> None:
    """Mutation proof: the identical invoice, minus the producer's amount, never reaches M111.

    Same producer call, same base/rate/counterparty/category as
    :func:`test_producer_created_invoice_routes_through_aggregate_cli_into_m111`
    -- only ``retention_rate``/``retention_amount`` differ (both ``None``,
    the pre-#66 state). The invoice is excluded for ``no_retencion_declared``,
    so the per-perceptor store stays empty and the M111 calculate path refuses
    for want of any observation rather than emitting an all-blank filing.

    The refusal is the mutation signal. Its companion above calculates
    successfully and moves the casillas, so the two outcomes still discriminate:
    routing a retención produces values, routing an invoice without one produces
    no observation at all. Asserting zeroed casillas here would instead require
    the silent zero the resolver deliberately refuses.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M111 producer retencion") as profile:
        objects: SecureObjectRepository = profile.repository
        _seed_ready_profile(profile.storage_root)
        invoice = _producer_created_invoice(
            objects=objects,
            number="F-PROV-CLI-902",
            retention_rate=None,
            retention_amount=None,
        )

        result = invoke_cached_cli(
            [
                "--language",
                "en",
                "app",
                "modelo",
                "aggregate",
                "--modelo",
                "111",
                "--year",
                "2026",
                "--period",
                "1T",
                "--received-invoice-retencion",
                f'{{"invoice_id": "{invoice.invoice_id}", "scheme": "actividades_profesionales"}}',
            ],
        )
        assert result.exit_code == 0, result.output
        assert "no_retencion_declared" in result.output
        assert invoice.invoice_id in result.output

        stored = build_retencion_observation_ports(bucket_id=_BUCKET_ID).repository.load_observations(
            "111",
            Period.from_year_and_code(2026, "1T"),
        )
        assert stored == ()

        with pytest.raises(AggregationValidationError) as exc_info:
            _calculate_m111(objects, Period.from_year_and_code(2026, "1T"))

    assert exc_info.value.translated_message == "aggregation.retenciones.errors.m111_no_retenciones_attestation_missing"
    context = exc_info.value.context
    assert context is not None, "the refusal must carry its context, not just a message"
    assert context["modelo"] == "111"
    assert context["period"] == "1T"
    assert not hasattr(exc_info.value, "suggestion")
    verdict = exc_info.value.terminal_precondition_verdict
    assert verdict is not None, "the refusal must carry its typed precondition verdict"
