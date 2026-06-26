"""Durable independent guard: the retenciones empty-store contract is ADVISORY, not RAISE (#35).

#6's empty-store design is: on a revision that DECLARES the perceptor-count binding
with an EMPTY per-perceptor retención store, ``RetencionesAggregationSourceResolver``
RETURNS a :class:`CalculationSourceResolution` carrying a non-blocking advisory
:class:`CalculationSourceDiagnostic` + EMPTY binding_values — it neither raises nor
silently materialises a zero count. A hard ``raise`` would over-block a legitimate
declaración-negativa filer (the exact over-block the codex's RAISE variant was
rejected for); a silent zero would under-declare.

This guard is DELIBERATELY in its own file, separate from the resolver's own unit
test (``test_retenciones_aggregation_resolver.py``): a rewrite of the resolver that
flips it to ``raise`` tends to co-flip that unit test (so it self-consistently
passes). An independent guard in a file the rewrite does not touch reds loudly if a
RAISE ever lands on origin.

NOTE (codex working-tree WIP): while the codex's uncommitted RAISE rewrite of
``_modelo_bindings.py`` sits in the working tree, ``test_real_resolver_*`` below
reds locally — that is the guard CORRECTLY firing on the live RAISE, not a test
bug. It is GREEN against HEAD/origin (confirmed advisory) and in CI. The
``test_advisory_contract_logic_*`` case validates the assertion logic itself
against a hand-constructed resolution (no real resolver), so the contract is
proven sound independent of the working-tree resolver state.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core import BindingSourceKind, Period
from ....core.resources import resources
from ....domain.calculations.registry import ModeloRevision
from ....tests.secure_sql import isolated_runtime_profile
from .._modelo_bindings import RetencionesAggregationSourceResolver
from .._source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceResolution,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERCEPTOR_BINDING_ID = "modelo-180-115-perceptores-anual"
_SOURCE_KIND = "retenciones_aggregation"


def _assert_advisory_contract(resolution: CalculationSourceResolution) -> None:
    """The #6 empty-store contract: advisory diagnostic + empty binding_values, no silent zero."""
    # No silently-materialised count (a zero would under-declare).
    assert dict(resolution.binding_values) == {}, "empty store must NOT materialise a (silent) count"
    # A non-blocking advisory names the gap (no-silent-under-declaration).
    assert len(resolution.diagnostics) >= 1, "empty store must surface an advisory diagnostic"
    advisory = resolution.diagnostics[0]
    assert advisory.source_kind == _SOURCE_KIND
    assert "perceptor" in advisory.message.lower()


def _m180_revision_declaring_perceptor_count() -> ModeloRevision:
    """The real M180 revision; its perceptor-count binding is the retenciones_aggregation source."""
    snapshot = resources().modelos.authority.snapshot("180", filing_year=2024, period="0A")
    existing = next(b for b in snapshot.revision.bindings if str(b.id) == _PERCEPTOR_BINDING_ID)
    flipped = existing.model_copy(update={"source": BindingSourceKind.RETENCIONES_AGGREGATION})
    other = tuple(b for b in snapshot.revision.bindings if str(b.id) != _PERCEPTOR_BINDING_ID)
    return snapshot.revision.model_copy(update={"bindings": (flipped, *other)})


def _context(revision: ModeloRevision) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id="operator",
        modelo="180",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "0A"),
        revision=revision,
    )


def test_advisory_contract_logic_accepts_advisory_and_rejects_silent_zero() -> None:
    """Validate the guard's assertion LOGIC against hand-constructed resolutions (no real resolver).

    Proves the contract check is sound regardless of the working-tree resolver: it
    ACCEPTS the advisory+empty shape and REJECTS a silently-materialised zero.
    """
    advisory_resolution = CalculationSourceResolution(
        resolver_id=_SOURCE_KIND,
        owned_sources=(BindingSourceKind.RETENCIONES_AGGREGATION,),
        binding_values={},
        diagnostics=(
            CalculationSourceDiagnostic(
                reason="source_issue",
                source_kind=_SOURCE_KIND,
                resolver_id=_SOURCE_KIND,
                message="Modelo 180 declares a perceptor-count binding but no per-perceptor records exist.",
            ),
        ),
    )
    # The advisory shape satisfies the contract.
    _assert_advisory_contract(advisory_resolution)

    # A silently-materialised zero (count 0, NO advisory) must FAIL the contract.
    silent_zero = CalculationSourceResolution(
        resolver_id=_SOURCE_KIND,
        owned_sources=(BindingSourceKind.RETENCIONES_AGGREGATION,),
        binding_values={_PERCEPTOR_BINDING_ID: Decimal(0)},
        diagnostics=(),
    )
    with pytest.raises(AssertionError):
        _assert_advisory_contract(silent_zero)


def test_real_resolver_empty_store_returns_advisory_not_raise(tmp_path: Path) -> None:
    """The real resolver on an empty store RETURNS the advisory contract — never raises, never 0.

    GREEN against HEAD/origin (advisory). Reds locally ONLY while the codex's
    uncommitted RAISE rewrite of _modelo_bindings.py sits in the working tree —
    that local red is this guard correctly firing on the live RAISE.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        resolution = RetencionesAggregationSourceResolver().resolve(
            _context(_m180_revision_declaring_perceptor_count()),
        )
        _assert_advisory_contract(resolution)
