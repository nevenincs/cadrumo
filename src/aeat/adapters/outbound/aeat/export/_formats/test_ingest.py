"""Tests for the DR spec ingestion library (EPIC #305 wave 86)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ._deserialise import deserialise_envelope
from ._ingest import ingest_dr_spec_document, ingest_dr_spec_path
from ._record_spec import FieldKind, SignedMode
from ._serialise import serialise_envelope

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]

_FIXTURE_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent.parent / "tests" / "fixtures" / "dr_specs"
)


class TestIngestMini303:
    """The mini_303.json fixture mirrors the Modelo 303 preview shape."""

    def test_fixture_loads_without_error(self) -> None:
        ingested = ingest_dr_spec_path(_FIXTURE_DIR / "mini_303.json")
        assert ingested["encoding"] == "iso-8859-1"
        assert len(ingested["segments"]) == 3
        segment_ids = tuple(s.segment_id for s in ingested["segments"])
        assert segment_ids == ("DP30300_MINI", "DP30301_MINI", "DP30303_MINI")

    def test_source_metadata_preserved(self) -> None:
        ingested = ingest_dr_spec_path(_FIXTURE_DIR / "mini_303.json")
        source = ingested["source"]
        assert source["modelo"] == "303"
        assert source["boe_id"] == "BOE-A-2024-16129"
        assert source["xlsx"] == "DR303e24.xlsx"

    def test_signed_mode_parsed(self) -> None:
        """Casilla 69 is declared INLINE_SIGN in the JSON — must parse through."""
        ingested = ingest_dr_spec_path(_FIXTURE_DIR / "mini_303.json")
        dp30303 = next(s for s in ingested["segments"] if s.segment_id == "DP30303_MINI")
        casilla_69 = next(f for f in dp30303.specs if f.casilla_id == "69")
        assert casilla_69.signed_mode is SignedMode.INLINE_SIGN
        assert casilla_69.kind is FieldKind.CURRENCY

    def test_ingested_segments_round_trip(self) -> None:
        """End-to-end: ingest JSON -> serialise_envelope -> deserialise_envelope
        preserves casilla values. This proves the ingestion output is
        functionally equivalent to a hand-authored spec."""
        ingested = ingest_dr_spec_path(_FIXTURE_DIR / "mini_303.json")
        payload = serialise_envelope(
            casilla_values={"69": Decimal("-1500.75")},
            headers={
                "EJERCICIO": "2024",
                "PERIODO": "1T",
                "NIF_DECLARANTE": "X1234567L",
                "TIPO_DECLARACION": "I",
                "DP30303_PREFIX_FILLER": " " * 322,
            },
            segments=ingested["segments"],
            encoding=ingested["encoding"],
        )
        parsed = deserialise_envelope(
            payload,
            segments=ingested["segments"],
            encoding=ingested["encoding"],
        )
        assert parsed.merged_casilla_values["69"] == Decimal("-1500.75")


class TestIngestValidation:
    def test_unknown_encoding_rejected(self) -> None:
        bad = {
            "source": {},
            "encoding": "utf-8",  # not allowed
            "segments": {},
        }
        with pytest.raises(ValueError, match="encoding 'utf-8'"):
            ingest_dr_spec_document(bad)

    def test_unknown_kind_rejected(self) -> None:
        bad = {
            "source": {},
            "encoding": "cp1252",
            "segments": {
                "S": {
                    "total_length": 3,
                    "fields": [
                        {"offset": 1, "length": 3, "field_id": "F", "kind": "WEIRD"},
                    ],
                },
            },
        }
        with pytest.raises(ValueError, match="unknown FieldKind"):
            ingest_dr_spec_document(bad)

    def test_contiguity_bubble_up(self) -> None:
        """A spec with an offset gap surfaces at ingestion time."""
        bad = {
            "source": {},
            "encoding": "cp1252",
            "segments": {
                "BADSEG": {
                    "total_length": 6,
                    "fields": [
                        {"offset": 1, "length": 2, "field_id": "A", "kind": "RESERVED", "literal": "AA"},
                        {
                            "offset": 5,
                            "length": 2,
                            "field_id": "B",  # gap
                            "kind": "RESERVED",
                            "literal": "BB",
                        },
                    ],
                },
            },
        }
        with pytest.raises(ValueError, match="BADSEG"):
            ingest_dr_spec_document(bad)
