"""Golden-fixture byte-exactness tests for Modelo 130 2025.

Mirrors :mod:`.test_golden_modelo_130` (the 2024 suite) for the 2025
ejercicio. :mod:`.modelo_130_2025` re-exports the 2024 record spec
verbatim (Orden EHA/672/2007 still governs Modelo 130), so the only
per-ejercicio byte difference must be the 4-byte ``EJERCICIO`` stamp
at offset 71 (0-indexed ``[70:74]``).

Pinning a separate SHA256 for 2025 catches any accidental divergence
between the two clones. The "delta only in EJERCICIO bytes" invariant
adds structural proof that the clone is pure.
"""

from __future__ import annotations

import hashlib

import pytest

from ._serialise import serialise
from ._test_fixtures import KENT_130_CASILLAS as _KENT_CASILLAS
from ._test_fixtures import kent_130_headers as _kent_headers
from .modelo_130_2024 import ENCODING as ENCODING_2024
from .modelo_130_2024 import RECORD_LENGTH as LEN_2024
from .modelo_130_2024 import RECORD_SPECS as SPECS_2024
from .modelo_130_2024 import REQUIRED_HEADER_FIELDS as REQ_2024
from .modelo_130_2025 import (
    ENCODING,
    RECORD_LENGTH,
    RECORD_SPECS,
    REQUIRED_HEADER_FIELDS,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


class TestModelo1302025GoldenKentQ1:
    """Kent's Q1 2025 Modelo 130: 20 000 ingresos, 5 000 gastos, 3 000 resultado."""

    @staticmethod
    def _serialise_kent_q1() -> bytes:
        return serialise(
            casilla_values=_KENT_CASILLAS,
            headers=_kent_headers("2025"),
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )

    def test_total_length_is_880(self) -> None:
        payload = self._serialise_kent_q1()
        assert len(payload) == 880

    def test_sha256_digest_is_stable(self) -> None:
        """Golden digest — DO NOT change without documented intent."""
        payload = self._serialise_kent_q1()
        expected = "fe5b3f7cad086ef4d4f9cefdeb8c54caa28087afc82ad40c8f854e884b2345c5"
        actual = hashlib.sha256(payload).hexdigest()
        assert actual == expected, (
            f"byte-layout drift detected on 130 2025!\n"
            f"  expected SHA256: {expected}\n"
            f"  actual   SHA256: {actual}\n"
            f"If the change is intentional, update the `expected` literal\n"
            f"above AND document the reason in the commit message."
        )

    def test_ejercicio_stamped_at_offset_71(self) -> None:
        payload = self._serialise_kent_q1()
        # Modelo 130 EJERCICIO lives at 1-based offset 71 (0-indexed 70..74).
        assert payload[70:74] == b"2025"


class TestModelo1302024vs2025StructuralParity:
    """2024 and 2025 clones differ only at the 4-byte ``EJERCICIO`` field
    when the same casilla values are filed.

    Since ``"2024"`` -> ``"2025"`` mutates only the final digit
    (ASCII 52 -> 53), exactly one byte must differ — position 73.
    """

    def test_clone_payloads_differ_only_at_ejercicio_last_digit(self) -> None:
        p24 = serialise(
            casilla_values=_KENT_CASILLAS,
            headers=_kent_headers("2024"),
            specs=SPECS_2024,
            encoding=ENCODING_2024,
            total_length=LEN_2024,
            required_field_ids=REQ_2024,
        )
        p25 = serialise(
            casilla_values=_KENT_CASILLAS,
            headers=_kent_headers("2025"),
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        assert len(p24) == len(p25) == 880
        diffs = [i for i, (a, b) in enumerate(zip(p24, p25, strict=True)) if a != b]
        assert diffs == [73], (
            f"2024→2025 clone invariant violated. Expected a single-byte "
            f"diff at position 73 (EJERCICIO last digit); got {diffs}."
        )
