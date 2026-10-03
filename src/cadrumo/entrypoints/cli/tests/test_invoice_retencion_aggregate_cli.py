"""Received-invoice retención reaches Modelo 111 through the aggregate CLI (#45).

``build_invoice_withholding_capture``
(``application/aggregation/invoice_retencion.py``) is only a translation: it
turns one invoice into the shared producer's capture command and writes nothing
itself. A unit test of that translation cannot show a received invoice's
retención reaching the per-perceptor store Modelo 111 reads. The gates below
assert the CLI wiring end to end -- that the Modelo 111 casilla value MOVES
after capturing a real invoice through
``aeat app modelo aggregate --received-invoice-retencion`` -- not merely that
the translation returns a command, which is exactly the gap that once let an
unwired projection survive unnoticed.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from cadrumo.application.modelo.invoice_withholding_capture_operation import (
    MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
)
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo.application.user_profile.tests.profile_values import complete_profile_facts
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
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
from ....core.i18n.render import lookup_translation
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.withholding_bindings import WithholdingObservation
from ....domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ...adapter_composition import build_calculation_action_ports, build_retencion_observation_ports
from .native_api_cli_support import native_api_cli_session
from .test_runtime_invoice_add import password_profile_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_T0 = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
_T1 = datetime(2026, 2, 1, 10, 0, tzinfo=UTC)
_M111_PERIOD = Period.from_year_and_code(2025, "1T")


def _professional_services_invoice(
    *,
    bucket_id: str,
    kind: InvoiceKind = InvoiceKind.RECEIVED,
    number: str = "F-PROV-900",
    issued_at: date = date(2025, 3, 15),
    counterparty_country: str = "ES",
    counterparty_tax_id: str = "B12345674",
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
            "counterparty_tax_id": counterparty_tax_id,
            "counterparty_country": counterparty_country,
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


_M111_PROFILE_FACTS = (
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
)


def _capture_scope(client_id: UUID) -> AccessScope:
    """Grant only invoice capture, with all-period catalogue lookup authority."""
    return AccessScope(
        operations=frozenset({MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID}),
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.COMMIT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
        ),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=f"{MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID}.result",
                    category=DisclosureCategory.TAX_VALUES,
                ),
            }
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _m111_capture_profile_preparer(
    authority_operation: PinnedAuthorityOperation,
    invoice_factory: Callable[[str], Invoice],
    *,
    save_invoice: bool = True,
) -> Callable[[UUID, Path], Invoice]:
    """Complete one registered profile and seed its invoice catalogue."""

    def prepare(profile_id: UUID, root: Path) -> Invoice:
        facts = complete_profile_facts(authority_operation.profile_schema(), _M111_PROFILE_FACTS)
        populated = upsert_test_profile_facts(profile_id, facts, root=root)
        with bound_test_profile_record(profile_id, root=root) as repository:
            ready = repository.complete_setup(
                populated.profile_id,
                expected_revision=populated.record_revision,
                expected_content_digest=populated.content_digest,
            )
        assert ready.setup_state is ProfileSetupState.COMPLETE

        invoice = invoice_factory(str(profile_id))
        if save_invoice:
            InvoiceCatalogueRepository(bucket_id=str(profile_id)).save(build_invoice_catalogue([invoice]))
        return invoice

    return prepare


def _calculate_m111(bucket_id: str, period: Period) -> dict[str, Decimal]:
    objects = secure_object_repository_for_bucket(bucket_id)
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("111", filing_year=period.filing_year, period="1T")
        wu_repo = WorkUnitCatalogueRepository(bucket_id=bucket_id, objects=objects)
        work_unit = create_work_unit(
            bucket_id=bucket_id,
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
            ports=build_calculation_action_ports(bucket_id=bucket_id, operation=operation),
            clock=_T1,
        )
    return dict(result.revision.casilla_values)


def test_received_invoice_routes_through_aggregate_cli_into_m111(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A CLI-routed received invoice's retención reaches the M111 calculate path.

    The per-perceptor store is populated ONLY by invoking
    ``aeat app modelo aggregate --received-invoice-retencion`` -- never by
    seeding ``RetencionObservationRepository`` directly, which is exactly what
    proves the production wiring rather than the pure projection.
    """
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_capture_scope,
        prepare_profile=_m111_capture_profile_preparer(
            authority_operation,
            lambda bucket_id: _professional_services_invoice(bucket_id=bucket_id),
        ),
    ) as session:
        invoice = session.prepared
        result = session.invoke_password(
            "--language",
            "en",
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
                allocation_id="allocation-routed",
                payment_event_id="payment-routed",
                idempotency_key="capture-routed",
            ),
        )
        assert result.exit_code == 0, result.output

        with password_profile_session(session.profile_id, authority_operation):
            stored = build_retencion_observation_ports(bucket_id=str(session.profile_id)).repository.load_observations(
                "111",
                _M111_PERIOD,
            )
            assert len(stored) == 1
            assert stored[0].source_object_id == invoice.invoice_id
            assert stored[0].retencion_amount == Decimal("150.00")

            values = _calculate_m111(str(session.profile_id), _M111_PERIOD)

    assert values["07"] == Decimal("1")
    assert values["08"] == Decimal("1000.00")
    assert values["09"] == Decimal("150.00")
    assert values["28"] == Decimal("150.00")
    assert values["30"] == Decimal("150.00")


