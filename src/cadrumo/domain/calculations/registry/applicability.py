"""Registry-grounded modelo-applicability derivation from the taxpayer model.

The overview surfaces (``explain`` / ``calendar`` / ``agenda`` /
``backlog``) used to treat every profile as an *autónomo en estimación
directa*: the :class:`~domain.deadlines.DeadlineEngine` produces an
obligation for every modelo with a registered deadline window, and no
layer asked *which kind of taxpayer this is*. A pure landlord was told
Modelo 130 was overdue.

This module is the derivation layer: each modelo's ``applicable``
verdict is DERIVED from the three-axis
:class:`~domain.deadlines.TaxpayerProfile` model (entity type,
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
:data:`_MODELO_APPLICABILITY_RULES` is the single canonical source for
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
remaining registered modelos is intentionally deferred, marked at
:data:`_SEED_COVERAGE_NOTICE`.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, Field, StringConstraints

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority

from ....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core import Modelo
from ....core.time import today_madrid
from ...deadlines import (
    EntityType,
    FiscalResidency,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    TaxpayerProfile,
)
from ._applicability_labels import PAYER_FACT_INCOMPLETE_LABELS as _PAYER_FACT_INCOMPLETE_LABELS
from .applicability_payer_facts import PayerFact, payer_fact_holds
from .applicability_routes import TAX_ROUTE_FOR_ENTITY_TYPE as _TAX_ROUTE_FOR_ENTITY_TYPE
from .applicability_routes import TaxRoute
from .errors import RegistryFailureClassification, RegistryFailureCondition, RegistryValidationError
from .ids import LegalRefId, ModeloId
from .schema import ApplicabilityRuleDefinition

type _OperatorReason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

_SEED_COVERAGE_NOTICE = (
    "Seed coverage only — the modelos in this table are the core "
    "natural-person and corporate-entity set. Full per-entity / "
    "per-regime applicability for every registered modelo is a "
    "deferred expansion."
)
"""Explicit marker that the seed rule table is intentionally narrow.

