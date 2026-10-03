"""Lossless, closed public projections for evidence extraction and confirmation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.exchange_rate_provider import exchange_rate_provider
from cadrumo.application.invoices.catalogue_creation import build_catalogue_invoice
from cadrumo.application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from cadrumo.application.ledger.classification_assembly import (
    ClassificationAssembly,
    DeclaredFact,
    DeclaredFacts,
    IvaCategoryResolution,
)
from cadrumo.application.ledger.confirm_establishment import ConfirmedEstablishment
from cadrumo.application.ledger.confirmation_gate import ConfirmationBlocker
from cadrumo.application.ledger.counterparty_establishment import CounterpartyEstablishmentContradiction
from cadrumo.application.ledger.establishment_ladder import (
    CounterpartyEstablishment,
    RegistrationEstablishmentConflict,
)
from cadrumo.application.ledger.evidence_draft import PrintedTotalDiscrepancy
from cadrumo.application.ledger.invoice_confirmation import InvoiceConfirmationResult
from cadrumo.application.ledger.invoice_draft_records import (
    DraftDiscrepancyFinding,
    FieldAmbiguityCandidate,
    FieldProvenance,
    InvoiceDraft,
    InvoiceDraftLine,
    InvoiceDraftRateBreakdown,
)
from cadrumo.application.ledger.invoice_evidence_operation_dtos import (
    ConfirmedEstablishmentProjectionV1,
    CounterpartyEstablishmentProjectionV1,
    InvoiceConfirmationProjectionV1,
    InvoiceDraftProjectionV1,
)
from cadrumo.application.ledger.structured_invoice_ports import (
    StructuredInvoiceClassification,
    StructuredInvoiceClassificationKind,
)
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.registry import OperationSchemaBindingV1
from cadrumo.application.operations.registry_schema_validation import strict_model_json_schema
from cadrumo.core.classifier_input_source import ClassifierInputSource
from cadrumo.core.confirmation_gate import ConfirmationBlockReason
from cadrumo.core.draft_discrepancy import DraftDiscrepancyKind
from cadrumo.core.field_grounding import FieldGroundingOutcome
from cadrumo.core.field_origin import FieldOrigin
from cadrumo.core.iva_category_resolution import IvaCategoryOutcome
from cadrumo.domain.iva.classification import (
    CustomerTaxStatus,
    InvoiceKind,
    IvaInvoiceClassificationCriteria,
    IvaTerritorialScope,
    TransactionKind,
)
from cadrumo.domain.iva.schema import EUMemberState, IvaCategory, IvaRateKind
from cadrumo.domain.iva.supply_nature import SupplyNature

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _draft() -> InvoiceDraft:
    draft = InvoiceDraft(
        supplier_tax_id="A58818501",
        supplier_name="Papeleria Sol SL",
        customer_tax_id="B12345674",
        customer_name="Cliente Ejemplo SL",
        supplier_postal_code="08001",
        customer_postal_code="28001",
        supplier_country="España",
        customer_country="España",
        supplier_country_code="ES",
        customer_country_code="ES",
        supplier_stated_country_code="ESP",
        customer_stated_country_code="ES",
        invoice_number="F-2026-0142",
        invoice_series="F",
        rectifies_invoice_number="F-2026-0100",
        proposed_supply_nature=SupplyNature.GOODS,
        invoice_date="2026-03-10",
        taxable_base=Decimal("137.25"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("28.82"),
        grand_total=Decimal("166.07"),
        currency="EUR",
        regime_legend="Régimen general",
        recargo_amount=Decimal("0.00"),
        retencion_rate=Decimal("0"),
        retencion_amount=Decimal("0.00"),
        suplidos_amount=Decimal("0.00"),
        lines=(
            InvoiceDraftLine(
                description="Material de oficina",
                quantity=Decimal("2"),
                unit_price=Decimal("68.625"),
                taxable_base=Decimal("137.25"),
                iva_rate=Decimal("21"),
                iva_amount=Decimal("28.82"),
                recargo_rate=Decimal("0"),
                recargo_amount=Decimal("0.00"),
            ),
        ),
        iva_breakdown=(
            InvoiceDraftRateBreakdown(
                iva_rate=Decimal("21"),
                taxable_base=Decimal("137.25"),
                iva_amount=Decimal("28.82"),
                recargo_rate=Decimal("0"),
                recargo_amount=Decimal("0.00"),
            ),
        ),
        iva_category="domestic_standard",
        suggested_kind=InvoiceKind.RECEIVED,
        transcription_sha256="a" * 64,
        provenance=(
            FieldProvenance(
                field="supplier_tax_id",
                origin=FieldOrigin.EXACT_STRUCTURED,
                grounding=FieldGroundingOutcome.ANCHORED,
                anchor="A58818501",
                role_evidence="Proveedor A58818501",
            ),
            FieldProvenance(
                field="taxable_base",
                origin=FieldOrigin.DERIVED,
                grounding=FieldGroundingOutcome.RECONCILED,
                derived_from=("lines.taxable_base",),
                note="Sum of structured line bases",
            ),
        ),
        discrepancies=(
            DraftDiscrepancyFinding(
                kind=DraftDiscrepancyKind.ARITHMETIC_CLOSURE,
                field="grand_total",
                detail="The printed total differs from the draft components.",
                expected=Decimal("166.07"),
                observed=Decimal("166.08"),
            ),
        ),
        raw_text_length=8192,
    )
    draft.set_facturae_invoice_class(
        StructuredInvoiceClassification(
            source_code="R1",
            kind=StructuredInvoiceClassificationKind.CORRECTIVE,
        ),
    )
    return draft


def _establishment() -> ConfirmedEstablishment:
    scope = IvaTerritorialScope("mainland", _registry_validated=True)
    other_scope = IvaTerritorialScope("canary_islands", _registry_validated=True)
    member_state = EUMemberState.from_registry("ES")
    tax_status = CustomerTaxStatus("b2b_registered", _registry_validated=True)
    category_token = IvaCategory("domestic_standard")
    category = DeclaredFact[IvaCategory](
        value=category_token,
        source=ClassifierInputSource.DOCUMENT_EVIDENCE,
    )
    criteria = IvaInvoiceClassificationCriteria(
        transaction_date=date(2026, 3, 10),
        issuer_residency=scope,
        customer_residency=other_scope,
        customer_tax_status=tax_status,
        kind=TransactionKind("goods"),
        direction=InvoiceKind.RECEIVED,
        rate_tier=IvaRateKind("general"),
    )
    declared = DeclaredFacts(
        supply_nature=DeclaredFact(value=SupplyNature.GOODS, source=ClassifierInputSource.DOCUMENT_EVIDENCE),
        customer_tax_status=DeclaredFact(value=tax_status, source=ClassifierInputSource.DOCUMENT_EVIDENCE),
        issuer_scope=DeclaredFact(value=scope, source=ClassifierInputSource.DOCUMENT_EVIDENCE),
        customer_scope=DeclaredFact(value=other_scope, source=ClassifierInputSource.OPERATOR_ASSERTION),
        issuer_identification_state=DeclaredFact(
            value=member_state,
            source=ClassifierInputSource.DOCUMENT_EVIDENCE,
        ),
        customer_identification_state=DeclaredFact(
            value=member_state,
            source=ClassifierInputSource.DOCUMENT_EVIDENCE,
        ),
        stated_category=category,
    )
    contradiction = CounterpartyEstablishmentContradiction(
        counterparty_key="b" * 64,
        canonical_tax_identifier="B12345674",
        confirmed_scope=other_scope,
        evidenced_scope=scope,
        detail="The remembered territory conflicts with this document.",
    )
    counterparty = CounterpartyEstablishment(
        scope=None,
        rung=None,
        source=None,
        contradiction=contradiction,
        identification_state=member_state,
    )
    classification = IvaCategoryResolution(
        outcome=IvaCategoryOutcome.CONTRADICTED,
        category=None,
        classified=IvaCategory("standard_rate"),
        declared=category,
        note="The document declaration conflicts with the classified result.",
    )
    blocker = ConfirmationBlocker(
        blocker_id="c" * 16,
        reason=ConfirmationBlockReason.UNDETERMINED_ESTABLISHMENT,
        field="counterparty_country_code",
        detail="A person must resolve the territory.",
        candidates=(
            FieldAmbiguityCandidate(value="mainland", note="Address evidence"),
            FieldAmbiguityCandidate(value="canary_islands", note="Remembered fact"),
        ),
    )
    return ConfirmedEstablishment(
        counterparty=counterparty,
        filer_scope=other_scope,
        declared=declared,
        assembly=ClassificationAssembly(criteria=criteria),
        category=classification,
        review_items=(blocker,),
    )


def _invoice():
    return build_catalogue_invoice(
        bucket_id="20202020-2020-4202-8202-202020202020",
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Papeleria Sol SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="F-2026-0142",
        issued_at=date(2026, 3, 10),
        taxable_base=Decimal("137.25"),
        iva_rate=Decimal("21"),
        currency="EUR",
        rate_provider=exchange_rate_provider(),
    )


def test_invoice_draft_projection_carries_all_fields_and_private_facturae_class() -> None:
    source = _draft()
    projected = InvoiceDraftProjectionV1.from_draft(source)
    decoded = InvoiceDraftProjectionV1.model_validate_json(projected.model_dump_json())

    assert decoded == projected
    assert set(type(source).model_fields) == set(type(projected).model_fields) - {"facturae_invoice_class"}
    assert projected.facturae_invoice_class is not None
    assert projected.facturae_invoice_class.source_code == "R1"
    assert projected.facturae_invoice_class.kind is StructuredInvoiceClassificationKind.CORRECTIVE
    assert projected.iva_rate == PublicDecimal(decimal="21")
    assert projected.lines[0].unit_price == PublicDecimal(decimal="68.625")
    assert projected.iva_breakdown[0].iva_amount == PublicDecimal(decimal="28.82")
    assert projected.discrepancies[0].expected == PublicDecimal(decimal="166.07")
    assert projected.discrepancies[0].observed == PublicDecimal(decimal="166.08")
    assert projected.provenance[1].derived_from == ("lines.taxable_base",)
    assert projected.provenance[0].role_evidence == "Proveedor A58818501"


@pytest.mark.parametrize("created", [True, False])
def test_confirmation_projection_preserves_actual_rerun_and_resolution_facts(created: bool) -> None:
    source_draft = _draft()
    establishment = _establishment()
    InvoiceConfirmationResult.model_rebuild(_types_namespace={"ConfirmedEstablishment": ConfirmedEstablishment})
    result = InvoiceConfirmationResult(
        invoice=_invoice(),
        draft=source_draft,
        created=created,
        total_discrepancy=PrintedTotalDiscrepancy(
            printed_total=Decimal("166.08"),
            recorded_total=Decimal("166.07"),
            difference=Decimal("0.01"),
        ),
        confirmation_id="d" * 16,
        confirmed_provenance=(
            FieldProvenance(
                field="supplier_name",
                origin=FieldOrigin.OPERATOR,
                grounding=FieldGroundingOutcome.UNANCHORED,
                note="Operator confirmed the counterparty display name.",
            ),
        ),
        establishment=establishment,
    )

    projected = InvoiceConfirmationProjectionV1.from_result(result)
    decoded = InvoiceConfirmationProjectionV1.model_validate_json(projected.model_dump_json())

    assert decoded == projected
    assert projected.invoice == CatalogueInvoiceSnapshot.from_invoice(result.invoice)
    assert projected.created is created
    assert projected.confirmation_id == result.confirmation_id
    assert projected.draft.facturae_invoice_class is not None
    assert projected.draft.provenance[0].origin is FieldOrigin.EXACT_STRUCTURED
    assert projected.confirmed_provenance[0].origin is FieldOrigin.OPERATOR
    assert projected.total_discrepancy is not None
    assert projected.total_discrepancy.printed_total == PublicDecimal(decimal="166.08")
    assert projected.total_discrepancy.recorded_total == PublicDecimal(decimal="166.07")
    assert projected.total_discrepancy.difference == PublicDecimal(decimal="0.01")
    assert projected.establishment is not None
    assert not projected.establishment.resolved
    assert projected.establishment.counterparty.scope is None
    assert projected.establishment.counterparty.contradiction is not None
    assert projected.establishment.counterparty.contradiction.confirmed_scope == "canary_islands"
    assert projected.establishment.declared.stated_category is not None
    assert projected.establishment.declared.stated_category.value == "domestic_standard"
    assert projected.establishment.assembly.criteria is not None
    assert projected.establishment.assembly.criteria.customer_residency == "canary_islands"
    assert projected.establishment.category.outcome is IvaCategoryOutcome.CONTRADICTED
    assert projected.establishment.review_items[0].candidates[1].value == "canary_islands"

    registration_conflict = RegistrationEstablishmentConflict(
        identification_state=EUMemberState.from_registry("ES"),
        spain_indicating=("Spanish address", "Spanish postal code"),
        detail="Registration and establishment evidence disagree.",
    )
    registration_projection = CounterpartyEstablishmentProjectionV1.from_counterparty(
        CounterpartyEstablishment(
            scope=None,
            identification_state=EUMemberState.from_registry("ES"),
            registration_conflict=registration_conflict,
        ),
    )
    assert registration_projection.registration_conflict is not None
    assert registration_projection.registration_conflict.spain_indicating == (
        "Spanish address",
        "Spanish postal code",
    )


def test_public_dto_graphs_bind_to_closed_operation_schemas() -> None:
    for index, model in enumerate(
        (InvoiceDraftProjectionV1, ConfirmedEstablishmentProjectionV1, InvoiceConfirmationProjectionV1),
        start=1,
    ):
        schema = strict_model_json_schema(model)
        assert schema["additionalProperties"] is False
        OperationSchemaBindingV1.bind(
            schema_id=f"ledger.evidence.dto-test-{index}",
            schema_version=1,
            model_type=model,
        )
