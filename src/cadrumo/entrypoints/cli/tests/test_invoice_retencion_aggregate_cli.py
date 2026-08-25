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

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....application.aggregation import AggregationValidationError, RetencionObservationRepository
from ....application.invoices import build_catalogue_invoice, create_catalogue_invoice
from ....application.modelo._calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo._work_lifecycle import create_work_unit
from ....core import Period
from ....core.resources import resources
from ....domain.invoices import Invoice, InvoiceCatalogue, InvoiceLine, IvaRate, PaymentStatus, iva_rate_percentage
from ....domain.iva import InvoiceKind, IvaCategory
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "00000000-0000-4000-8000-000000000452"
_T0 = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
_T1 = datetime(2026, 2, 1, 10, 0, tzinfo=UTC)


def _professional_services_invoice(
    *,
    bucket_id: str,
    kind: InvoiceKind = InvoiceKind.RECEIVED,
    number: str = "F-PROV-900",
) -> Invoice:
    subtotal = Decimal("1000.00")
    rate = iva_rate_percentage(IvaRate.RATE_21)
    assert rate is not None
    line = InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=subtotal,
        subtotal=subtotal,
        iva_rate=IvaRate.RATE_21,
        iva_amount=subtotal * rate,
    )
    return Invoice.model_validate(
        {
            "bucket_id": bucket_id,
            "kind": kind,
            "invoice_number": number,
            "issued_at": date(2026, 3, 15),
            "counterparty_name": "Asesoría Profesional SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": subtotal,
            "iva_total": line.iva_amount,
            "grand_total": subtotal + line.iva_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": IvaCategory.DOMESTIC_GENERAL,
            "retention_rate": Decimal("0.15"),
            "retention_amount": Decimal("150.00"),
        },
    )


def _seed_ready_profile(root: Path) -> None:
    seed_test_profile_record(
        UserProfileRecord(
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
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
        root=root,
        label="M111 invoice retención routing",
    )


def _calculate_m111(objects: SecureObjectRepository, period: Period) -> dict[str, Decimal]:
    snapshot = resources().modelos.authority.snapshot("111", filing_year=period.filing_year, period="1T")
    wu_repo = WorkUnitCatalogueRepository(objects=objects)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="111",
        filing_year=period.filing_year,
        period=period,
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
        invoice_repository=InvoiceCatalogueRepository(objects=objects),
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
        InvoiceCatalogueRepository(objects=objects).save(InvoiceCatalogue.from_invoices([invoice]))

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
        stored = RetencionObservationRepository(objects=objects).load_observations(
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


def test_excluded_invoice_retencion_is_not_routed_and_surfaces_a_notice(tmp_path: Path) -> None:
    """An issued invoice's retención is a CREDIT, not a retenedor liability, and is refused routing.

    Excluding it must surface as a warning notice naming the invoice rather than
    silently dropping it -- an excluded retención is a liability the taxpayer
    may still owe.
    """
    issued = _professional_services_invoice(bucket_id=_BUCKET_ID, kind=InvoiceKind.ISSUED, number="F-CLI-002")

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M111 invoice retencion") as profile:
        objects: SecureObjectRepository = profile.repository
        InvoiceCatalogueRepository(objects=objects).save(InvoiceCatalogue.from_invoices([issued]))

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

        stored = RetencionObservationRepository(objects=objects).load_observations(
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
    result = create_catalogue_invoice(
        invoice=build_catalogue_invoice(
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
            iva_category=IvaCategory.DOMESTIC_GENERAL,
            retention_rate=retention_rate,
            retention_amount=retention_amount,
        ),
        repository=InvoiceCatalogueRepository(objects=objects),
    )
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

        stored = RetencionObservationRepository(objects=objects).load_observations(
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

        stored = RetencionObservationRepository(objects=objects).load_observations(
            "111",
            Period.from_year_and_code(2026, "1T"),
        )
        assert stored == ()

        with pytest.raises(AggregationValidationError) as exc_info:
            _calculate_m111(objects, Period.from_year_and_code(2026, "1T"))

    assert exc_info.value.translated_message == "aggregation.retenciones.errors.perceptor_observations_missing"
    context = exc_info.value.context
    assert context is not None, "the refusal must carry its context, not just a message"
    assert context["modelo"] == "111"
    assert context["period"] == "1T"
    assert not hasattr(exc_info.value, "suggestion")
    verdict = exc_info.value.terminal_precondition_verdict
    assert verdict is not None, "the refusal must carry its typed precondition verdict"