A modelo absent from :data:`_MODELO_APPLICABILITY_RULES` is reported
with :attr:`ApplicabilityVerdict.INCOMPLETE` and a rationale pointing
at the deferred expansion — never a confident guess.
"""


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
    """

    model_config = _STRICT_FROZEN

    modelo: ModeloId
    verdict: ApplicabilityVerdict
    reason: _OperatorReason
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    failure: RegistryFailureClassification | None = None
    """Domain facts for a boundary to project when applicability is incomplete."""

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
        required_payer_fact: The :class:`PayerFact` the modelo's
            applicability depends on, or ``None`` when the modelo does
            not gate on a payer fact. When set, a profile that
            positively declares the fact gets ``APPLICABLE``; a profile
            that does not gets ``INCOMPLETE`` — the underlying boolean
            has no tri-state, so the engine cannot positively justify a
            ``NOT_APPLICABLE`` (see :class:`PayerFact`).
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
    required_payer_fact: PayerFact | None = None
    applicable_reason: _OperatorReason
    not_applicable_reason: _OperatorReason
    cuota_bearing: bool = False
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)

    def _entity_type_result(self, profile: TaxpayerProfile) -> ModeloApplicability | None:
        if profile.entity_type in self.applicable_entity_types:
            return None
        if self.cuota_bearing and profile.entity_type is EntityType.ATTRIBUTION_ENTITY:
            return ModeloApplicability(
                modelo=self.modelo,
                verdict=ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH,
                reason=_ATTRIBUTION_PASS_THROUGH_REASON,
                legal_refs=_ATTRIBUTION_PASS_THROUGH_LEGAL_REFS,
            )
        return self._not_applicable()

    def _natural_person_axes_result(self, profile: TaxpayerProfile) -> ModeloApplicability | None:
        if profile.entity_type is not EntityType.NATURAL_PERSON:
            return None
        if self.required_income_categories:
            if not profile.irpf_income_categories:
                return _incomplete_applicability(
                    self.modelo,
                    entity_type_declared=profile.entity_type is not None,
                )
            if profile.irpf_income_categories.isdisjoint(self.required_income_categories):
                return self._not_applicable()
        if self.required_estimation_regimes:
            regime = profile.irpf_estimation_regime or IrpfEstimationRegime.DIRECTA_NORMAL
            if regime not in self.required_estimation_regimes:
                return self._not_applicable()
        return None

    def _payer_fact_result(self, profile: TaxpayerProfile) -> ModeloApplicability | None:
        if self.required_payer_fact is None or payer_fact_holds(profile, self.required_payer_fact):
            return None
        return _undetermined_applicability(
            self.modelo,
            payer_fact=self.required_payer_fact,
            legal_refs=self.legal_refs,
        )

    def evaluate(self, profile: TaxpayerProfile) -> ModeloApplicability:
        """Derive the :class:`ModeloApplicability` for ``profile``.

        Returns an ``INCOMPLETE`` verdict when the taxpayer model is not
        declared in enough detail to decide; an
        ``ATTRIBUTION_PASS_THROUGH`` verdict when the modelo is a cuota
        self-assessment asked of an attribution entity; otherwise an
        ``APPLICABLE`` / ``NOT_APPLICABLE`` verdict derived from the
        entity-type, income-category, estimation-regime, and
        payer-fact axes.

        Args:
            profile: The :class:`TaxpayerProfile` to evaluate against this rule.
        """
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
        # The income-category and estimation-regime axes are
        # natural-person facts: a legal entity carries neither (income
        # categories and the IRPF estimation regime only describe a
        # persona física). A legal or attribution entity that matched
        # the entity-type and IVA-regime gates of a modelo applicable to
        # it (e.g. Modelo 303 / 390) is not re-gated on those axes.
        if (result := self._natural_person_axes_result(profile)) is not None:
            return result
        # The payer-fact axis (Modelo 111 / 115 / 349 / 347) can only be
        # asserted in the positive direction — the underlying boolean has
        # no tri-state, so an absent fact yields INCOMPLETE rather than a
        # NOT_APPLICABLE the engine cannot positively justify.
        if (result := self._payer_fact_result(profile)) is not None:
            return result
        return ModeloApplicability(
            modelo=self.modelo,
            verdict=ApplicabilityVerdict.APPLICABLE,
            reason=self.applicable_reason,
            legal_refs=self.legal_refs,
        )

    def _not_applicable(self) -> ModeloApplicability:
        """Return the ``NOT_APPLICABLE`` applicability for this rule."""
        return ModeloApplicability(
            modelo=self.modelo,
            verdict=ApplicabilityVerdict.NOT_APPLICABLE,
            reason=self.not_applicable_reason,
            legal_refs=self.legal_refs,
        )


def hydrate_applicability_rule(modelo: Modelo, fragment: ApplicabilityRuleDefinition) -> ModeloApplicabilityRule:
    """Hydrate a registry-authored applicability fragment into the runtime rule.

    The loader boundary for the ``applicability`` schema family
    (W01.P03.S08): every free-form TOML string on ``fragment`` is resolved
    here to its ``domain.deadlines`` enum member (or :class:`PayerFact`),
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
        RegistryValidationError: A field names a token with no matching enum
            member.
    """
    try:
        return ModeloApplicabilityRule(
            modelo=modelo.value,
            applicable_entity_types=frozenset(EntityType(value) for value in fragment.applicable_entity_types),
            required_income_categories=frozenset(
                IrpfIncomeCategory(value) for value in fragment.required_income_categories
            ),
            required_estimation_regimes=frozenset(
                IrpfEstimationRegime(value) for value in fragment.required_estimation_regimes
            ),
            applicable_fiscal_residencies=frozenset(
                FiscalResidency(value) for value in fragment.applicable_fiscal_residencies
            ),
            applicable_iva_regimes=frozenset(IVARegime(value) for value in fragment.applicable_iva_regimes),
            required_payer_fact=PayerFact(fragment.required_payer_fact)
            if fragment.required_payer_fact is not None
            else None,
            applicable_reason=fragment.applicable_reason,
            not_applicable_reason=fragment.not_applicable_reason,
            cuota_bearing=fragment.cuota_bearing,
            legal_refs=fragment.legal_refs,
        )
    except ValueError as exc:
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

