"""Observability sink inheritance contract."""

import logging

import pytest

from ..observability.sink import JsonlRunSink

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_sink_is_logging_handler_subclass() -> None:
    assert issubclass(JsonlRunSink, logging.Handler)
