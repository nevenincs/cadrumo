"""CLI determinism lock: identical inputs → byte-identical outputs (wave 141).

A foundational Kent-observable guarantee: running
``aeat submission export`` twice with the same draft must produce
the exact same bytes on disk. Without this, diff-against-receipt
workflows would be unreliable — Kent couldn't tell whether a
byte difference came from his data or from a non-deterministic
serialiser.

The serialiser itself is fundamentally deterministic (pure
function of inputs), but import-time state (env vars, random
seeds, hash randomisation, file-system timestamps) can leak into
the output through careless dependencies. Wave 141 locks that no
such leak exists at the CLI boundary.

Exercised for every registered schema so a future Modelo 390 or
Modelo 100 registration automatically picks up the determinism
check with no extra code.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from . import app
from ._schema_registry import SCHEMA_REGISTRY

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]

_runner = CliRunner()

_REGISTRY_KEYS = sorted(SCHEMA_REGISTRY.keys())
_REGISTRY_IDS = [f"{m}-{e}" for m, e in _REGISTRY_KEYS]


def _write_draft(tmp_path: Path, *, modelo: str, period: str) -> Path:
    payload = {
        "draft_id": f"DETERMINISM-{modelo}-{period}",
        "modelo": modelo,
        "period": period,
        "profile_tax_id": "X1234567L",
        "status": "DRAFT",
        "values": {"01": "12345.67"},
        "findings": [],
    }
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _export(tmp_path: Path, *, modelo: str, period: str, sub: str) -> Path:
    draft = _write_draft(tmp_path, modelo=modelo, period=period)
    out = tmp_path / sub
    result = _runner.invoke(
        app,
        [
            "export",
            str(draft),
            "--output-dir",
            str(out),
            "--nombre",
            "KENT",
            "--apellidos",
            "DOE",
            "--tipo",
            "I",
        ],
    )
    assert result.exit_code == 0, f"export failed: {result.stdout}"
    ejercicio = period[:4]
    quarter = period[-2:].replace("Q", "") + "T"
    return out / f"X1234567L{ejercicio}{quarter}.{modelo}"


@pytest.mark.parametrize(("modelo", "ejercicio"), _REGISTRY_KEYS, ids=_REGISTRY_IDS)
def test_two_exports_produce_byte_identical_files(tmp_path: Path, modelo: str, ejercicio: str) -> None:
    """Export the same draft twice; both output files must be byte-exact."""
    period = f"{ejercicio}Q1"
    file_a = _export(tmp_path, modelo=modelo, period=period, sub="a")
    file_b = _export(tmp_path, modelo=modelo, period=period, sub="b")
    bytes_a = file_a.read_bytes()
    bytes_b = file_b.read_bytes()
    assert bytes_a == bytes_b, (
        f"non-deterministic export for modelo={modelo} ejercicio={ejercicio}: "
        f"run A produced {len(bytes_a)} bytes, run B produced {len(bytes_b)} bytes; "
        f"hash A = {hashlib.sha256(bytes_a).hexdigest()}, "
        f"hash B = {hashlib.sha256(bytes_b).hexdigest()}. "
        "Some non-pure dependency leaked into the serialiser output."
    )


@pytest.mark.parametrize(("modelo", "ejercicio"), _REGISTRY_KEYS, ids=_REGISTRY_IDS)
def test_five_sequential_exports_all_identical(tmp_path: Path, modelo: str, ejercicio: str) -> None:
    """Five runs in a row must all produce the same SHA256.

    Stronger than the 2-run check: catches a non-deterministic
    dependency that only surfaces every few invocations (e.g. a
    hash-randomised dict ordering that happens to match on 2 runs
    but diverges later)."""
    period = f"{ejercicio}Q1"
    hashes: list[str] = []
    for i in range(5):
        file = _export(tmp_path, modelo=modelo, period=period, sub=f"run-{i}")
        hashes.append(hashlib.sha256(file.read_bytes()).hexdigest())
    assert len(set(hashes)) == 1, (
        f"modelo={modelo} ejercicio={ejercicio} exported {len(set(hashes))} distinct hashes across 5 runs: {hashes}"
    )
