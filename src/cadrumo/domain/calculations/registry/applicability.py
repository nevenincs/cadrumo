"""Registry-grounded modelo-applicability derivation from the taxpayer model.

The overview surfaces (``explain`` / ``calendar`` / ``agenda`` /
``backlog``) used to treat every profile as an *autónomo en estimación
directa*: the :class:`~domain.deadlines.engine.DeadlineEngine` produces an
obligation for every modelo with a registered deadline window, and no
layer asked *which kind of taxpayer this is*. A pure landlord was told
Modelo 130 was overdue.

This module is the derivation layer: each modelo's ``applicable``
verdict is DERIVED from the three-axis
:class:`~domain.deadlines.models.TaxpayerProfile` model (entity type,
IRPF income categories, estimation regime) through a registry-grounded
rule table. The autónomo-by-default assumption is removed.

Four verdicts are possible:

* :attr:`ApplicabilityVerdict.APPLICABLE` — the taxpayer model
  triggers this modelo.
* :attr:`ApplicabilityVerdict.NOT_APPLICABLE` — the taxpayer model
  positively excludes this modelo (a landlord has no Modelo 130;
  an S.L. has no Modelo 100).
* :attr:`ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH` — the
  profile is an *attribution entity* (comunidad de bienes, sociedad
  civil sin objeto mercantil) and the modelo asked about is a cuota
  self-assessment (the IRPF Modelo 100 / 130 or the IS Modelo
  200 / 202). An attribution entity runs no IS and no IRPF cuota of
  its own — the régimen de atribución de rentas (LIRPF Title X
  Section 2) attributes the income to the members, who file the
  substantive tax. The honest answer to "what is my cuota" is
  "none — taxed in the members' returns". This is structurally
  distinct from a plain ``NOT_APPLICABLE``: a salaried-only natural
  person is positively excluded from Modelo 200 because they file a
  *different* cuota (Modelo 100); an attribution entity files *no*
  cuota at all.
* :attr:`ApplicabilityVerdict.INCOMPLETE` — the taxpayer model is
  undeclared (no ``entity_type`` and, for a natural person, no income
  categories), or the entity form is recognised-but-unsupported. The
  engine refuses to guess: it never reports a confident wrong
  obligation, and it never runs an IRPF cuota for a company or an IS
  cuota for an attribution entity.

The entity-type axis selects the *income-tax* route: a legal entity
routes to the IS path (Modelo 200 / 202), a natural person to the IRPF
path (Modelo 100 / 130), and an attribution entity to member
pass-through for cuota self-assessments. IVA and payer-fact modelos are
then decided by their own declared profile facts (IVA regime,
withholding-payer facts, trade thresholds). The engine routing contract
does not treat pass-through income taxation as an exemption from
non-income-tax obligations.

**Canonical applicability authority — modelo level.**
:data:`MODELO_APPLICABILITY_RULES` is the single canonical source for
modelo-level applicability. Any question of the form "does this
taxpayer ever owe this modelo?" is answered here. Code that derives
applicability verdicts MUST read from this table; it MUST NOT
re-implement the logic in another module or maintain a parallel copy
of the rules dict.

**Relation to ``applicability_conditions`` on ``ModeloDeadlineWindow``.**
``ModeloDeadlineWindow`` carries a
``applicability_conditions`` mapping that governs *window-level*
scheduling — which specific deadline window applies for a profile
within the set of applicable windows (e.g. Modelo 202 uses different
modality windows for the April / October / December instalments, and
some windows filter by ``entity_size``). These conditions are
COMPLEMENTARY to the modelo-level rules, not replacements:
``applicability_conditions`` operates after the modelo-level gate
confirms the modelo applies at all; it never overrides the modelo-level
verdict. Adding a condition to a deadline window does not affect the
``ApplicabilityVerdict`` returned by :func:`derive_modelo_applicability`.

Every rule carries ``legal_refs`` — scoped registry citation keys in
the ``law-slug:art-N`` form (e.g. ``ley-35-2006:art-99``) that resolve
against ``src/cadrumo/_data/registry/aeat/legal/*.toml`` — per
``.claude/rules/aeat-calculation-grounding.md``: applicability is
regulatory data and must be registry-grounded, and every typed-ID
reference must point at an existing registry entity. The seed table
below covers the core modelo set an ordinary taxpayer encounters —
the IRPF Renta and pago-fraccionado modelos (100 / 130 / 131), the
corporate IS modelos (200 / 202), the IVA modelos (303 / 390), the
retención modelos and their annual companions (111 / 190, 115 / 180),
the operaciones modelos (349 / 347), and the attribution-entity
informational Modelo 184. Per-entity / per-regime expansion to the
remaining registered modelos is intentionally deferred; a modelo with no
seed rule is reported INCOMPLETE with a rationale that says so.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, NamedTuple, override

from pydantic import BaseModel, Field, StringConstraints

if TYPE_CHECKING:
    from .authority import PinnedAuthorityOperation, ValidatedRegistryAuthority

from ....core.aggregation import ThirdPartyDeclarationRole
from ....core.i18n.render import tr
from ....core.modelo import Modelo
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core.time.clock import today_madrid
from ...contribuyente.entity_type import (
    EntityType,
    entity_type_attribution_entity_token,
    entity_type_natural_person_token,
    entity_type_tokens,
    require_entity_type,
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
    resolve_payer_fact,
)
from .applicability_routes import TaxRoute, tax_route_for_entity_type
from .errors import RegistryFailureClassification, RegistryFailureCondition, RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .ids import LegalRefId, ModeloId
from .irpf_income_categories import (
    irpf_income_category_actividad_economica_token,
    require_irpf_income_category,
)
from .irpf_regimes import irpf_estimation_regime_directa_normal_token, require_irpf_estimation_regime
from .iva_regime_vocabulary import (
    iva_regime_self_assessment_tokens,
    require_iva_regime,
)
from .schema_base import DateAxis
from .schema_revision_members import ApplicabilityExclusionDefinition, ApplicabilityRuleDefinition
from .third_party_declaration_roles import resolve_third_party_declaration_role_catalogue

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
    ATTRIBUTION_PASS_THROUGH = "attribution_pass_through"
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


_NO_LEDGER_PAYER_FACTS: Mapping[str, LedgerPayerFactDerivation] = MappingProxyType[str, LedgerPayerFactDerivation](
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
            return _ExclusionFinding(_incomplete_applicability(modelo, entity_type_declared=True), answered=False)
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
                reason=_registry_applicability_reason("attribution_pass_through.reason"),
                legal_refs=_ATTRIBUTION_PASS_THROUGH_LEGAL_REFS,
            )
        return self._not_applicable()

    def _natural_person_axes_result(self, profile: TaxpayerProfile) -> ModeloApplicability | None:
        if profile.entity_type != entity_type_natural_person_token():
            return None
        if self.required_income_categories:
            if not profile.irpf_income_categories:
                return _incomplete_applicability(
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
            return _incomplete_applicability(self.modelo, entity_type_declared=False)
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
        ledger_payer_facts: Mapping[str, LedgerPayerFactDerivation] = _NO_LEDGER_PAYER_FACTS,
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


def _hydrate_applicability_exclusion(fragment: ApplicabilityExclusionDefinition) -> ModeloApplicabilityExclusion:
    """Hydrate one exclusion, refusing a fact that cannot tell a declared no from an unanswered one."""
    payer_fact = resolve_payer_fact(fragment.payer_fact) if fragment.payer_fact is not None else None
    if payer_fact is not None and not (isinstance(payer_fact, PayerFactProjection) and payer_fact.three_state):
        raise RegistryValidationError(
            f"exclusion {fragment.id!r} reads payer fact {fragment.payer_fact!r}, which cannot tell a declared no "
            "from an unanswered question",
        )
    selection = fragment.declaration_role_selection
    return ModeloApplicabilityExclusion(
        id=fragment.id,
        outcome=ApplicabilityVerdict(fragment.outcome),
        entity_types=frozenset(require_entity_type(value) for value in fragment.entity_types),
        iva_regimes=frozenset(require_iva_regime(value) for value in fragment.iva_regimes),
        lacking_income_categories=frozenset(
            require_irpf_income_category(value) for value in fragment.lacking_income_categories
        ),
        declaration_roles=(
            None if selection is None else resolve_third_party_declaration_role_catalogue().roles_for_clave(selection)
        ),
        payer_fact=payer_fact,
        payer_fact_declared=fragment.payer_fact_declared,
        reason=fragment.reason,
        legal_refs=fragment.legal_refs,
    )


def hydrate_applicability_rule(modelo: Modelo, fragment: ApplicabilityRuleDefinition) -> ModeloApplicabilityRule:
    """Hydrate a registry-authored applicability fragment into the runtime rule.

    The loader boundary for the ``applicability`` schema family: every
    free-form TOML string on ``fragment`` is resolved
    here to its typed registry token (or :class:`PayerFactValue`),
    never left as a raw string for a downstream branch to compare against.
    An unknown token raises :class:`RegistryValidationError` naming the
    offending rule and the underlying enum-coercion error, mirroring the
    coercion-boundary shape :data:`~._schema_base.RevisionReviewStatusField`
    and its siblings already use.

    Args:
        modelo: The modelo the owning revision belongs to; the fragment
            carries no self-referential ``modelo`` field to avoid a value
            that could silently diverge from the revision it is nested in.
        fragment: The validated :class:`ApplicabilityRuleDefinition` to hydrate.

    Returns:
        The equivalent :class:`ModeloApplicabilityRule`.

    Raises:
        RegistryValidationError: A field names a token not declared by the
            selected facts registry.
    """
    try:
        return ModeloApplicabilityRule(
            modelo=modelo.value,
            applicable_entity_types=frozenset(require_entity_type(value) for value in fragment.applicable_entity_types),
            required_income_categories=frozenset(
                require_irpf_income_category(value) for value in fragment.required_income_categories
            ),
            required_estimation_regimes=frozenset(
                require_irpf_estimation_regime(value) for value in fragment.required_estimation_regimes
            ),
            applicable_fiscal_residencies=frozenset(
                FiscalResidency.from_registry(value) for value in fragment.applicable_fiscal_residencies
            ),
            applicable_iva_regimes=frozenset(require_iva_regime(value) for value in fragment.applicable_iva_regimes),
            required_payer_fact=resolve_payer_fact(fragment.required_payer_fact)
            if fragment.required_payer_fact is not None
            else None,
            applicable_reason=fragment.applicable_reason,
            not_applicable_reason=fragment.not_applicable_reason,
            cuota_bearing=fragment.cuota_bearing,
            exclusions=tuple(_hydrate_applicability_exclusion(exclusion) for exclusion in fragment.exclusions),
            legal_refs=fragment.legal_refs,
        )
    except (ValueError, RegistryValidationError) as exc:
        raise RegistryValidationError(
            f"applicability rule {fragment.id!r} for modelo {modelo.value!r} does not hydrate: {exc}",
        ) from exc


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


def _registry_applicability_reason(key: str, *, operation: PinnedAuthorityOperation | None = None) -> str:
    """Resolve an operator-facing verdict reason from the authored catalogue."""
    if operation is None:
        from .authority import bundled_indexed_authority

        with bundled_indexed_authority().operation() as indexed_operation:
            return _registry_applicability_reason(key, operation=indexed_operation)

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

Used when :data:`MODELO_APPLICABILITY_RULES` carries no rule for the
requested modelo. The profile may be fully declared; this verdict is a
statement about the seed coverage, not about the operator. It must never tell a declared operator to declare
their taxpayer type.
"""

