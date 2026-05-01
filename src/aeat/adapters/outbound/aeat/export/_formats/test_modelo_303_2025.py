"""Tests for the Modelo 303 2025 schema clone."""

from __future__ import annotations

import pytest

from . import modelo_303_2024, modelo_303_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


class TestModelo3032025Clone:
    def test_envelope_is_identical_to_2024(self) -> None:
        """Orden HAC/819/2024 governs both ejercicios; same bytes on the wire."""
        assert modelo_303_2025.ENVELOPE is modelo_303_2024.ENVELOPE

    def test_encoding_is_iso_8859_1(self) -> None:
        assert modelo_303_2025.ENCODING == "iso-8859-1"

    def test_required_header_fields_are_identical(self) -> None:
        assert modelo_303_2025.REQUIRED_HEADER_FIELDS == modelo_303_2024.REQUIRED_HEADER_FIELDS

    def test_public_api_matches_2024(self) -> None:
        """``__all__`` exports the same three public names."""
        assert set(modelo_303_2025.__all__) == {"ENCODING", "ENVELOPE", "REQUIRED_HEADER_FIELDS"}