_ATTRIBUTION_PASS_THROUGH_REASON = (
    "Una entidad en régimen de atribución de rentas (comunidad de bienes, "
    "sociedad civil sin objeto mercantil) no presenta autoliquidación de "
    "cuota propia: no tributa por el Impuesto sobre Sociedades ni por el "
    "IRPF. La renta se atribuye a cada socio, comunero o partícipe y "
    "tributa en la declaración de cada miembro. La obligación propia de la "
    "entidad es informativa (Modelo 184)."
)
"""``ATTRIBUTION_PASS_THROUGH`` rationale.

The honest answer to "what is my cuota" for an attribution entity: it
files no IS and no IRPF cuota of its own. The substantive tax is each
member's; the entity's own obligation is the informational Modelo 184.
"""

_INCOMPLETE_UNDECLARED_REASON = (
    "No se puede determinar la aplicabilidad: el tipo de contribuyente no "
    "está declarado. Faltan el tipo de entidad y, en su caso, las "
    "categorías de renta del IRPF."
)
"""``INCOMPLETE`` rationale for an *undeclared taxpayer model*.

Used only when the engine cannot decide because the profile itself is
incomplete: no ``entity_type``, or a natural person with no declared
IRPF income category against a category-gated rule. The guidance to
declare the taxpayer type first is correct here.
"""

_INCOMPLETE_UNRULED_REASON = (
    "No se puede determinar la aplicabilidad de este modelo: todavía no se "
    "ha derivado una regla de aplicabilidad para él. La cobertura de reglas "
    "es deliberadamente reducida (el conjunto inicial de personas) y la "
    "expansión por entidad y régimen está pendiente. No es una afirmación "
    "sobre su perfil: su tipo de contribuyente puede estar correctamente "
    "declarado."
)
"""``INCOMPLETE`` rationale for a *modelo with no seed rule*.

Used when :data:`_MODELO_APPLICABILITY_RULES` carries no rule for the
requested modelo. The profile may be fully declared; this verdict is a
statement about the seed coverage (:data:`_SEED_COVERAGE_NOTICE`), not
about the operator. It must never tell a declared operator to declare
their taxpayer type.
"""

_INCOMPLETE_UNDETERMINED_REASON = (
    "No se puede determinar la aplicabilidad de este modelo desde el modelo "
    "de contribuyente declarado: depende de un hecho que el perfil no "
    "expresa con certeza. El modelo solo se afirma aplicable cuando ese "
    "hecho se declara positivamente; en otro caso no se conjetura una "
    "obligación."
)

# Public read-only facades consumed by the focused applicability module. The
# implementation names remain underscored to mark configuration ownership;
# consumers import these aliases rather than reaching into private symbols.
INCOMPLETE_LEGAL_REFS = _INCOMPLETE_LEGAL_REFS
ATTRIBUTION_PASS_THROUGH_LEGAL_REFS = _ATTRIBUTION_PASS_THROUGH_LEGAL_REFS
INCOMPLETE_UNDECLARED_REASON = _INCOMPLETE_UNDECLARED_REASON
INCOMPLETE_UNRULED_REASON = _INCOMPLETE_UNRULED_REASON
INCOMPLETE_UNDETERMINED_REASON = _INCOMPLETE_UNDETERMINED_REASON
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

