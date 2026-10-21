"""A settled operation's result is paged, and a stopped one is worded from what it recorded."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from .....application.operations.error_detail import (
    OperationErrorContextEntryV1,
    OperationErrorDetailKind,
    OperationErrorDetailV1,
)
from .....application.operator_actions.models import PreconditionVerdict
from .....application.operator_actions.preconditions import (
    no_action_precondition_verdict,
    profile_setup_incomplete_verdict,
)
from .....core.errors.error_codes import render_error_text
from .....core.errors.hierarchy import RecordedRegisteredError
from .....core.i18n.render import tr
from .....core.models import STRICT_FROZEN_CONFIG
from .....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ..run_result import RESULT_PAGE_LINES, result_pages, stopped_operation_text

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CODE = "REFUSED_AUTH_CERTIFICATE_SOURCE_NOT_FOUND"


class _Row(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    index: int
    label: str


class _Listing(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    title: str
    rows: tuple[_Row, ...]


def test_a_short_result_is_one_page_of_its_own_json() -> None:
    listing = _Listing(title="Año 2026", rows=(_Row(index=1, label="uno"),))

    pages = result_pages(listing)

    assert len(pages) == 1
    assert json.loads(pages[0]) == {"title": "Año 2026", "rows": [{"index": 1, "label": "uno"}]}
    assert "Año" in pages[0]


def test_a_long_result_is_cut_into_bounded_pages_that_rejoin_into_the_whole() -> None:
    listing = _Listing(title="long", rows=tuple(_Row(index=index, label=f"row {index}") for index in range(300)))

    pages = result_pages(listing)

    assert len(pages) > 1
    assert all(len(page.splitlines()) <= RESULT_PAGE_LINES for page in pages)
    assert all(len(page.splitlines()) == RESULT_PAGE_LINES for page in pages[:-1])
    assert json.loads("\n".join(pages)) == listing.model_dump(mode="json")


def test_a_stopped_operation_shows_its_recorded_code_and_the_message_the_command_line_prints() -> None:
    detail = OperationErrorDetailV1(
        kind=OperationErrorDetailKind.REGISTERED_ERROR,
        error_code=_CODE,
        message_key=None,
        context=(OperationErrorContextEntryV1(key="name", value="synthetic-source"),),
    )

    text = stopped_operation_text(detail)

    printed = render_error_text(RecordedRegisteredError(_CODE, context={"name": "synthetic-source"})).rstrip()
    assert text.splitlines()[0] == f"{tr('tui.operations.stopped.code')}: {_CODE}"
    assert printed in text
    assert "synthetic-source" in text
    assert tr("tui.operations.stopped.remedy") not in text


def _stopped_with(verdict: PreconditionVerdict) -> OperationErrorDetailV1:
    return OperationErrorDetailV1(
        kind=OperationErrorDetailKind.REGISTERED_ERROR,
        error_code=_CODE,
        message_key=None,
        context=(),
        precondition_verdict_json=verdict.model_dump_json(),
    )


def test_a_stopped_operation_names_the_remedy_command_beneath_its_verdict() -> None:
    verdict = profile_setup_incomplete_verdict(modelo="303", missing_required_field_count=1)

    lines = stopped_operation_text(_stopped_with(verdict)).splitlines()

    heading = lines.index(f"{tr('tui.operations.stopped.remedy')}:")
    assert json.loads("".join(lines[heading + 1 : -1])) == json.loads(verdict.model_dump_json())
    assert lines[-1] == tr("tui.operations.stopped.remedy_command", command="aeat config profile complete-setup")


def test_a_verdict_that_names_no_action_is_shown_without_a_remedy_command() -> None:
    verdict = no_action_precondition_verdict(
        condition_id="storage.root.unreadable",
        facts={"readable": False},
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )

    lines = stopped_operation_text(_stopped_with(verdict)).splitlines()

    heading = lines.index(f"{tr('tui.operations.stopped.remedy')}:")
    # Everything beneath the heading is the verdict: a line after it would not parse as its JSON.
    assert json.loads("".join(lines[heading + 1 :])) == json.loads(verdict.model_dump_json())


def test_an_operation_that_recorded_no_registered_detail_adds_nothing_to_its_receipt() -> None:
    fault = OperationErrorDetailV1(
        kind=OperationErrorDetailKind.RECORD_VALIDATION, error_code=None, message_key=None, context=()
    )

    assert stopped_operation_text(None) == ""
    assert stopped_operation_text(fault) == ""
