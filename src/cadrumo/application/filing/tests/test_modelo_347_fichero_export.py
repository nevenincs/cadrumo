"""A Modelo 347 filer without leases exports a fichero the post-write read-back accepts.

The normal path end to end: synthetic invoices through the real 347 resolver,
its binding and row values into ``build_draft``, and ``export_draft`` writing
the file and reading it back. The 2025 design (aeat-dr-347-2025) fixes the
bytes asserted here: the type 1 EJERCICIO at positions 5-8, the TIPO DE SOPORTE
at 58 ("'T': Transmisión telemática", the only way Cadrumo files), the type 2 kind
``D`` at 76, the signed annual amount at 83-98 ("N" when negative, otherwise a
space, then 13 integer and 2 decimal digits), and the declarado EJERCICIO at
132-135, which carries "las cuatro cifras del ejercicio en el que se hubieran
declarado las operaciones que dan origen al cobro en metálico por importe
superior a 6.000 euros" and so has no content without such a collection
("Los campos numéricos que no tengan contenido se rellenarán a ceros").

A landlord of business premises (RD 1065/2007 art. 34.1.d: "se harán constar
separadamente de otras operaciones ... los arrendamientos de locales de negocios
... el arrendador consignará ... las referencias catastrales") files the lease
apart in its own declarado record, marked at position 100 ("Se pondrá en este
campo una "X" para operaciones de arrendamiento de locales de negocio"), and one
inmueble record per leased premises: kind ``I`` at 76, the tenant's NIF at
18-26, the signed IMPORTE DE LA OPERACION at 99-114, the SITUACIÓN DEL INMUEBLE
at 115 and the REFERENCIA CATASTRAL at 116-140. The type 1 record counts those
records at 161-169 and sums their amounts at 170-185.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.modelo import Modelo
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....domain.calculations.registry.applicability import derive_modelo_applicability
from ....domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.filing.errors import FilingExportValidationError
from ....domain.filing.protocols import ModeloInputScalar, ModeloInputValue
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine, derive_invoice_id
from ....domain.iva.schema import InvoiceKind
from ....domain.submission.models import ModeloDraftStatus
from ....domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...aggregation.source_mesh import CalculationSourceContext
from ...invoices.source_resolver import InvoiceCatalogueSourceResolver
from ...invoices.source_resolver_ports import InvoiceSourceResolverPorts
from ...modelo.work_profile import ModeloWorkProfile
from ...user_profile.projections import projection_for_taxpayer
from ..draft_construction import build_draft
from ..export import export_draft
from ..runtime import ModeloOperatorProfile, build_runtime_schema_provider
from .export_support import m151_producer_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = 2025
_BUCKET_ID = "24242424-2424-4242-8242-242424242424"


def _domestic(
    number: str,
    kind: InvoiceKind,
    tax_id: str,
    name: str,
    base: str,
    *,
    referencia_catastral: str | None = None,
) -> Invoice:
    base_total = Decimal(base)
    lease = referencia_catastral is not None
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
        arrendamiento_local_negocio=lease,
        situacion_inmueble="1" if lease else None,
        referencia_catastral=referencia_catastral,
    )


class _CatalogueReader:
    def __init__(self, invoices: tuple[Invoice, ...]) -> None:
        self._catalogue = build_invoice_catalogue(invoices)

    def load(self) -> InvoiceCatalogue:
        return self._catalogue


def _profile(
    operation: PinnedAuthorityOperation,
    *,
    iva_regime: str = "GENERAL",
    estimation_regime: str | None = None,
    voluntary_sii: bool = False,
    threshold_declared: bool | None = None,
) -> ModeloWorkProfile:
    stated = [
        UserProfileFact(path="identity.tax_id", value="12345678Z"),
        UserProfileFact(path="iva.regime", value=iva_regime),
        UserProfileFact(path="iva.voluntary_sii_enrolled", value=voluntary_sii),
    ]
    if estimation_regime is not None:
        stated.append(UserProfileFact(path="irpf.estimation_regime", value=estimation_regime))
    if threshold_declared is not None:
        stated.append(
            UserProfileFact(path="obligations.third_party_transactions_above_347_threshold", value=threshold_declared)
        )
    omitted = (
        *(("irpf.estimation_regime",) if estimation_regime is None else ()),
        *(("obligations.third_party_transactions_above_347_threshold",) if threshold_declared is None else ()),
    )
    facts = persona_facts_beneath(stated, without=omitted)
    record = create_user_profile_record(
        context=profile_creation_context_for_test(),
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=facts,
    )
    return ModeloWorkProfile(record=record, profile_decode_context=operation.profile_decode_context())


def _ordinary_invoices() -> tuple[Invoice, ...]:
    return (
        _domestic("V-1", InvoiceKind.ISSUED, "B00015016", "CLIENTE NACIONAL SL", "8000.00"),
        _domestic("C-1", InvoiceKind.RECEIVED, "A00010074", "PROVEEDOR NACIONAL SA", "5000.00"),
        _domestic("V-2", InvoiceKind.ISSUED, "C0001502D", "CLIENTE PEQUENO SL", "1000.00"),
    )


def _resolved_inputs(
    operation: PinnedAuthorityOperation,
    invoices: tuple[Invoice, ...] | None = None,
    profile: ModeloWorkProfile | None = None,
) -> dict[str, ModeloInputValue]:
    invoices = _ordinary_invoices() if invoices is None else invoices
    provider = build_runtime_schema_provider(
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        modelos=("347",),
        operation=operation,
    )
    context = CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo="347",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        revision=provider.get_snapshot("347").revision,
        profile=_profile(operation) if profile is None else profile,
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
    provider = build_runtime_schema_provider(
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        modelos=("347",),
        operation=operation,
    )
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
    assert declarante[57] == "T"
    assert declarante[135:144] == "000000002"
    assert declarante[144:160] == " 000000001573000"
    amounts = {line[35:75].rstrip(): line[82:98] for line in declarados}
    assert amounts == {
        "CLIENTE NACIONAL SL": " 000000000968000",
        "PROVEEDOR NACIONAL SA": " 000000000605000",
    }
    assert len(declarados) == 2
    assert {line[131:135] for line in declarados} == {"0000"}
    assert [line for line in type_2 if line[75] == "I"] == []
    assert declarante[160:169] == "000000000"
    assert declarante[169:185] == " 000000000000000"


def _exported_lines(
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
    invoices: tuple[Invoice, ...],
    profile: ModeloWorkProfile | None = None,
) -> list[str]:
    provider = build_runtime_schema_provider(
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        modelos=("347",),
        operation=operation,
    )
    draft = build_draft(
        modelo="347",
        period=Period.from_year_and_code(_YEAR, "0A"),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="DECLARANTE PRUEBA"),
        inputs=_resolved_inputs(operation, invoices, profile),
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
    return output_path.read_bytes().decode("iso-8859-1").splitlines()


def test_a_landlord_files_one_inmueble_record_per_leased_premises_and_the_leases_apart(
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
) -> None:
    """Two premises let to one tenant each: two inmueble records, two marked declarado records."""
    invoices = (
        _domestic(
            "A-1",
            InvoiceKind.ISSUED,
            "B00015016",
            "INQUILINO UNO SL",
            "10000.00",
            referencia_catastral="9872023VH5797S0001WX",
        ),
        _domestic(
            "A-2",
            InvoiceKind.ISSUED,
            "B00015057",
            "INQUILINO DOS SL",
            "6000.00",
            referencia_catastral="1234567DF3813S0002QK",
        ),
        _domestic("V-1", InvoiceKind.ISSUED, "B00015016", "INQUILINO UNO SL", "5000.00"),
    )

    declarante, *type_2 = _exported_lines(operation, tmp_path, invoices)

    declarados = {(line[17:26], line[99]): line[82:98] for line in type_2 if line[75] == "D"}
    assert declarados == {
        ("B00015016", "X"): " 000000001210000",
        ("B00015016", " "): " 000000000605000",
        ("B00015057", "X"): " 000000000726000",
    }
    inmuebles = [line for line in type_2 if line[75] == "I"]
    assert [
        (line[17:26], line[35:75].rstrip(), line[98:114], line[114], line[115:140].rstrip()) for line in inmuebles
    ] == [
        ("B00015016", "INQUILINO UNO SL", " 000000001210000", "1", "9872023VH5797S0001WX"),
        ("B00015057", "INQUILINO DOS SL", " 000000000726000", "1", "1234567DF3813S0002QK"),
    ]
    assert declarante[135:144] == "000000003"
    assert declarante[144:160] == " 000000002541000"
    assert declarante[160:169] == "000000002"
    assert declarante[169:185] == " 000000001936000"


def _export_with_inputs(
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
    invoices: tuple[Invoice, ...],
    extra_inputs: dict[str, ModeloInputValue],
) -> list[str]:
    provider = build_runtime_schema_provider(
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        modelos=("347",),
        operation=operation,
    )
    draft = build_draft(
        modelo="347",
        period=Period.from_year_and_code(_YEAR, "0A"),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="DECLARANTE PRUEBA"),
        inputs={**_resolved_inputs(operation, invoices), **extra_inputs},
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
    return output_path.read_bytes().decode("iso-8859-1").splitlines()


@pytest.mark.parametrize(
    ("casilla_id", "value"),
    [
        ("contraparte.importe-metalico", "7000"),
        ("contraparte.operacion-seguro", "X"),
        ("contraparte.numero-convocatoria-bdns", "123456"),
    ],
)
def test_a_single_valued_casilla_is_refused_instead_of_copied_onto_every_counterparty_row(
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
    casilla_id: str,
    value: str,
) -> None:
    """Two counterparties exceed the floor, so one typed value has no row to belong to."""
    with pytest.raises(FilingExportValidationError) as raised:
        _export_with_inputs(operation, tmp_path, _ordinary_invoices(), {casilla_id: value})

    context = raised.value.context
    assert context is not None
    assert context["casilla_ids"] == (casilla_id,)
    assert context["row_count"] == 2
    assert not (tmp_path / "modelo-347-2025.txt").exists()


def test_absent_or_zero_single_valued_casillas_leave_every_row_without_cash(
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
) -> None:
    typed_cash: tuple[dict[str, ModeloInputValue], ...] = ({}, {"contraparte.importe-metalico": "0"})
    for typed in typed_cash:
        lines = _export_with_inputs(operation, tmp_path, _ordinary_invoices(), typed)
        declarados = [line for line in lines[1:] if line[75] == "D"]
        assert len(declarados) == 2
        # Positions 101-115 are the cash amount: 13 integer and 2 decimal digits.
        assert {line[100:115] for line in declarados} == {"000000000000000"}


def test_a_single_counterparty_row_carries_the_typed_cash_amount(
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
) -> None:
    only_one = (_domestic("V-1", InvoiceKind.ISSUED, "B00015016", "CLIENTE NACIONAL SL", "8000.00"),)

    lines = _export_with_inputs(operation, tmp_path, only_one, {"contraparte.importe-metalico": "7000"})

    declarados = [line for line in lines[1:] if line[75] == "D"]
    assert len(declarados) == 1
    # 7000 euros in positions 101-115: 13 integer digits, then 2 decimal digits.
    assert declarados[0][100:115] == "000000000700000"


def _declarados(lines: list[str]) -> tuple[str, list[str]]:
    declarante, *type_2 = lines
    return declarante, [line for line in type_2 if line[75] == "D"]


@pytest.mark.parametrize(
    ("iva_regime", "received_files"),
    [
        pytest.param("RECARGO_EQUIVALENCIA", False, id="modulos-recargo-issued-only"),
        pytest.param("REAGP", False, id="modulos-reagp-issued-only"),
        pytest.param("SIMPLIFICADO", True, id="modulos-simplificado-adds-libro-registro-received"),
    ],
)
def test_a_modulos_filer_files_the_declarados_art_32_b_keeps(
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
    iva_regime: str,
    received_files: bool,
) -> None:
    """RGAT art. 32.b: invoices issued, plus the received ones of the simplificado's libro registro.

    The ledger is the ordinary one: an 8,000 sale (9,680.00 with 21 % IVA), a
    5,000 purchase from one supplier (6,050.00) and a 1,000 sale to a customer
    below the 3,005.06 floor. The estimación objetiva filer under the recargo
    de equivalencia or the REAGP files the customer alone; under the simplificado
    the supplier joins.
    """
    profile = _profile(operation, iva_regime=iva_regime, estimation_regime="objetiva")

    declarante, declarados = _declarados(_exported_lines(operation, tmp_path, _ordinary_invoices(), profile))

    amounts = {line[35:75].rstrip(): line[82:98] for line in declarados}
    if received_files:
        assert amounts == {
            "CLIENTE NACIONAL SL": " 000000000968000",
            "PROVEEDOR NACIONAL SA": " 000000000605000",
        }
        assert declarante[135:144] == "000000002"
        assert declarante[144:160] == " 000000001573000"
    else:
        assert amounts == {"CLIENTE NACIONAL SL": " 000000000968000"}
        assert declarante[135:144] == "000000001"
        assert declarante[144:160] == " 000000000968000"
    assert len(declarados) == len(amounts)
    assert declarante[:8] == "13472025"


def test_a_filer_outside_estimacion_objetiva_files_both_directions_whatever_its_special_regime(
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
) -> None:
    """The art. 32.b scope needs estimación objetiva as well; recargo de equivalencia alone does not narrow it."""
    profile = _profile(operation, iva_regime="RECARGO_EQUIVALENCIA", estimation_regime="directa_simplificada")

    _declarante, declarados = _declarados(_exported_lines(operation, tmp_path, _ordinary_invoices(), profile))

    assert {line[35:75].rstrip() for line in declarados} == {"CLIENTE NACIONAL SL", "PROVEEDOR NACIONAL SA"}


@pytest.mark.parametrize(
    ("voluntary_sii", "verdict"),
    [
        pytest.param(False, ApplicabilityVerdict.APPLICABLE, id="books-outside-sii-must-file"),
        pytest.param(True, ApplicabilityVerdict.NOT_APPLICABLE, id="sii-filer-is-not-obliged"),
    ],
)
def test_an_sii_filer_is_not_obliged_to_file_the_ledger_that_obliges_a_filer_outside_sii(
    operation: PinnedAuthorityOperation,
    voluntary_sii: bool,
    verdict: ApplicabilityVerdict,
) -> None:
    """RGAT art. 32.e: a filer keeping its IVA books through the SII does not file, however large its ledger.

    The profile states the threshold exceeded in both cases and differs only in
    the SII enrolment, and the one applicability evaluator every surface reads
    gives the opposite verdicts.
    """
    work_profile = _profile(operation, voluntary_sii=voluntary_sii, threshold_declared=True)
    taxpayer = projection_for_taxpayer(
        work_profile.record,
        schema=work_profile.profile_decode_context.schema,
        as_of=date(_YEAR, 12, 31),
    )

    result = derive_modelo_applicability(taxpayer, "347", today=date(_YEAR + 1, 1, 15), operation=operation)

    assert result.verdict is verdict
    if verdict is ApplicabilityVerdict.NOT_APPLICABLE:
        assert "rd-1065-2007:art-32" in result.legal_refs
