"""The legal citations an election's limits carry, resolved through the published authority."""

from __future__ import annotations

import pytest

from cadrumo.application.actividad_asset.legal_citations import resolve_legal_citations
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema_references import LegalReference

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LINEAR_MAXIMUM = "renta-actividad-inmovilizado-amortizacion-normal-coeficiente-lineal-maximo"
_LINEAR_PERIOD = "renta-actividad-inmovilizado-amortizacion-normal-periodo-maximo-anos"
_STAMP = "modelo-100:2025:parameter:"
_ART_28 = "Ley 35/2006, art.\u00a028"
_ART_12 = "Ley 27/2014, art.\u00a012"


def test_a_parameter_entry_resolves_to_the_provisions_the_registry_declares_for_it() -> None:
    with bundled_indexed_authority().operation() as operation:
        modelo = operation.revision_for_context("100", filing_year=2025, period="0A")
        resolved = resolve_legal_citations(
            [f"{_STAMP}{_LINEAR_MAXIMUM}:key:mobiliario"],
            modelo=modelo,
            legal_reference=operation.legal_reference,
        )

    assert resolved.complete
    assert [(item.text, item.permalink) for item in resolved.citations] == [
        (_ART_28, "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a28"),
        (_ART_12, "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a12"),
    ]


def test_parameters_sharing_a_provision_cite_it_once_in_first_cited_order() -> None:
    with bundled_indexed_authority().operation() as operation:
        modelo = operation.revision_for_context("100", filing_year=2025, period="0A")
        resolved = resolve_legal_citations(
            [f"{_STAMP}{_LINEAR_PERIOD}:key:mobiliario", f"{_STAMP}{_LINEAR_MAXIMUM}:key:equipo-proceso-informacion"],
            modelo=modelo,
            legal_reference=operation.legal_reference,
        )

    assert resolved.complete
    assert [item.text for item in resolved.citations] == [_ART_28, _ART_12]


def test_operator_evidence_entries_cite_no_provision_and_leave_the_result_complete() -> None:
    with bundled_indexed_authority().operation() as operation:
        modelo = operation.revision_for_context("100", filing_year=2025, period="0A")
        resolved = resolve_legal_citations(
            ["approved-plan:REF-1", "useful-life-evidence:EV-1", ""],
            modelo=modelo,
            legal_reference=operation.legal_reference,
        )

    assert resolved.citations == ()
    assert resolved.complete


def test_an_undeclared_parameter_is_left_out_and_marks_the_result_incomplete_without_failing() -> None:
    with bundled_indexed_authority().operation() as operation:
        modelo = operation.revision_for_context("100", filing_year=2025, period="0A")
        resolved = resolve_legal_citations(
            [f"{_STAMP}no-such-parameter:key:mobiliario", f"{_STAMP}{_LINEAR_MAXIMUM}:key:mobiliario"],
            modelo=modelo,
            legal_reference=operation.legal_reference,
        )

    assert not resolved.complete
    assert [item.text for item in resolved.citations] == [_ART_28, _ART_12]


def test_a_provision_the_authority_cannot_load_is_left_out_and_marks_the_result_incomplete() -> None:
    with bundled_indexed_authority().operation() as operation:
        modelo = operation.revision_for_context("100", filing_year=2025, period="0A")

        def lookup(reference_id: str) -> LegalReference:
            if reference_id == "ley-35-2006:art-28":
                raise LookupError(reference_id)
            return operation.legal_reference(reference_id)

        resolved = resolve_legal_citations(
            [f"{_STAMP}{_LINEAR_MAXIMUM}:key:mobiliario"],
            modelo=modelo,
            legal_reference=lookup,
        )

    assert not resolved.complete
    assert [item.text for item in resolved.citations] == [_ART_12]
