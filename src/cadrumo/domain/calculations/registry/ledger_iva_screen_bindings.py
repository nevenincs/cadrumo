"""Invoice IVA ledger screen selection and deduction partition checks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import TYPE_CHECKING, NamedTuple

from ....core.aggregation import BindingSourceKind
from ....core.iva_deduction_fact import IvaDeductionFactKind
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ...iva.flow import (
    IvaFlowDirection,
    is_standard_issued_or_received_flow,
    issued_flow_direction,
    received_flow_direction,
)
from ...iva.schema import IvaCategory, IvaLedgerObservationRole, IvaRateKind
from .binding_selector_utils import provider_member
from .binding_targets import casillas_by_binding
from .errors import RegistryValidationError
from .form_codes import form_for_role, forms_for_role
from .ids import BindingId
from .iva_category_catalogue import resolve_iva_category_catalogue
from .iva_rate_kind_catalogue import resolve_iva_rate_kind_catalogue
from .ledger_binding_selector_support import LedgerIvaFact
from .ledger_iva_bindings import LedgerIvaProvider

if TYPE_CHECKING:
    from .schema import BindingDefinition, ModeloRevision


class IvaLedgerScreenBinding(NamedTuple):
    """One selected-revision binding used by the invoice-versus-ledger screen.

    The screen is deliberately selected from the typed IVA selector rather than
    from binding IDs authored in application code.  Keeping the parsed selector
    alongside its ID lets callers retain the category/rate/flow provenance when
    producing diagnostics without introducing a second selector representation.
    """

    binding_id: BindingId
    selector: LedgerIvaProvider


class _InvoiceLedgerScreenShape(NamedTuple):
    """The selector axes that identify one invoice-screen slot."""

    categories: tuple[IvaCategory, ...]
    rate_kinds: tuple[IvaRateKind, ...]
    flow_direction: IvaFlowDirection
    fact: LedgerIvaFact


_INVOICE_LEDGER_SCREEN_OBSERVATION_ROLES: tuple[IvaLedgerObservationRole, ...] = (IvaLedgerObservationRole.SETTLEMENT,)
_INVOICE_LEDGER_SCREEN_FACTS = frozenset(
    {
        LedgerIvaFact.IVA_AMOUNT_SUM,
        LedgerIvaFact.RECARGO_AMOUNT_SUM,
    },
)
_INVOICE_LEDGER_SCREEN_ROLE = "invoice_ledger_screen.modelos"


def _invoice_ledger_screen_rate_slots(effective_date: date) -> tuple[_InvoiceLedgerScreenShape, ...]:
    """Project the screen's rate tiers from the governed rate-kind catalogue."""
    category_catalogue = resolve_iva_category_catalogue(effective_date=effective_date)
    general_category = category_catalogue.require("domestic_general")
    reduced_category = category_catalogue.require("domestic_reduced")
    super_reduced_category = category_catalogue.require("domestic_super_reduced")
    catalogue = resolve_iva_rate_kind_catalogue(effective_date=effective_date)
    general = catalogue.for_category(general_category)
    reduced = catalogue.for_category(reduced_category)
    super_reduced = catalogue.for_category(super_reduced_category)
    return (
        _InvoiceLedgerScreenShape(
            (general_category,),
            (general,),
            issued_flow_direction(),
            LedgerIvaFact.IVA_AMOUNT_SUM,
        ),
        _InvoiceLedgerScreenShape(
            (reduced_category,),
            (reduced,),
            issued_flow_direction(),
            LedgerIvaFact.IVA_AMOUNT_SUM,
        ),
        _InvoiceLedgerScreenShape(
            (super_reduced_category,),
            (super_reduced,),
            issued_flow_direction(),
            LedgerIvaFact.IVA_AMOUNT_SUM,
        ),
        _InvoiceLedgerScreenShape(
            (
                general_category,
                reduced_category,
                super_reduced_category,
            ),
            (general, reduced, super_reduced),
            received_flow_direction(),
            LedgerIvaFact.IVA_AMOUNT_SUM,
        ),
        _InvoiceLedgerScreenShape(
            (general_category,),
            (general,),
            issued_flow_direction(),
            LedgerIvaFact.RECARGO_AMOUNT_SUM,
        ),
        _InvoiceLedgerScreenShape(
            (reduced_category,),
            (reduced,),
            issued_flow_direction(),
            LedgerIvaFact.RECARGO_AMOUNT_SUM,
        ),
        _InvoiceLedgerScreenShape(
            (super_reduced_category,),
            (super_reduced,),
            issued_flow_direction(),
            LedgerIvaFact.RECARGO_AMOUNT_SUM,
        ),
    )


