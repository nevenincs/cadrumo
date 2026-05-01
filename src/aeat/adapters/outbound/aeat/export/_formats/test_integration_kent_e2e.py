"""End-to-end integration: ruleset engine → serialise → deserialise (wave 108).

Kent's complete produce → verify → export journey in a single
pytest: the Modelo 130 2024 formula ruleset derives casillas from
Kent's inputs (ingresos + gastos), the serialiser emits the
fichero-BOE bytes, and the deserialiser rebuilds the casilla map.

This bridges the two EPIC tracks (A: submission / export, B:
financial input / formula derivation) inside a single assertion:
the derived casillas serialise to the wave-84 golden SHA256 when
fed the same inputs the golden fixture pins.

If this test fails, either the ruleset's formulas drifted away
from the AEAT BOE law, or the serialiser/schema drifted away from
dr130.09.pdf. Both failure modes are named explicitly in the
assertion messages so a git bisect + stack trace point at the
right layer.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import ClassVar

import pytest

from ......domain.formulas._engine import Engine
from ......domain.formulas._rulesets.modelo_130_2024 import RULESET as RULESET_130_2024
from ......domain.formulas._rulesets.modelo_130_2025 import RULESET as RULESET_130_2025
from ._deserialise import deserialise
from ._serialise import serialise
from ._test_fixtures import kent_130_headers
from .modelo_130_2024 import (
    ENCODING,
    RECORD_LENGTH,
    RECORD_SPECS,
    REQUIRED_HEADER_FIELDS,
)
from .modelo_130_2025 import ENCODING as ENCODING_2025
from .modelo_130_2025 import RECORD_LENGTH as RECORD_LENGTH_2025
from .modelo_130_2025 import RECORD_SPECS as RECORD_SPECS_2025
from .modelo_130_2025 import REQUIRED_HEADER_FIELDS as REQUIRED_HEADER_FIELDS_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


class TestKentE2EModelo130Q12024:
    """Kent's Q1 2024 scenario: 20 000 ingresos, 5 000 gastos.

    The ruleset derives every cascade casilla (03, 04, 07, 09, 11,
    12, 14, 17, 19); the serialiser stamps them into the 878-byte
    payload; the deserialiser round-trips them back; the golden SHA
    proves byte-exact equivalence with the wave-84 fixture.
    """

    _INPUTS: ClassVar[dict[str, Decimal]] = {
        "01": Decimal("20000.00"),  # ingresos computables
        "02": Decimal("5000.00"),  # gastos deducibles
    }

    _HEADERS: ClassVar[dict[str, str]] = dict(kent_130_headers("2024"))

    def _derive_casillas(self) -> dict[str, Decimal]:
        """Run the Modelo 130 2024 ruleset over Kent's inputs."""
        ledger = Engine().derive(ruleset=RULESET_130_2024, inputs=self._INPUTS)
        derived: dict[str, Decimal] = {**self._INPUTS}
        for entry in ledger.entries:
            derived[entry.casilla_id] = entry.value
        return derived

    def test_ruleset_derives_every_cascade_casilla(self) -> None:
        """Prove the formula engine computes casillas 03 / 04 / 07 / 12 / 14 / 17 / 19."""
        casillas = self._derive_casillas()
        # Key arithmetic checks: these lock the sum/subtraction/20% rules
        # against the BOE ruleset so a later formula edit is audible here.
        assert casillas["03"] == Decimal("15000.00"), "casilla 03 = 01 - 02 (rendimiento neto)"
        assert casillas["04"] == Decimal("3000.00"), "casilla 04 = 20 % of casilla 03"
        assert casillas["07"] == Decimal("3000.00"), "apartado I resultado"
        assert casillas["12"] == Decimal("3000.00"), "suma parciales (07 + 11)"
        assert casillas["14"] == Decimal("3000.00"), "neto tras minoración"
        assert casillas["17"] == Decimal("3000.00"), "diferencia"
        assert casillas["19"] == Decimal("3000.00"), "resultado a ingresar"

    def test_ruleset_to_serialised_bytes_hits_golden_sha(self) -> None:
        """End-to-end: ruleset → serialise should be byte-identical to
        the wave-84 golden fixture."""
        casillas = self._derive_casillas()
        payload = serialise(
            casilla_values=casillas,
            headers=self._HEADERS,
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        expected_golden = "fb5fd7955a2265d0cf6b1bcb31b8ceee52aeea75297d8de98d8b649cbd479494"
        actual = hashlib.sha256(payload).hexdigest()
        assert actual == expected_golden, (
            "E2E drift: ruleset-derived casillas no longer byte-match the "
            "wave-84 golden fixture.\n"
            f"  expected SHA256: {expected_golden}\n"
            f"  actual   SHA256: {actual}\n"
            "Either:\n"
            "  - the Modelo 130 2024 ruleset changed a formula (Track B), OR\n"
            "  - the schema/serialiser shifted a byte (Track A).\n"
            "Both layers ship to Kent together, so this test guards the seam."
        )

    def test_round_trip_recovers_ruleset_casillas(self) -> None:
        """serialise → deserialise reproduces every casilla the ruleset emitted."""
        casillas = self._derive_casillas()
        payload = serialise(
            casilla_values=casillas,
            headers=self._HEADERS,
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        parsed = deserialise(
            payload,
            specs=RECORD_SPECS,
            encoding=ENCODING,
            total_length=RECORD_LENGTH,
        )
        for cid, expected in casillas.items():
            got = parsed.casilla_values[cid]
            assert got == expected, f"round-trip drift on casilla {cid!r}: expected {expected}, got {got}"


class TestKentE2EModelo130Q12025:
    """Wave 110: 2025 ejercicio clone parity end-to-end.

    The 2025 ruleset re-exports the 2024 formulas, and the 2025
    schema re-exports the 2024 specs. Feeding the same Kent inputs
    with ejercicio=2025 must produce the wave-105 golden SHA256
    because the only byte-level difference is the 4-byte EJERCICIO
    stamp at position 70-73.
    """

    _INPUTS: ClassVar[dict[str, Decimal]] = {
        "01": Decimal("20000.00"),
        "02": Decimal("5000.00"),
    }

    _HEADERS: ClassVar[dict[str, str]] = dict(kent_130_headers("2025"))

    def _derive_casillas(self) -> dict[str, Decimal]:
        ledger = Engine().derive(ruleset=RULESET_130_2025, inputs=self._INPUTS)
        derived: dict[str, Decimal] = {**self._INPUTS}
        for entry in ledger.entries:
            derived[entry.casilla_id] = entry.value
        return derived

    def test_2025_ruleset_matches_2024_arithmetic(self) -> None:
        """The clone contract says 2024 and 2025 rulesets compute
        identical casilla values when fed identical inputs."""
        ledger_2024 = Engine().derive(ruleset=RULESET_130_2024, inputs=self._INPUTS)
        ledger_2025 = Engine().derive(ruleset=RULESET_130_2025, inputs=self._INPUTS)
        derived_2024 = {e.casilla_id: e.value for e in ledger_2024.entries}
        derived_2025 = {e.casilla_id: e.value for e in ledger_2025.entries}
        assert derived_2024 == derived_2025, (
            "2024 and 2025 rulesets diverged on casilla outputs. Expected "
            "parity until AEAT publishes a 130-specific Orden — ship new "
            "golden SHAs and update the clone-parity assertions when they do."
        )

    def test_2025_ruleset_to_serialised_hits_golden_sha(self) -> None:
        casillas = self._derive_casillas()
        payload = serialise(
            casilla_values=casillas,
            headers=self._HEADERS,
            specs=RECORD_SPECS_2025,
            encoding=ENCODING_2025,
            total_length=RECORD_LENGTH_2025,
            required_field_ids=REQUIRED_HEADER_FIELDS_2025,
        )
        expected = "fe5b3f7cad086ef4d4f9cefdeb8c54caa28087afc82ad40c8f854e884b2345c5"
        actual = hashlib.sha256(payload).hexdigest()
        assert actual == expected, (
            f"E2E drift on Modelo 130 2025.\n"
            f"  expected SHA256: {expected}\n  actual   SHA256: {actual}\n"
            "Either the 2025 ruleset diverged, the schema clone broke, "
            "or the test needs an intentional SHA update."
        )
