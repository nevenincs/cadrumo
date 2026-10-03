"""Modelo 347 operation scope for estimación objetiva filers, RD 1065/2007 art. 32.b.

A filer in estimación objetiva and, simultaneously, in the IVA régimen
simplificado, the REAGP or the recargo de equivalencia relates only the
invoices it issues, except that under the simplificado it also relates the
received invoices of its libro registro. The dated
``m347-estimacion-objetiva-operation-scope`` fact carries that pairing; these
tests read it through the published authority, and feed malformed mappings
through a fact source that answers only that one query itself.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

import pytest

from ....deadlines.models import IrpfEstimationRegime, IVARegime
from ....iva.classification import InvoiceKind
from ..authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..errors import RegistryValidationError
from ..facts.payloads import MappingFactEntry, MappingFactPayload
from ..facts.resolution import GovernedFactQuery, MappingFactQuery, ResolvedGovernedFact, ResolvedMappingFact
from ..m347_operation_scope import M347EstimacionObjetivaScope, resolve_m347_estimacion_objetiva_scope
from ..schema import SupportedFilingYearsCatalogue
from ..schema_base import DateAxis

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ON_DATE = date(2025, 12, 31)
_SCOPE_FACT_ID = "m347-estimacion-objetiva-operation-scope"


def _objetiva() -> IrpfEstimationRegime:
    return IrpfEstimationRegime.from_registry("objetiva")


@pytest.fixture(autouse=True)
def _generation_pinned_authority() -> Iterator[None]:
    """Run every test inside one generation-pinned authority operation."""
    with bundled_indexed_authority().operation():
        yield


@pytest.mark.parametrize(
    ("iva_regime", "expected"),
    [
        pytest.param("RECARGO_EQUIVALENCIA", frozenset({InvoiceKind.ISSUED}), id="recargo"),
        pytest.param("REAGP", frozenset({InvoiceKind.ISSUED}), id="reagp"),
        pytest.param("SIMPLIFICADO", frozenset({InvoiceKind.ISSUED, InvoiceKind.RECEIVED}), id="simplificado"),
        pytest.param("GENERAL", None, id="general-is-not-scoped"),
    ],
)
def test_estimacion_objetiva_filers_relate_the_directions_art_32_b_keeps(
    iva_regime: str,
    expected: frozenset[InvoiceKind] | None,
) -> None:
    scope = resolve_m347_estimacion_objetiva_scope(effective_date=_ON_DATE)

    assert scope.invoice_kinds_for(irpf_estimation_regime=_objetiva(), iva_regime=IVARegime(iva_regime)) == expected


@pytest.mark.parametrize("estimation", ["directa_normal", "directa_simplificada", None])
def test_a_filer_outside_estimacion_objetiva_is_never_scoped(estimation: str | None) -> None:
    scope = resolve_m347_estimacion_objetiva_scope(effective_date=_ON_DATE)
    regime = None if estimation is None else IrpfEstimationRegime.from_registry(estimation)

    assert scope.invoice_kinds_for(irpf_estimation_regime=regime, iva_regime=IVARegime("RECARGO_EQUIVALENCIA")) is None


@dataclass(frozen=True, slots=True)
class _ScopeMappingSource:
    """Answer the scope query with ``entries``; delegate everything else to the published operation."""

    base: PinnedAuthorityOperation
    entries: tuple[tuple[str, str], ...]

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        if query.fact_id != _SCOPE_FACT_ID:
            return self.base.resolve_governed_fact(query)
        context = self.base.resolve_governed_fact(
            MappingFactQuery(
                fact_id="m347-clave-threshold-buckets",
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=query.effective_date,
            ),
        )
        assert isinstance(context, ResolvedMappingFact)
        return context.model_copy(
            update={
                "fact_id": _SCOPE_FACT_ID,
                "payload": MappingFactPayload(
                    entries=tuple(MappingFactEntry(key=key, value=value) for key, value in self.entries),
                ),
            },
        )

    def supported_filing_years(self) -> SupportedFilingYearsCatalogue:
        return self.base.supported_filing_years()


_WELL_FORMED: tuple[tuple[str, str], ...] = (
    ("irpf_estimation_regime", "objetiva"),
    ("iva_regime.order", "SIMPLIFICADO,RECARGO_EQUIVALENCIA"),
    ("iva_regime.SIMPLIFICADO.declared_invoice_kinds", "issued,received"),
    ("iva_regime.RECARGO_EQUIVALENCIA.declared_invoice_kinds", "issued"),
)


def _resolve_with(entries: tuple[tuple[str, str], ...]) -> M347EstimacionObjetivaScope:
    with bundled_indexed_authority().operation() as operation:
        return resolve_m347_estimacion_objetiva_scope(
            effective_date=_ON_DATE,
            authority=_ScopeMappingSource(base=operation, entries=entries),
        )


def _replace(key: str, value: str | None) -> tuple[tuple[str, str], ...]:
    kept = tuple(entry for entry in _WELL_FORMED if entry[0] != key)
    return kept if value is None else (*kept, (key, value))


def test_the_override_source_resolves_a_well_formed_mapping() -> None:
    """The refusals below are meaningful only because this same source accepts a valid mapping."""
    scope = _resolve_with(_WELL_FORMED)

    assert scope.invoice_kinds_for(
        irpf_estimation_regime=_objetiva(), iva_regime=IVARegime("RECARGO_EQUIVALENCIA")
    ) == frozenset({InvoiceKind.ISSUED})
    assert scope.invoice_kinds_for(irpf_estimation_regime=_objetiva(), iva_regime=IVARegime("REAGP")) is None


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        pytest.param(_replace("irpf_estimation_regime", "modulos"), "not declared", id="unknown-estimation-regime"),
        pytest.param(
            (
                *_replace("iva_regime.order", "SIMPLIFICADO,RECARGO_EQUIVALENCIA,ESPECIAL"),
                ("iva_regime.ESPECIAL.declared_invoice_kinds", "issued"),
            ),
            "ESPECIAL",
            id="unknown-iva-regime",
        ),
        pytest.param(
            _replace("iva_regime.RECARGO_EQUIVALENCIA.declared_invoice_kinds", "issued,sent"),
            "unknown invoice direction",
            id="unknown-direction",
        ),
        pytest.param(
            _replace("iva_regime.RECARGO_EQUIVALENCIA.declared_invoice_kinds", None),
            "is missing",
            id="ordered-regime-without-directions",
        ),
        pytest.param(
            (*_WELL_FORMED, ("iva_regime.REAGP.declared_invoice_kinds", "issued")),
            "unknown entries",
            id="unordered-regime",
        ),
    ],
)
def test_a_malformed_scope_mapping_is_refused(entries: tuple[tuple[str, str], ...], message: str) -> None:
    with pytest.raises(RegistryValidationError, match=message):
        _resolve_with(entries)
