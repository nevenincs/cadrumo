"""Clean evidence rows for cross-period dependencies the application scopes out.

Each builder returns a dependency row without blockers whose provenance records
why the requirement is not read from a source: the activity had not started, the
Modelo 202 instalment has no art. 40.2 base in the first year, the taxpayer does
not file the source modelo, or the filer attested a zero or no-retenciones
period. :func:`relax_same_year_local_chain` is the one disposition that edits a
row an evaluation already produced.
"""

from __future__ import annotations

from datetime import date
from typing import Final

from ...domain.calculations.registry.applicability_modelo202 import Modelo202Modality
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.form_codes import form_for_role
from .cross_period_models import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyRequirement,
    NoPriorObligationProvenance,
    NoPriorObligationProvenanceKind,
)
from .modelo_202_base_source import modelo_202_instalment_has_no_prior_return


def suppressed_pre_activity_evidence(
    requirement: CrossPeriodDependencyRequirement,
    *,
    activity_start_date: date,
) -> CrossPeriodDependencyEvidence:
    """Build the clean, facet-stamped evidence row for a pre-activity dependency.

    The requirement's period is strictly before the recorded activity-start
    date, so no prior obligation could have legally existed. There is no
    observation to load and nothing to stamp; the
    binding value resolves to a provenance-marked ``Decimal`` zero through the
    existing absent-by-design path, recorded here as an explicit, auditable
    no-prior-obligation outcome with NO blockers (the row is :attr:`clean`).
    """
    return CrossPeriodDependencyEvidence(
        requirement=requirement,
        no_prior_obligation=NoPriorObligationProvenance(
            activity_start_date=activity_start_date,
            provenance_kind=NoPriorObligationProvenanceKind.OPERATOR_DECLARED,
        ),
    )


OFFICIAL_EVIDENCE_DELTA_BLOCKERS: Final = frozenset(
    {
        CrossPeriodCleanStateBlocker.MISSING_AEAT_ACCEPTANCE,
        CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE,
        CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE,
    },
)
"""The blocker set that distinguishes a locally-evidenced chain from an AEAT-evidenced one."""


def relax_same_year_local_chain(
    evidence: CrossPeriodDependencyEvidence,
    *,
    target_filing_year: int,
) -> CrossPeriodDependencyEvidence:
    """Admit a same-year ``app_filing`` chain (only official-evidence-delta blockers) to verify/export with an advisory.

    Cross-year deps, operator_manual sources, value/revision divergence, and missing
    observation/filing keep their blockers (stay blocking); the source stays non-official.
    """
    if evidence.requirement.filing_year != target_filing_year:
        return evidence
    if evidence.observation_source_kind != "app_filing":
        return evidence
    if not evidence.blockers:
        return evidence
    if not set(evidence.blockers) <= OFFICIAL_EVIDENCE_DELTA_BLOCKERS:
        return evidence
    return evidence.model_copy(
        update={"blockers": (), "non_official_local_chain_advisory": True},
    )


def suppressed_modelo_not_applicable_evidence(
    requirement: CrossPeriodDependencyRequirement,
) -> CrossPeriodDependencyEvidence:
    """Clean, advisory-stamped row for a not-applicable dependency (taxpayer suffers, does not file)."""
    return CrossPeriodDependencyEvidence(
        requirement=requirement,
        modelo_not_applicable_advisory=True,
    )


def suppressed_zero_value_previous_filing_evidence(
    requirement: CrossPeriodDependencyRequirement,
) -> CrossPeriodDependencyEvidence:
    """Clean, advisory-stamped row for an explicit zero previous-filing carry."""
    return CrossPeriodDependencyEvidence(
        requirement=requirement,
        zero_value_previous_filing_advisory=True,
    )


def suppressed_m111_no_retenciones_evidence(
    requirement: CrossPeriodDependencyRequirement,
) -> CrossPeriodDependencyEvidence:
    """Clean advisory row for an explicit M111 no-retenciones/no-obligation period."""
    return CrossPeriodDependencyEvidence(
        requirement=requirement,
        m111_no_retenciones_no_obligation_advisory=True,
    )


def suppressed_first_year_fractional_evidence(
    requirement: CrossPeriodDependencyRequirement,
    *,
    activity_start_date: date,
) -> CrossPeriodDependencyEvidence:
    """Build the clean, facet-stamped evidence row for a first-year Modelo 202 modalidad-cuota dependency.

    The taxpayer is a first-year Impuesto sobre Sociedades filer under
    modalidad cuota (LIS art. 40.2), whose
    pago fraccionado is a percentage of the cuota íntegra of the LAST IS return
    whose deadline has elapsed. A first-year IS company has no such prior return,
    so the art. 40.2 modality produces no Modelo 202 obligation. There is no
    observation to load and nothing to stamp; the requirement is scoped out and
    recorded here as an explicit, auditable no-fractional-payment-obligation
    outcome with NO blockers (the row's ``clean`` property is true).

    The provenance kind stays ``OPERATOR_DECLARED`` — the determination rests on the
    operator-declared INCN (driving the derived modality) and the operator-declared
    ``activity_start_date`` (proving the first IS year), neither corroborated against
    an AEAT censo snapshot — so the suppression carries the operator-declared
    advisory, never silently. The ``facet_kind`` records that this is the
    modalidad-cuota first-year facet, distinct from the pre-activity facet.
    """
    return CrossPeriodDependencyEvidence(
        requirement=requirement,
        no_prior_obligation=NoPriorObligationProvenance(
            facet_kind=NoPriorObligationProvenanceKind.NO_FRACTIONAL_PAYMENT_OBLIGATION_FIRST_YEAR,
            activity_start_date=activity_start_date,
            provenance_kind=NoPriorObligationProvenanceKind.OPERATOR_DECLARED,
        ),
    )


def qualifies_for_first_year_fractional_suppression(
    requirement: CrossPeriodDependencyRequirement,
    *,
    modelo_202_modality: Modelo202Modality | None,
    activity_start_date: date | None,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Return whether ``requirement`` is a Modelo 202 instalment with no art. 40.2 base to scope out.

    A requirement qualifies IFF ALL hold (fail-closed — any unmet condition
    keeps the requirement in scope):

    * the cross-period source is the Impuesto sobre Sociedades instalment
      (Modelo 202);
    * the derived Modelo 202 modality is ``ART_40_2_OPTIONAL`` (modalidad cuota,
      INCN ≤ 6.000.000 €) — under ``ART_40_3_MANDATORY`` (base imponible) the pago
      fraccionado IS owed in the first year, and ``INCOMPLETE`` / ``None`` means the
      modality could not be derived, so neither is suppressed;
    * an ``activity_start_date`` is recorded AND every earlier period the
      instalment's art. 40.2 base binding reads, by its declared per-instalment
      offsets, ended before it. That covers every instalment of the first IS
      year and the first instalment of the second, whose window opens before the
      first year's Modelo 200 deadline has passed.
    """
    if requirement.source_modelo != form_for_role("sociedades.instalment"):
        return False
    if modelo_202_modality is not Modelo202Modality.ART_40_2_OPTIONAL:
        return False
    return modelo_202_instalment_has_no_prior_return(
        requirement.period,
        activity_start_date=activity_start_date,
        operation=operation,
    )