def test_aggregate_readback_survives_omission_and_supplies_replace_baseline(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The aggregate CLI reads the exact baseline needed for replacement.

    The readback uses the public aggregate envelope, while the stored state is
    consulted only to prove an omitted invocation did not mutate it.  The
    replacement itself is another public aggregate capture guarded by the
    previously returned baseline, so this exercises the real producer and CAS
    boundary instead of reimplementing either in the test.
    """
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_capture_scope,
        prepare_profile=_m111_capture_profile_preparer(
            authority_operation,
            lambda bucket_id: _professional_services_invoice(
                bucket_id=bucket_id,
                number="F-PROV-READBACK",
                issued_at=date(2025, 3, 15),
            ),
        ),
    ) as session:
        invoice = session.prepared
        first = session.invoke_password(
            "--language",
            "en",
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

        replay = session.invoke_password(
            "--language",
            "en",
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
        )
        assert replay.exit_code == 0, replay.output
        assert json.loads(replay.output)["result"]["withholding_window"] == first_window

        omitted = session.invoke_password(
            "--language", "en", "app", "modelo", "aggregate", "--modelo", "111", "--year", "2025", "--period", "1T"
        )
        assert omitted.exit_code == 0, omitted.output
        omitted_window = json.loads(omitted.output)["result"]["withholding_window"]
        assert omitted_window == first_window

        replaced = session.invoke_password(
            "--language",
            "en",
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
        )
        assert replaced.exit_code == 0, replaced.output
        replacement_window = json.loads(replaced.output)["result"]["withholding_window"]

        stale = session.invoke_password(
            "--language",
            "en",
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
        )
        assert stale.exit_code != 0
        after_stale = session.invoke_password(
            "--language", "en", "app", "modelo", "aggregate", "--modelo", "111", "--year", "2025", "--period", "1T"
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


def test_issued_invoice_retencion_is_refused_and_not_routed(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """An issued invoice's retención is a CREDIT, not a retenedor liability, and is refused routing.

    The refusal names its reason rather than dropping the evidence silently,
    and nothing reaches the per-perceptor store.
    """
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_capture_scope,
        prepare_profile=_m111_capture_profile_preparer(
            authority_operation,
            lambda bucket_id: _professional_services_invoice(
                bucket_id=bucket_id,
                kind=InvoiceKind.ISSUED,
                number="F-CLI-002",
            ),
        ),
    ) as session:
        issued = session.prepared
        result = session.invoke_password(
            "--language",
            "en",
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
                issued,
                allocation_id="allocation-issued",
                payment_event_id="payment-issued",
                idempotency_key="capture-issued",
            ),
        )

        assert result.exit_code == 2, result.output
        assert "not_a_retenedor_liability" in result.output, result.output

        with password_profile_session(session.profile_id, authority_operation):
            stored = build_retencion_observation_ports(bucket_id=str(session.profile_id)).repository.load_observations(
                "111",
                _M111_PERIOD,
            )
            assert stored == ()


@pytest.mark.parametrize("language", ("en", "es"))
def test_an_invoice_with_two_defects_is_refused_naming_both(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    language: str,
) -> None:
    """An issued invoice from a non-resident is refused once, with both defects, in the operator's language.

    The refusal crosses the profile worker as stable defect tokens and reaches
    the registered error envelope rather than a flattened argument error, so a
    machine reads every defect token and a person reads every explanation, and
    nothing reaches the per-perceptor store.
    """
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_capture_scope,
        prepare_profile=_m111_capture_profile_preparer(
            authority_operation,
            lambda bucket_id: _professional_services_invoice(
                bucket_id=bucket_id,
                kind=InvoiceKind.ISSUED,
                number="F-CLI-003",
                counterparty_country="PT",
                counterparty_tax_id="PT123456789",
            ),
        ),
    ) as session:
        issued_abroad = session.prepared
        result = session.invoke_password(
            "--language",
            language,
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
                issued_abroad,
                allocation_id="allocation-issued-abroad",
                payment_event_id="payment-issued-abroad",
                idempotency_key="capture-issued-abroad",
            ),
        )

        assert result.exit_code == 2, result.output
        error = json.loads(result.output)["error"]
        assert error["code"] == "REFUSED_INVOICE_WITHHOLDING_DEFECTS", error
        assert error["context"]["refusal_code"] == "not_a_retenedor_liability,non_resident_supplier"
        for defect in ("not_a_retenedor_liability", "non_resident_supplier"):
            reason = lookup_translation(f"aggregation.invoice_retencion.defects.{defect}", locale=language)
            assert reason is not None, defect
            assert reason in error["context"]["defect_reasons"], error

        with password_profile_session(session.profile_id, authority_operation):
            stored = build_retencion_observation_ports(bucket_id=str(session.profile_id)).repository.load_observations(
                "111",
                _M111_PERIOD,
            )
            assert stored == ()


def _producer_created_invoice(
    *,
    bucket_id: str,
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
    catalogue_ports = build_catalogue_creation_ports(bucket_id=bucket_id)
    with bundled_indexed_authority().operation() as operation:
        invoice = build_catalogue_invoice(
            bucket_id=bucket_id,
            kind=InvoiceKind.RECEIVED,
            counterparty_name="Asesoría Profesional SL",
            counterparty_tax_id="B12345674",
            counterparty_country="ES",
            invoice_number=number,
            issued_at=date(2025, 3, 15),
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


def test_producer_created_invoice_routes_through_aggregate_cli_into_m111(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The new retention_rate/retention_amount producer (#66) reaches M111.

    Mutation-proof companion:
    :func:`test_producer_without_retention_is_excluded_from_m111` builds the
    identical invoice through the identical producer call, differing only in
    ``retention_rate``/``retention_amount`` being ``None`` -- disabling the
    producer's output reddens the M111 casilla assertions below.
    """
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_capture_scope,
        prepare_profile=_m111_capture_profile_preparer(
            authority_operation,
            lambda bucket_id: _producer_created_invoice(
                bucket_id=bucket_id,
                number="F-PROV-CLI-901",
                retention_rate=Decimal("0.15"),
                retention_amount=Decimal("150.00"),
            ),
            save_invoice=False,
        ),
    ) as session:
        invoice = session.prepared
        result = session.invoke_password(
            "--language",
            "en",
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
                allocation_id="allocation-producer",
                payment_event_id="payment-producer",
                idempotency_key="capture-producer",
            ),
        )
        assert result.exit_code == 0, result.output

        with password_profile_session(session.profile_id, authority_operation):
            stored = build_retencion_observation_ports(bucket_id=str(session.profile_id)).repository.load_observations(
                "111",
                _M111_PERIOD,
            )
            assert len(stored) == 1
            assert stored[0].source_object_id == invoice.invoice_id
            assert stored[0].retencion_amount == Decimal("150.00")

            values = _calculate_m111(str(session.profile_id), _M111_PERIOD)

    assert values["07"] == Decimal("1")
    assert values["08"] == Decimal("1000.00")
    assert values["09"] == Decimal("150.00")
    assert values["28"] == Decimal("150.00")
    assert values["30"] == Decimal("150.00")


