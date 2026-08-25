"""Modelo 349 invoice binding registry tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, cast

import pytest

from .....core import BindingSourceKind, CasillaId, IntracomOperationType
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.bindings import InvoiceObservation, invoice_binding_requirements, resolve_available_bound_inputs_by_casilla_id, resolve_invoice_binding_row_values, resolve_invoice_binding_values
from ..binding_selector_utils import selector_as_dict
from ..schema import DataBindingDefinition
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

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _selector(binding: DataBindingDefinition) -> dict[str, Any]:
    return selector_as_dict(binding)


def test_committed_modelo_349_declares_invoice_source_bindings_for_declarant_summary() -> None:
    revision = _modelo_349_revision()

    collectible_bindings: dict[str, DataBindingDefinition] = {
        b.id: b
        for b in revision.bindings
        if b.source == "collectible_invoice" and b.aggregation is not None and b.aggregation.op != "rows"
    }
    payable_bindings: dict[str, DataBindingDefinition] = {
        b.id: b
        for b in revision.bindings
        if b.source == "payable_invoice" and b.aggregation is not None and b.aggregation.op != "rows"
    }
    expected_collectible = {
        "iva-349-declarante-numero-operadores",
        "iva-349-declarante-importe-operaciones",
        "iva-349-declarante-numero-rectificaciones",
        "iva-349-declarante-importe-rectificaciones",
    }
    expected_payable = {f"{binding_id}-adquisicion" for binding_id in expected_collectible}
    assert set(collectible_bindings) == expected_collectible
    assert set(payable_bindings) == expected_payable

    expected_claves = ("E", "M", "H", "A", "T", "S", "I", "R", "D", "C")
    for binding_id in (
        "iva-349-declarante-numero-operadores",
        "iva-349-declarante-importe-operaciones",
    ):
        binding = collectible_bindings[binding_id]
        selector = _selector(binding)
        assert selector["rectification_scope"] == "exclude_rectifications"
        assert cast("tuple[str, ...]", selector["claves"]) == expected_claves
    for binding_id in (
        "iva-349-declarante-numero-rectificaciones",
        "iva-349-declarante-importe-rectificaciones",
    ):
        binding = collectible_bindings[binding_id]
        selector = _selector(binding)
        assert selector["rectification_scope"] == "only_rectifications"
        assert cast("tuple[str, ...]", selector["claves"]) == expected_claves

    expected_payable_claves = ("A", "I", "T")
    for binding_id in (
        "iva-349-declarante-numero-operadores-adquisicion",
        "iva-349-declarante-importe-operaciones-adquisicion",
    ):
        binding = payable_bindings[binding_id]
        selector = _selector(binding)
        assert selector["rectification_scope"] == "exclude_rectifications"
        assert cast("tuple[str, ...]", selector["claves"]) == expected_payable_claves
    for binding_id in (
        "iva-349-declarante-numero-rectificaciones-adquisicion",
        "iva-349-declarante-importe-rectificaciones-adquisicion",
    ):
        binding = payable_bindings[binding_id]
        selector = _selector(binding)
        assert selector["rectification_scope"] == "only_rectifications"
        assert cast("tuple[str, ...]", selector["claves"]) == expected_payable_claves


def test_core_intracom_operation_type_covers_modelo_349_registry_claves() -> None:
    """The shared invoice enum must cover the official M349 clave-de-operacion set."""

    revision = _modelo_349_revision()
    registry_claves = {
        clave
        for binding in revision.bindings
        if binding.source in {BindingSourceKind.COLLECTIBLE_INVOICE, BindingSourceKind.PAYABLE_INVOICE}
        for clave in cast("tuple[str, ...]", _selector(binding).get("claves", ()))
    }

    assert {member.value for member in IntracomOperationType} == registry_claves


def test_committed_modelo_349_invoice_binding_requirements_split_by_rectification_scope() -> None:
    revision = _modelo_349_revision()
    requirements = invoice_binding_requirements(revision)

    by_scope_and_claves = {(req.rectification_scope, req.claves): req for req in requirements}
    expected_collectible_claves = ("A", "C", "D", "E", "H", "I", "M", "R", "S", "T")
    expected_payable_claves = ("A", "I", "T")
    assert set(by_scope_and_claves) == {
        ("exclude_rectifications", expected_collectible_claves),
        ("only_rectifications", expected_collectible_claves),
        ("exclude_rectifications", expected_payable_claves),
        ("only_rectifications", expected_payable_claves),
    }
    expected_collectible_exclude = {
        "iva-349-declarante-numero-operadores",
        "iva-349-declarante-importe-operaciones",
        "iva-349-operador-row-codigo-pais",
        "iva-349-operador-row-nif",
        "iva-349-operador-row-apellidos",
        "iva-349-operador-row-clave",
        "iva-349-operador-row-base",
    }
    expected_collectible_only = {
        "iva-349-declarante-numero-rectificaciones",
        "iva-349-declarante-importe-rectificaciones",
        "iva-349-rectificacion-row-codigo-pais",
        "iva-349-rectificacion-row-nif",
        "iva-349-rectificacion-row-apellidos",
        "iva-349-rectificacion-row-clave",
        "iva-349-rectificacion-row-ejercicio",
        "iva-349-rectificacion-row-periodo",
        "iva-349-rectificacion-row-base-rectificada",
        "iva-349-rectificacion-row-base-anterior",
    }
    expected_payable_exclude = {f"{binding_id}-adquisicion" for binding_id in expected_collectible_exclude}
    expected_payable_only = {f"{binding_id}-adquisicion" for binding_id in expected_collectible_only}
    assert (
        set(by_scope_and_claves[("exclude_rectifications", expected_collectible_claves)].binding_ids)
        == expected_collectible_exclude
    )
    assert (
        set(by_scope_and_claves[("only_rectifications", expected_collectible_claves)].binding_ids)
        == expected_collectible_only
    )
    assert (
        set(by_scope_and_claves[("exclude_rectifications", expected_payable_claves)].binding_ids)
        == expected_payable_exclude
    )
    assert (
        set(by_scope_and_claves[("only_rectifications", expected_payable_claves)].binding_ids) == expected_payable_only
    )


def test_committed_modelo_349_invoice_bindings_resolve_substantive_legal_refs() -> None:
    modelo, catalogues = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    invoice_bindings = [
        binding for binding in revision.bindings if binding.source in {"collectible_invoice", "payable_invoice"}
    ]

    assert len(invoice_bindings) == 34
    assert sum(1 for binding in invoice_bindings if binding.source == "collectible_invoice") == 17
    assert sum(1 for binding in invoice_bindings if binding.source == "payable_invoice") == 17
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

    # Assert the source-specific scalar binding keys are all present.
    expected_collectible_keys = {
        "iva-349-declarante-numero-operadores",
        "iva-349-declarante-importe-operaciones",
        "iva-349-declarante-numero-rectificaciones",
        "iva-349-declarante-importe-rectificaciones",
    }
    expected_payable_keys = {f"{binding_id}-adquisicion" for binding_id in expected_collectible_keys}
    assert expected_collectible_keys | expected_payable_keys == set(resolved.keys()), (
        "resolver must populate the four public declarant bindings plus payable acquisition mirrors"
    )

    # Operator count and total base are derived directly from the non-rectification
    # observations — the resolver must sum distinct operators and their base amounts.
    expected_num_operators = Decimal(len({obs.party_tax_id for obs in non_rect_obs}))
    expected_importe_operaciones = sum((obs.base_amount for obs in non_rect_obs), Decimal("0"))
    assert resolved["iva-349-declarante-numero-operadores"] == expected_num_operators
    assert resolved["iva-349-declarante-importe-operaciones"] == expected_importe_operaciones

    # Rectification count is the number of rectification observations.
    assert resolved["iva-349-declarante-numero-rectificaciones"] == Decimal("1")

    # Rectification importe is the absolute delta between new and previous base,
    # derived from the rectification observation supplied to the resolver.
    assert rect_obs.rectified_base_previous is not None
    expected_rect_delta = abs(rect_obs.base_amount - rect_obs.rectified_base_previous)
    assert resolved["iva-349-declarante-importe-rectificaciones"] == expected_rect_delta
    for binding_id in expected_payable_keys:
        assert resolved[binding_id] == Decimal("0")


def test_committed_modelo_349_invoice_binding_resolver_separates_payable_service_acquisitions() -> None:
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

    assert resolved["iva-349-declarante-numero-operadores"] == Decimal("0")
    assert resolved["iva-349-declarante-importe-operaciones"] == Decimal("0")
    assert resolved["iva-349-declarante-numero-operadores-adquisicion"] == Decimal("1")
    assert resolved["iva-349-declarante-importe-operaciones-adquisicion"] == Decimal("3000.00")


def test_committed_modelo_349_row_resolver_appends_payable_acquisitions_to_public_export_rows() -> None:
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
    assert rows[("iva-349-operador-row-clave-adquisicion", 1)] == "A"
    assert rows[("iva-349-operador-row-nif-adquisicion", 1)] == "222222222"
    assert rows[("iva-349-operador-row-clave-adquisicion", 2)] == "I"
    assert rows[("iva-349-operador-row-nif-adquisicion", 2)] == "12345678901"
    assert rows[("iva-349-operador-row-clave", 2)] == "A"
    assert rows[("iva-349-operador-row-nif", 2)] == "222222222"
    assert rows[("iva-349-operador-row-clave", 3)] == "I"
    assert rows[("iva-349-operador-row-nif", 3)] == "12345678901"


def test_committed_modelo_349_construct_includes_invoice_bindings() -> None:
    revision = _modelo_349_revision()
    construct = revision.constructs[0]
    assert set(construct.bindings) == {
        b.id for b in revision.bindings if b.source in {"collectible_invoice", "payable_invoice"}
    }


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

    row_bindings: dict[str, DataBindingDefinition] = {
        b.id: b
        for b in revision.bindings
        if b.source == "collectible_invoice" and b.aggregation is not None and b.aggregation.op == "rows"
    }
    payable_row_bindings: dict[str, DataBindingDefinition] = {
        b.id: b
        for b in revision.bindings
        if b.source == "payable_invoice" and b.aggregation is not None and b.aggregation.op == "rows"
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
    assert set(payable_row_bindings) == {
        f"{binding_id}-adquisicion"
        for binding_id in expected_operador_row_bindings | expected_rectificacion_row_bindings
    }

    for binding_id in expected_operador_row_bindings:
        row_selector = _selector(row_bindings[binding_id])
        assert row_selector["grouping"] == "operator_clave"
        assert row_selector["rectification_scope"] == "exclude_rectifications"
        payable_binding = payable_row_bindings[f"{binding_id}-adquisicion"]
        payable_selector = _selector(payable_binding)
        assert payable_selector["grouping"] == "operator_clave"
        assert payable_selector["rectification_scope"] == "exclude_rectifications"
        assert cast("tuple[str, ...]", payable_selector["claves"]) == ("A", "I", "T")
    for binding_id in expected_rectificacion_row_bindings:
        row_selector = _selector(row_bindings[binding_id])
        assert row_selector["grouping"] == "operator_clave_period"
        assert row_selector["rectification_scope"] == "only_rectifications"
        payable_binding = payable_row_bindings[f"{binding_id}-adquisicion"]
        payable_selector = _selector(payable_binding)
        assert payable_selector["grouping"] == "operator_clave_period"
        assert payable_selector["rectification_scope"] == "only_rectifications"
        assert cast("tuple[str, ...]", payable_selector["claves"]) == ("A", "I", "T")


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

    # Rectification delta must equal the absolute difference between new and previous base.
    assert rect_obs.rectified_base_previous is not None
    expected_rect_delta = abs(rect_obs.base_amount - rect_obs.rectified_base_previous)
    assert casilla_values[_DECL_IMPORTE_RECTIFICACIONES_CASILLA] == expected_rect_delta