_INCOMPLETE_UNDETERMINED_REASON_LOCALE_KEY = "filing.applicability.incomplete_undetermined_fact"
"""``INCOMPLETE`` rationale for a fact only the taxpayer can supply."""

_IMPATRIADO_M720_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "ley-35-2006:art-93",  # LIRPF Art. 93 — régimen especial impatriados.
    "ley-7-2012:da-1",  # Ley 7/2012 DA 1ª — obligación Modelo 720.
    "orden-hap-72-2013:art-1",  # Orden HAP/72/2013 — aprobación Modelo 720.
)
"""Legal refs grounding the IRPF Art. 93 impatriado Modelo 720 exemption.

An impatriado under LIRPF Art. 93 is taxed as a non-resident (IRNR) for
the duration of the special regime. Modelo 720 (bienes en el extranjero)
is an obligation reserved for IRPF residents; it does not extend to
non-residents or to IRPF taxpayers who have opted into the IRNR-rate
regime. The general Art. 93 key resolves in the registry table
``legal/irpf-impatriados.toml``; the two Modelo 720 keys resolve in the
table ``legal/modelo-720.toml``.
"""

_IMPATRIADO_M151_ROUTE_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "ley-35-2006:art-93",  # LIRPF Art. 93 — impatriados opt into IRNR taxation.
    "rd-439-2007:art-115",  # RIRPF Art. 115 — duration of the special regime.
    "rd-439-2007:art-116",  # RIRPF Art. 116 — option exercise / start-date selector.
    # Form orders for the Modelo 151 declaration, both eras. This was a single
    # ref to `orden-eha-2887-2008:modelo-151`, which the registry retired as a
    # stub whose document_id never resolved to real text; it grounded nothing and
    # was absent from the legal catalogue, so this tuple carried a dangling id.
    # The real instruments are bundled: Orden HAP/2783/2015 governs 2015-2022 and
    # Orden HFP/1338/2023 governs ejercicio 2023 onward, per its own Disposicion
    # Final Segunda(a). Both are cited because the route's grounding spans the
    # whole regime rather than one filing year.
    "orden-hap-2783-2015:art-1",
    "orden-hfp-1338-2023:art-1",
)
"""Legal refs grounding the Art. 93 Modelo 151 route and M100 suppression."""