_IMPATRIADO_M720_EXEMPT_REASON = (
    "Modelo 720 no aplica: el contribuyente tiene activado el régimen "
    "especial para trabajadores desplazados a territorio español (LIRPF "
    "Art. 93). En este régimen el contribuyente tributa conforme al IRNR "
    "y no tiene la consideración de contribuyente residente del IRPF a "
    "efectos de la obligación de declarar bienes y derechos en el "
    "extranjero. La obligación del Modelo 720 corresponde exclusivamente "
    "a los residentes fiscales contribuyentes del IRPF (DA 18ª Ley "
    "58/2003 LGT introducida por la Ley 7/2012 DA 1ª)."
)
"""``NOT_APPLICABLE`` rationale for the impatriado Art. 93 M720 exemption.

Surfaced when ``profile.irpf_special_regime is IrpfSpecialRegime.IMPATRIADO``
and ``modelo == "720"``. The pre-check in :func:`derive_modelo_applicability`
fires before the :data:`_MODELO_APPLICABILITY_RULES` lookup to guarantee the
exemption is enforced even when ``bienes_extranjero_above_threshold`` is
``True``.
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

_IMPATRIADO_M100_SUPPRESSED_REASON = (
    "Modelo 100 no aplica: el contribuyente tiene activo el régimen especial "
    "de trabajadores, profesionales, emprendedores e inversores desplazados "
    "a territorio español (LIRPF Art. 93) dentro de la ventana de seis "
    "ejercicios. Durante esa ventana tributa por las reglas del IRNR "
    "manteniendo la condición de contribuyente IRPF, y la declaración anual "
    "correspondiente es el Modelo 151, no el Modelo 100."
)
"""``NOT_APPLICABLE`` rationale for suppressing M100 during Art. 93."""

_IMPATRIADO_M151_APPLICABLE_REASON = (
    "Modelo 151 aplica: el contribuyente tiene activo el régimen especial de "
    "impatriados del Art. 93 LIRPF dentro de la ventana de seis ejercicios "
    "del año de opción y los cinco siguientes; la declaración anual del "
    "régimen se presenta por Modelo 151."
)
"""``APPLICABLE`` rationale for the active Art. 93 Modelo 151 route."""

_IMPATRIADO_M151_NOT_APPLICABLE_REASON = (
    "Modelo 151 no aplica: el perfil no tiene activo el régimen especial de "
    "impatriados del Art. 93 LIRPF dentro de su ventana de seis ejercicios. "
    "Fuera de esa ventana, o sin opción por el régimen, la persona física "
    "residente vuelve a la ruta ordinaria del IRPF y al Modelo 100 cuando "
    "proceda."
)
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
    reason = _INCOMPLETE_UNRULED_REASON if unruled else _INCOMPLETE_UNDECLARED_REASON
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
    payer_fact: PayerFact,
    legal_refs: tuple[LegalRefId, ...],
) -> ModeloApplicability:
    """Return the ``INCOMPLETE`` applicability for a fact only the taxpayer can supply.

    Used when a modelo gates on a :class:`PayerFact` (Modelo
    111 / 115 / 349 / 347 / 720 / 721) and the profile does not positively declare
    the fact. The taxpayer model itself may be fully declared — the
    entity type and regime are known — but the payer fact has no
    tri-state, so the engine refuses to guess a ``NOT_APPLICABLE`` it
    cannot positively justify. The rationale is distinct from the
    *undeclared taxpayer model* one: it never tells a declared operator
    to declare their taxpayer type.

    Args:
        modelo: The AEAT modelo identifier the verdict decides.
        payer_fact: The specific profile fact required to positively
            establish applicability.
        legal_refs: The concrete rule legal refs that ground the
            payer-fact requirement, pending the taxpayer's own answer.

    Returns:
        A :class:`ModeloApplicability` with ``INCOMPLETE`` verdict and the
        undetermined-payer-fact rationale.
    """
    return ModeloApplicability(
        modelo=modelo,
        verdict=ApplicabilityVerdict.INCOMPLETE,
        reason=(
            f"{_INCOMPLETE_UNDETERMINED_REASON} "
            f"Hecho requerido para este modelo: {_PAYER_FACT_INCOMPLETE_LABELS[payer_fact]}."
        ),
        legal_refs=legal_refs,
    )


# ---------------------------------------------------------------------
# Seed rule table — core persona coverage (see _SEED_COVERAGE_NOTICE)
# ---------------------------------------------------------------------
#
# Every rule below is grounded against the registry legal tables for the
# taxpayer-type applicability model. Citation keys are scoped registry
# keys (``law-slug:art-N``) that resolve against
# ``src/cadrumo/_data/registry/aeat/legal/*.toml`` — never URLs, never
# invented slugs. Full per-entity / per-regime coverage of every
# registered modelo is a deferred expansion.

_NATURAL_PERSON: frozenset[EntityType] = frozenset({EntityType.NATURAL_PERSON})
_LEGAL_ENTITY: frozenset[EntityType] = frozenset({EntityType.LEGAL_ENTITY})
_ATTRIBUTION_ENTITY: frozenset[EntityType] = frozenset({EntityType.ATTRIBUTION_ENTITY})
_IVA_OBLIGED_ENTITY_TYPES: frozenset[EntityType] = frozenset(
    {EntityType.NATURAL_PERSON, EntityType.LEGAL_ENTITY, EntityType.ATTRIBUTION_ENTITY},
)
_IVA_SELF_ASSESSMENT_REGIMES: frozenset[IVARegime] = frozenset(
    {IVARegime.GENERAL, IVARegime.SIMPLIFICADO},
)
_PAYER_FACT_ENTITY_TYPES: frozenset[EntityType] = frozenset(
    {EntityType.NATURAL_PERSON, EntityType.LEGAL_ENTITY, EntityType.ATTRIBUTION_ENTITY},
)

_MODELO_APPLICABILITY_RULES: dict[str, ModeloApplicabilityRule] = {
    # Modelo 390 — declaración-resumen anual del IVA. The annual companion
    # to Modelo 303: a taxpayer in a periodic IVA self-assessment regime
    # files it. A natural person must also declare actividad económica;
    # legal and attribution entities do not carry the IRPF income-category
    # axis, so their gate is entity type plus IVA regime. Same
    # applicability gate as Modelo 303. (SII filers are exempt from Modelo
    # 390; that suppression is not yet modelled and would gate on the SII
    # enrolment axis.)
    Modelo.M390: ModeloApplicabilityRule(
        modelo=Modelo.M390,
        applicable_entity_types=_IVA_OBLIGED_ENTITY_TYPES,
        required_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        applicable_iva_regimes=_IVA_SELF_ASSESSMENT_REGIMES,
        applicable_reason=(
            "Modelo 390 (resumen anual del IVA): el contribuyente realiza "
            "una actividad económica sujeta al IVA y presenta la "
            "declaración-resumen anual del impuesto."
        ),
        not_applicable_reason=(
            "Modelo 390 no aplica: sin una actividad económica sujeta al "
            "IVA no hay declaración-resumen anual del impuesto."
        ),
        # RD 1624/1992 art. 71 — declaraciones-liquidaciones del IVA y la
        # declaración-resumen anual; Orden EHA/3111/2009 art. 1 —
        # aprobación del Modelo 390.
        legal_refs=(
            "rd-1624-1992:art-71",
            "orden-eha-3111-2009:art-1",
        ),
    ),
    # Modelo 303 — autoliquidación periódica del IVA. Triggered by carrying
    # on an actividad económica subject to IVA: a natural person with
    # rendimientos de actividades económicas, or a legal / attribution
    # entity in a periodic IVA self-assessment regime. A pure landlord of
    # residential property, a salaried-only taxpayer, and a pensioner carry
    # on no IVA-subject activity. (Commercial rental can be IVA-subject;
    # the seed gates natural persons on the actividad-económica category,
    # which a pure landlord does not declare. Finer rental-IVA nuance is a
    # deferred expansion.)
    Modelo.M303: ModeloApplicabilityRule(
        modelo=Modelo.M303,
        applicable_entity_types=_IVA_OBLIGED_ENTITY_TYPES,
        required_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        applicable_iva_regimes=_IVA_SELF_ASSESSMENT_REGIMES,
        applicable_reason=(
            "Modelo 303 (autoliquidación del IVA): el contribuyente "
            "realiza una actividad económica sujeta al IVA y presenta la "
            "autoliquidación periódica."
        ),
        not_applicable_reason=(
            "Modelo 303 no aplica: sin una actividad económica sujeta al "
            "IVA no hay autoliquidación periódica del impuesto."
        ),
        # LIVA art. 99 — ejercicio del derecho a la deducción mediante
        # las declaraciones-liquidaciones periódicas del IVA que liquida
        # el Modelo 303.
        legal_refs=("ley-37-1992:art-99",),
    ),
}

MODELO_APPLICABILITY_RULES = _MODELO_APPLICABILITY_RULES
"""Seed modelo-applicability rules — core persona coverage.