def _is_invoice_ledger_screen_candidate(
    revision: ModeloRevision,
    binding: BindingDefinition,
    selector: LedgerIvaProvider,
    *,
    modelo: str,
    effective_date: date,
    cash_accounting_treatments: tuple[str, ...] | None = None,
) -> bool:
    """Return whether a binding has the screen's typed candidate envelope.

    ``applied_rates`` is an orthogonal rate-layer axis.  M390's rate-specific
    annual boxes are not screen candidates because its conceptual total rows
    are rate-blind.  M303's ordinary reduced/super-reduced rows are qualified
    by a rate, while the same revision also declares supplemental transitional
    rungs.  The selected casilla continuity target distinguishes those layers:
    a target carrying the revision's transitional qualifier is a separate rung,
    not the conceptual screen slot.  This keeps the distinction in authored
    registry target identity rather than copying a rate fact into Python.
    """
    if not _is_conceptual_invoice_screen_rung(revision, binding, selector, modelo=modelo):
        return False
    rate_kinds = frozenset(resolve_iva_rate_kind_catalogue(effective_date=effective_date).positive_kinds)
    if not _has_invoice_screen_selector_axes(selector, cash_accounting_treatments):
        return False
    return _invoice_screen_categories_match(selector, effective_date) and set(selector.rate_kinds).issubset(rate_kinds)


def _is_conceptual_invoice_screen_rung(
    revision: ModeloRevision,
    binding: BindingDefinition,
    selector: LedgerIvaProvider,
    *,
    modelo: str,
) -> bool:
    if selector.applied_rates is not None:
        if modelo != form_for_role("iva.periodic"):
            return False
        target_ids = casillas_by_binding(revision).get(binding.id, ())
        if not target_ids:
            return False
        if any("transitorio" in target_id.casefold() for target_id in target_ids):
            return False
    return True


def _has_invoice_screen_selector_axes(
    selector: LedgerIvaProvider,
    cash_accounting_treatments: tuple[str, ...] | None,
) -> bool:
    return (
        selector.exemption_articles is None
        and selector.observation_roles == _INVOICE_LEDGER_SCREEN_OBSERVATION_ROLES
        and (cash_accounting_treatments is None or selector.cash_accounting_treatments == cash_accounting_treatments)
        and is_standard_issued_or_received_flow(selector.flow_direction)
        and selector.fact in _INVOICE_LEDGER_SCREEN_FACTS
    )


def _invoice_screen_categories_match(selector: LedgerIvaProvider, effective_date: date) -> bool:
    return set(selector.categories).issubset(
        {
            resolve_iva_category_catalogue(effective_date=effective_date).require("domestic_general"),
            resolve_iva_category_catalogue(effective_date=effective_date).require("domestic_reduced"),
            resolve_iva_category_catalogue(effective_date=effective_date).require("domestic_super_reduced"),
        },
    )


def _invoice_ledger_screen_shape(selector: LedgerIvaProvider) -> _InvoiceLedgerScreenShape:
    return _InvoiceLedgerScreenShape(
        categories=selector.categories,
        rate_kinds=selector.rate_kinds,
        flow_direction=selector.flow_direction,
        fact=selector.fact,
    )


def _partitions_by_deduction_kind(matches: Sequence[IvaLedgerScreenBinding]) -> bool:
    """Return whether the bindings serving one screen slot never claim the same row."""
    if len(matches) == 1:
        return True
    claimed: set[IvaDeductionFactKind] = set()
    for match in matches:
        kinds = match.selector.deduction_fact_kinds
        if kinds is None or claimed.intersection(kinds):
            return False
        claimed.update(kinds)
    return True


