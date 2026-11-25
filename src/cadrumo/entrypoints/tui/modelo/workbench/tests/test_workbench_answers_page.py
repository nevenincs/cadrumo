"""The workbench draws the answers no page of the form takes on a page of their own, headed as the outline heads them.

The first-quarter Modelo 130 is built by the real form builder over the
published registry; its layout prints no field for the earlier-year answers its
calculation reads, so the form serves them among its answers.
"""

from __future__ import annotations

import pytest

from ......application.modelo.tests.work_form_fixture import built_form
from ......application.modelo.work_form_models import ModeloFormOutlineKind
from ......domain.calculations.registry.authority import PinnedAuthorityOperation
from ..page_items import ANSWERS_PAGE_ID, DETAILS_PAGE_ID, workbench_pages

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_the_answers_stand_on_their_own_page_after_the_calculation_details(
    operation: PinnedAuthorityOperation,
) -> None:
    form = built_form(operation, "130", 2025, "1T")
    assert form.answers

    pages = workbench_pages(form)

    answers = pages[-1]
    assert answers.id == ANSWERS_PAGE_ID
    assert answers.fields() == form.answers
    (group,) = (group for group in form.outline if group.kind is ModeloFormOutlineKind.ANSWERS)
    assert answers.heading == group.heading
    details = next((page for page in pages if page.id == DETAILS_PAGE_ID), None)
    assert details is None or not any(field in form.answers for field in details.fields())


def test_a_form_without_answers_has_no_answers_page(operation: PinnedAuthorityOperation) -> None:
    form = built_form(operation, "303", 2026, "1T")

    assert all(page.id != ANSWERS_PAGE_ID for page in workbench_pages(form))
