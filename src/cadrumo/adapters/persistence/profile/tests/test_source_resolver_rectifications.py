"""Facturas rectificativas and suplidos through the invoice source resolver, for Modelos 347 and 349.

Modelo 349: the IVA manual 2025 (pp. 300-302) and the Modelo 349 instructions. A
correction notified in the period of the operation nets into its one operator
record; one notified later fills a rectification record for the corrected period.

Modelo 347: RD 1065/2007 arts. 33.1, 34.2, 34.4 and 35.2, and LIVA art. 78.Tres.3.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.profile.invoice_source_resolver import M349FiledDeclarationAdapter
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext, CalculationSourceResolution
from cadrumo.application.invoices.source_resolver import InvoiceCatalogueSourceResolver
from cadrumo.application.invoices.source_resolver_ports import (
    InvoiceSourcePersistenceError,
    InvoiceSourceResolverPorts,
    M349FiledDeclaration,
)
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope, revision_covering
from cadrumo.domain.invoices.enums import invoice_class_rectificativa
from cadrumo.domain.invoices.models import Invoice
from cadrumo.domain.iva.schema import InvoiceKind, IvaCategory
from cadrumo.domain.modelos.calculation_repository import CalculationRevisionPersistenceError
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.row_models import Modelo349OperadorRow, Modelo349RectificacionRow

from .source_resolver_test_support import (
    BUCKET_ID,
    InMemoryCatalogueReader,
    domestic_invoice,
    m347_2026_context,
    modelo_revision,
    public_resolution,
    source_resolver_invoice,
    unsettled_reading_refs,
)
from .source_resolver_test_support import (
    generation_pinned_authority as generation_pinned_authority,
)
from .source_resolver_test_support import secure_profile as secure_profile

_YEAR = filing_year_envelope().horizon
_PRIOR = _YEAR - 1

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_SUPPLY = IvaCategory("intra_community_supply")
_DE_OPERATOR = "DE123456789"
_M347_COUNT = "modelo-347-declarante-numero-personas-entidades"
_M347_TOTAL = "modelo-347-declarante-importe-total-anual-operaciones"
_M349_OPERATORS = "iva-349-declarante-numero-operadores"
_M349_RECTIFICATIONS = "iva-349-declarante-numero-rectificaciones"
_M349_RECTIFIED_TOTAL = "iva-349-declarante-importe-rectificaciones"


def _rectificativa(invoice: Invoice, *, of: str) -> Invoice:
    return invoice.model_copy(
        update={"invoice_class": invoice_class_rectificativa(), "series": "R", "rectifies_invoice_number": of},
    )


def _supply(number: str, *, issued_at: date, base: str, operator: str = _DE_OPERATOR) -> Invoice:
    return source_resolver_invoice(
        bucket_id=BUCKET_ID,
        invoice_number=number,
        issued_at=issued_at,
        counterparty_tax_id=operator,
        base_total=Decimal(base),
        iva_category=_SUPPLY,
    )


def _m349_context(period: str) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id=BUCKET_ID,
        modelo="349",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period),
        revision=modelo_revision("349", revision_covering("349", _YEAR).id),
    )


def _filed_operator(*, importe: str, nif: str = _DE_OPERATOR) -> Modelo349OperadorRow:
    return Modelo349OperadorRow(
        codigo_pais=nif[:2],
        nif_comunitario=nif,
        razon_social="EU Customer GmbH",
        clave_operacion="E",
        importe=Decimal(importe),
    )


def _filed_rectification(*, ejercicio: str, periodo: str, nueva: str, anterior: str) -> Modelo349RectificacionRow:
    return Modelo349RectificacionRow(
        codigo_pais="DE",
        nif_comunitario=_DE_OPERATOR,
        razon_social="EU Customer GmbH",
        clave_operacion="E",
        ejercicio=ejercicio,
        periodo=periodo,
        base_rectificada=Decimal(nueva),
        base_anterior=Decimal(anterior),
    )


class _FiledDeclarations:
    """The filed Modelo 349 declarations a test states, as the composed reader projects them."""

    def __init__(self, *declarations: M349FiledDeclaration) -> None:
        self._declarations = declarations

    def load(self) -> tuple[M349FiledDeclaration, ...]:
        return self._declarations


def _m349_resolution(
    invoices: Sequence[Invoice],
    *,
    period: str,
    filed: _FiledDeclarations | None = None,
) -> CalculationSourceResolution:
    return InvoiceCatalogueSourceResolver(
        ports=InvoiceSourceResolverPorts(
            catalogue_reader=InMemoryCatalogueReader(invoices),
            m349_filed_declarations=filed,
        ),
    ).resolve(_m349_context(period))


def _operators(resolution: CalculationSourceResolution) -> list[Modelo349OperadorRow]:
    return [row for row in resolution.detail_rows if isinstance(row, Modelo349OperadorRow)]


def _rectifications(resolution: CalculationSourceResolution) -> list[Modelo349RectificacionRow]:
    return [row for row in resolution.detail_rows if isinstance(row, Modelo349RectificacionRow)]


def _refusals(resolution: CalculationSourceResolution) -> list[str | None]:
    return sorted(
        (item.source_ref for item in resolution.diagnostics if item.reason == "unrouted_declarable_quantity"),
        key=str,
    )


def test_m349_correction_of_the_same_quarter_nets_into_its_one_operator_record() -> None:
    """Manual IVA 2025 p. 302: "se enviará un único registro en la hoja de declarados neteando el importe".

    10,000 supplied and 2,000 corrected in the first quarter declare 8,000, not 12,000.
    """
    supply = _supply("F-1", issued_at=date(_YEAR, 1, 20), base="10000.00")
    correction = _rectificativa(_supply("R-1", issued_at=date(_YEAR, 2, 20), base="2000.00"), of="F-1")

    resolution = _m349_resolution((supply, correction), period="1T")

    assert [row.importe for row in _operators(resolution)] == [Decimal("8000.00")]
    assert _rectifications(resolution) == []
    assert resolution.binding_values[_M349_OPERATORS] == Decimal("1")
    assert resolution.binding_values[_M349_RECTIFICATIONS] == Decimal("0")
    assert _refusals(resolution) == []


def test_m349_full_correction_of_the_same_quarter_leaves_no_operator_record() -> None:
    """A supply wholly corrected in its own quarter is an operation with nothing left to declare."""
    supply = _supply("F-1", issued_at=date(_YEAR, 1, 20), base="10000.00")
    correction = _rectificativa(_supply("R-1", issued_at=date(_YEAR, 2, 20), base="10000.00"), of="F-1")

    resolution = _m349_resolution((supply, correction), period="1T")

    assert _operators(resolution) == []
    assert resolution.binding_values[_M349_OPERATORS] == Decimal("0")


def test_m349_correction_of_a_filed_earlier_quarter_fills_one_rectification_record() -> None:
    """Instructions: "La rectificación se incluirá en la declaración recapitulativa del periodo en el que haya
    sido notificada"; manual p. 300: the new total goes in "Base imponible rectificada", the amount declared in
    "Base imponible declarada anteriormente", the corrected period in "Ejercicio" and "Período".

    10,000 filed for 1T and 2,000 corrected in 2T: no 2T operator record, and one record 2026/1T, 8,000 against 10,000.
    """
    supply = _supply("F-1", issued_at=date(_YEAR, 1, 20), base="10000.00")
    correction = _rectificativa(_supply("R-1", issued_at=date(_YEAR, 4, 20), base="2000.00"), of="F-1")
    filed = _FiledDeclarations(
        M349FiledDeclaration(
            period=Period.from_year_and_code(_YEAR, "1T"), rows=(_filed_operator(importe="10000.00"),)
        ),
    )

    resolution = _m349_resolution((supply, correction), period="2T", filed=filed)

    assert _operators(resolution) == []
    rows = _rectifications(resolution)
    assert len(rows) == 1
    assert (rows[0].ejercicio, rows[0].periodo) == (str(_YEAR), "1T")
    assert rows[0].clave_operacion == "E"
    assert rows[0].nif_comunitario == _DE_OPERATOR
    assert rows[0].base_rectificada == Decimal("8000.00")
    assert rows[0].base_anterior == Decimal("10000.00")
    assert resolution.binding_values[_M349_OPERATORS] == Decimal("0")
    assert resolution.binding_values[_M349_RECTIFICATIONS] == Decimal("1")
    # Instructions, casilla 04: "la suma total de los importes consignados en el apartado 'base imponible rectificada'".
    assert resolution.binding_values[_M349_RECTIFIED_TOTAL] == Decimal("8000.00")
    assert _refusals(resolution) == []


def test_m349_two_corrections_of_one_filed_quarter_share_one_record() -> None:
    """Corrections of one operator, clave and period fold into the one record the design holds for them."""
    supply = _supply("F-1", issued_at=date(_YEAR, 1, 20), base="10000.00")
    first = _rectificativa(_supply("R-1", issued_at=date(_YEAR, 4, 20), base="2000.00"), of="F-1")
    second = _rectificativa(_supply("R-2", issued_at=date(_YEAR, 5, 20), base="500.00"), of="F-1")
    filed = _FiledDeclarations(
        M349FiledDeclaration(
            period=Period.from_year_and_code(_YEAR, "1T"), rows=(_filed_operator(importe="10000.00"),)
        ),
    )

    rows = _rectifications(_m349_resolution((supply, first, second), period="2T", filed=filed))

    assert [(row.base_rectificada, row.base_anterior) for row in rows] == [(Decimal("7500.00"), Decimal("10000.00"))]


def test_m349_a_later_correction_starts_from_the_base_an_earlier_rectification_left() -> None:
    """A base already rectified in 2T is what a 3T correction of the same quarter moves from."""
    supply = _supply("F-1", issued_at=date(_YEAR, 1, 20), base="10000.00")
    first = _rectificativa(_supply("R-1", issued_at=date(_YEAR, 4, 20), base="2000.00"), of="F-1")
    second = _rectificativa(_supply("R-2", issued_at=date(_YEAR, 7, 20), base="500.00"), of="F-1")
    filed = _FiledDeclarations(
        M349FiledDeclaration(
            period=Period.from_year_and_code(_YEAR, "1T"), rows=(_filed_operator(importe="10000.00"),)
        ),
        M349FiledDeclaration(
            period=Period.from_year_and_code(_YEAR, "2T"),
            rows=(_filed_rectification(ejercicio=str(_YEAR), periodo="1T", nueva="8000.00", anterior="10000.00"),),
        ),
    )

    rows = _rectifications(_m349_resolution((supply, first, second), period="3T", filed=filed))

    assert [(row.base_rectificada, row.base_anterior) for row in rows] == [(Decimal("7500.00"), Decimal("8000.00"))]


@pytest.mark.parametrize(
    "filed",
    [
        pytest.param(None, id="no-filed-reader"),
        pytest.param(_FiledDeclarations(), id="earlier-quarter-not-filed"),
        pytest.param(
            _FiledDeclarations(
                M349FiledDeclaration(
                    period=Period.from_year_and_code(_YEAR, "1T"),
                    rows=(_filed_operator(importe="10000.00", nif="FR12345678901"),),
                ),
            ),
            id="filed-without-this-operator",
        ),
    ],
)
def test_m349_correction_refuses_when_the_declared_base_is_not_known(filed: _FiledDeclarations | None) -> None:
    """No previously declared base means no record can be filled: not an operator row, not a guessed base."""
    supply = _supply("F-1", issued_at=date(_YEAR, 1, 20), base="10000.00")
    correction = _rectificativa(_supply("R-1", issued_at=date(_YEAR, 4, 20), base="2000.00"), of="F-1")

    resolution = _m349_resolution((supply, correction), period="2T", filed=filed)

    assert _operators(resolution) == []
    assert _rectifications(resolution) == []
    assert _refusals(resolution) == [f"invoice:{correction.invoice_id}"]


def test_m349_correction_of_an_invoice_the_catalogue_does_not_hold_refuses() -> None:
    """The corrected period is read off the corrected invoice, so without it the correction has no place."""
    correction = _rectificativa(_supply("R-1", issued_at=date(_YEAR, 4, 20), base="2000.00"), of="F-MISSING")

    resolution = _m349_resolution((correction,), period="2T")

    assert _operators(resolution) == []
    assert _refusals(resolution) == [f"invoice:{correction.invoice_id}"]


def test_m349_correction_above_the_declared_base_refuses() -> None:
    """A rectified base below zero has no place in the record, whose base carries no sign."""
    supply = _supply("F-1", issued_at=date(_YEAR, 1, 20), base="10000.00")
    correction = _rectificativa(_supply("R-1", issued_at=date(_YEAR, 4, 20), base="12000.00"), of="F-1")
    filed = _FiledDeclarations(
        M349FiledDeclaration(
            period=Period.from_year_and_code(_YEAR, "1T"), rows=(_filed_operator(importe="10000.00"),)
        ),
    )

    resolution = _m349_resolution((supply, correction), period="2T", filed=filed)

    assert _rectifications(resolution) == []
    assert _refusals(resolution) == [f"invoice:{correction.invoice_id}"]


def _sale(number: str, *, issued_at: date, gross: str) -> Invoice:
    gross_total = Decimal(gross)
    base_total = (gross_total / Decimal("1.21")).quantize(Decimal("0.01"))
    return domestic_invoice(
        bucket_id=BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        invoice_number=number,
        issued_at=issued_at,
        counterparty_tax_id="B00015016",
        counterparty_name="Cliente Rectificado SL",
        base_total=base_total,
        iva_total=gross_total - base_total,
    )


def _with_suplido(invoice: Invoice, suplido: str) -> Invoice:
    return invoice.model_copy(
        update={"suplido_amount": Decimal(suplido), "grand_total": invoice.grand_total + Decimal(suplido)},
    )


def _record_total(resolution: CalculationSourceResolution) -> Decimal:
    values = [
        value
        for (binding_id, _row), value in resolution.row_binding_values.items()
        if binding_id == "modelo-347-contraparte-row-importe"
    ]
    assert len(values) == 1
    assert isinstance(values[0], Decimal)
    return values[0]


def test_m347_suplido_does_not_count_towards_the_floor(secure_profile: TestRuntimeProfile) -> None:
    """Art. 34.2.c takes the contraprestación from LIVA art. 78, and art. 78.Tres.3 leaves out "las sumas pagadas
    en nombre y por cuenta del cliente". 2,000 + 420 IVA + 700 suplido is 2,420, below 3,005.06, so no record.
    """
    invoice = _with_suplido(
        domestic_invoice(
            bucket_id=secure_profile.bucket_id,
            kind=InvoiceKind.ISSUED,
            invoice_number="S-1",
            issued_at=date(_YEAR, 3, 1),
            counterparty_tax_id="B00015016",
            counterparty_name="Cliente Mandante SL",
            base_total=Decimal("2000.00"),
            iva_total=Decimal("420.00"),
        ),
        "700.00",
    )

    resolution = public_resolution((invoice,), context=m347_2026_context(secure_profile.bucket_id))

    assert resolution.binding_values[_M347_COUNT] == Decimal("0")
    assert resolution.row_binding_values == {}


def test_m347_declares_the_cuota_and_recargo_without_the_suplido(secure_profile: TestRuntimeProfile) -> None:
    """Art. 34.2.a keeps "las cuotas y recargos": 3,000 + 630 IVA + 156 recargo + 500 suplido declares 3,786."""
    invoice = _with_suplido(
        domestic_invoice(
            bucket_id=secure_profile.bucket_id,
            kind=InvoiceKind.ISSUED,
            invoice_number="S-2",
            issued_at=date(_YEAR, 3, 1),
            counterparty_tax_id="B00015016",
            counterparty_name="Cliente Mandante SL",
            base_total=Decimal("3000.00"),
            iva_total=Decimal("630.00"),
        ).model_copy(update={"recargo_amount": Decimal("156.00"), "grand_total": Decimal("3786.00")}),
        "500.00",
    )

    resolution = public_resolution((invoice,), context=m347_2026_context(secure_profile.bucket_id))

    assert _record_total(resolution) == Decimal("3786.00")
    assert resolution.binding_values[_M347_TOTAL] == Decimal("3786.00")


def test_m347_earlier_year_correction_is_declared_in_the_total_but_not_held_against_the_floor(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Art. 35.2: a modification in another year is consigned in the year it happens and "el importe total de las
    operaciones realizadas con la misma persona o entidad se declarará teniendo en cuenta dichas modificaciones".

    Art. 33.1 asks whether the year's operations exceed the floor. 6,000 of 2026 sales do; a 4,000 credit note on a
    2025 sale is no 2026 operation, but enters the amount, so the record declares 2,000 rather than vanishing.
    """
    bucket_id = secure_profile.bucket_id
    earlier = _sale("F-2025", issued_at=date(_PRIOR, 11, 20), gross="8000.00").model_copy(
        update={"bucket_id": bucket_id}
    )
    sale = _sale("F-2026", issued_at=date(_YEAR, 4, 1), gross="6000.00").model_copy(update={"bucket_id": bucket_id})
    credit = _rectificativa(
        _sale("R-2026", issued_at=date(_YEAR, 5, 1), gross="4000.00").model_copy(update={"bucket_id": bucket_id}),
        of="F-2025",
    )

    resolution = public_resolution((earlier, sale, credit), context=m347_2026_context(bucket_id))

    assert resolution.binding_values[_M347_COUNT] == Decimal("1")
    assert _record_total(resolution) == Decimal("2000.00")
    assert unsettled_reading_refs(resolution) == []