def invoice_ledger_screen_bindings(
    revision: ModeloRevision,
    *,
    modelo: str,
) -> tuple[IvaLedgerScreenBinding, ...]:
    """Resolve the invoice screen's typed bindings for its seven slots.

    The invoice-versus-ledger refusal applies only to the M303 and M390
    revisions.  For every other modelo the empty result preserves the previous
    non-applicability contract.  For an applicable modelo, every one of the
    seven slot shapes must be served; an incomplete, overlapping, cross-model,
    or unknown screen-shaped binding raises a registry validation error rather
    than silently weakening the screen.

    A slot is served by one binding, or by several that partition it by
    deduction kind: the domestic input IVA slot is split between the
    corrientes and the bienes de inversión boxes, whose rows share category,
    rate and flow.  Each of those bindings is screened, so an investment
    purchase's invoice is compared against the ledger exactly as a corriente
    one is.  Two bindings that could both claim one row would compare it twice,
    so their kind sets must be declared and disjoint.

    Binding IDs are returned in a stable conceptual order (three IVA output
    tiers, domestic input IVA, then three recargo tiers), and in declaration
    order within a partitioned slot.  The IDs are merely selected outputs; the
    selector is the authority used to identify them.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    if modelo not in forms_for_role(_INVOICE_LEDGER_SCREEN_ROLE):
        return ()

    rate_slots = _invoice_ledger_screen_rate_slots(revision.valid_from)
    expected_by_shape = _invoice_ledger_screen_candidates(revision, modelo, rate_slots)
    selected = _select_invoice_ledger_screen_bindings(revision, modelo, rate_slots, expected_by_shape)
    selected_ids = tuple(item.binding_id for item in selected)
    if len(set(selected_ids)) != len(selected_ids):
        raise RegistryValidationError(
            f"revision {revision.id!r} modelo {modelo!r} invoice IVA screen resolved duplicate binding IDs",
        )
    return tuple(selected)


def _invoice_ledger_screen_candidates(
    revision: ModeloRevision,
    modelo: str,
    rate_slots: tuple[_InvoiceLedgerScreenShape, ...],
) -> dict[_InvoiceLedgerScreenShape, list[IvaLedgerScreenBinding]]:
    shape_set = frozenset(rate_slots)
    expected_by_shape: dict[_InvoiceLedgerScreenShape, list[IvaLedgerScreenBinding]] = {
        shape: [] for shape in rate_slots
    }
    expected_prefix = f"modelo-{modelo}-"
    # The screen's treatment vocabulary is a revision declaration.  Derive it
    # from the first structural candidate instead of restating the allowed
    # classifications in Python; authored compilation checks each declaration
    # against the canonical IVA vocabulary fact.
    screen_cash_accounting_treatments: tuple[str, ...] | None = None
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.LEDGER_IVA_AGGREGATION:
            continue
        selector = provider_member(binding, LedgerIvaProvider)
        if not _is_invoice_ledger_screen_candidate(
            revision,
            binding,
            selector,
            modelo=modelo,
            effective_date=revision.valid_from,
            cash_accounting_treatments=screen_cash_accounting_treatments,
        ):
            continue
        if screen_cash_accounting_treatments is None:
            screen_cash_accounting_treatments = selector.cash_accounting_treatments
        shape = _invoice_ledger_screen_shape(selector)
        if shape not in shape_set:
            raise RegistryValidationError(
                f"revision {revision.id!r} modelo {modelo!r} has an unknown "
                f"invoice IVA screen selector shape {shape!r} on binding {binding.id!r}",
            )
        if not binding.id.startswith(expected_prefix):
            raise RegistryValidationError(
                f"revision {revision.id!r} modelo {modelo!r} has cross-model invoice IVA screen binding {binding.id!r}",
            )
        expected_by_shape[shape].append(IvaLedgerScreenBinding(binding.id, selector))
    return expected_by_shape


def _select_invoice_ledger_screen_bindings(
    revision: ModeloRevision,
    modelo: str,
    rate_slots: tuple[_InvoiceLedgerScreenShape, ...],
    expected_by_shape: Mapping[_InvoiceLedgerScreenShape, list[IvaLedgerScreenBinding]],
) -> list[IvaLedgerScreenBinding]:
    selected: list[IvaLedgerScreenBinding] = []
    for shape in rate_slots:
        matches = expected_by_shape[shape]
        if not matches or not _partitions_by_deduction_kind(matches):
            state = "missing" if not matches else "duplicate"
            raise RegistryValidationError(
                f"revision {revision.id!r} modelo {modelo!r} invoice IVA screen "
                f"shape is {state}: expected one binding or a deduction-kind partition, "
                f"got {len(matches)} for {shape!r}",
            )
        selected.extend(matches)
    return selected


def invoice_ledger_screen_binding_ids(
    revision: ModeloRevision,
    *,
    modelo: str,
) -> tuple[BindingId, ...]:
    """Return the selected revision's stable invoice-screen binding IDs.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    return tuple(item.binding_id for item in invoice_ledger_screen_bindings(revision, modelo=modelo))


