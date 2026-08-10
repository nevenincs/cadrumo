"""Operator-surface manifest: the agent-facing capability catalogue.

Projects the backend-owned :class:`OperatorSurfaceContract` together with the
CLI's registered JSON command-result schema keys into a single machine-readable
:class:`OperatorSurfaceManifest`. This is the capability catalogue an LLM
operator reads to learn the two-root command tree, each command family's intent
and :class:`~application.operator_surface.OperatorMutability`, the modelo
``CALCULATE -> VERIFY -> FILE`` lifecycle, and the per-command result-schema
reference. It is also the natural source a tool-exposure server consumes for its
tool list.

The contract half is owned here in the application layer. The
``command_schemas`` half is the CLI's own ``--json`` result-schema registry, an
entrypoint-layer concern; the CLI adapter enumerates it and injects it into
:func:`build_operator_surface_manifest`, so this module never imports the CLI
schema registry and the hexagonal direction is preserved.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ._contract import get_operator_surface_contract
from ._models import OperatorSurfaceContract

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


def _require_non_blank_inventory_text(value: str) -> str:
    """Reject whitespace-only identity, provenance, and evidence fields."""
    if not value.strip():
        raise ValueError("inventory text must not be blank")
    return value


class ReconciliationSurface(StrEnum):
    """A projection that must account for every live command identity.

    The values name data feeds, rather than implementation modules, so the
    application-owned reconciliation stays independent of the Click and MCP
    adapters that collect the inventory.
    """

    RESULT_SCHEMA = "result_schema"
    INPUT_SCHEMA = "input_schema"
    MOUNTED_FAMILY = "mounted_family"
    PROFILE_POLICY = "profile_policy"
    MCP_EXPOSURE = "mcp_exposure"


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
    """One mounted-family declaration projected from the operator contract."""

    model_config = _STRICT_FROZEN

    root: str = Field(min_length=1)
    child: str = Field(min_length=1)
    provenance: str = Field(min_length=1)

    @field_validator("root", "child", "provenance")
    @classmethod
    def _mounted_family_text_is_non_blank(cls, value: str) -> str:
        return _require_non_blank_inventory_text(value)

    @property
    def identity(self) -> tuple[str, str]:
        """Return the stable mounted-family identity."""
        return (self.root, self.child)


class ProfilePolicyInventoryRow(BaseModel):
    """One leaf's profile-policy classification and required MCP exposure."""

    model_config = _STRICT_FROZEN

    subject_leaf_key: str = Field(min_length=1)
    classification: str = Field(min_length=1)
    should_expose_via_mcp: bool
    provenance: str = Field(min_length=1)

    @field_validator("classification", "provenance")
    @classmethod
    def _policy_text_is_non_blank(cls, value: str) -> str:
        return _require_non_blank_inventory_text(value)


class McpExposureInventoryRow(BaseModel):
    """One observed MCP-exposure decision for a stable leaf identity."""

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
    mcp_exposure: McpExposureInventoryRow | None
    exclusions: tuple[ExplicitExclusionInventoryRow, ...]


class OperatorSurfaceReconciliation(BaseModel):
    """An exact, application-owned join over the live operator surface."""

    model_config = _STRICT_FROZEN

    leaves: tuple[ReconciledOperatorLeaf, ...]


def _index_subject_rows[
    InventoryRow: ResultSchemaInventoryRow
    | InputSchemaInventoryRow
    | ProfilePolicyInventoryRow
    | McpExposureInventoryRow
](
    rows: tuple[InventoryRow, ...],
    *,
    source: ReconciliationSurface,
    live_subjects: frozenset[str],
) -> dict[str, InventoryRow]:
    """Index one leaf-keyed source while refusing duplicate or orphan rows."""
    indexed: dict[str, InventoryRow] = {}
    for row in rows:
        key = row.subject_leaf_key
        if key not in live_subjects:
            raise ValueError(f"unmatched {source.value} identity: {key}")
        if key in indexed:
            raise ValueError(f"duplicate {source.value} identity: {key}")
        indexed[key] = row
    return indexed


def _index_live_leaves(rows: tuple[LiveLeafInventoryRow, ...]) -> dict[str, LiveLeafInventoryRow]:
    """Index leaves and ensure canonical and alias paths resolve unambiguously."""
    indexed: dict[str, LiveLeafInventoryRow] = {}
    path_owners: dict[tuple[str, ...], str] = {}
    for row in rows:
        if row.subject_leaf_key in indexed:
            raise ValueError(f"duplicate live leaf identity: {row.subject_leaf_key}")
        if row.canonical_cli_path in row.alias_cli_paths:
            raise ValueError(f"canonical CLI path is also an alias: {row.subject_leaf_key}")
        for path in (row.canonical_cli_path, *row.alias_cli_paths):
            previous = path_owners.get(path)
            if previous is not None:
                raise ValueError(
                    f"ambiguous CLI path {' '.join(path)}: {previous} and {row.subject_leaf_key}"
                )
            path_owners[path] = row.subject_leaf_key
        indexed[row.subject_leaf_key] = row
    if not indexed:
        raise ValueError("live leaf inventory must not be empty")
    return indexed


