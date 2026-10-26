"""``aeat app ledger evidence page`` writes the drawn page the registered read returns, and nothing else."""

from __future__ import annotations

import base64
import hashlib
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer
from PIL import Image
from pydantic import BaseModel

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.transport.frontend_client import FrontendClient

from ....adapters.inbound.pdf.page_image import PageImageRenderer
from ....application.ledger.evidence_page_contracts import (
    EVIDENCE_PAGE_IMAGE_URL_PREFIX,
    EVIDENCE_PAGE_MAX_IMAGE_BYTES,
    LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID,
    EvidencePageMediaType,
    LedgerEvidencePageProjection,
    LedgerEvidencePageRequest,
)
from ....application.operations.models import OperationId
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....tests.pdf_fixtures import multi_page_text_pdf_bytes
from .. import ledger_evidence_commands as commands
from .. import operation_ledger_evidence_page as bridge
from ..command_specs import COMMAND_GRAPH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_EVIDENCE_ID = "ev-page-1"
_PDF = multi_page_text_pdf_bytes(("Factura",), ("Anexo",))
_ATTACHMENT_ID = hashlib.sha256(_PDF).hexdigest()


def _drawn_page() -> tuple[LedgerEvidencePageProjection, bytes]:
    """A page the real renderer drew, as the worker would return it."""
    drawn = PageImageRenderer().render(
        _PDF, media_type=EvidencePageMediaType.PDF, page=2, max_width=500, max_image_bytes=EVIDENCE_PAGE_MAX_IMAGE_BYTES
    )
    projection = LedgerEvidencePageProjection(
        profile_id=_PROFILE,
        evidence_id=_EVIDENCE_ID,
        attachment_id=_ATTACHMENT_ID,
        media_type=EvidencePageMediaType.PDF,
        page=2,
        page_count=drawn.page_count,
        width=drawn.width,
        height=drawn.height,
        source_sha256=_ATTACHMENT_ID,
        file_name="factura.pdf",
        image_data_url=EVIDENCE_PAGE_IMAGE_URL_PREFIX + base64.b64encode(drawn.png).decode("ascii"),
    )
    return projection, drawn.png


def _bind(monkeypatch: pytest.MonkeyPatch, projection: BaseModel, submitted: list[BaseModel]) -> None:
    client = cast(FrontendClient, SimpleNamespace(profile_id=_PROFILE))
    monkeypatch.setattr(bridge, "active_bucket_id_or_refuse", lambda: str(_PROFILE))
    monkeypatch.setattr(bridge, "require_profile_client", lambda _ctx, *, expected_profile_id: client)

    def submit(
        actual_client: FrontendClient, request: BaseModel, **kwargs: object
    ) -> RegisteredOperationCompletion[BaseModel]:
        submitted.append(request)
        assert actual_client is client
        assert kwargs["definition_id"] == LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is LedgerEvidencePageProjection
        return RegisteredOperationCompletion(
            operation_id=cast("OperationId", "f" * 64),
            projection=projection,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    monkeypatch.setattr(commands, "emit_envelope", lambda *_args, **_kwargs: None)


def test_the_command_is_registered_for_the_page_read_and_writes_to_output() -> None:
    node = next(node for node in COMMAND_GRAPH.nodes() if node.path == ("aeat", "app", "ledger", "evidence", "page"))
    assert node.spec.result_schema.identity == LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID
    names = {parameter.name for parameter in node.spec.parameters}
    assert names == {"output", "evidence_id", "attachment_id", "page", "max_width"}


def test_the_drawn_page_is_written_to_the_named_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    projection, png = _drawn_page()
    submitted: list[BaseModel] = []
    _bind(monkeypatch, projection, submitted)
    output = tmp_path / "pages" / "factura-2.png"

    commands.evidence_page(
        cast(typer.Context, cast(object, None)), output, evidence_id=_EVIDENCE_ID, page=2, max_width=500
    )

    assert submitted == [
        LedgerEvidencePageRequest(profile_id=_PROFILE, evidence_id=_EVIDENCE_ID, page=2, max_width=500)
    ]
    assert output.read_bytes() == png
    assert Image.open(BytesIO(output.read_bytes()), formats=("PNG",)).size == (projection.width, projection.height)


@pytest.mark.parametrize(
    ("evidence_id", "attachment_id"),
    [(None, None), (_EVIDENCE_ID, _ATTACHMENT_ID)],
    ids=["neither", "both"],
)
def test_the_command_names_exactly_one_document(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, evidence_id: str | None, attachment_id: str | None
) -> None:
    submitted: list[BaseModel] = []
    _bind(monkeypatch, _drawn_page()[0], submitted)
    output = tmp_path / "page.png"

    with pytest.raises(typer.BadParameter):
        commands.evidence_page(
            cast(typer.Context, cast(object, None)), output, evidence_id=evidence_id, attachment_id=attachment_id
        )

    assert submitted == []
    assert not output.exists()


def test_a_result_for_another_page_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    projection, _ = _drawn_page()
    _bind(monkeypatch, projection, [])
    output = tmp_path / "page.png"

    with pytest.raises(CliRefusedBoundaryError):
        commands.evidence_page(cast(typer.Context, cast(object, None)), output, evidence_id=_EVIDENCE_ID, page=1)

    assert not output.exists()
