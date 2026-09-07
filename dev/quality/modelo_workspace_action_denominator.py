"""ModeloWorkspaceActionDenominatorV1: the complete, closed Modelo action set.

Enumerates every live Modelo command-graph candidate the interface plan must
eventually classify, and pins a CLOSED, hand-reviewed disposition for each one
today. The candidate set is derived from production imports only
(``cadrumo.entrypoints.cli.command_api.command_spec_nodes``,
``cadrumo.application.operator_actions.OPERATOR_ACTION_CATALOGUE``) -- never a
filesystem walk -- so it cannot ingest a gitignored mirror or any other
untracked artefact, and it is reproducible on any checkout.

The closed table is deliberately NOT re-derived at validation time from the
same mechanical rule that produced it. ``validate_modelo_workspace_action_denominator``
diffs the CURRENT live candidate set against the CLOSED, checked-in table:
a live identity absent from the table is an ``unclassified action candidate``
violation, a table entry no longer live is a stale-entry violation, and a live
signature (command key, write_route, side effects, action-catalogue
membership) that no longer matches its recorded classification is a
drifted-signature violation. A brand-new Modelo command therefore reds this
gate immediately rather than silently inheriting whatever the mechanical rule
would have assigned it -- the whole point of a denominator is that nothing
can join the classified set without a reviewed, committed decision.

Disposition taxonomy (closed, per the tui-modelo-workspace-interface ADR D10
staged-cohort framing):

- ``C1_BOUNDED_REVIEW`` -- already relocated to the sole enrolled C1 read
  destination (``modelo.work.review``).
- ``C1_OR_C2_READ_PENDING`` -- an in-scope read query (no direct effect) not
  yet migrated to a numbered C1 or C2 Workspace destination.
- ``C4_MUTATION_PENDING`` -- an in-scope direct-effect mutation; no visual
  lifecycle control may appear before its C3/C4 conformance suites are green.
- ``FLOW_OWNED`` -- a guided-wizard command owned by a flow renderer rather
  than a Workspace destination.
- ``DEFERRED`` -- owned by an authority entirely OUTSIDE this interface plan
  (currently only work-unit lifecycle creation).
- ``NOT_VISUAL`` -- reserved: no candidate uses it today, but the ADR names it
  as a legal disposition for a future candidate with no visual destination.

Only two dispositions are the product of a genuine judgement call recorded in
the ADR text rather than a mechanical rule: ``modelo.work.create`` (DEFERRED)
and the wizard-token candidates (FLOW_OWNED). Every other row follows
mechanically from the command's own declared ``write_route`` (none == query,
anything else == direct-effect mutation) plus whether it is the one
canonically relocated C1 read.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.application.operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
from cadrumo.entrypoints.cli.command_api import command_spec_nodes
from cadrumo.entrypoints.cli.command_spec import SchemaState

from .modelo_workspace_action_classification import (
    MODELO_IDENTITY_PREFIX,
    ModeloWorkspaceActionClassificationV1,
    ModeloWorkspaceActionDisposition,
    modelo_action_classification,
)
from .modelo_workspace_action_classification_table import MODELO_ACTION_CLASSIFICATIONS

SCHEMA_VERSION: Final[int] = 1


class ModeloWorkspaceActionDenominatorV1(BaseModel):
    """The bound between the live candidate set and its closed classifications.

    ``live_action_identities`` is what ``command_spec_nodes()`` reports RIGHT
    NOW; ``classifications`` is the closed table. Construction never fails on
    a mismatch between the two -- that is what the validator's diff is for --
    but it does refuse a live identity set with an internal duplicate, which
    would indicate a broken command-graph invariant far outside this module's
    concern.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    schema_version: int = Field(ge=1)
    live_action_identities: tuple[str, ...]
    classifications: Mapping[str, ModeloWorkspaceActionClassificationV1]

    @model_validator(mode="after")
    def _check_live_identities_are_unique(self) -> ModeloWorkspaceActionDenominatorV1:
        if len(set(self.live_action_identities)) != len(self.live_action_identities):
            raise ValueError("live_action_identities contains a duplicate; the command graph invariant is broken")
        return self


def discover_live_modelo_action_signatures() -> dict[str, ModeloWorkspaceActionClassificationV1]:
    """Observe the CURRENT live Modelo action signatures, unclassified.

    Returns one throwaway :class:`ModeloWorkspaceActionClassificationV1` per
    live candidate carrying only its observed mechanical signature; the
    ``disposition``/``owning_authority``/``reason``/``evidence_reference``/
    ``reopening_condition`` fields are placeholders the caller must never
    trust -- they exist only so the live signature can be compared field-by-
    field against the closed table's recorded signature.
    """
    catalogue_target_keys = frozenset(entry.target_command_key for entry in OPERATOR_ACTION_CATALOGUE.entries)
    dispatchable = discover_dispatchable_modelo_action_identities()
    live: dict[str, ModeloWorkspaceActionClassificationV1] = {}
    for node in command_spec_nodes():
        spec = node.spec
        if spec.result_schema.state is not SchemaState.TARGET:
            continue
        identity = spec.result_schema.identity
        if identity is None or not identity.startswith(MODELO_IDENTITY_PREFIX):
            continue
        live[identity] = modelo_action_classification(
            identity,
            ModeloWorkspaceActionDisposition.NOT_VISUAL,
            command_key=spec.key,
            write_route=spec.policy.write_route,
            side_effects=tuple(sorted(spec.policy.side_effects)),
            has_action_catalogue_entry=identity in catalogue_target_keys,
            tui_capability=spec.tui_capability,
            is_surface_dispatchable=identity in dispatchable,
            owning_authority="live-observation-placeholder",
            reason="live-observation-placeholder",
            evidence_reference="live-observation-placeholder",
            reopening_condition="live-observation-placeholder",
        )
    return live