A modelo absent from this table has no derived rule yet: its
applicability is reported :attr:`ApplicabilityVerdict.INCOMPLETE` with
a rationale pointing at the deferred expansion. See
:data:`_SEED_COVERAGE_NOTICE`.
"""


#: Modelo ids whose applicability rule is authored in the registry rather than
#: declared as a Python literal in :data:`_MODELO_APPLICABILITY_RULES` below.
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
#: ``_MODELO_APPLICABILITY_RULES`` is now in: these modelos resolve from the
#: registry, 303 and 390 still resolve from the literal table. The literal
#: table retires outright once the export-fragment campaign closes those two
#: trees and they are migrated the same way; this module then stops authoring
#: applicability data at all -- it only reads it.
REGISTRY_RESOLVED_APPLICABILITY_MODELOS: frozenset[Modelo] = frozenset(
    {
        Modelo.M100,
        Modelo.M111,
        Modelo.M115,
        Modelo.M117,
        Modelo.M123,
        Modelo.M126,
        Modelo.M128,
        Modelo.M130,
        Modelo.M131,
        Modelo.M136,
        Modelo.M145,
        Modelo.M151,
        Modelo.M180,
        Modelo.M184,
        Modelo.M187,
        Modelo.M188,
        Modelo.M190,
        Modelo.M193,
        Modelo.M194,
        Modelo.M200,
        Modelo.M202,
        Modelo.M210,
        Modelo.M216,
        Modelo.M232,
        Modelo.M296,
        Modelo.M322,
        Modelo.M347,
        Modelo.M349,
        Modelo.M353,
        Modelo.M360,
        Modelo.M369,
        Modelo.M714,
        Modelo.M720,
        Modelo.M721,
        Modelo.M840,
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
    applicability answer. The fragment was already validated once, at
    registry build time, by
    :func:`~._validate_applicability_section.validate_applicability_section`.

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
    tree or monkeypatching anything; the production wrapper is the only
    caller that hardcodes :func:`~._authority.bundled_authority`.

    Raises:
        RegistryValidationError: No declared revision carries an
            ``applicability`` rule, or the rule fails to hydrate.
    """
    definition = authority.modelo(modelo.value)
    for revision in definition.revisions.values():
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
) -> ModeloApplicabilityRule:
    """Resolve one modelo's applicability rule from the bundled registry authoring tree.

    The import is function-local by necessity, not preference: ``_authority``
    transitively imports THIS module already, through the build-validation
    dispatch chain (``_authority`` -> ``_snapshot`` -> ``_validate`` ->
    ``_validate_revision_sections`` -> ``_validate_applicability_section`` ->
    here), so a module-level import of :func:`~._authority.bundled_authority`
    would close a real cycle. Resolving on first call, long after both
    modules have finished importing, is the same discipline
    :func:`~._loader.load_legal_parameters_only`'s own cycle-safe entry point
    already documents -- module-body evaluation is the hazard, first-call
    resolution is not.

    No local cache sits in front of this call: :func:`~._authority.bundled_authority`
    is itself fingerprint-bounded (W01.P02.S28), so calling it here costs one
    O(1) cache-key hash, not a re-parse, and a tree edit is seen on the very
    next call. Caching here would re-introduce the path-only registry cache
    the authority-flow rule forbids -- exactly the defect S28 removed.
    """
    if authority is not None:
        return resolve_applicability_rule_from_authority(authority, modelo)

    from .authority import bundled_authority

    return resolve_applicability_rule_from_authority(bundled_authority(), modelo)


