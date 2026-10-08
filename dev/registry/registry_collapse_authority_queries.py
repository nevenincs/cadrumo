"""Fact, snapshot, and indexed-authority projections for collapse verification."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import date

from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    ValidatedRegistryAuthority,
)
from cadrumo.domain.calculations.registry.facts.resolution import (
    GovernedFactQuery,
)
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact
from cadrumo.domain.calculations.registry.facts.variants import GovernedFactVariant
from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
    ModeloRevision,
    RegistrySnapshot,
)
from cadrumo.domain.calculations.registry.schema_form_layouts import FormLayoutDefinition
from cadrumo.domain.calculations.registry.schema_references import DateSupportEnvelope, RegistryValidityWindow
from cadrumo.domain.calculations.registry.temporal import (
    revision_temporal_resolution,
)

from .registry_collapse_comparison import _typed_projection
from .registry_collapse_models import _FACT_QUERY_TYPES, RequestCoordinate


def _fact_projection(value: object) -> object:
    """Compare fact meaning while checking each generation digest separately."""
    projected = _typed_projection(value)
    if isinstance(projected, Mapping):
        return {key: child for key, child in projected.items() if key != "authority_digest"}
    return projected


def _fact_queries(authority: ValidatedRegistryAuthority) -> tuple[GovernedFactQuery, ...]:
    catalogue = authority.catalogues.facts
    envelope = authority.catalogues.require_supported_filing_years().date_envelope()
    queries: dict[str, GovernedFactQuery] = {}
    for fact in catalogue.facts.values():
        windows = fact.materialized_windows(envelope)
        query_type = _FACT_QUERY_TYPES[fact.family]
        for variant in fact.variants:
            query = _fact_query_for_variant(fact, variant, windows[variant.variant_id], envelope, query_type)
            if query is None:
                continue
            key = json.dumps(query.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
            queries[key] = query
    return tuple(queries[key] for key in sorted(queries))


def _fact_query_for_variant(
    fact: GovernedFact,
    variant: GovernedFactVariant,
    window: RegistryValidityWindow,
    envelope: DateSupportEnvelope,
    query_type: Callable[..., GovernedFactQuery],
) -> GovernedFactQuery | None:
    effective_date = max(window.valid_from, envelope.floor)
    if (window.valid_to is not None and window.valid_to < effective_date) or not envelope.admits_coordinate(
        effective_date
    ):
        return None
    filing_year = period = None
    selector = variant.period_selector
    if selector is not None:
        filing_year = selector.years[0] if selector.years else selector.year_from
        if filing_year is None:
            return None
        period = str(selector.periods_for_year(filing_year)[0])
    return query_type(
        fact_id=fact.fact_id,
        date_axis=variant.date_axis,
        effective_date=effective_date,
        selectors=variant.selectors,
        filing_year=filing_year,
        period=period,
    )


def _fact_result(resolve: Callable[[GovernedFactQuery], object], query: GovernedFactQuery) -> Mapping[str, object]:
    try:
        value = resolve(query)
        digest = getattr(value, "authority_digest", None)
        return {
            "outcome": "resolved",
            "authority_digest_valid": isinstance(digest, str) and len(digest) == 64,
            "value": _fact_projection(value),
        }
    except Exception as exc:
        return {"outcome": "refused", "error_type": type(exc).__name__, "detail": str(exc)}


def _snapshot_result(
    snapshot: Callable[..., object],
    modelo_id: str,
    coordinate: RequestCoordinate,
    *,
    indexed_form_layout: Callable[[str, str], FormLayoutDefinition | None] | None = None,
) -> Mapping[str, object]:
    try:
        value = snapshot(
            modelo_id,
            filing_year=coordinate.filing_year,
            period=coordinate.period,
            on=None if coordinate.on is None else date.fromisoformat(coordinate.on),
            revision_id=coordinate.revision_id,
        )
        if indexed_form_layout is not None and isinstance(value, RegistrySnapshot):
            value = _snapshot_with_form_layout(
                value,
                indexed_form_layout(modelo_id, str(value.revision.id)),
            )
        return {"outcome": "admitted", "value": _typed_projection(_scoped_to_selected_edition(value))}
    except Exception as exc:
        return {"outcome": "refused", "error_type": type(exc).__name__, "detail": str(exc)}


def _scoped_to_selected_edition(snapshot: object) -> object:
    """Keep only the selected edition in the snapshot's modelo.

    The indexed runtime composes a snapshot's modelo from the one revision it
    selected, while an in-memory authority keeps every edition there; the
    editions the snapshot did not select are not part of its meaning.
    """
    if not isinstance(snapshot, RegistrySnapshot):
        return snapshot
    selected = snapshot.revision.id
    revisions = {
        revision_id: revision for revision_id, revision in snapshot.modelo.revisions.items() if revision_id == selected
    }
    return snapshot.model_copy(update={"modelo": snapshot.modelo.model_copy(update={"revisions": revisions})})


def _snapshot_with_form_layout(
    snapshot: RegistrySnapshot,
    form_layout: FormLayoutDefinition | None,
) -> RegistrySnapshot:
    """Restore the separately addressed form layout without replacing export projections.

    A snapshot's effective ``revision`` may derive export fields from bindings,
    while ``modelo.revisions[selected]`` retains the raw declared export layout.
    The form sidecar belongs on both views independently, preserving each one's
    existing export layouts.
    """
    form_layouts = () if form_layout is None else (form_layout,)
    selected = snapshot.revision.model_copy(update={"form_layouts": form_layouts})
    model_revision = snapshot.modelo.revisions[selected.id].model_copy(update={"form_layouts": form_layouts})
    revisions = {**snapshot.modelo.revisions, selected.id: model_revision}
    return snapshot.model_copy(
        update={
            "revision": selected,
            "modelo": snapshot.modelo.model_copy(update={"revisions": revisions}),
        }
    )


def _indexed_complete_revision(
    operation: PinnedAuthorityOperation,
    modelo_id: str,
    revision_id: str,
) -> ModeloRevision:
    """Compose all separately addressed layout components into their typed revision."""
    revision = operation.revision_with_export_layouts(modelo_id, revision_id)
    form_layout = operation.form_layout(modelo_id, revision_id)
    return revision.model_copy(update={"form_layouts": () if form_layout is None else (form_layout,)})


def _indexed_selection_result(
    operation: PinnedAuthorityOperation,
    modelo_id: str,
    coordinate: RequestCoordinate,
) -> Mapping[str, object]:
    try:
        directory = operation.modelo_directory(modelo_id)
        selected = operation.revision_for_context(
            modelo_id,
            filing_year=coordinate.filing_year,
            period=coordinate.period,
            on=None if coordinate.on is None else date.fromisoformat(coordinate.on),
            revision_id=coordinate.revision_id,
        )
        resolution = revision_temporal_resolution(
            selected,
            filing_year=coordinate.filing_year,
            period=coordinate.period,
            support=directory.supported_filing_years,
        )
        return {
            "outcome": "selected",
            "revision": str(selected.id),
            "requested_filing_year": resolution.requested_filing_year,
            "authored_filing_year": resolution.authored_filing_year,
            "projection_direction": str(resolution.projection_direction),
            # The runtime addresses export and form layouts separately from the base revision.
            "value": _typed_projection(_indexed_complete_revision(operation, modelo_id, str(selected.id))),
        }
    except Exception as exc:
        return {"outcome": "refused", "error_type": type(exc).__name__, "detail": str(exc)}


def _revision_inventory(modelo: ModeloDefinition) -> tuple[Mapping[str, object], ...]:
    return tuple(
        {
            "revision": str(revision.id),
            "valid_from": revision.valid_from.isoformat(),
            "valid_to": None if revision.valid_to is None else revision.valid_to.isoformat(),
            "years": list(revision.period_selector.years),
            "year_from": revision.period_selector.year_from,
            "year_to": revision.period_selector.year_to,
            "periods": [str(period) for period in revision.period_selector.declared_periods],
        }
        for revision in sorted(modelo.revisions.values(), key=lambda item: (item.valid_from, str(item.id)))
    )
