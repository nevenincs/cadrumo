"""Reflective gate: every exported source-mesh resolver is enrolled or classified.

The rule (no-dormant-source-resolvers, aeat-architecture-boundaries): every class
that satisfies the :class:`ModeloSourceResolver` structural protocol
(``resolver_id`` + ``owned_sources`` + ``resolve``) and is reachable from a
package public surface (``__all__``) MUST be enrolled on the live calculate path —
either inside the ``merge_source_resolutions`` mesh tuple in
``_resolve_bucket_source_mesh`` (``_calculation_actions.py``) or as a documented
pre-mesh resolver called directly on the production calculate path.

A second shape of resolver — a ``resolve``-bearing class that does NOT satisfy the
source-mesh protocol (it lacks ``resolver_id`` / ``owned_sources``), such as the
explicit multi-year scan API — is enumerated separately and must be recorded as a
known non-mesh resolver with a stated reason. A newly-added dormant resolver of
either shape then fails this gate immediately instead of resolving silently to a
blank casilla.

Discovery is purely class-level and never constructs a resolver: several resolvers
take required keyword-only dependencies, so a no-argument construction probe would
silently skip them and let an arg-requiring resolver evade the gate. Membership is
checked against the protocol members on the class object directly.
"""

from __future__ import annotations

import importlib
import inspect

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Packages that publish resolver symbols through their ``__all__`` surface.
_RESOLVER_PACKAGES = (
    "aeat.application.aggregation",
    "aeat.application.calculations",
    "aeat.application.invoices",
    "aeat.application.modelo",
)

# The structural members that define the source-mesh resolver protocol.
_SOURCE_MESH_MEMBERS = ("resolver_id", "owned_sources", "resolve")

# The protocol class itself carries the members and is exported; it is the
# contract, not a concrete resolver, so it is excluded from the enrolled sweep.
_PROTOCOL_QUALNAME = "aeat.application.aggregation.ModeloSourceResolver"

# Concrete source-mesh resolvers that are live on the production calculate path.
# Eight are wired into the ``merge_source_resolutions`` tuple inside
# ``_resolve_bucket_source_mesh``; three are pre-mesh resolvers invoked directly
# on the production calculate path (the iva-wallet gate and the binding-resolution
# gate). All eleven are enrolled — none may resolve to a silent blank.
_ENROLLED_SOURCE_MESH_RESOLVERS = frozenset(
    {
        "aeat.application.aggregation.LedgerIvaAggregationSourceResolver",
        "aeat.application.aggregation.LedgerRentaExpenseAggregationSourceResolver",
        "aeat.application.aggregation.LedgerRentaGastoAggregationSourceResolver",
        "aeat.application.aggregation.LedgerRentaIncomeAggregationSourceResolver",
        "aeat.application.aggregation.OssIossLedgerSourceResolver",
        "aeat.application.aggregation.ProfileSourceResolver",
        "aeat.application.calculations.IvaWalletDecisionSourceResolver",
        "aeat.application.calculations.PreviousFilingSourceResolver",
        "aeat.application.calculations.RelationPrefillSourceResolver",
        "aeat.application.invoices.InvoiceCatalogueSourceResolver",
        "aeat.application.modelo.Modelo100BorradorSourceResolver",
    }
)

# Exported ``resolve``-bearing classes that are deliberately NOT source-mesh
# resolvers. Each carries a stated reason. This mapping must only shrink (when a
# class is enrolled or removed); a new unclassified entry fails the gate.
_KNOWN_NON_MESH_RESOLVERS: dict[str, str] = {
    "aeat.application.calculations.MultiYearResolver": (
        "Explicit multi-year scan API for the M200 base-imponible-negativa carry "
        "and the M303 prorrata. It exposes only resolve(); it is not a source-mesh "
        "resolver (no resolver_id / owned_sources) and is intentionally not wired "
        "into the calculate mesh. Its dormancy is separately adjudicated and tracked."
    ),
}


def _discover_resolve_bearing_classes() -> dict[str, bool]:
    """Return {qualified_name: is_source_mesh} for every exported resolver class.

    A class qualifies if it is exported via a package ``__all__`` and carries a
    ``resolve`` method. ``is_source_mesh`` is True when the class also carries the
    remaining protocol members (``resolver_id`` and ``owned_sources``). No instance
    is constructed: the check reads the class object directly so a resolver with
    required constructor dependencies is still discovered.
    """
    discovered: dict[str, bool] = {}
    for package_name in _RESOLVER_PACKAGES:
        module = importlib.import_module(package_name)
        for name in getattr(module, "__all__", []):
            obj = getattr(module, name, None)
            if not inspect.isclass(obj):
                continue
            if not hasattr(obj, "resolve"):
                continue
            is_source_mesh = all(hasattr(obj, member) for member in _SOURCE_MESH_MEMBERS)
            discovered[f"{package_name}.{name}"] = is_source_mesh
    return discovered


