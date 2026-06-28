"""Registry-grounded modelo-applicability derivation from the taxpayer model.

The overview surfaces (``explain`` / ``calendar`` / ``agenda`` /
``backlog``) used to treat every profile as an *autónomo en estimación
directa*: the :class:`~aeat.domain.deadlines.DeadlineEngine` produces an
obligation for every modelo with a registered deadline window, and no
layer asked *which kind of taxpayer this is*. A pure landlord was told
Modelo 130 was overdue.

This module is the derivation layer: each modelo's ``applicable``
verdict is DERIVED from the three-axis
:class:`~aeat.domain.deadlines.TaxpayerProfile` model (entity type,
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

The entity-type axis selects the *tax*, and the tax selects the
modelos: a legal entity routes to the IS path (Modelo 200 / 202), a
natural person to the IRPF path (Modelo 100 / 130 / 303), and an
attribution entity to the member pass-through (its own obligation is
the informational Modelo 184). This is the corporate-entity ADR §4
engine routing contract.

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
against ``src/aeat/_data/registry/aeat/legal/*.toml`` — per
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

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field

from ....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core import Modelo
from ...deadlines import FiscalResidency
from ...deadlines.taxpayer_model import (
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    TaxpayerProfile,
)
from ._applicability_modelo202 import (
    Modelo202Modality,
    Modelo202ModalityVerdict,
    derive_modelo_202_modality,
    modelo_202_modality_from_inputs,
)
from ._applicability_payer_facts import PayerFact, payer_fact_holds
from ._applicability_routes import TAX_ROUTE_FOR_ENTITY_TYPE as _TAX_ROUTE_FOR_ENTITY_TYPE
from ._applicability_routes import TaxRoute

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

    modelo: str = Field(min_length=1, max_length=8)
    verdict: ApplicabilityVerdict
    reason: str = Field(min_length=1)
    legal_refs: tuple[str, ...] = Field(min_length=1)

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
            ``NOT_APPLICABLE``. An *undeclared* regime is resolved from
            the always-definite ``uses_objective_estimation_irpf``
            boolean (default ``False``): estimación directa is the
            default IRPF method (LIRPF art. 16; RIRPF art. 32 makes
            módulos opt-in), so an undeclared regime defaults to directa
            and an actividad-económica autónomo who has not elected
            módulos owes Modelo 130. This is the axis that splits Modelo
            130 (estimación directa) from Modelo 131 (estimación
            objetiva): the two are mutually exclusive on the regime.
        applicable_fiscal_residencies: The fiscal residency categories
            the modelo applies to. Empty means the modelo does not gate
            on fiscal residency. An undeclared residency is kept on the
            resident-IRPF default path described by ``TaxpayerProfile``;
            a declared residency outside this set is a positive
            exclusion.
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
            members' returns (corporate-entity ADR §2). An
            informational modelo (Modelo 184) is *not* cuota-bearing —
            it stays a plain ``NOT_APPLICABLE`` for the entity types
            its ``applicable_entity_types`` excludes.
        legal_refs: Scoped registry citation keys (``law-slug:art-N``)
            grounding the rule, each resolvable against the registry
            ``legal/*.toml`` tables.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    applicable_entity_types: frozenset[EntityType] = Field(min_length=1)
    required_income_categories: frozenset[IrpfIncomeCategory] = frozenset()
    required_estimation_regimes: frozenset[IrpfEstimationRegime] = frozenset()
    applicable_fiscal_residencies: frozenset[FiscalResidency] = frozenset()
    required_payer_fact: PayerFact | None = None
    applicable_reason: str = Field(min_length=1)
    not_applicable_reason: str = Field(min_length=1)
    cuota_bearing: bool = False
    legal_refs: tuple[str, ...] = Field(min_length=1)

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
            return _incomplete_applicability(self.modelo)
        if profile.entity_type not in self.applicable_entity_types:
            # An attribution entity asked about a cuota self-assessment
            # gets the honest pass-through answer, not a plain
            # exclusion: it runs no IS and no IRPF cuota — the income
            # is attributed to and taxed in the members' returns
            # (corporate-entity ADR §2). An informational modelo is not
            # cuota-bearing and falls through to NOT_APPLICABLE.
            if self.cuota_bearing and profile.entity_type is EntityType.ATTRIBUTION_ENTITY:
                return ModeloApplicability(
                    modelo=self.modelo,
                    verdict=ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH,
                    reason=_ATTRIBUTION_PASS_THROUGH_REASON,
                    legal_refs=_ATTRIBUTION_PASS_THROUGH_LEGAL_REFS,
                )
            return self._not_applicable()
        # The income-category and estimation-regime axes are
        # natural-person facts: a legal entity carries neither (income
        # categories and the IRPF estimation regime only describe a
        # persona física). A legal entity that matched the entity-type
        # gate of a modelo applicable to it (e.g. Modelo 303 / 390) is
        # not re-gated on those axes — its applicability is settled by
        # the entity type.
        if profile.entity_type is EntityType.NATURAL_PERSON:
            if (
                self.applicable_fiscal_residencies
                and profile.fiscal_residency is not None
                and profile.fiscal_residency not in self.applicable_fiscal_residencies
            ):
                return self._not_applicable()
            # A natural-person modelo that gates on income category needs
            # at least one declared category to match.
            if self.required_income_categories:
                if not profile.irpf_income_categories:
                    return _incomplete_applicability(self.modelo)
                if profile.irpf_income_categories.isdisjoint(self.required_income_categories):
                    return self._not_applicable()
            # The estimation-regime axis splits Modelo 130 (estimación
            # directa) from Modelo 131 (estimación objetiva). A regime
            # outside the rule's set is a positive exclusion.
            #
            # When the structured ``irpf_estimation_regime`` is undeclared
            # the engine still resolves the directa-vs-objetiva split from
            # the always-definite ``uses_objective_estimation_irpf``
            # boolean (default ``False``, kept in lockstep with the regime
            # by ``TaxpayerProfile._derive_objective_estimation_flag`` /
            # ``_check_objective_estimation_consistency``). Estimación
            # directa is the default IRPF method for actividad-económica
            # income (LIRPF art. 16; RIRPF RD 439/2007 art. 32 makes
            # estimación objetiva an opt-in módulos regime that requires
            # eligibility and non-renuncia): an autónomo who declares
            # actividad económica but has not elected módulos files under
            # estimación directa and owes Modelo 130. Reading the boolean
            # rather than refusing to decide is grounded in that default —
            # it does not invent profile data, and M130 / M131 stay
            # mutually exclusive (``False`` ⇒ directa ⇒ M130, ``True`` ⇒
            # objetiva ⇒ M131).
            if self.required_estimation_regimes:
                regime = profile.irpf_estimation_regime
                if regime is None:
                    regime = (
                        IrpfEstimationRegime.OBJETIVA
                        if profile.uses_objective_estimation_irpf
                        else IrpfEstimationRegime.DIRECTA_NORMAL
                    )
                if regime not in self.required_estimation_regimes:
                    return self._not_applicable()
        # The payer-fact axis (Modelo 111 / 115 / 349 / 347) can only be
        # asserted in the positive direction — the underlying boolean has
        # no tri-state, so an absent fact yields INCOMPLETE rather than a
        # NOT_APPLICABLE the engine cannot positively justify.
        if self.required_payer_fact is not None and not payer_fact_holds(profile, self.required_payer_fact):
            return _undetermined_applicability(self.modelo)
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


# Scoped registry citation keys grounding the "declare your taxpayer
# type first" answer. An undeclared profile cannot be decided, but the
# verdict still carries the LIRPF / LIS articles that frame the question
# the operator must answer. Both keys resolve in the registry legal
# tables (irpf.toml / is.toml).
_INCOMPLETE_LEGAL_REFS: tuple[str, ...] = (
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
_ATTRIBUTION_PASS_THROUGH_LEGAL_REFS: tuple[str, ...] = (
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
files no IS and no IRPF cuota of its own (corporate-entity ADR §2).
The substantive tax is each member's; the entity's own obligation is
the informational Modelo 184.
"""

