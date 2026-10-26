"""Benchmark scopes cannot leak a worker or observer into later sequences."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import copy_context
from pathlib import Path

import pytest

from .. import runner, runtime_fixture

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def test_nested_worker_selection_restores_after_failure_and_copies_to_thread_context(tmp_path: Path) -> None:
    outer = tmp_path / "outer.py"
    inner = tmp_path / "inner.py"
    outer.write_text("", encoding="utf-8")
    inner.write_text("", encoding="utf-8")
    previous = runtime_fixture._WORKER_SCRIPT.get()

    with runtime_fixture.sequence_worker_script(outer):
        assert runtime_fixture._WORKER_SCRIPT.get() == outer.resolve()
        with pytest.raises(RuntimeError), runtime_fixture.sequence_worker_script(inner):
            assert copy_context().run(runtime_fixture._WORKER_SCRIPT.get) == inner.resolve()
            raise RuntimeError("leave the inner benchmark scope")
        assert runtime_fixture._WORKER_SCRIPT.get() == outer.resolve()

    assert runtime_fixture._WORKER_SCRIPT.get() == previous


def test_missing_worker_is_refused_without_changing_the_selected_scope(tmp_path: Path) -> None:
    previous = runtime_fixture._WORKER_SCRIPT.get()

    with pytest.raises(FileNotFoundError), runtime_fixture.sequence_worker_script(tmp_path / "missing.py"):
        pytest.fail("missing workers must never enter their selection scope")

    assert runtime_fixture._WORKER_SCRIPT.get() == previous


def test_nested_frame_observer_restores_after_failure() -> None:
    observed: list[tuple[str, int]] = []

    @contextmanager
    def outer(index: int) -> Generator[None]:
        observed.append(("outer", index))
        yield

    @contextmanager
    def inner(index: int) -> Generator[None]:
        observed.append(("inner", index))
        yield

    previous = runner._FRAME_OBSERVER.get()
    with runner.observe_sequence_frames(outer):
        with pytest.raises(RuntimeError), runner.observe_sequence_frames(inner):
            selected = runner._FRAME_OBSERVER.get()
            assert selected is inner
            with selected(2):
                raise RuntimeError("leave the inner benchmark observer")
        selected = runner._FRAME_OBSERVER.get()
        assert selected is outer
        with selected(3):
            pass

    assert runner._FRAME_OBSERVER.get() is previous
    assert observed == [("inner", 2), ("outer", 3)]
