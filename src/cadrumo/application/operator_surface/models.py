"""Strict Pydantic records for the backend-owned operator-surface contract.

The records describe accepted :class:`RootSurface` values, curated
:class:`HelpDocument` / :class:`RootLandingReport` presentation documents,
mounted :class:`MountedCommandFamily` declarations, parser-only
:class:`~core.BindingSourceKind` aliases, backend :class:`ServiceOwner`
inventory, stable :class:`OperatorSurfaceLogFields`, and the aggregate
:class:`OperatorSurfaceContract` built by
:func:`~application.operator_surface.build_operator_surface_contract`.
They are data contracts only; builders and renderers live in sibling modules.

Invariant-guard classification note
------------------------------------
All :class:`ValueError` raises in this module appear inside Pydantic v2
``@field_validator`` / ``@model_validator`` methods. Pydantic wraps these into
:class:`pydantic.ValidationError` automatically; raising any other exception
type (including :class:`core.errors.CadrumoError`) would bypass that wrapping
and surface as an uncaught internal exception. These guards are therefore
**developer-surface-only invariants** and must remain :class:`ValueError`. They
are NOT operator-facing errors and do not require ``translated_message``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...core.aggregation import COUNTERPART_SOURCE_KIND_ORDER, BindingSourceKind
from ...core.identifier_grammar import NamespacedId
from ...core.logging import LogExtra
from ...core.operator_action_enums import NoRecoveryOutcome
from ..operator_actions.models import ActionReference


class RootSurfaceName(StrEnum):
    """Accepted root command surfaces enforced by :class:`OperatorSurfaceContract`."""

    CONFIG = "config"
    APP = "app"


class ModeloLifecycleStep(StrEnum):
    """Canonical modelo lifecycle steps carried by :class:`LifecycleContract`."""

    CALCULATE = "calculate"
    VERIFY = "verify"
    FILE = "file"


class FilingStatus(StrEnum):
    """Canonical live-read filing token used by mounted live command families."""

    FILED = "filed"


class OperatorMutability(StrEnum):
    """Side-effect class declared on each :class:`MountedCommandFamily`."""

    READ_ONLY = "read_only"
    LOCAL_STATE_MUTATING = "local_state_mutating"


class MountedCommandDomain(StrEnum):
    """Backend-owned command domains used to classify mounted command families."""

    FIRST_RUN = "first_run"
    PROFILE = "profile"
    CUSTODY = "custody"
    BUCKET = "bucket"
    AUTH = "auth"
    DIAGNOSTICS = "diagnostics"
    PROVISIONING = "provisioning"
    MAINTENANCE = "maintenance"
    STORAGE = "storage"
    GOOGLE = "google"
    COLLAB = "collab"
    OVERVIEW = "overview"
    LEDGER = "ledger"
    LIVE = "live"
    MODELO = "modelo"
    REVIEW = "review"
    REGISTRY = "registry"
    QUICKFILE = "quickfile"


class RootSurface(BaseModel):
    """Backend ownership record for an accepted root surface.

    Instances are declared in :data:`~application.operator_surface.ACCEPTED_ROOTS`
    and validated into the aggregate :class:`OperatorSurfaceContract`. The
    ``required_children`` field names required command-family children, not an
    exhaustive command tree.
    """

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    name: RootSurfaceName
    purpose: str = Field(min_length=1)
    owns_storage_maintenance: bool
    owns_operational_workflow: bool
    required_children: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("required_children")
    @classmethod
    def _children_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("root surface children must be unique")
        return value


class LifecycleContract(BaseModel):
    """Modelo lifecycle vocabulary and live-submission safety contract.

    The default ``internal_filed_term`` and disabled live-submission fields keep
    operator copy aligned with the accepted workflow: calculate, verify, then
    internally file/export without implying live AEAT submission.
    """

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    steps: tuple[ModeloLifecycleStep, ...]
    internal_filed_term: str = "internal filed"
    live_submission_enabled: bool = False
    live_submission_wording: str = "live submission is permanently disabled"

    @field_validator("steps")
    @classmethod
    def _steps_are_canonical(cls, value: tuple[ModeloLifecycleStep, ...]) -> tuple[ModeloLifecycleStep, ...]:
        expected = (
            ModeloLifecycleStep.CALCULATE,
            ModeloLifecycleStep.VERIFY,
            ModeloLifecycleStep.FILE,
        )
        if value != expected:
            raise ValueError("modelo lifecycle must be calculate -> verify -> file")
        return value

    @field_validator("live_submission_enabled")
    @classmethod
    def _live_submission_is_forbidden(cls, value: bool) -> bool:
        if value:
            raise ValueError("live submission must remain disabled")
        return value


class SourceKindAlias(BaseModel):
    """Input-only parser alias mapped to canonical :class:`BindingSourceKind`.

    Alias resolution is owned by
    :func:`~application.operator_surface.resolve_source_kind_alias`; no
    operator-only source-kind enum is introduced here.
    """

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    alias: str = Field(min_length=1)
    canonical: BindingSourceKind


class FamilyMountState(StrEnum):
    """Why a declared command family is, or is not, reachable in the live tree.

    A family that no live path reaches has two utterly different causes, and
    collapsing them loses the only thing worth knowing. ``MOUNTED`` asserts the
    tree reaches it. ``DECLARED_UNIMPLEMENTED`` asserts the opposite ON PURPOSE:
    the operator surface has an answer for this family, and the capability
    behind it has not been built, so the declaration is the record of an open
    gap rather than residue of a retirement.

    A family retired by an accepted ruling is neither state. It is deleted,
    because nothing is owed and nothing is pending.
    """

    MOUNTED = "mounted"
    DECLARED_UNIMPLEMENTED = "declared_unimplemented"


class MountedCommandFamily(BaseModel):
    """One accepted command-family declaration and its backend owner.

    A family declares only what the live command tree cannot supply: which
    ``root`` it hangs from, its ``child`` token, its :class:`MountedCommandDomain`,
    the ``operator_question`` it answers, its backend ``service_owner``, its
    :class:`OperatorMutability`, and its :class:`FamilyMountState`.

    It deliberately declares NO command inventory. Which verbs a family contains
    is established solely by the live command tree, projected once as the
    registered command-schema keys the manifest carries; group them with
    the live command reconciliation. A second, hand-authored
    inventory here would be a restatement of that authority, and a restatement
    is a thing that can disagree.
    """

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    domain: MountedCommandDomain
    root: RootSurfaceName
    child: str = Field(min_length=1)
    operator_question: str = Field(min_length=1)
    service_owner: str = Field(pattern=r"^cadrumo\.(application|domain|adapters|core)(\.[a-z_][a-z0-9_]*)*$")
    mutability: OperatorMutability
    mount_state: FamilyMountState = FamilyMountState.MOUNTED
    unimplemented_reason: str | None = None

    @field_validator("child")
    @classmethod
    def _child_is_kebab(cls, value: str) -> str:
        if value != value.strip().lower() or " " in value:
            raise ValueError("mounted command child must be a lower-case command token")
        return value

    @model_validator(mode="after")
    def _unimplemented_families_state_the_missing_capability(self) -> MountedCommandFamily:
        """Bind the reason to the state, in both directions.

        A ``DECLARED_UNIMPLEMENTED`` family without a reason would pass every
        membership check while telling a future reader nothing about what is
        missing, which is the failure mode a bare carve-out flag always has. A
        ``MOUNTED`` family carrying one would leave a stale gap note attached to
        a capability that has since shipped.
        """
        if self.mount_state is FamilyMountState.DECLARED_UNIMPLEMENTED:
            if self.unimplemented_reason is None or not self.unimplemented_reason.strip():
                raise ValueError("a declared-unimplemented family must state the capability it is waiting on")
        elif self.unimplemented_reason is not None:
            raise ValueError("only a declared-unimplemented family may carry an unimplemented reason")
        return self


class ManifestActionProfile(BaseModel):
    """One declarative precondition outcome exposed by the operator manifest.

    A profile is keyed to one live subject leaf, failed condition, and scenario.
    It preserves the exact condition-to-recovery association by carrying either
    one canonical :class:`~application.operator_actions.ActionReference` or one
    explicit :class:`~core.NoRecoveryOutcome`.  The
    application guard remains the authority for deciding whether the condition
    applies; this record contains no predicate, runtime evidence, argument
    value, localized prose, or CLI command string.
    """

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    subject_leaf_key: NamespacedId
    condition_id: NamespacedId
    scenario_id: NamespacedId
    action: ActionReference | None = None
    no_recovery_outcome: NoRecoveryOutcome | None = None

    @property
    def identity(self) -> tuple[str, str, str]:
        """Return the canonical live-coverage key for this declared outcome."""
        return (self.subject_leaf_key, self.condition_id, self.scenario_id)

    @model_validator(mode="after")
    def _require_action_or_explicit_no_recovery(self) -> ManifestActionProfile:
        if (self.action is None) == (self.no_recovery_outcome is None):
            raise ValueError(
                "manifest action profiles require exactly one action reference or explicit no-recovery outcome"
            )
        return self


class ServiceOwner(BaseModel):
    """Application/domain package that owns an operator-facing capability."""

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    capability: str = Field(min_length=1)
    owner: str = Field(pattern=r"^cadrumo\.(application|domain|adapters|core)(\.[a-z_][a-z0-9_]*)*$")
    notes: str = Field(min_length=1)


class OperatorSurfaceLogFields(BaseModel):
    """Stable non-secret log fields emitted by operator-surface services."""

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    contract_name: str = "operator_surface"
    root_count: int
    lifecycle: str
    source_kind_count: int

    def as_extra(self) -> LogExtra:
        """Return a typed logging ``extra`` payload with stable field names."""
        return LogExtra(
            {
                "contract_name": self.contract_name,
                "root_count": self.root_count,
                "lifecycle": self.lifecycle,
                "source_kind_count": self.source_kind_count,
            }
        )


class OperatorSurfaceContract(BaseModel):
    """Complete backend-owned contract consumed by CLI adapters.

    Built by :func:`~application.operator_surface.build_operator_surface_contract`,
    this record ties together accepted roots, modelo lifecycle vocabulary,
    canonical :class:`BindingSourceKind` subset, parser aliases, mounted command
    families, backend ownership inventory, log metadata, and registered error
    codes.
    """

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    schema_version: str = "1"
    roots: tuple[RootSurface, ...]
    lifecycle: LifecycleContract
    source_kinds: tuple[BindingSourceKind, ...]
    source_kind_aliases: tuple[SourceKindAlias, ...]
    command_families: tuple[MountedCommandFamily, ...]
    service_owners: tuple[ServiceOwner, ...]
    log_fields: OperatorSurfaceLogFields
    error_codes: tuple[str, ...]

    @field_validator("roots")
    @classmethod
    def _roots_are_exact(cls, value: tuple[RootSurface, ...]) -> tuple[RootSurface, ...]:
        names = tuple(root.name for root in value)
        expected = (RootSurfaceName.CONFIG, RootSurfaceName.APP)
        if names != expected:
            raise ValueError("operator roots must be exactly config and app")
        return value

    @field_validator("source_kinds")
    @classmethod
    def _source_kinds_are_exact(cls, value: tuple[BindingSourceKind, ...]) -> tuple[BindingSourceKind, ...]:
        if value != COUNTERPART_SOURCE_KIND_ORDER:
            raise ValueError("source kinds must match the accepted four-kind taxonomy")
        return value

    @field_validator("command_families")
    @classmethod
    def _command_families_are_unique(
        cls,
        value: tuple[MountedCommandFamily, ...],
    ) -> tuple[MountedCommandFamily, ...]:
        keys = tuple((family.root, family.child) for family in value)
        if len(set(keys)) != len(keys):
            raise ValueError("mounted command families must be unique per root and child")
        return value