def test_m347_earlier_year_correction_can_take_the_record_negative(secure_profile: TestRuntimeProfile) -> None:
    """The record's sign field: "Se consignará una 'N' cuando el importe anual de las operaciones sea menor que 0"."""
    bucket_id = secure_profile.bucket_id
    earlier = _sale("F-2025", issued_at=date(_PRIOR, 11, 20), gross="9000.00").model_copy(
        update={"bucket_id": bucket_id}
    )
    sale = _sale("F-2026", issued_at=date(_YEAR, 4, 1), gross="3100.00").model_copy(update={"bucket_id": bucket_id})
    credit = _rectificativa(
        _sale("R-2026", issued_at=date(_YEAR, 5, 1), gross="4000.00").model_copy(update={"bucket_id": bucket_id}),
        of="F-2025",
    )

    resolution = public_resolution((earlier, sale, credit), context=m347_2026_context(bucket_id))

    assert _record_total(resolution) == Decimal("-900.00")
    assert resolution.binding_values[_M347_TOTAL] == Decimal("-900.00")


def test_m347_same_year_full_correction_is_left_out_as_settled(secure_profile: TestRuntimeProfile) -> None:
    """Arts. 33.1 and 34.4 settle it: a sale undone in its own year leaves no operation above the floor."""
    bucket_id = secure_profile.bucket_id
    sale = _sale("F-2026", issued_at=date(_YEAR, 3, 1), gross="5000.00").model_copy(update={"bucket_id": bucket_id})
    credit = _rectificativa(
        _sale("R-2026", issued_at=date(_YEAR, 9, 1), gross="5000.00").model_copy(update={"bucket_id": bucket_id}),
        of="F-2026",
    )

    resolution = public_resolution((sale, credit), context=m347_2026_context(bucket_id))

    assert resolution.binding_values[_M347_COUNT] == Decimal("0")
    assert unsettled_reading_refs(resolution) == []


