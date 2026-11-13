"""Modelo 202 applicability modality gate.

The full-profile entry point reads :class:`TaxpayerProfile` entity type and
INCN facts, then delegates to the raw-input modality rule used by calculation.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, Field, StringConstraints

from ....core.decimal.grammar import try_parse_canonical_decimal
from ....core.modelo import Modelo
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.parsing.utils import parse_bool
from ...contribuyente.entity_type import EntityType
from ...deadlines.models import TaxpayerProfile
from .applicability_models import ApplicabilityVerdict, ModeloApplicability
from .entity_type import entity_type_legal_entity_token, require_entity_type
from .errors import RegistryFailureClassification, RegistryFailureCondition, RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact, ResolvedScalarFact, ScalarFactQuery
from .governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from .ids import BindingId, LegalRefId
from .runtime_graph import expression_binding_refs
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .schema import ModeloRevision

type _OperatorReason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

_MODELO_202_APPLICABILITY_FACT_ID = "modelo-202-applicability-catalogue"


class Modelo202Modality(StrEnum):
    """The pago-fraccionado modality available to a Modelo 202 filer."""

    ART_40_2_OPTIONAL = "art_40_2_optional"
    ART_40_3_MANDATORY = "art_40_3_mandatory"
    ART_40_3_MANDATORY_REGIME = "art_40_3_mandatory_regime"
    """Art. 40.3 is mandatory because the entity applies the navieras tonelaje regime.

    The stated turnover does not exceed the threshold, so unlike
    ``ART_40_3_MANDATORY`` this does not make the Modelo 202 owed in every
    instalment (Orden HFP/227/2017 art. 1.3).
    """
    INCOMPLETE = "incomplete"


class Modelo202InstalmentOutcome(StrEnum):
    """What decides one instalment's Modelo 202 filing obligation below the art. 40.3 threshold.

    Each value names its served reason in the applicability catalogue.
    """

    BASE_UNDECLARED = "filing_depends_on_ingreso"
    ELECTION_UNSTATED = "instalment_election_unstated"
    ELECTED_PENDING_CALCULATION = "instalment_elected_pending_calculation"
    ELECTED_PENDING_VERIFICATION = "instalment_elected_pending_verification"
    ELECTED_CALCULATION_POSITIVE = "instalment_elected_calculation_positive"
    ELECTED_CALCULATION_ZERO = "instalment_elected_calculation_zero"
    BASE_POSITIVE = "instalment_base_positive"
    BASE_NOT_POSITIVE = "instalment_base_not_positive"
    NO_PRIOR_RETURN = "instalment_no_prior_return"
    BASE_ABSENT = "instalment_base_absent"

    @property
    def verdict(self) -> ApplicabilityVerdict:
        """Return the filing verdict this outcome decides (Orden HFP/227/2017 art. 1.3)."""
        if self in _INSTALMENT_APPLICABLE:
            return ApplicabilityVerdict.APPLICABLE
        if self in _INSTALMENT_NOT_APPLICABLE:
            return ApplicabilityVerdict.NOT_APPLICABLE
        return ApplicabilityVerdict.INCOMPLETE


_INSTALMENT_APPLICABLE = frozenset(
    {Modelo202InstalmentOutcome.ELECTED_CALCULATION_POSITIVE, Modelo202InstalmentOutcome.BASE_POSITIVE}
)
_INSTALMENT_NOT_APPLICABLE = frozenset(
    {
        Modelo202InstalmentOutcome.ELECTED_CALCULATION_ZERO,
        Modelo202InstalmentOutcome.BASE_NOT_POSITIVE,
        Modelo202InstalmentOutcome.NO_PRIOR_RETURN,
    }
)


class Modelo202BaseBasis(StrEnum):
    """Which record supplied an instalment's art. 40.2 base; each names its served sentence."""

    LOCAL_FILING = "local_filing"
    AEAT_EVIDENCE = "aeat_evidence"
    OPERATOR_ATTESTED = "operator_attested"


class Modelo202ModalityVerdict(BaseModel):
    """The derived Modelo 202 modality verdict and its grounding."""

    model_config = STRICT_FROZEN_CONFIG

    modality: Modelo202Modality
    reason: _OperatorReason
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    failure: RegistryFailureClassification | None = None
    """Domain facts for a boundary to project when the modality is incomplete."""
    threshold_fact: ResolvedScalarFact | None = None
    """Resolved statutory threshold, including the authority provenance used."""