def test_producer_without_retention_is_excluded_from_m111(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Mutation proof: the identical invoice, minus the producer's amount, never reaches M111.

    Same producer call, same base/rate/counterparty/category as
    :func:`test_producer_created_invoice_routes_through_aggregate_cli_into_m111`
    -- only ``retention_rate``/``retention_amount`` differ (both ``None``,
    the pre-#66 state). The capture is refused for ``no_retencion_declared``,
    so the per-perceptor store stays empty and the M111 calculate path refuses
    for want of any observation rather than emitting an all-blank filing.

    The refusal is the mutation signal. Its companion above calculates
    successfully and moves the casillas, so the two outcomes still discriminate:
    routing a retención produces values, routing an invoice without one produces
    no observation at all. Asserting zeroed casillas here would instead require
    the silent zero the resolver deliberately refuses.
    """
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_capture_scope,
        prepare_profile=_m111_capture_profile_preparer(
            authority_operation,
            lambda bucket_id: _producer_created_invoice(
                bucket_id=bucket_id,
                number="F-PROV-CLI-902",
                retention_rate=None,
                retention_amount=None,
            ),
            save_invoice=False,
        ),
    ) as session:
        invoice = session.prepared
        result = session.invoke_password(
            "--language",
            "en",
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
                allocation_id="allocation-unwithheld",
                payment_event_id="payment-unwithheld",
                idempotency_key="capture-unwithheld",
            ),
        )
        assert result.exit_code == 2, result.output
        assert "no_retencion_declared" in result.output

        with password_profile_session(session.profile_id, authority_operation):
            stored = build_retencion_observation_ports(bucket_id=str(session.profile_id)).repository.load_observations(
                "111",
                _M111_PERIOD,
            )
            assert stored == ()

            with pytest.raises(AggregationValidationError) as exc_info:
                _calculate_m111(str(session.profile_id), _M111_PERIOD)

    assert exc_info.value.translated_message == "aggregation.retenciones.errors.m111_no_retenciones_attestation_missing"
    context = exc_info.value.context
    assert context is not None, "the refusal must carry its context, not just a message"
    assert context["modelo"] == "111"
    assert context["period"] == "1T"
    assert not hasattr(exc_info.value, "suggestion")
    verdict = exc_info.value.terminal_precondition_verdict
    assert verdict is not None, "the refusal must carry its typed precondition verdict"
