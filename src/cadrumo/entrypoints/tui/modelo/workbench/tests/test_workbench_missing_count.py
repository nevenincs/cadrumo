"""A value only a finding names, such as a Modelo 349 record's, counts as missing in the header and on the next line.

A Modelo 349 form is built from the real published registry with five findings
of a missing value in the operator records, which no box of the form lists.
The header's missing chip counts the five, nothing counts them as blocking, and
the next-action line sends the filer to them with the same count, since the
issue list is where they are answered.
"""

from __future__ import annotations

import pytest

from ......application.modelo.work_form import build_modelo_work_form
from ......application.modelo.work_form_service import modelo_form_snapshot
from ......application.modelo.work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.modelo_work_progress_state import ModeloWorkProgressState
from ......core.period import Period
from ......domain.calculations.registry.authority import PinnedAuthorityOperation
from ......domain.modelos.codes import ModeloCode
from ......domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ..header import ChipLevel, attention_chips, blocking_count, missing_count
from ..progress import NextAction, workbench_progress

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RECORD_VALUES = (
    "op.codigo-pais",
    "op.nif-comunitario",
    "op.clave-operacion",
    "op.nombre",
    "op.base-imponible",
)


def _missing_record_values(operation: PinnedAuthorityOperation) -> object:
    modelo, year, code = "349", 2026, "1T"
    period = Period.from_year_and_code(year, code)
    revision_id = str(operation.revision_for_context(modelo, filing_year=year, period=code).id)
    snapshot = modelo_form_snapshot(operation, ModeloCode(modelo), year, period, revision_id)
    known = {str(casilla.casilla_id) for casilla in snapshot.revision.casillas}
    findings = tuple(
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            casilla_id=casilla_id,
            message_locale_key="application.modelo.findings.missing_required_casilla",
            message_facts={"casilla_id": casilla_id},
            legal_refs=("ley-37-1992:art-164",),
        )
        for casilla_id in _RECORD_VALUES
        if casilla_id in known
    )
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000349",
        modelo=modelo,
        filing_year=year,
        period=period,
        registry_revision_id=snapshot.revision.id,
        work_unit_id="e" * 64,
        calculation_revision_id=None,
        lifecycle_state=None,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation),
        findings=findings,
        blockers=(),
    )
    return build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=operation.form_layout(modelo, snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=None,
        overridden_binding_ids=None,
        language=OutputLanguage.EN,
    )


def test_missing_record_values_count_in_the_missing_chip_and_on_the_next_line(
    operation: PinnedAuthorityOperation,
) -> None:
    built = _missing_record_values(operation)
    form = built.model_copy(update={"calculation_revision_id": "b" * 64})
    with override_settings(cadrumo_output_language="en"):
        chips = {chip.level: chip.count for chip in attention_chips(form, recorded=False)}
        missing = missing_count(form)
        progress = workbench_progress(form, staged=0, verified=False, filed=False)

    assert len(form.issues) == len(_RECORD_VALUES), "every record value is a field of the published revision"
    assert blocking_count(form) == 0
    assert ChipLevel.BLOCKS not in chips
    assert chips[ChipLevel.MISSING] == missing >= len(_RECORD_VALUES)
    assert progress.next_action in {NextAction.FILL, NextAction.RESOLVE}
    assert progress.count == missing
