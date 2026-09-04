"""Import-light tuple composer for the complete application ledger CommandSpec subtree."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from ._app_ledger_bienes_inversion_command_specs import LEDGER_BIENES_INVERSION_COMMAND_SPECS
from ._app_ledger_classification_command_specs import LEDGER_CLASSIFICATION_COMMAND_SPECS
from ._app_ledger_counterparty_command_specs import LEDGER_COUNTERPARTY_COMMAND_SPECS
from ._app_ledger_evidence_command_specs import LEDGER_EVIDENCE_COMMAND_SPECS
from ._app_ledger_evidence_followup_command_specs import LEDGER_EVIDENCE_FOLLOWUP_COMMAND_SPECS
from ._app_ledger_foundation_command_specs import LEDGER_FOUNDATION_COMMAND_SPECS
from ._app_ledger_inventory_analysis_command_specs import LEDGER_INVENTORY_ANALYSIS_COMMAND_SPECS
from ._app_ledger_inventory_command_specs import LEDGER_INVENTORY_COMMAND_SPECS
from ._app_ledger_invoice_intake_command_specs import LEDGER_INVOICE_INTAKE_COMMAND_SPECS
from ._app_ledger_invoice_lifecycle_command_specs import LEDGER_INVOICE_LIFECYCLE_COMMAND_SPECS
from ._app_ledger_lifecycle_command_specs import LEDGER_LIFECYCLE_COMMAND_SPECS
from ._app_ledger_management_command_specs import LEDGER_MANAGEMENT_COMMAND_SPECS
from ._app_ledger_operations_command_specs import LEDGER_OPERATIONS_COMMAND_SPECS
from ._app_ledger_participation_command_specs import LEDGER_PARTICIPATION_COMMAND_SPECS
from ._app_ledger_prorrata_command_specs import LEDGER_PRORRATA_COMMAND_SPECS
from ._app_ledger_ratios_command_specs import LEDGER_RATIOS_COMMAND_SPECS
from ._app_ledger_rule_command_specs import LEDGER_RULE_COMMAND_SPECS
from .command_spec import BindingState, CommandNodeKind, CommandSpec, SchemaState, TuiCapability

_LEDGER_SUBOPERATION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"ledger(?:\.[a-z][a-z0-9_]*)+")

LEDGER_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    *LEDGER_FOUNDATION_COMMAND_SPECS,
    *LEDGER_CLASSIFICATION_COMMAND_SPECS,
    *LEDGER_OPERATIONS_COMMAND_SPECS,
    *LEDGER_MANAGEMENT_COMMAND_SPECS,
    *LEDGER_LIFECYCLE_COMMAND_SPECS,
    *LEDGER_BIENES_INVERSION_COMMAND_SPECS,
    *LEDGER_COUNTERPARTY_COMMAND_SPECS,
    *LEDGER_EVIDENCE_COMMAND_SPECS,
    *LEDGER_INVENTORY_COMMAND_SPECS,
    *LEDGER_INVOICE_INTAKE_COMMAND_SPECS,
    *LEDGER_INVOICE_LIFECYCLE_COMMAND_SPECS,
    *LEDGER_PARTICIPATION_COMMAND_SPECS,
    *LEDGER_PRORRATA_COMMAND_SPECS,
    *LEDGER_RATIOS_COMMAND_SPECS,
    *LEDGER_RULE_COMMAND_SPECS,
    *LEDGER_EVIDENCE_FOLLOWUP_COMMAND_SPECS,
    *LEDGER_INVENTORY_ANALYSIS_COMMAND_SPECS,
)


class LedgerCliAdapterOwnership(StrEnum):
    """The currently observed amount of Ledger policy carried by one CLI endpoint.

    This is a census observation rather than a semantic-home decision.  The
    latter belongs to the cross-stream adjudication, while this annotation
    makes the current adapter burden explicit and prevents a newly enrolled
    endpoint from silently inheriting a verdict.
    """

    TRANSPORT_ONLY = "transport-only"
    MIXED = "mixed"
    POLICY_BEARING = "policy-bearing"


@dataclass(frozen=True, slots=True)
class LedgerCliCensusAnnotation:
    """The non-derivable adjudication attached to exactly one invocable spec."""

    command_key: str
    adapter_ownership: LedgerCliAdapterOwnership
    suboperation_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.command_key.startswith("app_ledger_"):
            raise ValueError("Ledger command census annotation requires an app_ledger command key")
        if len(set(self.suboperation_ids)) != len(self.suboperation_ids):
            raise ValueError(f"Ledger command census annotation has duplicate sub-operations: {self.command_key}")
        for identity in self.suboperation_ids:
            if _LEDGER_SUBOPERATION_ID_PATTERN.fullmatch(identity) is None:
                raise ValueError(f"Ledger command census sub-operation is not a stable identity: {identity}")


@dataclass(frozen=True, slots=True)
class LedgerCliCommandCensusEntry:
    """One immutable, path-derived executable Ledger command observation."""

    command_key: str
    path: tuple[str, ...]
    handler_identity: str
    result_schema_identity: str
    tui_capability: TuiCapability
    adapter_ownership: LedgerCliAdapterOwnership
    suboperation_ids: tuple[str, ...]


def _annotation(
    command_key: str,
    ownership: LedgerCliAdapterOwnership,
    *suboperation_ids: str,
) -> LedgerCliCensusAnnotation:
    return LedgerCliCensusAnnotation(command_key, ownership, suboperation_ids)


# These are deliberately the only hand-authored census facts.  Command path,
# deferred handler, schema, and TUI metadata are always projected from the
# production CommandSpec.  A new invocable therefore fails import until it has
# an explicit ownership observation rather than being given a default verdict.
_LEDGER_CLI_CENSUS_ANNOTATIONS: Final[tuple[LedgerCliCensusAnnotation, ...]] = (
    _annotation("app_ledger_add", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_allocate", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_archive", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_attach", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_bienes_inversion_declare", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_bienes_inversion_list", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_categories", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_check", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation(
        "app_ledger_classify",
        LedgerCliAdapterOwnership.POLICY_BEARING,
        "ledger.classify.direct",
        "ledger.classify.m210",
        "ledger.classify.iva_derive",
        "ledger.classify.llm_preview",
        "ledger.classify.llm_apply",
        "ledger.classify.llm_reject",
        "ledger.classify.llm_saturate_preview",
        "ledger.classify.llm_saturate_apply",
        "ledger.classify.llm_saturate_reject",
        "ledger.classify.evidence_read",
        "ledger.classify.auto_split.reject",
        "ledger.classify.auto_split.split_preview",
        "ledger.classify.auto_split.split_apply",
        "ledger.classify.auto_split.single_preview",
        "ledger.classify.auto_split.single_apply",
        "ledger.classify.bulk_csv",
    ),
    _annotation("app_ledger_counterparty_confirm", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_counterparty_view", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_counterparty_withdraw", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_detach", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_evidence_add", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_evidence_attachment_queue", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_evidence_attachment_view", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_evidence_batch", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_evidence_confirm", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_evidence_consent_list", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_evidence_consent_rederive", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_evidence_extract", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_evidence_list", LedgerCliAdapterOwnership.MIXED),
    _annotation(
        "app_ledger_evidence_pull",
        LedgerCliAdapterOwnership.POLICY_BEARING,
        "ledger.evidence.pull.gmail",
        "ledger.evidence.pull.drive",
        "ledger.evidence.pull.url",
    ),
    _annotation("app_ledger_evidence_pull_all", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_evidence_remove", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_evidence_review_list", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_evidence_review_view", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_evidence_update", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_evidence_view", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_exclude", LedgerCliAdapterOwnership.MIXED),
    _annotation(
        "app_ledger_export",
        LedgerCliAdapterOwnership.MIXED,
        "ledger.export.csv",
        "ledger.export.jsonl",
        "ledger.export.xlsx",
    ),
    _annotation(
        "app_ledger_history",
        LedgerCliAdapterOwnership.POLICY_BEARING,
        "ledger.history.direct",
        "ledger.history.split_siblings",
    ),
    _annotation(
        "app_ledger_import",
        LedgerCliAdapterOwnership.POLICY_BEARING,
        "ledger.import.file",
        "ledger.import.directory",
        "ledger.import.dry_run",
        "ledger.import.verify",
        "ledger.import.provider_auto",
        "ledger.import.provider_csv",
        "ledger.import.provider_ofx_qfx",
        "ledger.import.provider_xlsx_excel",
        "ledger.import.provider_n26",
        "ledger.import.provider_pdf",
        "ledger.import.provider_pdf_n26",
    ),
    _annotation("app_ledger_inventory_closing_authority_record", LedgerCliAdapterOwnership.TRANSPORT_ONLY),
    _annotation("app_ledger_inventory_create", LedgerCliAdapterOwnership.TRANSPORT_ONLY),
    _annotation("app_ledger_inventory_list", LedgerCliAdapterOwnership.TRANSPORT_ONLY),
    _annotation("app_ledger_inventory_movement_add", LedgerCliAdapterOwnership.TRANSPORT_ONLY),
    _annotation("app_ledger_inventory_valuation_preview", LedgerCliAdapterOwnership.TRANSPORT_ONLY),
    _annotation("app_ledger_invoice_add", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_invoice_import", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_invoice_list", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_invoice_remove", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_invoice_update", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_invoice_view", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_invoice_wizard", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_link", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation(
        "app_ledger_list",
        LedgerCliAdapterOwnership.POLICY_BEARING,
        "ledger.list.filter",
        "ledger.list.group",
        "ledger.list.sort",
        "ledger.list.page",
        "ledger.list.rejected_llm_filter",
    ),
    _annotation("app_ledger_llm_diagnostics", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_merge", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_participation", LedgerCliAdapterOwnership.TRANSPORT_ONLY),
    _annotation("app_ledger_participation_rebuild", LedgerCliAdapterOwnership.TRANSPORT_ONLY),
    _annotation("app_ledger_preflight", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_prorrata_declare_sector", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_prorrata_elect_especial", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_prorrata_elect_general", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_prorrata_list", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_prorrata_revoke_especial", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_prorrata_seed", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_prorrata_seed_sector", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_prorrata_settle_sector", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_ratios_eligible", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_ratios_list", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_ratios_set", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_ratios_unset", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_ratios_validate", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation(
        "app_ledger_remove",
        LedgerCliAdapterOwnership.MIXED,
        "ledger.remove.preview",
        "ledger.remove.commit",
    ),
    _annotation(
        "app_ledger_reset",
        LedgerCliAdapterOwnership.MIXED,
        "ledger.reset.preview",
        "ledger.reset.commit",
    ),
    _annotation("app_ledger_restore", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_review", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_rule_add", LedgerCliAdapterOwnership.MIXED),
    _annotation(
        "app_ledger_rule_apply",
        LedgerCliAdapterOwnership.POLICY_BEARING,
        "ledger.rule.apply.preview",
        "ledger.rule.apply.commit",
    ),
    _annotation("app_ledger_rule_list", LedgerCliAdapterOwnership.MIXED),
    _annotation(
        "app_ledger_split",
        LedgerCliAdapterOwnership.POLICY_BEARING,
        "ledger.split.manual",
        "ledger.split.llm_preview",
        "ledger.split.llm_apply",
        "ledger.split.evidence_read",
    ),
    _annotation("app_ledger_stash", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_status", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_track", LedgerCliAdapterOwnership.POLICY_BEARING),
    _annotation("app_ledger_update", LedgerCliAdapterOwnership.MIXED),
    _annotation("app_ledger_view", LedgerCliAdapterOwnership.POLICY_BEARING),
)


def _ledger_invocable_specs(
    specs: tuple[CommandSpec, ...] = LEDGER_COMMAND_SPECS,
) -> tuple[CommandSpec, ...]:
    """Return leaves and explicitly executable groups from the sole Ledger spec tree."""
    return tuple(spec for spec in specs if spec.kind is CommandNodeKind.LEAF or spec.invocation.invoke_without_command)


def _ledger_path_for(spec: CommandSpec, by_key: Mapping[str, CommandSpec]) -> tuple[str, ...]:
    """Derive one full operator path without importing the global graph cycle."""
    tokens = [spec.token]
    current = spec
    while current.key != "app_ledger":
        if current.parent_key is None or current.parent_key not in by_key:
            raise ValueError(f"Ledger command census has an unresolvable parent for {spec.key}")
        current = by_key[current.parent_key]
        tokens.append(current.token)
    if current.parent_key != "app":
        raise ValueError("Ledger command census requires app_ledger to remain under the app root")
    return ("aeat", "app", *reversed(tokens))


def _validated_annotations(
    invocables: tuple[CommandSpec, ...],
    annotations: tuple[LedgerCliCensusAnnotation, ...] = _LEDGER_CLI_CENSUS_ANNOTATIONS,
) -> MappingProxyType[str, LedgerCliCensusAnnotation]:
    """Reject duplicate, unknown, or missing adjudications before publishing a census."""
    annotation_keys = tuple(annotation.command_key for annotation in annotations)
    if len(set(annotation_keys)) != len(annotation_keys):
        raise ValueError("Ledger command census has duplicate ownership annotations")
    invocable_key_sequence = tuple(spec.key for spec in invocables)
    if len(set(invocable_key_sequence)) != len(invocable_key_sequence):
        raise ValueError("Ledger command census has duplicate invocable command keys")
    invocable_keys = {spec.key for spec in invocables}
    unknown = sorted(set(annotation_keys) - invocable_keys)
    missing = sorted(invocable_keys - set(annotation_keys))
    if unknown or missing:
        raise ValueError(f"Ledger command census annotations mismatch invocables: unknown={unknown}; missing={missing}")
    suboperations = tuple(suboperation for annotation in annotations for suboperation in annotation.suboperation_ids)
    if len(set(suboperations)) != len(suboperations):
        raise ValueError("Ledger command census has duplicate semantic sub-operation identities")
    return MappingProxyType({annotation.command_key: annotation for annotation in annotations})


def _build_ledger_cli_command_census(
    specs: tuple[CommandSpec, ...] = LEDGER_COMMAND_SPECS,
    annotations: tuple[LedgerCliCensusAnnotation, ...] = _LEDGER_CLI_CENSUS_ANNOTATIONS,
) -> tuple[LedgerCliCommandCensusEntry, ...]:
    """Project executable Ledger command facts and their explicit census annotations."""
    by_key = MappingProxyType({spec.key: spec for spec in specs})
    invocables = _ledger_invocable_specs(specs)
    annotations_by_key = _validated_annotations(invocables, annotations)
    entries: list[LedgerCliCommandCensusEntry] = []
    for spec in invocables:
        if spec.handler is None or spec.handler.state is not BindingState.TARGET or spec.handler.target is None:
            raise ValueError(f"Ledger invocable {spec.key} lacks an available deferred handler")
        if spec.result_schema.state is not SchemaState.TARGET or spec.result_schema.identity is None:
            raise ValueError(f"Ledger invocable {spec.key} lacks an available result schema")
        annotation = annotations_by_key[spec.key]
        entries.append(
            LedgerCliCommandCensusEntry(
                command_key=spec.key,
                path=_ledger_path_for(spec, by_key),
                handler_identity=spec.handler.target.identity,
                result_schema_identity=spec.result_schema.identity,
                tui_capability=spec.tui_capability,
                adapter_ownership=annotation.adapter_ownership,
                suboperation_ids=annotation.suboperation_ids,
            )
        )
    return tuple(sorted(entries, key=lambda entry: entry.path))


LEDGER_CLI_COMMAND_CENSUS: Final[tuple[LedgerCliCommandCensusEntry, ...]] = _build_ledger_cli_command_census()
"""Immutable S04 projection of every executable Ledger command from CommandSpec facts."""


__all__ = [
    "LEDGER_CLI_COMMAND_CENSUS",
    "LEDGER_COMMAND_SPECS",
    "LedgerCliAdapterOwnership",
    "LedgerCliCensusAnnotation",
    "LedgerCliCommandCensusEntry",
]
