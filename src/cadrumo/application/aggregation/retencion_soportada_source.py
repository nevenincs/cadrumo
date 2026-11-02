"""Source mesh resolver for withholding the taxpayer suffered, per payer and income class.

Three states stay apart, and none of them is invented here:

* **absent** -- the revision declares no member of the family. The resolver
  reads nothing and returns an empty resolution, which differs from reading an
  empty store.
* **missing** -- the family is declared, and a bound class has no payer record
  for the ejercicio. The binding receives no value and is reported unresolved,
  so the casilla blocks instead of reading as zero. Whether a class needs
  records at all, and the operator's attestation that it had no payer, are
  decided before this resolver and are not read here: until they are, every
  bound class without a record stays missing.
* **recorded** -- records exist, and the binding takes the sum of the drawn
  quantity over every payer of its class. A record whose figures are zero is
  present and yields a proven zero.

Every record of the ejercicio is read whenever the family is declared. A record
whose class no binding of the revision consumes is reported unrouted, which
blocks, so no payer's withholding is dropped without a word.

The resolver reads only its own store; no withholding-agent store or source kind
reaches it. Each contributing record is one primary provenance node named by
its keyed ``payer_ref``, never by the payer's tax identifier.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar, Final

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.retencion_soportada import RetencionSoportadaClase
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.retencion_soportada_bindings import (
    retencion_soportada_bindings,
    revision_declares_retencion_soportada,
)
from ...domain.renta.retencion_soportada import RetencionSoportadaOrigen, RetencionSoportadaRecord
from ._modelo_bindings_support import STORAGE_DEGRADATION_ERRORS, empty_source_resolution
from .retencion_soportada_repository import (
    RetencionSoportadaPersistenceError,
    RetencionSoportadaPorts,
    retencion_soportada_record_key,
)
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import storage_degradation_resolution, unresolved_binding_diagnostics

if TYPE_CHECKING:
    from ...core.period import Period
    from ...domain.calculations.registry.ids import BindingId
    from ...domain.calculations.registry.schema import ModeloRevision

__all__ = ["RETENCION_SOPORTADA_SOURCE_REF_PREFIX", "RetencionSoportadaSourceResolver"]

RETENCION_SOPORTADA_SOURCE_REF_PREFIX: Final[str] = "retencion-soportada:"
"""The provenance reference family of one payer record; its subject is the record's keyed object key."""

_SOURCE_KIND: Final = BindingSourceKind.RETENCION_SOPORTADA

_TERMINAL_ORIGIN_BY_RECORD_ORIGIN: Final[dict[RetencionSoportadaOrigen, TerminalOriginClass]] = {
    RetencionSoportadaOrigen.PAYER_CERTIFICATE: TerminalOriginClass.PAYER_CERTIFICATE,
    RetencionSoportadaOrigen.OPERATOR_DECLARATION: TerminalOriginClass.OPERATOR_INPUT,
}


def _source_ref(record: RetencionSoportadaRecord) -> str:
    return f"{RETENCION_SOPORTADA_SOURCE_REF_PREFIX}{retencion_soportada_record_key(record.identity)}"


class RetencionSoportadaSourceResolver:
    """Resolve the family's bindings from the per-payer suffered-withholding records."""

    resolver_id: ClassVar[str] = "retencion_soportada"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.RETENCION_SOPORTADA,)

    def __init__(self, *, ports: RetencionSoportadaPorts) -> None:
        """Use the required suffered-withholding read capability."""
        self._ports = ports

    def load_calculation_records(
        self,
        *,
        period: Period,
        revision: ModeloRevision,
    ) -> tuple[RetencionSoportadaRecord, ...] | None:
        """Return every stored record of the period's ejercicio, or ``None`` when the family is absent.

        ``None`` means the revision declares no member of the family, so the
        calculation reads nothing from this store; an empty tuple means it read
        the store and found no record.
        """
        if not revision_declares_retencion_soportada(revision):
            return None
        return self._ports.repository.load_records(period.filing_year)

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve each family binding to its class total, or leave it unresolved when no record exists."""
        try:
            records = self.load_calculation_records(period=context.period, revision=context.revision)
        except (RetencionSoportadaPersistenceError, *STORAGE_DEGRADATION_ERRORS) as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        if records is None:
            return empty_source_resolution(self.resolver_id, self.owned_sources)
        by_class: defaultdict[RetencionSoportadaClase, list[RetencionSoportadaRecord]] = defaultdict(list)
        for record in records:
            by_class[record.income_class].append(record)
        binding_values: dict[BindingId, Decimal] = {}
        missing: list[BindingId] = []
        consumed: set[RetencionSoportadaClase] = set()
        for binding, provider in retencion_soportada_bindings(context.revision):
            consumed.add(provider.income_class)
            class_records = by_class.get(provider.income_class, [])
            if not class_records:
                missing.append(binding.id)
                continue
            binding_values[binding.id] = sum(
                (record.quantity(provider.quantity) for record in class_records),
                Decimal("0"),
            )
        contributing = tuple(record for record in records if record.income_class in consumed)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            diagnostics=(
                *self._missing_diagnostics(context.revision, tuple(missing)),
                *self._unrouted_diagnostics(context.revision, records, consumed),
            ),
            provenance=tuple(self._provenance(record) for record in contributing),
        )

    def _missing_diagnostics(
        self,
        revision: ModeloRevision,
        missing: tuple[BindingId, ...],
    ) -> tuple[CalculationSourceDiagnostic, ...]:
        if not missing:
            return ()
        return unresolved_binding_diagnostics(
            revision=revision,
            source_kind=_SOURCE_KIND.value,
            binding_ids=missing,
            resolver_id=self.resolver_id,
            message=(
                "no payer record of suffered withholding exists for this binding's income class and ejercicio; "
                "a missing record is never read as zero, so record each payer's certificate before filing"
            ),
        )

    def _unrouted_diagnostics(
        self,
        revision: ModeloRevision,
        records: tuple[RetencionSoportadaRecord, ...],
        consumed: set[RetencionSoportadaClase],
    ) -> tuple[CalculationSourceDiagnostic, ...]:
        return tuple(
            CalculationSourceDiagnostic(
                reason="unrouted_observation",
                source_kind=_SOURCE_KIND.value,
                resolver_id=self.resolver_id,
                source_ref=_source_ref(record),
                message=(
                    f"a suffered-withholding record of income class {record.income_class.value!r} is consumed by "
                    f"no binding on revision {revision.id!r}; its withholding is not credited on this calculation"
                ),
            )
            for record in records
            if record.income_class not in consumed
        )

    def _provenance(self, record: RetencionSoportadaRecord) -> CalculationSourceProvenance:
        return CalculationSourceProvenance(
            resolver_id=self.resolver_id,
            resolved_binding_source=_SOURCE_KIND,
            contributor_source_kind=_SOURCE_KIND.value,
            contributor_binding_source=_SOURCE_KIND,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=_source_ref(record),
            parent_source_ref=None,
            fingerprint=record.evidence_fingerprint,
            terminal_origin=_TERMINAL_ORIGIN_BY_RECORD_ORIGIN[record.origin],
        )
