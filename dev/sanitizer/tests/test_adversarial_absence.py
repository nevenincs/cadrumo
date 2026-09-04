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

A committed PDF carrying no sidecar was formerly dropped from this
gate entirely: the pair was only appended when the sidecar existed,
so three of the sixty-three committed fixtures never met the
leak-marker assertions - which need no sidecar at all. The two
obligations are now separate. Leak markers are checked on every
committed fixture; synthetic presence is checked on those that
carry the sanitiser's audit log. The sidecar-less set is declared
below, so a new one forces a decision instead of vanishing.
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


_SYNTHETIC_BY_CONSTRUCTION: dict[str, str] = {
    "modelo_100_2025A.pdf": "built synthetic for the justificante parser tests; never a sanitised capture",
    "modelo_130_2026Q1.pdf": "built synthetic for the parser, reconciliation and live-capture tests",
    "modelo_303_2026Q1.pdf": "built synthetic for the justificante parser tests; never a sanitised capture",
}
"""Committed fixtures that carry no sanitiser audit log, and why.

These were authored synthetic rather than sanitised from a real
justificante, so there is no ``replacements_applied`` list to prove
present. They are still subject to the leak-marker assertions. The
set is declared here so that a fixture arriving without a sidecar
fails until someone states which of the two it is.
"""


def _committed_fixtures() -> list[tuple[Path, Path | None]]:
    """Return ``(pdf_path, sidecar_json_path_or_None)`` for every committed fixture.

    The sidecar is optional in the RESULT, not in the gate: a fixture
    without one still owes the leak-marker check, and previously
    escaped it by never entering this list.
    """
    fixture_root = FIXTURES_DIR / "justificantes"
    if not fixture_root.is_dir():
        return []
    fixtures: list[tuple[Path, Path | None]] = []
    for pdf_path in scan_directory(fixture_root, pattern="*.pdf", recursive=True):
        sidecar = pdf_path.with_suffix(".json")
        fixtures.append((pdf_path, sidecar if sidecar.is_file() else None))
    return fixtures


_FIXTURES = _committed_fixtures()


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
    assert _FIXTURES, (
        "no committed fixture was discovered under justificantes/; this gate proves "
        "nothing over an empty corpus, and sixty-three fixtures are committed, so an "
        "empty result means the corpus root moved rather than that none exist yet"
    )

    leak_markers = (b"REPLACE_WITH_REAL_CLEARTEXT", b"REPLACE_WITH_SYNTHETIC")
    sidecar_less: list[str] = []
    synthetics_asserted = 0

    for pdf_path, sidecar_path in _FIXTURES:
        raw_bytes = pdf_path.read_bytes()
        decompressed = _decompressed_streams(raw_bytes)

        if sidecar_path is None:
            sidecar_less.append(pdf_path.name)
        else:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            assert "replacements_applied" in sidecar, (
                f"{sidecar_path} carries no replacements_applied list; a sanitiser audit "
                "log without one records no work and cannot be proven against the fixture"
            )

            # Every replacement's synthetic must be present somewhere in
            # the fixture (either in the decompressed streams or in the
            # raw byte image - DocInfo strings appear unencoded outside of
            # streams).
            for replacement in sidecar["replacements_applied"]:
                synthetic = replacement.get("synthetic")
                assert synthetic is not None, (
                    f"a replacement in {sidecar_path} records no synthetic; skipping it "
                    "would drop the one value this gate can prove landed"
                )
                synthetic_bytes = synthetic.encode("utf-8")
                assert synthetic_bytes in raw_bytes or synthetic_bytes in decompressed, (
                    f"Synthetic {synthetic!r} from {sidecar_path} not found in {pdf_path}"
                )
                synthetics_asserted += 1

        for marker in leak_markers:
            assert marker not in raw_bytes, (
                f"Leak marker {marker!r} found in {pdf_path}; partially-filled mapping committed"
            )
            assert marker not in decompressed, f"Leak marker {marker!r} found in decompressed streams of {pdf_path}"

    assert synthetics_asserted, (
        "not one synthetic was proven present across the whole corpus; the leak-marker "
        "half can pass on its own, so this gate would report clean having checked nothing"
    )

    assert set(sidecar_less) == set(_SYNTHETIC_BY_CONSTRUCTION), (
        "the set of committed fixtures carrying no sanitiser audit log has changed: "
        f"{sorted(set(sidecar_less) ^ set(_SYNTHETIC_BY_CONSTRUCTION))}. A fixture without "
        "a sidecar cannot be proven sanitised, so each one must be declared in "
        "_SYNTHETIC_BY_CONSTRUCTION with the reason it needs none."
    )
