"""Typed applicability rules and their evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, NamedTuple

from pydantic import BaseModel, Field, StringConstraints

if TYPE_CHECKING:
    from .authority import PinnedAuthorityOperation

from ....core.aggregation import ThirdPartyDeclarationRole
from ....core.i18n.render import tr
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core.time.clock import today_madrid
from ...contribuyente.entity_type import (
    EntityType,
    entity_type_attribution_entity_token,
    entity_type_natural_person_token,
)
from ...contribuyente.renta_codes import FiscalResidency
from ...deadlines.models import (
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    TaxpayerProfile,
)
from ._applicability_labels import payer_fact_incomplete_label
from .applicability_payer_facts import (
    PayerFactDeclaration,
    PayerFactProjection,
    PayerFactValue,
    payer_fact_declaration,
)
from .errors import RegistryFailureClassification, RegistryFailureCondition, RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .ids import LegalRefId, ModeloId
from .irpf_regimes import irpf_estimation_regime_directa_normal_token
from .schema_base import DateAxis

type _OperatorReason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ApplicabilityVerdict(StrEnum):
    """Whether a modelo applies to a taxpayer, derived from its model.

    Attributes:
        APPLICABLE: The declared taxpayer model triggers this modelo.
        NOT_APPLICABLE: The declared taxpayer model positively excludes
            this modelo (e.g. a landlord has no Modelo 130 obligation;
            a sociedad limitada files no Modelo 100).
        ATTRIBUTION_PASS_THROUGH: The profile is an attribution entity
            and the modelo is a cuota self-assessment (Modelo
            100 / 130 / 200 / 202). The entity runs no IS and no IRPF
            cuota of its own — the régimen de atribución de rentas
            (LIRPF Title X Section 2) attributes the income to the
            members, who file the substantive tax. The honest answer
            to "what is my cuota" is "none — the income is taxed in
            the members' returns". Distinct from ``NOT_APPLICABLE``,
            which means the taxpayer files a *different* cuota.
        INCOMPLETE: The taxpayer model is not declared in enough detail
            to decide, or the entity form is recognised-but-unsupported.
            The engine refuses to guess — the operator must declare
            their taxpayer type first.
    """

    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    ATTRIBUTION_PASS_THROUGH = "attribution" + "_pass_through"
    INCOMPLETE = "incomplete"


class LedgerPayerFactDerivation(StrEnum):
    """What the taxpayer's own records show about one payer fact for one filing year.

    A local derivation from records Cadrumo holds, never an official AEAT value.

    Attributes:
        DERIVED_YES: The records already establish the fact.
        DERIVED_NO: The records are complete for the year and do not establish
            it. Absence of records is not this state.
        UNKNOWN: The records cannot settle the fact for the year.
    """

    DERIVED_YES = "derived_yes"
    DERIVED_NO = "derived_no"
    UNKNOWN = "unknown"


class ApplicabilityProvenance(StrEnum):
    """Which evidence decided a payer-fact applicability verdict.

    Attributes:
        PROFILE_DECLARED: The operator's profile answer decided it.
        LEDGER_DERIVED: A :class:`LedgerPayerFactDerivation` decided it; the
            verdict is a local derivation, not an operator answer.
    """

    PROFILE_DECLARED = "profile_declared"
    LEDGER_DERIVED = "ledger_derived"


class ApplicabilityEvidenceDisagreement(BaseModel):
    """The profile answer and the ledger derivation of one payer fact contradict each other.

    Neither side wins silently: the verdict carrying this keeps the obligation
    visible, and every surface reports the disagreement until one of the two
    sources is corrected.
    """

    model_config = _STRICT_FROZEN

    payer_fact: Annotated[str, StringConstraints(min_length=1)]
    profile_declaration: PayerFactDeclaration
    ledger_derivation: LedgerPayerFactDerivation


class ModeloApplicability(BaseModel):
    """The derived applicability of one modelo for one taxpayer profile.

    Attributes:
        modelo: The AEAT modelo identifier.
        verdict: The :class:`ApplicabilityVerdict` derived from the
            taxpayer model.
        reason: Operator-facing prose explaining the verdict. An
            ``INCOMPLETE`` verdict carries one of two distinct
            rationales: the "declare your taxpayer type first" guidance
            when the taxpayer model is undeclared, or a "no rule derived
            yet" notice when the modelo has no seed rule (the latter is
            not a statement about the operator's profile).
        legal_refs: Scoped registry citation keys (``law-slug:art-N``)
            grounding the rule, each resolvable against the registry
            ``legal/*.toml`` tables. Always at least one entry —
            applicability is regulatory data and must be grounded
            (``.claude/rules/aeat-calculation-grounding.md``). For an
            ``INCOMPLETE`` verdict the refs ground the *concept* being
            asked about (the LIRPF / LIS taxpayer definitions) so the
            operator still sees a citation.
        provenance: Whether the profile answer or a ledger derivation decided
            the payer-fact axis of the verdict.
        evidence_disagreement: Set when the profile answer and the ledger
            derivation of the rule's payer fact contradict each other.
    """

    model_config = _STRICT_FROZEN

    modelo: ModeloId
    verdict: ApplicabilityVerdict
    reason: _OperatorReason
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    failure: RegistryFailureClassification | None = None
    """Domain facts for a boundary to project when applicability is incomplete."""
    provenance: ApplicabilityProvenance = ApplicabilityProvenance.PROFILE_DECLARED
    evidence_disagreement: ApplicabilityEvidenceDisagreement | None = None

    @property
    def applicable(self) -> bool:
        """Return whether the modelo positively applies.

        Only :attr:`ApplicabilityVerdict.APPLICABLE` is a confident
        yes. ``NOT_APPLICABLE``, ``ATTRIBUTION_PASS_THROUGH`` and
        ``INCOMPLETE`` all yield ``False`` — the operative views must
        not surface an obligation the engine cannot positively justify.
        An attribution entity owes no cuota self-assessment, so a
        pass-through verdict is not an applicable obligation.
        """
        return self.verdict is ApplicabilityVerdict.APPLICABLE


class _ExclusionFinding(NamedTuple):
    """An exclusion that did not fail, and whether every fact it reads was answered."""

    applicability: ModeloApplicability
    answered: bool


class _PayerFactReading(NamedTuple):
    """The rule's payer-fact answer once the profile and the ledger derivation are combined."""

    declaration: PayerFactDeclaration | None
    provenance: ApplicabilityProvenance
    disagreement: ApplicabilityEvidenceDisagreement | None
    ledger_conclusive: bool


NO_LEDGER_PAYER_FACTS: Mapping[str, LedgerPayerFactDerivation] = MappingProxyType[str, LedgerPayerFactDerivation](
    {},
)
_UNANSWERED_PAYER_FACT_DECLARATIONS = frozenset(
    {PayerFactDeclaration.UNDECLARED, PayerFactDeclaration.PERIODS_UNDECLARED},
)


class ModeloApplicabilityExclusion(BaseModel):
    """A registry-grounded exclusion from one modelo-applicability rule.

    A conjunction of typed conditions on the declared profile. Each condition
    either holds, fails, or cannot be read because the profile leaves its fact
    unanswered. One failing condition disarms the exclusion; when none fails,
    an unanswered condition makes it undetermined, and otherwise it holds and
    yields ``outcome`` with its own reason and legal refs.

    Attributes:
        id: The exclusion's registry identifier within its rule.
        outcome: ``NOT_APPLICABLE`` for a legal exclusion, ``INCOMPLETE`` when
            the declared facts cannot settle the obligation on their own.
        entity_types: Holds when the profile's entity type is one of these.
        iva_regimes: Holds when the profile's IVA regime is one of these.
        lacking_income_categories: Holds when the profile declares none of
            these IRPF income categories; an empty category set is unanswered.
        declaration_roles: Holds when the filer declares any of these
            third-party declaration roles; ``None`` reads no role.
        payer_fact: The three-state payer fact the exclusion reads, if any.
        payer_fact_declared: The declared answer ``payer_fact`` must carry.
        reason: Operator-facing prose for the exclusion's verdict.
        legal_refs: Scoped registry citation keys grounding the exclusion.
    """

    model_config = _STRICT_FROZEN

    id: Annotated[str, StringConstraints(min_length=1)]
    outcome: ApplicabilityVerdict
    entity_types: frozenset[EntityType] = frozenset()
    iva_regimes: frozenset[IVARegime] = frozenset()
    lacking_income_categories: frozenset[IrpfIncomeCategory] = frozenset()
    declaration_roles: frozenset[ThirdPartyDeclarationRole] | None = None
    payer_fact: PayerFactValue | None = None
    payer_fact_declared: bool = True
    reason: _OperatorReason
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)

    def _lacks_income_categories(self, profile: TaxpayerProfile) -> bool | None:
        if not self.lacking_income_categories:
            return True
        if not profile.irpf_income_categories:
            return None
        return profile.irpf_income_categories.isdisjoint(self.lacking_income_categories)

    def _payer_fact_holds(self, declaration: PayerFactDeclaration | None) -> bool | None:
        if declaration is None:
            return True
        if declaration is PayerFactDeclaration.DECLARED_YES:
            return self.payer_fact_declared
        if declaration is PayerFactDeclaration.DECLARED_NO:
            return not self.payer_fact_declared
        return None

    def evaluate(self, modelo: ModeloId, profile: TaxpayerProfile) -> _ExclusionFinding | None:
        """Return this exclusion's finding for ``profile``, or ``None`` when a condition fails.

        Parameter types: ``profile`` (:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`).
        """
        lacks_income_categories = self._lacks_income_categories(profile)
        declaration = None if self.payer_fact is None else payer_fact_declaration(profile, self.payer_fact)
        payer_fact_holds = self._payer_fact_holds(declaration)
        conditions = (
            not self.entity_types or profile.entity_type in self.entity_types,
            not self.iva_regimes or profile.iva_regime in self.iva_regimes,
            self.declaration_roles is None or not profile.declaration_roles.isdisjoint(self.declaration_roles),
            lacks_income_categories,
            payer_fact_holds,
        )
        if any(condition is False for condition in conditions):
            return None
        if lacks_income_categories is None:
            return _ExclusionFinding(incomplete_applicability(modelo, entity_type_declared=True), answered=False)
        if payer_fact_holds is None and self.payer_fact is not None:
            undetermined = _undetermined_applicability(
                modelo,
                payer_fact=self.payer_fact,
                legal_refs=self.legal_refs,
                periods_missing=declaration is PayerFactDeclaration.PERIODS_UNDECLARED,
            )
            return _ExclusionFinding(undetermined, answered=False)
        verdict = ModeloApplicability(
            modelo=modelo, verdict=self.outcome, reason=self.reason, legal_refs=self.legal_refs
        )
        return _ExclusionFinding(verdict, answered=True)


class ModeloApplicabilityRule(BaseModel):
    """A single registry-grounded modelo-applicability rule.

    A rule answers, for one modelo, the question "does the declared
    taxpayer model trigger this modelo?". The predicate is expressed as
    closed sets over the three taxpayer axes; evaluation never invents
    legal behaviour beyond what the seed table grounds.

    Attributes:
        modelo: The AEAT modelo identifier the rule decides.
        applicable_entity_types: The :class:`EntityType` values the
            modelo applies to. A taxpayer whose ``entity_type`` is
            outside this set gets :attr:`ApplicabilityVerdict.NOT_APPLICABLE`.
        required_income_categories: For a natural person, the IRPF
            income categories of which *at least one* must be declared
            for the modelo to apply. Empty means the modelo does not
            gate on income category (it applies to every natural person
            whose ``entity_type`` matches). Non-empty means a natural
            person without any of these categories gets
            ``NOT_APPLICABLE`` — this is the gate that excludes Modelo
            130 for a pure landlord.
        required_estimation_regimes: The IRPF estimation regimes the
            modelo applies to. Empty means the modelo does not gate on
            the estimation regime. Non-empty means a natural person
            whose ``irpf_estimation_regime`` is outside the set gets
            ``NOT_APPLICABLE``. An undeclared regime resolves to the
            direct-estimation default: estimación directa is the default
            IRPF method (LIRPF art. 16; RIRPF art. 32 makes módulos
            opt-in), so an actividad-económica autónomo who has not
            explicitly elected módulos owes Modelo 130. This is the axis
            that splits Modelo 130 (estimación directa) from Modelo 131
            (estimación objetiva): the two are mutually exclusive on the
            regime.
        applicable_fiscal_residencies: The fiscal residency categories
            the modelo applies to. Empty means the modelo does not gate
            on fiscal residency. An undeclared residency is kept on the
            resident-IRPF default path described by ``TaxpayerProfile``;
            a declared residency outside this set is a positive
            exclusion.
        applicable_iva_regimes: The IVA regimes that positively keep a
            modelo in scope. Empty means the modelo does not gate on IVA
            regime. Non-empty means a profile outside those regimes gets
            ``NOT_APPLICABLE``. This lets Modelo 303 / 390 be driven by
            the declared IVA obligation instead of borrowing the natural
            person's IRPF income-category axis for legal and attribution
            entities.
        required_payer_fact: The :class:`PayerFactValue` the modelo's
            applicability depends on, or ``None`` when the modelo does
            not gate on a payer fact. When set, a profile that
            positively declares the fact gets ``APPLICABLE``; a profile
            that does not gets ``INCOMPLETE`` — the underlying boolean
            has no tri-state, so the engine cannot positively justify a
            ``NOT_APPLICABLE`` (see :class:`PayerFactValue`).
        applicable_reason: Operator-facing prose for the
            ``APPLICABLE`` verdict.
        not_applicable_reason: Operator-facing prose for the
            ``NOT_APPLICABLE`` verdict.
        cuota_bearing: ``True`` when the modelo is a cuota
            self-assessment (the IRPF Modelo 100 / 130 or the IS Modelo
            200 / 202). A cuota-bearing modelo asked of an *attribution
            entity* yields an :attr:`ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH`
            verdict rather than a plain ``NOT_APPLICABLE``: the entity
            runs no cuota of its own, the income is taxed in the
            members' returns. An
            informational modelo (Modelo 184) is *not* cuota-bearing —
            it stays a plain ``NOT_APPLICABLE`` for the entity types
            its ``applicable_entity_types`` excludes.
        exclusions: The :class:`ModeloApplicabilityExclusion` entries read
            once the positive gates pass. A holding exclusion decides the
            verdict before the payer fact; an undetermined one keeps the
            modelo ``INCOMPLETE`` unless the payer fact already rules it out,
            so an unanswered excluding fact never reads as applicable. An
            exclusion that reads ``required_payer_fact`` itself qualifies how
            far the operator's answer to that fact settles the obligation; it
            is not consulted when a conclusive ledger derivation answers the
            fact directly.
        legal_refs: Scoped registry citation keys (``law-slug:art-N``)
            grounding the rule, each resolvable against the registry
            ``legal/*.toml`` tables.
    """

    model_config = _STRICT_FROZEN

    modelo: ModeloId
    applicable_entity_types: frozenset[EntityType] = Field(min_length=1)
    required_income_categories: frozenset[IrpfIncomeCategory] = frozenset()
    required_estimation_regimes: frozenset[IrpfEstimationRegime] = frozenset()
    applicable_fiscal_residencies: frozenset[FiscalResidency] = frozenset()
    applicable_iva_regimes: frozenset[IVARegime] = frozenset()
    required_payer_fact: PayerFactValue | None = None
    applicable_reason: _OperatorReason
    not_applicable_reason: _OperatorReason
    cuota_bearing: bool = False
    exclusions: tuple[ModeloApplicabilityExclusion, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)

    def _exclusion_finding(
        self,
        profile: TaxpayerProfile,
        *,
        ledger_answers_payer_fact: bool,
    ) -> _ExclusionFinding | None:
        """Return the deciding exclusion.

        A holding legal exclusion wins, then any other holding one, then the
        first undetermined one in authored order. When the ledger answers the
        required payer fact conclusively, exclusions reading that same fact are
        skipped: they qualify the operator's answer, which no longer decides.
        """
        findings = self._evaluated_exclusion_findings(
            profile,
            ledger_answers_payer_fact=ledger_answers_payer_fact,
        )
        return self._preferred_exclusion_finding(findings)

    def _evaluated_exclusion_findings(
        self,
        profile: TaxpayerProfile,
        *,
        ledger_answers_payer_fact: bool,
    ) -> list[_ExclusionFinding]:
        """Evaluate eligible exclusions in their authored order."""
        findings: list[_ExclusionFinding] = []
        for exclusion in self.exclusions:
            if ledger_answers_payer_fact and exclusion.payer_fact == self.required_payer_fact:
                continue
            finding = exclusion.evaluate(self.modelo, profile)
            if finding is not None:
                findings.append(finding)
        return findings

    @staticmethod
    def _preferred_exclusion_finding(findings: list[_ExclusionFinding]) -> _ExclusionFinding | None:
        """Prefer a holding legal exclusion, then the first answered finding."""
        for finding in findings:
            if finding.answered and finding.applicability.verdict is ApplicabilityVerdict.NOT_APPLICABLE:
                return finding
        return next((finding for finding in findings if finding.answered), findings[0] if findings else None)

    def _entity_type_result(self, profile: TaxpayerProfile) -> ModeloApplicability | None:
        if profile.entity_type in self.applicable_entity_types:
            return None
        if self.cuota_bearing and profile.entity_type == entity_type_attribution_entity_token():
            return ModeloApplicability(
                modelo=self.modelo,
                verdict=ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH,
                reason=registry_applicability_reason("attribution_pass_through.reason"),
                legal_refs=_ATTRIBUTION_PASS_THROUGH_LEGAL_REFS,
            )
        return self._not_applicable()

    def _natural_person_axes_result(self, profile: TaxpayerProfile) -> ModeloApplicability | None:
        if profile.entity_type != entity_type_natural_person_token():
            return None
        if self.required_income_categories:
            if not profile.irpf_income_categories:
                return incomplete_applicability(
                    self.modelo,
                    # Reached only once the caller's own `profile.entity_type is
                    # None` guard has already returned, so entity_type is
                    # always declared by this point.
                    entity_type_declared=True,
                )
            if profile.irpf_income_categories.isdisjoint(self.required_income_categories):
                return self._not_applicable()
        if self.required_estimation_regimes:
            regime = profile.irpf_estimation_regime or irpf_estimation_regime_directa_normal_token()
            if regime not in self.required_estimation_regimes:
                return self._not_applicable()
        return None

    def _payer_fact_reading(
        self,
        profile: TaxpayerProfile,
        ledger_payer_facts: Mapping[str, LedgerPayerFactDerivation],
    ) -> _PayerFactReading:
        """Combine the profile answer with the ledger derivation of the required payer fact.

        A derived yes establishes the fact whatever the profile says, because
        the records show operations the answer cannot undo; a contradicting
        profile answer is kept as a disagreement rather than overruled in
        silence. A derived no only corroborates a declared no: records Cadrumo
        does not hold can still establish the fact, so it never replaces an
        unanswered question. A fact with a period companion is read from the
        profile alone, since a derivation states no periods.
        """
        fact = self.required_payer_fact
        if fact is None:
            return _PayerFactReading(None, ApplicabilityProvenance.PROFILE_DECLARED, None, ledger_conclusive=False)
        declared = payer_fact_declaration(profile, fact)
        derivation = self._ledger_payer_fact_derivation(fact, ledger_payer_facts)
        disagreement = self._payer_fact_disagreement(fact, declared, derivation)
        conclusive = derivation in {LedgerPayerFactDerivation.DERIVED_YES, LedgerPayerFactDerivation.DERIVED_NO}
        if derivation is LedgerPayerFactDerivation.DERIVED_YES and declared is not PayerFactDeclaration.DECLARED_YES:
            return _PayerFactReading(
                PayerFactDeclaration.DECLARED_YES,
                ApplicabilityProvenance.LEDGER_DERIVED,
                disagreement,
                ledger_conclusive=True,
            )
        return _PayerFactReading(
            declared, ApplicabilityProvenance.PROFILE_DECLARED, disagreement, ledger_conclusive=conclusive
        )

    @staticmethod
    def _ledger_payer_fact_derivation(
        fact: PayerFactValue,
        ledger_payer_facts: Mapping[str, LedgerPayerFactDerivation],
    ) -> LedgerPayerFactDerivation | None:
        """Read a derivation only for an unperiodized projected payer fact."""
        if not isinstance(fact, PayerFactProjection) or fact.period_companion is not None:
            return None
        return ledger_payer_facts.get(fact.token)

    @staticmethod
    def _payer_fact_disagreement(
        fact: PayerFactValue,
        declared: PayerFactDeclaration,
        derivation: LedgerPayerFactDerivation | None,
    ) -> ApplicabilityEvidenceDisagreement | None:
        """Keep a contradiction visible when the profile and ledger disagree."""
        if not isinstance(fact, PayerFactProjection):
            return None
        if declared is PayerFactDeclaration.DECLARED_YES and derivation is LedgerPayerFactDerivation.DERIVED_NO:
            return ApplicabilityEvidenceDisagreement(
                payer_fact=fact.token,
                profile_declaration=declared,
                ledger_derivation=derivation,
            )
        if declared is PayerFactDeclaration.DECLARED_NO and derivation is LedgerPayerFactDerivation.DERIVED_YES:
            return ApplicabilityEvidenceDisagreement(
                payer_fact=fact.token,
                profile_declaration=declared,
                ledger_derivation=derivation,
            )
        return None

    def _payer_fact_verdict(
        self,
        reading: _PayerFactReading,
        exclusion: _ExclusionFinding | None,
    ) -> ModeloApplicability:
        """Decide the verdict once no exclusion holds outright.

        A declared yes is ``APPLICABLE`` and a declared no ``NOT_APPLICABLE``.
        An unanswered fact -- and every coded or two-state fact whose boolean
        cannot tell "no" from "not asked" -- yields ``INCOMPLETE`` rather than a
        ``NOT_APPLICABLE`` the engine cannot positively justify. An undetermined
        exclusion is held back until here: a payer fact that rules the modelo
        out still wins, and otherwise the modelo stays ``INCOMPLETE`` rather than
        applicable.
        """
        if reading.declaration is PayerFactDeclaration.DECLARED_NO:
            return self._not_applicable()
        if self.required_payer_fact is not None and reading.declaration in _UNANSWERED_PAYER_FACT_DECLARATIONS:
            return _undetermined_applicability(
                self.modelo,
                payer_fact=self.required_payer_fact,
                legal_refs=self.legal_refs,
                periods_missing=reading.declaration is PayerFactDeclaration.PERIODS_UNDECLARED,
            )
        if exclusion is not None:
            return exclusion.applicability
        return ModeloApplicability(
            modelo=self.modelo,
            verdict=ApplicabilityVerdict.APPLICABLE,
            reason=self.applicable_reason,
            legal_refs=self.legal_refs,
        )

    def _with_ledger_evidence(self, verdict: ModeloApplicability, reading: _PayerFactReading) -> ModeloApplicability:
        """Label a ledger-derived verdict and carry a disagreement onto whatever verdict was reached."""
        fact = self.required_payer_fact
        derived = reading.provenance is ApplicabilityProvenance.LEDGER_DERIVED
        if fact is None or (not derived and reading.disagreement is None):
            return verdict
        label = payer_fact_incomplete_label(fact)
        reason = verdict.reason
        if derived and verdict.verdict is ApplicabilityVerdict.APPLICABLE:
            reason = f"{reason} {tr('filing.applicability.ledger_derived_basis', fact=label)}"
        if reading.disagreement is not None:
            reason = f"{reason} {tr('filing.applicability.ledger_profile_disagreement', fact=label)}"
        return verdict.model_copy(
            update={
                "reason": reason,
                "provenance": reading.provenance,
                "evidence_disagreement": reading.disagreement,
            },
        )

    def _positive_rule_gates_result(self, profile: TaxpayerProfile) -> ModeloApplicability | None:
        """Resolve the entity, residency, IVA, and natural-person gates in order."""
        if profile.entity_type is None:
            return incomplete_applicability(self.modelo, entity_type_declared=False)
        if (result := self._entity_type_result(profile)) is not None:
            return result
        if (
            self.applicable_fiscal_residencies
            and profile.fiscal_residency is not None
            and profile.fiscal_residency not in self.applicable_fiscal_residencies
        ):
            return self._not_applicable()
        if self.applicable_iva_regimes and profile.iva_regime not in self.applicable_iva_regimes:
            return self._not_applicable()
        return self._natural_person_axes_result(profile)

    def evaluate(
        self,
        profile: TaxpayerProfile,
        *,
        ledger_payer_facts: Mapping[str, LedgerPayerFactDerivation] = NO_LEDGER_PAYER_FACTS,
    ) -> ModeloApplicability:
        """Derive the :class:`ModeloApplicability` for ``profile``.

        Returns an ``INCOMPLETE`` verdict when the taxpayer model is not
        declared in enough detail to decide; an
        ``ATTRIBUTION_PASS_THROUGH`` verdict when the modelo is a cuota
        self-assessment asked of an attribution entity; otherwise an
        ``APPLICABLE`` / ``NOT_APPLICABLE`` verdict derived from the
        entity-type, income-category, estimation-regime, exclusion and
        payer-fact axes.

        Args:
            profile: The :class:`TaxpayerProfile` to evaluate against this rule.
            ledger_payer_facts: What the taxpayer's own records show about
                payer facts for the filing year being decided, keyed by payer
                fact token. Empty when no derivation is available.
        """
        if (result := self._positive_rule_gates_result(profile)) is not None:
            return result
        # The exclusion axis runs once the positive gates pass. A holding
        # exclusion decides the verdict outright; an undetermined one is held
        # back for the payer-fact axis.
        reading = self._payer_fact_reading(profile, ledger_payer_facts)
        exclusion = self._exclusion_finding(profile, ledger_answers_payer_fact=reading.ledger_conclusive)
        if exclusion is not None and exclusion.answered:
            return exclusion.applicability
        return self._with_ledger_evidence(self._payer_fact_verdict(reading, exclusion), reading)

    def _not_applicable(self) -> ModeloApplicability:
        """Return the ``NOT_APPLICABLE`` applicability for this rule."""
        return ModeloApplicability(
            modelo=self.modelo,
            verdict=ApplicabilityVerdict.NOT_APPLICABLE,
            reason=self.not_applicable_reason,
            legal_refs=self.legal_refs,
        )


# Scoped registry citation keys grounding the "declare your taxpayer
# type first" answer. An undeclared profile cannot be decided, but the
# verdict still carries the LIRPF / LIS articles that frame the question
# the operator must answer. Both keys resolve in the registry legal
# tables (irpf.toml / is.toml).
_INCOMPLETE_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "ley-35-2006:art-99",  # LIRPF art. 99 — IRPF contribuyente / pagos a cuenta.
    "ley-27-2014:art-124",  # LIS art. 124 — obligación de declarar del IS.
)

# Scoped registry citation keys grounding the attribution pass-through
# verdict — the régimen de atribución de rentas. LIRPF art. 86 fixes
# the general régimen (income attributed to socios / herederos /
# comuneros / partícipes); LIRPF art. 87 defines which entities fall
# under it (sociedades civiles sin objeto mercantil, comunidades de
# bienes, herencias yacentes). Both keys resolve in the registry legal
# table ``legal/irpf.toml``.
_ATTRIBUTION_PASS_THROUGH_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "ley-35-2006:art-86",  # LIRPF art. 86 — régimen general de atribución de rentas.
    "ley-35-2006:art-87",  # LIRPF art. 87 — entidades en régimen de atribución.
)

_APPLICABILITY_VERDICT_REASON_FACT_ID = "modelo-applicability-verdict-reason-catalogue"


def registry_applicability_reason(key: str, *, operation: PinnedAuthorityOperation | None = None) -> str:
    """Resolve an operator-facing verdict reason from the authored catalogue."""
    if operation is None:
        from .authority import bundled_indexed_authority

        with bundled_indexed_authority().operation() as indexed_operation:
            return registry_applicability_reason(key, operation=indexed_operation)

    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_APPLICABILITY_VERDICT_REASON_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=today_madrid(),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("modelo applicability reasons must resolve as a mapping fact")
    entries = {str(entry.key): str(entry.value) for entry in resolved.payload.entries}
    try:
        return entries[key]
    except KeyError as exc:
        raise RegistryValidationError(f"modelo applicability reason is missing {key!r}") from exc


_INCOMPLETE_UNDECLARED_REASON_LOCALE_KEY = "filing.applicability.incomplete_undeclared_taxpayer"
"""``INCOMPLETE`` rationale for an *undeclared taxpayer model*.

Used only when the engine cannot decide because the profile itself is
incomplete: no ``entity_type``, or a natural person with no declared
IRPF income category against a category-gated rule. The guidance to
declare the taxpayer type first is correct here.

These rationales reach the operator through ``overview explain``, so they
are catalogue keys rendered in the active output language rather than
authored prose. Registry-authored legal text keeps its authored wording;
this text is the engine's own, and the engine speaks the user's language.
"""

_INCOMPLETE_UNRULED_REASON_LOCALE_KEY = "filing.applicability.incomplete_no_rule"
"""``INCOMPLETE`` rationale for a *modelo with no seed rule*.

Used when no revision declares a rule for the
requested modelo. The profile may be fully declared; this verdict is a
statement about the seed coverage, not about the operator. It must never tell a declared operator to declare
their taxpayer type.
"""

_INCOMPLETE_UNDETERMINED_REASON_LOCALE_KEY = "filing.applicability.incomplete_undetermined_fact"
"""``INCOMPLETE`` rationale for a fact only the taxpayer can supply."""


def incomplete_applicability(
    modelo: str,
    *,
    unruled: bool = False,
    entity_type_declared: bool = False,
) -> ModeloApplicability:
    """Return the explicit ``INCOMPLETE`` applicability for ``modelo``.

    The safe default: the engine never assumes autónomo and never
    reports a confident wrong obligation. The two ``INCOMPLETE`` causes
    are structurally distinct and carry distinct rationale:

    Args:
        modelo: The AEAT modelo identifier the verdict decides.
        unruled: ``True`` when the cause is a *missing seed rule* for the
            modelo — the profile may be fully declared. ``False`` (the
            default) when the cause is an *undeclared taxpayer model*.
        entity_type_declared: Whether the profile supplied its entity-type
            fact.  Retained as a fact for the application boundary; it is not
            a domain recovery instruction.

    Returns:
        A :class:`ModeloApplicability` with ``INCOMPLETE`` verdict and the
        appropriate rationale for the given cause.
    """
    reason = tr(_INCOMPLETE_UNRULED_REASON_LOCALE_KEY if unruled else _INCOMPLETE_UNDECLARED_REASON_LOCALE_KEY)
    return ModeloApplicability(
        modelo=modelo,
        verdict=ApplicabilityVerdict.INCOMPLETE,
        reason=reason,
        legal_refs=_INCOMPLETE_LEGAL_REFS,
        failure=(
            None
            if unruled
            else RegistryFailureClassification(
                condition=RegistryFailureCondition.TAXPAYER_MODEL_DECLARED,
                facts={
                    "modelo": modelo,
                    "taxpayer_model_declared": False,
                    "entity_type_declared": entity_type_declared,
                },
            )
        ),
    )


def _undetermined_applicability(
    modelo: str,
    *,
    payer_fact: PayerFactValue,
    legal_refs: tuple[LegalRefId, ...],
    periods_missing: bool = False,
) -> ModeloApplicability:
    """Return the ``INCOMPLETE`` applicability for a fact only the taxpayer can supply.

    Used when a modelo gates on a :class:`PayerFactValue` (Modelo
    111 / 115 / 349 / 347 / 720 / 721) and the profile does not positively declare
    the fact. The taxpayer model itself may be fully declared — the
    entity type and regime are known — but the payer fact is unanswered
    (or answered yes without the periods it needs), so the engine refuses
    to guess a verdict it cannot positively justify. The rationale is distinct from the
    *undeclared taxpayer model* one: it never tells a declared operator
    to declare their taxpayer type.

    Args:
        modelo: The AEAT modelo identifier the verdict decides.
        payer_fact: The specific profile fact required to positively
            establish applicability.
        legal_refs: The concrete rule legal refs that ground the
            payer-fact requirement, pending the taxpayer's own answer.
        periods_missing: Whether the fact was answered yes without the
            period set its declaration requires.

    Returns:
        A :class:`ModeloApplicability` with ``INCOMPLETE`` verdict and the
        undetermined-payer-fact rationale.
    """
    required = tr(
        "filing.applicability.incomplete_undetermined_fact_required",
        fact=payer_fact_incomplete_label(payer_fact),
    )
    reason = f"{tr(_INCOMPLETE_UNDETERMINED_REASON_LOCALE_KEY)} {required}"
    if periods_missing and isinstance(payer_fact, PayerFactProjection) and payer_fact.period_companion is not None:
        periods = tr(
            "filing.applicability.incomplete_undetermined_periods_missing",
            periods=payer_fact.period_companion.label,
        )
        reason = f"{reason} {periods}"
    return ModeloApplicability(
        modelo=modelo,
        verdict=ApplicabilityVerdict.INCOMPLETE,
        reason=reason,
        legal_refs=legal_refs,
    )
