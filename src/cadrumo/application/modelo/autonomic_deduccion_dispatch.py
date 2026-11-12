"""The shared dispatch of the autonomic deducciones a Modelo 100 edition enrols.

A comunidad deducción reaches a calculated return only through its enrolment on the
formula of its box (:mod:`~domain.calculations.registry.autonomic_deduccion_enrolment`).
This module reads every enrolment the selected edition carries and supplies each one's
count binding from the profile, one rule for all of them:

- A filer resident in another comunidad gets zero: the box is not theirs.
- A resident gets the weighted count the enrolment's axis primitive reads from the
  stated household. Facts that rule the deducción out give a proven zero.
- A resident whose stated facts leave the count open gets no count at all. The path is
  withheld, the consuming binding is reported unresolved, and the notes name the
  missing facts by row, which is what stops checking, local filing and export and
  sends the filer to the door that states them.

A count path the profile schema declares derived is the engine's alone: a stored
value there can only be stale or hand-planted and is replaced. A count path the
schema leaves as an ordinary field keeps its earlier contract: the dispatch supplies
zero where nothing is stored and overwrites only with a positive count.

An axis whose deciding fact no door can yet state keeps its earlier behaviour. The
descendant window axis under a unidad familiar income limit is one: no stored fact
holds the other members' base, so an indeterminate unit resolves to zero and the
verification advisory names the possible entitlement instead.

A filer whose comunidad of residence has no enrolment in the edition, or who states
none, is told so in one non-blocking note: the regional deducciones are not computed
and can be entered by hand. Leaving a deducción out can only raise the tax.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from ...core.aggregation import BindingSourceKind
from ...domain.calculations.registry.autonomic_deduccion_enrolment import (
    AUTONOMIC_DEDUCCION_SECTION,
    AscendantMinimumEntitlementAxis,
    AutonomicDeduccionEnrolment,
    AutonomicIncomeLimit,
    AutonomicIncomeUnit,
    DescendantEntryWindowAxis,
)
from ...domain.calculations.registry.autonomic_deduccion_enrolment_checks import autonomic_deduccion_enrolments
from ...domain.calculations.registry.formula_runtime_ops import resolve_parameter
from ...domain.contribuyente.descendant_facts import descendant_list_from_facts
from ...domain.contribuyente.renta_codes import RentaDeclaracionType
from ...domain.user_profile.registry_contract import profile_binding_selectors
from ...domain.user_profile.schema import derived_selector_for_path
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from .profile_derived_facts import partnered_status_codes, snapshot_authored_year
from .profile_minimo_ascendientes import ascendant_entitlement_count

if TYPE_CHECKING:
    from ...domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
    from ...domain.contribuyente.family_fact_context import FamilyFactResolutionContext
    from ...domain.user_profile.schema import ProfileSchemaDefinition
    from ...domain.user_profile.values import UserProfileFactValue

__all__ = [
    "AUTONOMIC_DEDUCCIONES_NOT_ENROLLED_REASON",
    "AutonomicDeduccionDerivation",
    "descendant_entry_window_weighted_count",
    "enrolment_count_path",
    "inject_autonomic_deduccion_facts",
    "is_indeterminate_unidad_familiar",
    "residence_ccaa",
]

AUTONOMIC_DEDUCCIONES_NOT_ENROLLED_REASON: Final = "autonomic_deducciones_not_enrolled"

_TAX_RESIDENCE_CCAA_KEY: Final = "tax_residence.ccaa"


@dataclass(frozen=True, slots=True)
class AutonomicDeduccionDerivation:
    """The count paths the dispatch decided, those it withheld, and the notes it serves."""

    decided_paths: frozenset[str] = frozenset()
    withheld_paths: frozenset[str] = frozenset()
    diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()


def residence_ccaa(fact_index: Mapping[str, UserProfileFactValue]) -> str | None:
    """The comunidad token the profile states as residence, or ``None`` when it states none."""
    raw = fact_index.get(_TAX_RESIDENCE_CCAA_KEY)
    if not isinstance(raw, str):
        return None
    token = raw.strip().lower()
    return token or None


def is_indeterminate_unidad_familiar(fact_index: Mapping[str, UserProfileFactValue]) -> bool:
    """Whether the filer's unit is a joint return or a partnered filer.

    For such a unit a unidad familiar income limit needs the other members' base
    imponible, which no stored fact holds.
    """
    declaration_type = str(fact_index.get("renta_filing.declaration_type", "")).strip()
    if declaration_type == RentaDeclaracionType.JOINT.code:
        return True
    marital_status = str(fact_index.get("renta_taxpayer.marital_status", "")).strip().lower()
    return marital_status in partnered_status_codes()


def descendant_entry_window_weighted_count(
    fact_index: Mapping[str, UserProfileFactValue],
    filing_year: int,
    *,
    following_periods: int,
    context: FamilyFactResolutionContext,
) -> Decimal:
    """The cohabiting descendants inside their entry window, each by its equal-parts share."""
    descendant_facts = {
        key: str(value) for key, value in fact_index.items() if key.startswith("renta_family.descendiente.")
    }
    weighted_count = Decimal("0")
    for descendant in descendant_list_from_facts(descendant_facts):
        if descendant.is_within_entry_window(filing_year, following_periods=following_periods):
            weighted_count += descendant.nacimiento_adopcion_prorrateo_share(context=context)
    return weighted_count


def _profile_path(revision: ModeloRevision, binding_id: str) -> str:
    # Registry hydration refuses an enrolment whose binding is absent, not a profile
    # binding, or reads other than one profile path, so the lookup and unpacking hold.
    binding = next(binding for binding in revision.bindings if binding.id == binding_id)
    (path,) = profile_binding_selectors(binding.provider)
    return path


def enrolment_count_path(revision: ModeloRevision, enrolment: AutonomicDeduccionEnrolment) -> str:
    """The profile path the enrolment's count binding reads."""
    return _profile_path(revision, enrolment.count_binding)


