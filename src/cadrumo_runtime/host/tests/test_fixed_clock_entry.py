"""The runtime and its profile workers refuse an unbound fixed clock at entry, and serve an admitted one."""

from __future__ import annotations

import json
from argparse import Namespace
from collections.abc import Callable, Mapping
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.core.time.clock import wall_now
from cadrumo.core.time.fixed_clock import (
    FIXED_CLOCK_INSTANT_VARIABLE,
    FIXED_CLOCK_ROOT_VARIABLE,
    FixedClockRefusal,
    fixed_clock_marker_path,
)
from cadrumo_client.contracts.contracts import ExitReason, RefusalCode, RefusalError, ServerHello
from cadrumo_client.transport.frame_io import decode_document, document_frame

from ..arguments import parse_runtime_arguments
from ..main import admitted_fixed_clock, run
from ..worker import admitted_worker_fixed_clock

pytestmark = [pytest.mark.hex_entrypoint]

_FRAME_HEADER_BYTES = 5
"""One kind byte and a four-byte payload length precede every frame's payload."""


def _past_instant_text() -> str:
    return (wall_now() - timedelta(days=400)).replace(microsecond=0).isoformat()


def _runtime_options(root: Path) -> Namespace:
    return parse_runtime_arguments(
        ["--storage-root", str(root), "--storage-identity", "0" * 64, "--expected-version", version("cadrumo")]
    )


@pytest.mark.integration
def test_the_runtime_refuses_a_lone_fixed_clock_slot_at_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(FIXED_CLOCK_ROOT_VARIABLE, raising=False)
    monkeypatch.setenv(FIXED_CLOCK_INSTANT_VARIABLE, _past_instant_text())

    code = run(_runtime_options(tmp_path))

    assert code == ExitReason.ROOT_MISMATCH.value
    assert capsys.readouterr().err == RefusalCode.ROOT_MISMATCH.value + "\n"
    # Refused before the endpoint exists: nothing was created beneath the root.
    assert not tuple(tmp_path.iterdir())


@pytest.mark.unit
def test_the_runtime_refuses_a_marked_root_started_on_wall_time(tmp_path: Path) -> None:
    marker = fixed_clock_marker_path(tmp_path)
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({"instant": _past_instant_text()}), encoding="utf-8")

    with pytest.raises(RefusalError) as error:
        admitted_fixed_clock(tmp_path, {})

    assert error.value.reason is RefusalCode.ROOT_MISMATCH
    assert error.value.check == FixedClockRefusal.MARKED_ROOT_WITHOUT_FIXED_CLOCK.value


@pytest.mark.unit
@pytest.mark.parametrize(
    ("environ_of", "refusal"),
    [
        pytest.param(lambda _root: {FIXED_CLOCK_ROOT_VARIABLE: "x"}, FixedClockRefusal.LONE_VARIABLE, id="lone"),
        pytest.param(
            lambda root: {FIXED_CLOCK_INSTANT_VARIABLE: "not an instant", FIXED_CLOCK_ROOT_VARIABLE: str(root)},
            FixedClockRefusal.INSTANT_NOT_UTC,
            id="not-utc",
        ),
        pytest.param(
            lambda root: {
                FIXED_CLOCK_INSTANT_VARIABLE: _past_instant_text(),
                FIXED_CLOCK_ROOT_VARIABLE: str(root / "x"),
            },
            FixedClockRefusal.ROOT_MISMATCH,
            id="root-mismatch",
        ),
    ],
)
def test_a_worker_repeats_the_runtime_checks_at_entry(
    tmp_path: Path, environ_of: Callable[[Path], Mapping[str, str]], refusal: FixedClockRefusal
) -> None:
    with pytest.raises(RefusalError) as error:
        admitted_worker_fixed_clock(tmp_path, environ_of(tmp_path))

    assert error.value.reason is RefusalCode.ROOT_MISMATCH
    assert error.value.check == refusal.value


@pytest.mark.unit
def test_a_worker_admits_the_clock_its_runtime_admitted(tmp_path: Path) -> None:
    instant = _past_instant_text()

    admitted = admitted_worker_fixed_clock(
        tmp_path, {FIXED_CLOCK_INSTANT_VARIABLE: instant, FIXED_CLOCK_ROOT_VARIABLE: str(tmp_path)}
    )

    assert admitted is not None
    assert admitted.instant.isoformat() == instant
    assert admitted_worker_fixed_clock(tmp_path, {}) is None


@pytest.mark.unit
def test_the_hello_serves_an_admitted_instant_and_omits_it_on_wall_time() -> None:
    fixed = (wall_now() - timedelta(days=400)).replace(microsecond=0)
    on_wall = ServerHello(product_version=version("cadrumo"), storage_identity="0" * 64, boot_id=uuid4())
    on_fixed = on_wall.model_copy(update={"fixed_clock_instant": fixed})

    wall_payload = document_frame(on_wall)[_FRAME_HEADER_BYTES:]
    fixed_payload = document_frame(on_fixed)[_FRAME_HEADER_BYTES:]

    assert "fixed_clock_instant" not in json.loads(wall_payload)
    assert decode_document(wall_payload, ServerHello).fixed_clock_instant is None
    assert decode_document(fixed_payload, ServerHello).fixed_clock_instant == fixed
