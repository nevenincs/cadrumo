"""Per-revision binding refusals derived from the provider registration authority.

The registration table states what each provider kind can do; this module is
where an authored row is held to it. Six refusals are errors, because each one
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
  resolved;
* a second ``prorrata_regularizacion`` binding in one revision, and two row
  bindings claiming one ``row_field`` of one export record. Both are order
  refusals: the prorrata consumer reads its four source roles positionally out
  of the concatenated declaration order, and export field derivation keeps the
  FIRST binding to claim a ``row_field`` and drops the rest. A revision carrying
  either duplicate therefore resolves differently depending on the merge order
  of its binding fragments, which is a filename accident rather than a
  declaration. Refusing the duplicate is what keeps the surviving positional
  reads meaningful, so the ambiguity is rejected at the source instead of being
  silently resolved downstream.

The fifth check, an unreferenced binding without the explicit
``non_calculation`` disposition, is :func:`unreferenced_binding_advisories` and
is deliberately NOT part of the failure list: the authored corpus still carries
enough such rows across the loadable modelos that enrolling it as an error would
refuse the corpus rather than gate it. It is a public diagnostic now and becomes
a refusal once the corpus rewrite lands. No count is recorded here: a number in
prose is stale the first time a modelo is authored, and the advisory itself
reports the live population.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cadrumo.core.aggregation import BindingAggregationOp
from cadrumo.domain.calculations.registry.binding_aggregation import binding_aggregation_op
from cadrumo.domain.calculations.registry.binding_provider_registration import (
    BINDING_PROVIDER_REGISTRATIONS,
    require_relative_provider_coordinates,
    validate_binding_against_registration,
)
from cadrumo.domain.calculations.registry.binding_selector_utils import selector_as_dict
from cadrumo.domain.calculations.registry.binding_targets import binding_consumers
from cadrumo.domain.calculations.registry.binding_temporal import BindingApplicabilityKind
from cadrumo.domain.calculations.registry.prorrata_regularizacion_bindings import ProrrataRegularizacionProvider
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.ids import BindingId
    from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision

__all__ = [
    "informational_binding_ids",
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
    failures.extend(_prorrata_duplicate_failures(prefix=prefix, revision=revision))
    failures.extend(_duplicate_row_field_failures(prefix=prefix, revision=revision))
    return failures


def _prorrata_duplicate_failures(*, prefix: str, revision: ModeloRevision) -> list[str]:
    """Refuse a revision declaring more than one prorrata regularisation binding.

    The consumer concatenates every prorrata binding's ``source_casilla_ids`` in
    declaration order and then reads four roles -- deductible cuotas, volume with
    right to deduct, total volume, definitive percentage -- by position. With one
    binding the positions come from that binding's own reviewed order; with two
    they come from whichever fragment filename sorted first, so the same corpus
    would compute a different regularisation after an unrelated rename.
    """
    declared = [
        binding.id for binding in revision.bindings if isinstance(binding.provider, ProrrataRegularizacionProvider)
    ]
    if len(declared) < 2:
        return []
    return [
        f"{prefix}: {len(declared)} prorrata_regularizacion bindings are declared ({sorted(declared)}); "
        f"the positional source roles are read from one binding's reviewed order, so a second declaration "
        f"makes the regularisation depend on binding fragment merge order",
    ]


def _duplicate_row_field_failures(*, prefix: str, revision: ModeloRevision) -> list[str]:
    """Refuse two row bindings claiming one ``row_field`` of one record.

    A ``rows`` binding names the record and the row field it fills. Two bindings
    naming the same pair are not two readings of one slot; they are an ambiguity
    resolved by merge order at every consumer. Export field derivation is the
    sharpest case -- it keeps the first claimant and silently drops the rest, so
    the emitted filing record carries whichever binding's legal and source refs
    happened to sort first -- and the row-set projection has the same problem.
    The pair is checked on the declared selector rather than on the export
    projection so that a record which is not (yet) claimed by an export layout
    is held to the same uniqueness as one that is.
    """
    claimants: dict[tuple[str, str], list[BindingId]] = {}
    for binding in revision.bindings:
        if binding_aggregation_op(binding) is not BindingAggregationOp.ROWS:
            continue
        selector = selector_as_dict(binding)
        record = selector.get("record")
        row_field = selector.get("row_field")
        if not isinstance(record, str) or not isinstance(row_field, str):
            continue
        claimants.setdefault((record, row_field), []).append(binding.id)
    return [
        f"{prefix}: record {record!r} row field {row_field!r} is claimed by {len(ids)} row bindings "
        f"({sorted(ids)}); only the first in binding order contributes a derived export field, so the "
        f"emitted record depends on binding fragment merge order"
        for (record, row_field), ids in sorted(claimants.items())
        if len(ids) > 1
    ]


def unreferenced_binding_advisories(*, prefix: str, revision: ModeloRevision) -> tuple[str, ...]:
    """Return one advisory per binding no typed consumer names.

    A binding with no casilla, formula, export, or relation consumer is either
    an orphan or an export-only declaration; the second case says so through
    ``applicability.kind == "non_calculation"`` and is skipped here. The
    remainder is an advisory rather than a refusal while the authored corpus
    still carries several hundred such rows.

    The skipped rows are not lost: :func:`informational_binding_ids` reports the
    same population under its own name, so a disposition moves a row from one
    counted line to another rather than out of the report.
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


def informational_binding_ids(revision: ModeloRevision) -> tuple[BindingId, ...]:
    """Return the bindings of one revision that declare a non-calculation disposition.

    The counterpart of :func:`unreferenced_binding_advisories`: the advisory
    skips these rows, and this is where they stay visible. Authoring a
    disposition must move a binding between two reported lines, never make it
    disappear, or the disposition would become a way to silence a row rather
    than to classify it.
    """
    return tuple(
        binding.id
        for binding in revision.bindings
        if binding.applicability.kind == BindingApplicabilityKind.NON_CALCULATION
    )