def _integer_parameter(snapshot: RegistrySnapshot, parameter_id: str) -> int:
    # Registry hydration refuses an axis parameter that is undeclared or has a dated
    # value that is not a whole number, so the lookup holds and the conversion is exact.
    parameter = next(parameter for parameter in snapshot.revision.parameters if parameter.id == parameter_id)
    # A projected year reuses the authored edition's dated values, as the amounts do.
    return int(resolve_parameter(parameter, {"filing_period": date(snapshot_authored_year(snapshot), 12, 31)}))


def _not_enrolled_note(ccaa: str | None, *, bucket_id: str) -> CalculationSourceDiagnostic:
    stated = ccaa if ccaa is not None else "unstated"
    return CalculationSourceDiagnostic(
        reason=AUTONOMIC_DEDUCCIONES_NOT_ENROLLED_REASON,
        source_kind=BindingSourceKind.PROFILE.value,
        binding_source=BindingSourceKind.PROFILE,
        message=(
            f"the edition enrols no autonomic deducción for the comunidad of residence ({stated}); "
            "its regional deducciones are not computed and can be entered by hand"
        ),
        resolver_id="profile",
        source_ref=f"profile:{bucket_id}:{_TAX_RESIDENCE_CCAA_KEY}",
    )


@dataclass(slots=True)
class _Dispatch:
    fact_index: dict[str, UserProfileFactValue]
    snapshot: RegistrySnapshot
    schema: ProfileSchemaDefinition
    context: FamilyFactResolutionContext
    bucket_id: str
    decided: set[str]
    withheld: set[str]
    diagnostics: list[CalculationSourceDiagnostic]

    def apply(self, enrolment: AutonomicDeduccionEnrolment, ccaa: str | None) -> None:
        revision = self.snapshot.revision
        path = enrolment_count_path(revision, enrolment)
        limit = enrolment.income_limit
        if isinstance(limit, AutonomicIncomeLimit) and limit.other_members_base_binding is not None:
            # No stored fact holds the other members' base; the formula reads zero beside the unit guard.
            self.fact_index.setdefault(_profile_path(revision, limit.other_members_base_binding), Decimal("0"))
        derived = derived_selector_for_path(path, self.schema.derived_selectors) is not None
        if derived:
            self.fact_index.pop(path, None)
            self.decided.add(path)
        else:
            self.fact_index.setdefault(path, Decimal("0"))
        if ccaa != enrolment.ccaa:
            if derived:
                self.fact_index[path] = Decimal("0")
            return
        count = self._count(enrolment)
        if count is None:
            self.withheld.add(path)
        elif derived or count > 0:
            self.fact_index[path] = count

    def _count(self, enrolment: AutonomicDeduccionEnrolment) -> Decimal | None:
        eligibility = enrolment.eligibility
        if isinstance(eligibility, DescendantEntryWindowAxis):
            limit = enrolment.income_limit
            unit_bound = isinstance(limit, AutonomicIncomeLimit) and limit.unit is AutonomicIncomeUnit.UNIDAD_FAMILIAR
            if unit_bound and is_indeterminate_unidad_familiar(self.fact_index):
                return Decimal("0")
            return descendant_entry_window_weighted_count(
                self.fact_index,
                self.snapshot.filing_year,
                following_periods=self.context.integer(eligibility.following_periods_fact),
                context=self.context,
            )
        if isinstance(eligibility, AscendantMinimumEntitlementAxis):
            entitlement = ascendant_entitlement_count(
                self.fact_index,
                self.snapshot,
                qualifying_age=_integer_parameter(self.snapshot, eligibility.minimum_age),
                qualifying_discapacidad_grado=_integer_parameter(self.snapshot, eligibility.minimum_discapacidad_grado),
                context=self.context,
                bucket_id=self.bucket_id,
            )
            self.diagnostics.extend(note for note in entitlement.diagnostics if note not in self.diagnostics)
            return entitlement.count
        raise AssertionError(f"unhandled eligibility axis {eligibility!r}")


def _declares_autonomic_deducciones(revision: ModeloRevision) -> bool:
    return any(AUTONOMIC_DEDUCCION_SECTION in casilla.section for casilla in revision.casillas)


def inject_autonomic_deduccion_facts(
    fact_index: dict[str, UserProfileFactValue],
    snapshot: RegistrySnapshot,
    *,
    schema: ProfileSchemaDefinition,
    context: FamilyFactResolutionContext,
    bucket_id: str,
) -> AutonomicDeduccionDerivation:
    """Supply the count of every enrolled deducción, withhold the open ones, and serve the limitation.

    ``schema`` says which count paths are derived. An edition with no autonomic
    deducción boxes gets nothing from this dispatch.
    """
    revision = snapshot.revision
    if not _declares_autonomic_deducciones(revision):
        return AutonomicDeduccionDerivation()
    ccaa = residence_ccaa(fact_index)
    dispatch = _Dispatch(fact_index, snapshot, schema, context, bucket_id, set(), set(), [])
    enrolments = [enrolment for _formula, enrolment in autonomic_deduccion_enrolments(revision)]
    for enrolment in enrolments:
        dispatch.apply(enrolment, ccaa)
    if ccaa is None or all(enrolment.ccaa != ccaa for enrolment in enrolments):
        dispatch.diagnostics.append(_not_enrolled_note(ccaa, bucket_id=bucket_id))
    return AutonomicDeduccionDerivation(
        decided_paths=frozenset(dispatch.decided),
        withheld_paths=frozenset(dispatch.withheld),
        diagnostics=tuple(dispatch.diagnostics),
    )