def discover_dispatchable_modelo_action_identities() -> frozenset[str]:
    """Observe which actions a TUI surface can actually DISPATCH today.

    A second candidate stream, deliberately separate from the command-graph
    one. The command graph answers "what commands exist"; this answers "what
    can a workspace surface invoke", and the two disagree in both directions:
    a command can exist with no surface reaching it, and a surface can dispatch
    an operation that is not a CLI command at all. Collapsing them into one
    stream would let each hide the other's gaps.

    Imported from the shipped package rather than re-listed here, so a dispatch
    row added to the surface enters this gate automatically instead of when
    somebody remembers to update a parallel list.
    """
    from cadrumo.entrypoints.tui.modelo.actions import MODELO_ACTION_DISPATCH

    return frozenset(MODELO_ACTION_DISPATCH)


def build_modelo_workspace_action_denominator() -> ModeloWorkspaceActionDenominatorV1:
    """Bind the current live candidate set to the closed classification table."""
    live_identities = tuple(sorted(discover_live_modelo_action_signatures()))
    return ModeloWorkspaceActionDenominatorV1(
        schema_version=SCHEMA_VERSION,
        live_action_identities=live_identities,
        classifications=MODELO_ACTION_CLASSIFICATIONS,
    )


_SIGNATURE_FIELDS: Final[tuple[str, ...]] = (
    "command_key",
    "write_route",
    "side_effects",
    "has_action_catalogue_entry",
    "tui_capability",
    "is_surface_dispatchable",
)


def validate_modelo_workspace_action_denominator(
    denominator: ModeloWorkspaceActionDenominatorV1 | None = None,
) -> list[str]:
    """Accumulate every violation of the Modelo action denominator.

    Rebuilds the live signature set itself (never trusts a caller-supplied one
    for the live side) so a stale ``denominator`` argument cannot mask drift;
    the argument, when supplied, is used only for its ``classifications``
    table so a candidate future denominator variant can be checked without
    mutating the module-level constant.
    """
    classifications = (denominator or build_modelo_workspace_action_denominator()).classifications
    live = discover_live_modelo_action_signatures()

    errors: list[str] = []

    unclassified = sorted(set(live) - set(classifications))
    if unclassified:
        errors.append(f"unclassified action candidate(s), never omit: {unclassified}")

    stale = sorted(set(classifications) - set(live))
    if stale:
        errors.append(f"stale classification(s) for action(s) no longer live: {stale}")

    # THE DISPATCH STREAM AND THE COMMAND-GRAPH STREAM HAVE DIFFERENT
    # DENOMINATORS, and that is the finding rather than a defect to paper
    # over. The classification table is keyed to command-graph candidates;
    # the dispatch table is keyed to REGISTERED OPERATIONS. Six members
    # overlap. `modelo.edit.apply` is dispatchable and is not a command-graph
    # candidate at all, so requiring it to be classified here would demand a
    # row that the stale-classification rule above would then reject -- the
    # two rules would contradict each other on the same identity.
    #
    # So the enforceable invariant is the intersection only: an action that
    # BOTH appears in the command graph AND is dispatchable from a surface
    # must be classified. Anything wider is a scope decision about what the
    # classification table's denominator is, which belongs to that table's
    # owner and not to this check.
    dispatchable = discover_dispatchable_modelo_action_identities()
    unadjudicated = sorted((dispatchable & set(live)) - set(classifications))
    if unadjudicated:
        errors.append(
            "action(s) both live in the command graph and dispatchable from a surface, yet absent "
            f"from the classification table: {unadjudicated}",
        )

    for identity in sorted(set(live) & set(classifications)):
        observed = live[identity]
        recorded = classifications[identity]
        drifted = [
            field_name
            for field_name in _SIGNATURE_FIELDS
            if getattr(observed, field_name) != getattr(recorded, field_name)
        ]
        if drifted:
            errors.append(
                f"drifted signature for {identity!r} on fields {drifted}: "
                f"observed={ {name: getattr(observed, name) for name in drifted} }, "
                f"recorded={ {name: getattr(recorded, name) for name in drifted} }",
            )

    return errors


__all__: tuple[str, ...] = (
    "SCHEMA_VERSION",
    "ModeloWorkspaceActionDenominatorV1",
    "build_modelo_workspace_action_denominator",
    "discover_dispatchable_modelo_action_identities",
    "discover_live_modelo_action_signatures",
    "validate_modelo_workspace_action_denominator",
)
