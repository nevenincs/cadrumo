"""Typed ``--json`` payload schema for the ``aeat app quickfile`` envelope.

Projects the application :class:`~application.modelo.QuickfileResult` onto a
strict :class:`~entrypoints.cli._schemas.OutputSchema` registered under the
``quickfile`` command path. The per-stage outcomes and the terminal export
receipt (path reference only — never raw fichero bytes) are surfaced so a machine
consumer can read exactly which stage the chain reached and where it halted.
"""

from __future__ import annotations

from ...application.modelo import QuickfileResult
from ...core import Period
from ._modelo_payloads import ModeloExportPayload
from ._schemas import OutputSchema, register_schema


class QuickfileStageOutcomePayload(OutputSchema):
    """One quickfile stage's outcome projected for the JSON envelope.

    ``stage`` is a :class:`~application.modelo.QuickfileStage` value and
    ``status`` a :class:`~application.modelo.QuickfileStageStatus` value;
    both are surfaced as their string form. ``context`` carries the stage's
    structured refs (work-unit id, revision id, refusal counts) verbatim.
    """

    stage: str
    status: str
    message: str = ""
    context: dict[str, str] = {}


@register_schema("quickfile")
class QuickfileResultPayload(OutputSchema):
    """Aggregate ``aeat app quickfile`` result envelope.

    ``completed`` is true only when the terminal local fichero-BOE export
    succeeded. ``stopped_at_stage`` names the stage that refused when the chain
    halted early. ``export`` is the path-reference export receipt (never raw
    bytes) and is ``None`` when the chain stopped before export.
    """

    operation: str = "quickfile"
    modelo: str
    filing_year: int
    period: Period
    registry_revision_id: str
    completed: bool
    stopped_at_stage: str | None = None
    work_unit_id: str | None = None
    calculation_revision_id: str | None = None
    granted_verificado_completo: bool | None = None
    export: ModeloExportPayload | None = None
    stages: tuple[QuickfileStageOutcomePayload, ...]

    @classmethod
    def from_result(cls, result: QuickfileResult) -> QuickfileResultPayload:
        """Project the application :class:`QuickfileResult` into this :class:`QuickfileResultPayload` envelope."""
        granted = result.verification_report.granted_verificado_completo if result.verification_report else None
        return cls(
            modelo=result.modelo,
            filing_year=result.filing_year,
            period=result.period,
            registry_revision_id=result.registry_revision_id,
            completed=result.completed,
            stopped_at_stage=result.stopped_at_stage.value if result.stopped_at_stage is not None else None,
            work_unit_id=result.work_unit.work_unit_id if result.work_unit is not None else None,
            calculation_revision_id=(
                result.calculation_revision.calculation_revision_id if result.calculation_revision is not None else None
            ),
            granted_verificado_completo=granted,
            export=ModeloExportPayload.from_result(result.export_result) if result.export_result is not None else None,
            stages=tuple(
                QuickfileStageOutcomePayload(
                    stage=outcome.stage.value,
                    status=outcome.status.value,
                    message=outcome.message,
                    context=dict(outcome.context),
                )
                for outcome in result.stages
            ),
        )


__all__ = ["QuickfileResultPayload", "QuickfileStageOutcomePayload"]
