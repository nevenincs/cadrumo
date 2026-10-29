"""A value only a finding names, such as a Modelo 349 record's, counts as missing in the header and on the next line.

A Modelo 349 form is built from the real published registry with three findings
of a missing value in the operator records, which no box of the form lists.
The header's missing chip counts the three with the boxes still empty, nothing counts them as blocking, and
the next-action line sends the filer to them with the same count, since the
issue list is where they are answered.
"""

from __future__ import annotations

import pytest

from ......application.modelo.work_form import build_modelo_work_form
from ......application.modelo.work_form_findings import ModeloFormAttention
from ......application.modelo.work_form_models import ModeloWorkForm
from ......application.modelo.work_form_next_step import (
    ModeloFormNextAction,
    blocking_count,
    missing_count,
    missing_findings,
    to_do_counts,
)
from ......application.modelo.work_form_service import modelo_form_snapshot
from ......application.modelo.work_review import (
    ModeloWorkProgress,
    ModeloWorkReview,
    build_modelo_work_review_casillas,
)
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
from ..header import attention_chips
from ..issue_projection import issue_lines
from ..issue_scale import IssueLevel
from ..progress import workbench_progress

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RECORD_VALUES = ("op.codigo-pais", "op.nif-comunitario", "op.clave-operacion")


def _missing_values(
    operation: PinnedAuthorityOperation, modelo: str, year: int, code: str, casillas: tuple[str, ...]
) -> ModeloWorkForm:
    """The form with one finding of a missing value per casilla named."""
    period = Period.from_year_and_code(year, code)
    revision_id = str(operation.revision_for_context(modelo, filing_year=year, period=code).id)
    snapshot = modelo_form_snapshot(operation, ModeloCode(modelo), year, period, revision_id)
    findings = tuple(
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            casilla_id=casilla_id,
            message_locale_key="application.modelo.findings.missing_required_casilla",
            message_facts={"casilla_id": casilla_id},
            legal_refs=("ley-37-1992:art-164",),
        )
        for casilla_id in casillas
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
    built = _missing_values(operation, "349", 2026, "1T", _RECORD_VALUES)
    form = built.model_copy(update={"calculation_revision_id": "b" * 64})
    with override_settings(cadrumo_output_language="en"):
        chips = {chip.level: chip.count for chip in attention_chips(form, recorded=False)}
        missing = missing_count(form)
        progress = workbench_progress(form, staged=0, verified=False, filed=False)

    assert len(form.issues) == len(_RECORD_VALUES)
    assert blocking_count(form) == 0
    assert ModeloFormAttention.BLOCKS not in chips
    assert chips[ModeloFormAttention.MISSING] == missing == to_do_counts(form).needs_input + len(_RECORD_VALUES)
    assert progress.next_action in {ModeloFormNextAction.FILL, ModeloFormNextAction.RESOLVE}
    assert progress.count == missing


def test_the_missing_values_only_findings_name_are_the_ones_the_findings_list_shows(
    operation: PinnedAuthorityOperation,
) -> None:
    """Record values are counted; a finding about a box the missing boxes already list is not counted again."""
    records = _missing_values(operation, "349", 2026, "1T", _RECORD_VALUES)
    listed = _missing_values(operation, "210", 2025, "0A", ("tipo_renta", "rendimientos_integros"))
    with override_settings(cadrumo_output_language="en"):
        shown = [sum(1 for line in issue_lines(form) if line.level is IssueLevel.MISSING) for form in (records, listed)]

    assert len(listed.issues) == 2
    assert [missing_findings(records), missing_findings(listed)] == shown == [len(_RECORD_VALUES), 0]