_IMPATRIADO_M100_SUPPRESSED_REASON_LOCALE_KEY = "filing.applicability.impatriado_m100_suppressed"
"""``NOT_APPLICABLE`` rationale for suppressing M100 during Art. 93."""

_IMPATRIADO_M151_APPLICABLE_REASON_LOCALE_KEY = "filing.applicability.impatriado_m151_applicable"
"""``APPLICABLE`` rationale for the active Art. 93 Modelo 151 route."""

_IMPATRIADO_M151_NOT_APPLICABLE_REASON_LOCALE_KEY = "filing.applicability.impatriado_m151_not_applicable"
"""``NOT_APPLICABLE`` rationale for M151 outside the active Art. 93 window."""


def _incomplete_applicability(
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


# ---------------------------------------------------------------------
# Seed rule table — core persona coverage, deliberately narrow
# ---------------------------------------------------------------------
#
# Every rule below is grounded against the registry legal tables for the
# taxpayer-type applicability model. Citation keys are scoped registry
# keys (``law-slug:art-N``) that resolve against
# ``src/cadrumo/_data/registry/aeat/legal/*.toml`` — never URLs, never
# invented slugs. Full per-entity / per-regime coverage of every
# registered modelo is a deferred expansion.


def _iva_seed_applicability_rule(modelo: str) -> ModeloApplicabilityRule:
    """Build an IVA seed rule from the governed facts in the active scope.

    These rules remain Python-authored until their export fragments migrate to
    the registry, but none of their governed vocabulary may be captured at
    module import. Development validation can compile several candidates in
    one process; resolving here makes each lookup observe that candidate's
    fact scope instead of the first candidate that happened to import this
    module.
    """
    if modelo == "390":
        return ModeloApplicabilityRule(
            modelo=modelo,
            applicable_entity_types=frozenset(entity_type_tokens()),
            required_income_categories=frozenset({irpf_income_category_actividad_economica_token()}),
            applicable_iva_regimes=iva_regime_self_assessment_tokens(),
            applicable_reason=(
                "Modelo 390 (resumen anual del IVA): el contribuyente realiza "
                "una actividad económica sujeta al IVA y presenta la "
                "declaración-resumen anual del impuesto."
            ),
            not_applicable_reason=(
                "Modelo 390 no aplica: sin una actividad económica sujeta al "
                "IVA no hay declaración-resumen anual del impuesto."
            ),
            legal_refs=("rd-1624-1992:art-71", "orden-eha-3111-2009:art-1"),
        )
    if modelo == "303":
        return ModeloApplicabilityRule(
            modelo=modelo,
            applicable_entity_types=frozenset(entity_type_tokens()),
            required_income_categories=frozenset({irpf_income_category_actividad_economica_token()}),
            applicable_iva_regimes=iva_regime_self_assessment_tokens(),
            applicable_reason=(
                "Modelo 303 (autoliquidación del IVA): el contribuyente "
                "realiza una actividad económica sujeta al IVA y presenta la "
                "autoliquidación periódica."
            ),
            not_applicable_reason=(
                "Modelo 303 no aplica: sin una actividad económica sujeta al "
                "IVA no hay autoliquidación periódica del impuesto."
            ),
            legal_refs=("ley-37-1992:art-99",),
        )
    raise KeyError(modelo)


class _SeedApplicabilityRules(Mapping[str, ModeloApplicabilityRule]):
    """Read-only seed-rule mapping whose values follow the active fact scope."""

    _MODELOS = ("303", "390")

    @override
    def __getitem__(self, modelo: str) -> ModeloApplicabilityRule:
        if modelo not in self._MODELOS:
            raise KeyError(modelo)
        return _iva_seed_applicability_rule(modelo)

    @override
    def __iter__(self) -> Iterator[str]:
        return iter(self._MODELOS)

    @override
    def __len__(self) -> int:
        return len(self._MODELOS)


MODELO_APPLICABILITY_RULES: Mapping[str, ModeloApplicabilityRule] = _SeedApplicabilityRules()

"""Seed modelo-applicability rules — core persona coverage.

A modelo absent from this table has no derived rule yet: its
applicability is reported :attr:`ApplicabilityVerdict.INCOMPLETE` with
a rationale naming the deferred expansion, never a confident guess.
"""


#: Modelo ids whose applicability rule is authored in the registry rather than
#: declared as a Python literal in :data:`MODELO_APPLICABILITY_RULES` below.
#: 303 and 390 stay literal -- their authoring trees are owned by the
#: export-fragment-generator-authority campaign, not unplaced by omission.
#:
#: Membership is reached two ways, and the difference matters when reading a
#: rule's provenance. Most entries arrived by MIGRATION: every revision of each
#: was hydration-verified equal to the literal it replaces, through the real
#: loader, before it was added here and the literal deleted in the same commit.
#: Modelo 840 arrived by AUTHORING instead -- it never had a literal to be
#: verified against, and its rule is grounded directly on TRLRHL arts. 78, 82
#: and 90 with real-profile verdicts asserted in
#: ``test_modelo_840_applicability``. A migrated entry's guarantee is
#: equivalence; an authored entry's is its citations and its tests, and no
#: count is stated here because a tally of either goes stale on the next entry.
#:
#: This is the single declaration of the mixed-surface state
#: ``MODELO_APPLICABILITY_RULES`` is now in: these modelos resolve from the
#: registry, 303 and 390 still resolve from the literal table. The literal
#: table retires outright once the export-fragment campaign closes those two
#: trees and they are migrated the same way; this module then stops authoring
#: applicability data at all -- it only reads it.
REGISTRY_RESOLVED_APPLICABILITY_MODELOS: frozenset[Modelo] = frozenset(
    {
        Modelo("100"),
        Modelo("111"),
        Modelo("115"),
        Modelo("117"),
        Modelo("123"),
        Modelo("126"),
        Modelo("128"),
        Modelo("130"),
        Modelo("131"),
        Modelo("136"),
        Modelo("151"),
        Modelo("180"),
        Modelo("184"),
        Modelo("187"),
        Modelo("188"),
        Modelo("190"),
        Modelo("193"),
        Modelo("194"),
        Modelo("200"),
        Modelo("202"),
        Modelo("210"),
        Modelo("216"),
        Modelo("232"),
        Modelo("296"),
        Modelo("322"),
        Modelo("347"),
        Modelo("349"),
        Modelo("353"),
        Modelo("360"),
        Modelo("369"),
        Modelo("714"),
        Modelo("720"),
        Modelo("721"),
        Modelo("840"),
    },
)


def resolve_applicability_rule_from_authority(
    authority: ValidatedRegistryAuthority,
    modelo: Modelo,
) -> ModeloApplicabilityRule:
    """Resolve one modelo's applicability rule from an already-loaded authority.

    Reads the UNVALIDATED :class:`~._schema.ModeloDefinition`
    (``authority.modelo(...)``), not ``validate_modelo``/``snapshot``:
    applicability derivation is a pervasive, taxpayer-facing read on every
    profile view, and coupling its availability to full business-rule
    validation or the review-status filing gate would make an unrelated
    validation defect elsewhere in the tree break every taxpayer's
    applicability answer. The fragment was already validated once, when the
    registry authority was built and published.

    This is a deliberate asymmetry with :class:`~._schema.RegistrySnapshot`,
    which carries a same-shaped projection for every OTHER schema family:
    applicability answers "is this modelo due, and to whom" -- the floor rung
    of the authority-grade ladder, scheduling reach, not filing authority.
    ``RegistrySnapshot`` is a filing-context projection one rung up. Resolving
    applicability without filing-grade review is correct per that ladder, not
    a gate dodged; coupling it to snapshot construction would wrongly tie a
    floor-rung fact to filing authority it does not need.

    Applicability content is uniform across a modelo's declared revisions
    today (the migrator authors the identical rule into every one), so any
    revision carrying the family answers the question -- the first one found
    is used.

    Split out from :func:`_resolve_registry_applicability_rule` so the real
    logic takes its authority as a parameter and is testable against a
    scratch :class:`ValidatedRegistryAuthority` without touching the bundled
    tree or monkeypatching anything; the production wrapper leases the indexed
    generation only when a caller has not already supplied an operation.

    Raises:
        RegistryValidationError: No declared revision carries an
            ``applicability`` rule, or the rule fails to hydrate.
    """
    from .queries import RegistryQueryService

    for _modelo_id, revision in RegistryQueryService(authority).iter_modelo_revisions(
        modelo_codes=(modelo.value,),
    ):
        if revision.applicability:
            return hydrate_applicability_rule(modelo, revision.applicability[0])
    raise RegistryValidationError(
        f"modelo {modelo.value!r} is declared in REGISTRY_RESOLVED_APPLICABILITY_MODELOS but no "
        "declared revision carries an applicability rule",
    )


def resolve_applicability_rule_from_operation(
    operation: PinnedAuthorityOperation,
    modelo: Modelo,
) -> ModeloApplicabilityRule:
    """Resolve one modelo's applicability rule from a generation-pinned directory."""
    directory = operation.modelo_directory(modelo.value)
    for metadata in directory.revisions:
        revision = operation.revision(modelo.value, str(metadata.id))
        if revision.applicability:
            return hydrate_applicability_rule(modelo, revision.applicability[0])
    raise RegistryValidationError(
        f"modelo {modelo.value!r} is declared in REGISTRY_RESOLVED_APPLICABILITY_MODELOS but no "
        "declared revision carries an applicability rule",
    )


def _resolve_registry_applicability_rule(
    modelo: Modelo,
    *,
    authority: ValidatedRegistryAuthority | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> ModeloApplicabilityRule:
    """Resolve one modelo's applicability rule from the pinned registry generation.

    The import is function-local by necessity, not preference: ``_authority``
    transitively imports THIS module already, through the build-validation
    dispatch chain (``_authority`` -> ``_snapshot`` -> ``_validate`` ->
    ``_validate_revision_sections`` -> ``validate_applicability_section`` ->
    here), so a module-level authority import would close a real cycle.
    Resolving on first call, long after both
    modules have finished importing, is the same discipline
    used by the shared-catalogue compiler -- module-body evaluation is the
    hazard, first-call resolution is not.

    No local cache sits in front of this call: the indexed operation already
    owns generation pinning and storage validation. Caching here would bypass
    the caller's generation boundary and re-introduce a path-only registry
    cache, exactly the defect that consolidation removed.
    """
    if authority is not None:
        return resolve_applicability_rule_from_authority(authority, modelo)
    if operation is not None:
        return resolve_applicability_rule_from_operation(operation, modelo)

    from .authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as indexed_operation:
        return resolve_applicability_rule_from_operation(indexed_operation, modelo)


def _modelo_applicability_rule(
    modelo: str,
    *,
    authority: ValidatedRegistryAuthority | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> ModeloApplicabilityRule | None:
    """Return ``modelo``'s applicability rule, resolved from the registry or the literal table.

    The single seam every consumer (:func:`derive_modelo_applicability` and
    :func:`iter_modelo_applicability_rules`) reads through, so the mixed-surface split (registry-resolved vs.
    still-literal) is decided in exactly one place. An unrecognised
    ``modelo`` string -- not a member of either surface -- returns ``None``,
    matching the pre-cutover dict-lookup behaviour exactly; it is never an
    error to ask about an unruled modelo.
    """
    if modelo in REGISTRY_RESOLVED_APPLICABILITY_MODELOS:
        return _resolve_registry_applicability_rule(Modelo(modelo), authority=authority, operation=operation)
    return MODELO_APPLICABILITY_RULES.get(modelo)


def iter_modelo_applicability_rules(
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> tuple[ModeloApplicabilityRule, ...]:
    """Return every registry-resolved or seed-literal :class:`ModeloApplicabilityRule`.

    The returned tuple is ordered by modelo id for deterministic audits and
    tests. Callers receive rule objects, not the mutable module-level
    dictionary, so the registry rule table remains read-only from the public
    API.

    Every registry rule is read from one generation: the caller's ``operation``
    when it holds one, otherwise a single lease taken for the whole table. A
    lease per modelo re-verified the published database for each of them and
    could read two modelos from two generations.
    """
    known_modelos = sorted(
        {str(modelo) for modelo in MODELO_APPLICABILITY_RULES} | REGISTRY_RESOLVED_APPLICABILITY_MODELOS,
    )
    if operation is None:
        from .authority import bundled_indexed_authority

        with bundled_indexed_authority().operation() as leased:
            return _applicability_rules(known_modelos, operation=leased)
    return _applicability_rules(known_modelos, operation=operation)


def _applicability_rules(
    modelos: list[str],
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[ModeloApplicabilityRule, ...]:
    return tuple(
        rule for modelo in modelos if (rule := _modelo_applicability_rule(modelo, operation=operation)) is not None
    )


def modelo_requires_iva_regime(modelo: str, *, operation: PinnedAuthorityOperation | None = None) -> bool:
    """Return whether the modelo's applicability rule depends on IVA regime.

    Calendar completeness is a consumer of the same applicability predicate
    that determines whether a taxpayer can have the modelo obligation.  Keep
    that classification here, where registry-resolved and seed rules already
    meet, rather than maintaining a second calendar or core-constants set.
    """
    rule = _modelo_applicability_rule(modelo, operation=operation)
    return rule is not None and bool(rule.applicable_iva_regimes)


def taxpayer_model_is_declared(profile: TaxpayerProfile) -> bool:
    """Return whether the profile carries a usable taxpayer model.

    The taxpayer model is "declared" when the operator has set an
    ``entity_type`` and — for a natural person — at least one IRPF
    income category. Without these, modelo applicability cannot be
    derived: the engine must report ``INCOMPLETE`` rather than assume
    autónomo. A legal / attribution entity needs no income category;
    the ``entity_type`` alone selects its tax.

    Args:
        profile: The :class:`TaxpayerProfile` to inspect.
    """
    if profile.entity_type is None:
        return False
    if profile.entity_type == entity_type_natural_person_token():
        return bool(profile.irpf_income_categories)
    return True


def derive_tax_route(profile: TaxpayerProfile) -> TaxRoute:
    """Return the tax branch ``profile`` routes to.

    The routing contract: the ``entity_type`` axis selects the tax. A
    legal-entity profile routes to the Impuesto sobre Sociedades
    (Modelo 200 / 202); a natural person to the IRPF (Modelo
    100 / 130 / 303); an attribution entity to the member pass-through.
    An undeclared ``entity_type`` yields :attr:`TaxRoute.INCOMPLETE` —
    the engine never runs an IRPF cuota for a company or an IS cuota
    for an attribution entity, and never defaults a tax for a profile
    that declared none.

    Args:
        profile: The :class:`TaxpayerProfile` whose ``entity_type``
            axis selects the tax branch.

    Returns:
        The :class:`TaxRoute` branch the profile's ``entity_type``
        selects, or :attr:`TaxRoute.INCOMPLETE` when ``entity_type``
        is undeclared.
    """
    if profile.entity_type is None:
        return TaxRoute.INCOMPLETE
    return tax_route_for_entity_type(profile.entity_type)


def derive_modelo_applicability(
    profile: TaxpayerProfile,
    modelo: str,
    *,
    today: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
    operation: PinnedAuthorityOperation | None = None,
    ledger_payer_facts: Mapping[str, LedgerPayerFactDerivation] = _NO_LEDGER_PAYER_FACTS,
) -> ModeloApplicability:
    """Derive a modelo's applicability from the taxpayer model.

    The verdict is DERIVED from the three-axis
    :class:`~domain.deadlines.models.TaxpayerProfile` model — never
    assumed. An undeclared taxpayer model yields an explicit
    :attr:`ApplicabilityVerdict.INCOMPLETE` answer; the engine never
    reports a confident wrong obligation.

    A modelo without a seed rule (the seed covers the core persona set
    only) is also reported ``INCOMPLETE`` so the operator is never told
    a confident yes/no the registry rules cannot yet justify; the
    rationale points at the deferred expansion.

    Args:
        profile: The operator's three-axis taxpayer model.
        modelo: The AEAT modelo identifier to decide.
        today: Reference date for the Beckham window check. Defaults to
            the Europe/Madrid civil date (``today_madrid()``) when ``None`` —
            the six-year window is a Spanish-calendar boundary. Pass an explicit
            date in tests so results are deterministic.
        authority: Already-resolved validated authority to reuse. Omitting it
            preserves the standalone fingerprint-bounded bundled-tree lookup.
        operation: Already-pinned indexed operation to reuse for point-loaded
            applicability facts. Omitting it leases the bundled indexed
            generation for this call.
        ledger_payer_facts: The ledger derivations of payer facts for the
            filing year ``profile`` was projected for. A derivation of the
            rule's payer fact is combined with the profile answer as
            :meth:`ModeloApplicabilityRule.evaluate` describes.

    Returns:
        The :class:`ModeloApplicability` for ``modelo`` and ``profile``.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    _today = today if today is not None else today_madrid()
    beckham_window_active = profile.beckham_window_active(_today)

    # The Art. 93 impatriado route is a modelo-level switch while the
    # six-year Beckham window is active: the annual declaration is Modelo
    # 151, and the ordinary Renta self-assessment (Modelo 100) is not the
    # filing route. Once the window expires, both modelos fall back to their
    # ordinary applicability rules: M100 through the seed table below, M151
    # to a positive NOT_APPLICABLE.
    if beckham_window_active and modelo == Modelo("100"):
        return ModeloApplicability(
            modelo=Modelo("100"),
            verdict=ApplicabilityVerdict.NOT_APPLICABLE,
            reason=tr(_IMPATRIADO_M100_SUPPRESSED_REASON_LOCALE_KEY),
            legal_refs=_IMPATRIADO_M151_ROUTE_LEGAL_REFS,
        )
    if modelo == Modelo("151"):
        return ModeloApplicability(
            modelo=Modelo("151"),
            verdict=(ApplicabilityVerdict.APPLICABLE if beckham_window_active else ApplicabilityVerdict.NOT_APPLICABLE),
            reason=(
                tr(
                    _IMPATRIADO_M151_APPLICABLE_REASON_LOCALE_KEY
                    if beckham_window_active
                    else _IMPATRIADO_M151_NOT_APPLICABLE_REASON_LOCALE_KEY,
                )
            ),
            legal_refs=_IMPATRIADO_M151_ROUTE_LEGAL_REFS,
        )

    # An impatriado (LIRPF Art. 93 special regime) is taxed as a non-resident
    # for the duration of the six-year Beckham window (RIRPF Art. 116.1) and
    # is therefore exempt from IRPF-resident obligations. Modelo 720 (bienes
    # en el extranjero) is one of those obligations: it applies to IRPF
    # residents, not to non-resident taxpayers under Art. 93. Enforce the
    # exemption before the rule table so the payer-fact gate is never reached.
    # Year-7+ filers whose window has expired revert to the general IRPF
    # regime and owe M720 again — the window-expiry check is wired here.
    if modelo == Modelo("720") and beckham_window_active:
        return ModeloApplicability(
            modelo=Modelo("720"),
            verdict=ApplicabilityVerdict.NOT_APPLICABLE,
            reason=_registry_applicability_reason("impatriado_m720_exempt.reason", operation=operation),
            legal_refs=_IMPATRIADO_M720_LEGAL_REFS,
        )
    rule = _modelo_applicability_rule(modelo, authority=authority, operation=operation)
    if rule is None:
        return _incomplete_applicability(modelo, unruled=True)
    return rule.evaluate(profile, ledger_payer_facts=ledger_payer_facts)


def derive_taxpayer_files_economic_activity(profile: TaxpayerProfile) -> bool | None:
    """Whether the taxpayer files actividad-económica pagos fraccionados (130/131).

    Reads the :class:`TaxpayerProfile` income-category declarations. ``True``
    when the profile declares actividad-económica income; ``False`` when it
    declares income categories that exclude it (a salaried/rental-only filer
    never files 130/131); ``None`` when income categories are undeclared
    (fail-closed: the 130/131 dependency stays enforced). LIRPF art. 99 /
    RIRPF art. 109.
    """
    if not profile.irpf_income_categories:
        return None
    return irpf_income_category_actividad_economica_token() in profile.irpf_income_categories


__all__ = [
    "MODELO_APPLICABILITY_RULES",
    "ApplicabilityEvidenceDisagreement",
    "ApplicabilityProvenance",
    "ApplicabilityVerdict",
    "LedgerPayerFactDerivation",
    "ModeloApplicability",
    "ModeloApplicabilityExclusion",
    "ModeloApplicabilityRule",
    "derive_modelo_applicability",
    "derive_tax_route",
    "derive_taxpayer_files_economic_activity",
    "iter_modelo_applicability_rules",
    "modelo_requires_iva_regime",
    "resolve_applicability_rule_from_operation",
    "taxpayer_model_is_declared",
]
