"""A record reaches each handler once, whichever kind of logger emitted it."""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import override

import pytest

from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS

from ..logging import flush_logging, get_logger

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_NAMESPACE = "cadrumo.tests.handler_delivery"


class _Recorder(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.NOTSET)
        self.messages: list[str] = []

    @override
    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@contextmanager
def _attached(logger: logging.Logger) -> Generator[_Recorder]:
    recorder = _Recorder()
    logger.addHandler(recorder)
    try:
        yield recorder
    finally:
        logger.removeHandler(recorder)


def test_a_stdlib_logger_record_reaches_a_root_handler_once(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger(f"{_NAMESPACE}.stdlib")

    with caplog.at_level(logging.INFO):
        logger.info("plain %s", "record")
        assert flush_logging(timeout=HANG_GUARD_SECONDS)

    assert [record.getMessage() for record in caplog.records if record.name == logger.name] == ["plain record"]


def test_a_project_logger_record_reaches_a_root_handler_once(caplog: pytest.LogCaptureFixture) -> None:
    logger = get_logger(f"{_NAMESPACE}.project")

    with caplog.at_level(logging.INFO):
        logger.info("project %s", "record")
        assert flush_logging(timeout=HANG_GUARD_SECONDS)

    assert [record.getMessage() for record in caplog.records if record.name == logger.name] == ["project record"]


@pytest.mark.parametrize("project_logger", [False, True], ids=["stdlib", "project"])
def test_a_handler_on_an_ancestor_logger_receives_a_record_once(project_logger: bool) -> None:
    ancestor = logging.getLogger(f"{_NAMESPACE}.ancestor")
    name = f"{ancestor.name}.child"
    logger = get_logger(name) if project_logger else logging.getLogger(name)

    with _attached(ancestor) as recorder:
        logger.warning("ancestor %s", "record")
        assert flush_logging(timeout=HANG_GUARD_SECONDS)

    assert recorder.messages == ["ancestor record"]
