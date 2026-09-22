"""Public-CLI capability audit for one RETENCIONES correction window.

The aggregate result now returns the opaque baseline and current generation's
immediate lineage required by an explicit replacement.  This remains a narrow
contract audit: it does not prove fresh-process reopening, a complete history
walk, an annual projection, or any filing action.
"""

from __future__ import annotations

import importlib
from dataclasses import asdict, dataclass
from typing import Any, Literal, get_args

from cadrumo.application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH

from .scenario import INSTALLED_CLI_SCENARIO_VERSION

SCENARIO_VERSION = "retenciones-public-cli-correction-history-v1"
LIMITATION_CODE = "full_generation_history_fresh_process_and_annual_projection_not_exercised"


@dataclass(frozen=True, slots=True)
class PublicCorrectionHistoryEvidence:
    """Safe capability evidence for one resident-professional correction.

    The evidence describes the installed command contract, never a taxpayer
    state.  In particular, it does not invent an AEAT filing confirmation or
    seed a persistence repository to obtain an otherwise private baseline.
    """

    scenario: str
    source_scenario: str
    slice_id: str
    modelo: str
    evidence_level: Literal["public_cli_contract"]
    outcome: Literal["partial"]
    append_transport_available: bool
    replace_transport_declared: bool
    public_baseline_read_available: bool
    immediate_generation_lineage_available: bool
    full_generation_history_available: bool
    fresh_process_readback_proven: bool
    effective_annual_projection_read_available: bool
    local_filing_or_export: Literal["not_exercised"]
    aeat_confirmation: Literal["not_claimed"]
    limitation_code: str

    def to_dict(self) -> dict[str, object]:
        """Return a stable, payload-free receipt shape."""
        return asdict(self)


def inspect_resident_professional_correction_capability() -> PublicCorrectionHistoryEvidence:
    """Audit the public contract required to correct one Modelo 111 window.

    The annual 190 journey is deliberately out of scope.  This contract makes
    the replacement transport actionable but does not prove the corrected
    source through a fresh process or an annual projection.
    """
    aggregate = COMMAND_GRAPH.resolve_path(("aeat", "app", "modelo", "aggregate"))
    history = COMMAND_GRAPH.resolve_path(("aeat", "app", "modelo", "history"))
    aggregate_parameters = {parameter.name for parameter in aggregate.parameters}
    aggregate_model = _result_model(aggregate)
    aggregate_fields = frozenset(aggregate_model.model_fields)
    history_fields = _result_fields(history)
    request_fields = frozenset(InvoiceWithholdingEvidenceRequest.model_fields)
    window_model = _nested_model(aggregate_model, "withholding_window")
    baseline_model = _nested_model(window_model, "baseline")
    audit_model = _nested_model(window_model, "generation_audit")

    append_transport_available = "received_invoice_retencion" in aggregate_parameters
    replace_transport_declared = {"mode", "baseline", "supersedes_generation_id"} <= request_fields
    public_baseline_read_available = "withholding_window" in aggregate_fields and {
        "scope_token",
        "generation_id",
    } <= frozenset(baseline_model.model_fields)
    immediate_generation_lineage_available = {
        "parent_generation_id",
        "mode",
        "supersedes_generation_id",
    } <= frozenset(audit_model.model_fields)
    full_generation_history_available = bool(
        {"generation_id", "parent_generation_id", "supersedes_generation_id"} & history_fields
    )
    fresh_process_readback_proven = False
    effective_annual_projection_read_available = False

    if (
        append_transport_available
        and replace_transport_declared
        and public_baseline_read_available
        and immediate_generation_lineage_available
        and not full_generation_history_available
    ):
        return PublicCorrectionHistoryEvidence(
            scenario=SCENARIO_VERSION,
            source_scenario=INSTALLED_CLI_SCENARIO_VERSION,
            slice_id="professional-111-q2-partial-payments",
            modelo="111",
            evidence_level="public_cli_contract",
            outcome="partial",
            append_transport_available=True,
            replace_transport_declared=True,
            public_baseline_read_available=True,
            immediate_generation_lineage_available=True,
            full_generation_history_available=False,
            fresh_process_readback_proven=fresh_process_readback_proven,
            effective_annual_projection_read_available=effective_annual_projection_read_available,
            local_filing_or_export="not_exercised",
            aeat_confirmation="not_claimed",
            limitation_code=LIMITATION_CODE,
        )
    raise AssertionError("the public correction/readback contract changed; update this acceptance case")


def _result_fields(spec: Any) -> frozenset[str]:
    """Resolve a live CLI result contract through its declared target."""
    return frozenset(_result_model(spec).model_fields)


def _result_model(spec: Any) -> Any:
    """Resolve the Pydantic model declared by one live CLI result target."""
    target = spec.result_schema.target
    if target is None:
        raise AssertionError(f"{spec.key} has no result target")
    value: object = importlib.import_module(target.module)
    for component in target.qualname.split("."):
        value = getattr(value, component)
    if not isinstance(getattr(value, "model_fields", None), dict):
        raise AssertionError(f"{target.identity} is not a Pydantic output schema")
    return value


def _nested_model(model: Any, field_name: str) -> Any:
    """Return the one Pydantic payload model nested in a result field."""
    field = model.model_fields.get(field_name)
    if field is None:
        raise AssertionError(f"{model.__name__} does not expose {field_name}")
    candidates = get_args(field.annotation) or (field.annotation,)
    models = [candidate for candidate in candidates if isinstance(getattr(candidate, "model_fields", None), dict)]
    if len(models) != 1:
        raise AssertionError(f"{model.__name__}.{field_name} has no unambiguous output payload")
    return models[0]


__all__ = [
    "LIMITATION_CODE",
    "SCENARIO_VERSION",
    "PublicCorrectionHistoryEvidence",
    "inspect_resident_professional_correction_capability",
]
