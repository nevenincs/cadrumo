"""Authored contract of the Modelo 347 estimación objetiva operation-scope fact.

Resolves the fact straight from the authored registry tree through a candidate
fact authority, so RD 1065/2007 art. 32.b is proven before publication: an
estimación objetiva filer under the recargo de equivalencia or the REAGP
relates only its issued invoices, one under the régimen simplificado also its
received ones, and every other pairing of regimes is left unscoped.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, validating_governed_facts
from cadrumo.domain.calculations.registry.m347_operation_scope import resolve_m347_estimacion_objetiva_scope
from cadrumo.domain.deadlines.models import IrpfEstimationRegime, IVARegime
from cadrumo.domain.iva.classification import InvoiceKind

from ..compiler.fact_loader import load_governed_facts
from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ON_DATE = date(2025, 12, 31)


@pytest.fixture
def authored() -> Iterator[CandidateFactAuthority]:
    facts = load_governed_facts(bundled_path("registry", "aeat", "facts"))
    support = load_shared_catalogues(bundled_path("registry", "aeat")).require_supported_filing_years()
    candidate = CandidateFactAuthority(GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts}), support)
    with validating_governed_facts(candidate):
        yield candidate


@pytest.mark.parametrize(
    ("estimation", "iva_regime", "expected"),
    [
        ("objetiva", "RECARGO_EQUIVALENCIA", frozenset({InvoiceKind.ISSUED})),
        ("objetiva", "REAGP", frozenset({InvoiceKind.ISSUED})),
        ("objetiva", "SIMPLIFICADO", frozenset({InvoiceKind.ISSUED, InvoiceKind.RECEIVED})),
        ("objetiva", "GENERAL", None),
        ("directa_simplificada", "RECARGO_EQUIVALENCIA", None),
        ("directa_normal", "GENERAL", None),
    ],
)
def test_the_authored_scope_keeps_the_directions_art_32_b_relates(
    authored: CandidateFactAuthority,
    estimation: str,
    iva_regime: str,
    expected: frozenset[InvoiceKind] | None,
) -> None:
    scope = resolve_m347_estimacion_objetiva_scope(effective_date=_ON_DATE, authority=authored)

    assert (
        scope.invoice_kinds_for(
            irpf_estimation_regime=IrpfEstimationRegime.from_registry(estimation),
            iva_regime=IVARegime(iva_regime),
        )
        == expected
    )
