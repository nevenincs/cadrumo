"""A batch closes a reading role only on a typed refusal of the role's model run.

The registered ``ledger.evidence.batch`` runs through the production registry,
the real supervisor, journal and encrypted operand store, the composed
extraction readers, the production client and the agent adapter. The agent
service behind the operation's execution authority is a recording stand-in, so
what was sent to it is observed rather than assumed. Each batch holds two
text-layer documents with no label the rules read, so both need the text
extraction role.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo_client.contracts.model_runs import ModelRunRefusal, ModelRunRefusalCode

from ...adapters.outbound.llm.providers.agent import model_run_refusal_verdict
from ...adapters.outbound.llm.tests.model_run_support import DEFAULT_LANE
from ...application.ledger.evidence_ingestion_contracts import (
    LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
    LedgerEvidenceBatchProjection,
    LedgerEvidenceBatchRequest,
)
from ...core.model_roles import ModelRole
from ...core.operations import OperationTerminalCondition
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.iva.schema import InvoiceKind
from ...tests.pdf_fixtures import text_pdf_bytes
from .dependency_operation_gating_support import OperationRuntime, operation_runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: Two documents with figures no label rule reads, so each needs the text model.
_DOCUMENTS = (("first.pdf", ("B1234567X B17283946 766,30",)), ("second.pdf", ("B7654321X B17283946 412,10",)))


def _settle_batch(runtime: OperationRuntime) -> LedgerEvidenceBatchProjection:
    folder = runtime.tmp_path / "documents"
    folder.mkdir()
    sources: list[str] = []
    for name, lines in _DOCUMENTS:
        document = folder / name
        document.write_bytes(text_pdf_bytes(lines))
        sources.append(str(document))
    settled = runtime.settle(
        LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
        LedgerEvidenceBatchRequest(
            profile_id=runtime.profile_id,
            sources=tuple(sources),
            source_directory=str(folder),
            direction=InvoiceKind.RECEIVED,
        ),
        LedgerEvidenceBatchProjection,
    )
    assert settled.condition is OperationTerminalCondition.SUCCEEDED, settled
    assert isinstance(settled.published, LedgerEvidenceBatchProjection)
    return settled.published


def test_a_role_with_no_selection_refuses_its_first_document_and_pauses_the_rest(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The refusal comes at lookup, so nothing is sent, and it closes the role it names."""
    del operation
    with operation_runtime(tmp_path, ModelRunRefusalCode.NO_SELECTION) as runtime:
        projection = _settle_batch(runtime)
        runs = list(runtime.service.runs)

    first, second = projection.run.items
    assert first.status == "refused"
    assert first.refusal_verdict is not None
    assert first.refusal_verdict.to_verdict() == model_run_refusal_verdict(
        ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION), role=ModelRole.TEXT_EXTRACTION
    )
    assert second.status == "paused", "a role the service cannot serve is not asked again in the same run"
    assert projection.run.inference_pause is not None
    assert runs == [], "a role refused at lookup sends nothing"


def test_a_failed_run_on_one_document_leaves_the_role_open_for_the_next(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """A run that failed is that document's refusal; the next document of the role is still read."""
    del operation
    with operation_runtime(tmp_path, ModelRunRefusalCode.RUN_FAILED, at_run=True) as runtime:
        projection = _settle_batch(runtime)
        runs = list(runtime.service.runs)

    assert [item.status for item in projection.run.items] == ["refused", "refused"]
    assert projection.run.inference_pause is None
    sent = {body.prompt for _header, body in runs}
    for _name, lines in _DOCUMENTS:
        assert any(lines[0] in prompt for prompt in sent), "each document reached the service"


def test_an_off_host_lane_without_consent_sends_nothing_and_pauses_the_role(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The batch carries no consent, so the first document's consent refusal closes its role for the rest."""
    del operation
    assert DEFAULT_LANE.reads_off_host
    with operation_runtime(tmp_path, None, lane=DEFAULT_LANE) as runtime:
        projection = _settle_batch(runtime)
        runs = list(runtime.service.runs)

    first, second = projection.run.items
    assert first.status == "refused"
    assert first.refusal_verdict is not None
    refused = first.refusal_verdict.to_verdict()
    assert refused.failed_condition_id == "llm.evidence.off_host_dispatch_permitted"
    facts = {key: value for evidence in refused.evidence for key, value in evidence.values.items()}
    assert facts["model_role"] == ModelRole.TEXT_EXTRACTION.value
    assert facts["model_run_refusal"] == ModelRunRefusalCode.CONSENT_MISSING.value
    assert facts["consent_token_present"] is False
    assert second.status == "paused", "a role refused for consent is not asked again in the same run"
    assert projection.run.inference_pause is not None
    assert projection.run.inference_pause.precondition_verdict.to_verdict() == refused
    assert runs == [], "nothing is sent off this computer without consent"
