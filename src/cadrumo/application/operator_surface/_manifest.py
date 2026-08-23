"""Protocol-neutral reconciliation of declared and live command contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..operator_actions import ActionCatalogue, ActionCatalogueEntry
from ._errors import OperatorSurfaceContractError
from ._models import ManifestActionProfile, MountedCommandFamily

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


def _refuse(surface: str, diagnostics: list[str]) -> None:
    """Raise one typed refusal carrying every accumulated disagreement.

    The join accumulates rather than raising at the first disagreement. A
    reconciliation that stops at the first orphan reports one item per crash,
    so repairing it merely uncovers the next: three retired custody families
    were declared while only the first was ever named by the refusal. The
    complete census has to survive one read.
    """
    if not diagnostics:
        return
    raise OperatorSurfaceContractError(surface, reason="; ".join(diagnostics))


def _require_non_blank_inventory_text(value: str) -> str:
    """Reject whitespace-only identity, provenance, and evidence fields."""
    if not value.strip():
        raise ValueError("inventory text must not be blank")
    return value


class ReconciliationSurface(StrEnum):
    """A projection that must account for every live command identity.

    The values name data feeds, rather than implementation modules, so the
    application-owned reconciliation stays independent of entrypoint and consumer
    adapters that collect the inventory.
    """

    RESULT_SCHEMA = "result_schema"
    INPUT_SCHEMA = "input_schema"
    MOUNTED_FAMILY = "mounted_family"
    PROFILE_POLICY = "profile_policy"
    SURFACE_EXPOSURE = "surface_exposure"


class LiveLeafInventoryRow(BaseModel):
    """One callable leaf as resolved from the live command tree.

    ``subject_leaf_key`` is the stable cross-surface identity.  The canonical
    Click path is the only path used to resolve a mounted family; aliases are
    retained as alternate dispatch paths and cannot silently change a leaf's
    family ownership.
    """

    model_config = _STRICT_FROZEN

    subject_leaf_key: str = Field(min_length=1)
    canonical_cli_path: tuple[str, ...]
    alias_cli_paths: tuple[tuple[str, ...], ...] = ()
    provenance: str = Field(min_length=1)

    @field_validator("subject_leaf_key", "provenance")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        return _require_non_blank_inventory_text(value)

    @field_validator("canonical_cli_path")
    @classmethod
    def _canonical_path_has_non_blank_tokens(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not token.strip() for token in value):
            raise ValueError("CLI paths must contain non-blank tokens")
        return value

    @field_validator("alias_cli_paths")
    @classmethod
    def _aliases_are_distinct_and_non_blank(
        cls,
        value: tuple[tuple[str, ...], ...],
    ) -> tuple[tuple[str, ...], ...]:
        if len(set(value)) != len(value):
            raise ValueError("alias CLI paths must be unique")
        if any(not path or any(not token.strip() for token in path) for path in value):
            raise ValueError("CLI paths must contain non-blank tokens")
        return value

    @model_validator(mode="after")
    def _empty_path_is_only_the_root_status_callback(self) -> LiveLeafInventoryRow:
        if not self.canonical_cli_path and self.subject_leaf_key != "root.status":
            raise ValueError("an empty canonical CLI path is valid only for root.status")
        return self


class ResultSchemaInventoryRow(BaseModel):
    """One result-schema registration projected by an entrypoint adapter."""

    model_config = _STRICT_FROZEN

    subject_leaf_key: str = Field(min_length=1)
    schema_name: str = Field(min_length=1)
    provenance: str = Field(min_length=1)

    @field_validator("subject_leaf_key", "schema_name", "provenance")
    @classmethod
    def _result_schema_text_is_non_blank(cls, value: str) -> str:
        return _require_non_blank_inventory_text(value)


class InputSchemaInventoryRow(BaseModel):
    """The required-input identity projection of one S05 input schema.

    S05 remains the authority for the full parameter models.  This row carries
    the stable leaf identity and every required parameter name so this pure
    join can prove that the input-schema projection was considered without
    importing the entrypoint-owned ``VerbInputSchema`` type.
    """

    model_config = _STRICT_FROZEN

    subject_leaf_key: str = Field(min_length=1)
    required_input_names: tuple[str, ...] = ()
    provenance: str = Field(min_length=1)

    @field_validator("required_input_names")
    @classmethod
    def _required_inputs_are_unique_and_non_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("required input names must be unique")
        if any(not name.strip() for name in value):
            raise ValueError("required input names must not be blank")
        return value

    @field_validator("subject_leaf_key", "provenance")
    @classmethod
    def _input_schema_text_is_non_blank(cls, value: str) -> str:
        return _require_non_blank_inventory_text(value)


class MountedFamilyInventoryRow(BaseModel):
    """One mounted-family declaration projected from the operator contract.

    ``unimplemented_reason`` carries the contract's
    :class:`~application.operator_surface.FamilyMountState` verdict in the form
    the join needs: present means the declaration knowingly describes a family
    the tree does not reach, and says which capability is owed; absent means the
    declaration claims the tree reaches it.
    """

    model_config = _STRICT_FROZEN

    root: str = Field(min_length=1)
    child: str = Field(min_length=1)
    provenance: str = Field(min_length=1)
    unimplemented_reason: str | None = None

    @field_validator("root", "child", "provenance")
    @classmethod
    def _mounted_family_text_is_non_blank(cls, value: str) -> str:
        return _require_non_blank_inventory_text(value)

    @field_validator("unimplemented_reason")
    @classmethod
    def _unimplemented_reason_is_non_blank_when_present(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("an unimplemented reason must say which capability is missing")
        return value

    @property
    def identity(self) -> tuple[str, str]:
        """Return the stable mounted-family identity."""
        return (self.root, self.child)


class ProfilePolicyInventoryRow(BaseModel):
    """One leaf's profile-policy classification and external exposure rule."""

    model_config = _STRICT_FROZEN

    subject_leaf_key: str = Field(min_length=1)
    classification: str = Field(min_length=1)
    should_expose_externally: bool
    provenance: str = Field(min_length=1)

    @field_validator("classification", "provenance")
    @classmethod
    def _policy_text_is_non_blank(cls, value: str) -> str:
        return _require_non_blank_inventory_text(value)