def test_every_discovered_resolver_is_enrolled_or_classified() -> None:
    """Every exported resolver class is enrolled (source-mesh) or recorded (non-mesh).

    This is the gate the dormancy review found missing: a new exported resolver
    that is neither enrolled in the live mesh nor recorded as a known non-mesh
    resolver surfaces here immediately instead of silently resolving to blank.
    """
    discovered = _discover_resolve_bearing_classes()
    assert discovered, (
        "Discovery returned no resolver classes — the package surface or the "
        "discovery logic is broken. Check that _RESOLVER_PACKAGES lists the right "
        "module paths and that the resolver symbols are still exported."
    )

    unclassified: list[str] = []
    for qualified_name, is_source_mesh in discovered.items():
        if qualified_name == _PROTOCOL_QUALNAME:
            continue
        if is_source_mesh:
            if qualified_name not in _ENROLLED_SOURCE_MESH_RESOLVERS:
                unclassified.append(
                    f"{qualified_name}: satisfies the source-mesh protocol but is "
                    f"not in _ENROLLED_SOURCE_MESH_RESOLVERS — enroll it in the live "
                    f"mesh (or as a documented pre-mesh resolver) and add it here."
                )
        elif qualified_name not in _KNOWN_NON_MESH_RESOLVERS:
            unclassified.append(
                f"{qualified_name}: exposes resolve() but is not a source-mesh "
                f"resolver and is not in _KNOWN_NON_MESH_RESOLVERS — enroll it or "
                f"record it as a known non-mesh resolver with a stated reason."
            )

    assert not unclassified, (
        "The following exported resolver classes are neither enrolled in the live "
        "source mesh nor classified as known non-mesh resolvers:\n\n"
        + "\n".join(f"  * {item}" for item in unclassified)
    )


def test_enrolled_resolvers_exist_and_satisfy_the_protocol() -> None:
    """Every name in _ENROLLED_SOURCE_MESH_RESOLVERS is still an exported source-mesh class.

    Guards against the declared enrolled set drifting away from the live surface —
    a renamed, removed, or protocol-broken resolver is caught here rather than
    silently dropping out of the gate.
    """
    discovered = _discover_resolve_bearing_classes()
    missing: list[str] = []
    not_source_mesh: list[str] = []
    for qualified_name in sorted(_ENROLLED_SOURCE_MESH_RESOLVERS):
        if qualified_name not in discovered:
            missing.append(qualified_name)
        elif not discovered[qualified_name]:
            not_source_mesh.append(qualified_name)

    assert not missing, (
        "Declared enrolled resolvers no longer exported from any package __all__ "
        "(renamed or removed?):\n" + "\n".join(f"  * {name}" for name in missing)
    )
    assert not not_source_mesh, (
        "Declared enrolled resolvers no longer satisfy the source-mesh protocol "
        "(resolver_id / owned_sources / resolve):\n" + "\n".join(f"  * {name}" for name in not_source_mesh)
    )


def test_known_non_mesh_resolvers_still_exported() -> None:
    """Every recorded non-mesh resolver is still exported and is still resolve-only.

    Guards against a non-mesh resolver being silently removed (leaving a stale
    record) or quietly upgraded into a source-mesh resolver without enrollment.
    """
    discovered = _discover_resolve_bearing_classes()
    for qualified_name, reason in _KNOWN_NON_MESH_RESOLVERS.items():
        assert qualified_name in discovered, (
            f"Recorded non-mesh resolver {qualified_name} is no longer exported "
            f"from any package __all__. Remove the record or re-export it. "
            f"Reason was: {reason}"
        )
        assert not discovered[qualified_name], (
            f"Recorded non-mesh resolver {qualified_name} now satisfies the "
            f"source-mesh protocol. Enroll it in the live mesh and move it to "
            f"_ENROLLED_SOURCE_MESH_RESOLVERS instead of leaving it recorded as "
            f"non-mesh. Reason was: {reason}"
        )


def test_discovery_count_is_pinned() -> None:
    """The exported resolver surface is pinned so a new resolver fails loudly.

    Eleven concrete source-mesh resolvers (all enrolled) plus the protocol
    contract plus one known non-mesh resolver. A new resolver added without
    updating the enrolled or non-mesh set changes this count and fails here.
    """
    discovered = _discover_resolve_bearing_classes()
    source_mesh = [name for name, is_mesh in discovered.items() if is_mesh and name != _PROTOCOL_QUALNAME]
    non_mesh = [name for name, is_mesh in discovered.items() if not is_mesh]

    assert len(source_mesh) == len(_ENROLLED_SOURCE_MESH_RESOLVERS), (
        f"Expected {len(_ENROLLED_SOURCE_MESH_RESOLVERS)} concrete source-mesh "
        f"resolvers, discovered {len(source_mesh)}:\n" + "\n".join(f"  {name}" for name in sorted(source_mesh))
    )
    assert len(non_mesh) == len(_KNOWN_NON_MESH_RESOLVERS), (
        f"Expected {len(_KNOWN_NON_MESH_RESOLVERS)} known non-mesh resolver(s), "
        f"discovered {len(non_mesh)}:\n" + "\n".join(f"  {name}" for name in sorted(non_mesh))
    )
    assert discovered.get(_PROTOCOL_QUALNAME), (
        f"The {_PROTOCOL_QUALNAME} protocol contract is no longer discovered as a "
        f"source-mesh-shaped export; the discovery surface has drifted."
    )
