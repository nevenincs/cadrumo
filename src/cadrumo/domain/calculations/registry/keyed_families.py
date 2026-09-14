"""The canonical policy for revision declaration-family inheritance.

``SCHEMA_FAMILY`` answers a coverage question: which revision fields are
collections of typed declarations.  It deliberately does not answer the
different question of whether a successor may omit one of those declarations
and inherit it from its predecessor.  Keeping that second decision here gives
the compiler, the migration authoring tool, and the delta signal one vocabulary
for the union rule.

The table is intentionally dependency-light.  It does not import
``ModeloRevision`` (which imports the restated-family schema), so the domain
schema can import this module without a cycle.  Consumers validate the table
against their local schema-family census where they have that schema available.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

__all__ = (
    "CANONICAL_FAMILY_SPECS",
    "CASILLAS_FAMILY",
    "DROPPABLE_FAMILY_SPECS",
    "HELD_BACK_FAMILY_REASONS",
    "INHERITED_FAMILIES",
    "INHERITED_FAMILY_SPECS",
    "KEYED_FAMILY_SPECS",
    "NON_INHERITED_FAMILIES",
    "PER_EDITION_FAMILIES",
    "RESTATABLE_FAMILIES",
    "SOURCE_DEFAULT_FIELDS",
    "FamilyInheritanceMode",
    "KeyedFamilySpec",
    "family_identity_value",
    "family_spec",
    "schema_family_specs",
)


class FamilyInheritanceMode(StrEnum):
    """How a revision family participates in predecessor materialisation."""

    #: Casillas use continuity lineage rather than a member-owned id and need
    #: their own merge for locale and row-attestation handling.
    CASILLA = "casilla"
    #: A collection whose members are joined by the declared ``identity``.
    KEYED = "keyed"
    #: A declaration about the edition's own generated/evidence surface.
    PER_EDITION = "per_edition"
    #: A typed family that is intentionally full-copy for now.
    NONE = "none"


@dataclass(frozen=True, slots=True)
class KeyedFamilySpec:
    """Immutable policy for one declaration family.

    ``identity`` is retained even for a ``NONE``/``PER_EDITION`` family when
    the schema has one.  That lets diagnostics report the family accurately
    without accidentally enrolling it in the predecessor union.  The
    ``inheritance`` mode, not the presence of an id, is the enrolment decision.
    """

    section: str
    identity: str | None
    identity_fields: tuple[str, ...] = ()
    period_scoped: bool = False
    inheritance: FamilyInheritanceMode = FamilyInheritanceMode.KEYED
    #: Whether a typed ``restated_families`` declaration is meaningful.  The
    #: casilla merge is inherited but does not yet honour that manifest list.
    restatable: bool = True
    #: Whether the migration drop operation may remove an identical member.
    #: Conditional period-scoped inheritance is deliberately not droppable.
    drop_eligible: bool = False
    #: Manifest field paired with a family's shared ``source_refs`` run, when
    #: that family has one.  This does not itself enroll a family.
    source_default_key: str | None = None
    #: Reason shown when a family is intentionally not droppable/inheritable.
    holdback_reason: str | None = None
    #: Whether the family is a ``ModeloRevision`` ``SCHEMA_FAMILY`` field.
    schema_family: bool = True

    def __post_init__(self) -> None:
        """Reject an internally contradictory policy at import time."""
        if not self.section:
            raise ValueError("a family specification needs a section")
        if self.inheritance in {FamilyInheritanceMode.CASILLA, FamilyInheritanceMode.KEYED} and not self.identity:
            raise ValueError(f"inherited family {self.section!r} needs an identity")
        if self.period_scoped and self.inheritance is not FamilyInheritanceMode.KEYED:
            raise ValueError(f"only keyed families may be period-scoped: {self.section!r}")
        if self.drop_eligible and self.inheritance not in {
            FamilyInheritanceMode.CASILLA,
            FamilyInheritanceMode.KEYED,
        }:
            raise ValueError(f"only inherited families may be droppable: {self.section!r}")
        if self.restatable and self.inheritance not in {
            FamilyInheritanceMode.CASILLA,
            FamilyInheritanceMode.KEYED,
        }:
            raise ValueError(f"only inherited families may be restatable: {self.section!r}")

    @property
    def inherited(self) -> bool:
        """Whether the loader carries members from a predecessor."""
        return self.inheritance in {FamilyInheritanceMode.CASILLA, FamilyInheritanceMode.KEYED}

    @property
    def keyed(self) -> bool:
        """Whether the generic identity union, rather than casilla merge, applies."""
        return self.inheritance is FamilyInheritanceMode.KEYED


CASILLAS_FAMILY: Final[str] = "casillas"


def family_identity_value(member: object, path: str) -> object:
    """Read one identity-bearing field, including a dotted nested path.

    Authoring and compiler boundaries carry raw TOML mappings, while focused
    callers may hold typed registry models.  Resolve both shapes without
    coercing the value: identity comparisons must distinguish missing values,
    enums, and scalar values exactly as their source declared them.
    """
    current = member
    for segment in path.split("."):
        if isinstance(current, Mapping):
            current = current.get(segment)
        else:
            try:
                current = getattr(current, segment)
            except AttributeError:
                return None
        if current is None:
            return None
    return current


# The order follows the loader's materialisation order.  Keeping it stable is
# useful to diagnostics and makes the census deterministic, while the mapping
# below remains the lookup boundary for all consumers.
CANONICAL_FAMILY_SPECS: Final[tuple[KeyedFamilySpec, ...]] = (
    KeyedFamilySpec(
        section=CASILLAS_FAMILY,
        identity="continuidad_id",
        identity_fields=("id",),
        inheritance=FamilyInheritanceMode.CASILLA,
        # The casilla merge does not honour restated_families yet; the schema
        # validator retains its dedicated refusal for that declaration.
        restatable=False,
        drop_eligible=True,
        source_default_key="casilla_source_refs",
    ),
    KeyedFamilySpec(
        section="formulas",
        identity="id",
        identity_fields=("target_casilla_id",),
        source_default_key="formula_source_refs",
        drop_eligible=True,
    ),
    KeyedFamilySpec(
        section="applicability",
        identity="id",
        source_default_key="applicability_source_refs",
        drop_eligible=True,
    ),
    KeyedFamilySpec(
        section="filing_schedules",
        identity="id",
        source_default_key="filing_schedule_source_refs",
        drop_eligible=True,
    ),
    KeyedFamilySpec(
        section="live_cross_references",
        identity="id",
        source_default_key="live_cross_reference_source_refs",
        drop_eligible=True,
    ),
    KeyedFamilySpec(
        section="extraction_profiles",
        identity="id",
        source_default_key="extraction_profile_source_refs",
        drop_eligible=True,
    ),
    KeyedFamilySpec(
        section="dependency_classifications",
        identity="id",
        source_default_key="dependency_classification_source_refs",
        drop_eligible=True,
    ),
    KeyedFamilySpec(
        section="constructs",
        identity="id",
        source_default_key="construct_source_refs",
        drop_eligible=True,
    ),
    KeyedFamilySpec(
        section="application_links",
        identity="id",
        source_default_key="application_link_source_refs",
        drop_eligible=True,
    ),
    KeyedFamilySpec(
        section="parameters",
        identity="id",
        identity_fields=("data_type",),
        source_default_key="parameter_source_refs",
        drop_eligible=True,
    ),
    KeyedFamilySpec(
        section="deadline_windows",
        identity="id",
        period_scoped=True,
        holdback_reason=(
            "enrolled, but inheritance is conditional on the successor's period_selector covering the member's "
            "filing_year and period; the migration will not guess at a selector"
        ),
    ),
    # These two families are live keyed unions.  They were previously held
    # back only while their member ids were absent; their schema now supplies
    # stable ids and the identity axes below are explicit.
    KeyedFamilySpec(
        section="projection_endpoints",
        identity="id",
        drop_eligible=True,
    ),
    KeyedFamilySpec(
        section="verification_predicates",
        identity="id",
        identity_fields=("finding_kind",),
        drop_eligible=True,
    ),
    # A binding id is edition-free, but the provider and value contract carry
    # the member's semantic identity.  A successor may supersede a declaration
    # (for example, when an official record design moves a field) while a
    # change to one of these axes is an id repurpose and must be refused.
    KeyedFamilySpec(
        section="bindings",
        identity="id",
        identity_fields=("provider.kind", "value.data_type", "value.channel"),
        inheritance=FamilyInheritanceMode.KEYED,
        restatable=True,
        drop_eligible=True,
        source_default_key="binding_source_refs",
    ),
    KeyedFamilySpec(
        section="export_layouts",
        identity="id",
        inheritance=FamilyInheritanceMode.PER_EDITION,
        restatable=False,
        holdback_reason="a per-edition claim about that edition's own record design",
    ),
    KeyedFamilySpec(
        section="workbook_parity_refs",
        identity="id",
        inheritance=FamilyInheritanceMode.PER_EDITION,
        restatable=False,
        holdback_reason="a per-edition claim about that edition's own workbook",
    ),
    KeyedFamilySpec(
        section="verification_expectations",
        identity="id",
        inheritance=FamilyInheritanceMode.PER_EDITION,
        restatable=False,
        holdback_reason="a per-edition verification claim about that edition",
    ),
    # This is not a SCHEMA_FAMILY collection, but it is a deliberate
    # per-edition holdback in migration policy and belongs in the same census.
    KeyedFamilySpec(
        section="completeness_manifest",
        identity=None,
        inheritance=FamilyInheritanceMode.PER_EDITION,
        restatable=False,
        holdback_reason="a per-edition graded closure claim; it must not attest for a successor",
        schema_family=False,
    ),
)


_BY_SECTION: Final[Mapping[str, KeyedFamilySpec]] = MappingProxyType(
    {spec.section: spec for spec in CANONICAL_FAMILY_SPECS}
)

INHERITED_FAMILY_SPECS: Final[tuple[KeyedFamilySpec, ...]] = tuple(
    spec for spec in CANONICAL_FAMILY_SPECS if spec.inherited
)
KEYED_FAMILY_SPECS: Final[tuple[KeyedFamilySpec, ...]] = tuple(spec for spec in CANONICAL_FAMILY_SPECS if spec.keyed)
DROPPABLE_FAMILY_SPECS: Final[tuple[KeyedFamilySpec, ...]] = tuple(
    spec for spec in CANONICAL_FAMILY_SPECS if spec.drop_eligible
)
INHERITED_FAMILIES: Final[frozenset[str]] = frozenset(spec.section for spec in INHERITED_FAMILY_SPECS)
RESTATABLE_FAMILIES: Final[frozenset[str]] = frozenset(
    spec.section for spec in INHERITED_FAMILY_SPECS if spec.restatable
)
PER_EDITION_FAMILIES: Final[frozenset[str]] = frozenset(
    spec.section for spec in CANONICAL_FAMILY_SPECS if spec.inheritance is FamilyInheritanceMode.PER_EDITION
)
NON_INHERITED_FAMILIES: Final[frozenset[str]] = frozenset(
    spec.section for spec in CANONICAL_FAMILY_SPECS if not spec.inherited
)
HELD_BACK_FAMILY_REASONS: Final[Mapping[str, str]] = MappingProxyType(
    {spec.section: spec.holdback_reason for spec in CANONICAL_FAMILY_SPECS if spec.holdback_reason is not None}
)
SOURCE_DEFAULT_FIELDS: Final[tuple[tuple[str, str], ...]] = tuple(
    (spec.section, spec.source_default_key) for spec in CANONICAL_FAMILY_SPECS if spec.source_default_key is not None
)


def family_spec(section: str) -> KeyedFamilySpec | None:
    """Return the canonical policy for ``section``, if it is known."""
    return _BY_SECTION.get(section)


def schema_family_specs() -> tuple[KeyedFamilySpec, ...]:
    """Return canonical specs corresponding to typed ``SCHEMA_FAMILY`` fields."""
    return tuple(spec for spec in CANONICAL_FAMILY_SPECS if spec.schema_family)
