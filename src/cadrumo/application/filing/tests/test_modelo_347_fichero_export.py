"""A Modelo 347 filer without leases exports a fichero the post-write read-back accepts.

The normal path end to end: synthetic invoices through the real 347 resolver,
its binding and row values into ``build_draft``, and ``export_draft`` writing
the file and reading it back. The 2025 design (aeat-dr-347-2025) fixes the
bytes asserted here: the type 1 EJERCICIO at positions 5-8, the type 2 kind
``D`` at 76, the signed annual amount at 83-98 ("N" when negative, otherwise a
space, then 13 integer and 2 decimal digits), and the declarado EJERCICIO at
132-135, which carries "las cuatro cifras del ejercicio en el que se hubieran
declarado las operaciones que dan origen al cobro en metálico por importe
superior a 6.000 euros" and so has no content without such a collection
("Los campos numéricos que no tengan contenido se rellenarán a ceros").
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.modelo import Modelo
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.filing.protocols import ModeloInputScalar, ModeloInputValue
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine, derive_invoice_id
from ....domain.iva.classification import InvoiceKind
from ....domain.submission.models import ModeloDraftStatus
from ....domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...aggregation.source_mesh import CalculationSourceContext
from ...invoices.source_resolver import InvoiceCatalogueSourceResolver
from ...invoices.source_resolver_ports import InvoiceSourceResolverPorts
from ...modelo.work_profile import ModeloWorkProfile
from ..draft_construction import build_draft
from ..export import export_draft
from ..runtime import ModeloOperatorProfile
from .export_support import _schema_provider, m151_producer_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = 2025
_BUCKET_ID = "24242424-2424-4242-8242-242424242424"


def _domestic(number: str, kind: InvoiceKind, tax_id: str, name: str, base: str) -> Invoice:
    base_total = Decimal(base)
    iva_total = (base_total * Decimal("0.21")).quantize(Decimal("0.01"))
    return Invoice(
        invoice_id=derive_invoice_id(
            kind=kind,
            invoice_number=number,
            issued_at=date(_YEAR, 5, 12),
            counterparty_tax_id=tax_id,
            currency="EUR",
            grand_total=base_total + iva_total,
        ),
        kind=kind,
        invoice_number=number,
        issued_at=date(_YEAR, 5, 12),
        counterparty_name=name,
        counterparty_tax_id=tax_id,
        counterparty_country="ES",
        base_total=base_total,
        iva_total=iva_total,
        grand_total=base_total + iva_total,
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Operacion interior",
                quantity=Decimal("1"),
                unit_price=base_total,
                subtotal=base_total,
                iva_rate=IvaRate.from_registry("RATE_21"),
                iva_amount=iva_total,
            ),
        ),
        payment_status=PaymentStatus.PAID,
    )


class _CatalogueReader:
    def __init__(self, invoices: tuple[Invoice, ...]) -> None:
        self._catalogue = build_invoice_catalogue(invoices)

    def load(self) -> InvoiceCatalogue:
        return self._catalogue


def _profile(operation: PinnedAuthorityOperation) -> ModeloWorkProfile:
    record = create_user_profile_record(
        context=profile_creation_context_for_test(),
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        ),
    )
    return ModeloWorkProfile(record=record, profile_decode_context=operation.profile_decode_context())


def _resolved_inputs(operation: PinnedAuthorityOperation) -> dict[str, ModeloInputValue]:
    provider = _schema_provider(filing_year=_YEAR, period="0A", modelos=("347",))
    invoices = (
        _domestic("V-1", InvoiceKind.ISSUED, "B12345674", "CLIENTE NACIONAL SL", "8000.00"),
        _domestic("C-1", InvoiceKind.RECEIVED, "A58818501", "PROVEEDOR NACIONAL SA", "5000.00"),
        _domestic("V-2", InvoiceKind.ISSUED, "C3333333G", "CLIENTE PEQUENO SL", "1000.00"),
    )
    context = CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo="347",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        revision=provider.get_snapshot("347").revision,
        profile=_profile(operation),
        operation=operation,
    )
    resolution = InvoiceCatalogueSourceResolver(
        ports=InvoiceSourceResolverPorts(catalogue_reader=_CatalogueReader(invoices)),
    ).resolve(context)
    inputs: dict[str, ModeloInputValue] = {
        "decl.ejercicio": str(_YEAR),
        **{str(binding_id): value for binding_id, value in resolution.binding_values.items()},
    }
    rows: dict[str, dict[str, ModeloInputScalar]] = {}
    for (binding_id, row_index), value in resolution.row_binding_values.items():
        rows.setdefault(str(binding_id), {})[str(row_index)] = value
    inputs.update(rows)
    return inputs


def test_a_347_filer_without_leases_exports_a_fichero_that_reads_back(
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
) -> None:
    provider = _schema_provider(filing_year=_YEAR, period="0A", modelos=("347",))
    draft = build_draft(
        modelo="347",
        period=Period.from_year_and_code(_YEAR, "0A"),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="DECLARANTE PRUEBA"),
        inputs=_resolved_inputs(operation),
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    output_path = tmp_path / "modelo-347-2025.txt"

    export_draft(
        draft,
        output_path=output_path,
        producer_snapshot=m151_producer_snapshot().model_copy(update={"modelo": Modelo("347")}),
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity=None,
        schema_provider=provider,
    )

    lines = output_path.read_bytes().decode("iso-8859-1").splitlines()
    declarante, *type_2 = lines
    # Position 76 marks the type 2 kind; the inmueble record ("I") is a lessor's
    # statement and has its own test, so the declarado ("D") records are read here.
    declarados = [line for line in type_2 if line[75] == "D"]
    assert declarante[:8] == "13472025"
    assert declarante[135:144] == "000000002"
    assert declarante[144:160] == " 000000001573000"
    amounts = {line[35:75].rstrip(): line[82:98] for line in declarados}
    assert amounts == {
        "CLIENTE NACIONAL SL": " 000000000968000",
        "PROVEEDOR NACIONAL SA": " 000000000605000",
    }
    assert len(declarados) == 2
    assert {line[131:135] for line in declarados} == {"0000"}
