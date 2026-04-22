"""Golden-fixture byte-exactness tests for Modelo 303 2025 (wave 99).

Mirrors the wave-93 :mod:`test_golden_modelo_303` test suite for
the 2025 ejercicio. Because :mod:`modelo_303_2025` re-exports the
2024 schema verbatim (Orden HAC/819/2024 governs both ejercicios),
the only per-year differences must be the three ejercicio stamps
in the envelope header, DP30301 devengo block, and trailer.

Pinning a separate SHA256 for 2025 catches any accidental
divergence between the two clones. The "delta only in ejercicio
bytes" invariant adds structural proof that the clone is pure —
no hidden offset drift.
"""

from __future__ import annotations

import hashlib

import pytest

from ._record_spec import SegmentSpec
from ._serialise import serialise_envelope
from ._test_fixtures import KENT_303_CASILLAS_HAND as _KENT_CASILLAS
from ._test_fixtures import kent_303_headers as _kent_headers
from .modelo_303_2024 import ENVELOPE as ENVELOPE_2024
from .modelo_303_2024 import REQUIRED_HEADER_FIELDS as REQUIRED_2024
from .modelo_303_2025 import (
    ENCODING,
    ENVELOPE,
    REQUIRED_HEADER_FIELDS,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


class TestModelo3032025GoldenKentQ1:
    """Kent's Q1 2025 Modelo 303: régimen general, cuota IVA 21 %."""

    @staticmethod
    def _serialise_kent_q1() -> bytes:
        return serialise_envelope(
            casilla_values=_KENT_CASILLAS,
            headers=_kent_headers("2025"),
            segments=ENVELOPE,
            encoding=ENCODING,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )

    def test_total_length_is_7996(self) -> None:
        payload = self._serialise_kent_q1()
        assert len(payload) == 7996

    def test_sha256_digest_is_stable(self) -> None:
        """Golden digest — DO NOT change without documented intent."""
        payload = self._serialise_kent_q1()
        expected = "f6085a9c6bb40952c2d0ecd5c7abfe5cbec98ccb829032339b54f042bd9c81a7"
        actual = hashlib.sha256(payload).hexdigest()
        assert actual == expected, (
            f"byte-layout drift detected on 303 2025!\n"
            f"  expected SHA256: {expected}\n"
            f"  actual   SHA256: {actual}\n"
            f"If the change is intentional, update the `expected` literal\n"
            f"above AND document the reason in the commit message."
        )

    def test_ejercicio_stamped_at_envelope_header(self) -> None:
        payload = self._serialise_kent_q1()
        assert payload[6:10] == b"2025"

    def test_ejercicio_stamped_at_dp30301_devengo(self) -> None:
        payload = self._serialise_kent_q1()
        # DP30301 starts at byte 328. F009 DEVENGO_EJERCICIO is at
        # 1-based offset 103 within the segment → absolute 328 + 102 = 430.
        assert payload[430:434] == b"2025"

    def test_ejercicio_stamped_at_trailer(self) -> None:
        payload = self._serialise_kent_q1()
        # Trailer starts at 7976. Ejercicio sits at trailer offset 8
        # (1-based) → absolute 7976 + 7 = 7983.
        assert payload[7983:7987] == b"2025"


class TestModelo3032024vs2025StructuralParity:
    """Wave 99 invariant: 2024 and 2025 clones differ only at the three
    ejercicio-stamped byte positions when the same casilla values are
    filed. A byte-level diff that falls outside those positions is a
    schema drift the clone contract forbids."""

    @staticmethod
    def _payload(segments: tuple[SegmentSpec, ...], required: frozenset[str], year: str) -> bytes:
        return serialise_envelope(
            casilla_values={},
            headers=_kent_headers(year),
            segments=segments,
            encoding=ENCODING,
            required_field_ids=required,
        )

    def test_clone_payloads_differ_only_at_ejercicio_stamps(self) -> None:
        p24 = self._payload(ENVELOPE_2024, REQUIRED_2024, "2024")
        p25 = self._payload(ENVELOPE, REQUIRED_HEADER_FIELDS, "2025")
        assert len(p24) == len(p25) == 7996
        # The 4-byte ejercicio appears at offsets [6:10], [430:434], [7983:7987].
        # Each value differs only in its final digit (2024 vs 2025), so
        # exactly three bytes must differ — positions 9, 433, and 7986.
        diffs = [i for i, (a, b) in enumerate(zip(p24, p25, strict=True)) if a != b]
        assert diffs == [9, 433, 7986], (
            f"2024→2025 clone invariant violated. Expected diffs only at "
            f"[9, 433, 7986] (ejercicio last-digit stamps); got {diffs}."
        )
