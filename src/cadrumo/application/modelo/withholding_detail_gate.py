"""Filing-grade gate over an annual withholding summary with no per-perceptor detail.

An informative resumen anual of retenciones declares one type-2 record per
perceptor and clave, and its declarante record totals those records. The
obligation to present it is triggered by SATISFYING the declared rentas, exempt
ones included (Orden EHA/3127/2009 art. 2.1 for Modelo 190), not by having
practised a retención: a filer who paid a professional invoice owes the
declaration even when no amount was withheld, and a filer who satisfied none of
those rentas owes no declaration at all. Each type-2 record carries the renta
obtenida -- including the rentas no sometidas a retención por razón de su
cuantía and the exempt ones -- next to the retención practicada (RIRPF art.
108.2.c and 108.2.i), and art. 108.5 obliges the retenedor to complete the
whole determined data set. Either way a declaration carrying zero type-2
records is not a filing: it either omits percepciones that exist, or is not
owed.

The calculate path deliberately materialises that empty store as an explicit
zero percepciones count and a ``withholding_detail_absent`` advisory rather than
refusing, because the bound casilla needs its fact and the pull surface shares
the one resolver. This gate is where that zero stops: it reads the persisted
advisory and refuses the verified-complete transition unless the absence is
PROVEN, which is what closes local filing too (filing requires a granted
verification).

Absence is proven only by the taxpayer's own attestation covering every
quarterly window of the year for the periodic modelo the annual source folds.
That attestation records the RIRPF art. 108.1 no-obligation condition -- no
rentas sometidas a retención were satisfied in the period, so not even a
declaración negativa is due -- which is the same condition that leaves art. 2.1
unsatisfied for the year. It does NOT reach a year in which rentas were
satisfied and no retención was due on them, which art. 2.1 still declares; that
residual is why the proven case stays a visible advisory instead of silence.

Recorded taxpayer evidence OVERRIDES that attestation: two sources disagree, and
the disagreement stays visible rather than letting either side win silently. Two
kinds count. A received invoice declaring a retención the taxpayer owes as
retenedor proves a practised retención nothing declares. An outgoing ledger row
in a withholding IRPF category proves the renta itself was satisfied, which is
what the obligation turns on even where no retención was due.

Scope is the EMPTY detail store, the one absence a zero cannot represent
honestly. A store holding fewer observations than the ledger's evidence is a
reconciliation question this gate does not answer and must not be read as
answering.

See Also:
    :mod:`~cadrumo.application.aggregation.withholding_source`
        The resolver that materialises the zero and raises the advisory.
    :mod:`~cadrumo.application.modelo.m123_count_authority_gate`
        The sibling withholding gate, which refuses a period whose captured
        evidence an unresolved count cannot declare.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from ...core.aggregation import BindingSourceKind
from ...core.modelo import Modelo
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.transactions.enums import TransactionDirection, TransactionLifecycleState
from ...domain.transactions.irpf_categories import has_activity_irpf_category
from ..aggregation.invoice_retencion import invoice_retencion_liability_defects
from ..aggregation.withholding_filing_cadence import QUARTERLY_WITHHOLDING_PERIODS
from ..aggregation.withholding_source import (
    annual_withholding_periodic_source,
    withholding_binding_grounding,
)
from ..calculations.m111_no_retenciones import (
    M111_NO_RETENCIONES_PROFILE_PATH,
    m111_no_retenciones_periods_from_profile_values,
)
from .verification_preconditions import build_verification_precondition_failure

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
    from ...domain.modelos.calculation_revision import CalculationRevision
    from ...domain.modelos.work_unit import WorkUnit
    from ...domain.transactions.models import Transaction
    from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
    from .preconditions import ModeloPreconditionFailure

_WITHHOLDING_SOURCE: Final = BindingSourceKind.WITHHOLDING
_DETAIL_ABSENT_REASON: Final = "withholding_detail_absent"

#: Rendered where a fact has no value to name, so every fact can be supplied on
#: every branch: ``tr()`` leaves an unsupplied placeholder in the rendered string
#: rather than raising, so a conditionally-supplied fact reaches the operator as
#: a literal ``%{source_modelo}``. Spelled as the adjacent verify findings spell
#: it, and it says which case this is — an absent subject reads differently from
#: one whose id is blank.
_ABSENT_FACT: Final[str] = "absent"


@dataclass(frozen=True, slots=True)
class _NoObligationAttestation:
    """One periodic withholding modelo's no-obligation attestation channel.

    ``profile_path`` is the canonical profile fact the operator writes;
    ``read_attested_periods`` is that fact's own parser, so the gate reads the
    attestation exactly as the calculate path does.
    """

    profile_path: str
    read_attested_periods: Callable[[Mapping[str, str] | None], frozenset[tuple[int, str]]]


#: Which periodic withholding modelos an operator can attest a no-obligation
#: period for, by the modelo the annual source folds.
#:
#: A modelo absent here has no channel at all, which is a different answer from
#: an unused channel: the operator cannot prove the absence, so an empty detail
#: store on a summary folding it is never filing grade. Modelo 123 is the live
#: case — its capital allocations carry no attestation — and Modelo 115's
#: attestation is deliberately not listed, because Modelo 180 declares no
#: withholding binding and its empty window is already refused at calculation by
#: the retenciones resolver, so it never reaches this gate.
_NO_OBLIGATION_ATTESTATIONS: Final[Mapping[str, _NoObligationAttestation]] = MappingProxyType(
    {
        Modelo("111").value: _NoObligationAttestation(
            profile_path=M111_NO_RETENCIONES_PROFILE_PATH,
            read_attested_periods=m111_no_retenciones_periods_from_profile_values,
        ),
    },
)

#: The periodic withholding modelo the activity-withholding ledger category feeds.
#:
#: The registry's IRPF ledger taxonomy declares the activity category's purpose
#: as activity-income withholding, which is this modelo's family and its resumen
#: anual's. Named once so the ledger comparison and the taxonomy cannot come to
#: disagree about which summary an activity row is evidence for.
_ACTIVITY_LEDGER_EVIDENCE_SOURCE_MODELO: Final = Modelo("111")


@dataclass(frozen=True, slots=True)
class WithholdingDetailAbsence:
    """Why an annual summary's per-perceptor detail store is empty for one year.

    ``source_modelo`` is the periodic modelo whose windows the annual source
    folds, or ``None`` for a summary reading its own window.
    ``attestation_profile_path`` is ``None`` when the source modelo has no
    attestation channel, so ``unattested_periods`` then lists every quarter.
    ``contradicting_invoice_ids`` are the received invoices dated in the year
    whose retención the taxpayer owes as retenedor and which the store does not
    hold. ``contradicting_ledger_row_ids`` are the year's outgoing ledger rows
    in a withholding IRPF category: evidence the taxpayer SATISFIED a renta the
    summary declares, which is what the obligation turns on even where no
    retención was practised.
    """

    modelo: str
    filing_year: int
    source_modelo: str | None
    attestation_profile_path: str | None
    attested_periods: tuple[str, ...]
    unattested_periods: tuple[str, ...]
    contradicting_invoice_ids: tuple[str, ...]
    contradicting_ledger_row_ids: tuple[str, ...]

    @property
    def absence_is_proven(self) -> bool:
        """Whether the taxpayer proved every periodic window carried no retención."""
        return self.attestation_profile_path is not None and not self.unattested_periods

    @property
    def contradicted_by_ledger(self) -> bool:
        """Whether recorded taxpayer evidence disagrees with the empty detail store."""
        return bool(self.contradicting_invoice_ids or self.contradicting_ledger_row_ids)

    @property
    def is_filing_grade(self) -> bool:
        """Whether the empty detail store may still reach ``verificado completo``."""
        return self.absence_is_proven and not self.contradicted_by_ledger


def _revision_declares_withholding_detail_absence(target: CalculationRevision) -> bool:
    """Whether the calculate path persisted the empty-detail condition on ``target``."""
    return any(
        issue.binding_source is _WITHHOLDING_SOURCE and issue.reason == _DETAIL_ABSENT_REASON
        for issue in target.source_issues
    )


def _contradicting_invoice_ids(
    *,
    filing_year: int,
    invoice_repository: InvoiceCatalogueRepositoryProtocol,
) -> tuple[str, ...]:
    """Return the year's received invoices whose retenedor-liability retención routes.

    Dated by issue date, which is the coordinate the invoice itself carries. It
    is EVIDENCE of practised withholding the store does not hold, not a
    determination of the window that withholding settles in — deriving that
    window is the recognition path's job and is not repeated here.

    The invoice does not fix which periodic modelo the retención belongs to
    either: that follows from the income kind the operator declares when the
    retención is captured. So this answers "a practised retención exists and no
    per-perceptor record declares it", never "these rows are this summary's
    percepciones".
    """
    catalogue = invoice_repository.load()
    return tuple(
        sorted(
            invoice.invoice_id
            for invoice in catalogue.invoices.values()
            if invoice.issued_at.year == filing_year and not invoice_retencion_liability_defects(invoice)
        ),
    )


def _is_retenedor_activity_payment(
    transaction: Transaction,
    *,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Whether one ledger row records a professional-activity renta the taxpayer satisfied.

    The category predicate is the registry-owned one, so the IRPF ledger
    taxonomy decides which tokens count rather than a list restated here. The
    outgoing direction is the retenedor side: the same category incoming is the
    taxpayer's own activity income, which no resumen anual of theirs declares.
    """
    if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        return False
    if transaction.direction is not TransactionDirection.OUTGOING:
        return False
    return has_activity_irpf_category(
        transaction.irpf_category,
        direction=transaction.direction,
        authority=operation,
    )