class DeductionKindClaimOverlap(NamedTuple):
    """Two deducible bindings of one selector that both claim some deduction kind.

    ``shared_kinds`` is ``None`` when one of the two declares no kind at all and
    so claims every row the other one claims.
    """

    binding_ids: tuple[BindingId, BindingId]
    shared_kinds: tuple[IvaDeductionFactKind, ...] | None


def _selector_identity_without_deduction_kinds(selector: LedgerIvaProvider) -> tuple[tuple[str, str], ...]:
    """Render every selector axis except the deduction kind, so kind partitions group together."""
    axes = STR_KEYED_MAPPING_ADAPTER.validate_python(selector.model_dump(exclude={"deduction_fact_kinds"}))
    return tuple(sorted((key, repr(value)) for key, value in axes.items()))


def deducible_deduction_kind_overlaps(revision: ModeloRevision) -> tuple[DeductionKindClaimOverlap, ...]:
    """Return deducible bindings that split one quantity by deduction kind but overlap.

    A form that asks for one deducible quantity in two boxes by what was
    acquired -- Modelo 303 [28]/[29] against [30]/[31] -- is served by bindings
    whose selectors agree on every axis and differ only in
    ``deduction_fact_kinds``. That split holds only while no row is claimed by
    both: a corrientes binding that also admits ``domestic_investment``, or
    that declares no kind at all, puts a bien de inversión in [28] as well as in
    [30], and the deduction is declared twice with nothing else to notice it.

    Only bindings feeding a deducible casilla are compared, and only within a
    selector group where at least one member declares a kind. The self-assessed
    devengado side of an intra-community acquisition reads the same rows as its
    deducible side on purpose, and a group where nobody splits by kind is not a
    partition at all.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    groups = _deducible_binding_groups(revision)
    return tuple(overlap for members in groups.values() for overlap in _deduction_kind_overlaps_in_group(members))


def _deducible_binding_groups(
    revision: ModeloRevision,
) -> dict[tuple[tuple[str, str], ...], list[tuple[BindingId, LedgerIvaProvider]]]:
    targets = casillas_by_binding(revision)
    deducible_casillas = frozenset(casilla.id for casilla in revision.casillas if "deducible" in casilla.section)
    groups: dict[tuple[tuple[str, str], ...], list[tuple[BindingId, LedgerIvaProvider]]] = {}
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.LEDGER_IVA_AGGREGATION:
            continue
        if not any(casilla_id in deducible_casillas for casilla_id in targets.get(binding.id, ())):
            continue
        selector = provider_member(binding, LedgerIvaProvider)
        groups.setdefault(_selector_identity_without_deduction_kinds(selector), []).append((binding.id, selector))
    return groups


def _deduction_kind_overlaps_in_group(
    members: list[tuple[BindingId, LedgerIvaProvider]],
) -> tuple[DeductionKindClaimOverlap, ...]:
    if all(selector.deduction_fact_kinds is None for _, selector in members):
        return ()
    overlaps: list[DeductionKindClaimOverlap] = []
    for index, (left_id, left) in enumerate(members):
        for right_id, right in members[index + 1 :]:
            overlap = _deduction_kind_overlap(left_id, left, right_id, right)
            if overlap is not None:
                overlaps.append(overlap)
    return tuple(overlaps)


def _deduction_kind_overlap(
    left_id: BindingId,
    left: LedgerIvaProvider,
    right_id: BindingId,
    right: LedgerIvaProvider,
) -> DeductionKindClaimOverlap | None:
    if left.deduction_fact_kinds is None or right.deduction_fact_kinds is None:
        return DeductionKindClaimOverlap((left_id, right_id), None)
    shared = tuple(kind for kind in left.deduction_fact_kinds if kind in right.deduction_fact_kinds)
    return DeductionKindClaimOverlap((left_id, right_id), shared) if shared else None