def _index_families(rows: tuple[MountedFamilyInventoryRow, ...]) -> dict[tuple[str, str], MountedFamilyInventoryRow]:
    """Index mounted declarations by their contract-defined root/child identity."""
    indexed: dict[tuple[str, str], MountedFamilyInventoryRow] = {}
    for row in rows:
        if row.identity in indexed:
            raise ValueError(f"duplicate mounted family identity: {' '.join(row.identity)}")
        indexed[row.identity] = row
    return indexed


def _index_exclusions(
    rows: tuple[ExplicitExclusionInventoryRow, ...],
    *,
    live_subjects: frozenset[str],
) -> dict[tuple[str, ReconciliationSurface], ExplicitExclusionInventoryRow]:
    """Index explicit omissions while rejecting duplicates and orphan identities."""
    indexed: dict[tuple[str, ReconciliationSurface], ExplicitExclusionInventoryRow] = {}
    for row in rows:
        if row.subject_leaf_key not in live_subjects:
            raise ValueError(f"unmatched exclusion identity: {row.subject_leaf_key}")
        key = (row.subject_leaf_key, row.surface)
        if key in indexed:
            raise ValueError(f"duplicate exclusion: {row.subject_leaf_key} / {row.surface.value}")
        indexed[key] = row
    return indexed


def _require_accounting(
    *,
    subject_leaf_key: str,
    surface: ReconciliationSurface,
    row: object | None,
    exclusions: dict[tuple[str, ReconciliationSurface], ExplicitExclusionInventoryRow],
) -> object | None:
    """Require one source row or a deliberate, attributable exclusion."""
    exclusion = exclusions.get((subject_leaf_key, surface))
    if row is None:
        if exclusion is None:
            raise ValueError(f"missing {surface.value} accounting for {subject_leaf_key}; explicit exclusion required")
        return None
    if exclusion is not None:
        raise ValueError(f"{surface.value} is both declared and excluded for {subject_leaf_key}")
    return row


def reconcile_operator_surface_inventory(
    *,
    live_leaves: tuple[LiveLeafInventoryRow, ...],
    result_schemas: tuple[ResultSchemaInventoryRow, ...],
    input_schemas: tuple[InputSchemaInventoryRow, ...],
    mounted_families: tuple[MountedFamilyInventoryRow, ...],
    profile_policies: tuple[ProfilePolicyInventoryRow, ...],
    mcp_exposures: tuple[McpExposureInventoryRow, ...],
    exclusions: tuple[ExplicitExclusionInventoryRow, ...] = (),
) -> OperatorSurfaceReconciliation:
    """Join every live leaf to all surface projections by stable identity.

    This is intentionally a pure application function.  Click traversal, JSON
    result-schema registration, S05 parameter projection, profile policy
    discovery, and MCP tool enumeration remain adapter concerns.  Their typed
    rows are joined here so a missing row, orphan, duplicate, path ambiguity,
    silent omission, or policy/exposure conflict is a hard failure rather than
    a hand-maintained hint.
    """
    live_by_subject = _index_live_leaves(live_leaves)
    live_subjects = frozenset(live_by_subject)
    result_by_subject = _index_subject_rows(
        result_schemas,
        source=ReconciliationSurface.RESULT_SCHEMA,
        live_subjects=live_subjects,
    )
    input_by_subject = _index_subject_rows(
        input_schemas,
        source=ReconciliationSurface.INPUT_SCHEMA,
        live_subjects=live_subjects,
    )
    policy_by_subject = _index_subject_rows(
        profile_policies,
        source=ReconciliationSurface.PROFILE_POLICY,
        live_subjects=live_subjects,
    )
    mcp_by_subject = _index_subject_rows(
        mcp_exposures,
        source=ReconciliationSurface.MCP_EXPOSURE,
        live_subjects=live_subjects,
    )
    family_by_identity = _index_families(mounted_families)
    exclusions_by_subject_surface = _index_exclusions(exclusions, live_subjects=live_subjects)
    reached_family_identities = frozenset(
        (leaf.canonical_cli_path[0], leaf.canonical_cli_path[1])
        for leaf in live_by_subject.values()
        if len(leaf.canonical_cli_path) > 1
    )
    for identity, declaration in family_by_identity.items():
        if identity not in reached_family_identities:
            raise ValueError(
                f"orphan mounted family declaration {' '.join(identity)} from {declaration.provenance}"
            )

    reconciled: list[ReconciledOperatorLeaf] = []
    for subject_leaf_key, live_leaf in sorted(live_by_subject.items()):
        result_schema = _require_accounting(
            subject_leaf_key=subject_leaf_key,
            surface=ReconciliationSurface.RESULT_SCHEMA,
            row=result_by_subject.get(subject_leaf_key),
            exclusions=exclusions_by_subject_surface,
        )
        input_schema = _require_accounting(
            subject_leaf_key=subject_leaf_key,
            surface=ReconciliationSurface.INPUT_SCHEMA,
            row=input_by_subject.get(subject_leaf_key),
            exclusions=exclusions_by_subject_surface,
        )
        policy = _require_accounting(
            subject_leaf_key=subject_leaf_key,
            surface=ReconciliationSurface.PROFILE_POLICY,
            row=policy_by_subject.get(subject_leaf_key),
            exclusions=exclusions_by_subject_surface,
        )

        canonical_path = live_leaf.canonical_cli_path
        family_identity = (canonical_path[0], canonical_path[1]) if len(canonical_path) > 1 else None
        mounted_family = _require_accounting(
            subject_leaf_key=subject_leaf_key,
            surface=ReconciliationSurface.MOUNTED_FAMILY,
            row=family_by_identity.get(family_identity) if family_identity is not None else None,
            exclusions=exclusions_by_subject_surface,
        )

        mcp_exposure = mcp_by_subject.get(subject_leaf_key)
        mcp_exclusion = exclusions_by_subject_surface.get((subject_leaf_key, ReconciliationSurface.MCP_EXPOSURE))
        if mcp_exposure is None:
            if mcp_exclusion is None:
                raise ValueError(
                    f"missing mcp_exposure accounting for {subject_leaf_key}; explicit exclusion required"
                )
        elif mcp_exposure.exposed:
            if mcp_exclusion is not None:
                raise ValueError(f"mcp_exposure is both exposed and excluded for {subject_leaf_key}")
        elif mcp_exclusion is None:
            raise ValueError(f"silent MCP exclusion for {subject_leaf_key}; reason and authority required")

        if isinstance(policy, ProfilePolicyInventoryRow):
            observed_exposure = mcp_exposure.exposed if mcp_exposure is not None else False
            if policy.should_expose_via_mcp != observed_exposure:
                raise ValueError(
                    f"MCP exposure contradicts profile policy for {subject_leaf_key}: "
                    f"expected {policy.should_expose_via_mcp}, observed {observed_exposure}"
                )

        leaf_exclusions = tuple(
            exclusion
            for (key, _), exclusion in sorted(
                exclusions_by_subject_surface.items(), key=lambda item: item[0][1].value
            )
            if key == subject_leaf_key
        )
        reconciled.append(
            ReconciledOperatorLeaf(
                live_leaf=live_leaf,
                result_schema=result_schema if isinstance(result_schema, ResultSchemaInventoryRow) else None,
                input_schema=input_schema if isinstance(input_schema, InputSchemaInventoryRow) else None,
                mounted_family=mounted_family if isinstance(mounted_family, MountedFamilyInventoryRow) else None,
                profile_policy=policy if isinstance(policy, ProfilePolicyInventoryRow) else None,
                mcp_exposure=mcp_exposure,
                exclusions=leaf_exclusions,
            )
        )
    return OperatorSurfaceReconciliation(leaves=tuple(reconciled))


