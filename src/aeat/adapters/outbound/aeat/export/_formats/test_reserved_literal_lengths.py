"""Rule-adherence invariant: RESERVED literal length == declared length.

A RESERVED field declares ``literal_value`` and ``length``; the
serialiser space-pads the literal to ``length``, but if
``len(literal_value) > length`` the emitted bytes truncate and the
fichero-BOE silently drifts out of the AEAT DR shape. If
``len(literal_value) < length`` the record still parses but the
trailing spaces ruin any future byte-exact comparison against an
AEAT-produced re-download.

This test guards both the hand-authored schemas (Modelo 130
2024/2025) and the JSON-ingested DR fixtures (Modelo 303
DR303e24, mini_303) as a single family invariant. Any future
fixture edit or schema extension that drifts this invariant
fails here before it reaches a golden SHA test.

Stream B (rule adherence, perpetual) per the project's
continuous-cycle mandate.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ._record_spec import FieldKind
from .modelo_130_2024 import RECORD_SPECS as RECORD_SPECS_130
from .modelo_303_2024 import ENVELOPE as ENVELOPE_303

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


_DR_SPEC_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent.parent / "tests" / "fixtures" / "dr_specs"
)


class TestReservedLiteralLengths:
    def test_modelo_130_2024_schema(self) -> None:
        """Every RESERVED field in the hand-authored 130 2024 schema must
        declare a literal whose character count matches ``length``."""
        mismatches = [
            (s.field_id, s.length, len(s.literal_value))
            for s in RECORD_SPECS_130
            if s.kind is FieldKind.RESERVED and s.literal_value is not None and len(s.literal_value) != s.length
        ]
        assert not mismatches, f"130 2024 RESERVED literal/length drift: {mismatches}"

    def test_modelo_303_2024_envelope(self) -> None:
        """Every RESERVED field in the auto-generated 303 envelope schema
        must carry a correctly-sized literal. Generated from dr303e24.json,
        so this is a belt-and-braces guard alongside the JSON fixture test."""
        mismatches: list[tuple[str, str, int, int]] = []
        for seg in ENVELOPE_303:
            for f in seg.specs:
                if f.kind is FieldKind.RESERVED and f.literal_value is not None and len(f.literal_value) != f.length:
                    mismatches.append((seg.segment_id, f.field_id, f.length, len(f.literal_value)))
        assert not mismatches, f"303 2024 envelope RESERVED literal/length drift: {mismatches}"

    @pytest.mark.parametrize("fixture_path", sorted(_DR_SPEC_DIR.glob("*.json")))
    def test_dr_spec_fixture(self, fixture_path: Path) -> None:
        """Every RESERVED field in every committed DR spec JSON fixture
        must carry a correctly-sized literal."""
        doc = json.loads(fixture_path.read_text(encoding="utf-8"))
        mismatches: list[tuple[str, str, int, int, str]] = []
        for seg_id, seg in doc["segments"].items():
            for f in seg["fields"]:
                if f.get("kind") != "RESERVED":
                    continue
                literal = f.get("literal")
                if literal is None:
                    continue
                declared = int(f["length"])
                actual = len(literal)
                if actual != declared:
                    mismatches.append((seg_id, f["field_id"], declared, actual, repr(literal)))
        assert not mismatches, (
            f"{fixture_path.name}: RESERVED literal/length drift in {len(mismatches)} "
            f"field(s) — first: {mismatches[0]}. Fix the fixture JSON + regenerate."
        )