class SurfaceExposureInventoryRow(BaseModel):
    """One observed operator-surface exposure decision for a stable leaf identity.

    Named for the SUBJECT, not for one consumer: the decision is whether this
    CLI leaf may be exposed on an external operator surface at all, computed
    by the command tree's protocol-neutral exposure policy.
    """

    model_config = _STRICT_FROZEN

    subject_leaf_key: str = Field(min_length=1)
    exposed: bool
    provenance: str = Field(min_length=1)

    @field_validator("provenance")
    @classmethod
    def _provenance_is_non_blank(cls, value: str) -> str:
        return _require_non_blank_inventory_text(value)


class ExplicitExclusionInventoryRow(BaseModel):
    """An intentional omission from one reconciliation projection.

    An exclusion is not a boolean convenience flag.  It names the omitted
    projection and carries both a concrete reason and the authority that made
    the decision, making every non-join reviewable at campaign closure.
    """

    model_config = _STRICT_FROZEN

    subject_leaf_key: str = Field(min_length=1)
    surface: ReconciliationSurface
    reason: str = Field(min_length=1)
    authority: str = Field(min_length=1)
    provenance: str = Field(min_length=1)

    @field_validator("reason", "authority", "provenance")
    @classmethod
    def _exclusion_text_is_non_blank(cls, value: str) -> str:
        return _require_non_blank_inventory_text(value)


class ReconciledOperatorLeaf(BaseModel):
    """The complete accounted-for projections of one live callable leaf."""

    model_config = _STRICT_FROZEN

    live_leaf: LiveLeafInventoryRow
    result_schema: ResultSchemaInventoryRow | None
    input_schema: InputSchemaInventoryRow | None
    mounted_family: MountedFamilyInventoryRow | None
    profile_policy: ProfilePolicyInventoryRow | None
    surface_exposure: SurfaceExposureInventoryRow | None
    exclusions: tuple[ExplicitExclusionInventoryRow, ...]


