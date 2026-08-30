"""Modelo 347 declarado record renders one occurrence per counterparty.

Before this export was repointed, ``m347-declarado`` carried scalar
``kind = 'casilla'`` fields with no ``repeat`` marker, so the record rendered
a single fixed occurrence regardless of how many counterparties the resolver
produced -- a multi-counterparty declaration would have truncated to one
counterparty, the exact defect this module guards against. This module
proves the repoint against BOTH real bundled revisions
(``2025-y-siguientes`` and ``2011-2024``, since the underlying defect names no
revision qualifier) and the real production entry points:
:func:`resolve_invoice_binding_row_values` and :func:`_record_render_rows`.

It also proves the quarterly-desagregación property the repoint's own
condition required before ``repeat`` could be declared: each row's four
quarterly amounts sum to its annual total, with a real invoice in every
quarter and one on a quarter boundary date.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core import CasillaId
from ....core.aggregation import BindingSourceKind
from ....core.external_constants import M347_CLAVE_C_THRESHOLD_EUR, M347_THRESHOLD_EUR
from ....core.resources import bundled_path
from ....domain.calculations.registry.export import derive_export_layouts_from_bindings
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.invoice_bindings import InvoiceObservation, resolve_invoice_binding_row_values
from ....domain.calculations.registry.loader import load_registry_tree
from ....domain.calculations.registry.schema_exports import ExportRecordDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REPOINTED_REVISIONS = ("2025-y-siguientes", "2011-2024")


def _revision(revision_id: str):
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return next(modelo for modelo in modelos if modelo.id == "347").revisions[revision_id]


def _declarado_record(revision) -> ExportRecordDefinition:
    return next(
        candidate
        for layout in derive_export_layouts_from_bindings(revision)
        for candidate in layout.records
        if candidate.id == "m347-declarado"
    )


def _observation(
    *,
    invoice_id: str,
    party_tax_id: str,
    party_legal_name: str,
    transaction_date: date,
    total: str,
    operation_clave: str,
    source_kind: BindingSourceKind = BindingSourceKind.PAYABLE_INVOICE,
    country_code: str = "ES",
) -> InvoiceObservation:
    return InvoiceObservation(
        invoice_id=invoice_id,
        source_kind=source_kind,
        party_tax_id=party_tax_id,
        country_code=country_code,
        transaction_date=transaction_date,
        base_amount=Decimal(total),
        invoice_total_amount=Decimal(total),
        operation_clave=operation_clave,
        party_legal_name=party_legal_name,
    )


@pytest.mark.parametrize("revision_id", _REPOINTED_REVISIONS)
def test_declarado_record_is_wired_for_row_indexed_binding_rendering(revision_id: str) -> None:
    """Guard the premise: the record this module measures is the repointed shape.

    Without this, every assertion below would pass vacuously against a record
    that reverted to a single fixed occurrence. Parametrized across both
    revisions -- the underlying defect names no revision qualifier, and both
    were already known calc-grade beforehand, so closing on one alone
    would narrow the fix's own completion criterion.
    """
    record = _declarado_record(_revision(revision_id))

    assert record.repeat == "binding_rows"
    assert record.row_field_casilla_ids["party_tax_id"] == "contraparte.nif"
    assert record.row_field_casilla_ids["importe_q1"] == "contraparte.importe-Q1"


@pytest.mark.parametrize("revision_id", _REPOINTED_REVISIONS)
def test_two_counterparties_resolve_two_distinct_rows_not_a_truncation(revision_id: str) -> None:
    """The multi-counterparty truncation defect, reproduced and proven fixed against the real bindings."""
    revision = _revision(revision_id)
    observations = (
        _observation(
            invoice_id="inv-1",
            party_tax_id="B11111112",
            party_legal_name="Contraparte Uno SL",
            transaction_date=date(2025, 2, 10),
            total="5000.00",
            operation_clave="A",
        ),
        _observation(
            invoice_id="inv-2",
            party_tax_id="C22222229",
            party_legal_name="Contraparte Dos SA",
            transaction_date=date(2025, 6, 15),
            total="3200.00",
            operation_clave="B",
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        ),
    )

    resolved = resolve_invoice_binding_row_values(revision, observations)
    row_indexes = {row_index for (_binding_id, row_index) in resolved}

    assert row_indexes == {1, 2}


@pytest.mark.parametrize("revision_id", _REPOINTED_REVISIONS)
def test_declaration_floor_gates_the_per_row_family_through_the_real_resolver(revision_id: str) -> None:
    """RD 1065/2007 art. 31's floor, proven for all three cases through the real resolver.

    Before this fix, the ``contraparte_clave`` per-row family applied NO
    threshold at all -- a real over-declaration bug, distinct from the
    under-declaration findings elsewhere in this area. This proves the
    fix routes through the one canonical comparison
    (``m347_declarable_party_ids``) rather than a new one written here: a
    counterparty BELOW the floor produces no row, one landing EXACTLY on it
    (the `>`, never `>=`, semantics the canonical comparison's own docstring
    names) produces no row either, and one ABOVE it still produces its row.
    """
    revision = _revision(revision_id)
    observations = (
        _observation(
            invoice_id="inv-below",
            party_tax_id="B11111112",
            party_legal_name="Contraparte Bajo Umbral SL",
            transaction_date=date(2025, 2, 10),
            total=str(M347_THRESHOLD_EUR - Decimal("0.01")),
            operation_clave="A",
        ),
        _observation(
            invoice_id="inv-exactly",
            party_tax_id="C22222229",
            party_legal_name="Contraparte Umbral Exacto SA",
            transaction_date=date(2025, 6, 15),
            total=str(M347_THRESHOLD_EUR),
            operation_clave="B",
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        ),
        _observation(
            invoice_id="inv-above",
            party_tax_id="D33333335",
            party_legal_name="Contraparte Sobre Umbral SL",
            transaction_date=date(2025, 9, 1),
            total=str(M347_THRESHOLD_EUR + Decimal("0.01")),
            operation_clave="A",
        ),
    )

    resolved = resolve_invoice_binding_row_values(revision, observations)
    row_indexes = {row_index for (_binding_id, row_index) in resolved}

    # Only the above-threshold counterparty produces a row: one row, not three.
    assert len(row_indexes) == 1
    resolved_values = set(resolved.values())
    assert "D33333335" in resolved_values
    assert "B11111112" not in resolved_values
    assert "C22222229" not in resolved_values


@pytest.mark.parametrize("revision_id", _REPOINTED_REVISIONS)
def test_clave_c_uses_its_own_lower_floor_alongside_the_general_one(revision_id: str) -> None:
    """RD 1065/2007 arts. 32.c/33.4's 300,51 EUR clave-C floor, through the real resolver.

    A beneficiary below the clave-C floor produces no row even though the
    amount would clear nothing at all; a beneficiary above it does. A THIRD
    party -- the SAME tax id as the below-floor clave-C beneficiary -- also
    carries an ORDINARY (clave B) operation above the clave-C floor but below
    the GENERAL floor: it must still produce no row, proving the two floors
    are judged independently rather than the lower one leaking into the
    general comparison.
    """
    revision = _revision(revision_id)
    observations = (
        _observation(
            invoice_id="inv-c-below",
            party_tax_id="B11111112",
            party_legal_name="Colegiado Bajo Umbral SL",
            transaction_date=date(2025, 2, 10),
            total=str(M347_CLAVE_C_THRESHOLD_EUR - Decimal("0.01")),
            operation_clave="C",
        ),
        _observation(
            invoice_id="inv-c-above",
            party_tax_id="C22222229",
            party_legal_name="Colegiado Sobre Umbral SA",
            transaction_date=date(2025, 6, 15),
            total=str(M347_CLAVE_C_THRESHOLD_EUR + Decimal("0.01")),
            operation_clave="C",
        ),
        _observation(
            invoice_id="inv-b-below-general",
            party_tax_id="B11111112",
            party_legal_name="Colegiado Bajo Umbral SL",
            transaction_date=date(2025, 3, 1),
            total=str(M347_CLAVE_C_THRESHOLD_EUR + Decimal("100.00")),
            operation_clave="B",
        ),
    )

    resolved = resolve_invoice_binding_row_values(revision, observations)
    resolved_values = set(resolved.values())

    # Only the above-clave-C-floor beneficiary produces a row.
    assert "C22222229" in resolved_values
    # The below-clave-C-floor beneficiary produces no clave-C row, AND its
    # unrelated clave-B operation (above the clave-C floor, below the
    # general one) produces no row either -- the two floors do not leak.
    assert "B11111112" not in resolved_values


@pytest.mark.parametrize("revision_id", _REPOINTED_REVISIONS)
def test_binding_rows_rendering_emits_one_occurrence_per_counterparty(revision_id: str) -> None:
    """The renderer itself, not just the resolver, emits every distinct counterparty row."""
    from .._record_renderer import _record_render_rows

    revision = _revision(revision_id)
    record = _declarado_record(revision)
    observations = (
        _observation(
            invoice_id="inv-1",
            party_tax_id="B11111112",
            party_legal_name="Contraparte Uno SL",
            transaction_date=date(2025, 2, 10),
            total="5000.00",
            operation_clave="A",
        ),
        _observation(
            invoice_id="inv-2",
            party_tax_id="C22222229",
            party_legal_name="Contraparte Dos SA",
            transaction_date=date(2025, 6, 15),
            total="3200.00",
            operation_clave="B",
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        ),
        _observation(
            invoice_id="inv-3",
            party_tax_id="D33333335",
            party_legal_name="Contraparte Tres SL",
            transaction_date=date(2025, 9, 1),
            total="7000.00",
            operation_clave="A",
        ),
    )

    resolved = resolve_invoice_binding_row_values(revision, observations)
    binding_values: dict[tuple[BindingId, int | None], object] = dict(resolved.items())
    rendered = _record_render_rows(record, binding_values, {})

    assert len({row.row_index for row in rendered}) == 3


@pytest.mark.parametrize("revision_id", _REPOINTED_REVISIONS)
def test_quarterly_amounts_sum_to_the_annual_total_for_a_real_multi_quarter_counterparty(revision_id: str) -> None:
    """The internal-consistency proof the repoint's own condition required.

    One real invoice in each of the four calendar quarters for the SAME
    counterparty; asserts the four resolved quarterly row values sum to the
    resolved annual total exactly. A row whose quarters do not sum to its
    annual total is a defect AEAT will reject, and this is the assertion that
    would catch a bucketing off-by-one at a year or quarter boundary.
    """
    revision = _revision(revision_id)
    observations = (
        _observation(
            invoice_id="q1",
            party_tax_id="B11111112",
            party_legal_name="Contraparte Uno SL",
            transaction_date=date(2025, 1, 15),
            total="1000.00",
            operation_clave="A",
        ),
        _observation(
            invoice_id="q2",
            party_tax_id="B11111112",
            party_legal_name="Contraparte Uno SL",
            transaction_date=date(2025, 4, 20),
            total="2000.00",
            operation_clave="A",
        ),
        _observation(
            invoice_id="q3",
            party_tax_id="B11111112",
            party_legal_name="Contraparte Uno SL",
            transaction_date=date(2025, 8, 5),
            total="3000.00",
            operation_clave="A",
        ),
        _observation(
            invoice_id="q4",
            party_tax_id="B11111112",
            party_legal_name="Contraparte Uno SL",
            transaction_date=date(2025, 12, 25),
            total="4000.00",
            operation_clave="A",
        ),
    )

    resolved = resolve_invoice_binding_row_values(revision, observations)

    def _value(binding_suffix: str) -> Decimal:
        binding_id = next(bid for (bid, _row) in resolved if bid.endswith(binding_suffix))
        row_index = next(row for (bid, row) in resolved if bid == binding_id)
        value = resolved[(binding_id, row_index)]
        assert isinstance(value, Decimal)
        return value

    annual = _value("-importe")
    q1 = _value("-importe-q1")
    q2 = _value("-importe-q2")
    q3 = _value("-importe-q3")
    q4 = _value("-importe-q4")

    assert (q1, q2, q3, q4) == (Decimal("1000.00"), Decimal("2000.00"), Decimal("3000.00"), Decimal("4000.00"))
    assert annual == q1 + q2 + q3 + q4 == Decimal("10000.00")


@pytest.mark.parametrize("revision_id", _REPOINTED_REVISIONS)
def test_a_quarter_boundary_date_classifies_into_the_correct_quarter(revision_id: str) -> None:
    """The off-by-one this assertion class exists to catch, at the Q1/Q2 boundary.

    One invoice dated the last day of Q1 and one dated the first day of Q2,
    for the same counterparty. A bucketing off-by-one would either merge both
    into one quarter or, worse, misfile the boundary date into the wrong one.
    """
    revision = _revision(revision_id)
    observations = (
        _observation(
            invoice_id="boundary-q1",
            party_tax_id="B11111112",
            party_legal_name="Contraparte Uno SL",
            transaction_date=date(2025, 3, 31),
            total="2000.00",
            operation_clave="A",
        ),
        _observation(
            invoice_id="boundary-q2",
            party_tax_id="B11111112",
            party_legal_name="Contraparte Uno SL",
            transaction_date=date(2025, 4, 1),
            total="1200.00",
            operation_clave="A",
        ),
    )

    resolved = resolve_invoice_binding_row_values(revision, observations)

    def _value(binding_suffix: str) -> Decimal:
        binding_id = next(bid for (bid, _row) in resolved if bid.endswith(binding_suffix))
        row_index = next(row for (bid, row) in resolved if bid == binding_id)
        value = resolved[(binding_id, row_index)]
        assert isinstance(value, Decimal)
        return value

    assert _value("-importe-q1") == Decimal("2000.00")
    assert _value("-importe-q2") == Decimal("1200.00")
    assert _value("-importe-q3") == Decimal("0")
    assert _value("-importe-q4") == Decimal("0")
    assert _value("-importe") == Decimal("3200.00")


@pytest.mark.parametrize("revision_id", _REPOINTED_REVISIONS)
def test_conditional_money_fields_stay_scalar_and_are_not_fabricated(revision_id: str) -> None:
    """The conditional fields (importe-metalico, transmisiones, ...) stay off the binding path.

    Confirms the repointed scope is exactly the money fields this repoint built
    a real per-row source for, and that the conditional fields the diseño
    itself gates with an explicit "Sólo..."/exception clause were
    deliberately left unbound rather than silently dropped from the record.
    """
    record = _declarado_record(_revision(revision_id))

    bound_casilla_ids = {
        record.row_field_casilla_ids["party_tax_id"],
        record.row_field_casilla_ids["party_legal_name"],
        record.row_field_casilla_ids["clave"],
        record.row_field_casilla_ids["importe_total"],
        record.row_field_casilla_ids["importe_q1"],
        record.row_field_casilla_ids["importe_q2"],
        record.row_field_casilla_ids["importe_q3"],
        record.row_field_casilla_ids["importe_q4"],
        record.row_field_casilla_ids["country_code"],
    }
    conditional_casillas: set[CasillaId] = {
        field.casilla_id
        for field in record.fields
        if field.casilla_id is not None and field.casilla_id not in bound_casilla_ids
    }

    assert "contraparte.importe-metalico" in conditional_casillas
    assert "contraparte.importe-transmisiones-inmuebles" in conditional_casillas
    assert "contraparte.operacion-seguro" in conditional_casillas
    assert "contraparte.arrendamiento-local-negocio" in conditional_casillas
    assert "contraparte.provincia-codigo" in conditional_casillas


@pytest.mark.parametrize("revision_id", _REPOINTED_REVISIONS)
def test_each_counterparty_renders_its_own_country_not_the_first_ones(revision_id: str) -> None:
    """`país-código` per row, not one value stamped across every occurrence.

    `país-código` is a real per-row binding sourced from each observation's
    own `country_code`. Asserts the VALUES, not merely the row count -- a
    record stamping one counterparty's country onto every row would still
    pass a count-only assertion.
    """
    revision = _revision(revision_id)
    observations = (
        _observation(
            invoice_id="inv-es",
            party_tax_id="B11111112",
            party_legal_name="Contraparte Uno SL",
            transaction_date=date(2025, 2, 10),
            total="5000.00",
            operation_clave="A",
            country_code="ES",
        ),
        _observation(
            invoice_id="inv-us",
            party_tax_id="C22222229",
            party_legal_name="Acme Imports Inc",
            transaction_date=date(2025, 6, 15),
            total="3200.00",
            operation_clave="B",
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            country_code="US",
        ),
    )

    resolved = resolve_invoice_binding_row_values(revision, observations)
    pais_binding_id = next(bid for (bid, _row) in resolved if bid.endswith("-pais-codigo"))
    countries_by_row = {row: resolved[(pais_binding_id, row)] for (bid, row) in resolved if bid == pais_binding_id}

    assert set(countries_by_row.values()) == {"ES", "US"}
    assert len(countries_by_row) == 2, "each counterparty must resolve its OWN pais-codigo row"
