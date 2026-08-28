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
  lifecycle control may appear before its C3/C4 receipts are green.
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
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.application.operator_actions import OPERATOR_ACTION_CATALOGUE
from cadrumo.entrypoints.cli._command_spec import SchemaState
from cadrumo.entrypoints.cli.command_api import command_spec_nodes

SCHEMA_VERSION: Final[int] = 1
_MODELO_IDENTITY_PREFIX: Final[str] = "modelo."
_PLACEHOLDER_REASONS: Final[frozenset[str]] = frozenset({"", "n/a", "na", "unmeasured", "tbd", "todo"})


class ModeloWorkspaceActionDisposition(StrEnum):
    """Closed classification outcome for one Modelo action candidate."""

    C1_BOUNDED_REVIEW = "c1_bounded_review"
    C1_OR_C2_READ_PENDING = "c1_or_c2_read_pending"
    C4_MUTATION_PENDING = "c4_mutation_pending"
    FLOW_OWNED = "flow_owned"
    DEFERRED = "deferred"
    NOT_VISUAL = "not_visual"


class ModeloWorkspaceActionClassificationV1(BaseModel):
    """One closed, hand-reviewed row: an action identity plus its disposition.

    ``command_key``, ``write_route``, ``side_effects``, and
    ``has_action_catalogue_entry`` are the recorded mechanical SIGNATURE this
    row was classified against; the validator re-observes the live signature
    and reds on drift rather than silently re-classifying.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    action_identity: str = Field(min_length=1)
    disposition: ModeloWorkspaceActionDisposition
    command_key: str = Field(min_length=1)
    write_route: str = Field(min_length=1)
    side_effects: tuple[str, ...]
    has_action_catalogue_entry: bool
    owning_authority: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    evidence_reference: str = Field(min_length=1)
    reopening_condition: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_reason_is_not_a_placeholder(self) -> ModeloWorkspaceActionClassificationV1:
        if self.reason.strip().lower() in _PLACEHOLDER_REASONS:
            raise ValueError(f"classification reason for {self.action_identity!r} must be a real, bounded reason")
        if not self.action_identity.startswith(_MODELO_IDENTITY_PREFIX):
            raise ValueError(f"{self.action_identity!r} is outside the Modelo action denominator's scope")
        return self


def _classification(
    action_identity: str,
    disposition: ModeloWorkspaceActionDisposition,
    *,
    command_key: str,
    write_route: str,
    side_effects: tuple[str, ...],
    has_action_catalogue_entry: bool,
    owning_authority: str,
    reason: str,
    evidence_reference: str,
    reopening_condition: str,
) -> ModeloWorkspaceActionClassificationV1:
    return ModeloWorkspaceActionClassificationV1(
        action_identity=action_identity,
        disposition=disposition,
        command_key=command_key,
        write_route=write_route,
        side_effects=side_effects,
        has_action_catalogue_entry=has_action_catalogue_entry,
        owning_authority=owning_authority,
        reason=reason,
        evidence_reference=evidence_reference,
        reopening_condition=reopening_condition,
    )


# Closed, hand-reviewed classification table. Every row was generated once from
# the mechanical rule documented in the module docstring and then reviewed;
# regenerating it is a deliberate act, never an implicit side effect of
# validation. See `dev/tests/test_modelo_workspace_action_denominator.py` for
# the anti-vacuity proof that a live candidate missing from this table reds.
MODELO_ACTION_CLASSIFICATIONS: Final[Mapping[str, ModeloWorkspaceActionClassificationV1]] = {
    "modelo.aggregate": _classification(
        "modelo.aggregate",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_aggregate",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.audit.check": _classification(
        "modelo.audit.check",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_audit_check",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.audit.export": _classification(
        "modelo.audit.export",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_audit_export",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.audit.view": _classification(
        "modelo.audit.view",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_audit_view",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.bindings.list": _classification(
        "modelo.bindings.list",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_bindings_list",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=True,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.bindings.resolve": _classification(
        "modelo.bindings.resolve",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_bindings_resolve",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.casilla": _classification(
        "modelo.casilla",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_casilla",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.casillas": _classification(
        "modelo.casillas",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_casillas",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.compare": _classification(
        "modelo.compare",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_compare",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.describe": _classification(
        "modelo.describe",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_describe",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=True,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.export": _classification(
        "modelo.export",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_export",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.filing_record.import": _classification(
        "modelo.filing_record.import",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_filing_record_import",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.filing_record.list": _classification(
        "modelo.filing_record.list",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_filing_record_list",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=True,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.filing_record.observe_local": _classification(
        "modelo.filing_record.observe_local",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_filing_record_observe_local",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.filing_record.view": _classification(
        "modelo.filing_record.view",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_filing_record_view",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.formulas": _classification(
        "modelo.formulas",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_formulas",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.history": _classification(
        "modelo.history",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_history",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.iva_wallet.balance": _classification(
        "modelo.iva_wallet.balance",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_iva_wallet_balance",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.iva_wallet.correct": _classification(
        "modelo.iva_wallet.correct",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_iva_wallet_correct",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.iva_wallet.override": _classification(
        "modelo.iva_wallet.override",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_iva_wallet_override",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.iva_wallet.seed": _classification(
        "modelo.iva_wallet.seed",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_iva_wallet_seed",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.list": _classification(
        "modelo.list",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_list",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.m036.alta": _classification(
        "modelo.m036.alta",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_m036_alta",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.m036.baja": _classification(
        "modelo.m036.baja",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_m036_baja",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.m036.list": _classification(
        "modelo.m036.list",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_m036_list",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.m036.modificacion": _classification(
        "modelo.m036.modificacion",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_m036_modificacion",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.m036.view": _classification(
        "modelo.m036.view",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_m036_view",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.m145.create": _classification(
        "modelo.m145.create",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_m145_create",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.m145.export": _classification(
        "modelo.m145.export",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_m145_export",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.m145.mark_delivered_to_payer": _classification(
        "modelo.m145.mark_delivered_to_payer",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_m145_mark_delivered_to_payer",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.m145.mark_locally_completed": _classification(
        "modelo.m145.mark_locally_completed",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_m145_mark_locally_completed",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.m145.validate": _classification(
        "modelo.m145.validate",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_m145_validate",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.project": _classification(
        "modelo.project",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_project",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.readiness": _classification(
        "modelo.readiness",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_readiness",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.reconcile.list": _classification(
        "modelo.reconcile.list",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_reconcile_list",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.reconcile.import": _classification(
        "modelo.reconcile.import",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_reconcile_import",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.reconcile.pull": _classification(
        "modelo.reconcile.pull",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_reconcile_pull",
        write_route="profile-bound",
        side_effects=("browser", "local-state", "network"),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.requires": _classification(
        "modelo.requires",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_requires",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.review_package.build": _classification(
        "modelo.review_package.build",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_review_package_build",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.review_package.counter_sign": _classification(
        "modelo.review_package.counter_sign",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_review_package_counter_sign",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.review_package.decrypt": _classification(
        "modelo.review_package.decrypt",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_review_package_decrypt",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.review_package.encrypt_feedback": _classification(
        "modelo.review_package.encrypt_feedback",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_review_package_encrypt_feedback",
        write_route="none",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.review_package.encrypt_for_recipient": _classification(
        "modelo.review_package.encrypt_for_recipient",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_review_package_encrypt_for_recipient",
        write_route="none",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.review_package.import_feedback": _classification(
        "modelo.review_package.import_feedback",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_review_package_import_feedback",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.review_package.sign": _classification(
        "modelo.review_package.sign",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_review_package_sign",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.review_package.verify": _classification(
        "modelo.review_package.verify",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_review_package_verify",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.review_package.verify_receipt": _classification(
        "modelo.review_package.verify_receipt",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_review_package_verify_receipt",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.review_package.verify_signature": _classification(
        "modelo.review_package.verify_signature",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_review_package_verify_signature",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.spreadsheet.calculate": _classification(
        "modelo.spreadsheet.calculate",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_spreadsheet_calculate",
        write_route="profile-bound",
        side_effects=("google", "local-state"),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.spreadsheet.pull": _classification(
        "modelo.spreadsheet.pull",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_spreadsheet_pull",
        write_route="profile-bound",
        side_effects=("google", "local-state"),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.spreadsheet.push": _classification(
        "modelo.spreadsheet.push",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_spreadsheet_push",
        write_route="profile-bound",
        side_effects=("google", "local-state"),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.spreadsheet.verify": _classification(
        "modelo.spreadsheet.verify",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_spreadsheet_verify",
        write_route="none",
        side_effects=("google",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.support_matrix": _classification(
        "modelo.support_matrix",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_support_matrix",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.verification_report.list": _classification(
        "modelo.verification_report.list",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_verification_report_list",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=True,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.verification_report.view": _classification(
        "modelo.verification_report.view",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_verification_report_view",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.work.amend": _classification(
        "modelo.work.amend",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_work_amend",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.work.amend_wizard": _classification(
        "modelo.work.amend_wizard",
        ModeloWorkspaceActionDisposition.FLOW_OWNED,
        command_key="app_modelo_work_amend_wizard",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-architecture guided flows",
        reason="guided-wizard command; owned by a flow renderer, not a Workspace destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens only if C4 assigns this wizard a distinct disposition",
    ),
    "modelo.work.calculate": _classification(
        "modelo.work.calculate",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_work_calculate",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=True,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.work.compare_taxation": _classification(
        "modelo.work.compare_taxation",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_work_compare_taxation",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.work.create": _classification(
        "modelo.work.create",
        ModeloWorkspaceActionDisposition.DEFERRED,
        command_key="app_modelo_work_create",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=True,
        owning_authority="work-lifecycle ownership",
        reason="work-unit lifecycle creation is owned outside this interface plan",
        evidence_reference="work-unit lifecycle creation ownership, tracked outside this interface effort",
        reopening_condition="reopens only if a future accepted decision moves this into scope",
    ),
    "modelo.work.dependencies": _classification(
        "modelo.work.dependencies",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_work_dependencies",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.work.discard": _classification(
        "modelo.work.discard",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_work_discard",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.work.file": _classification(
        "modelo.work.file",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_work_file",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=True,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.work.history": _classification(
        "modelo.work.history",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_work_history",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.work.list": _classification(
        "modelo.work.list",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_work_list",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=True,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.work.observations": _classification(
        "modelo.work.observations",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_work_observations",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.work.preview_maritime_exemption": _classification(
        "modelo.work.preview_maritime_exemption",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_work_preview_maritime_exemption",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.work.rename": _classification(
        "modelo.work.rename",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_work_rename",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.work.resume": _classification(
        "modelo.work.resume",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_work_resume",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.work.review": _classification(
        "modelo.work.review",
        ModeloWorkspaceActionDisposition.C1_BOUNDED_REVIEW,
        command_key="app_modelo_work_review",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-architecture W04.P10.S104",
        reason="canonically relocated to the C1 bounded-review destination",
        evidence_reference="the independently verified modelo.work.review relocation review",
        reopening_condition="never reopens: terminal C1 disposition",
    ),
    "modelo.work.select": _classification(
        "modelo.work.select",
        ModeloWorkspaceActionDisposition.C1_BOUNDED_REVIEW,
        command_key="app_modelo_work_select",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10.S24",
        reason="the sole C1 work-unit picker entrance into modelo.work.review",
        evidence_reference="src/cadrumo/entrypoints/tui/modelo/view/work_select.py",
        reopening_condition="never reopens: terminal C1 disposition",
    ),
    "modelo.work.revision": _classification(
        "modelo.work.revision",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_work_revision",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.work.revisions": _classification(
        "modelo.work.revisions",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_work_revisions",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=True,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.work.run": _classification(
        "modelo.work.run",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_work_run",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.work.run_details": _classification(
        "modelo.work.run_details",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_work_run_details",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.work.runs": _classification(
        "modelo.work.runs",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_work_runs",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.work.status": _classification(
        "modelo.work.status",
        ModeloWorkspaceActionDisposition.C1_OR_C2_READ_PENDING,
        command_key="app_modelo_work_status",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=True,
        owning_authority="tui-interface W05.P10/W05.P11",
        reason="read-only query, not yet migrated to a C1 or C2 destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
    ),
    "modelo.work.verify": _classification(
        "modelo.work.verify",
        ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        command_key="app_modelo_work_verify",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=True,
        owning_authority="tui-interface W06.P12c",
        reason="direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens once C3/C4 receipts are green and this is enrolled as a C4 action",
    ),
    "modelo.work.wizard": _classification(
        "modelo.work.wizard",
        ModeloWorkspaceActionDisposition.FLOW_OWNED,
        command_key="app_modelo_work_wizard",
        write_route="profile-bound",
        side_effects=("local-state",),
        has_action_catalogue_entry=False,
        owning_authority="tui-architecture guided flows",
        reason="guided-wizard command; owned by a flow renderer, not a Workspace destination",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="reopens only if C4 assigns this wizard a distinct disposition",
    ),
}


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
    live: dict[str, ModeloWorkspaceActionClassificationV1] = {}
    for node in command_spec_nodes():
        spec = node.spec
        if spec.result_schema.state is not SchemaState.TARGET:
            continue
        identity = spec.result_schema.identity
        if identity is None or not identity.startswith(_MODELO_IDENTITY_PREFIX):
            continue
        live[identity] = _classification(
            identity,
            ModeloWorkspaceActionDisposition.NOT_VISUAL,
            command_key=spec.key,
            write_route=spec.policy.write_route,
            side_effects=tuple(sorted(spec.policy.side_effects)),
            has_action_catalogue_entry=identity in catalogue_target_keys,
            owning_authority="live-observation-placeholder",
            reason="live-observation-placeholder",
            evidence_reference="live-observation-placeholder",
            reopening_condition="live-observation-placeholder",
        )
    return live


def build_modelo_workspace_action_denominator() -> ModeloWorkspaceActionDenominatorV1:
    """Bind the current live candidate set to the closed classification table."""
    live_identities = tuple(sorted(discover_live_modelo_action_signatures()))
    return ModeloWorkspaceActionDenominatorV1(
        schema_version=SCHEMA_VERSION,
        live_action_identities=live_identities,
        classifications=MODELO_ACTION_CLASSIFICATIONS,
    )


_SIGNATURE_FIELDS: Final[tuple[str, ...]] = ("command_key", "write_route", "side_effects", "has_action_catalogue_entry")


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


__all__ = [
    "MODELO_ACTION_CLASSIFICATIONS",
    "SCHEMA_VERSION",
    "ModeloWorkspaceActionClassificationV1",
    "ModeloWorkspaceActionDenominatorV1",
    "ModeloWorkspaceActionDisposition",
    "build_modelo_workspace_action_denominator",
    "discover_live_modelo_action_signatures",
    "validate_modelo_workspace_action_denominator",
]