class OperatorSurfaceReconciliation(BaseModel):
    """An exact, application-owned join over the live operator surface."""

    model_config = _STRICT_FROZEN

    leaves: tuple[ReconciledOperatorLeaf, ...]

    def commands_for_family(self, family: MountedCommandFamily) -> tuple[str, ...]:
        """Return ``family``'s command inventory, derived from the live tree.

        Membership is read off the reconciled canonical CLI paths, which are the
        authority for what exists, rather than declared alongside them where the
        two could disagree. It is deliberately NOT derived from the schema-key
        spelling: that namespace drops the ``app`` root segment for some families
        and keeps it for others, so a prefix match would silently report an empty
        family. A family mounted as one leaf command (``config login``) yields
        the degenerate self-reference ``(child,)``, matching how the live tree
        presents it.

        Args:
            family: One declared family of the operator-surface contract.

        Returns:
            The family's command tokens, sorted, each token dotted for a nested
            subgroup (``descendiente.add``).
        """
        identity = (family.root.value, family.child)
        commands: set[str] = set()
        for leaf in self.leaves:
            path = leaf.live_leaf.canonical_cli_path
            if len(path) < 2 or (path[0], path[1]) != identity:
                continue
            commands.add(".".join(path[2:]) if len(path) > 2 else family.child)
        return tuple(sorted(commands))


class ResolvedCatalogueAction(BaseModel):
    """One canonical action joined to a live command and its schemas.

    The canonical catalogue declaration remains the action authority.  This
    record retains only resolution evidence: the exact live leaf whose stable
    subject key equals the declaration's target command key.  It introduces no
    applicability predicate, presentation text, command string, or runtime
    argument value.
    """

    model_config = _STRICT_FROZEN

    declaration: ActionCatalogueEntry
    target_leaf: ReconciledOperatorLeaf

    @model_validator(mode="after")
    def _require_exact_target_and_sufficient_sources(self) -> ResolvedCatalogueAction:
        target_key = self.declaration.target_command_key
        live_key = self.target_leaf.live_leaf.subject_leaf_key
        if live_key != target_key:
            raise ValueError(
                f"action target identity mismatch for {self.declaration.action_id}: "
                f"catalogue={target_key}, live={live_key}"
            )

        result_schema = self.target_leaf.result_schema
        if result_schema is None:
            raise ValueError(
                f"action target lacks result schema accounting: {self.declaration.action_id} -> {target_key}"
            )
        if result_schema.subject_leaf_key != target_key:
            raise ValueError(
                f"action result-schema identity mismatch for {self.declaration.action_id}: "
                f"target={target_key}, schema={result_schema.subject_leaf_key}"
            )

        input_schema = self.target_leaf.input_schema
        if input_schema is None:
            raise ValueError(
                f"action target lacks input schema accounting: {self.declaration.action_id} -> {target_key}"
            )
        if input_schema.subject_leaf_key != target_key:
            raise ValueError(
                f"action input-schema identity mismatch for {self.declaration.action_id}: "
                f"target={target_key}, schema={input_schema.subject_leaf_key}"
            )

        declared_inputs = frozenset(
            specification.argument_name for specification in self.declaration.argument_specifications
        )
        missing_inputs = tuple(
            input_name for input_name in input_schema.required_input_names if input_name not in declared_inputs
        )
        if missing_inputs:
            raise ValueError(
                f"insufficient action argument specifications for {self.declaration.action_id} -> "
                f"{target_key}; missing required inputs: {', '.join(missing_inputs)}"
            )
        return self

    @property
    def action_id(self) -> str:
        """Return the canonical catalogue identity."""
        return self.declaration.action_id

    @property
    def target_command_key(self) -> str:
        """Return the exact resolved command-schema identity."""
        return self.declaration.target_command_key


class ResolvedManifestActionProfile(BaseModel):
    """One declared condition scenario joined to its live subject and action."""

    model_config = _STRICT_FROZEN

    declaration: ManifestActionProfile
    subject_leaf: ReconciledOperatorLeaf
    resolved_action: ResolvedCatalogueAction | None = None

    @model_validator(mode="after")
    def _require_exact_profile_resolution(self) -> ResolvedManifestActionProfile:
        subject_key = self.subject_leaf.live_leaf.subject_leaf_key
        if subject_key != self.declaration.subject_leaf_key:
            raise ValueError(
                f"action-profile subject identity mismatch: "
                f"profile={self.declaration.subject_leaf_key}, live={subject_key}"
            )

        action_reference = self.declaration.action
        if action_reference is None:
            if self.resolved_action is not None:
                raise ValueError("explicit no-recovery profiles cannot carry a resolved action")
            if self.declaration.no_recovery_outcome is None:
                raise ValueError("resolved profiles require an action or explicit no-recovery outcome")
            return self

        if self.resolved_action is None:
            raise ValueError(f"action profile has no resolved action: {action_reference.action_id}")
        if self.resolved_action.action_id != action_reference.action_id:
            raise ValueError(
                f"action-profile identity mismatch: profile={action_reference.action_id}, "
                f"resolved={self.resolved_action.action_id}"
            )
        return self


