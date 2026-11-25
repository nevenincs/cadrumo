"""The exception-hygiene scans must report each defect they exist to find."""

from __future__ import annotations

import ast

import pytest

from .exception_hygiene_scan import (
    bare_excepts,
    broad_handlers_without_raise_or_log,
    contextlib_suppress_uses,
    swallowed_with_pass,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DEFECTIVE = ast.parse(
    """
import contextlib
from contextlib import suppress

def swallow():
    try:
        work()
    except ValueError:
        pass

def bare():
    try:
        work()
    except:
        recover()

def silent_broad():
    try:
        work()
    except (OSError, Exception):
        recover()

def suppressing():
    with contextlib.suppress(OSError):
        work()
    with suppress(OSError):
        work()
"""
)

_CLEAN = ast.parse(
    """
def handled(log):
    try:
        work()
    except Exception:
        log.warning("failed")
    try:
        work()
    except BaseException:
        raise
    try:
        work()
    except ValueError:
        recover()
"""
)


def test_each_scan_reports_the_defect_it_names() -> None:
    assert [node.lineno for node in swallowed_with_pass(_DEFECTIVE)] == [8]
    assert [node.lineno for node in bare_excepts(_DEFECTIVE)] == [14]
    assert [node.lineno for node in broad_handlers_without_raise_or_log(_DEFECTIVE)] == [20]
    assert [node.lineno for node in contextlib_suppress_uses(_DEFECTIVE)] == [24, 26]


def test_handled_exceptions_are_not_reported() -> None:
    assert swallowed_with_pass(_CLEAN) == []
    assert bare_excepts(_CLEAN) == []
    assert broad_handlers_without_raise_or_log(_CLEAN) == []
    assert contextlib_suppress_uses(_CLEAN) == []
