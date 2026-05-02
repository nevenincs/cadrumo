"""End-to-end integration coverage for Modelo 303 2024.

Exercises an IVA Q1 2024 scenario through both the envelope
serialiser and the formula ruleset in a single pytest run. A
régimen-general base imponible (casilla 07 = 20 000 EUR at 21 %)
is fed into the Modelo 303 2024 ruleset; the engine derives all
12 downstream casillas (rates, cuotas, totals); the result is
serialised to the 7994-byte fichero-BOE envelope and pinned to a
golden SHA256 with a byte-exact round-trip back through
:func:`aeat.adapters.outbound.aeat.export._formats._deserialise.deserialise_envelope`.

Ruleset and schema share a known mapping gap: casillas 45, 64, 67,
71 are declared in the ruleset but have no fields in the 303 DR
fixture (the extraction missed the cuota-devengada-total /
diferencia / a-ingresar rollup block, captured by
``_EXPECTED_GAPS["303.2024"]`` in ``test_ruleset_schema_coverage.py``
and the matching note in ``tests/fixtures/dr_specs/dr303e24.json``
``source.notes``). Comparisons are filtered to casillas that live
in both layers so the gap is documented without masking a real
regression.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import ClassVar

import pytest

from ......domain.formulas._engine import Engine
from ......domain.formulas._rulesets.modelo_303_2024 import RULESET as RULESET_303_2024
from ......domain.formulas._rulesets.modelo_303_2025 import RULESET as RULESET_303_2025
from ._deserialise import deserialise_envelope
from ._record_spec import FieldKind
from ._serialise import serialise_envelope
from ._test_fixtures import kent_303_headers
from .modelo_303_2024 import ENCODING, ENVELOPE, REQUIRED_HEADER_FIELDS
from .modelo_303_2025 import ENCODING as ENCODING_2025
from .modelo_303_2025 import ENVELOPE as ENVELOPE_2025
from .modelo_303_2025 import REQUIRED_HEADER_FIELDS as REQUIRED_HEADER_FIELDS_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


def _schema_casilla_ids() -> frozenset[str]:
    """Enumerate CURRENCY ``casilla_id`` values carried by the 303 envelope schema.

    RESERVED rate-literal fields (e.g. casilla 02 = 4.00 %, 05 = 10.00 %,
    08 = 21.00 %) carry ``casilla_id`` values but never enter
    ``merged_casilla_values`` on deserialisation — only
    :attr:`aeat.adapters.outbound.aeat.export._formats._record_spec.FieldKind.CURRENCY`
    fields do — so they are excluded from the round-trip comparison.

    Returns:
        Immutable set of casilla identifiers that participate in the
        envelope's CURRENCY round-trip.
    """
    out: set[str] = set()
    for seg in ENVELOPE:
        for f in seg.specs:
            if f.casilla_id is not None and f.kind is FieldKind.CURRENCY:
                out.add(f.casilla_id)
    return frozenset(out)


class TestKentE2EModelo303Q12024:
    """Q1 2024 IVA scenario: 20 000 EUR servicios al 21 %, sin deducciones.

    Pins the engine + envelope serialiser to a known SHA256 and exercises
    the round-trip through
    :func:`aeat.adapters.outbound.aeat.export._formats._deserialise.deserialise_envelope`.
    """

    _INPUTS: ClassVar[dict[str, Decimal]] = {
        "07": Decimal("20000.00"),  # base imponible al 21 %
    }

    _HEADERS: ClassVar[dict[str, str]] = dict(kent_303_headers("2024"))

    def _derive_casillas(self) -> dict[str, Decimal]:
        """Run the Modelo 303 2024 ruleset over the scenario inputs."""
        ledger = Engine().derive(ruleset=RULESET_303_2024, inputs=self._INPUTS)
        out: dict[str, Decimal] = {**self._INPUTS}
        for entry in ledger.entries:
            out[entry.casilla_id] = entry.value
        return out

    def test_ruleset_derives_21_percent_cuota(self) -> None:
        """Assert casilla 09 equals exactly 21 % of casilla 07 (cuota devengada)."""
        casillas = self._derive_casillas()
        assert casillas["07"] == Decimal("20000.00")
        assert casillas["09"] == Decimal("4200.00"), "casilla 09 = 07 * 21 %"
        # Cuota devengada total rolls up to 45 (IVA devengada) and 64
        # (diferencia) at 4200 when no other rate row is populated.
        assert casillas["45"] == Decimal("4200.00")
        assert casillas["64"] == Decimal("4200.00")

    def test_ruleset_to_envelope_hits_golden_sha(self) -> None:
        """Assert ruleset + envelope serialiser produce a fixed SHA256 for this scenario.

        Pinning this byte output surfaces ruleset or schema drift
        immediately and names both layers (formula engine vs.
        serialiser) in the failure message so the regression can be
        attributed without bisecting.
        """
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
            "  - the Modelo 303 2024 ruleset changed a formula, OR\n"
            "  - the schema/serialiser shifted a byte, OR\n"
            "  - casillas 45 / 64 / 67 / 71 gained schema fields,\n"
            " closing the /113 gap (update _EXPECTED_GAPS too).\n"
            "Pick one, update the `expected` literal, and explain in the commit."
        )

    def test_round_trip_preserves_schema_backed_casillas(self) -> None:
        """Assert ruleset-derived casillas backed by the envelope schema round-trip byte-exactly.

        Casillas 45, 64, 67, 71 are declared in the ruleset but have no
        corresponding envelope field (see ``_EXPECTED_GAPS`` and the
        fixture's ``source.notes``), so they are excluded from the
        comparison via :func:`_schema_casilla_ids`.
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
    """2025 ejercicio end-to-end coverage for Modelo 303.

    Orden HAC/819/2024 governs both 2024 and 2025 Modelo 303 filings,
    so the 2025 ruleset + schema clones must compute and serialise
    identically modulo the ``EJERCICIO`` stamp.
    """

    _INPUTS: ClassVar[dict[str, Decimal]] = {
        "07": Decimal("20000.00"),
    }

    _HEADERS: ClassVar[dict[str, str]] = dict(kent_303_headers("2025"))

    def _derive_casillas(self) -> dict[str, Decimal]:
        """Run the Modelo 303 2025 ruleset over the scenario inputs."""
        ledger = Engine().derive(ruleset=RULESET_303_2025, inputs=self._INPUTS)
        out: dict[str, Decimal] = {**self._INPUTS}
        for entry in ledger.entries:
            out[entry.casilla_id] = entry.value
        return out

    def test_2025_ruleset_matches_2024_arithmetic(self) -> None:
        """Assert the 2024 and 2025 rulesets derive identical casilla values for identical inputs.

        This clone invariant must hold until AEAT publishes a
        303-specific update; the moment it does, this test should be
        rewritten to capture the new arithmetic deliberately.
        """
        ledger_24 = Engine().derive(ruleset=RULESET_303_2024, inputs=self._INPUTS)
        ledger_25 = Engine().derive(ruleset=RULESET_303_2025, inputs=self._INPUTS)
        derived_24 = {e.casilla_id: e.value for e in ledger_24.entries}
        derived_25 = {e.casilla_id: e.value for e in ledger_25.entries}
        assert derived_24 == derived_25, "2024 vs 2025 ruleset divergence — clone contract broken."

    def test_2025_envelope_hits_golden_sha(self) -> None:
        """Pin the 2025 envelope serialisation of the scenario to a fixed SHA256."""
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
