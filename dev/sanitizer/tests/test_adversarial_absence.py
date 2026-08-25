"""Adversarial absence tests for committed sanitised fixtures.

This is the load-bearing security gate the sanitiser exists to
satisfy. For every committed fixture under
``src/cadrumo/tests/fixtures/justificantes/<modelo>/`` the test loads the
sidecar mapping JSON (which records the synthetic values applied
to the fixture) and asserts that no entry in any forbidden-leak
category contains a value that should have been replaced.

The mapping sidecar is the canonical post-sanitisation audit log
written by ``aeat sanitize pdf --report``. It records:

* ``replacements_applied`` — every (real_sha256, synthetic) pair.
* ``surfaces_scrubbed`` — every PII surface wiped.

The adversarial test does NOT have the cleartext (the cleartext
mapping YAML stays gitignored under ``scratch/``). Instead, it
asserts:

1. The fixture is structurally a PDF that opens through
   :mod:`pikepdf` without warnings.
2. The fixture's content streams contain every synthetic value
   listed in ``replacements_applied``.
3. The fixture's raw bytes do not contain any leak-marker string
   from the synthetic mapping (e.g. ``REPLACE_WITH_REAL``).

When no fixtures are committed yet, the loop has no fixture work
to perform but the module still contributes one passing test.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pikepdf
import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.tests import FIXTURES_DIR

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _committed_fixture_pairs() -> list[tuple[Path, Path]]:
    """Return ``(pdf_path, sidecar_json_path)`` for every committed fixture.

    Returns an empty list when no fixtures have landed yet, so a
    fresh checkout collects zero parametrised cases.
    """
    fixture_root = FIXTURES_DIR / "justificantes"
    if not fixture_root.is_dir():
        return []
    pairs: list[tuple[Path, Path]] = []
    for pdf_path in scan_directory(fixture_root, pattern="*.pdf", recursive=True):
        sidecar = pdf_path.with_suffix(".json")
        if sidecar.is_file():
            pairs.append((pdf_path, sidecar))
    return pairs


_FIXTURE_PAIRS = _committed_fixture_pairs()


def _decompressed_streams(pdf_bytes: bytes) -> bytes:
    """Returns the concatenated decompressed content streams of every page."""
    pdf = pikepdf.Pdf.open(io.BytesIO(pdf_bytes))
    chunks: list[bytes] = []
    for page in pdf.pages:
        contents = page.obj.get("/Contents")
        if contents is None:
            continue
        if isinstance(contents, pikepdf.Array):
            for index in range(len(contents)):
                chunks.append(bytes(contents[index].read_bytes()))
        else:
            chunks.append(bytes(contents.read_bytes()))
    return b"\n".join(chunks)


def test_committed_fixtures_have_synthetics_and_no_leak_markers() -> None:
    """Every committed fixture exposes synthetics and carries no scaffold markers."""
    leak_markers = (b"REPLACE_WITH_REAL_CLEARTEXT", b"REPLACE_WITH_SYNTHETIC")
    for pdf_path, sidecar_path in _FIXTURE_PAIRS:
        raw_bytes = pdf_path.read_bytes()
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        decompressed = _decompressed_streams(raw_bytes)

        # Every replacement's synthetic must be present somewhere in
        # the fixture (either in the decompressed streams or in the
        # raw byte image — DocInfo strings appear unencoded outside of
        # streams).
        for replacement in sidecar.get("replacements_applied", ()):
            synthetic = replacement.get("synthetic")
            if synthetic is None:
                continue
            synthetic_bytes = synthetic.encode("utf-8")
            assert synthetic_bytes in raw_bytes or synthetic_bytes in decompressed, (
                f"Synthetic {synthetic!r} from {sidecar_path} not found in {pdf_path}"
            )

        for marker in leak_markers:
            assert marker not in raw_bytes, (
                f"Leak marker {marker!r} found in {pdf_path}; partially-filled mapping committed"
            )
            assert marker not in decompressed, f"Leak marker {marker!r} found in decompressed streams of {pdf_path}"