def _contradicting_ledger_row_ids(
    *,
    work_unit: WorkUnit,
    source_modelo: Modelo | None,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    operation: PinnedAuthorityOperation,
) -> tuple[str, ...]:
    """Return the year's outgoing ledger rows in a withholding IRPF category.

    Evidence that the taxpayer SATISFIED one of the rentas the summary declares,
    which is what triggers the obligation (Orden EHA/3127/2009 art. 2.1) whether
    or not a retención was practised on the payment.

    Scoped to the summary whose periodic source is
    :data:`_ACTIVITY_LEDGER_EVIDENCE_SOURCE_MODELO`, because the registry
    taxonomy gives this category the activity-income withholding purpose and
    that is the family the modelo owns. A summary folding another periodic
    modelo reads a different store, and an activity row says nothing about it.
    """
    if source_modelo != _ACTIVITY_LEDGER_EVIDENCE_SOURCE_MODELO:
        return ()
    catalogue = transaction_repository.load_for_date_range(
        work_unit.period.start_date,
        work_unit.period.end_date,
    )
    return tuple(
        sorted(
            transaction_id
            for transaction_id, transaction in catalogue.transactions.items()
            if _is_retenedor_activity_payment(transaction, operation=operation)
        ),
    )


def resolve_withholding_detail_absence(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    invoice_repository: InvoiceCatalogueRepositoryProtocol,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    profile_path_values: Mapping[str, str] | None,
    operation: PinnedAuthorityOperation,
) -> WithholdingDetailAbsence | None:
    """Classify the empty per-perceptor detail store behind ``target``, or ``None``.

    ``None`` when the calculate path recorded no empty-detail condition, which
    covers every revision whose store held observations and every revision whose
    modelo declares no withholding binding at all. ``target`` is the calculated
    :class:`CalculationRevision`.
    """
    if not _revision_declares_withholding_detail_absence(target):
        return None
    modelo = str(work_unit.modelo)
    filing_year = work_unit.filing_year
    source_modelo = annual_withholding_periodic_source(modelo)
    attestation = _NO_OBLIGATION_ATTESTATIONS.get(source_modelo.value) if source_modelo is not None else None
    attested_keys: frozenset[tuple[int, str]] = (
        attestation.read_attested_periods(profile_path_values)
        if attestation is not None
        else frozenset[tuple[int, str]]()
    )
    attested = tuple(period for period in QUARTERLY_WITHHOLDING_PERIODS if (filing_year, period) in attested_keys)
    return WithholdingDetailAbsence(
        modelo=modelo,
        filing_year=filing_year,
        source_modelo=source_modelo.value if source_modelo is not None else None,
        attestation_profile_path=attestation.profile_path if attestation is not None else None,
        attested_periods=attested,
        unattested_periods=tuple(period for period in QUARTERLY_WITHHOLDING_PERIODS if period not in attested),
        contradicting_invoice_ids=_contradicting_invoice_ids(
            filing_year=filing_year,
            invoice_repository=invoice_repository,
        ),
        contradicting_ledger_row_ids=_contradicting_ledger_row_ids(
            work_unit=work_unit,
            source_modelo=source_modelo,
            transaction_repository=transaction_repository,
            operation=operation,
        ),
    )