def _modelo_applicability_rule(
    modelo: str,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> ModeloApplicabilityRule | None:
    """Return ``modelo``'s applicability rule, resolved from the registry or the literal table.

    The single seam every consumer (:func:`derive_modelo_applicability`,
    :func:`has_applicability_rule`, :func:`iter_modelo_applicability_rules`)
    reads through, so the mixed-surface split (registry-resolved vs.
    still-literal) is decided in exactly one place. An unrecognised
    ``modelo`` string -- not a member of either surface -- returns ``None``,
    matching the pre-cutover dict-lookup behaviour exactly; it is never an
    error to ask about an unruled modelo.
    """
    if modelo in REGISTRY_RESOLVED_APPLICABILITY_MODELOS:
        return _resolve_registry_applicability_rule(Modelo(modelo), authority=authority)
    return _MODELO_APPLICABILITY_RULES.get(modelo)


def has_applicability_rule(modelo: str) -> bool:
    """Return whether an applicability rule exists for ``modelo``."""
    return _modelo_applicability_rule(modelo) is not None


def iter_modelo_applicability_rules() -> tuple[ModeloApplicabilityRule, ...]:
    """Return every registry-resolved or seed-literal :class:`ModeloApplicabilityRule`.

    The returned tuple is ordered by modelo id for deterministic audits and
    tests. Callers receive rule objects, not the mutable module-level
    dictionary, so the registry rule table remains read-only from the public
    API.
    """
    known_modelos = sorted(
        {str(modelo) for modelo in _MODELO_APPLICABILITY_RULES} | REGISTRY_RESOLVED_APPLICABILITY_MODELOS,
    )
    return tuple(rule for modelo in known_modelos if (rule := _modelo_applicability_rule(modelo)) is not None)


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
    if profile.entity_type is EntityType.NATURAL_PERSON:
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
    return _TAX_ROUTE_FOR_ENTITY_TYPE[profile.entity_type]


def derive_modelo_applicability(
    profile: TaxpayerProfile,
    modelo: str,
    *,
    today: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> ModeloApplicability:
    """Derive a modelo's applicability from the taxpayer model.

    The verdict is DERIVED from the three-axis
    :class:`~domain.deadlines.TaxpayerProfile` model — never
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

    Returns:
        The :class:`ModeloApplicability` for ``modelo`` and ``profile``.
    """
    _today = today if today is not None else today_madrid()
    beckham_window_active = profile.beckham_window_active(_today)

    # The Art. 93 impatriado route is a modelo-level switch while the
    # six-year Beckham window is active: the annual declaration is Modelo
    # 151, and the ordinary Renta self-assessment (Modelo 100) is not the
    # filing route. Once the window expires, both modelos fall back to their
    # ordinary applicability rules: M100 through the seed table below, M151
    # to a positive NOT_APPLICABLE.
    if beckham_window_active and modelo == Modelo.M100:
        return ModeloApplicability(
            modelo=Modelo.M100,
            verdict=ApplicabilityVerdict.NOT_APPLICABLE,
            reason=_IMPATRIADO_M100_SUPPRESSED_REASON,
            legal_refs=_IMPATRIADO_M151_ROUTE_LEGAL_REFS,
        )
    if modelo == Modelo.M151:
        return ModeloApplicability(
            modelo=Modelo.M151,
            verdict=(ApplicabilityVerdict.APPLICABLE if beckham_window_active else ApplicabilityVerdict.NOT_APPLICABLE),
            reason=(
                _IMPATRIADO_M151_APPLICABLE_REASON if beckham_window_active else _IMPATRIADO_M151_NOT_APPLICABLE_REASON
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
    if modelo == Modelo.M720 and beckham_window_active:
        return ModeloApplicability(
            modelo=Modelo.M720,
            verdict=ApplicabilityVerdict.NOT_APPLICABLE,
            reason=_IMPATRIADO_M720_EXEMPT_REASON,
            legal_refs=_IMPATRIADO_M720_LEGAL_REFS,
        )
    rule = _modelo_applicability_rule(modelo, authority=authority)
    if rule is None:
        return _incomplete_applicability(modelo, unruled=True)
    return rule.evaluate(profile)


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
    return IrpfIncomeCategory.ACTIVIDAD_ECONOMICA in profile.irpf_income_categories


def derive_not_applicable_source_modelos(profile: TaxpayerProfile, modelos: Iterable[str]) -> frozenset[str] | None:
    """Return source modelos positively known not applicable for ``profile``.

    Fail-closed: if applicability derivation raises or returns an
    incomplete/undetermined verdict for ANY queried modelo, callers receive
    ``None`` and suppress nothing. A positive
    :attr:`ApplicabilityVerdict.NOT_APPLICABLE` result is grounded in the same
    rules :func:`derive_modelo_applicability` applies to decide whether the
    :class:`TaxpayerProfile` files M130 or M131.

    Consumed by the cross-period clean-state gate (which sources need no
    upstream filing evidence) and by the relation-prefill resolver (which
    unresolved relation legs fold in as an explicit zero). Both must read one
    applicability verdict, so it lives here beside
    :func:`derive_modelo_applicability` rather than in either consumer.
    """
    not_applicable: set[str] = set()
    for modelo in sorted({str(modelo) for modelo in modelos}):
        try:
            applicability = derive_modelo_applicability(profile, modelo)
        except (TypeError, ValueError):
            return None
        if applicability.verdict is ApplicabilityVerdict.NOT_APPLICABLE:
            not_applicable.add(modelo)
        elif applicability.verdict not in {
            ApplicabilityVerdict.APPLICABLE,
            ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH,
        }:
            return None
    return frozenset(not_applicable)


__all__ = [
    "ApplicabilityVerdict",
    "ModeloApplicability",
    "ModeloApplicabilityRule",
    "derive_modelo_applicability",
    "derive_not_applicable_source_modelos",
    "derive_tax_route",
    "derive_taxpayer_files_economic_activity",
    "has_applicability_rule",
    "iter_modelo_applicability_rules",
    "taxpayer_model_is_declared",
]
