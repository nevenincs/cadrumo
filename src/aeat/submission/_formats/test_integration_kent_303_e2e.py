"""End-to-end integration for Modelo 303 2024 (wave 109).

Kent's IVA Q1 2024 scenario through both Track A (envelope
serialiser) and Track B (formula ruleset) in a single pytest.

Feeds his régimen-general base imponible (casilla 07 = 20 000 € at
21 %) into the Modelo 303 2024 ruleset, lets the engine derive all
12 downstream casillas (rates, cuotas, totals), and proves that
serialising the result to the 7994-byte fichero-BOE envelope yields
the wave-109 golden SHA256 + round-trips back byte-exactly.

Ruleset + schema share a known mapping gap: casilla 71 is declared
in the ruleset but has no field in the 303 DR fixture. The test
filters comparisons to casillas that live in both layers so the
gap is documented (see ``_SCHEMA_CASILLAS``) without masking a
real regression.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import ClassVar

import pytest

from ...formulas._engine import Engine
from ...formulas._rulesets.modelo_303_2024 import RULESET as RULESET_303_2024
from ...formulas._rulesets.modelo_303_2025 import RULESET as RULESET_303_2025
from ._deserialise import deserialise_envelope
from ._record_spec import FieldKind
from ._serialise import serialise_envelope
from ._test_fixtures import kent_303_headers
from .modelo_303_2024 import ENCODING, ENVELOPE, REQUIRED_HEADER_FIELDS
from .modelo_303_2025 import ENCODING as ENCODING_2025
from .modelo_303_2025 import ENVELOPE as ENVELOPE_2025
from .modelo_303_2025 import REQUIRED_HEADER_FIELDS as REQUIRED_HEADER_FIELDS_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _schema_casilla_ids() -> frozenset[str]:
    """Enumerate CURRENCY casilla_ids carried by the 303 envelope schema.

    RESERVED rate-literal fields (e.g., casilla 02 = 4.00 %, 05 = 10.00 %,
    08 = 21.00 %) have casilla_ids but never enter merged_casilla_values
    on deserialisation — only CURRENCY fields do — so we exclude them
    from the round-trip comparison.
    """
    out: set[str] = set()
    for seg in ENVELOPE:
        for f in seg.specs:
            if f.casilla_id is not None and f.kind is FieldKind.CURRENCY:
                out.add(f.casilla_id)
    return frozenset(out)


class TestKentE2EModelo303Q12024:
    """Kent's Q1 2024 IVA: 20 000 € servicios al 21 %, sin deducciones."""

    _INPUTS: ClassVar[dict[str, Decimal]] = {
        "07": Decimal("20000.00"),  # base imponible al 21 %
    }

    _HEADERS: ClassVar[dict[str, str]] = dict(kent_303_headers("2024"))

    def _derive_casillas(self) -> dict[str, Decimal]:
        ledger = Engine().derive(ruleset=RULESET_303_2024, inputs=self._INPUTS)
        out: dict[str, Decimal] = {**self._INPUTS}
        for entry in ledger.entries:
            out[entry.casilla_id] = entry.value
        return out

    def test_ruleset_derives_21_percent_cuota(self) -> None:
        """Casilla 09 must be exactly 21 % of casilla 07 (cuota devengada)."""
        casillas = self._derive_casillas()
        assert casillas["07"] == Decimal("20000.00")
        assert casillas["09"] == Decimal("4200.00"), "casilla 09 = 07 * 21 %"
        # Cuota devengada total rolls up to 45 (IVA devengada) and 64
        # (diferencia) at 4200 when no other rate row is populated.
        assert casillas["45"] == Decimal("4200.00")
        assert casillas["64"] == Decimal("4200.00")

    def test_ruleset_to_envelope_hits_golden_sha(self) -> None:
        """Ruleset + envelope serialiser must produce a fixed SHA256 for
        this scenario. Pinning this byte output makes any future ruleset
        or schema drift surface immediately, and names both tracks."""
        casillas = self._derive_casillas()
        payload = serialise_envelope(
            casilla_values=casillas,
            headers=self._HEADERS,
            segments=ENVELOPE,
            encoding=ENCODING,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        expected = "dbf21aa1d8de7233cf7a82d5cb0fd477eddffd0a09d2183d472c675064038c8f"
        actual = hashlib.sha256(payload).hexdigest()
        assert actual == expected, (
            "E2E drift on Modelo 303 2024.\n"
            f"  expected SHA256: {expected}\n"
            f"  actual   SHA256: {actual}\n"
            "Either:\n"
            "  - the Modelo 303 2024 ruleset changed a formula (Track B), OR\n"
            "  - the schema/serialiser shifted a byte (Track A), OR\n"
            "  - casilla 71 gained a schema field, closing the wave-109 gap.\n"
            "Pick one, update the `expected` literal, and explain in the commit."
        )

    def test_round_trip_preserves_schema_backed_casillas(self) -> None:
        """Every ruleset-derived casilla that the envelope schema also
        carries must round-trip byte-exactly through deserialise_envelope.

        Casilla 71 is declared in the ruleset but has no schema field, so
        it is excluded from the comparison — see :func:`_schema_casilla_ids`.
        """
        casillas = self._derive_casillas()
        payload = serialise_envelope(
            casilla_values=casillas,
            headers=self._HEADERS,
            segments=ENVELOPE,
            encoding=ENCODING,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        parsed = deserialise_envelope(payload, segments=ENVELOPE, encoding=ENCODING)
        schema_casillas = _schema_casilla_ids()
        for cid, expected in casillas.items():
            if cid not in schema_casillas:
                continue
            assert parsed.merged_casilla_values[cid] == expected, (
                f"round-trip drift on 303 casilla {cid!r}: expected {expected}, got {parsed.merged_casilla_values[cid]}"
            )


class TestKentE2EModelo303Q12025:
    """Wave 110: 2025 ejercicio end-to-end. Orden HAC/819/2024 governs
    both 2024 and 2025 Modelo 303 filings, so the 2025 ruleset + schema
    clones must compute + serialise identically modulo the EJERCICIO stamps.
    """

    _INPUTS: ClassVar[dict[str, Decimal]] = {
        "07": Decimal("20000.00"),
    }

    _HEADERS: ClassVar[dict[str, str]] = dict(kent_303_headers("2025"))

    def _derive_casillas(self) -> dict[str, Decimal]:
        ledger = Engine().derive(ruleset=RULESET_303_2025, inputs=self._INPUTS)
        out: dict[str, Decimal] = {**self._INPUTS}
        for entry in ledger.entries:
            out[entry.casilla_id] = entry.value
        return out

    def test_2025_ruleset_matches_2024_arithmetic(self) -> None:
        """Same-inputs clone invariant: 2024 and 2025 rulesets must derive
        identical casilla values until AEAT publishes a 303-specific update."""
        ledger_24 = Engine().derive(ruleset=RULESET_303_2024, inputs=self._INPUTS)
        ledger_25 = Engine().derive(ruleset=RULESET_303_2025, inputs=self._INPUTS)
        derived_24 = {e.casilla_id: e.value for e in ledger_24.entries}
        derived_25 = {e.casilla_id: e.value for e in ledger_25.entries}
        assert derived_24 == derived_25, "2024 vs 2025 ruleset divergence — clone contract broken."

    def test_2025_envelope_hits_golden_sha(self) -> None:
        casillas = self._derive_casillas()
        payload = serialise_envelope(
            casilla_values=casillas,
            headers=self._HEADERS,
            segments=ENVELOPE_2025,
            encoding=ENCODING_2025,
            required_field_ids=REQUIRED_HEADER_FIELDS_2025,
        )
        expected = "5fcacf5621278f28a8199cec8b8f22a5800e7953699a240e77b51e1cf97bde4d"
        actual = hashlib.sha256(payload).hexdigest()
        assert actual == expected, (
            f"E2E drift on Modelo 303 2025.\n  expected SHA256: {expected}\n  actual   SHA256: {actual}"
        )
