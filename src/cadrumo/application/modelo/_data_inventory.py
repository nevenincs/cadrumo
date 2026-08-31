"""Data-inventory checklist composer for one modelo / filing-year / period.

Composes the registry-authoritative facts an operator needs before they can
calculate a modelo: which manual casillas are required, which are optional,
which are populated automatically from the bucket ledger, and which are
populated from the active taxpayer profile (with a per-binding readiness flag
so an unset profile fact — e.g. the home-office usage ratio — surfaces as an
actionable gap rather than a silent blank downstream).

This module owns the read-only composition over
:func:`~domain.calculations.registry.authority.bundled_authority`
(the registry snapshot for the casilla/binding declarations) and
:func:`~application.modelo.profile_resolvable_binding_ids`
(the profile-fact resolution already used by the ``bindings list --missing``
surface), so the CLI ``requires`` command stays a thin projection layer. No new
aggregation path is introduced: the same registry snapshot and profile-binding
resolver the calculate path uses are read, not re-derived.

See Also:
    :func:`~application.modelo._registry_helpers.required_input_casilla_ids_for_revision`
        Sibling helper returning only the bare required/optional id tuples
        (used by amendment completeness checks); this module composes the
        richer operator-facing checklist over the same snapshot.
    :func:`~application.modelo.profile_resolvable_binding_ids`
        Profile-fact binding resolver reused here to flag missing coefficients.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...core.aggregation import LEDGER_BINDING_SOURCE_KINDS, BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.i18n import output_language
from ...core.logging import get_logger
from ...core.period import Period
from ...core.resources._boundary import bundled_path
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.bindings import bound_casilla_binding_ids
from ...domain.calculations.registry.ids import (
    BindingId,
    LegalRefId,
    RevisionId,
    SourceRefId,
)
from ...domain.calculations.registry.loader import load_registry_tree
from ...domain.calculations.registry.profile_grounding import (
    binding_profile_keys,
    build_profile_grounding_index,
)
from ...domain.calculations.registry.schema import DataBindingDefinition
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.calculations.registry.temporal import select_revision
from ._binding_readiness import profile_resolvable_binding_ids

_log = get_logger(__name__)

# Sources whose calculate resolvers read bucket-local observation, register, or
# invoice evidence rather than the general ledger, taxpayer profile, or a
# prior-filing/relation carry.  ``live`` here means live application state: it
# does not claim that ``modelo requires`` contacts an AEAT remote service.
_LIVE_OBSERVATION_SOURCE_KINDS: frozenset[BindingSourceKind] = frozenset(
    {
        BindingSourceKind.BIENES_INVERSION_REGULARIZACION,
        BindingSourceKind.COLLECTIBLE_INVOICE,
        BindingSourceKind.FOREIGN_ASSET,
        BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION,
        BindingSourceKind.M347_THIRD_PARTY_OPERATION,
        BindingSourceKind.PAYABLE_INVOICE,
        BindingSourceKind.PRORRATA_REGULARIZACION,
        BindingSourceKind.RETENCIONES_AGGREGATION,
        BindingSourceKind.WITHHOLDING,
    },
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.schema import ModeloRevision


@dataclass(frozen=True, slots=True)
class DataInventoryCasilla:
    """One casilla entry on a data-inventory checklist.

    ``legal_refs`` and ``source_refs`` are mandatory and non-empty: regulatory
    grounding travels with a casilla all the way to the operator, so an entry
    that cannot say which provision establishes it has nothing to show and must
    not be built. The refs are copied from the registry
    :class:`~domain.calculations.registry.schema_surfaces.CasillaDefinition`,
    which already refuses an ungrounded casilla at registry build; enforcing it
    here too means the checklist type states the guarantee itself rather than
    inheriting it from wherever its fields happened to come from.
    """

    casilla_id: CasillaId
    number: str
    label: str
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]
    binding_id: BindingId | None = None
    binding_source: str | None = None

    def __post_init__(self) -> None:
        """Refuse an entry whose regulatory grounding is missing."""
        missing = [
            name for name, refs in (("legal_refs", self.legal_refs), ("source_refs", self.source_refs)) if not refs
        ]
        if missing:
            raise ValueError(
                f"data-inventory casilla {self.casilla_id} must carry non-empty {' and '.join(missing)}",
            )


@dataclass(frozen=True, slots=True)
class DataInventoryChecklist:
    """Composed "what data do I need" checklist for one modelo/year/period.

    ``required_manual`` and ``optional_manual`` are the casillas an operator
    must (or may) hand-enter. ``ledger_derivable`` are casillas the ledger
    aggregation mesh populates automatically once the relevant transactions
    are imported and classified — the operator imports these rather than
    typing them. ``profile_derivable`` are casillas populated from the active
    taxpayer profile (coefficients such as the home-office usage ratio).
    ``previous_filing`` and ``relation_prefill`` expose the two distinct
    cross-filing channels. ``live_observation`` contains bucket-local
    observation, register, and invoice-backed sources; it does not imply a
    remote AEAT query. ``unbucketed_sources`` preserves any remaining declared
    binding pair for an advisory instead of silently dropping it.

    ``unresolved_profile_bindings`` names the subset of those bindings the
    active profile has not yet supplied a fact for, so the checklist can warn
    the operator before they calculate and hit a missing-binding refusal.
    """

    modelo: str
    revision_id: RevisionId
    filing_year: int
    period: str
    required_manual: tuple[DataInventoryCasilla, ...]
    optional_manual: tuple[DataInventoryCasilla, ...]
    ledger_derivable: tuple[DataInventoryCasilla, ...]
    profile_derivable: tuple[DataInventoryCasilla, ...]
    previous_filing: tuple[DataInventoryCasilla, ...]
    relation_prefill: tuple[DataInventoryCasilla, ...]
    live_observation: tuple[DataInventoryCasilla, ...]
    unbucketed_sources: tuple[DataInventoryCasilla, ...]
    unresolved_profile_bindings: tuple[BindingId, ...]
    #: The profile keys those unresolved bindings consume, in binding order and
    #: de-duplicated. Carried alongside the binding ids because the operator
    #: needs to know WHICH PROFILE FACT to supply, and a binding id names the
    #: registry's internal consumer of that fact rather than the fact itself.
    unresolved_profile_keys: tuple[str, ...]
    profile_checked: bool


@dataclass(slots=True)
class _DataInventoryBuckets:
    required_manual: list[DataInventoryCasilla]
    optional_manual: list[DataInventoryCasilla]
    ledger_derivable: list[DataInventoryCasilla]
    profile_derivable: list[DataInventoryCasilla]
    previous_filing: list[DataInventoryCasilla]
    relation_prefill: list[DataInventoryCasilla]
    live_observation: list[DataInventoryCasilla]
    unbucketed_sources: list[DataInventoryCasilla]
    profile_binding_ids: list[BindingId]


def _profile_keys_for_bindings(
    revision: ModeloRevision,
    binding_ids: tuple[BindingId, ...],
) -> tuple[str, ...]:
    """Return the profile keys the given bindings consume, in order, de-duplicated.

    A binding may consume several profile keys, and several bindings may
    consume the same one, so the operator-facing list is de-duplicated while
    preserving the binding order the checklist already presents.

    A binding contributing no key is simply absent: nothing is invented for
    it, and its binding id remains available on the checklist.
    """
    wanted = set(binding_ids)
    keys: list[str] = []
    seen: set[str] = set()
    for binding in revision.bindings:
        if binding.id not in wanted:
            continue
        for key in binding_profile_keys(binding):
            if key in seen:
                continue
            seen.add(key)
            keys.append(key)
    return tuple(keys)


def data_inventory_checklist(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    bucket_id: str | None,
) -> DataInventoryChecklist:
    """Compose the data-inventory checklist for one modelo / year / period.

    Reads the resolved :class:`~domain.calculations.registry.RegistrySnapshot`
    for ``(modelo, filing_year, period)`` and classifies every casilla:

    * ``input_kind == MANUAL`` casillas split into ``required_manual`` /
      ``optional_manual`` by their ``required`` flag.
    * ``input_kind == BOUND`` casillas are classified by their binding's
      :class:`~core.aggregation.BindingSourceKind`: ledger-aggregation
      sources become ``ledger_derivable``; ``profile`` sources become
      ``profile_derivable``; prior-filing carries, relation prefills, and
      bucket-local observation/register/invoice sources have their own
      buckets. Source kinds outside those explicit buckets remain visible in
      ``unbucketed_sources`` so taxonomy growth cannot silently disappear.
    * ``COMPUTED`` and ``INFORMATIONAL`` casillas need no source data and are
      omitted.

    When ``bucket_id`` names an active profile, ``profile_derivable`` bindings
    are cross-checked against
    :func:`~application.modelo.profile_resolvable_binding_ids`
    and any binding the profile has not yet resolved is surfaced in
    ``unresolved_profile_bindings`` — the coefficient-missing warning the issue
    calls for (e.g. an unset home-office ratio). ``profile_checked`` is
    ``False`` when no ``bucket_id`` was supplied or the check could not run;
    callers should not read an empty ``unresolved_profile_bindings`` as "all
    clear" in that case.

    Raises:
        RegistrySnapshotError: When the registry has no revision covering
            ``(modelo, filing_year, period)``.

    Returns:
        A :class:`DataInventoryChecklist`.
    """
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo_definition = next(candidate for candidate in modelos if candidate.id == modelo)
    revision = select_revision(modelo_definition, filing_year=filing_year, period=period.registry_token)
    bindings_by_id = {binding.id: binding for binding in revision.bindings}
    buckets = _collect_inventory_buckets(revision, bindings_by_id)

    unresolved_profile_bindings: tuple[BindingId, ...] = ()
    unresolved_profile_keys: tuple[str, ...] = ()
    if bucket_id is not None and buckets.profile_binding_ids:
        resolved = profile_resolvable_binding_ids(
            modelo=modelo,
            bucket_id=bucket_id,
            filing_year=filing_year,
            period=period,
        )
        profile_checked = True
        unresolved_profile_bindings = tuple(
            binding_id for binding_id in buckets.profile_binding_ids if str(binding_id) not in resolved
        )
        unresolved_profile_keys = _profile_keys_for_bindings(revision, unresolved_profile_bindings)
    elif bucket_id is not None:
        profile_checked = True
    else:
        profile_checked = False

    return DataInventoryChecklist(
        modelo=str(modelo),
        revision_id=str(revision.id),
        filing_year=filing_year,
        period=period.registry_token,
        required_manual=tuple(buckets.required_manual),
        optional_manual=tuple(buckets.optional_manual),
        ledger_derivable=tuple(buckets.ledger_derivable),
        profile_derivable=tuple(buckets.profile_derivable),
        previous_filing=tuple(buckets.previous_filing),
        relation_prefill=tuple(buckets.relation_prefill),
        live_observation=tuple(buckets.live_observation),
        unbucketed_sources=tuple(buckets.unbucketed_sources),
        unresolved_profile_bindings=unresolved_profile_bindings,
        unresolved_profile_keys=unresolved_profile_keys,
        profile_checked=profile_checked,
    )


def _inventory_entry(
    casilla: CasillaDefinition,
    *,
    binding_id: BindingId | None = None,
    binding_source: BindingSourceKind | None = None,
) -> DataInventoryCasilla:
    return DataInventoryCasilla(
        casilla_id=casilla.id,
        number=casilla.number,
        label=casilla.get_label(output_language()),
        legal_refs=tuple(casilla.legal_refs),
        source_refs=tuple(casilla.source_refs),
        binding_id=binding_id,
        binding_source=binding_source.value if binding_source is not None else None,
    )


def _collect_inventory_buckets(
    revision: ModeloRevision,
    bindings_by_id: dict[BindingId, DataBindingDefinition],
) -> _DataInventoryBuckets:
    buckets = _DataInventoryBuckets(
        required_manual=[],
        optional_manual=[],
        ledger_derivable=[],
        profile_derivable=[],
        previous_filing=[],
        relation_prefill=[],
        live_observation=[],
        unbucketed_sources=[],
        profile_binding_ids=[],
    )
    for casilla in revision.casillas:
        if casilla.input_kind == InputKind.MANUAL:
            target = buckets.required_manual if casilla.required else buckets.optional_manual
            target.append(_inventory_entry(casilla))
            continue
        if casilla.input_kind != InputKind.BOUND:
            continue
        for binding_id in bound_casilla_binding_ids(casilla):
            binding_source = bindings_by_id[binding_id].source
            entry = _inventory_entry(casilla, binding_id=binding_id, binding_source=binding_source)
            _append_binding_inventory_entry(buckets, binding_id, binding_source, entry)
    return buckets


def _append_binding_inventory_entry(
    buckets: _DataInventoryBuckets,
    binding_id: BindingId,
    binding_source: BindingSourceKind,
    entry: DataInventoryCasilla,
) -> None:
    if binding_source in LEDGER_BINDING_SOURCE_KINDS:
        buckets.ledger_derivable.append(entry)
    elif binding_source is BindingSourceKind.PROFILE:
        buckets.profile_derivable.append(entry)
        if binding_id not in buckets.profile_binding_ids:
            buckets.profile_binding_ids.append(binding_id)
    elif binding_source is BindingSourceKind.PREVIOUS_FILING:
        buckets.previous_filing.append(entry)
    elif binding_source is BindingSourceKind.RELATION_PREFILL:
        buckets.relation_prefill.append(entry)
    elif binding_source in _LIVE_OBSERVATION_SOURCE_KINDS:
        buckets.live_observation.append(entry)
    else:
        buckets.unbucketed_sources.append(entry)


def profile_requirements_for_binding(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    binding_id: str,
) -> str:
    """Name the profile facts one binding consumes, as grounded requirement text.

    A binding id names the registry's internal consumer of a profile fact and
    appears nowhere in the profile editor, so an operator told to set one has
    nothing to act on. This resolves the binding to the facts behind it.

    Lives here rather than at the CLI boundary because the binding definitions
    it reads are registry state: resolving them at the entrypoint would put a
    registry-authority read in a transport layer that is budgeted to hold none.

    Best-effort by contract. An unresolvable snapshot, a binding id matching no
    row, or a binding naming no profile key all return the empty string, and
    the caller keeps whatever guidance it already had. A degraded message is
    worse than a resolved one and better than none.
    """
    from ...domain.user_profile.loader import load_user_profile_schema
    from ..user_profile.preflight import format_profile_path_requirements

    try:
        authority = bundled_authority()
        revision = select_revision(authority.modelo(modelo), filing_year=filing_year, period=period.registry_token)
        keys = next(
            (binding_profile_keys(b) for b in revision.bindings if str(b.id) == binding_id),
            (),
        )
        if not keys:
            return ""
        rendered = format_profile_path_requirements(
            keys,
            schema=load_user_profile_schema(),
            grounding_index=build_profile_grounding_index(authority),
        )
    except Exception:
        _log.debug("profile-fact lookup for binding failed", exc_info=True)
        return ""
    return ", ".join(rendered)


__all__ = [
    "DataInventoryCasilla",
    "DataInventoryChecklist",
    "data_inventory_checklist",
    "profile_requirements_for_binding",
]
