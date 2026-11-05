"""Which casillas each grade-capped binding of one revision reaches.

A cap is declared on a binding, but a filer reads boxes. The calculation names
the box a capped value lands in, the calculation gate decides whether the
revision it reads was screened against the current caps, and registry build
refuses a cap that reaches no box. All three read the map this module derives,
so none of them re-derives the edges.

A binding reaches a casilla through either of two declared edges: a ``BOUND``
casilla naming it as primary or reviewed alternate, or an output redirect a peer
domain declares through a governed fact. Modelo 130 casilla 06 is the redirect
case: its binding is matched on the income rows and the governed routing fact
writes the value to casilla 06, so no casilla names the binding at all.

The registry must not import those peer domains. A domain declares its redirect
by registering a reader here, and the module that registers it is installed by
import before the first redirect query, the same arrangement the cross-domain
snapshot checks use;
:class:`ModeloRevision`, the registry revision a modelo is calculated against;
:class:`RegistrySnapshot`, the pinned registry snapshot.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from ....core.casilla_id import CasillaId
from ....core.hashing import content_hash_hex
from .binding_targets import casillas_by_binding

if TYPE_CHECKING:
    from .binding_grade_cap import BindingGradeCap
    from .governed_fact_scope import GovernedFactSource
    from .ids import BindingId
    from .schema import ModeloRevision, RegistrySnapshot

type BindingOutputRedirect = Callable[
    [ModeloRevision, GovernedFactSource | None, date], Mapping[BindingId, tuple[CasillaId, ...]]
]
"""Read one domain's declared redirects: each redirected binding of the revision and the casillas it writes,
as the governed facts in force on the given filing-period date declare them."""

# Each entry names the public defining module whose import registers a redirect.
_BINDING_OUTPUT_REDIRECT_MODULES: Final[tuple[str, ...]] = ("...renta.retenciones_routing_integrity",)
_redirects: list[BindingOutputRedirect] = []
_redirect_modules_installed = False


@dataclass(frozen=True, slots=True)
class CappedBindingReach:
    """One capped binding, its declared cap, and the casillas its value reaches, in declaration order."""

    binding_id: BindingId
    cap: BindingGradeCap
    casilla_ids: tuple[CasillaId, ...]


def register_binding_output_redirect(redirect: BindingOutputRedirect) -> None:
    """Enrol one domain's redirect reader; registering the same reader twice is a no-op."""
    if redirect not in _redirects:
        _redirects.append(redirect)


def _install_redirect_modules() -> None:
    global _redirect_modules_installed
    if _redirect_modules_installed:
        return
    for module_name in _BINDING_OUTPUT_REDIRECT_MODULES:
        # Module names are controlled by the hard-coded tuple above.
        importlib.import_module(module_name, package=__package__)  # nosemgrep
    _redirect_modules_installed = True


def snapshot_reach_date(snapshot: RegistrySnapshot) -> date:
    """The filing-period date a snapshot's redirects are read at: the close of its period, else of its ejercicio.

    A snapshot without a filing period, such as a communication with no
    period, or with one that spans no calendar dates, such as an instalment
    clave, is read at the close of its filing year.

    ``snapshot`` is the :class:`RegistrySnapshot`, the pinned registry snapshot.
    """
    period = snapshot.filing_period
    if period is None or not period.has_date_span():
        return date(snapshot.filing_year, 12, 31)
    return period.end_date


def binding_output_redirects(
    revision: ModeloRevision, *, authority: GovernedFactSource | None, effective_date: date
) -> dict[BindingId, tuple[CasillaId, ...]]:
    """Return every declared output redirect of ``revision``, read through ``authority`` at ``effective_date``.

    ``authority`` is the generation-pinned fact source; ``None`` reads the facts
    of the registry validation in progress. ``effective_date`` is the
    filing-period date the governed facts are selected for.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    _install_redirect_modules()
    redirected: dict[BindingId, list[CasillaId]] = {}
    for redirect in _redirects:
        for binding_id, casilla_ids in redirect(revision, authority, effective_date).items():
            targets = redirected.setdefault(binding_id, [])
            targets.extend(casilla_id for casilla_id in casilla_ids if casilla_id not in targets)
    return {binding_id: tuple(casilla_ids) for binding_id, casilla_ids in redirected.items()}


def capped_binding_reach(
    revision: ModeloRevision, *, authority: GovernedFactSource | None, effective_date: date
) -> Mapping[BindingId, CappedBindingReach]:
    """Map each capped binding of ``revision`` to its cap and the casillas it reaches on ``effective_date``.

    A revision without a cap reads no redirect, so the common case touches no
    governed fact. A capped binding that reaches nothing keeps an empty
    ``casilla_ids``: registry build refuses it, and a consumer reading a map
    built outside build validation still sees it rather than losing it.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    caps = {binding.id: binding.grade_cap for binding in revision.bindings if binding.grade_cap is not None}
    if not caps:
        no_reach: dict[BindingId, CappedBindingReach] = {}
        return MappingProxyType(no_reach)
    bound = casillas_by_binding(revision)
    redirected = binding_output_redirects(revision, authority=authority, effective_date=effective_date)
    reach: dict[BindingId, CappedBindingReach] = {}
    for binding_id, cap in caps.items():
        casilla_ids = list(bound.get(binding_id, ()))
        casilla_ids.extend(casilla_id for casilla_id in redirected.get(binding_id, ()) if casilla_id not in casilla_ids)
        reach[binding_id] = CappedBindingReach(binding_id=binding_id, cap=cap, casilla_ids=tuple(casilla_ids))
    return MappingProxyType(reach)


def capped_binding_reach_digest(reach: Mapping[BindingId, CappedBindingReach]) -> str:
    """Return a content digest of the declarations a capped-value screen reads.

    Order-free and grounded only in the declarations themselves, so a
    publication that changes nothing in them yields the same digest.
    """
    return content_hash_hex(
        {
            str(binding_id): {
                "grade": entry.cap.grade.value,
                "reason": entry.cap.reason.value,
                "legal_refs": sorted(str(ref) for ref in entry.cap.legal_refs),
                "casilla_ids": sorted(str(casilla_id) for casilla_id in entry.casilla_ids),
            }
            for binding_id, entry in reach.items()
        }
    )


__all__ = [
    "BindingOutputRedirect",
    "CappedBindingReach",
    "binding_output_redirects",
    "capped_binding_reach",
    "capped_binding_reach_digest",
    "register_binding_output_redirect",
    "snapshot_reach_date",
]
