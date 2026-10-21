"""``modelo.work.report_verify`` releases the document ``work report-verify`` prints.

The operation runs on its real executor with the real PDF reader over a real
file; only the profile's store is replaced, and a file that is not a Cadrumo
summary is refused before the store is reached, so the verdict is the one the
command gives with ``--document-only``.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pikepdf
import pytest
from pydantic import BaseModel

from ....adapters.outbound.calculation_summary_pdf.summary_reading import read_calculation_summary_pdf
from ....application.modelo.calculation_report_verification import CalculationSummaryStoreContext
from ....application.modelo.calculation_report_verification_operation import (
    MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID,
    ModeloCalculationReportVerificationPorts,
    ModeloCalculationReportVerificationProjection,
    ModeloCalculationReportVerificationRequest,
    build_modelo_calculation_report_verify_definition,
)
from ....application.modelo.export_ports import ModeloExportPorts
from ....application.modelo.review_package_signing_ports import ReviewPackageSigningKeypairReader
from ....application.operations.models import OperationRequest
from ....application.operations.owner import OperationExecutorContext
from ....core.config import override_settings
from ....core.hashing import sha256_hex
from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")


def _document_without_a_report(tmp_path: Path) -> Path:
    path = tmp_path / "plain.pdf"
    with pikepdf.new() as pdf:
        pdf.add_blank_page()
        pdf.save(path)
    return path


def _released(path: Path, *, source_sha256: str | None) -> ModeloCalculationReportVerificationProjection:
    def factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> ModeloCalculationReportVerificationPorts:
        return ModeloCalculationReportVerificationPorts(
            profile_id=profile_id,
            reader=read_calculation_summary_pdf,
            store=CalculationSummaryStoreContext(
                active_bucket_id=str(profile_id),
                export_ports=cast(ModeloExportPorts, object()),
                signing_keypair=cast(ReviewPackageSigningKeypairReader, object()),
                operation=operation,
            ),
        )

    stored: list[BaseModel] = []
    effects: list[OperationEffect] = []

    class Events:
        async def phase(self, _phase: str) -> None:
            pass

        async def effect(self, effect: OperationEffect) -> None:
            effects.append(effect)

    class Operands:
        async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
            stored.append(operand)
            return "f" * 64

    definition = build_modelo_calculation_report_verify_definition(factory)
    request = OperationRequest[BaseModel](
        definition_id=MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ModeloCalculationReportVerificationRequest(
            profile_id=_PROFILE, source_path=str(path), source_sha256=source_sha256
        ),
    )
    context = cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=SimpleNamespace(definition_id=request.definition_id, subject_ref=request.subject_ref),
                authority_operation=cast(PinnedAuthorityOperation, object()),
                events=Events(),
                operands=Operands(),
            ),
        ),
    )
    with override_settings(cadrumo_active_profile=str(_PROFILE)):
        asyncio.run(definition.executor_factory.create().execute(request, context))
    assert effects == [OperationEffect.NONE]
    return ModeloCalculationReportVerificationProjection.model_validate(stored[0])


@pytest.mark.parametrize("supplied", [True, False], ids=["digest-supplied", "digest-left-to-the-operation"])
def test_the_operation_result_is_the_document_the_command_prints(tmp_path: Path, supplied: bool) -> None:
    path = _document_without_a_report(tmp_path)
    digest = sha256_hex(path.read_bytes())

    projection = _released(path, source_sha256=digest if supplied else None)
    command = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "report-verify", str(path), "--document-only"]
    )
    printed = json.loads(command.output)["result"]
    released = projection.model_dump(mode="json", exclude={"result_version", "profile_id", "source_sha256"})

    assert command.exit_code == 1
    assert released == printed
    assert printed["outcome"] == "refused"
    # What the operation adds to the command's document: the profile and the digest of the bytes verified.
    assert (projection.profile_id, projection.source_sha256) == (_PROFILE, digest)