class ManifestActionResolution(BaseModel):
    """Deterministic resolution evidence for catalogue actions and profiles.

    ``catalogue_actions`` is a projection of the supplied canonical catalogue,
    not a second declaration source.  It includes unreferenced catalogue entries
    so an incrementally introduced action cannot retain a dead command target.
    """

    model_config = _STRICT_FROZEN

    catalogue_actions: tuple[ResolvedCatalogueAction, ...]
    profiles: tuple[ResolvedManifestActionProfile, ...]

    @field_validator("catalogue_actions")
    @classmethod
    def _catalogue_action_ids_are_unique(
        cls,
        value: tuple[ResolvedCatalogueAction, ...],
    ) -> tuple[ResolvedCatalogueAction, ...]:
        action_ids = tuple(action.action_id for action in value)
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("resolved catalogue action IDs must be unique")
        return tuple(sorted(value, key=lambda action: action.action_id))

    @field_validator("profiles")
    @classmethod
    def _profile_identities_are_unique(
        cls,
        value: tuple[ResolvedManifestActionProfile, ...],
    ) -> tuple[ResolvedManifestActionProfile, ...]:
        identities = tuple(profile.declaration.identity for profile in value)
        if len(identities) != len(set(identities)):
            raise ValueError("manifest action-profile identities must be unique")
        return tuple(sorted(value, key=lambda profile: profile.declaration.identity))

    def action_for(self, action_id: str) -> ResolvedCatalogueAction:
        """Return one resolved canonical action or fail closed."""
        for action in self.catalogue_actions:
            if action.action_id == action_id:
                return action
        raise KeyError(f"unresolved operator action ID: {action_id!r}")


def _index_subject_rows[
    InventoryRow: ResultSchemaInventoryRow
    | InputSchemaInventoryRow
    | ProfilePolicyInventoryRow
    | SurfaceExposureInventoryRow
](
    rows: tuple[InventoryRow, ...],
    *,
    source: ReconciliationSurface,
    live_subjects: frozenset[str],
    diagnostics: list[str],
) -> dict[str, InventoryRow]:
    """Index one leaf-keyed source while recording duplicate or orphan rows."""
    indexed: dict[str, InventoryRow] = {}
    for row in rows:
        key = row.subject_leaf_key
        if key not in live_subjects:
            diagnostics.append(f"unmatched {source.value} identity: {key}")
            continue
        if key in indexed:
            diagnostics.append(f"duplicate {source.value} identity: {key}")
            continue
        indexed[key] = row
    return indexed


def _index_live_leaves(
    rows: tuple[LiveLeafInventoryRow, ...],
    *,
    diagnostics: list[str],
) -> dict[str, LiveLeafInventoryRow]:
    """Index leaves and record canonical or alias paths that resolve ambiguously."""
    indexed: dict[str, LiveLeafInventoryRow] = {}
    path_owners: dict[tuple[str, ...], str] = {}
    for row in rows:
        if row.subject_leaf_key in indexed:
            diagnostics.append(f"duplicate live leaf identity: {row.subject_leaf_key}")
            continue
        if row.canonical_cli_path in row.alias_cli_paths:
            diagnostics.append(f"canonical CLI path is also an alias: {row.subject_leaf_key}")
        for path in (row.canonical_cli_path, *row.alias_cli_paths):
            previous = path_owners.get(path)
            if previous is not None:
                diagnostics.append(f"ambiguous CLI path {' '.join(path)}: {previous} and {row.subject_leaf_key}")
                continue
            path_owners[path] = row.subject_leaf_key
        indexed[row.subject_leaf_key] = row
    if not indexed:
        # The authority itself is missing, so every downstream projection would
        # be reported orphaned against an empty denominator. Refuse here rather
        # than emit a census of false orphans.
        diagnostics.append("live leaf inventory must not be empty")
        _refuse("operator_surface_reconciliation", diagnostics)
    return indexed


