"""A packaged command's JSON envelope is read whether it spans lines or follows startup diagnostics."""

from __future__ import annotations

import json

import pytest

from ..caller_owned_root import parse_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_an_indented_envelope_is_read_whole() -> None:
    envelope = {"ok": True, "result": {"session_persisted": True}, "notices": []}
    assert parse_envelope(json.dumps(envelope, indent=2), "") == envelope


def test_a_one_line_envelope_after_startup_diagnostics_is_read() -> None:
    stderr = 'starting runtime client\n{"ok": false, "error": {"code": "REFUSED_LOCAL_RUNTIME"}}\n'
    assert parse_envelope("", stderr) == {"ok": False, "error": {"code": "REFUSED_LOCAL_RUNTIME"}}


def test_output_that_is_not_an_envelope_is_marked_unparsed() -> None:
    assert parse_envelope("not json\nstill not json", "") == {"unparsed_output": True}


def test_no_output_is_an_empty_envelope() -> None:
    assert parse_envelope("", "") == {}
