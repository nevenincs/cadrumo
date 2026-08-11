"""Data-inventory checklist composer for one modelo / filing-year / period.

Composes the registry-authoritative facts an operator needs before they can
calculate a modelo: which manual casillas are required, which are optional,
which are populated automatically from the bucket ledger, and which are
populated from the active taxpayer profile (with a per-binding readiness flag
so an unset profile fact — e.g. the home-office usage ratio — surfaces as an
actionable gap rather than a silent blank downstream).

This module owns the read-only composition over
:func:`~application.modelo._registry_resources.authority_via_resources`
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

from ...core import CasillaId, Period
from ...core.aggregation import LEDGER_BINDING_SOURCE_KINDS, BindingSourceKind
from ...core.i18n import output_language
from ...core.logging import get_logger
from ...domain.calculations.registry import (
    BindingId,
    InputKind,
    LegalRefId,
    RevisionId,
    SourceRefId,
    binding_profile_keys,
    build_profile_grounding_index,
)
from ._binding_readiness import profile_resolvable_binding_ids
from ._registry_resources import authority_via_resources

_log = get_logger(__name__)

if TYPE_CHECKING:
    from ...domain.calculations.registry import ModeloRevision


@dataclass(frozen=True, slots=True)
class DataInventoryCasilla:
    """One casilla entry on a data-inventory checklist."""

    casilla_id: CasillaId
    number: str
    label: str
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()
    binding_id: BindingId | None = None
    binding_source: str | None = None


@dataclass(frozen=True, slots=True)
class DataInventoryChecklist:
    """Composed "what data do I need" checklist for one modelo/year/period.

    ``required_manual`` and ``optional_manual`` are the casillas an operator
    must (or may) hand-enter. ``ledger_derivable`` are casillas the ledger
    aggregation mesh populates automatically once the relevant transactions
    are imported and classified — the operator imports these rather than
    typing them. ``profile_derivable`` are casillas populated from the active
    taxpayer profile (coefficients such as the home-office usage ratio);
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
    unresolved_profile_bindings: tuple[BindingId, ...]
    #: The profile keys those unresolved bindings consume, in binding order and
    #: de-duplicated. Carried alongside the binding ids because the operator
    #: needs to know WHICH PROFILE FACT to supply, and a binding id names the
    #: registry's internal consumer of that fact rather than the fact itself.
    unresolved_profile_keys: tuple[str, ...]
    profile_checked: bool


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
      ``profile_derivable``. Every other bound source (previous-filing carry,
      relation prefill, live observation, constant value, ...) requires no
      operator data-gathering action and is intentionally omitted from the
      checklist.
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
    authority = authority_via_resources()
    snapshot = authority.snapshot(modelo, filing_year=filing_year, period=period.registry_token)
    revision = snapshot.revision
    binding_sources = {binding.id: binding.source for binding in revision.bindings}

    required_manual: list[DataInventoryCasilla] = []
    optional_manual: list[DataInventoryCasilla] = []
    ledger_derivable: list[DataInventoryCasilla] = []
    profile_derivable: list[DataInventoryCasilla] = []
    profile_binding_ids: list[BindingId] = []

    for casilla in revision.casillas:
        binding_source = binding_sources.get(casilla.binding) if casilla.binding is not None else None
        entry = DataInventoryCasilla(
            casilla_id=casilla.id,
            number=casilla.number,
            label=casilla.get_label(output_language()),
            legal_refs=tuple(casilla.legal_refs),
            source_refs=tuple(casilla.source_refs),
            binding_id=casilla.binding,
            binding_source=str(binding_source) if binding_source is not None else None,
        )
        if casilla.input_kind == InputKind.MANUAL:
            if casilla.required:
                required_manual.append(entry)
            else:
                optional_manual.append(entry)
        elif casilla.input_kind == InputKind.BOUND and casilla.binding is not None:
            if binding_source in LEDGER_BINDING_SOURCE_KINDS:
                ledger_derivable.append(entry)
            elif binding_source == BindingSourceKind.PROFILE:
                profile_derivable.append(entry)
                profile_binding_ids.append(casilla.binding)
        # COMPUTED, INFORMATIONAL, and non-ledger/non-profile BOUND casillas
        # (previous_filing, relation_prefill, live_observation,
        # constant_value, ...) need no operator data-gathering action.

    unresolved_profile_bindings: tuple[BindingId, ...] = ()
    unresolved_profile_keys: tuple[str, ...] = ()
    profile_checked = False
    if bucket_id is not None and profile_binding_ids:
        resolved = profile_resolvable_binding_ids(
            modelo=modelo,
            bucket_id=bucket_id,
            filing_year=filing_year,
            period=period,
        )
        profile_checked = True
        unresolved_profile_bindings = tuple(
            binding_id for binding_id in profile_binding_ids if str(binding_id) not in resolved
        )
        unresolved_profile_keys = _profile_keys_for_bindings(revision, unresolved_profile_bindings)
    elif bucket_id is not None:
        profile_checked = True

    return DataInventoryChecklist(
        modelo=str(snapshot.modelo.id),
        revision_id=str(revision.id),
        filing_year=filing_year,
        period=period.registry_token,
        required_manual=tuple(required_manual),
        optional_manual=tuple(optional_manual),
        ledger_derivable=tuple(ledger_derivable),
        profile_derivable=tuple(profile_derivable),
        unresolved_profile_bindings=unresolved_profile_bindings,
        unresolved_profile_keys=unresolved_profile_keys,
        profile_checked=profile_checked,
    )


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
    from ...core.resources import resources
    from ..user_profile import format_profile_path_requirements

    try:
        authority = authority_via_resources()
        snapshot = authority.snapshot(modelo, filing_year=filing_year, period=period.registry_token)
        keys = next(
            (binding_profile_keys(b) for b in snapshot.revision.bindings if str(b.id) == binding_id),
            (),
        )
        if not keys:
            return ""
        rendered = format_profile_path_requirements(
            keys,
            schema=resources().user_profile_schema.singleton,
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