def _index_families(
    rows: tuple[MountedFamilyInventoryRow, ...],
    *,
    diagnostics: list[str],
) -> dict[tuple[str, str], MountedFamilyInventoryRow]:
    """Index mounted declarations by their contract-defined root/child identity."""
    indexed: dict[tuple[str, str], MountedFamilyInventoryRow] = {}
    for row in rows:
        if row.identity in indexed:
            diagnostics.append(f"duplicate mounted family identity: {' '.join(row.identity)}")
            continue
        indexed[row.identity] = row
    return indexed


def _index_exclusions(
    rows: tuple[ExplicitExclusionInventoryRow, ...],
    *,
    live_subjects: frozenset[str],
    diagnostics: list[str],
) -> dict[tuple[str, ReconciliationSurface], ExplicitExclusionInventoryRow]:
    """Index explicit omissions while recording duplicates and orphan identities."""
    indexed: dict[tuple[str, ReconciliationSurface], ExplicitExclusionInventoryRow] = {}
    for row in rows:
        if row.subject_leaf_key not in live_subjects:
            diagnostics.append(f"unmatched exclusion identity: {row.subject_leaf_key}")
            continue
        key = (row.subject_leaf_key, row.surface)
        if key in indexed:
            diagnostics.append(f"duplicate exclusion: {row.subject_leaf_key} / {row.surface.value}")
            continue
        indexed[key] = row
    return indexed


def _require_accounting(
    *,
    subject_leaf_key: str,
    surface: ReconciliationSurface,
    row: object | None,
    exclusions: dict[tuple[str, ReconciliationSurface], ExplicitExclusionInventoryRow],
    diagnostics: list[str],
) -> object | None:
    """Require one source row or a deliberate, attributable exclusion."""
    exclusion = exclusions.get((subject_leaf_key, surface))
    if row is None:
        if exclusion is None:
            diagnostics.append(
                f"missing {surface.value} accounting for {subject_leaf_key}; explicit exclusion required"
            )
        return None
    if exclusion is not None:
        diagnostics.append(f"{surface.value} is both declared and excluded for {subject_leaf_key}")
    return row


def _reconcile_mounted_families(
    *,
    live_by_subject: dict[str, LiveLeafInventoryRow],
    family_by_identity: dict[tuple[str, str], MountedFamilyInventoryRow],
    diagnostics: list[str],
) -> None:
    """Reconcile mounted-family declarations against the live tree, both ways.

    The live command tree is the authority for a family's existence, so the
    check is symmetric: a declaration no live canonical path reaches is a dead
    manifest entry that advertises a door which is not there, and a live family
    with no declaration is a mounted subtree the capability manifest omits, so
    an adapter reads an authoritative-looking command map with a hole in it.
    Neither direction is a warning.

    A declaration that STATES it is unimplemented is the third case, and it is
    not a disagreement: the contract and the tree agree the family is not
    reachable, and the declaration exists to record which capability is owed.
    Refusing it would force a choice between deleting the record — asserting a
    retirement no ruling supports — and mounting a verb over a capability that
    does not exist. The staleness teeth are the reverse arm: once the tree DOES
    reach it, the note has outlived its gap and must be removed with the same
    change that closes it, or the surface keeps calling a shipped capability
    missing.
    """
    reached_family_identities = frozenset(
        (leaf.canonical_cli_path[0], leaf.canonical_cli_path[1])
        for leaf in live_by_subject.values()
        if len(leaf.canonical_cli_path) > 1
    )
    for identity, declaration in family_by_identity.items():
        reached = identity in reached_family_identities
        if not reached and declaration.unimplemented_reason is None:
            diagnostics.append(f"orphan mounted family declaration {' '.join(identity)} from {declaration.provenance}")
        elif reached and declaration.unimplemented_reason is not None:
            diagnostics.append(
                f"stale declared-unimplemented family {' '.join(identity)}: the live tree now reaches it, "
                f"so the recorded gap is closed and its note must go with the change that closed it "
                f"({declaration.unimplemented_reason})"
            )
    for identity in sorted(reached_family_identities - frozenset(family_by_identity)):
        diagnostics.append(f"live mounted family with no contract declaration: {' '.join(identity)}")