def _absence_message_facts(absence: WithholdingDetailAbsence) -> dict[str, str | int | bool]:
    """Project the classified absence into locale-neutral finding facts.

    Every key is populated unconditionally: a fact supplied conditionally renders
    as its own placeholder in front of an operator, and "there is no periodic
    source" has to read differently from a blank one.
    """
    return {
        "modelo": absence.modelo,
        "filing_year": absence.filing_year,
        "source_family": _WITHHOLDING_SOURCE.value,
        "source_modelo": absence.source_modelo or _ABSENT_FACT,
        "attestation_profile_path": absence.attestation_profile_path or _ABSENT_FACT,
        "attested_periods": "|".join(absence.attested_periods) if absence.attested_periods else _ABSENT_FACT,
        "unattested_periods": "|".join(absence.unattested_periods) if absence.unattested_periods else _ABSENT_FACT,
        "contradicting_invoice_count": len(absence.contradicting_invoice_ids),
        "contradicting_ledger_row_count": len(absence.contradicting_ledger_row_ids),
    }


def withholding_detail_absence_finding(
    absence: WithholdingDetailAbsence,
    *,
    snapshot: RegistrySnapshot,
) -> ModeloVerificationFinding:
    """Build the finding for one classified empty detail store.

    BLOCKING unless the absence is proven and nothing in the ledger contradicts
    it; the proven case stays a WARNING so the disclosure survives into the
    report without refusing a declaration the taxpayer attested has nothing to
    declare. Grounding is read off the withholding bindings of the :class:`RegistrySnapshot`'s
    revision.

    The three outcomes are three constructions rather than one call with computed
    arguments. Both the finding kind and the locale key are read statically from
    the construction site -- the kind by the operator-action spine, the key by
    the catalogue coverage scanner -- so a computed value is invisible to each.
    """
    legal_refs, source_refs = withholding_binding_grounding(snapshot.revision)
    facts = _absence_message_facts(absence)
    if absence.contradicted_by_ledger:
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.withholding_detail_absent_against_ledger_evidence",
            message_facts=facts,
            legal_refs=legal_refs,
            source_refs=source_refs,
        )
    if absence.absence_is_proven:
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.ADVISORY,
            severity=ModeloVerificationFindingSeverity.WARNING,
            message_locale_key="application.modelo.findings.withholding_detail_absent_attested",
            message_facts=facts,
            legal_refs=legal_refs,
            source_refs=source_refs,
        )
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.withholding_detail_absent_unproven",
        message_facts=facts,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def append_withholding_detail_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    snapshot: RegistrySnapshot,
    invoice_repository: InvoiceCatalogueRepositoryProtocol,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    profile_path_values: Mapping[str, str] | None,
    operation: PinnedAuthorityOperation,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> None:
    """Append the empty-detail finding and its typed precondition, when one applies.

    ``target`` is the :class:`CalculationRevision` under verification and ``snapshot`` the
    :class:`RegistrySnapshot` it was calculated against.
    """
    absence = resolve_withholding_detail_absence(
        work_unit=work_unit,
        target=target,
        invoice_repository=invoice_repository,
        transaction_repository=transaction_repository,
        profile_path_values=profile_path_values,
        operation=operation,
    )
    if absence is None:
        return
    finding = withholding_detail_absence_finding(absence, snapshot=snapshot)
    findings.append(finding)
    if finding.severity is not ModeloVerificationFindingSeverity.BLOCKING:
        return
    scenario = "contradicted" if absence.contradicted_by_ledger else "unproven"
    failures_by_finding_id[id(finding)] = build_verification_precondition_failure(
        calculation_revision_id=target.calculation_revision_id,
        work_unit_id=target.work_unit_id,
        condition_id="modelo.work.verify.withholding_detail.proven",
        scenario_id=f"modelo.work.verify.withholding_detail.{scenario}",
        evidence_id="modelo.work.verify.withholding_detail",
        evidence_values={
            "modelo": absence.modelo,
            "year": absence.filing_year,
            "period": work_unit.period.registry_token,
            "source_family": _WITHHOLDING_SOURCE.value,
            "source_modelo": absence.source_modelo or _ABSENT_FACT,
            "unattested_period_count": len(absence.unattested_periods),
            "contradicting_invoice_count": len(absence.contradicting_invoice_ids),
            "contradicting_ledger_row_count": len(absence.contradicting_ledger_row_ids),
            "absence_proven": absence.absence_is_proven,
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )


__all__ = [
    "WithholdingDetailAbsence",
    "append_withholding_detail_findings",
    "resolve_withholding_detail_absence",
    "withholding_detail_absence_finding",
]
