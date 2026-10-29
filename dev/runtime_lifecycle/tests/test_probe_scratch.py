"""Developer probes reclaim their synthetic profiles on completion and failure."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from .. import backend_probe, concurrent_sessions_probe

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("probe_name", ("backend", "concurrent"))
@pytest.mark.parametrize("fails", (False, True))
def test_probe_reclaims_only_its_controlled_scratch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, probe_name: str, fails: bool
) -> None:
    probe = backend_probe if probe_name == "backend" else concurrent_sessions_probe
    roots: list[Path] = []
    sibling = tmp_path / "unrelated"
    sibling.mkdir()

    def exercise(root: Path) -> None:
        assert root.is_dir() and root.parent == tmp_path
        roots.append(root)
        (root / "synthetic-profile").write_text("private fixture state", encoding="utf-8")
        if fails:
            raise RuntimeError("probe failed")

    monkeypatch.setattr(probe, "prepare_temp_root", lambda: tmp_path)
    monkeypatch.setattr(probe, "source_programs", lambda: None)
    if probe_name == "backend":

        def signed_in(_probe, _programs, scratch: Path, *, source: bool) -> None:
            assert source
            exercise(scratch.parent)

        monkeypatch.setattr(backend_probe, "signed_in_phase", signed_in)
    else:

        @contextmanager
        def runtime(*_args):
            yield SimpleNamespace(ready=lambda: {"kind": "runtime_ready"})

        def setup(_run, context) -> bool:
            exercise(context.scratch)
            return False

        monkeypatch.setattr(concurrent_sessions_probe, "caller_owned_runtime", runtime)
        monkeypatch.setattr(concurrent_sessions_probe, "mark_development_root", lambda _root: None)
        monkeypatch.setattr(concurrent_sessions_probe, "_setup", setup)

    if fails:
        with pytest.raises(RuntimeError, match="probe failed"):
            probe.main(["--source"])
    else:
        assert probe.main(["--source"]) == 0

    assert len(roots) == 1
    assert not roots[0].exists()
    assert sibling.is_dir()