def _reconcile_surface_exposure(
    *,
    subject_leaf_key: str,
    profile_policy: object | None,
    surface_exposure: SurfaceExposureInventoryRow | None,
    exclusions: dict[tuple[str, ReconciliationSurface], ExplicitExclusionInventoryRow],
    diagnostics: list[str],
) -> SurfaceExposureInventoryRow | None:
    """Require attributable absence and enforce the profile exposure policy."""
    exposure_exclusion = exclusions.get((subject_leaf_key, ReconciliationSurface.SURFACE_EXPOSURE))
    if surface_exposure is None:
        if exposure_exclusion is None:
            diagnostics.append(
                f"missing surface_exposure accounting for {subject_leaf_key}; explicit exclusion required"
            )
    elif surface_exposure.exposed:
        if exposure_exclusion is not None:
            diagnostics.append(f"surface_exposure is both exposed and excluded for {subject_leaf_key}")
    elif exposure_exclusion is None:
        diagnostics.append(f"silent external-surface exclusion for {subject_leaf_key}; reason and authority required")

    if isinstance(profile_policy, ProfilePolicyInventoryRow):
        observed_exposure = surface_exposure.exposed if surface_exposure is not None else False
        if profile_policy.should_expose_externally != observed_exposure:
            diagnostics.append(
                f"external exposure contradicts profile policy for {subject_leaf_key}: "
                f"expected {profile_policy.should_expose_externally}, observed {observed_exposure}"
            )
    return surface_exposure


def _reconciled_leaf_exclusions(
    *,
    subject_leaf_key: str,
    exclusions: dict[tuple[str, ReconciliationSurface], ExplicitExclusionInventoryRow],
) -> tuple[ExplicitExclusionInventoryRow, ...]:
    """Return one leaf's exclusions in stable surface order for the public report."""
    return tuple(
        exclusion
        for (key, _), exclusion in sorted(exclusions.items(), key=lambda item: item[0][1].value)
        if key == subject_leaf_key
    )


def _reconcile_live_leaf(
    *,
    subject_leaf_key: str,
    live_leaf: LiveLeafInventoryRow,
    result_by_subject: dict[str, ResultSchemaInventoryRow],
    input_by_subject: dict[str, InputSchemaInventoryRow],
    family_by_identity: dict[tuple[str, str], MountedFamilyInventoryRow],
    policy_by_subject: dict[str, ProfilePolicyInventoryRow],
    exposure_by_subject: dict[str, SurfaceExposureInventoryRow],
    exclusions: dict[tuple[str, ReconciliationSurface], ExplicitExclusionInventoryRow],
    diagnostics: list[str],
) -> ReconciledOperatorLeaf:
    """Account for every required projection of one live command leaf."""
    result_schema = _require_accounting(
        subject_leaf_key=subject_leaf_key,
        surface=ReconciliationSurface.RESULT_SCHEMA,
        row=result_by_subject.get(subject_leaf_key),
        exclusions=exclusions,
        diagnostics=diagnostics,
    )
    input_schema = _require_accounting(
        subject_leaf_key=subject_leaf_key,
        surface=ReconciliationSurface.INPUT_SCHEMA,
        row=input_by_subject.get(subject_leaf_key),
        exclusions=exclusions,
        diagnostics=diagnostics,
    )
    profile_policy = _require_accounting(
        subject_leaf_key=subject_leaf_key,
        surface=ReconciliationSurface.PROFILE_POLICY,
        row=policy_by_subject.get(subject_leaf_key),
        exclusions=exclusions,
        diagnostics=diagnostics,
    )
    canonical_path = live_leaf.canonical_cli_path
    family_identity = (canonical_path[0], canonical_path[1]) if len(canonical_path) > 1 else None
    mounted_family = _require_accounting(
        subject_leaf_key=subject_leaf_key,
        surface=ReconciliationSurface.MOUNTED_FAMILY,
        row=family_by_identity.get(family_identity) if family_identity is not None else None,
        exclusions=exclusions,
        diagnostics=diagnostics,
    )
    surface_exposure = _reconcile_surface_exposure(
        subject_leaf_key=subject_leaf_key,
        profile_policy=profile_policy,
        surface_exposure=exposure_by_subject.get(subject_leaf_key),
        exclusions=exclusions,
        diagnostics=diagnostics,
    )
    return ReconciledOperatorLeaf(
        live_leaf=live_leaf,
        result_schema=result_schema if isinstance(result_schema, ResultSchemaInventoryRow) else None,
        input_schema=input_schema if isinstance(input_schema, InputSchemaInventoryRow) else None,
        mounted_family=mounted_family if isinstance(mounted_family, MountedFamilyInventoryRow) else None,
        profile_policy=profile_policy if isinstance(profile_policy, ProfilePolicyInventoryRow) else None,
        surface_exposure=surface_exposure,
        exclusions=_reconciled_leaf_exclusions(subject_leaf_key=subject_leaf_key, exclusions=exclusions),
    )


