"""Public operation schemas must expose the bounds enforced on their payloads."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from ....core.errors.hierarchy import InternalInvariantError
from ....core.period import Period
from ....domain.modelos.codes import ModeloCodeText
from ...aggregation.service import PerModeloAggregationCommand
from ...inventory.registered_requests import InventoryPhysicalClosingObservationRequest
from ...ledger.merge_operation import LedgerMergeOperationResult, LedgerMergeRequest
from ...ledger.split_operation import LedgerSplitOperationResult, LedgerSplitRequest
from ...modelo.aggregate_public import PublicModeloAggregateCommand
from ...modelo.lifecycle_advisories import ModeloM210PlazoAdvisoryV1
from ...modelo.projection_operation import ModeloCompareOperationRequest
from ...modelo.work_plazo import M210PlazoResolution
from ...workflow.resume_contracts import WorkflowResumeAmbiguity

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("model", "field"),
    [
        (InventoryPhysicalClosingObservationRequest, "evidence"),
        (LedgerMergeRequest, "child_ids"),
        (LedgerMergeOperationResult, "source_child_ids"),
        (LedgerSplitRequest, "children"),
        (LedgerSplitOperationResult, "child_transaction_ids"),
        (ModeloCompareOperationRequest, "years"),
        (WorkflowResumeAmbiguity, "candidates"),
    ],
)
def test_public_schema_declares_the_two_item_minimum(model: type[BaseModel], field: str) -> None:
    assert model.model_json_schema()["properties"][field]["minItems"] == 2


def test_public_modelo_code_exposes_and_enforces_its_ascii_wire_shape() -> None:
    adapter = TypeAdapter(ModeloCodeText)
    assert adapter.json_schema()["pattern"] == r"^[0-9]{3}$"
    assert adapter.validate_python("145") == "145"
    for invalid in ("14", "1450", "abc", "\uff11\uff14\uff15"):
        with pytest.raises(ValidationError):
            adapter.validate_python(invalid)


def _resolution_for(modelo: str) -> M210PlazoResolution:
    context = {
        "modelo": modelo,
        "filing_year": "2025",
        "period": "0A",
        "resultado": "I",
        "deadline_window_id": "window",
        "opens_on": "2025-04-01",
        "closes_on": "2025-05-01",
        "legal_refs": "law",
        "source_refs": "source",
    }
    return M210PlazoResolution(closes_on=context["closes_on"], context=context)


def test_m210_producer_uses_the_pinned_form_role(authority_operation: object) -> None:
    del authority_operation  # The fixture supplies the generation-pinned governed-fact scope.
    assert ModeloM210PlazoAdvisoryV1.from_resolution(_resolution_for("210")).modelo == "210"
    with pytest.raises(ValueError, match="unsupported modelo"):
        ModeloM210PlazoAdvisoryV1.from_resolution(_resolution_for("145"))


def test_m210_producer_refuses_to_decide_a_role_without_authority() -> None:
    with pytest.raises(InternalInvariantError, match="explicit generation-pinned"):
        ModeloM210PlazoAdvisoryV1.from_resolution(_resolution_for("210"))


def test_aggregate_public_command_projects_an_empty_domain_request() -> None:
    command = PerModeloAggregationCommand(modelo="193", period=Period.from_year_and_code(2025, "0A"))
    public = PublicModeloAggregateCommand.from_domain(command)
    assert public.to_domain() == command
    assert PublicModeloAggregateCommand.model_json_schema()["properties"]["foreign_asset_observations"]
