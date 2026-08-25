"""Grounded verification of the Modelo 151 escala del ahorro (art. 93.2.e.2º).

The savings escala del régimen de impatriados is registered as a
``bracket_table`` parameter ``modelo-151.escala-cuota-integra-ahorro`` under the
``2025-y-siguientes`` revision, with ``bracket_axis = "filing_period"`` and
``legal_refs = ["ley-35-2006:art-93", "ley-35-2006:art-93-ahorro"]``. The runtime
computes ``fixed_addition + marginal_rate * (base - lower_bound)`` for the bracket
covering the supplied base liquidable del ahorro.

Expected values are NOT hand-computed from the registry formula. They are
transcribed from external AEAT/BOE authority: the "Cuota íntegra – Euros" column
of the art. 93.2.e).2.º escala published verbatim in the bundled consolidated
Ley 35/2006 (``corpus/normatives/html/ley-35-2006.html#a93``, redacción vigente
con efectos 1-1-2025 tras la disp. final 7.3 de la Ley 7/2024, BOE-A-2024-26694):

    Base liquidable del ahorro   Cuota íntegra   Resto base    Tipo
    Hasta euros                  Euros           Hasta euros   Porcentaje
    0                            0               6.000         19
    6.000,00                     1.140           44.000        21
    50.000,00                    10.380          150.000       23
    200.000,00                   44.880          100.000       27
    300.000,00                   71.880          En adelante   30

At each breakpoint the cuota equals the bracket's published cumulative cuota
íntegra; mid-bracket amounts are derived from the published breakpoint plus the
published marginal rate, exactly the external-oracle arithmetic the law fixes.
The escala is Beckham-specific by legal basis (art. 93.2.e).2.º) and structure —
a single unified table with no autonomic split — not by its top rate: for 2025
the general IRPF savings top (art. 66+76) is also 30% after Ley 7/2024. The
oracle pins the art. 93 bracket amounts/thresholds, guarding the table structure.

See Also:
    :class:`~domain.calculations.registry.ParameterDefinition`
        Registry parameter record that carries the bracket table under test.
    :class:`~domain.calculations.registry.BracketEntry`
        Per-band cumulative cuota and marginal-rate rows asserted here.
    :class:`~domain.calculations.registry.ModeloRevision`
        Revision container that splits the 2015 and 2025 Modelo 151 schemas.
    :func:`~domain.calculations.registry._formula_runtime._resolve_bracket`
        Runtime bracket resolver exercised directly by these oracle checks.
    :exc:`~domain.calculations.registry.RegistryValidationError`
        Raised when the required filing-period axis is missing.
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_modelo`
        Test helper that loads the committed registry definition.
    :mod:`~application.calculations.tests.test_modelo_151_beckham_cuota_continuity`
        Application-level companion for the Modelo 151 cuota calculation chain.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from ..errors import RegistryValidationError
from .._formula_runtime import _resolve_bracket
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION = "2025-y-siguientes"
_PARAM_ID = "modelo-151.escala-cuota-integra-ahorro"
_AS_OF = {"filing_period": date(2025, 12, 31)}


@cache
def _ahorro_table():
    modelo, _ = _committed_modelo("151")
    revision = modelo.revisions[_REVISION]
    return next(p for p in revision.parameters if p.id == _PARAM_ID)


def test_escala_ahorro_declares_art_93_legal_refs() -> None:
    table = _ahorro_table()
    assert table.data_type == "bracket_table"
    assert "ley-35-2006:art-93" in table.legal_refs
    assert "ley-35-2006:art-93-ahorro" in table.legal_refs


def test_escala_ahorro_absent_from_2015_revision() -> None:
    """The pre-escala revision must NOT carry the savings escala, so a filing
    for those years keeps the general-only engine and never resolves an
    ungrounded savings bracket.

    The cut-off is 2023, not 2025. The impatriado savings escala was introduced
    by art. 63.3 of Ley 31/2022 with effect from 2023-01-01
    (`ley-35-2006:art-93-ahorro-2023`, effective 2023-01-01..2024-12-31) and
    RE-fixed for 2025 onward (`ley-35-2006:art-93-ahorro`, effective
    2025-01-01). Reading the later redaction as the introduction is what put
    "2025 amendment (Ley 7/2024)" here; the registry carries both refs, so the
    revision governing 2023 onward SHOULD carry the escala.

    The revision id also moved: the 2015-y-siguientes revision was split, and
    the pre-escala half is `2015-2022`, which ends 2022-12-31 -- exactly the day
    before the escala took effect.
    """
    modelo, _ = _committed_modelo("151")
    revision_2015 = modelo.revisions["2015-2022"]
    assert revision_2015.valid_to == date(2022, 12, 31)
    assert all(p.id != _PARAM_ID for p in revision_2015.parameters)


def test_escala_ahorro_zero_base_resolves_zero() -> None:
    assert _resolve_bracket(_ahorro_table(), Decimal("0"), _AS_OF) == Decimal("0")


@pytest.mark.parametrize(
    ("breakpoint", "published_cuota_integra"),
    [
        (Decimal("6000"), Decimal("1140")),
        (Decimal("50000"), Decimal("10380")),
        (Decimal("200000"), Decimal("44880")),
        (Decimal("300000"), Decimal("71880")),
    ],
)
def test_escala_ahorro_breakpoint_matches_published_cuota_integra(
    breakpoint: Decimal,
    published_cuota_integra: Decimal,
) -> None:
    """At each breakpoint the cuota equals the BOE-published cumulative cuota
    íntegra of the bracket starting there (art. 93.2.e.2º table column 2)."""
    assert _resolve_bracket(_ahorro_table(), breakpoint, _AS_OF) == published_cuota_integra


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        # 50.000 breakpoint (10.380) + 23% on the excess to 100.000.
        (Decimal("100000"), Decimal("10380") + Decimal("0.23") * Decimal("50000")),
        # 200.000 breakpoint (44.880) + 27% on the excess to 250.000.
        (Decimal("250000"), Decimal("44880") + Decimal("0.27") * Decimal("50000")),
        # 300.000 breakpoint (71.880) + the Beckham-specific 30% top rate.
        (Decimal("400000"), Decimal("71880") + Decimal("0.30") * Decimal("100000")),
    ],
)
def test_escala_ahorro_mid_bracket_matches_boe_arithmetic(base: Decimal, expected: Decimal) -> None:
    """Mid-bracket cuota = published breakpoint cumulative + published marginal
    rate on the excess — the escala arithmetic the BOE fixes, never the registry
    formula re-run. The 400.000 case pins the 30% Beckham top rate."""
    assert _resolve_bracket(_ahorro_table(), base, _AS_OF) == expected.quantize(Decimal("0.01"))


def test_escala_ahorro_top_bracket_is_beckham_art93_thirty_percent() -> None:
    """A €100.000 slice above 300.000 taxes at 30% (art. 93.2.e.2º) — an extra
    30.000 over the 71.880 breakpoint, pinning the Beckham art. 93.2.e.2º table.
    The durable distinction from the general savings scale (art. 66+76) is the
    legal basis and the single unified table with no autonomic split — NOT the
    marginal rate: for 2025 the general savings top is also 30% after Ley 7/2024,
    so this oracle guards the art. 93 bracket structure, not a rate difference."""
    at_300k = _resolve_bracket(_ahorro_table(), Decimal("300000"), _AS_OF)
    at_400k = _resolve_bracket(_ahorro_table(), Decimal("400000"), _AS_OF)
    assert at_400k - at_300k == Decimal("30000.00")


def test_escala_ahorro_requires_filing_period_axis() -> None:
    with pytest.raises(RegistryValidationError):
        _resolve_bracket(_ahorro_table(), Decimal("100000"), {})
