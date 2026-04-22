"""Structural parity between Modelo 130 2024 and 2025 (wave 80b)."""

from __future__ import annotations

import pytest

from . import modelo_130_2024 as m130_2024
from . import modelo_130_2025 as m130_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


class TestModelo1302025ClonesParity:
    """The 2025 module re-exports 2024's spec verbatim until AEAT
    publishes a 2025-specific Orden / Diseño de registros."""

    def test_record_length_matches(self) -> None:
        assert m130_2025.RECORD_LENGTH == m130_2024.RECORD_LENGTH

    def test_encoding_matches(self) -> None:
        assert m130_2025.ENCODING == m130_2024.ENCODING

    def test_required_headers_match(self) -> None:
        assert m130_2025.REQUIRED_HEADER_FIELDS == m130_2024.REQUIRED_HEADER_FIELDS

    def test_specs_are_identity_clone(self) -> None:
        """No BOE change for 2025 — spec tuple is the SAME object."""
        assert m130_2025._RECORD_SPECS is m130_2024._RECORD_SPECS
