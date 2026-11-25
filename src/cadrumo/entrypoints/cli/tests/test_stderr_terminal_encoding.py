"""Stderr funnels render untrusted text inert while keeping their deliberate controls."""

from __future__ import annotations

import io
import json

import pytest

from cadrumo_client.commands.output import write_stderr as write_client_stderr

from ....core.errors.error_codes import render_error_json
from ....core.output_rendering import OutputRenderingError
from ..errors import write_stderr

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ESC = chr(0x1B)
_RLO = chr(0x202E)
_HOSTILE = f"Cafe{_ESC}]52;c;cHduZWQ={chr(0x07)}\rRefund 9999{_RLO}gnp.exe{chr(0x9B)}31m"
_UNSAFE = frozenset([chr(code) for code in (0x07, 0x0D, 0x1B, 0x9B, 0x202E)])


def test_cli_stderr_funnel_renders_controls_inert_and_keeps_separators() -> None:
    stream = io.StringIO()

    write_stderr(f"refused:\t{_HOSTILE}\n", stream=stream)

    written = stream.getvalue()
    assert not _UNSAFE.intersection(written)
    assert written.startswith("refused:\tCafe\\u001b]52;")
    assert written.endswith("\\u009b31m\n")


def test_cli_stderr_funnel_keeps_a_json_error_document_valid() -> None:
    stream = io.StringIO()
    document = render_error_json(
        OutputRenderingError(
            context={"type_name": _HOSTILE},
            translated_message="errors.internal.internal_output_rendering",
        ),
    )
    # json.dumps(ensure_ascii=False) leaves C1 and bidi controls raw in the document.
    assert {chr(0x9B), _RLO} <= set(document)

    write_stderr(document, stream=stream)

    written = stream.getvalue()
    assert not _UNSAFE.intersection(written)
    assert json.loads(written) == json.loads(document)


def test_client_stderr_funnel_renders_controls_inert() -> None:
    stream = io.StringIO()

    write_client_stderr(_HOSTILE, stream=stream)

    written = stream.getvalue()
    assert not _UNSAFE.intersection(written)
    assert written.endswith("31m\n")