_INCOMPLETE_UNDECLARED_REASON = (
    "No se puede determinar la aplicabilidad: el tipo de contribuyente no "
    "está declarado. Declare primero el tipo de entidad y, en su caso, las "
    "categorías de renta del IRPF con 'aeat config profile edit'."
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
    "expresa con certeza (si paga retribuciones o alquileres sujetos a "
    "retención, o si realiza operaciones intracomunitarias o con terceros). "
    "El modelo solo se afirma aplicable cuando ese hecho se declara "
    "positivamente; en otro caso no se conjetura una obligación."
)
"""``INCOMPLETE`` rationale for a *payer fact the profile cannot decide*.

Used by :func:`_undetermined_applicability` when a modelo gates on a
:class:`PayerFact` (Modelo 111 / 115 / 349 / 347) and the profile does
not positively declare it. The underlying boolean has no tri-state, so
a ``False`` value is indistinguishable from "not declared" — the engine
refuses to guess a ``NOT_APPLICABLE`` it cannot positively justify.
This is structurally distinct from the *undeclared taxpayer model*
rationale: the entity type and regime can be fully declared and this
verdict still holds.
"""

_IMPATRIADO_M720_LEGAL_REFS: tuple[str, ...] = (
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


def _incomplete_applicability(
    modelo: str,
    *,
    unruled: bool = False,
) -> ModeloApplicability:
    """Return the explicit ``INCOMPLETE`` applicability for ``modelo``.

    The safe default: the engine never assumes autónomo and never
    reports a confident wrong obligation. The two ``INCOMPLETE`` causes
    are structurally distinct and carry distinct rationale:

    Args:
        modelo: The AEAT modelo identifier the verdict decides.
        unruled: ``True`` when the cause is a *missing seed rule* for the
            modelo — the profile may be fully declared. ``False`` (the
            default) when the cause is an *undeclared taxpayer model* —
            the operator must declare their taxpayer type first.

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
    )


def _undetermined_applicability(modelo: str) -> ModeloApplicability:
    """Return the ``INCOMPLETE`` applicability for an *undecidable* fact.

    Used when a modelo gates on a :class:`PayerFact` (Modelo
    111 / 115 / 349 / 347) and the profile does not positively declare
    the fact. The taxpayer model itself may be fully declared — the
    entity type and regime are known — but the payer fact has no
    tri-state, so the engine refuses to guess a ``NOT_APPLICABLE`` it
    cannot positively justify. The rationale is distinct from the
    *undeclared taxpayer model* one: it never tells a declared operator
    to declare their taxpayer type.

    Args:
        modelo: The AEAT modelo identifier the verdict decides.

    Returns:
        A :class:`ModeloApplicability` with ``INCOMPLETE`` verdict and the
        undetermined-payer-fact rationale.
    """
    return ModeloApplicability(
        modelo=modelo,
        verdict=ApplicabilityVerdict.INCOMPLETE,
        reason=_INCOMPLETE_UNDETERMINED_REASON,
        legal_refs=_INCOMPLETE_LEGAL_REFS,
    )


# ---------------------------------------------------------------------
# Seed rule table — core persona coverage (see _SEED_COVERAGE_NOTICE)
# ---------------------------------------------------------------------
#
# Every rule below is grounded against the registry legal tables for the
# taxpayer-type applicability model. Citation keys are scoped registry
# keys (``law-slug:art-N``) that resolve against
# ``src/aeat/_data/registry/aeat/legal/*.toml`` — never URLs, never
# invented slugs. Full per-entity / per-regime coverage of every
# registered modelo is a deferred expansion.

_NATURAL_PERSON: frozenset[EntityType] = frozenset({EntityType.NATURAL_PERSON})
_LEGAL_ENTITY: frozenset[EntityType] = frozenset({EntityType.LEGAL_ENTITY})
_ATTRIBUTION_ENTITY: frozenset[EntityType] = frozenset({EntityType.ATTRIBUTION_ENTITY})

_MODELO_APPLICABILITY_RULES: dict[str, ModeloApplicabilityRule] = {
    # Modelo 100 — declaración anual de la Renta (IRPF). Applies to every
    # natural person who is an IRPF contribuyente, regardless of which
    # income category they declare. It does NOT apply to a legal entity:
    # an S.L. is a contribuyente del Impuesto sobre Sociedades and files
    # Modelo 200, never Modelo 100. Research §1.1, §1.2.
    Modelo.M100: ModeloApplicabilityRule(
        modelo=Modelo.M100,
        applicable_entity_types=_NATURAL_PERSON,
        required_income_categories=frozenset(),
        applicable_reason=(
            "Modelo 100 (declaración de la Renta): una persona física "
            "residente es contribuyente del IRPF y presenta la "
            "autoliquidación anual de la Renta."
        ),
        not_applicable_reason=(
            "Modelo 100 no aplica: la declaración de la Renta corresponde "
            "únicamente a las personas físicas contribuyentes del IRPF. El "
            "tipo de contribuyente declarado no es una persona física."
        ),
        # Modelo 100 is the IRPF cuota self-assessment: an attribution
        # entity asked about it gets the pass-through verdict.
        cuota_bearing=True,
        # LIRPF art. 99 — régimen general de pagos a cuenta del IRPF,
        # que identifica al contribuyente del IRPF; art. 17 —
        # rendimientos del trabajo, la categoría de renta más común que
        # obliga a la persona física a presentar la Renta.
        legal_refs=("ley-35-2006:art-99", "ley-35-2006:art-17"),
    ),
    # Modelo 130 — pago fraccionado del IRPF, estimación DIRECTA. Triggered
    # by the rendimientos de actividades económicas income category (LIRPF
    # Arts. 27-32) ONLY when the activity is in estimación directa (normal
    # o simplificada). An activity in estimación objetiva (módulos) files
    # Modelo 131 instead — the two are mutually exclusive on the regime.
    # A natural person whose only income is capital inmobiliario (a pure
    # landlord), trabajo, pensión, etc. has no actividad económica and
    # therefore no Modelo 130. A legal entity never files Modelo 130.
    Modelo.M130: ModeloApplicabilityRule(
        modelo=Modelo.M130,
        applicable_entity_types=_NATURAL_PERSON,
        required_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        required_estimation_regimes=frozenset(
            {
                IrpfEstimationRegime.DIRECTA_NORMAL,
                IrpfEstimationRegime.DIRECTA_SIMPLIFICADA,
            },
        ),
        applicable_fiscal_residencies=frozenset({FiscalResidency.RESIDENT_IRPF}),
        applicable_reason=(
            "Modelo 130 (pago fraccionado del IRPF): la persona física "
            "residente IRPF declara rendimientos de actividades económicas "
            "en estimación directa, que generan la obligación del pago "
            "fraccionado."
        ),
        not_applicable_reason=(
            "Modelo 130 no aplica: el pago fraccionado en estimación "
            "directa solo corresponde a la persona física residente IRPF "
            "que obtiene rendimientos de actividades económicas determinados "
            "por ese método. Una actividad en estimación objetiva presenta "
            "el Modelo 131; un contribuyente NON_RESIDENT_IRNR queda en la "
            "ruta IRNR."
        ),
        # Modelo 130 is an IRPF pago-fraccionado cuota self-assessment:
        # an attribution entity asked about it gets the pass-through
        # verdict — it runs no IRPF cuota of its own.
        cuota_bearing=True,
        # RD 439/2007 art. 110 — pago fraccionado del IRPF en estimación
        # directa, importe y cálculo; Orden EHA/672/2007 art. 1 —
        # aprobación del Modelo 130; LIRPF art. 99 — pagos fraccionados
        # como pagos a cuenta del IRPF.
        legal_refs=(
            "rd-439-2007:art-110",
            "orden-eha-672-2007:art-1",
            "ley-35-2006:art-99",
            "trlirnr-rdleg-5-2004:art-2",
        ),
    ),
    # Modelo 131 — pago fraccionado del IRPF, estimación OBJETIVA (módulos).
    # Triggered by the rendimientos de actividades económicas income
    # category ONLY when the activity is determined under estimación
    # objetiva. This is the regime counterpart of Modelo 130: an activity
    # in estimación directa files Modelo 130, never Modelo 131. A legal
    # entity never files Modelo 131. Research §2.1.
    Modelo.M131: ModeloApplicabilityRule(
        modelo=Modelo.M131,
        applicable_entity_types=_NATURAL_PERSON,
        required_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        required_estimation_regimes=frozenset({IrpfEstimationRegime.OBJETIVA}),
        applicable_reason=(
            "Modelo 131 (pago fraccionado del IRPF): la persona física "
            "declara rendimientos de actividades económicas en estimación "
            "objetiva (módulos), que generan la obligación del pago "
            "fraccionado por ese método."
        ),
        not_applicable_reason=(
            "Modelo 131 no aplica: el pago fraccionado en estimación "
            "objetiva solo corresponde a la persona física cuya actividad "
            "económica se determina por el método de módulos. Una "
            "actividad en estimación directa presenta el Modelo 130."
        ),
        # Modelo 131 is an IRPF pago-fraccionado cuota self-assessment:
        # an attribution entity asked about it gets the pass-through
        # verdict.
        cuota_bearing=True,
        # RD 439/2007 art. 110 — pago fraccionado del IRPF, importe y
        # cálculo; Orden EHA/672/2007 art. 1 — aprobación del Modelo 131
        # junto con el 130; LIRPF art. 99 — pagos fraccionados como pagos
        # a cuenta del IRPF.
        legal_refs=(
            "rd-439-2007:art-110",
            "orden-eha-672-2007:art-1",
            "ley-35-2006:art-99",
        ),
    ),
    # Modelo 111 — autoliquidación de retenciones e ingresos a cuenta del
    # IRPF (rendimientos del trabajo / actividades profesionales). It is
    # the PAYER's obligation: a taxpayer — a natural person with actividad
    # económica or a legal entity — who pays salaries or withholding-
    # subject professional fees. Whether the taxpayer pays such income is
    # a payer fact the three-axis model cannot decide on its own; a
    # profile that does not positively declare it yields INCOMPLETE rather
    # than a guessed NOT_APPLICABLE. Research §1.1.
    Modelo.M111: ModeloApplicabilityRule(
        modelo=Modelo.M111,
        applicable_entity_types=frozenset({EntityType.NATURAL_PERSON, EntityType.LEGAL_ENTITY}),
        required_payer_fact=PayerFact.PAYS_WITHHELD_INCOME,
        applicable_reason=(
            "Modelo 111 (retenciones e ingresos a cuenta del IRPF): el "
            "contribuyente paga rendimientos del trabajo o de actividades "
            "profesionales sujetos a retención y autoliquida las "
            "retenciones practicadas."
        ),
        not_applicable_reason=(
            "Modelo 111 no aplica: la autoliquidación de retenciones del "
            "IRPF solo corresponde a quien paga rendimientos sujetos a "
            "retención."
        ),
        # LIRPF art. 99 — obligación de practicar retenciones e ingresos a
        # cuenta; RD 439/2007 art. 108 — declaración e ingreso de las
        # retenciones (Modelo 111); Orden EHA/586/2011 art. 1 — aprobación
        # del Modelo 111.
        legal_refs=(
            "ley-35-2006:art-99",
            "rd-439-2007:art-108",
            "orden-eha-586-2011:art-1",
        ),
    ),
    # Modelo 115 — autoliquidación de retenciones por arrendamiento de
    # inmuebles urbanos. The PAYER's obligation: a taxpayer who pays rent
    # subject to retención. Whether the taxpayer pays such rent is a payer
    # fact the three-axis model cannot decide alone; an undeclared fact
    # yields INCOMPLETE.
    Modelo.M115: ModeloApplicabilityRule(
        modelo=Modelo.M115,
        applicable_entity_types=frozenset({EntityType.NATURAL_PERSON, EntityType.LEGAL_ENTITY}),
        required_payer_fact=PayerFact.PAYS_RENT_WITH_RETENCION,
        applicable_reason=(
            "Modelo 115 (retenciones por arrendamiento de inmuebles "
            "urbanos): el contribuyente paga alquiler de inmueble urbano "
            "sujeto a retención y autoliquida las retenciones practicadas."
        ),
        not_applicable_reason=(
            "Modelo 115 no aplica: la autoliquidación de retenciones por "
            "arrendamiento solo corresponde a quien paga alquileres "
            "sujetos a retención."
        ),
        # LIRPF art. 99 — obligación de practicar retenciones; RD 439/2007
        # art. 100 — retención sobre rendimientos del arrendamiento de
        # inmuebles urbanos; RD 439/2007 art. 108 — declaración e ingreso
        # de las retenciones (Modelo 115).
        legal_refs=(
            "ley-35-2006:art-99",
            "rd-439-2007:art-100",
            "rd-439-2007:art-108",
        ),
    ),
    # Modelo 190 — resumen anual de retenciones e ingresos a cuenta del
    # IRPF sobre rendimientos del trabajo y de actividades económicas. The
    # annual companion to Modelo 111: a taxpayer who files Modelo 111
    # files Modelo 190. Gated on the same payer fact as Modelo 111.
    Modelo.M190: ModeloApplicabilityRule(
        modelo=Modelo.M190,
        applicable_entity_types=frozenset({EntityType.NATURAL_PERSON, EntityType.LEGAL_ENTITY}),
        required_payer_fact=PayerFact.PAYS_WITHHELD_INCOME,
        applicable_reason=(
            "Modelo 190 (resumen anual de retenciones del IRPF): el "
            "contribuyente que paga rendimientos del trabajo o de "
            "actividades profesionales sujetos a retención presenta el "
            "resumen anual de las retenciones declaradas en el Modelo 111."
        ),
        not_applicable_reason=(
            "Modelo 190 no aplica: el resumen anual de retenciones del "
            "IRPF solo corresponde a quien paga rendimientos sujetos a "
            "retención."
        ),
        # LIRPF art. 99 — obligación de retener; RD 439/2007 art. 108 —
        # declaración trimestral/mensual y resumen anual de las retenciones
        # e ingresos a cuenta.
        legal_refs=(
            "ley-35-2006:art-99",
            "rd-439-2007:art-108",
        ),
    ),
    # Modelo 180 — resumen anual de retenciones e ingresos a cuenta del
    # IRPF sobre rendimientos del arrendamiento de inmuebles urbanos. The
    # annual companion to Modelo 115: gated on the same payer fact.
    Modelo.M180: ModeloApplicabilityRule(
        modelo=Modelo.M180,
        applicable_entity_types=frozenset({EntityType.NATURAL_PERSON, EntityType.LEGAL_ENTITY}),
        required_payer_fact=PayerFact.PAYS_RENT_WITH_RETENCION,
        applicable_reason=(
            "Modelo 180 (resumen anual de retenciones por arrendamiento): "
            "el contribuyente que paga alquiler de inmueble urbano sujeto "
            "a retención presenta el resumen anual de las retenciones "
            "declaradas en el Modelo 115."
        ),
        not_applicable_reason=(
            "Modelo 180 no aplica: el resumen anual de retenciones por "
            "arrendamiento solo corresponde a quien paga alquileres "
            "sujetos a retención."
        ),
        # LIRPF art. 99 — obligación de retener; RD 439/2007 art. 100 —
        # retención sobre el arrendamiento de inmuebles urbanos; RD
        # 439/2007 art. 108 — declaración trimestral/mensual y resumen
        # anual de las retenciones e ingresos a cuenta.
        legal_refs=(
            "ley-35-2006:art-99",
            "rd-439-2007:art-100",
            "rd-439-2007:art-108",
        ),
    ),
    # Modelo 349 — declaración recapitulativa de operaciones
    # intracomunitarias. Applies to a taxpayer — a natural person with
    # actividad económica or a legal entity — who performs operaciones
    # intracomunitarias. Whether the taxpayer trades intracommunity is a
    # payer fact the three-axis model cannot decide alone; an undeclared
    # fact yields INCOMPLETE. Research §3.3.
    Modelo.M349: ModeloApplicabilityRule(
        modelo=Modelo.M349,
        applicable_entity_types=frozenset({EntityType.NATURAL_PERSON, EntityType.LEGAL_ENTITY}),
        required_payer_fact=PayerFact.TRADES_INTRACOMMUNITY,
        applicable_reason=(
            "Modelo 349 (declaración recapitulativa de operaciones "
            "intracomunitarias): el contribuyente realiza operaciones "
            "intracomunitarias y presenta su declaración recapitulativa."
        ),
        not_applicable_reason=(
            "Modelo 349 no aplica: la declaración recapitulativa solo "
            "corresponde a quien realiza operaciones intracomunitarias."
        ),
        # Orden EHA/769/2010 art. 1 — aprobación del Modelo 349; Orden
        # HAC/174/2020 art. 1 — modificación del Modelo 349; LGT art. 93 —
        # obligación de información sobre operaciones con terceros.
        legal_refs=(
            "orden-eha-769-2010:art-1",
            "orden-hac-174-2020:art-1",
            "ley-58-2003:art-93",
        ),
    ),
    # Modelo 347 — declaración anual de operaciones con terceras personas.
    # Applies to a taxpayer whose third-party transactions exceeded the
    # declaration threshold. Whether the threshold is exceeded is a payer
    # fact the three-axis model cannot decide alone; an undeclared fact
    # yields INCOMPLETE.
    Modelo.M347: ModeloApplicabilityRule(
        modelo=Modelo.M347,
        applicable_entity_types=frozenset({EntityType.NATURAL_PERSON, EntityType.LEGAL_ENTITY}),
        required_payer_fact=PayerFact.EXCEEDS_THIRD_PARTY_THRESHOLD,
        applicable_reason=(
            "Modelo 347 (declaración anual de operaciones con terceras "
            "personas): las operaciones del contribuyente con un tercero "
            "superan el umbral de declaración y debe presentar la "
            "declaración informativa anual."
        ),
        not_applicable_reason=(
            "Modelo 347 no aplica: la declaración de operaciones con "
            "terceros solo corresponde a quien supera el umbral de "
            "operaciones declarable."
        ),
        # Orden EHA/3012/2008 art. 1 — aprobación del Modelo 347 y
        # obligados a presentarlo; Orden EHA/3012/2008 art. 10 — contenido
        # de la declaración; LGT art. 93 — obligación de información sobre
        # operaciones con terceros.
        legal_refs=(
            "orden-eha-3012-2008:art-1",
            "orden-eha-3012-2008:art-10",
            "ley-58-2003:art-93",
        ),
    ),
    # Modelo 390 — declaración-resumen anual del IVA. The annual companion
    # to Modelo 303: a taxpayer carrying on an IVA-subject actividad
    # económica — a natural person with actividad económica or a legal
    # entity — files it. Same applicability gate as Modelo 303. (SII
    # filers are exempt from Modelo 390; that suppression is a deferred
    # expansion gated on the SII enrolment axis — research §3.1.)
    Modelo.M390: ModeloApplicabilityRule(
        modelo=Modelo.M390,
        applicable_entity_types=frozenset({EntityType.NATURAL_PERSON, EntityType.LEGAL_ENTITY}),
        required_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
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
    # rendimientos de actividades económicas, or a legal entity. A pure
    # landlord of residential property, a salaried-only taxpayer, and a
    # pensioner carry on no IVA-subject activity. (Commercial rental can be
    # IVA-subject; the seed gates on the actividad-económica category,
    # which a pure landlord does not declare. Finer rental-IVA nuance is
    # a deferred expansion.)
    Modelo.M303: ModeloApplicabilityRule(
        modelo=Modelo.M303,
        applicable_entity_types=frozenset({EntityType.NATURAL_PERSON, EntityType.LEGAL_ENTITY}),
        required_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
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
    # Modelo 200 — autoliquidación anual del Impuesto sobre Sociedades.
    # Applies, in general, to every IS contribuyente — a legal entity with
    # personalidad jurídica. It does NOT apply to a natural person, who
    # files the Renta (Modelo 100). Research §1.2.
    Modelo.M200: ModeloApplicabilityRule(
        modelo=Modelo.M200,
        applicable_entity_types=_LEGAL_ENTITY,
        required_income_categories=frozenset(),
        applicable_reason=(
            "Modelo 200 (Impuesto sobre Sociedades): una entidad jurídica "
            "con personalidad jurídica es contribuyente del IS y presenta "
            "la autoliquidación anual."
        ),
        not_applicable_reason=(
            "Modelo 200 no aplica: la autoliquidación del Impuesto sobre "
            "Sociedades corresponde únicamente a las entidades jurídicas "
            "con personalidad jurídica contribuyentes del IS. El tipo de "
            "contribuyente declarado no es una entidad de esta clase."
        ),
        # Modelo 200 is the IS cuota self-assessment: an attribution
        # entity asked about it gets the pass-through verdict — it runs
        # no IS cuota of its own.
        cuota_bearing=True,
        # LIS art. 124 — obligación de presentar la declaración del
        # Impuesto sobre Sociedades, que el Modelo 200 liquida.
        legal_refs=("ley-27-2014:art-124",),
    ),
    # Modelo 202 — pago fraccionado del Impuesto sobre Sociedades. Filed by
    # IS contribuyentes in April / October / December. A natural person
    # never files Modelo 202. Research §1.2.
    Modelo.M202: ModeloApplicabilityRule(
        modelo=Modelo.M202,
        applicable_entity_types=_LEGAL_ENTITY,
        required_income_categories=frozenset(),
        applicable_reason=(
            "Modelo 202 (pago fraccionado del IS): una entidad jurídica "
            "contribuyente del Impuesto sobre Sociedades presenta los "
            "pagos fraccionados de abril, octubre y diciembre."
        ),
        not_applicable_reason=(
            "Modelo 202 no aplica: el pago fraccionado del Impuesto sobre "
            "Sociedades solo corresponde a las entidades jurídicas."
        ),
        # Modelo 202 is an IS pago-fraccionado cuota self-assessment:
        # an attribution entity asked about it gets the pass-through
        # verdict.
        cuota_bearing=True,
        # LIS art. 40 — pago fraccionado del Impuesto sobre Sociedades,
        # las modalidades y el calendario de abril, octubre y diciembre
        # que liquida el Modelo 202.
        legal_refs=("ley-27-2014:art-40",),
    ),
    # Modelo 184 — declaración informativa anual de Entidades en
    # régimen de atribución de rentas. This is the attribution entity's
    # OWN obligation — informational, not a cuota self-assessment (the
    # substantive tax is each member's). It applies ONLY to an
    # attribution entity; a natural person and a legal entity never
    # file it. Modelo 184 is not cuota-bearing: a non-attribution
    # entity asked about it gets a plain NOT_APPLICABLE, never a
    # pass-through verdict. Corporate-entity ADR §2; research §1.3.
    Modelo.M184: ModeloApplicabilityRule(
        modelo=Modelo.M184,
        applicable_entity_types=_ATTRIBUTION_ENTITY,
        required_income_categories=frozenset(),
        applicable_reason=(
            "Modelo 184 (declaración informativa de entidades en régimen "
            "de atribución de rentas): la entidad declara las rentas "
            "obtenidas y las atribuibles a cada socio, comunero o "
            "partícipe en el ejercicio. Es la obligación propia de la "
            "entidad; la tributación de la renta corresponde a cada "
            "miembro."
        ),
        not_applicable_reason=(
            "Modelo 184 no aplica: la declaración informativa de "
            "atribución de rentas solo corresponde a las entidades en "
            "régimen de atribución de rentas (comunidades de bienes, "
            "sociedades civiles sin objeto mercantil). El tipo de "
            "contribuyente declarado no es una entidad de esta clase."
        ),
        cuota_bearing=False,
        # Orden HAP/2250/2015 arts. 1-2 — aprobación del Modelo 184 y
        # obligados a presentarlo (entidades en régimen de atribución de
        # rentas; exención por debajo de 3.000 € sin actividad
        # económica); art. 4 — plazo de presentación (mes de febrero).
        legal_refs=(
            "orden-hap-2250-2015:art-1",
            "orden-hap-2250-2015:art-2",
            "orden-hap-2250-2015:art-4",
        ),
    ),
    # Modelo 721 — declaracion informativa sobre monedas virtuales situadas
    # en el extranjero. Introduced by Ley 11/2021 DA 10a; form approved by
    # Orden HFP/887/2023. Applies to any natural person or legal entity that
    # holds virtual currencies abroad through a third-party custodian or in
    # self-custody wallets with aggregate value exceeding EUR 50,000 at 31
    # December (threshold per Orden HFP/887/2023 Art. 3). The three-axis
    # profile cannot determine whether the threshold is met; applicability is
    # reported APPLICABLE for natural persons and legal entities — the operator
    # decides whether the EUR 50,000 threshold is crossed.
    # Path-B stub: registry entry records legal authority; full casilla
    # authoring is a follow-on step (full casilla inventory not yet authored).
    Modelo.M721: ModeloApplicabilityRule(
        modelo=Modelo.M721,
        applicable_entity_types=frozenset({EntityType.NATURAL_PERSON, EntityType.LEGAL_ENTITY}),
        required_income_categories=frozenset(),
        applicable_reason=(
            "Modelo 721 (declaracion informativa sobre monedas virtuales en "
            "el extranjero): el contribuyente que posee monedas virtuales "
            "situadas en el extranjero con valor agregado superior a 50.000 "
            "EUR el 31 de diciembre esta obligado a presentar esta declaracion "
            "informativa anual. La obligacion nace con la Ley 11/2021 DA 10a "
            "y el formulario esta aprobado por Orden HFP/887/2023. Nota: la "
            "aplicacion no ha implementado aun el calculo completo del Modelo "
            "721; utilice la Sede Electronica de la AEAT para presentarlo."
        ),
        not_applicable_reason=(
            "Modelo 721 no aplica: la declaracion informativa sobre monedas "
            "virtuales en el extranjero solo corresponde a personas fisicas o "
            "entidades juridicas. El tipo de contribuyente declarado no esta "
            "incluido en el ambito subjetivo de la Ley 11/2021 DA 10a."
        ),
        cuota_bearing=False,
        # Ley 11/2021 DA 10a — obligacion de declarar monedas virtuales en el
        # extranjero; RD 1065/2007 Art. 42 quater — reglamento base de
        # declaraciones informativas de bienes y derechos en el extranjero
        # incluyendo el umbral de 50.000 EUR para monedas virtuales.
        legal_refs=(
            "ley-11-2021:da-10",
            "rd-1065-2007:art-42-quater",
        ),
    ),
    # Modelo 720 — declaración informativa sobre bienes y derechos situados
    # en el extranjero. Applies to any natural person or legal entity who
    # holds foreign assets above the declaration threshold as of 31 December
    # (Ley 7/2012 DA 1ª introducing DA 18ª Ley 58/2003 LGT; Orden
    # HAP/72/2013). The threshold is whether the aggregate value exceeds
    # the applicable limit — a payer-fact the three-axis model cannot
    # resolve alone; a profile that does not positively declare
    # ``bienes_extranjero_above_threshold = True`` yields INCOMPLETE rather
    # than a guessed NOT_APPLICABLE.
    #
    # IMPORTANT: the IRPF Art. 93 special regime (impatriados / Beckham)
    # exempts the taxpayer from Modelo 720 for the duration of the regime.
    # An impatriado is taxed as a non-resident (IRNR) and does not owe the
    # obligations reserved for IRPF residents. This exemption is enforced by
    # the pre-check in :func:`derive_modelo_applicability` before this rule
    # is evaluated.
    Modelo.M720: ModeloApplicabilityRule(
        modelo=Modelo.M720,
        applicable_entity_types=frozenset({EntityType.NATURAL_PERSON, EntityType.LEGAL_ENTITY}),
        required_payer_fact=PayerFact.BIENES_EXTRANJERO_ABOVE_THRESHOLD,
        applicable_reason=(
            "Modelo 720 (declaración informativa sobre bienes y derechos en "
            "el extranjero): el contribuyente posee bienes o derechos situados "
            "en el extranjero con valor agregado superior al umbral declarable "
            "y está obligado a presentar esta declaración informativa anual. "
            "La obligación se estableció por la Ley 7/2012 DA 1ª."
        ),
        not_applicable_reason=(
            "Modelo 720 no aplica: la declaración informativa sobre bienes en "
            "el extranjero solo corresponde a personas físicas o entidades "
            "jurídicas. El tipo de contribuyente declarado no está incluido en "
            "el ámbito subjetivo de la DA 18ª Ley 58/2003 LGT."
        ),
        cuota_bearing=False,
        # Ley 7/2012 DA 1ª — obligación de declarar bienes y derechos en el
        # extranjero (introducing DA 18ª Ley 58/2003 LGT); Orden HAP/72/2013
        # Art. 1 — aprobación del Modelo 720 y obligados a presentarlo.
        legal_refs=(
            "ley-7-2012:da-1",
            "orden-hap-72-2013:art-1",
        ),
    ),
}
"""Seed modelo-applicability rules — core persona coverage.

A modelo absent from this table has no derived rule yet: its
applicability is reported :attr:`ApplicabilityVerdict.INCOMPLETE` with
a rationale pointing at the deferred expansion. See
:data:`_SEED_COVERAGE_NOTICE`.
"""


def has_applicability_rule(modelo: str) -> bool:
    """Return whether a seed applicability rule exists for ``modelo``."""
    return modelo in _MODELO_APPLICABILITY_RULES


def iter_modelo_applicability_rules() -> tuple[ModeloApplicabilityRule, ...]:
    """Return the registry-owned seed :class:`ModeloApplicabilityRule` instances.

    The returned tuple is ordered by modelo id for deterministic audits
    and tests. Callers receive rule objects, not the mutable module-level
    dictionary, so the registry rule table remains read-only from the
    public API.
    """
    return tuple(_MODELO_APPLICABILITY_RULES[modelo] for modelo in sorted(_MODELO_APPLICABILITY_RULES))


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
    """Return the tax branch ``profile`` routes to — corporate-entity ADR §4.

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
) -> ModeloApplicability:
    """Derive a modelo's applicability from the taxpayer model.

    The verdict is DERIVED from the three-axis
    :class:`~aeat.domain.deadlines.TaxpayerProfile` model — never
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
            ``date.today()`` when ``None``. Pass an explicit date in tests
            so results are deterministic.

    Returns:
        The :class:`ModeloApplicability` for ``modelo`` and ``profile``.
    """
    _today = today if today is not None else date.today()

    # An impatriado (LIRPF Art. 93 special regime) is taxed as a non-resident
    # for the duration of the six-year Beckham window (RIRPF Art. 116.1) and
    # is therefore exempt from IRPF-resident obligations. Modelo 720 (bienes
    # en el extranjero) is one of those obligations: it applies to IRPF
    # residents, not to non-resident taxpayers under Art. 93. Enforce the
    # exemption before the rule table so the payer-fact gate is never reached.
    # Year-7+ filers whose window has expired revert to the general IRPF
    # regime and owe M720 again — the window-expiry check is wired here.
    if modelo == Modelo.M720 and profile.beckham_window_active(_today):
        return ModeloApplicability(
            modelo=Modelo.M720,
            verdict=ApplicabilityVerdict.NOT_APPLICABLE,
            reason=_IMPATRIADO_M720_EXEMPT_REASON,
            legal_refs=_IMPATRIADO_M720_LEGAL_REFS,
        )
    rule = _MODELO_APPLICABILITY_RULES.get(modelo)
    if rule is None:
        return _incomplete_applicability(modelo, unruled=True)
    return rule.evaluate(profile)


__all__ = [
    "ApplicabilityVerdict",
    "Modelo202Modality",
    "Modelo202ModalityVerdict",
    "ModeloApplicability",
    "ModeloApplicabilityRule",
    "PayerFact",
    "TaxRoute",
    "derive_modelo_202_modality",
    "derive_modelo_applicability",
    "derive_tax_route",
    "has_applicability_rule",
    "iter_modelo_applicability_rules",
    "modelo_202_modality_from_inputs",
    "taxpayer_model_is_declared",
]
