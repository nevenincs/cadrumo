"""Modelo 349 invoice binding registry tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, cast

import pytest

from .....core.aggregation import BindingSourceKind, IntracomOperationType
from .....core.casilla_id import CasillaId
from ..binding_selector_utils import selector_as_dict
from ..bindings import resolve_available_bound_inputs_by_casilla_id
from ..invoice_bindings import (
    InvoiceObservation,
    resolve_invoice_binding_row_values,
    resolve_invoice_binding_values,
)
from ..schema import BindingDefinition
from ..schema_input_kind import InputKind
from ._modelo_349_registry_support import (
    _DECL_IMPORTE_OPERACIONES_CASILLA,
    _DECL_IMPORTE_RECTIFICACIONES_CASILLA,
    _DECL_NUMERO_OPERADORES_CASILLA,
    _DECL_NUMERO_RECTIFICACIONES_CASILLA,
    _DECLARANT_SUMMARY_CASILLAS,
    _M349_SUBSTANTIVE_BINDING_LEGAL_REFS,
    _load_modelo_349,
    _modelo_349_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


def _selector(binding: BindingDefinition) -> dict[str, Any]:
    return selector_as_dict(binding)


def test_committed_modelo_349_declares_invoice_source_bindings_for_declarant_summary() -> None:
    revision = _modelo_349_revision()

    summary_bindings: dict[str, BindingDefinition] = {
        b.id: b
        for b in revision.bindings
        if b.source == "m349_intracommunity_operation" and b.aggregation is not None and b.aggregation.op != "rows"
    }
    assert set(summary_bindings) == {
        "iva-349-declarante-numero-operadores",
        "iva-349-declarante-importe-operaciones",
        "iva-349-declarante-numero-rectificaciones",
        "iva-349-declarante-importe-rectificaciones",
    }

    expected_claves = ("E", "M", "H", "A", "T", "S", "I", "R", "D", "C")
    for binding_id in (
        "iva-349-declarante-numero-operadores",
        "iva-349-declarante-importe-operaciones",
    ):
        selector = _selector(summary_bindings[binding_id])
        assert selector["rectification_scope"] == "exclude_rectifications"
        assert cast("tuple[str, ...]", selector["claves"]) == expected_claves
    for binding_id in (
        "iva-349-declarante-numero-rectificaciones",
        "iva-349-declarante-importe-rectificaciones",
    ):
        selector = _selector(summary_bindings[binding_id])
        assert selector["rectification_scope"] == "only_rectifications"
        assert cast("tuple[str, ...]", selector["claves"]) == expected_claves
    # Casilla 04 is the sum of the rectified bases (aeat-dr-349-2020-current type 1
    # pos. 171-185 over type 2 pos. 153-165), not the rectification deltas.
    assert _selector(summary_bindings["iva-349-declarante-importe-rectificaciones"])["fact"] == "base_sum"


def test_core_intracom_operation_type_covers_modelo_349_registry_claves() -> None:
    """The shared invoice enum must cover the official M349 clave-de-operacion set."""

    revision = _modelo_349_revision()
    registry_claves = {
        clave
        for binding in revision.bindings
        if binding.source is BindingSourceKind.M349_INTRACOMMUNITY_OPERATION
        for clave in cast("tuple[str, ...]", _selector(binding).get("claves", ()))
    }

    assert {member.value for member in IntracomOperationType} == registry_claves


def test_committed_modelo_349_invoice_bindings_resolve_substantive_legal_refs() -> None:
    modelo, catalogues = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    invoice_bindings = [binding for binding in revision.bindings if binding.source == "m349_intracommunity_operation"]

    assert len(invoice_bindings) == 17
    assert set(catalogues.legal) >= _M349_SUBSTANTIVE_BINDING_LEGAL_REFS

    for binding in invoice_bindings:
        refs = set(binding.legal_refs)
        unresolved_refs = sorted(ref for ref in refs if ref not in catalogues.legal)
        assert not unresolved_refs, f"binding {binding.id!r} has unresolved legal refs: {unresolved_refs!r}"
        assert refs >= _M349_SUBSTANTIVE_BINDING_LEGAL_REFS, (
            f"binding {binding.id!r} is missing substantive M349 legal refs: "
            f"{sorted(_M349_SUBSTANTIVE_BINDING_LEGAL_REFS - refs)!r}"
        )
        assert "ley-37-1992:art-141" not in refs, (
            f"binding {binding.id!r} must not cite LIVA art. 141; that article is the travel-agency "
            "special regime, not M349 triangular or intracommunity operation grounding"
        )


def test_committed_modelo_349_invoice_binding_resolver_aggregates_synthetic_ledger() -> None:
    revision = _modelo_349_revision()

    non_rect_obs = (
        InvoiceObservation(
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            invoice_id="inv-de-1",
            party_tax_id="DE123456789",
            country_code="DE",
            transaction_date=date(2026, 3, 1),
            base_amount=Decimal("1000.00"),
            intracommunity_clave="E",
        ),
        InvoiceObservation(
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            invoice_id="inv-fr-1",
            party_tax_id="FR12345678901",
            country_code="FR",
            transaction_date=date(2026, 3, 5),
            base_amount=Decimal("500.50"),
            intracommunity_clave="S",
        ),
    )
    rect_obs = InvoiceObservation(
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        invoice_id="inv-it-1-rect",
        party_tax_id="IT12345678901",
        country_code="IT",
        transaction_date=date(2026, 3, 8),
        base_amount=Decimal("200.00"),
        intracommunity_clave="E",
        is_rectification=True,
        rectified_base_previous=Decimal("180.00"),
        rectified_period="4T",
        rectified_year=2025,
    )
    observations = (*non_rect_obs, rect_obs)

    resolved = resolve_invoice_binding_values(revision, observations)

    assert set(resolved) == {
        "iva-349-declarante-numero-operadores",
        "iva-349-declarante-importe-operaciones",
        "iva-349-declarante-numero-rectificaciones",
        "iva-349-declarante-importe-rectificaciones",
    }

    # Operator count and total base are derived directly from the non-rectification
    # observations — the resolver must sum distinct operators and their base amounts.
    expected_num_operators = Decimal(len({obs.party_tax_id for obs in non_rect_obs}))
    expected_importe_operaciones = sum((obs.base_amount for obs in non_rect_obs), Decimal("0"))
    assert resolved["iva-349-declarante-numero-operadores"] == expected_num_operators
    assert resolved["iva-349-declarante-importe-operaciones"] == expected_importe_operaciones

    # Rectification count is the number of rectification observations.
    assert resolved["iva-349-declarante-numero-rectificaciones"] == Decimal("1")

    # Rectification importe is the sum of the rectified bases (instructions casilla 04:
    # "base imponible rectificada"), not the delta against the previous base.
    assert resolved["iva-349-declarante-importe-rectificaciones"] == rect_obs.base_amount


def test_committed_modelo_349_invoice_binding_resolver_counts_payable_service_acquisitions() -> None:
    revision = _modelo_349_revision()

    observations = (
        InvoiceObservation(
            invoice_id="inv-it-service-acq",
            source_kind=BindingSourceKind.PAYABLE_INVOICE,
            party_tax_id="IT12345678901",
            country_code="IT",
            transaction_date=date(2026, 3, 1),
            base_amount=Decimal("3000.00"),
            intracommunity_clave="I",
        ),
    )

    resolved = resolve_invoice_binding_values(revision, observations)

    assert resolved["iva-349-declarante-numero-operadores"] == Decimal("1")
    assert resolved["iva-349-declarante-importe-operaciones"] == Decimal("3000.00")


def test_committed_modelo_349_row_resolver_reads_both_directions_into_one_record_sequence() -> None:
    revision = _modelo_349_revision()

    observations = (
        InvoiceObservation(
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            invoice_id="inv-de-sale",
            party_tax_id="DE111111111",
            country_code="DE",
            transaction_date=date(2026, 3, 1),
            base_amount=Decimal("1000.00"),
            intracommunity_clave="E",
            party_legal_name="SALE GMBH",
        ),
        InvoiceObservation(
            invoice_id="inv-de-acq",
            source_kind=BindingSourceKind.PAYABLE_INVOICE,
            party_tax_id="DE222222222",
            country_code="DE",
            transaction_date=date(2026, 3, 2),
            base_amount=Decimal("750.00"),
            intracommunity_clave="A",
            party_legal_name="SUPPLIER GMBH",
        ),
        InvoiceObservation(
            invoice_id="inv-it-service-acq",
            source_kind=BindingSourceKind.PAYABLE_INVOICE,
            party_tax_id="IT12345678901",
            country_code="IT",
            transaction_date=date(2026, 3, 3),
            base_amount=Decimal("3000.00"),
            intracommunity_clave="I",
            party_legal_name="SERVIZI SRL",
        ),
    )

    rows = resolve_invoice_binding_row_values(revision, observations)

    assert rows[("iva-349-operador-row-clave", 1)] == "E"
    assert rows[("iva-349-operador-row-nif", 1)] == "111111111"
    assert rows[("iva-349-operador-row-clave", 2)] == "A"
    assert rows[("iva-349-operador-row-nif", 2)] == "222222222"
    assert rows[("iva-349-operador-row-clave", 3)] == "I"
    assert rows[("iva-349-operador-row-nif", 3)] == "12345678901"
    assert ("iva-349-operador-row-clave", 4) not in rows


def test_committed_modelo_349_triangular_operation_from_both_directions_is_one_record() -> None:
    """Clave T bought and sold with one operator is one operador record (aeat-dr-349-2020-current type 2)."""
    revision = _modelo_349_revision()
    observations = tuple(
        InvoiceObservation(
            source_kind=source_kind,
            invoice_id=invoice_id,
            party_tax_id="FR12345678901",
            country_code="FR",
            transaction_date=date(2026, 3, day),
            base_amount=base,
            intracommunity_clave="T",
            party_legal_name="TRIANGLE SARL",
        )
        for source_kind, invoice_id, day, base in (
            (BindingSourceKind.COLLECTIBLE_INVOICE, "inv-fr-t-sale", 4, Decimal("400.00")),
            (BindingSourceKind.PAYABLE_INVOICE, "inv-fr-t-acq", 5, Decimal("250.00")),
        )
    )

    rows = resolve_invoice_binding_row_values(revision, observations)
    values = resolve_invoice_binding_values(revision, observations)

    assert rows[("iva-349-operador-row-clave", 1)] == "T"
    assert rows[("iva-349-operador-row-base", 1)] == Decimal("650.00")
    assert ("iva-349-operador-row-clave", 2) not in rows
    assert values["iva-349-declarante-numero-operadores"] == Decimal("1")
    assert values["iva-349-declarante-importe-operaciones"] == Decimal("650.00")


def test_committed_modelo_349_construct_includes_invoice_bindings() -> None:
    revision = _modelo_349_revision()
    construct = revision.constructs[0]
    # Every 349 binding reads the combined-direction intra-community population.
    assert set(construct.bindings) == {b.id for b in revision.bindings}
    assert {b.source for b in revision.bindings} == {"m349_intracommunity_operation"}


def test_committed_modelo_349_declarant_summary_casillas_are_bound_to_invoice_bindings() -> None:
    revision = _modelo_349_revision()

    casillas_by_id = {c.id: c for c in revision.casillas}
    expected_bindings: dict[CasillaId, str] = {
        _DECL_NUMERO_OPERADORES_CASILLA: "iva-349-declarante-numero-operadores",
        _DECL_IMPORTE_OPERACIONES_CASILLA: "iva-349-declarante-importe-operaciones",
        _DECL_NUMERO_RECTIFICACIONES_CASILLA: "iva-349-declarante-numero-rectificaciones",
        _DECL_IMPORTE_RECTIFICACIONES_CASILLA: "iva-349-declarante-importe-rectificaciones",
    }
    for casilla_id, expected_binding in expected_bindings.items():
        casilla = casillas_by_id[casilla_id]
        assert casilla.input_kind == InputKind.BOUND
        assert casilla.binding == expected_binding


def test_committed_modelo_349_declares_operador_and_rectificacion_row_bindings() -> None:
    revision = _modelo_349_revision()

    row_bindings: dict[str, BindingDefinition] = {
        b.id: b
        for b in revision.bindings
        if b.source == "m349_intracommunity_operation" and b.aggregation is not None and b.aggregation.op == "rows"
    }
    expected_operador_row_bindings = {
        "iva-349-operador-row-codigo-pais",
        "iva-349-operador-row-nif",
        "iva-349-operador-row-apellidos",
        "iva-349-operador-row-clave",
        "iva-349-operador-row-base",
    }
    expected_rectificacion_row_bindings = {
        "iva-349-rectificacion-row-codigo-pais",
        "iva-349-rectificacion-row-nif",
        "iva-349-rectificacion-row-apellidos",
        "iva-349-rectificacion-row-clave",
        "iva-349-rectificacion-row-ejercicio",
        "iva-349-rectificacion-row-periodo",
        "iva-349-rectificacion-row-base-rectificada",
        "iva-349-rectificacion-row-base-anterior",
    }
    assert set(row_bindings) == expected_operador_row_bindings | expected_rectificacion_row_bindings

    for binding_id in expected_operador_row_bindings:
        row_selector = _selector(row_bindings[binding_id])
        assert row_selector["grouping"] == "operator_clave"
        assert row_selector["rectification_scope"] == "exclude_rectifications"
    for binding_id in expected_rectificacion_row_bindings:
        row_selector = _selector(row_bindings[binding_id])
        assert row_selector["grouping"] == "operator_clave_period"
        assert row_selector["rectification_scope"] == "only_rectifications"


def test_committed_modelo_349_operador_row_resolver_groups_by_operator_and_clave() -> None:
    revision = _modelo_349_revision()

    observations = (
        InvoiceObservation(
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            invoice_id="inv-de-1",
            party_tax_id="DE123456789",
            country_code="DE",
            transaction_date=date(2026, 3, 1),
            base_amount=Decimal("1000.00"),
            intracommunity_clave="E",
            party_legal_name="ALEMAN GMBH",
        ),
        InvoiceObservation(
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            invoice_id="inv-de-2",
            party_tax_id="DE123456789",
            country_code="DE",
            transaction_date=date(2026, 3, 5),
            base_amount=Decimal("500.00"),
            intracommunity_clave="E",
            party_legal_name="ALEMAN GMBH",
        ),
        InvoiceObservation(
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            invoice_id="inv-fr-1",
            party_tax_id="FR12345678901",
            country_code="FR",
            transaction_date=date(2026, 3, 7),
            base_amount=Decimal("300.50"),
            intracommunity_clave="S",
            party_legal_name="FRANCE SARL",
        ),
    )

    rows = resolve_invoice_binding_row_values(revision, observations)

    # Two row groups: (DE, DE123456789, E) at row 1 and (FR, FR12345678901, S) at row 2.
    assert rows[("iva-349-operador-row-codigo-pais", 1)] == "DE"
    assert rows[("iva-349-operador-row-nif", 1)] == "123456789"
    assert rows[("iva-349-operador-row-apellidos", 1)] == "ALEMAN GMBH"
    assert rows[("iva-349-operador-row-clave", 1)] == "E"
    # Both German observations must contribute to row 1's base.
    # Assertion pins the grouping contract by requiring the aggregate
    # to exceed the larger single-observation value.
    row_1_base = rows[("iva-349-operador-row-base", 1)]
    assert isinstance(row_1_base, Decimal)
    assert row_1_base > Decimal("1000.00"), (
        f"row 1 base = {row_1_base} not greater than max DE observation 1000.00 — "
        f"second German observation did not contribute to the group"
    )
    assert rows[("iva-349-operador-row-codigo-pais", 2)] == "FR"
    assert rows[("iva-349-operador-row-nif", 2)] == "12345678901"
    assert rows[("iva-349-operador-row-apellidos", 2)] == "FRANCE SARL"
    assert rows[("iva-349-operador-row-clave", 2)] == "S"
    # Single-observation row: identity passthrough of the fixture value.
    assert rows[("iva-349-operador-row-base", 2)] == Decimal("300.50")


def test_committed_modelo_349_rectificacion_row_resolver_groups_by_operator_clave_period() -> None:
    revision = _modelo_349_revision()

    observations = (
        InvoiceObservation(
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            invoice_id="inv-de-rect",
            party_tax_id="DE123456789",
            country_code="DE",
            transaction_date=date(2026, 3, 1),
            base_amount=Decimal("1100.00"),
            intracommunity_clave="E",
            party_legal_name="ALEMAN GMBH",
            is_rectification=True,
            rectified_base_previous=Decimal("1000.00"),
            rectified_period="2T",
            rectified_year=2025,
        ),
        InvoiceObservation(
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            invoice_id="inv-it-rect",
            party_tax_id="IT12345678901",
            country_code="IT",
            transaction_date=date(2026, 3, 5),
            base_amount=Decimal("200.00"),
            intracommunity_clave="E",
            party_legal_name="ITALIA SRL",
            is_rectification=True,
            rectified_base_previous=Decimal("180.00"),
            rectified_period="4T",
            rectified_year=2025,
        ),
    )

    rows = resolve_invoice_binding_row_values(revision, observations)

    # DE/DE123456789/E/2025/2T at row 1, IT/IT12345678901/E/2025/4T at row 2.
    assert rows[("iva-349-rectificacion-row-codigo-pais", 1)] == "DE"
    assert rows[("iva-349-rectificacion-row-nif", 1)] == "123456789"
    assert rows[("iva-349-rectificacion-row-apellidos", 1)] == "ALEMAN GMBH"
    assert rows[("iva-349-rectificacion-row-clave", 1)] == "E"
    assert rows[("iva-349-rectificacion-row-ejercicio", 1)] == "2025"
    assert rows[("iva-349-rectificacion-row-periodo", 1)] == "2T"
    assert rows[("iva-349-rectificacion-row-base-rectificada", 1)] == Decimal("1100.00")
    assert rows[("iva-349-rectificacion-row-base-anterior", 1)] == Decimal("1000.00")
    assert rows[("iva-349-rectificacion-row-codigo-pais", 2)] == "IT"
    assert rows[("iva-349-rectificacion-row-base-rectificada", 2)] == Decimal("200.00")
    assert rows[("iva-349-rectificacion-row-base-anterior", 2)] == Decimal("180.00")


def test_committed_modelo_349_full_invoice_to_casilla_pipeline() -> None:
    revision = _modelo_349_revision()

    non_rect_obs = (
        InvoiceObservation(
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            invoice_id="inv-de-1",
            party_tax_id="DE123456789",
            country_code="DE",
            transaction_date=date(2026, 3, 1),
            base_amount=Decimal("1000.00"),
            intracommunity_clave="E",
        ),
        InvoiceObservation(
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            invoice_id="inv-fr-1",
            party_tax_id="FR12345678901",
            country_code="FR",
            transaction_date=date(2026, 3, 5),
            base_amount=Decimal("500.50"),
            intracommunity_clave="S",
        ),
    )
    rect_obs = InvoiceObservation(
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        invoice_id="inv-it-1-rect",
        party_tax_id="IT12345678901",
        country_code="IT",
        transaction_date=date(2026, 3, 8),
        base_amount=Decimal("200.00"),
        intracommunity_clave="E",
        is_rectification=True,
        rectified_base_previous=Decimal("180.00"),
        rectified_period="4T",
        rectified_year=2025,
    )
    observations = (*non_rect_obs, rect_obs)

    binding_values = resolve_invoice_binding_values(revision, observations)
    casilla_values = resolve_available_bound_inputs_by_casilla_id(revision, binding_values)

    # Assert the four expected casilla keys are present — wiring check.
    expected_casilla_keys = set(_DECLARANT_SUMMARY_CASILLAS)
    assert expected_casilla_keys == set(casilla_values.keys()), (
        "invoice-to-casilla pipeline must produce exactly the four declarant casillas"
    )

    # Operator and importe values must equal what the resolver computed from the
    # non-rectification observations.
    assert casilla_values[_DECL_NUMERO_OPERADORES_CASILLA] == binding_values["iva-349-declarante-numero-operadores"]
    assert casilla_values[_DECL_IMPORTE_OPERACIONES_CASILLA] == binding_values["iva-349-declarante-importe-operaciones"]

    # Rectification casillas must pass through from binding to casilla unchanged.
    assert (
        casilla_values[_DECL_NUMERO_RECTIFICACIONES_CASILLA]
        == (binding_values["iva-349-declarante-numero-rectificaciones"])
    )
    assert (
        casilla_values[_DECL_IMPORTE_RECTIFICACIONES_CASILLA]
        == (binding_values["iva-349-declarante-importe-rectificaciones"])
    )

    # Casilla 04 carries the rectified base (200.00), not its 20.00 delta against the previous base.
    assert casilla_values[_DECL_IMPORTE_RECTIFICACIONES_CASILLA] == Decimal("200.00")
