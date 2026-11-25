"""Compare each credit casilla of withholding suffered with the sources its revision declares.

A Modelo 100 revision declares, per credit casilla, the one source its value comes
from and the other sources that state the same figure
(:mod:`cadrumo.domain.calculations.registry.credit_reconciliation`). After the
calculation has produced its values, each declared cross-check is read and
compared with the value, or with the named operand of the value's formula:

* equal to the cent: the two sources agree and nothing is said;
* different by any amount: a ``credit_source_disagreement`` issue carries both
  figures as a :class:`~cadrumo.domain.modelos.source_disagreement.SourceDisagreementFact`
  and withholds checking, export and local filing until a recalculation from
  corrected sources clears it;
* the cross-check holds nothing: a ``credit_cross_check_absent`` note says the
  figure is not cross-checked, which is never read as agreement, and withholds
  nothing.

A payer certifies a retención in the year it pays it (DGT V4965-16), while an
accrual taxpayer credits it in the year the income is imputed. When the value
source states its figure by payment year as well, a payer-record cross-check is
compared with that figure: a difference that the receipts' own payment dates
explain is timing, not disagreement, and any remaining difference still blocks.

A filed return is compared in the same way. The year's last pago fraccionado
credits only the retención practised by its window's end, and keeps a rental
activity's, so a filed-observation cross-check is compared with the value
source's figure restated on that basis, row by row.

A credit casilla whose own value is unresolved is not compared: its missing value
is already reported, and no cross-check can stand in for it. No modelo name or
casilla number is read here; everything comes from the revision's declarations;
:class:`RegistrySnapshot`, the pinned registry snapshot.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from ...core.casilla_id import CasillaId
from ...core.hashing import content_hash_hex
from ...core.period import Period
from ...core.retencion_soportada import RetencionSoportadaCantidad, RetencionSoportadaClase
from ...domain.calculations.registry.binding_targets import revision_bindings_by_id
from ...domain.calculations.registry.credit_reconciliation import (
    BorradorCrossCheck,
    CreditCrossCheck,
    CreditCrossCheckKind,
    CreditReconciliationEntry,
    CreditReconciliationOperand,
    FiledObservationCrossCheck,
    LedgerCrossCheck,
    RetencionSoportadaCrossCheck,
)
from ...domain.modelos.calculation_revision_sources import (
    CALCULATION_SOURCE_ISSUE_MESSAGE_LIMIT,
    CalculationNoteFact,
    CalculationNoteSentence,
    CalculationSourceIssue,
)
from ...domain.modelos.source_disagreement import (
    DisagreementDecimalValue,
    SourceDisagreementEntry,
    SourceDisagreementFact,
    SourceDisagreementRole,
)
from ..aggregation.retencion_soportada_repository import RetencionSoportadaPersistenceError
from ..persistence_errors import PersistenceDegradationError
from .borrador_binding import Modelo100BorradorBindingCommand, borrador_cross_check_values

if TYPE_CHECKING:
    from ...core.aggregation import BindingSourceKind
    from ...domain.calculations.registry.ids import BindingId
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from ...domain.modelos.work_unit import WorkUnit
    from ...domain.renta.retencion_soportada import RetencionSoportadaRecord
    from .calculation_action_ports import CalculationActionPorts

__all__ = [
    "CreditCrossCheckSources",
    "credit_reconciliation_issues",
    "load_credit_cross_check_sources",
    "retencion_soportada_class_totals",
]

_VALUE_CHANNEL: Final[str] = "decimal"
_CROSS_CHECK_SOURCE_FAMILIES: Final[Mapping[CreditCrossCheckKind, str]] = MappingProxyType(
    {
        CreditCrossCheckKind.RETENCION_SOPORTADA: "retencion_soportada",
        CreditCrossCheckKind.BORRADOR: "borrador",
        CreditCrossCheckKind.LEDGER: "ledger",
        CreditCrossCheckKind.FILED_OBSERVATION: "filed_observation",
    }
)


@dataclass(frozen=True, slots=True)
class CreditCrossCheckSources:
    """What every cross-check source stated for one calculation.

    ``retencion_soportada_totals`` holds the summed ``pago_a_cuenta`` of each
    income class that has at least one payer record; a class with none is
    absent, never zero. ``borrador_values`` holds what a selected borrador
    snapshot states for its compare-only bindings, and is empty when no
    snapshot was selected. ``borrador_snapshot_id`` locates those values.
    ``payment_year_binding_values`` holds a value-source binding's figure with
    its rows placed on the payer's payment date, stated only for an accrual
    ejercicio. ``filed_observation_values`` holds, per filed-observation
    cross-check, the casilla value its effective observation states and where it
    was read; a return never captured or filed is absent.
    ``instalment_basis_binding_values`` holds a value-source binding's figure
    restated as the year's last pago fraccionado credits it.
    """

    retencion_soportada_totals: Mapping[RetencionSoportadaClase, Decimal]
    borrador_values: Mapping[BindingId, Decimal]
    borrador_snapshot_id: str | None = None
    payment_year_binding_values: Mapping[BindingId, Decimal] = field(default_factory=lambda: MappingProxyType({}))
    filed_observation_values: Mapping[FiledObservationCrossCheck, tuple[Decimal, str]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    instalment_basis_binding_values: Mapping[BindingId, Decimal] = field(default_factory=lambda: MappingProxyType({}))


def retencion_soportada_class_totals(
    records: tuple[RetencionSoportadaRecord, ...] | None,
) -> dict[RetencionSoportadaClase, Decimal]:
    """Sum the credit each payer certificate states, by income class; a class with no record is left out."""
    totals: defaultdict[RetencionSoportadaClase, Decimal] = defaultdict(Decimal)
    for record in records or ():
        totals[record.income_class] += record.quantity(RetencionSoportadaCantidad.PAGO_A_CUENTA)
    return dict(totals)


def _declares_cross_check(snapshot: RegistrySnapshot, kind: CreditCrossCheckKind) -> bool:
    return any(
        cross_check.kind is kind
        for entry in snapshot.revision.credit_reconciliation
        for cross_check in entry.cross_checks
    )


def _payer_record_totals(
    snapshot: RegistrySnapshot, work_unit: WorkUnit, ports: CalculationActionPorts
) -> dict[RetencionSoportadaClase, Decimal]:
    """Read the ejercicio's payer records when a cross-check names them.

    A store that cannot be read leaves every class without a total. The same
    store feeds the suffered-withholding bindings, whose resolver reports the
    unreadable store and withholds filing, so nothing here reads as agreement.
    """
    if not _declares_cross_check(snapshot, CreditCrossCheckKind.RETENCION_SOPORTADA):
        return {}
    try:
        records = ports.retencion_soportada_ports.repository.load_records(work_unit.filing_year)
    except (RetencionSoportadaPersistenceError, PersistenceDegradationError):
        return {}
    return retencion_soportada_class_totals(records)


def _filed_observation_values(
    snapshot: RegistrySnapshot, work_unit: WorkUnit, ports: CalculationActionPorts
) -> dict[FiledObservationCrossCheck, tuple[Decimal, str]]:
    """Read the casilla each filed-observation cross-check names from its effective observation.

    The same ejercicio's return is read: a filed-observation cross-check names a
    modelo and period, never a year. A store that cannot be read, or a return
    never captured or filed, leaves the cross-check without a value, which is
    noted as not cross-checked and never read as agreement.
    """
    values: dict[FiledObservationCrossCheck, tuple[Decimal, str]] = {}
    for entry in snapshot.revision.credit_reconciliation:
        for cross_check in entry.cross_checks:
            if not isinstance(cross_check, FiledObservationCrossCheck) or cross_check in values:
                continue
            try:
                envelope = ports.observation_repository.load_observation(
                    cross_check.modelo, Period.from_year_and_code(work_unit.filing_year, cross_check.period)
                )
            except PersistenceDegradationError:
                continue
            value = None if envelope is None else envelope.observation.casilla_values.get(cross_check.casilla)
            if envelope is not None and value is not None:
                values[cross_check] = (value, f"observation:{envelope.source_kind}:{envelope.captured_at.isoformat()}")
    return values


def load_credit_cross_check_sources(
    snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
    *,
    ports: CalculationActionPorts,
    borrador_snapshot_id: str | None,
    payment_year_binding_values: Mapping[BindingId, Decimal],
    instalment_basis_binding_values: Mapping[BindingId, Decimal],
) -> CreditCrossCheckSources:
    """Read every cross-check source the revision's credit reconciliation names, and nothing else.

    ``snapshot`` is the :class:`RegistrySnapshot`, the pinned registry snapshot.
    """
    borrador_values: dict[BindingId, Decimal] = {}
    if borrador_snapshot_id is not None and _declares_cross_check(snapshot, CreditCrossCheckKind.BORRADOR):
        borrador_values = borrador_cross_check_values(
            Modelo100BorradorBindingCommand(
                bucket_id=work_unit.bucket_id,
                modelo=work_unit.modelo,
                filing_year=work_unit.filing_year,
                period=work_unit.period,
                borrador_snapshot_id=borrador_snapshot_id,
            ),
            registry_snapshot=snapshot,
            snapshot_repository=ports.borrador_snapshot_repository,
            operation=ports.operation,
        )
    return CreditCrossCheckSources(
        retencion_soportada_totals=_payer_record_totals(snapshot, work_unit, ports),
        borrador_values=borrador_values,
        borrador_snapshot_id=borrador_snapshot_id if borrador_values else None,
        payment_year_binding_values=payment_year_binding_values,
        filed_observation_values=_filed_observation_values(snapshot, work_unit, ports),
        instalment_basis_binding_values=instalment_basis_binding_values,
    )


def _compared_value(
    entry: CreditReconciliationEntry,
    operand: CreditReconciliationOperand | None,
    *,
    casilla_values: Mapping[CasillaId, Decimal],
    binding_values: Mapping[BindingId, Decimal],
) -> tuple[Decimal | None, str]:
    """Return the figure a cross-check is compared with, and a reference naming it."""
    if operand is None:
        return casilla_values.get(entry.casilla_id), f"casilla:{entry.casilla_id}"
    if operand.casilla_id is not None:
        return casilla_values.get(operand.casilla_id), f"casilla:{operand.casilla_id}"
    binding_id = operand.binding
    if binding_id is None:
        return None, f"casilla:{entry.casilla_id}"
    return binding_values.get(binding_id), f"binding:{binding_id}"


def _cross_check_value(
    cross_check: CreditCrossCheck,
    *,
    sources: CreditCrossCheckSources,
    binding_values: Mapping[BindingId, Decimal],
) -> tuple[Decimal | None, str, str | None]:
    """Return what one cross-check source states, a reference naming it, and where it was read."""
    if isinstance(cross_check, RetencionSoportadaCrossCheck):
        return (
            sources.retencion_soportada_totals.get(cross_check.income_class),
            f"income_class:{cross_check.income_class.value}",
            None,
        )
    if isinstance(cross_check, BorradorCrossCheck):
        return (
            sources.borrador_values.get(cross_check.binding),
            f"binding:{cross_check.binding}",
            None if sources.borrador_snapshot_id is None else f"borrador:{sources.borrador_snapshot_id}",
        )
    if isinstance(cross_check, FiledObservationCrossCheck):
        stated = sources.filed_observation_values.get(cross_check)
        return (
            None if stated is None else stated[0],
            f"filed:{cross_check.modelo}:{cross_check.period}:{cross_check.casilla}",
            None if stated is None else stated[1],
        )
    ledger: LedgerCrossCheck = cross_check
    return binding_values.get(ledger.binding), f"binding:{ledger.binding}", None


def _comparison_basis(
    entry: CreditReconciliationEntry,
    cross_check: CreditCrossCheck,
    *,
    value: Decimal,
    sources: CreditCrossCheckSources,
) -> Decimal:
    """Return the figure a cross-check is compared with, on the basis its source states the credit.

    A payer record is compared by the payer's payment year and a filed pago
    fraccionado by its own basis, where the value source states that figure;
    every other cross-check is compared with the value itself.
    """
    binding_id = entry.value_source.binding
    if cross_check.operand is not None or binding_id is None:
        return value
    if isinstance(cross_check, RetencionSoportadaCrossCheck):
        return sources.payment_year_binding_values.get(binding_id, value)
    if isinstance(cross_check, FiledObservationCrossCheck):
        return sources.instalment_basis_binding_values.get(binding_id, value)
    return value


def _value_source_family(entry: CreditReconciliationEntry) -> str:
    return "binding" if entry.value_source.binding is not None else "formula"


def _value_source_binding_kind(
    snapshot: RegistrySnapshot, entry: CreditReconciliationEntry
) -> BindingSourceKind | None:
    if entry.value_source.binding is None:
        return None
    binding = revision_bindings_by_id(snapshot.revision).get(entry.value_source.binding)
    return None if binding is None else binding.source


def _fact_box(entry: CreditReconciliationEntry, operand: CreditReconciliationOperand | None) -> CasillaId:
    if operand is not None and operand.casilla_id is not None:
        return operand.casilla_id
    return entry.casilla_id


def _absent_issue(
    snapshot: RegistrySnapshot,
    entry: CreditReconciliationEntry,
    cross_check: CreditCrossCheck,
    cross_check_ref: str,
) -> CalculationSourceIssue:
    kind = cross_check.kind
    return CalculationSourceIssue(
        reason="credit_cross_check_absent",
        binding_source=_value_source_binding_kind(snapshot, entry),
        casilla_id=entry.casilla_id,
        message=(
            f"credit casilla {entry.casilla_id!r}: cross-check {kind.value!r} ({cross_check_ref}) holds nothing "
            "to compare, so the figure is not cross-checked"
        )[:CALCULATION_SOURCE_ISSUE_MESSAGE_LIMIT],
        source_ref=cross_check_ref,
        fact=CalculationNoteFact.of(
            CalculationNoteSentence.CREDIT_CROSS_CHECK_ABSENT,
            box=_fact_box(entry, cross_check.operand),
            cross_check=kind.value,
        ),
    )


def _disagreement_issue(
    snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
    entry: CreditReconciliationEntry,
    cross_check: CreditCrossCheck,
    *,
    value: Decimal,
    value_ref: str,
    compared: Decimal,
    compared_ref: str,
    evidence_ref: str | None,
) -> CalculationSourceIssue:
    kind = cross_check.kind
    fact = SourceDisagreementFact.of(
        modelo=str(snapshot.modelo.id),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        work_unit_id=work_unit.work_unit_id,
        registry_revision_id=str(snapshot.revision.id),
        inputs_digest=content_hash_hex(entry.model_dump(mode="json")),
        key=str(entry.casilla_id),
        value_channel=_VALUE_CHANNEL,
        reached_casillas=(entry.casilla_id,),
        sources=(
            SourceDisagreementEntry(
                role=SourceDisagreementRole.VALUE_SOURCE,
                source_family=_value_source_family(entry),
                source_ref=value_ref,
                value=DisagreementDecimalValue.of(value),
            ),
            SourceDisagreementEntry(
                role=SourceDisagreementRole.CROSS_CHECK,
                source_family=_CROSS_CHECK_SOURCE_FAMILIES[kind],
                source_ref=compared_ref,
                value=DisagreementDecimalValue.of(compared),
                evidence_ref=evidence_ref,
            ),
        ),
        selected_role=SourceDisagreementRole.VALUE_SOURCE,
    )
    return CalculationSourceIssue(
        reason="credit_source_disagreement",
        binding_source=_value_source_binding_kind(snapshot, entry),
        casilla_id=entry.casilla_id,
        message=(
            f"credit casilla {entry.casilla_id!r}: {value_ref} states {value}, cross-check {kind.value!r} "
            f"({compared_ref}) states {compared}"
        )[:CALCULATION_SOURCE_ISSUE_MESSAGE_LIMIT],
        source_ref=compared_ref,
        fact=CalculationNoteFact.of(
            CalculationNoteSentence.CREDIT_SOURCE_DISAGREEMENT,
            box=_fact_box(entry, cross_check.operand),
            amount=value,
            compared_amount=compared,
            cross_check=kind.value,
        ),
        disagreement=fact,
    )


def credit_reconciliation_issues(
    snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
    *,
    casilla_values: Mapping[CasillaId, Decimal],
    binding_values: Mapping[BindingId, Decimal],
    sources: CreditCrossCheckSources,
) -> tuple[CalculationSourceIssue, ...]:
    """Return every disagreement and every absent cross-check the revision's credit reconciliation finds.

    Amounts are compared exactly: a credit is money already rounded to the
    cent, so any difference is a disagreement and none is tolerated.

    ``snapshot`` is the :class:`RegistrySnapshot`, the pinned registry snapshot.
    """
    issues: list[CalculationSourceIssue] = []
    for entry in snapshot.revision.credit_reconciliation:
        for cross_check in entry.cross_checks:
            value, value_ref = _compared_value(
                entry, cross_check.operand, casilla_values=casilla_values, binding_values=binding_values
            )
            if value is None:
                continue
            compared, compared_ref, evidence_ref = _cross_check_value(
                cross_check, sources=sources, binding_values=binding_values
            )
            if compared is None:
                issues.append(_absent_issue(snapshot, entry, cross_check, compared_ref))
            elif compared != _comparison_basis(entry, cross_check, value=value, sources=sources):
                issues.append(
                    _disagreement_issue(
                        snapshot,
                        work_unit,
                        entry,
                        cross_check,
                        value=value,
                        value_ref=value_ref,
                        compared=compared,
                        compared_ref=compared_ref,
                        evidence_ref=evidence_ref,
                    )
                )
    return tuple(issues)
