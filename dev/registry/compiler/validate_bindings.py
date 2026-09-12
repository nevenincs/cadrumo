"""Per-revision binding refusals derived from the provider registration authority.

The registration table states what each provider kind can do; this module is
where an authored row is held to it. Four refusals are errors, because each one
names a declaration that cannot resolve to the value it promises:

* a provider kind with no registration, or a ``deferred`` kind named by a
  ``BOUND`` casilla -- a deferred kind may exist, but nothing routes it, so a
  casilla resting on one would resolve blank rather than to a proven zero;
* every diagnostic :func:`validate_binding_against_registration` earns -- the
  value channel, the aggregation operation, the rows-versus-scalar agreement
  between them, and the terminal-origin classes the family can produce;
* an absolute filing coordinate on any provider member, which the domain owns
  structurally and checks once at import (see
  :func:`~cadrumo.domain.calculations.registry.binding_provider_registration.require_relative_provider_coordinates`);
* a reviewed-equivalent binding whose value contract differs from the primary's
  -- two alternates that disagree on data type or channel are not equivalents,
  and the casilla would take a different typed value depending on which one
  resolved.

The fifth check, an unreferenced binding without the explicit
``non_calculation`` disposition, is :func:`unreferenced_binding_advisories` and
is deliberately NOT part of the failure list: measured across every currently
loadable modelo it reports 299 rows (232: 96, 360: 151, 184: 38, 720: 9, 182: 5),
so enrolling it as an error would refuse the corpus rather than gate it. It is a
public diagnostic now and becomes a refusal once the corpus rewrite lands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cadrumo.domain.calculations.registry.binding_provider_registration import (
    BINDING_PROVIDER_REGISTRATIONS,
    require_relative_provider_coordinates,
    validate_binding_against_registration,
)
from cadrumo.domain.calculations.registry.binding_targets import binding_consumers
from cadrumo.domain.calculations.registry.binding_temporal import BindingApplicabilityKind
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.ids import BindingId
    from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision

__all__ = [
    "unreferenced_binding_advisories",
    "validate_binding_registration_section",
]

require_relative_provider_coordinates()


def _bound_casilla_binding_ids(revision: ModeloRevision) -> dict[BindingId, str]:
    """Return each binding a ``BOUND`` casilla names, mapped to that casilla."""
    named: dict[BindingId, str] = {}
    for casilla in revision.casillas:
        if casilla.input_kind is not InputKind.BOUND:
            continue
        if casilla.binding is not None:
            named.setdefault(casilla.binding, str(casilla.id))
        for alternate in casilla.alternate_bindings:
            named.setdefault(alternate, str(casilla.id))
    return named


def _registration_failures(
    *,
    prefix: str,
    binding: BindingDefinition,
    bound_by: dict[BindingId, str],
) -> list[str]:
    """Return the registration-authority failures one binding earns."""
    try:
        registration = BINDING_PROVIDER_REGISTRATIONS[binding.source]
    except KeyError:
        return [
            f"{prefix}: binding {binding.id!r} declares provider kind {binding.source.value!r} "
            f"with no enrolled registration",
        ]
    failures: list[str] = []
    if registration.disposition == "deferred" and binding.id in bound_by:
        failures.append(
            f"{prefix}: binding {binding.id!r} has the deferred provider kind {registration.kind.value!r} "
            f"and cannot feed bound casilla {bound_by[binding.id]!r}: no route resolves it",
        )
    failures.extend(f"{prefix}: {diagnostic}" for diagnostic in validate_binding_against_registration(binding))
    return failures


def _alternate_contract_failures(*, prefix: str, revision: ModeloRevision) -> list[str]:
    """Return failures for alternates whose value contract differs from the primary's."""
    by_id = {binding.id: binding for binding in revision.bindings}
    failures: list[str] = []
    for casilla in revision.casillas:
        if casilla.input_kind is not InputKind.BOUND or casilla.binding is None:
            continue
        primary = by_id.get(casilla.binding)
        if primary is None:
            continue
        for alternate_id in casilla.alternate_bindings:
            alternate = by_id.get(alternate_id)
            if alternate is None or alternate.value == primary.value:
                continue
            failures.append(
                f"{prefix}: casilla {casilla.id!r} alternate binding {alternate_id!r} declares value contract "
                f"{alternate.value.data_type.value}/{alternate.value.channel.value}, which differs from primary "
                f"binding {primary.id!r} contract {primary.value.data_type.value}/{primary.value.channel.value}",
            )
    return failures


def validate_binding_registration_section(*, prefix: str, revision: ModeloRevision) -> list[str]:
    """Return every registration-authority failure for one modelo revision.

    ``prefix`` names the modelo and revision, so each returned diagnostic
    identifies the modelo, the revision, the binding id, and the reason.
    """
    bound_by = _bound_casilla_binding_ids(revision)
    failures: list[str] = []
    for binding in revision.bindings:
        failures.extend(_registration_failures(prefix=prefix, binding=binding, bound_by=bound_by))
    failures.extend(_alternate_contract_failures(prefix=prefix, revision=revision))
    return failures


def unreferenced_binding_advisories(*, prefix: str, revision: ModeloRevision) -> tuple[str, ...]:
    """Return one advisory per binding no typed consumer names.

    A binding with no casilla, formula, export, or relation consumer is either
    an orphan or an export-only declaration; the second case says so through
    ``applicability.kind == "non_calculation"`` and is skipped here. The
    remainder is an advisory rather than a refusal while the authored corpus
    still carries several hundred such rows.
    """
    consumers = binding_consumers(revision)
    advisories: list[str] = []
    for binding in revision.bindings:
        if consumers[binding.id]:
            continue
        if binding.applicability.kind == BindingApplicabilityKind.NON_CALCULATION:
            continue
        advisories.append(
            f"{prefix}: binding {binding.id!r} is named by no casilla, formula, export, or relation and "
            f"declares no non_calculation applicability",
        )
    return tuple(advisories)
