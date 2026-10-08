"""Which invoices a Modelo 347 filer under estimación objetiva relates.

RD 1065/2007 art. 32.b relieves "las personas físicas y entidades en
atribución de rentas" of the declaration "por las actividades que tributen en
dicho impuesto por el método de estimación objetiva y, simultáneamente, en el
Impuesto sobre el Valor Añadido por los regímenes especiales simplificado o de
la agricultura, ganadería y pesca o del recargo de equivalencia, salvo por las
operaciones por las que emitan factura", and adds that the filers under the
régimen simplificado also relate "las adquisiciones de bienes y servicios que
realicen que deban ser objeto de anotación en el libro registro de facturas
recibidas". The dated ``m347-estimacion-objetiva-operation-scope`` fact carries
that pairing as data: the IRPF estimation regime it applies to and, per IVA
regime, the invoice directions that stay declared. This module resolves it;
the source resolver applies it at its single exclusion point.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

from ...deadlines.models import IrpfEstimationRegime, IVARegime
from ...iva.classification import InvoiceKind
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import MappingValueWhitespace, StringMappingFact, StringMappingPolicy
from .governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from .irpf_regimes import require_irpf_estimation_regime
from .iva_regime_vocabulary import require_iva_regime
from .schema_base import DateAxis

__all__ = [
    "M347EstimacionObjetivaScope",
    "resolve_m347_estimacion_objetiva_scope",
]

_SUBJECT: Final = "M347 estimacion objetiva operation scope"
_FACT: Final = StringMappingFact(
    fact_id="m347-estimacion-objetiva-operation-scope",
    date_axis=DateAxis.FILING_PERIOD,
    policy=StringMappingPolicy(subject=_SUBJECT, value_whitespace=MappingValueWhitespace.STRIP),
)
_ESTIMATION_KEY: Final = "irpf_estimation_regime"
_ORDER_KEY: Final = "iva_regime.order"
_REGIME_PREFIX: Final = "iva_regime."
_KINDS_FIELD: Final = "declared_invoice_kinds"


@dataclass(frozen=True, slots=True)
class M347EstimacionObjetivaScope:
    """The art. 32.b pairing: one IRPF estimation regime and the IVA regimes it scopes."""

    irpf_estimation_regime: IrpfEstimationRegime
    declared_invoice_kinds: Mapping[IVARegime, frozenset[InvoiceKind]]

    def invoice_kinds_for(
        self,
        *,
        irpf_estimation_regime: IrpfEstimationRegime | None,
        iva_regime: IVARegime,
    ) -> frozenset[InvoiceKind] | None:
        """Return the invoice directions such a filer relates, or ``None`` when art. 32.b does not scope it."""
        if irpf_estimation_regime != self.irpf_estimation_regime:
            return None
        return self.declared_invoice_kinds.get(iva_regime)


def resolve_m347_estimacion_objetiva_scope(
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> M347EstimacionObjetivaScope:
    """Resolve the filing period's art. 32.b operation scope.

    Raises:
        RegistryValidationError: When the fact names an estimation regime, an
            IVA regime or an invoice direction outside its vocabulary, leaves an
            ordered IVA regime without its directions, or declares an entry the
            scope does not define.
    """
    selected = require_governed_fact_authority(authority, subject=_SUBJECT)
    entries = _FACT.resolve_entries(selected, effective_date=effective_date)
    estimation = require_irpf_estimation_regime(
        required_mapping_entry(entries, _ESTIMATION_KEY, subject=_SUBJECT),
        effective_date=effective_date,
        authority=selected,
    )
    regimes = unique_mapping_tokens(entries, _ORDER_KEY, subject=_SUBJECT)
    declared = {_ESTIMATION_KEY, _ORDER_KEY, *(f"{_REGIME_PREFIX}{regime}.{_KINDS_FIELD}" for regime in regimes)}
    undeclared = sorted(set(entries) - declared)
    if undeclared:
        raise RegistryValidationError(f"{_SUBJECT} declares unknown entries {undeclared}")
    kinds: dict[IVARegime, frozenset[InvoiceKind]] = {}
    for raw_regime in regimes:
        regime = require_iva_regime(raw_regime, effective_date=effective_date, authority=selected)
        tokens = unique_mapping_tokens(entries, f"{_REGIME_PREFIX}{raw_regime}.{_KINDS_FIELD}", subject=_SUBJECT)
        try:
            kinds[regime] = frozenset(InvoiceKind(token) for token in tokens)
        except ValueError as exc:
            raise RegistryValidationError(
                f"{_SUBJECT} names an unknown invoice direction for IVA regime {raw_regime!r}: {tokens}",
            ) from exc
    return M347EstimacionObjetivaScope(
        irpf_estimation_regime=estimation,
        declared_invoice_kinds=MappingProxyType(kinds),
    )
