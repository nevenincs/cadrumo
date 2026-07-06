"""Fincas and inventory source-mesh readiness resolvers refuse visibly.

The fincas domain and the inventory application service both hold real
aggregates, but neither is persisted through the canonical secure-storage
revision boundary yet, so they must not be enrolled as live calculation
sources. The ``no-dormant-source-resolvers`` rule still applies: the surface is
provisioned and its unreadiness is made visible through a
``source_domain_not_ready`` blocked-readiness diagnostic rather than a silent
blank.

These tests are the fail-closed proof of that contract. They assert that each
readiness resolver:

* reports its domain as not ready (the pure-domain / pure-application readiness
  fact);
* resolves no binding value on any channel and owns no binding source
  (``owned_sources == ()``) — it cannot contribute to a calculation even if
  merged;
* emits exactly one ``source_domain_not_ready`` diagnostic carrying the domain's
  blocking reason and ``binding_source is None`` (an advisory category, not a
  registry binding source); and

that neither ``fincas`` nor ``inventory`` is a member of the closed
:class:`~aeat.core.BindingSourceKind` taxonomy — so neither can appear in the
enrolled, deferred, or reserved source sets (all ``frozenset[BindingSourceKind]``),
the structural guarantee that they are not enrolled in the live mesh — while the
live novel-source boundary gate (``assert_no_novel_source_kinds``) stays green on
a revision carrying an accepted source, unaffected by the provisioned-but-blocked
readiness surface.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ....core import BindingSourceKind, Period
from ....domain.calculations.registry import DataBindingDefinition, ModeloRevision, PeriodSelector
from ...modelo import ModeloAggregationBindingError, assert_no_novel_source_kinds
from .._source_fincas import FincasSourceReadinessResolver
from .._source_inventory import InventorySourceReadinessResolver
from .._source_mesh import (
    CalculationSourceContext,
    CalculationSourceResolution,
    merge_source_resolutions,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "30300000-0000-4000-8000-000000000303"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_LEGAL_REFS = ("ley-58-2003:art-93",)
_SOURCE_REFS = ("test-source-mesh-readiness",)


def _readiness_revision(*bindings: DataBindingDefinition) -> ModeloRevision:
    return ModeloRevision(
        id="source-mesh-readiness-test",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(years=(2026,), periods=("1T",)),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
        bindings=bindings,
    )


def _accepted_source_revision() -> ModeloRevision:
    return _readiness_revision(
        DataBindingDefinition(
            id="source-mesh-readiness-manual-input",
            source=BindingSourceKind.MANUAL_INPUT,
            selector={
                "record": "DPA",
                "field": "readiness",
                "offset": 1,
                "length": 1,
                "data_type": "integer",
            },
            legal_refs=_LEGAL_REFS,
            source_refs=_SOURCE_REFS,
        ),
    )


def _context() -> CalculationSourceContext:
    """Build a calculation context; the readiness resolvers ignore its revision."""
    return CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision=_readiness_revision(),
        calculated_at=_T0,
    )


def _assert_resolves_no_value(resolution: CalculationSourceResolution) -> None:
    """A blocked-readiness resolution contributes no calculation value on any channel."""
    assert resolution.owned_sources == ()
    assert dict(resolution.binding_values) == {}
    assert dict(resolution.enum_binding_values) == {}
    assert dict(resolution.date_binding_values) == {}
    assert dict(resolution.row_binding_values) == {}
    assert dict(resolution.relation_values) == {}
    assert dict(resolution.bound_inputs_by_casilla_id) == {}
    assert resolution.detail_rows == ()
    assert tuple(resolution.source_transaction_ids) == ()
    assert resolution.provenance == ()
    assert resolution.borrador_provenance is None


def test_fincas_resolver_emits_only_blocked_readiness_and_no_value() -> None:
    """The fincas resolver refuses visibly: one ``source_domain_not_ready``, no value."""
    resolution = FincasSourceReadinessResolver().resolve(_context())

    _assert_resolves_no_value(resolution)
    assert len(resolution.diagnostics) == 1
    (diagnostic,) = resolution.diagnostics
    assert diagnostic.reason == "source_domain_not_ready"
    assert diagnostic.source_kind == "fincas"
    assert diagnostic.binding_source is None
    assert diagnostic.resolver_id == "fincas_readiness"
    assert diagnostic.message


def test_inventory_resolver_emits_only_blocked_readiness_and_no_value() -> None:
    """The inventory resolver refuses visibly: one ``source_domain_not_ready``, no value."""
    resolution = InventorySourceReadinessResolver().resolve(_context())

    _assert_resolves_no_value(resolution)
    assert len(resolution.diagnostics) == 1
    (diagnostic,) = resolution.diagnostics
    assert diagnostic.reason == "source_domain_not_ready"
    assert diagnostic.source_kind == "inventory"
    assert diagnostic.binding_source is None
    assert diagnostic.resolver_id == "inventory_readiness"
    assert diagnostic.message


def test_merging_readiness_resolutions_enrolls_no_source_and_no_value() -> None:
    """Even merged into the mesh, the readiness resolvers add no source and no value.

    ``merge_source_resolutions`` is the exact merge the live calculate path uses;
    passing both readiness resolutions through it proves that IF they were enrolled
    they would still own no source and resolve no binding — only surface the two
    blocked-readiness advisories.
    """
    context = _context()
    merged = merge_source_resolutions(
        (
            FincasSourceReadinessResolver().resolve(context),
            InventorySourceReadinessResolver().resolve(context),
        ),
    )

    _assert_resolves_no_value(merged)
    reasons = {diagnostic.reason for diagnostic in merged.diagnostics}
    source_kinds = {diagnostic.source_kind for diagnostic in merged.diagnostics}
    assert reasons == {"source_domain_not_ready"}
    assert source_kinds == {"fincas", "inventory"}


def test_readiness_source_kinds_are_outside_the_binding_source_taxonomy() -> None:
    """``fincas`` / ``inventory`` are not ``BindingSourceKind`` members — cannot be enrolled.

    The enrolled, deferred, and reserved source sets consumed by the live mesh are
    all ``frozenset[BindingSourceKind]``. A source kind that is not a member of that
    closed taxonomy cannot appear in any of them, so this is the structural guarantee
    that the readiness surfaces are not enrolled as live calculation sources.
    """
    taxonomy = {kind.value for kind in BindingSourceKind}
    assert "fincas" not in taxonomy
    assert "inventory" not in taxonomy


def test_readiness_resolvers_own_no_binding_source() -> None:
    """Both readiness resolvers declare ``owned_sources == ()`` — they claim no live source."""
    assert FincasSourceReadinessResolver().owned_sources == ()
    assert InventorySourceReadinessResolver().owned_sources == ()


def test_novel_source_boundary_gate_stays_green_with_readiness_provisioned() -> None:
    """The live novel-source gate accepts known sources, unaffected by the readiness surface.

    The provisioned-but-blocked readiness resolvers introduce no registry binding
    source, so ``assert_no_novel_source_kinds`` — which rejects any binding source
    absent from the enrolled/deferred sets — must not raise for an accepted source.
    """
    try:
        assert_no_novel_source_kinds(_accepted_source_revision())
    except ModeloAggregationBindingError as error:  # pragma: no cover - failure path
        pytest.fail(f"novel-source gate unexpectedly rejected an accepted source: {error}")