def _modelo_202_applicability_declarations(
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> dict[str, str]:
    """Resolve the dated Modelo 202 applicability catalogue."""
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_MODELO_202_APPLICABILITY_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        from .errors import RegistryValidationError

        raise RegistryValidationError(
            f"Modelo 202 applicability fact {_MODELO_202_APPLICABILITY_FACT_ID!r} must resolve to a mapping",
        )
    declarations = {
        entry.key: entry.value
        for entry in resolved.payload.entries
        if isinstance(entry.key, str) and isinstance(entry.value, str)
    }
    required = {
        "threshold.fact_id",
        "reason.not_applicable",
        "reason.incomplete",
        "reason.navieras_unstated",
        f"reason.{Modelo202Modality.ART_40_3_MANDATORY.value}",
        f"reason.{Modelo202Modality.ART_40_3_MANDATORY_REGIME.value}",
        f"reason.{Modelo202Modality.ART_40_2_OPTIONAL.value}",
        "legal_refs.not_applicable",
        "legal_refs.incomplete",
        "legal_refs.navieras_unstated",
        f"legal_refs.{Modelo202Modality.ART_40_3_MANDATORY.value}",
        f"legal_refs.{Modelo202Modality.ART_40_3_MANDATORY_REGIME.value}",
        f"legal_refs.{Modelo202Modality.ART_40_2_OPTIONAL.value}",
        "reason.filing_mandatory",
        "reason.filing_depends_on_ingreso",
        "legal_refs.filing_mandatory",
        "legal_refs.filing_depends_on_ingreso",
        *(f"reason.{outcome.value}" for outcome in Modelo202InstalmentOutcome),
        *(f"legal_refs.{outcome.value}" for outcome in Modelo202InstalmentOutcome),
        *(f"basis.{basis.value}" for basis in Modelo202BaseBasis),
        *(_method_section_key(art_40_3=method) for method in (False, True)),
    }
    missing = sorted(required - declarations.keys())
    if missing:
        from .errors import RegistryValidationError

        raise RegistryValidationError(
            f"Modelo 202 applicability fact {_MODELO_202_APPLICABILITY_FACT_ID!r} is missing {missing!r}",
        )
    return declarations


def _method_section_key(*, art_40_3: bool) -> str:
    return "section.art_40_3" if art_40_3 else "section.art_40_2"


def modelo_202_method_section(
    *,
    art_40_3: bool,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> str:
    """Return the form section that calculates the pago fraccionado under one LIS art. 40 method.

    The Modelo 202 instructions calculate an instalment in one section per
    method: art. 40.2 from the earlier cuota, or art. 40.3 from the base
    imponible of the months elapsed, which alone deducts the earlier
    instalments of the same periodo impositivo. The catalogue names each
    method's section token as the casillas declare it.
    """
    authority = require_governed_fact_authority(authority, subject="Modelo 202 applicability")
    declarations = _modelo_202_applicability_declarations(effective_date=effective_date, authority=authority)
    return declarations[_method_section_key(art_40_3=art_40_3)]


def _modelo_202_legal_refs(
    declarations: dict[str, str],
    outcome: str,
) -> tuple[LegalRefId, ...]:
    """Materialise the catalogue's legal-reference tuple for a verdict."""
    key = f"legal_refs.{outcome}"
    return tuple(item for item in declarations[key].split("|") if item)


def resolve_modelo_202_art_40_3_incn_threshold(
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> ResolvedScalarFact:
    """Resolve the LIS art. 40.3 INCN threshold with complete authority provenance."""
    authority = require_governed_fact_authority(authority, subject="Modelo 202 applicability")
    declarations = _modelo_202_applicability_declarations(
        effective_date=effective_date,
        authority=authority,
    )
    resolved = authority.resolve_governed_fact(
        ScalarFactQuery(
            fact_id=declarations["threshold.fact_id"],
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedScalarFact):
        raise RegistryValidationError("Modelo 202 INCN threshold must resolve as a scalar fact")
    return resolved


def modelo_202_incn_threshold_decimal(threshold: ResolvedScalarFact) -> Decimal:
    """Return the Modelo 202 INCN threshold only when the governed payload is decimal."""
    value = threshold.payload.value
    if not isinstance(value, Decimal):
        from .errors import RegistryValidationError

        raise RegistryValidationError(
            f"Modelo 202 INCN threshold fact {threshold.fact_id!r} resolved non-decimal payload {value!r}",
        )
    return value


def modelo_202_modality_from_inputs(
    *,
    entity_type: EntityType | None,
    incn_prior_12_months: Decimal | None,
    effective_date: date,
    regimen_entidades_navieras_tonelaje: bool | None = None,
    authority: GovernedFactSource | None = None,
) -> Modelo202ModalityVerdict:
    """Derive the Modelo 202 modality from the raw inputs (entity type, INCN, navieras regime).

    The Modelo 202 instructions make art. 40.3 mandatory for two cases: a
    cifra de negocios above the threshold in the twelve months before the
    período, and an entity that applies the navieras tonelaje regime. Below the
    threshold an unstated navieras regime leaves the modality incomplete, since
    assuming it away would assume the entity is not a naviera. An unstated
    turnover leaves it incomplete even for a naviera: the method is then known,
    but whether the Modelo 202 is owed in every instalment or only where an
    ingreso results (Orden HFP/227/2017 art. 1.3) turns on that turnover.

    The SINGLE modality definition, callable WITHOUT a full
    :class:`TaxpayerProfile` so the calculation engine can evaluate it off the
    wizard-free profile projection (``record_to_path_values``) in a non-CLI
    context where the wizard ``SETUP_FLOW`` catalogue is not registered. No
    fork: :func:`derive_modelo_202_modality` delegates here.

    Returns:
        :class:`Modelo202ModalityVerdict`: Derived modality, explanation, and
        legal grounding.
    """
    authority = require_governed_fact_authority(authority, subject="Modelo 202 applicability")
    declarations = _modelo_202_applicability_declarations(
        effective_date=effective_date,
        authority=authority,
    )
    if entity_type is None or entity_type != entity_type_legal_entity_token(authority=authority):
        return Modelo202ModalityVerdict(
            modality=Modelo202Modality.INCOMPLETE,
            reason=declarations["reason.not_applicable"],
            legal_refs=_modelo_202_legal_refs(declarations, "not_applicable"),
        )
    if incn_prior_12_months is None:
        return Modelo202ModalityVerdict(
            modality=Modelo202Modality.INCOMPLETE,
            reason=declarations["reason.incomplete"],
            legal_refs=_modelo_202_legal_refs(declarations, "incomplete"),
            failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.MODELO_202_INCN_DECLARED,
                facts={
                    "modelo": Modelo("202").value,
                    "incn_prior_12_months_declared": False,
                    "entity_type_legal": True,
                },
            ),
        )
    threshold_fact = resolve_modelo_202_art_40_3_incn_threshold(
        effective_date=effective_date,
        authority=authority,
    )
    if incn_prior_12_months > modelo_202_incn_threshold_decimal(threshold_fact):
        return Modelo202ModalityVerdict(
            modality=Modelo202Modality.ART_40_3_MANDATORY,
            reason=declarations[f"reason.{Modelo202Modality.ART_40_3_MANDATORY.value}"],
            legal_refs=_modelo_202_legal_refs(
                declarations,
                Modelo202Modality.ART_40_3_MANDATORY.value,
            ),
            threshold_fact=threshold_fact,
        )
    if regimen_entidades_navieras_tonelaje is True:
        return _regime_mandatory_verdict(declarations, threshold_fact=threshold_fact)
    if regimen_entidades_navieras_tonelaje is None:
        return Modelo202ModalityVerdict(
            modality=Modelo202Modality.INCOMPLETE,
            reason=declarations["reason.navieras_unstated"],
            legal_refs=_modelo_202_legal_refs(declarations, "navieras_unstated"),
            failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.MODELO_202_NAVIERAS_DECLARED,
                facts={
                    "modelo": Modelo("202").value,
                    "regimen_entidades_navieras_tonelaje_declared": False,
                    "entity_type_legal": True,
                },
            ),
            threshold_fact=threshold_fact,
        )
    return Modelo202ModalityVerdict(
        modality=Modelo202Modality.ART_40_2_OPTIONAL,
        reason=declarations[f"reason.{Modelo202Modality.ART_40_2_OPTIONAL.value}"],
        legal_refs=_modelo_202_legal_refs(declarations, Modelo202Modality.ART_40_2_OPTIONAL.value),
        threshold_fact=threshold_fact,
    )


def _regime_mandatory_verdict(
    declarations: dict[str, str],
    *,
    threshold_fact: ResolvedScalarFact,
) -> Modelo202ModalityVerdict:
    """Return art. 40.3 as mandatory for the navieras tonelaje regime."""
    modality = Modelo202Modality.ART_40_3_MANDATORY_REGIME
    return Modelo202ModalityVerdict(
        modality=modality,
        reason=declarations[f"reason.{modality.value}"],
        legal_refs=_modelo_202_legal_refs(declarations, modality.value),
        threshold_fact=threshold_fact,
    )


def derive_modelo_202_modality(
    profile: TaxpayerProfile,
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> Modelo202ModalityVerdict:
    """Derive the Modelo 202 pago-fraccionado modality and return a :class:`Modelo202ModalityVerdict`.

    Reads :class:`TaxpayerProfile` entity type and INCN, then delegates the rule
    to :func:`modelo_202_modality_from_inputs` (the single definition).
    """
    return modelo_202_modality_from_inputs(
        entity_type=profile.entity_type,
        incn_prior_12_months=profile.incn_prior_12_months,
        effective_date=effective_date,
        regimen_entidades_navieras_tonelaje=profile.regimen_entidades_navieras_tonelaje,
        authority=authority,
    )


_ENTITY_TYPE_PATH = "taxpayer_type.entity_type"
_INCN_PATH = "taxpayer_type.incn_prior_12_months"
NAVIERAS_TONELAJE_PATH = "taxpayer_type.regimen_entidades_navieras_tonelaje"


def _entity_type_from_token(raw: str | None) -> EntityType | None:
    """Map a raw ``taxpayer_type.entity_type`` token to :class:`EntityType`, or ``None``."""
    if raw is None or not raw:
        return None
    try:
        return require_entity_type(raw)
    except RegistryValidationError:
        return None


def modelo_202_modality_from_path_values(
    values: Mapping[str, str],
    *,
    filing_year: int,
    authority: GovernedFactSource,
) -> Modelo202Modality:
    """Derive the ejercicio's Modelo 202 modality from the wizard-free profile projection.

    An absent or unreadable entity type or INCN leaves the modality incomplete;
    a malformed decimal never stands for a value. An unstated or unreadable
    navieras regime is unknown, never no.
    """
    incn = values.get(_INCN_PATH)
    return modelo_202_modality_from_inputs(
        entity_type=_entity_type_from_token(values.get(_ENTITY_TYPE_PATH)),
        incn_prior_12_months=None if incn is None or not incn else try_parse_canonical_decimal(incn),
        effective_date=date(filing_year, 12, 31),
        regimen_entidades_navieras_tonelaje=parse_bool(values.get(NAVIERAS_TONELAJE_PATH)),
        authority=authority,
    ).modality


def art_40_3_method_applies(modality: Modelo202Modality, *, elected: bool | None) -> bool | None:
    """Return whether LIS art. 40.3 calculates the instalment, or ``None`` when that is not known.

    Above the threshold, or for an entity under the navieras tonelaje regime,
    art. 40.3 is mandatory; otherwise the declaración censal election decides,
    and an unstated election decides nothing.
    """
    if modality in (Modelo202Modality.ART_40_3_MANDATORY, Modelo202Modality.ART_40_3_MANDATORY_REGIME):
        return True
    if modality is Modelo202Modality.ART_40_2_OPTIONAL:
        return elected
    return None


def modelo_202_bindings_outside_method(
    revision: ModeloRevision,
    *,
    art_40_3: bool,
    filing_year: int,
    authority: GovernedFactSource,
) -> frozenset[BindingId]:
    """Return the bindings only the LIS art. 40 method not in force reads.

    Each method calculates the instalment in its own section of the form, so a
    binding counts only when at least one casilla carries it, every such
    casilla lies in the other method's section, and no formula reads it
    directly.
    """
    other_section = modelo_202_method_section(
        art_40_3=not art_40_3, effective_date=date(filing_year, 12, 31), authority=authority
    )
    formula_read = {binding for formula in revision.formulas for binding in expression_binding_refs(formula.expression)}
    sections_by_binding: dict[BindingId, list[tuple[str, ...]]] = {}
    for casilla in revision.casillas:
        if casilla.binding is not None:
            sections_by_binding.setdefault(casilla.binding, []).append(tuple(casilla.section))
    return frozenset(
        binding
        for binding, sections in sections_by_binding.items()
        if binding not in formula_read and all(other_section in section for section in sections)
    )


def modelo_202_filing_obligation(
    profile: TaxpayerProfile,
    entity_applicability: ModeloApplicability,
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> ModeloApplicability:
    """Narrow an applicable Modelo 202 entity verdict to whether filing is owed.

    LIS art. 40.1 asks every contribuyente for the pago fraccionado, but the
    Modelo 202 order (Orden HFP/227/2017 art. 1.3) makes filing unconditional
    only when the INCN of the twelve months before the período impositivo
    exceeds the art. 40.3 threshold. Below it, filing is owed only in a period
    that yields an ingreso, which depends on the art. 40.2 base (the last
    declared cuota íntegra less deductions, bonificaciones and retenciones) or
    on an art. 40.3 option elected in the declaración censal. Both are facts of
    one instalment, so this per-profile answer stays incomplete there; the
    calendar decides each instalment through
    :func:`modelo_202_instalment_applicability`. Any verdict other than
    applicable passes through unchanged.
    """
    if entity_applicability.verdict is not ApplicabilityVerdict.APPLICABLE:
        return entity_applicability
    authority = require_governed_fact_authority(authority, subject="Modelo 202 applicability")
    modality = derive_modelo_202_modality(profile, effective_date=effective_date, authority=authority)
    if modality.modality is Modelo202Modality.INCOMPLETE:
        return ModeloApplicability(
            modelo=entity_applicability.modelo,
            verdict=ApplicabilityVerdict.INCOMPLETE,
            reason=modality.reason,
            legal_refs=modality.legal_refs,
            failure=modality.failure,
        )
    declarations = _modelo_202_applicability_declarations(effective_date=effective_date, authority=authority)
    if modality.modality is Modelo202Modality.ART_40_3_MANDATORY_REGIME:
        # Art. 40.3 is forced, but filing is unconditional only above the threshold.
        return ModeloApplicability(
            modelo=entity_applicability.modelo,
            verdict=ApplicabilityVerdict.INCOMPLETE,
            reason=modality.reason,
            legal_refs=modality.legal_refs,
            provenance=entity_applicability.provenance,
        )
    if modality.modality is Modelo202Modality.ART_40_3_MANDATORY:
        return ModeloApplicability(
            modelo=entity_applicability.modelo,
            verdict=ApplicabilityVerdict.APPLICABLE,
            reason=declarations["reason.filing_mandatory"],
            legal_refs=_modelo_202_legal_refs(declarations, "filing_mandatory"),
            provenance=entity_applicability.provenance,
        )
    return ModeloApplicability(
        modelo=entity_applicability.modelo,
        verdict=ApplicabilityVerdict.INCOMPLETE,
        reason=declarations["reason.filing_depends_on_ingreso"],
        legal_refs=_modelo_202_legal_refs(declarations, "filing_depends_on_ingreso"),
        provenance=entity_applicability.provenance,
    )


def modelo_202_instalment_applicability(
    entity_applicability: ModeloApplicability,
    outcome: Modelo202InstalmentOutcome,
    *,
    basis: Modelo202BaseBasis | None,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> ModeloApplicability:
    """Return one instalment's filing verdict with the catalogue's served reason for ``outcome``.

    ``basis`` names the record that supplied the art. 40.2 base, and its served
    sentence follows the reason so the operator sees where the figure came from.
    """
    grounds = modelo_202_instalment_grounds(outcome, basis=basis, effective_date=effective_date, authority=authority)
    return ModeloApplicability(
        modelo=entity_applicability.modelo,
        verdict=outcome.verdict,
        reason=grounds.reason,
        legal_refs=grounds.legal_refs,
        provenance=entity_applicability.provenance,
    )


class Modelo202InstalmentGrounds(BaseModel):
    """The catalogue's served reason and legal references for one instalment outcome."""

    model_config = STRICT_FROZEN_CONFIG

    outcome: Modelo202InstalmentOutcome
    reason: _OperatorReason
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)


def modelo_202_instalment_grounds(
    outcome: Modelo202InstalmentOutcome,
    *,
    basis: Modelo202BaseBasis | None,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> Modelo202InstalmentGrounds:
    """Return the served reason and legal references the catalogue gives ``outcome``.

    ``basis`` names the record that supplied the art. 40.2 base; its served
    sentence follows the reason so the reader sees where the figure came from.
    """
    authority = require_governed_fact_authority(authority, subject="Modelo 202 applicability")
    declarations = _modelo_202_applicability_declarations(effective_date=effective_date, authority=authority)
    reason = declarations[f"reason.{outcome.value}"]
    if basis is not None:
        reason = f"{reason} {declarations[f'basis.{basis.value}']}"
    return Modelo202InstalmentGrounds(
        outcome=outcome,
        reason=reason,
        legal_refs=_modelo_202_legal_refs(declarations, outcome.value),
    )


__all__ = [
    "Modelo202BaseBasis",
    "Modelo202InstalmentGrounds",
    "Modelo202InstalmentOutcome",
    "Modelo202Modality",
    "Modelo202ModalityVerdict",
    "art_40_3_method_applies",
    "derive_modelo_202_modality",
    "modelo_202_bindings_outside_method",
    "modelo_202_filing_obligation",
    "modelo_202_incn_threshold_decimal",
    "modelo_202_instalment_applicability",
    "modelo_202_instalment_grounds",
    "modelo_202_method_section",
    "modelo_202_modality_from_inputs",
    "modelo_202_modality_from_path_values",
    "resolve_modelo_202_art_40_3_incn_threshold",
]