def test_m347_upward_correction_stays_a_disclosed_reduction_because_no_field_records_its_direction(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Art. 34.4 counts "las alteraciones del precio", and +1,000 on a 3,000 sale should declare 4,000.

    The invoice stores a magnitude and no direction, so the correction nets as a reduction (2,000, below the floor)
    and the record gap is disclosed as something the filer supplies, not as an open reading of the law.
    """
    bucket_id = secure_profile.bucket_id
    sale = _sale("F-2026", issued_at=date(_YEAR, 3, 1), gross="3000.00").model_copy(update={"bucket_id": bucket_id})
    raise_ = _rectificativa(
        _sale("R-2026", issued_at=date(_YEAR, 9, 1), gross="1000.00").model_copy(update={"bucket_id": bucket_id}),
        of="F-2026",
    )

    resolution = public_resolution((sale, raise_), context=m347_2026_context(bucket_id))

    assert resolution.binding_values[_M347_COUNT] == Decimal("0")
    advisory = next(
        item for item in resolution.diagnostics if item.source_ref == "m347-rectificativa:netted-as-reduction"
    )
    assert advisory.reason == "source_issue"
    assert "R-2026" in advisory.message


def test_m347_earlier_year_correction_below_the_floor_is_disclosed(secure_profile: TestRuntimeProfile) -> None:
    """Art. 35.2 consigns the modification of an operation that "debió incluirse", but a party whose year stays
    below the floor has no record to carry it; that is left out and named.
    """
    bucket_id = secure_profile.bucket_id
    earlier = _sale("F-2025", issued_at=date(_PRIOR, 11, 20), gross="8000.00").model_copy(
        update={"bucket_id": bucket_id}
    )
    credit = _rectificativa(
        _sale("R-2026", issued_at=date(_YEAR, 5, 1), gross="4000.00").model_copy(update={"bucket_id": bucket_id}),
        of="F-2025",
    )

    resolution = public_resolution((earlier, credit), context=m347_2026_context(bucket_id))

    assert resolution.binding_values[_M347_COUNT] == Decimal("0")
    assert unsettled_reading_refs(resolution) == ["m347-threshold-bucket:earlier-year-modification-left-out"]


class _CalculationRepository:
    def __init__(self, catalogue: CalculationRevisionCatalogue | Exception) -> None:
        self._catalogue = catalogue

    def load(self, *, operation: PinnedAuthorityOperation | None = None) -> CalculationRevisionCatalogue:
        if isinstance(self._catalogue, Exception):
            raise self._catalogue
        return self._catalogue


def _filed_revision(
    *,
    modelo: str = "349",
    state: CalculationRevisionState = CalculationRevisionState.PRESENTADO,
    importe: str = "10000.00",
    updated_at: datetime = datetime(_YEAR, 4, 20, tzinfo=UTC),
) -> CalculationRevision:
    rows = (_filed_operator(importe=importe),)
    sealed = state is not CalculationRevisionState.BORRADOR
    sealed_at = updated_at if sealed else None
    sealed_by = "operator" if sealed else None
    work_unit = hashlib.sha256(f"{modelo}-1T-{importe}-{state.value}".encode()).hexdigest()
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            detail_rows=rows,
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=work_unit,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=modelo, revision_id=str(_YEAR), modelo_year=_YEAR, period="1T"
        ),
        state=state,
        casilla_values={},
        observations=(),
        detail_rows=rows,
        created_at=updated_at,
        updated_at=updated_at,
        filing_instance_evidence=None,
        source_provenance=(),
        verified_at=sealed_at,
        verified_by=sealed_by,
        filed_at=sealed_at,
        filed_by=sealed_by,
        superseded_at=updated_at if state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO else None,
    )


def test_m349_filed_declarations_are_the_current_filed_revision_of_each_period() -> None:
    """Drafts, superseded revisions and other modelos state nothing declared; the latest filing of a period does."""
    revisions = (
        _filed_revision(state=CalculationRevisionState.PRESENTADO_SUPERSEDIDO, importe="1.00"),
        _filed_revision(state=CalculationRevisionState.BORRADOR, importe="2.00"),
        _filed_revision(modelo="303", importe="3.00"),
        _filed_revision(importe="9000.00", updated_at=datetime(_YEAR, 4, 20, tzinfo=UTC)),
        _filed_revision(importe="10000.00", updated_at=datetime(_YEAR, 5, 20, tzinfo=UTC)),
    )
    reader = M349FiledDeclarationAdapter(
        repository=_CalculationRepository(
            CalculationRevisionCatalogue(revisions={item.calculation_revision_id: item for item in revisions}),
        ),
        operation=None,
    )

    declarations = reader.load()

    assert [item.period for item in declarations] == [Period.from_year_and_code(_YEAR, "1T")]
    assert declarations[0].rows == (_filed_operator(importe="10000.00"),)


def test_m349_filed_declaration_read_failure_is_a_persistence_failure() -> None:
    """Unreadable storage must not read as nothing filed."""
    reader = M349FiledDeclarationAdapter(
        repository=_CalculationRepository(CalculationRevisionPersistenceError("unreadable")),
        operation=None,
    )

    with pytest.raises(InvoiceSourcePersistenceError):
        reader.load()
