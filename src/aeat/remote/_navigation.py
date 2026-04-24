"""Typed post-auth navigation catalogue for the AEAT read surface.

This module promotes the provisional URL constants inlined in
:mod:`aeat.status._reader` into strict-frozen pydantic records so the
Phase 2 read-only fetchers can reason about post-auth navigation as
data rather than as magic strings. Every record carries the Layer 1
write-guard literal ``mode: Literal["read"] = "read"``; any future
contributor who adds a node MUST inherit that invariant, which surfaces
both as a pydantic validation error and as a review-level signal.

Navigation primitive discipline:

- Every :class:`NavigationNode` describes a target reachable by a
  single ``page.goto(url, wait_until="domcontentloaded")`` followed by
  ``page.content()`` — the exact same pattern
  :class:`aeat.status.StatusReader.fetch_detail_html` already uses on
  main. No state-mutating Playwright primitive appears in this module
  or in the per-modelo fetchers consuming it; the write-guard grep
  test in :mod:`aeat.remote.test_no_write_surface` enforces the ban
  structurally and rejects the forbidden method-call fragments under
  a case-insensitive prefix match.

- Link-navigation is expressed exclusively as a fresh ``page.goto``
  against the anchor's resolved ``href``; no mutating invocation on a
  locator handle is permitted, which the grep guard rejects under the
  ``.cl`` / ``.pr`` / ``.fi`` fragment set.

Consumers MUST import from :mod:`aeat.remote`, not from this module
directly.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class NavigationNode(BaseModel):
    """One entry in the post-auth navigation catalogue.

    Each node names a stable AEAT surface the read path reaches via
    plain ``page.goto(...)`` navigation. ``path_template`` is the
    relative path the caller joins against
    :attr:`aeat.config.Settings.aeat_base_url`; ``{placeholder}``
    segments are substituted with URL-quoted values at call time.

    Attributes:
        node_id: Short stable identifier used by the fetchers to look
            the node up in :data:`NAVIGATION_CATALOGUE`.
        description: One-line human-readable description of what AEAT
            serves at this URL.
        path_template: URL path relative to ``aeat_base_url``. When
            the template carries ``{...}`` placeholders, callers
            substitute them via ``path_template.format(...)`` after
            URL-quoting the substitution values.
        mode: Structural write-guard literal; always ``"read"``. Any
            attempt to widen this field fails pydantic validation.
    """

    model_config = _STRICT_FROZEN

    node_id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=256)
    path_template: str = Field(min_length=1, max_length=512)
    mode: Literal["read"] = "read"


MIS_EXPEDIENTES: NavigationNode = NavigationNode(
    node_id="mis_expedientes",
    description="Listing of the authenticated taxpayer's filed expedientes.",
    path_template="/wlpl/TC-UTIL/Expediente?COPT=Y",
)
"""Stable entry point for the `Mis expedientes` listing.

Identical to the provisional ``_EXPEDIENTES_PATH`` constant inlined in
:mod:`aeat.status._reader`. Promoted here so the Phase 2 fetchers and
any Phase 5 sync-run stage can reference the path as a typed record
rather than as a private string literal.
"""


EXPEDIENTE_DETAIL: NavigationNode = NavigationNode(
    node_id="expediente_detail",
    description="Detail page for one expediente (casillas, receipts, status).",
    path_template="/wlpl/TC-UTIL/Expediente/Detalle?EXP={expediente_id}",
)
"""Per-expediente detail-page template.

Callers substitute ``{expediente_id}`` with the URL-quoted expediente
identifier before resolving against ``aeat_base_url``. Mirrors the
provisional ``_EXPEDIENTE_DETAIL_PATH_TEMPLATE_DEFAULT`` constant and
the :attr:`aeat.config.Settings.aeat_status_detail_url_template`
override.
"""


MIS_NOTIFICACIONES: NavigationNode = NavigationNode(
    node_id="mis_notificaciones",
    description="Listing of pending and acknowledged AEAT notifications.",
    path_template="/wlpl/DTNE-PRUE/Notificaciones",
)
"""Entry point for the notification centre.

Phase 2 does not exercise this node — the per-modelo fetchers only
reach for filing detail pages — but the catalogue records it so
downstream code (:mod:`aeat.filing.reconciliation` in Phase 3, the
Phase 5 sync-run stage) can wire it in without re-hardcoding the path.
"""


NAVIGATION_CATALOGUE: tuple[NavigationNode, ...] = (
    MIS_EXPEDIENTES,
    EXPEDIENTE_DETAIL,
    MIS_NOTIFICACIONES,
)
"""Immutable tuple exposing every declared :class:`NavigationNode`.

The tuple is ordered by traversal frequency in a typical
reconciliation pass: the expediente listing is fetched first, each
resolved expediente is expanded against the detail-page template, and
the notification surface is reached only when a higher-tier consumer
explicitly asks for it.
"""


def find_node(node_id: str) -> NavigationNode:
    """Return the :class:`NavigationNode` whose ``node_id`` matches ``node_id``.

    The lookup is a linear scan of :data:`NAVIGATION_CATALOGUE` — the
    catalogue is small (three entries today, a handful at most even
    after Tier-2 / Tier-3 expansion) and the explicit scan keeps the
    module dependency footprint trivial.

    Args:
        node_id: Stable identifier of the node to resolve.

    Returns:
        The matching :class:`NavigationNode`.

    Raises:
        KeyError: If no node with that ``node_id`` exists in the
            catalogue. The error carries the requested identifier and
            the list of available ones so the misspelling is obvious
            at the call site.
    """
    for node in NAVIGATION_CATALOGUE:
        if node.node_id == node_id:
            return node
    available = ", ".join(n.node_id for n in NAVIGATION_CATALOGUE)
    raise KeyError(f"unknown navigation node {node_id!r}; available: {available}")


__all__ = [
    "EXPEDIENTE_DETAIL",
    "MIS_EXPEDIENTES",
    "MIS_NOTIFICACIONES",
    "NAVIGATION_CATALOGUE",
    "NavigationNode",
    "find_node",
]
