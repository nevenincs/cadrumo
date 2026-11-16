"""The shared text-transport notice rows."""

from __future__ import annotations

import pytest

from cadrumo.application.operator_output.text_transport import notice_lines
from cadrumo.core.json_contract import Notice, NoticeSeverity

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_notice_lines_render_code_and_message_as_tab_rows() -> None:
    notices = (
        Notice(severity=NoticeSeverity.INFO, code="a.b", message="first"),
        Notice(severity=NoticeSeverity.WARNING, code="c.d", message="second"),
    )

    assert notice_lines(notices) == ("notice\ta.b\tfirst", "notice\tc.d\tsecond")
    assert notice_lines(()) == ()