def reconcile_operator_surface_inventory(
    *,
    live_leaves: tuple[LiveLeafInventoryRow, ...],
    result_schemas: tuple[ResultSchemaInventoryRow, ...],
    input_schemas: tuple[InputSchemaInventoryRow, ...],
    mounted_families: tuple[MountedFamilyInventoryRow, ...],
    profile_policies: tuple[ProfilePolicyInventoryRow, ...],
    surface_exposures: tuple[SurfaceExposureInventoryRow, ...],
    exclusions: tuple[ExplicitExclusionInventoryRow, ...] = (),
) -> OperatorSurfaceReconciliation:
    """Join every live leaf to all surface projections by stable identity.

    This is intentionally a pure application function.  Click traversal, JSON
    result-schema registration, S05 parameter projection, profile policy
    discovery and external enumeration remain adapter concerns. Their typed
    rows are joined here so a missing row, orphan, duplicate, path ambiguity,
    silent omission, or policy/exposure conflict is a hard failure rather than
    a hand-maintained hint.

    Every disagreement found is accumulated and reported together through one
    :class:`~application.operator_surface.OperatorSurfaceContractError`, so the
    reader of a failed reconciliation sees the whole census rather than
    whichever item the iteration order happened to reach first.
    """
    diagnostics: list[str] = []
    live_by_subject = _index_live_leaves(live_leaves, diagnostics=diagnostics)
    live_subjects = frozenset(live_by_subject)
    result_by_subject = _index_subject_rows(
        result_schemas,
        source=ReconciliationSurface.RESULT_SCHEMA,
        live_subjects=live_subjects,
        diagnostics=diagnostics,
    )
    input_by_subject = _index_subject_rows(
        input_schemas,
        source=ReconciliationSurface.INPUT_SCHEMA,
        live_subjects=live_subjects,
        diagnostics=diagnostics,
    )
    policy_by_subject = _index_subject_rows(
        profile_policies,
        source=ReconciliationSurface.PROFILE_POLICY,
        live_subjects=live_subjects,
        diagnostics=diagnostics,
    )
    exposure_by_subject = _index_subject_rows(
        surface_exposures,
        source=ReconciliationSurface.SURFACE_EXPOSURE,
        live_subjects=live_subjects,
        diagnostics=diagnostics,
    )
    family_by_identity = _index_families(mounted_families, diagnostics=diagnostics)
    exclusions_by_subject_surface = _index_exclusions(
        exclusions,
        live_subjects=live_subjects,
        diagnostics=diagnostics,
    )
    _reconcile_mounted_families(
        live_by_subject=live_by_subject,
        family_by_identity=family_by_identity,
        diagnostics=diagnostics,
    )
    reconciled = tuple(
        _reconcile_live_leaf(
            subject_leaf_key=subject_leaf_key,
            live_leaf=live_leaf,
            result_by_subject=result_by_subject,
            input_by_subject=input_by_subject,
            family_by_identity=family_by_identity,
            policy_by_subject=policy_by_subject,
            exposure_by_subject=exposure_by_subject,
            exclusions=exclusions_by_subject_surface,
            diagnostics=diagnostics,
        )
        for subject_leaf_key, live_leaf in sorted(live_by_subject.items())
    )
    _refuse("operator_surface_reconciliation", diagnostics)
    return OperatorSurfaceReconciliation(leaves=reconciled)


def _index_reconciled_leaves(
    reconciliation: OperatorSurfaceReconciliation,
) -> dict[str, ReconciledOperatorLeaf]:
    """Index reconciled leaves while rechecking identity and path uniqueness."""
    diagnostics: list[str] = []
    indexed: dict[str, ReconciledOperatorLeaf] = {}
    path_owners: dict[tuple[str, ...], str] = {}
    for leaf in reconciliation.leaves:
        key = leaf.live_leaf.subject_leaf_key
        if key in indexed:
            diagnostics.append(f"duplicate reconciled live leaf identity: {key}")
            continue
        for path in (leaf.live_leaf.canonical_cli_path, *leaf.live_leaf.alias_cli_paths):
            previous = path_owners.get(path)
            if previous is not None:
                diagnostics.append(f"ambiguous reconciled CLI path {' '.join(path)}: {previous} and {key}")
                continue
            path_owners[path] = key
        for surface, schema_key in (
            ("result_schema", leaf.result_schema.subject_leaf_key if leaf.result_schema is not None else None),
            ("input_schema", leaf.input_schema.subject_leaf_key if leaf.input_schema is not None else None),
        ):
            if schema_key is not None and schema_key != key:
                diagnostics.append(f"reconciled {surface} identity mismatch for {key}: observed {schema_key}")
        indexed[key] = leaf
    if not indexed:
        diagnostics.append("operator-surface reconciliation must not be empty")
    _refuse("operator_surface_reconciliation", diagnostics)
    return indexed


