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
from ._deserialise import deserialise_envelope
from ._record_spec import FieldKind
from ._serialise import serialise_envelope
from .modelo_303_2024 import ENCODING, ENVELOPE, REQUIRED_HEADER_FIELDS

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

    _HEADERS: ClassVar[dict[str, str]] = {
        "DP30300_F004_EJERCICIO_DE_DEVENGO": "2024",
        "DP30300_F008_RESERVADO_PARA_LA_ADMINISTRA": " ",
        "DP30300_F009_VERSI_N_DEL_PROGRAMA": " ",
        "DP30300_F010_RESERVADO_PARA_LA_ADMINISTRA": " ",
        "DP30300_F011_NIF_EMPRESA_DESARROLLO": " ",
        "DP30300_F012_RESERVADO_PARA_LA_ADMINISTRA": " ",
        "DP30301_F006_TIPO_DECLARACI_N": "I",
        "DP30301_F007_IDENTIFICACI_N_NIF": "X1234567L",
        "DP30301_F008_IDENTIFICACI_N_APELLIDOS_Y_N": "DOE RODRIGUEZ KENT",
        "DP30301_F009_DEVENGO_EJERCICIO": "2024",
        "DP30301_F010_DEVENGO_PER_ODO": "1T",
    }

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
