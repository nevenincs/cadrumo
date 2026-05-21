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

Three verdicts are possible:

* :attr:`ApplicabilityVerdict.APPLICABLE` — the taxpayer model
  triggers this modelo.
* :attr:`ApplicabilityVerdict.NOT_APPLICABLE` — the taxpayer model
  positively excludes this modelo (a landlord has no Modelo 130;
  an S.L. has no Modelo 100).
* :attr:`ApplicabilityVerdict.INCOMPLETE` — the taxpayer model is
  undeclared (no ``entity_type`` and, for a natural person, no income
  categories). The engine refuses to guess: it never reports a
  confident wrong obligation.

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


class ApplicabilityVerdict(StrEnum):
    """Whether a modelo applies to a taxpayer, derived from its model.

    Attributes:
        APPLICABLE: The declared taxpayer model triggers this modelo.
        NOT_APPLICABLE: The declared taxpayer model positively excludes
            this modelo (e.g. a landlord has no Modelo 130 obligation;
            a sociedad limitada files no Modelo 100).
        INCOMPLETE: The taxpayer model is not declared in enough detail
            to decide. The engine refuses to guess — the operator must
            declare their taxpayer type first.
    """

    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    INCOMPLETE = "incomplete"


class ModeloApplicability(BaseModel):
    """The derived applicability of one modelo for one taxpayer profile.

    Attributes:
        modelo: The AEAT modelo identifier.
        verdict: The :class:`ApplicabilityVerdict` derived from the
            taxpayer model.
        reason: Operator-facing prose explaining the verdict. For an
            ``INCOMPLETE`` verdict this is the "declare your taxpayer
            type first" guidance.
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
        yes. ``NOT_APPLICABLE`` and ``INCOMPLETE`` both yield ``False``
        — the operative views must not surface an obligation the engine
        cannot positively justify.
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
    legal_refs: tuple[str, ...] = Field(min_length=1)

    def evaluate(self, profile: TaxpayerProfile) -> ModeloApplicability:
        """Derive the :class:`ModeloApplicability` for ``profile``.

        Returns an ``INCOMPLETE`` verdict when the taxpayer model is not
        declared in enough detail to decide; otherwise an
        ``APPLICABLE`` / ``NOT_APPLICABLE`` verdict derived from the
        entity-type and income-category axes.
        """

        if profile.entity_type is None:
            return _incomplete_applicability(self.modelo)
        if profile.entity_type not in self.applicable_entity_types:
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

_INCOMPLETE_REASON = (
    "No se puede determinar la aplicabilidad: el tipo de contribuyente no "
    "está declarado. Declare primero el tipo de entidad y, en su caso, las "
    "categorías de renta del IRPF con 'aeat config profile edit'."
)


def _incomplete_applicability(modelo: str) -> ModeloApplicability:
    """Return the explicit ``INCOMPLETE`` applicability for ``modelo``.

    The safe default: the engine never assumes autónomo and never
    reports a confident wrong obligation when the taxpayer model is
    undeclared.
    """

    return ModeloApplicability(
        modelo=modelo,
        verdict=ApplicabilityVerdict.INCOMPLETE,
        reason=_INCOMPLETE_REASON,
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
            "Modelo 100 no aplica: solo las personas físicas presentan la "
            "Renta. Una entidad jurídica tributa por el Impuesto sobre "
            "Sociedades (Modelo 200)."
        ),
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
            "corresponde a quien obtiene rendimientos de actividades "
            "económicas. Las rentas del capital inmobiliario, del trabajo "
            "o las pensiones no generan obligación de Modelo 130."
        ),
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
            "Modelo 200 no aplica: el Impuesto sobre Sociedades solo grava "
            "a las entidades jurídicas. Una persona física tributa por el "
            "IRPF (Modelo 100)."
        ),
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
        # LIS art. 40 — pago fraccionado del Impuesto sobre Sociedades,
        # las modalidades y el calendario de abril, octubre y diciembre
        # que liquida el Modelo 202.
        legal_refs=("ley-27-2014:art-40",),
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
        return _incomplete_applicability(modelo)
    return rule.evaluate(profile)


__all__ = [
    "ApplicabilityVerdict",
    "ModeloApplicability",
    "ModeloApplicabilityRule",
    "derive_modelo_applicability",
    "has_applicability_rule",
    "taxpayer_model_is_declared",
]