def resolve_action_catalogue(
    *,
    catalogue: ActionCatalogue,
    reconciliation: OperatorSurfaceReconciliation,
) -> tuple[ResolvedCatalogueAction, ...]:
    """Resolve every canonical catalogue target against the live schemas.

    All catalogue entries are checked, including entries not yet referenced by
    a manifest action profile during incremental migration.  The S06 input row
    exposes the complete set of required names, so sufficiency means each of
    those names has one canonical source specification.  Additional
    specifications are retained: S06 deliberately does not claim an inventory
    of optional parameter names and this layer cannot soundly reject them.
    """
    live_by_key = _index_reconciled_leaves(reconciliation)
    diagnostics: list[str] = []
    resolved: list[ResolvedCatalogueAction] = []
    for declaration in catalogue.entries:
        target_leaf = live_by_key.get(declaration.target_command_key)
        if target_leaf is None:
            diagnostics.append(
                f"orphan action target command identity: {declaration.action_id} -> {declaration.target_command_key}"
            )
            continue
        resolved.append(
            ResolvedCatalogueAction(
                declaration=declaration,
                target_leaf=target_leaf,
            )
        )
    _refuse("operator_action_catalogue", diagnostics)
    return tuple(sorted(resolved, key=lambda action: action.action_id))


def resolve_manifest_action_profiles(
    *,
    profiles: tuple[ManifestActionProfile, ...],
    catalogue: ActionCatalogue,
    reconciliation: OperatorSurfaceReconciliation,
) -> ManifestActionResolution:
    """Resolve declarative profiles through one catalogue and live schema join."""
    live_by_key = _index_reconciled_leaves(reconciliation)
    catalogue_actions = resolve_action_catalogue(
        catalogue=catalogue,
        reconciliation=reconciliation,
    )
    action_by_id = {action.action_id: action for action in catalogue_actions}
    diagnostics: list[str] = []
    seen_profile_identities: set[tuple[str, str, str]] = set()
    resolved_profiles: list[ResolvedManifestActionProfile] = []
    for profile in profiles:
        if profile.identity in seen_profile_identities:
            diagnostics.append(
                "duplicate manifest action-profile identity: "
                f"{profile.subject_leaf_key} / {profile.condition_id} / {profile.scenario_id}"
            )
            continue
        seen_profile_identities.add(profile.identity)

        subject_leaf = live_by_key.get(profile.subject_leaf_key)
        if subject_leaf is None:
            diagnostics.append(f"orphan manifest action-profile subject identity: {profile.subject_leaf_key}")
            continue

        resolved_action: ResolvedCatalogueAction | None = None
        if profile.action is not None:
            resolved_action = action_by_id.get(profile.action.action_id)
            if resolved_action is None:
                diagnostics.append(f"unknown manifest action-profile action identity: {profile.action.action_id}")
                continue
        resolved_profiles.append(
            ResolvedManifestActionProfile(
                declaration=profile,
                subject_leaf=subject_leaf,
                resolved_action=resolved_action,
            )
        )
    _refuse("manifest_action_profiles", diagnostics)
    return ManifestActionResolution(
        catalogue_actions=catalogue_actions,
        profiles=tuple(resolved_profiles),
    )


class CommandSchemaRef(BaseModel):
    """One registered command-path to result-schema reference.

    ``command`` is a stable command-spec result identity
    (e.g. ``"modelo.calculate"``); ``schema_name`` is the authored
    :class:`~core.json_contract.OutputSchema` subclass name an adapter resolves
    to read the command's result shape.
    """

    model_config = _STRICT_FROZEN

    command: str = Field(min_length=1)
    schema_name: str = Field(min_length=1)
