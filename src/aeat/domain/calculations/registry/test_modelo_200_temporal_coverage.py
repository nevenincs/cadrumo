"""Modelo 200 pyme bracket temporal coverage regression.

LIS Art. 29 pyme/micro-empresa rates apply across the full
``2024-y-siguientes`` revision date range (2024-01-01 onward).  Before the
W03.P14.S56 backfill the ``is.modelo-200.tipo-gravamen-pyme`` bracket table
had windows only from 2025-01-01, so any 2024 filing_period raised a
``bracket_no_window`` runtime error.

Two invariants are pinned here:

1. A Modelo 200 cuota calculation for a 2024 fiscal year with a pyme-form
   (``sl``) profile resolves without raising ``bracket_no_window`` — the
   2024 window at 23 % is present and the formula executes cleanly.

2. The ``validate_bracket_table_temporal_coverage`` validator fires on a
   deliberately gapped parameter fixture, confirming the detection logic is
   not tautological: removing the check leaves the coverage gap silent.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import lru_cache

import pytest

from aeat.core.resources import bundled_path

from . import build_snapshot, load_registry_tree
from ._errors import RegistryValidationError
from ._schema import ParameterDefinition
from ._validate_revision_rules import (
    _bracket_coverage_gaps,
    validate_bracket_table_temporal_coverage,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_DISPATCH_BINDING = "modelo-200-2024-profile-legal-entity-form"


@lru_cache(maxsize=1)
def _load_modelo_200():
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == "200")
    return modelo, catalogues


@lru_cache(maxsize=1)
def _snapshot_2024():
    modelo, catalogues = _load_modelo_200()
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )


# ---------------------------------------------------------------------------
# 1. 2024 pyme filing resolves without bracket_no_window
# ---------------------------------------------------------------------------


def test_pyme_sl_2024_cuota_resolves_without_bracket_no_window() -> None:
    """A 2024 IS filing for an SL (pyme/micro-empresa profile) must not raise.

    Before the S56 backfill the ``is.modelo-200.tipo-gravamen-pyme``
    bracket table had no window for dates in 2024, so
    ``_formula_runtime.apply_bracket_table`` raised
    ``bracket_no_window``.  The 2024 bracket at 23 % (LIS Art. 29
    pre-2025 pyme flat rate) must now exist and the cuota calculation
    must complete without error.
    """
    from ._formula_runtime import calculate_registry_snapshot

    # The micro-empresa lane applies when INCN < 1.000.000 EUR (LIS Art. 29.1).
    # Supply INCN = 500.000 EUR to route through the pyme bracket table.
    # Base imponible 00552 = 100.000 EUR; casilla 01330 (post-nivelación base)
    # equals 00552 when nivelación corrections 01033/01034 are zero.
    result = calculate_registry_snapshot(
        _snapshot_2024(),
        inputs={
            "DP200014:00552": Decimal("100000"),
            "DP200014:01033": Decimal("0"),
            "DP200014:01034": Decimal("0"),
            "DP200014B:00592": Decimal("0"),
            "DP200014B:01766": Decimal("0"),
            "DP200014B:01784": Decimal("0"),
            "DP200026:00625": Decimal("100"),
        },
        enum_binding_values={_DISPATCH_BINDING: "sl"},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            # INCN below 1.000.000 EUR → micro-empresa lane → tipo-gravamen-pyme bracket
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("500000"),
        },
        relation_values={"modelo-200-2024-rel-202-pagos-fraccionados": Decimal("0")},
        date_context={"filing_period": date(2024, 12, 31)},
    )
    # The cuota íntegra for a micro-empresa SL at the 2024 flat pyme rate
    # (23 %, LIS Art. 29 pre-2025 regime) on a 100.000 EUR base must be
    # 23.000 EUR.  External authority: LIS Art. 29 (BOE-A-2014-12328) as
    # in force for ejercicios iniciados en 2024; AEAT Manual de
    # Sociedades "Tipos de gravamen" 2024.
    assert result.values["DP200014:00562"] == Decimal("23000.00"), (
        "cuota íntegra for micro-empresa SL on 100.000 EUR base at 23 % must be 23.000 EUR"
    )


def test_pyme_bracket_2024_window_is_present_in_registry() -> None:
    """The 2024 pyme bracket window exists at 23 % in the registry.

    After the S56 backfill ``is.modelo-200.tipo-gravamen-pyme`` must carry a
    window covering 2024-01-01 – 2024-12-31 with ``marginal_rate = 0.23``.
    This tests the registry encoding directly against the LIS Art. 29 2024
    authority; it is not a recomputation of the formula.
    """
    parameters = {p.id: p for p in _snapshot_2024().revision.parameters}
    parameter = parameters["is.modelo-200.tipo-gravamen-pyme"]
    brackets_2024 = [
        b for b in parameter.brackets if b.valid_from == date(2024, 1, 1)
    ]
    assert brackets_2024, (
        "is.modelo-200.tipo-gravamen-pyme must have at least one bracket for 2024-01-01"
    )
    # The 2024 flat rate was 23 % (pre-tranche regime).
    assert any(b.marginal_rate == Decimal("0.23") for b in brackets_2024), (
        "2024 bracket must carry the LIS Art. 29 pre-2025 pyme flat rate of 23 %"
    )


# ---------------------------------------------------------------------------
# 2. Coverage-gap validator anti-tautology probe
# ---------------------------------------------------------------------------


def test_coverage_validator_fires_on_deliberate_gap() -> None:
    """``_bracket_coverage_gaps`` catches a gap in a fixture parameter.

    This is an anti-tautology probe: if the gap detector never fires the S58
    regression test cannot distinguish a silent gap from a covered one.
    A ``ParameterDefinition`` fixture is constructed with ``bracket_axis =
    "filing_period"`` and brackets covering only 2025-01-01 onward — matching
    the exact pre-backfill state that was the original bug.  The detector must
    return at least one gap tuple and that gap must start at 2024-01-01.

    ``model_construct`` bypasses pydantic validation so the fixture can carry
    minimal fields without satisfying the production non-empty ref constraints.
    """
    from ._schema import BracketEntry

    bracket_2025 = BracketEntry(
        lower_bound=Decimal("0"),
        fixed_addition=Decimal("0"),
        marginal_rate=Decimal("0.17"),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )
    gapped_parameter = ParameterDefinition.model_construct(
        id="test.gapped-bracket-table",
        data_type="bracket_table",
        unit="EUR",
        bracket_axis="filing_period",
        brackets=(bracket_2025,),
        values=(),
    )

    gaps = _bracket_coverage_gaps(
        gapped_parameter,
        revision_from=date(2024, 1, 1),
        revision_to=date(2024, 12, 31),
    )
    assert gaps, (
        "_bracket_coverage_gaps must detect the 2024 gap when brackets start at 2025"
    )
    assert gaps[0][0] == date(2024, 1, 1), (
        "gap must start at the revision's valid_from (2024-01-01)"
    )


def test_coverage_validator_passes_when_no_gap() -> None:
    """The validator must not flag a fully covered parameter as gapped.

    A ``bracket_table`` parameter whose windows start at ``revision_from``
    and extend to ``revision_to`` without interruption must produce zero
    failures.  This guards against false positives in the coverage check.
    """
    from ._schema import BracketEntry

    bracket_2024 = BracketEntry(
        lower_bound=Decimal("0"),
        fixed_addition=Decimal("0"),
        marginal_rate=Decimal("0.23"),
        valid_from=date(2024, 1, 1),
        valid_to=date(2024, 12, 31),
    )
    bracket_2025 = BracketEntry(
        lower_bound=Decimal("0"),
        fixed_addition=Decimal("0"),
        marginal_rate=Decimal("0.17"),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )
    covered_parameter = ParameterDefinition.model_construct(
        id="test.covered-bracket-table",
        data_type="bracket_table",
        unit="EUR",
        bracket_axis="filing_period",
        brackets=(bracket_2024, bracket_2025),
        values=(),
    )

    gaps = _bracket_coverage_gaps(
        covered_parameter,
        revision_from=date(2024, 1, 1),
        revision_to=date(2025, 12, 31),
    )
    assert not gaps, (
        "_bracket_coverage_gaps must not flag a parameter whose windows cover the full revision range"
    )
