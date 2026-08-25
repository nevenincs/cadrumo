"""A source-backed binding with no live resolver cannot silently calculate zero.

This is the application-layer live-mesh source-connectivity gate. It joins the
committed registry source inventory
(``RegistryQueryService.source_inventory`` — the domain-side report) against the
live enrolled resolver set (``BUCKET_AGGREGATION_OWNED_SOURCES``, derived from
every enrolled resolver's ``owned_sources`` plus the pre-mesh tiers and
``manual_input``) and the disposition taxonomy
(``build_binding_source_dispositions``), and proves three anti-silent-zero
invariants:

* every source kind the committed registry declares resolves ``ENROLLED`` or
  ``DEFERRED`` under the live mesh — a declared kind owned by no live resolver
  and not explicitly deferred would classify ``RESERVED`` and fail here;
* the accepted-source set the live novel-source gate enforces
  (``ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS``) covers every declared kind, so no
  declared source is a novel silent-blank; and
* a novel (unaccounted) binding source raises ``ModeloAggregationBindingError``
  at the gate rather than compiling into a silently-zero revision.

The registry-inventory integrity half (no committed revision declares a reserved
kind) lives in the domain companion
``domain/calculations/registry/tests/test_source_enrollment.py``.

See Also:
    :class:`BindingSourceKind`
        Closed source-kind enum whose committed members are audited here.
    :class:`~domain.calculations.registry.RegistryQueryService`
        Domain query service that supplies the source-inventory report.
    :class:`~domain.calculations.registry.DataBindingDefinition`
        Binding schema mutated in the novel-source anti-tautology check.
    :func:`~application.aggregation.build_binding_source_dispositions`
        Builds the enrolled/deferred/reserved taxonomy used by this gate.
    :class:`~application.aggregation.BindingSourceDisposition`
        Disposition enum this gate accepts only as enrolled or deferred.
    :func:`~application.modelo.assert_no_novel_source_kinds`
        Live calculate-path guard proved by the synthetic source case.
    :exc:`~application.modelo.ModeloAggregationBindingError`
        Loud failure raised for novel source kinds instead of silent zero.
    :mod:`~domain.calculations.registry.tests.test_source_enrollment`
        Domain companion that verifies committed registry inventory.
"""

from __future__ import annotations

import pytest

from ....core import BindingSourceKind
from ....core.resources import resources
from cadrumo.domain.calculations.registry.schema import DataBindingDefinition
from cadrumo.domain.calculations.registry.queries import RegistryQueryService
from ...aggregation import (
    BindingSourceDisposition,
    build_binding_source_dispositions,
)
from .._action_errors import ModeloAggregationBindingError
from .._calculation_actions import assert_no_novel_source_kinds
from .._calculation_source_policy import (
    ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS,
    BUCKET_AGGREGATION_OWNED_SOURCES,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _declared_source_kinds() -> frozenset[BindingSourceKind]:
    report = RegistryQueryService(resources().modelos.authority).source_inventory()
    return report.declared_source_kinds


def test_declared_source_kinds_are_non_empty() -> None:
    """Anti-vacuity floor: the committed registry declares source kinds to test against."""
    assert _declared_source_kinds(), "no declared source kinds — the connectivity assertions would be vacuous"


def test_every_declared_source_kind_resolves_enrolled_or_deferred_under_live_mesh() -> None:
    """Each committed-registry source kind is routed by a live resolver or explicitly advised.

    Reads each declared kind's disposition from the disposition registry built
    over the LIVE enrolled set (``BUCKET_AGGREGATION_OWNED_SOURCES``). A declared
    kind that no live resolver owns and that is not explicitly deferred would
    classify ``RESERVED`` here — the silent-blank ``aeat-calculation-aggregation``
    defect — and this gate would enumerate it.
    """
    dispositions = build_binding_source_dispositions(BUCKET_AGGREGATION_OWNED_SOURCES)
    offenders: list[str] = []
    for kind in sorted(_declared_source_kinds(), key=lambda source: source.value):
        disposition = dispositions[kind]
        if disposition not in {BindingSourceDisposition.ENROLLED, BindingSourceDisposition.DEFERRED}:
            offenders.append(f"{kind.value} -> {disposition.value}")
    assert not offenders, (
        "Committed-registry source kinds resolve to neither an enrolled resolver nor a deferred advisory "
        "under the live mesh — each would silently calculate zero:\n" + "\n".join(f"  * {o}" for o in offenders)
    )


def test_accepted_source_kinds_cover_every_declared_source_kind() -> None:
    """The live novel-source gate accepts every declared kind, so none is rejected-or-blanked as novel.

    ``ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS`` is exactly the set
    ``assert_no_novel_source_kinds`` checks each binding against on the live
    calculate path. If a declared kind fell outside it, calculation would raise
    (never silently zero) — but a permanently-rejected declared kind is itself a
    connectivity defect, so this asserts full coverage.
    """
    declared = _declared_source_kinds()
    uncovered = sorted(kind.value for kind in declared - ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS)
    assert not uncovered, f"declared source kinds outside the accepted live-mesh set: {uncovered}"


def test_accepted_set_excludes_reserved_kinds() -> None:
    """Anti-tautology: the accepted set is a proper subset — a reserved kind is not accepted.

    If ``ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS`` trivially contained every
    member, the coverage assertion above would be vacuous. Every reserved kind is
    excluded, so a reserved-but-declared source would be rejected as novel, not
    silently zeroed.
    """
    from ...aggregation import RESERVED_SOURCE_KINDS

    assert RESERVED_SOURCE_KINDS, "expected a non-empty reserved set for this anti-tautology proof"
    for reserved_kind in RESERVED_SOURCE_KINDS:
        assert reserved_kind not in ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS


def test_novel_source_binding_raises_not_silent_zero() -> None:
    """A binding whose source is unknown to the live mesh raises rather than blanking.

    ``model_construct`` bypasses the ``BindingSourceKind`` field validation so a
    source token absent from the enrolled and deferred sets can be injected —
    exactly the TOML-authoring mistake the gate must convert from a silent zero
    into a loud ``ModeloAggregationBindingError`` at calculate time.
    """
    # Resolved from (modelo, filing year, period) rather than indexed by a
    # literal revision id: AEAT re-cuts revision layouts, and this modelo's
    # a broad M303 revision was decomposed into four narrower revisions.
    revision = resources().modelos.authority.snapshot("303", filing_year=2025, period="1T").revision
    synthetic = DataBindingDefinition.model_construct(
        id="synthetic-missing-source-binding",
        source="synthetic_unrouted_source_qqq",
    )
    patched = revision.model_copy(update={"bindings": (*revision.bindings, synthetic)})

    with pytest.raises(ModeloAggregationBindingError) as exc_info:
        assert_no_novel_source_kinds(patched)

    context = exc_info.value.context
    assert context is not None
    novel_kinds = context["novel_source_kinds"]
    assert isinstance(novel_kinds, list)
    assert "synthetic_unrouted_source_qqq" in novel_kinds
