"""Golden refresh publishes complete files and preserves prior data on failure."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cadrumo.core import atomic_write

from ..golden_store import golden_path, read_golden, write_golden
from ..runner import FrameExecution, SequenceTranscript
from ..schema import FrameKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_PAGE = "tutorials/publication"
_SEQUENCE_ID = "publication"
_PREVIOUS = b"previous reviewed golden\n"


def _transcript(root: Path) -> SequenceTranscript:
    return SequenceTranscript(
        sequence_id=_SEQUENCE_ID,
        profile_id="publication-profile",
        frozen_instant=datetime(2026, 1, 1, tzinfo=UTC),
        storage_root=str(root / "storage"),
        workdir=str(root / "workdir"),
        frames=(
            FrameExecution(
                kind=FrameKind.RESULT,
                command_line="aeat --help",
                argv=("aeat", "--help"),
                exit_code=0,
                output="Información fiscal\n",
            ),
        ),
    )


@pytest.mark.parametrize("existing", [False, True])
def test_golden_is_complete_before_replacing_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: bool
) -> None:
    """The real replace sees complete UTF-8 bytes while prior data is intact."""
    target = golden_path(_PAGE, _SEQUENCE_ID, goldens_root=tmp_path)
    target.parent.mkdir(parents=True)
    if existing:
        target.write_bytes(_PREVIOUS)
    replace = os.replace
    publications: list[Path] = []

    def publish(source: Path, destination: Path) -> None:
        assert destination == target
        assert source != target and source.parent == target.parent
        if existing:
            assert target.read_bytes() == _PREVIOUS
        else:
            assert not target.exists()
        payload = source.read_bytes()
        assert "Información fiscal".encode() in payload
        assert payload.endswith(b"\n") and b"\r\n" not in payload
        publications.append(source)
        replace(source, destination)

    monkeypatch.setattr(atomic_write.os, "replace", publish)

    assert write_golden(_transcript(tmp_path), page=_PAGE, goldens_root=tmp_path) == target
    assert len(publications) == 1
    assert read_golden(_PAGE, _SEQUENCE_ID, goldens_root=tmp_path).frames[0].text == "Información fiscal\n"
    assert list(target.parent.iterdir()) == [target]


@pytest.mark.parametrize("failure_point", ["fsync", "replace"])
@pytest.mark.parametrize("failure_type", [OSError, KeyboardInterrupt])
@pytest.mark.parametrize("existing", [False, True])
def test_failed_golden_publication_preserves_target_and_cleans_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
    failure_type: type[BaseException],
    existing: bool,
) -> None:
    """Errors and interrupts propagate once, leaving no partial or orphan file."""
    target = golden_path(_PAGE, _SEQUENCE_ID, goldens_root=tmp_path)
    target.parent.mkdir(parents=True)
    if existing:
        target.write_bytes(_PREVIOUS)
    failure = failure_type("publication failed")
    attempts = 0

    def fail(*_args: object) -> None:
        nonlocal attempts
        attempts += 1
        assert len(list(target.parent.glob("*.tmp"))) == 1
        raise failure

    monkeypatch.setattr(atomic_write.os, failure_point, fail)

    with pytest.raises(failure_type) as raised:
        write_golden(_transcript(tmp_path), page=_PAGE, goldens_root=tmp_path)

    assert raised.value is failure
    assert attempts == 1
    if existing:
        assert target.read_bytes() == _PREVIOUS
        assert list(target.parent.iterdir()) == [target]
    else:
        assert not target.exists()
        assert list(target.parent.iterdir()) == []