class CommandSchemaRef(BaseModel):
    """One registered command-path to result-schema reference.

    ``command`` is a stable :data:`~core.json_contract.SCHEMA_REGISTRY`
    key (e.g. ``"modelo.calculate"``); ``schema_name`` is the registered
    :class:`~core.json_contract.OutputSchema` subclass name an operator (or
    a tool-exposure server) resolves to read the command's result shape.
    """

    model_config = _STRICT_FROZEN

    command: str = Field(min_length=1)
    schema_name: str = Field(min_length=1)


class OperatorSurfaceManifest(BaseModel):
    """Agent-facing capability catalogue over the operator surface.

    Wraps the immutable :class:`OperatorSurfaceContract` (roots, mounted
    command families with their mutability and intent, modelo lifecycle,
    source-kind taxonomy, service owners) and the CLI's registered result-schema
    references. An LLM operator reads one manifest to discover what the CLI can
    do, which verbs mutate state, and where each command's result schema lives,
    instead of scraping ``--help``.
    """

    model_config = _STRICT_FROZEN

    manifest_version: str = "1"
    envelope_schema_version: str = Field(min_length=1)
    contract: OperatorSurfaceContract
    command_schemas: tuple[CommandSchemaRef, ...]


def build_operator_surface_manifest(
    *,
    envelope_schema_version: str,
    command_schemas: tuple[CommandSchemaRef, ...],
) -> OperatorSurfaceManifest:
    """Build the :class:`OperatorSurfaceManifest` from the cached contract.

    The contract is read from
    :func:`~application.operator_surface.get_operator_surface_contract`.
    The ``envelope_schema_version`` and ``command_schemas`` are supplied by the
    CLI adapter, which owns the JSON-contract registry; this keeps the
    application layer free of any dependency on the entrypoint package.

    Args:
        envelope_schema_version: The shared CLI envelope contract version
            (``ENVELOPE_SCHEMA_VERSION``) the manifest documents.
        command_schemas: The registered command-path to result-schema
            references, enumerated by the CLI from its schema registry.

    Returns:
        The validated :class:`OperatorSurfaceManifest`.
    """
    contract: OperatorSurfaceContract = get_operator_surface_contract()
    return OperatorSurfaceManifest(
        envelope_schema_version=envelope_schema_version,
        contract=contract,
        command_schemas=command_schemas,
    )
