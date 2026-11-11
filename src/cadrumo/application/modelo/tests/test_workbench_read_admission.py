"""The form read says why a declaration cannot be edited, and whether its rules stop short of calculating it.

A frontend shows the admission refusal in its own words and never infers that
the registry rules are incomplete from a missing next step: the read states
both, in the form's language, and its public envelope carries them unchanged.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ..edit_admission import RESPONSIBLE_OWNER
from ..edit_models import ModeloEditDomainRefusalV1, ModeloEditRefusalCode, ModeloEditRefusedV1
from ..edit_review_wording import edit_refusal_words
from ..work_form_service import ModeloWorkFormLoadV1
from ..workbench_projection import (
    ModeloWorkbenchFormProjectionV1,
    project_modelo_workbench_form,
    restore_modelo_workbench_form,
)
from ..workbench_read import ModeloWorkbenchFormReadV1
from .work_form_fixture import built_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("13000000-0000-4000-8000-000000000455")


def _refusal(*facts: str) -> ModeloEditRefusedV1:
    return ModeloEditRefusedV1(
        refusal=ModeloEditDomainRefusalV1(
            code=ModeloEditRefusalCode.ADMISSION_DENIED,
            facts=facts,
            responsible_owner=RESPONSIBLE_OWNER,
            reconsideration_condition="edit a modelo revision whose registry authority reaches calculation grade",
        )
    )


def _read(operation: PinnedAuthorityOperation, admission: ModeloEditRefusedV1, language: OutputLanguage):
    form = built_form(operation, "210", 2025, "0A", entered=frozenset(), language=language)
    return ModeloWorkbenchFormReadV1(
        load=ModeloWorkFormLoadV1(form=form, verified=False, filed=False),
        admission=admission,
        calculation_revision_id=None,
        verification_report_id=None,
        asks_m303_evidence=False,
        asks_modelo_390=False,
        registry_revision_id=form.registry_revision_id,
        tax_id_format=runtime_tax_id_format(authority=operation),
    )


@pytest.mark.parametrize(
    ("facts", "incomplete"),
    [(("registry_authority_grade",), True), (("current_calculation_revision_id",), False)],
)
def test_the_read_says_the_refusal_in_the_forms_language_and_whether_the_rules_are_incomplete(
    operation: PinnedAuthorityOperation, facts: tuple[str, ...], incomplete: bool
) -> None:
    admission = _refusal(*facts)
    read = _read(operation, admission, OutputLanguage.ES)

    assert read.admission_refusal_words == edit_refusal_words(admission.refusal, OutputLanguage.ES)
    assert read.admission_refusal_words != edit_refusal_words(admission.refusal, OutputLanguage.EN)
    assert read.rules_incomplete is incomplete
    assert (read.next_step is None) is incomplete

    projection = project_modelo_workbench_form(_PROFILE, read.load.form.work_unit_id, read)
    assert projection.admission_refusal_words == read.admission_refusal_words
    assert projection.rules_incomplete is incomplete
    public = ModeloWorkbenchFormProjectionV1.model_validate_json(projection.model_dump_json())
    assert restore_modelo_workbench_form(public).admission_refusal_words == read.admission_refusal_words
