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

Every rule carries ``legal_refs`` — scoped registry citation keys in
the ``law-slug:art-N`` form (e.g. ``ley-35-2006:art-99``) that resolve
against ``src/aeat/_data/registry/aeat/legal/*.toml`` — per
``.claude/rules/aeat-calculation-grounding.md``: applicability is
regulatory data and must be registry-grounded, and every typed-ID
reference must point at an existing registry entity. The seed table
below covers only the modelos the operator personas exercise;
per-entity / per-regime expansion to the full modelo set is
intentionally deferred, marked at :data:`_SEED_COVERAGE_NOTICE`.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ...domain.deadlines import (
    EntityType,
    IrpfIncomeCategory,
    TaxpayerProfile,
)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

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

_IS_RATE_SCHEDULE_BOUNDARY = (
    "The IS rate schedule lives in the registry, not in this module. "
    "The LIS Art. 29 tipo de gravamen and the entity-type rate dispatch "
    "are registry data on Modelo 200 (the is.modelo-200.tipo-gravamen-* "
    "parameters and the modelo-200-tipo-gravamen-por-forma-juridica "
    "formula). This module routes a profile to its tax and derives "
    "modelo applicability only; it does not encode rates or the "
    "corporate calendar. The Modelo 202 deadline windows / corporate "
    "filing calendar and the Modelo 202 modality (Art. 40.2 vs 40.3) "
    "INCN-threshold selection remain registry-data gaps."
)
"""Explicit marker for the applicability / rate-schedule boundary.

This module routes a profile to its *tax* (entity-type → IRPF / IS /
attribution pass-through) and derives modelo applicability. The IS rate
schedule and the corporate calendar are registry data, not application
logic; this constant records the boundary so no rate shell is added
here in violation of ``.claude/rules/aeat-source-hygiene.md``.
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
        entity-type and income-category axes.
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
            if (
                self.cuota_bearing
                and profile.entity_type is EntityType.ATTRIBUTION_ENTITY
            ):
                return ModeloApplicability(
                    modelo=self.modelo,
                    verdict=ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH,
                    reason=_ATTRIBUTION_PASS_THROUGH_REASON,
                    legal_refs=_ATTRIBUTION_PASS_THROUGH_LEGAL_REFS,
                )
            return ModeloApplicability(
                modelo=self.modelo,
                verdict=ApplicabilityVerdict.NOT_APPLICABLE,
                reason=self.not_applicable_reason,
                legal_refs=self.legal_refs,
            )
        # The entity type matches. A natural-person modelo that gates on
        # income category needs at least one declared category to match.
        if self.required_income_categories:
            if not profile.irpf_income_categories:
                return _incomplete_applicability(self.modelo)
            if profile.irpf_income_categories.isdisjoint(self.required_income_categories):
                return ModeloApplicability(
                    modelo=self.modelo,
                    verdict=ApplicabilityVerdict.NOT_APPLICABLE,
                    reason=self.not_applicable_reason,
                    legal_refs=self.legal_refs,
                )
        return ModeloApplicability(
            modelo=self.modelo,
            verdict=ApplicabilityVerdict.APPLICABLE,
            reason=self.applicable_reason,
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
    """

    reason = _INCOMPLETE_UNRULED_REASON if unruled else _INCOMPLETE_UNDECLARED_REASON
    return ModeloApplicability(
        modelo=modelo,
        verdict=ApplicabilityVerdict.INCOMPLETE,
        reason=reason,
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
    "100": ModeloApplicabilityRule(
        modelo="100",
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
    # Modelo 130 — pago fraccionado del IRPF, estimación directa. Triggered
    # ONLY by the rendimientos de actividades económicas income category
    # (LIRPF Arts. 27-32). A natural person whose only income is capital
    # inmobiliario (a pure landlord), trabajo, pensión, etc. has no
    # actividad económica and therefore no Modelo 130 obligation. A legal
    # entity never files Modelo 130.
    "130": ModeloApplicabilityRule(
        modelo="130",
        applicable_entity_types=_NATURAL_PERSON,
        required_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        applicable_reason=(
            "Modelo 130 (pago fraccionado del IRPF): la persona física "
            "declara rendimientos de actividades económicas, que generan "
            "la obligación del pago fraccionado en estimación directa."
        ),
        not_applicable_reason=(
            "Modelo 130 no aplica: el pago fraccionado del IRPF solo "
            "corresponde a la persona física que obtiene rendimientos de "
            "actividades económicas. El tipo de contribuyente declarado no "
            "obtiene rendimientos de actividades económicas."
        ),
        # Modelo 130 is an IRPF pago-fraccionado cuota self-assessment:
        # an attribution entity asked about it gets the pass-through
        # verdict — it runs no IRPF cuota of its own.
        cuota_bearing=True,
        # LIRPF art. 27 — definición de los rendimientos de actividades
        # económicas, la categoría de renta que dispara el Modelo 130;
        # art. 99 — pagos fraccionados como pagos a cuenta del IRPF.
        legal_refs=("ley-35-2006:art-27", "ley-35-2006:art-99"),
    ),
    # Modelo 303 — autoliquidación periódica del IVA. Triggered by carrying
    # on an actividad económica subject to IVA: a natural person with
    # rendimientos de actividades económicas, or a legal entity. A pure
    # landlord of residential property, a salaried-only taxpayer, and a
    # pensioner carry on no IVA-subject activity. (Commercial rental can be
    # IVA-subject; the seed gates on the actividad-económica category,
    # which a pure landlord does not declare. Finer rental-IVA nuance is
    # a deferred expansion.)
    "303": ModeloApplicabilityRule(
        modelo="303",
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
    "200": ModeloApplicabilityRule(
        modelo="200",
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
    "202": ModeloApplicabilityRule(
        modelo="202",
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
    "184": ModeloApplicabilityRule(
        modelo="184",
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


def taxpayer_model_is_declared(profile: TaxpayerProfile) -> bool:
    """Return whether the profile carries a usable taxpayer model.

    The taxpayer model is "declared" when the operator has set an
    ``entity_type`` and — for a natural person — at least one IRPF
    income category. Without these, modelo applicability cannot be
    derived: the engine must report ``INCOMPLETE`` rather than assume
    autónomo. A legal / attribution entity needs no income category;
    the ``entity_type`` alone selects its tax.
    """

    if profile.entity_type is None:
        return False
    if profile.entity_type is EntityType.NATURAL_PERSON:
        return bool(profile.irpf_income_categories)
    return True


class TaxRoute(StrEnum):
    """The tax branch a taxpayer profile routes to — corporate-entity ADR §4.

    The ``entity_type`` axis selects the *tax*, and the tax selects the
    modelos, the calendar, and the calculation chain. There are exactly
    three substantive branches plus an explicit "cannot route" state.

    Attributes:
        IRPF: A natural person — routes to the IRPF path (Modelo
            100 / 130 / 303, the IRPF tarifa).
        IMPUESTO_SOCIEDADES: A legal entity — routes to the Impuesto
            sobre Sociedades path (Modelo 200 / 202, the LIS Art. 29
            rate scale). The engine never runs an IRPF cuota for it.
        ATTRIBUTION_PASS_THROUGH: An attribution entity — runs no IS
            and no IRPF cuota of its own; the income is taxed in the
            members' returns. Its own obligation is the informational
            Modelo 184.
        INCOMPLETE: The ``entity_type`` is undeclared. The engine
            refuses to guess and never defaults to a tax — a wrong tax
            is worse than an incomplete answer (corporate-entity ADR
            §4, parent ADR's safe default).
    """

    IRPF = "irpf"
    IMPUESTO_SOCIEDADES = "impuesto_sociedades"
    ATTRIBUTION_PASS_THROUGH = "attribution_pass_through"
    INCOMPLETE = "incomplete"


_TAX_ROUTE_FOR_ENTITY_TYPE: dict[EntityType, TaxRoute] = {
    EntityType.NATURAL_PERSON: TaxRoute.IRPF,
    EntityType.LEGAL_ENTITY: TaxRoute.IMPUESTO_SOCIEDADES,
    EntityType.ATTRIBUTION_ENTITY: TaxRoute.ATTRIBUTION_PASS_THROUGH,
}
"""The entity-type → tax-route table (corporate-entity ADR §4).

A closed mapping over every :class:`EntityType`. ``entity_type is
None`` (undeclared) is handled separately by :func:`derive_tax_route`
and yields :attr:`TaxRoute.INCOMPLETE` — the engine never defaults a
tax.
"""


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
        profile: The operator's three-axis taxpayer model.

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

    Returns:
        The :class:`ModeloApplicability` for ``modelo`` and ``profile``.
    """

    rule = _MODELO_APPLICABILITY_RULES.get(modelo)
    if rule is None:
        return _incomplete_applicability(modelo, unruled=True)
    return rule.evaluate(profile)


__all__ = [
    "ApplicabilityVerdict",
    "ModeloApplicability",
    "ModeloApplicabilityRule",
    "TaxRoute",
    "derive_modelo_applicability",
    "derive_tax_route",
    "has_applicability_rule",
    "taxpayer_model_is_declared",
]
