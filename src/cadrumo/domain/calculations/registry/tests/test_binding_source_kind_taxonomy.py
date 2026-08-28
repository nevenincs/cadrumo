"""Parity gates binding :class:`BindingSourceKind` to the registry and frozensets.

These guards keep the single canonical source-kind taxonomy
(:class:`cadrumo.core.BindingSourceKind`) in lock-step with two surfaces it claims
authority over:

* every ``source`` token actually declared across the compiled registry
  revisions (the registry is the authority for which tokens exist), and
* the per-family source-kind frozensets, which MUST be derived subsets of the
  enum rather than independently hand-maintained.

This is the source-kind sibling of the :class:`cadrumo.core.Modelo` /
``registry_modelo_codes()`` parity gate in ``core/tests/test_modelo.py``.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from .....application.aggregation import DEFERRED_SOURCE_KINDS
from .....core import BindingSourceKind
from .....core.aggregation import (
    COUNTERPART_SOURCE_KINDS,
    INVOICE_BINDING_SOURCE_KINDS,
    LEDGER_BINDING_SOURCE_KINDS,
)
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _declared_source_kinds() -> set[BindingSourceKind]:
    """Return every distinct ``source`` declared across all compiled revisions."""
    modelos, _ = _committed_registry_tree()
    declared: set[BindingSourceKind] = set()
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for binding in revision.bindings:
                declared.add(binding.source)
    return declared


def test_declared_registry_sources_are_a_subset_of_the_enum() -> None:
    """Every binding ``source`` in the registry is a :class:`BindingSourceKind`.

    Because the schema field is typed :class:`BindingSourceKind`, the registry
    loader already rejects an unknown token at compile time; this assertion
    re-confirms it across the full tree and yields an instructive diff if a
    revision ever declares a token outside the enum.
    """
    declared = _declared_source_kinds()
    enum_members = set(BindingSourceKind)

    assert declared <= enum_members, (
        "Registry declares binding source token(s) absent from BindingSourceKind: "
        f"{sorted(str(kind) for kind in declared - enum_members)}"
    )


# Enum members that are load-bearing in code (validators, selector dispatch,
# resolver routing) but are not yet declared by any compiled registry binding.
# These are the source-kind analogue of ``NON_REGISTRY_MODELOS``: each is fenced
# as out-of-scope-but-tracked by the binding-source-kind taxonomy design
# (the ``PurchaseInvoiceEvidenceSourceResolver`` data-shape blocker and the
# counterpart-shaped ``ledger_transaction`` source). A member dropping off this
# set without gaining a registry declaration is a genuine orphan and fails the
# gate below.
_RESERVED_UNDECLARED_SOURCE_KINDS: frozenset[BindingSourceKind] = frozenset(
    {
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
        BindingSourceKind.LEDGER_TRANSACTION,
    },
)


# Enum members that are resolved entirely by a pre-mesh gate and carry NO registry
# binding declaration by design. Unlike the reserved-undeclared carve-out (members
# awaiting a future registry binding), these are mesh-only sourcing decisions whose
# canonical home is the application resolver mesh, not a
# ``DataBindingDefinition.source``: ``borrador`` is the Modelo 100 borrador prefill
# and ``iva_wallet_decision`` is the M303 IVA-wallet compensación decision. They are
# first-class :class:`BindingSourceKind` members (taxonomy unification) so
# the mesh carries enum members, but they will never appear in the registry, so the
# enum↔registry orphan gate exempts them here. The application-layer enum↔mesh parity
# gate (``test_binding_source_kind_mesh_parity.py``) asserts they ARE accounted for
# as enrolled/pre-mesh sources, closing the union so neither set is silently missing.
_MESH_ONLY_SOURCE_KINDS: frozenset[BindingSourceKind] = frozenset(
    {
        BindingSourceKind.BORRADOR,
        BindingSourceKind.IVA_WALLET_DECISION,
    },
)


def _deferred_undeclared_source_kinds(declared: frozenset[BindingSourceKind]) -> frozenset[BindingSourceKind]:
    """Members the application mesh DEFERS that carry no registry binding yet.

    Derived from production's :data:`DEFERRED_SOURCE_KINDS` rather than restated,
    because a second copy of that decision drifts from it: this was a hand-written
    empty set annotated "currently empty", and it stayed empty when
    ``withholding296`` was deferred, so a member with a real, reviewed deferral
    was reported as an orphan or typo.

    The distinction the carve-out draws still holds and is what the subtraction
    computes: the other deferred members (M184 / M232 / M720 / M360) ARE
    registry-declared and merely lack a live resolver, so they never reach here.
    These are advisory-backed feeds whose registry binding waits on a separately
    deferred upstream, and a member that later gains a binding leaves the set on
    its own.
    """
    return frozenset(DEFERRED_SOURCE_KINDS) - declared


def test_enum_members_have_no_undeclared_orphans_beyond_reserved_sources() -> None:
    """No enum member sits unused beyond the design-fenced reserved carve-out.

    The enum is the canonical *declarable* binding-source set. Every member
    except the documented :data:`_RESERVED_UNDECLARED_SOURCE_KINDS` must be
    exercised by at least one compiled registry binding; an undocumented orphan
    is either a typo or a token that should have been removed. The carve-out
    mirrors the ``NON_REGISTRY_MODELOS`` pattern in ``core/tests/test_modelo.py``
    and is itself asserted disjoint from the declared set, so a reserved member
    that *does* gain a registry declaration must be removed from the carve-out.
    """
    declared = _declared_source_kinds()
    enum_members = set(BindingSourceKind)

    orphans = (
        enum_members
        - declared
        - _RESERVED_UNDECLARED_SOURCE_KINDS
        - _MESH_ONLY_SOURCE_KINDS
        - _deferred_undeclared_source_kinds(frozenset(declared))
    )
    assert not orphans, (
        "BindingSourceKind member(s) declared by no registry binding and not in "
        f"the reserved/mesh-only/deferred carve-outs (orphan or typo): {sorted(str(kind) for kind in orphans)}"
    )

    # The deferred carve-out no longer needs a staleness assertion: it is derived
    # by subtracting the declared set, so a member that gains a registry binding
    # leaves it in the same breath and the intersection is empty by construction.
    # Asserting it here would be a tautology. What IS still worth holding is that
    # production's deferral list names only real members, which a typo in
    # DEFERRED_SOURCE_KINDS would break.
    assert frozenset(DEFERRED_SOURCE_KINDS) <= set(BindingSourceKind), (
        "DEFERRED_SOURCE_KINDS names something outside the closed taxonomy"
    )

    spuriously_reserved = _RESERVED_UNDECLARED_SOURCE_KINDS & declared
    assert not spuriously_reserved, (
        "Reserved-undeclared source kind(s) now declared by the registry; remove "
        f"from _RESERVED_UNDECLARED_SOURCE_KINDS: {sorted(str(kind) for kind in spuriously_reserved)}"
    )

    spuriously_mesh_only = _MESH_ONLY_SOURCE_KINDS & declared
    assert not spuriously_mesh_only, (
        "Mesh-only source kind(s) now declared by the registry; a borrador / "
        "iva_wallet_decision binding contradicts the pre-mesh-gate design — remove "
        f"from _MESH_ONLY_SOURCE_KINDS: {sorted(str(kind) for kind in spuriously_mesh_only)}"
    )


def test_invoice_frozenset_is_the_invoice_subset_of_the_enum() -> None:
    """``INVOICE_BINDING_SOURCE_KINDS`` is exactly the four invoice members."""
    assert {
        BindingSourceKind.COLLECTIBLE_INVOICE,
        BindingSourceKind.PAYABLE_INVOICE,
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
        BindingSourceKind.M347_THIRD_PARTY_OPERATION,
    } == INVOICE_BINDING_SOURCE_KINDS
    assert set(BindingSourceKind) >= INVOICE_BINDING_SOURCE_KINDS


def test_ledger_frozenset_covers_all_ledger_aggregation_members() -> None:
    """``LEDGER_BINDING_SOURCE_KINDS`` tracks the enum's ledger namespace.

    Guards against the historical regression where the set listed only two of
    the ledger kinds (OSS and renta-income were missing), which silently
    excluded those modelos from the ledger preflight. The fifth member is the
    M130 deductible-expense (gasto) aggregation source, the OUTGOING sibling of
    the renta-income source; the sixth is the M151 impatriado (Ley Beckham)
    Spanish-source base aggregation source; the seventh is the M210 explicit
    IRNR income aggregation. ``ledger_transaction`` remains a counterpart
    substrate rather than an aggregation binding source.
    """
    assert {
        BindingSourceKind.LEDGER_OSS_AGGREGATION,
        BindingSourceKind.LEDGER_IVA_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
        BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION,
        BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION,
    } == LEDGER_BINDING_SOURCE_KINDS
    assert set(BindingSourceKind) >= LEDGER_BINDING_SOURCE_KINDS
    assert BindingSourceKind.LEDGER_TRANSACTION not in LEDGER_BINDING_SOURCE_KINDS
    assert len(LEDGER_BINDING_SOURCE_KINDS) == 7


def test_inventory_is_a_distinct_non_ledger_non_invoice_source_kind() -> None:
    """Inventory names its schedule proposition without joining another family."""
    assert BindingSourceKind.INVENTORY.value == "inventory"
    assert BindingSourceKind.INVENTORY not in LEDGER_BINDING_SOURCE_KINDS
    assert BindingSourceKind.INVENTORY not in INVOICE_BINDING_SOURCE_KINDS
    assert BindingSourceKind.INVENTORY not in COUNTERPART_SOURCE_KINDS


def test_counterpart_frozenset_is_a_subset_of_the_enum() -> None:
    """The counterpart source kinds are a derived subset of :class:`BindingSourceKind`.

    ``COUNTERPART_SOURCE_KINDS`` is declared directly over :class:`BindingSourceKind`
    members (taxonomy unification, replacing the former
    ``AggregationSourceKind``-derived subset); the assertion confirms every
    counterpart value is a binding-source member.
    """
    counterpart_as_binding = {BindingSourceKind(kind.value) for kind in COUNTERPART_SOURCE_KINDS}
    assert counterpart_as_binding <= set(BindingSourceKind)
    assert counterpart_as_binding == {
        BindingSourceKind.LEDGER_TRANSACTION,
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
        BindingSourceKind.PAYABLE_INVOICE,
        BindingSourceKind.COLLECTIBLE_INVOICE,
    }


def test_per_family_frozensets_are_disjoint_where_expected() -> None:
    """Invoice and ledger families do not overlap.

    ``ledger_transaction`` is a counterpart/invoice-shaped source, not a ledger
    aggregation source, so the invoice and ledger frozensets are disjoint.
    """
    assert INVOICE_BINDING_SOURCE_KINDS.isdisjoint(LEDGER_BINDING_SOURCE_KINDS)


class _SourceEnvelope(BaseModel):
    source: BindingSourceKind


def test_bogus_source_string_is_rejected_by_the_typed_field() -> None:
    """Anti-tautology: a token outside the enum fails typed validation.

    If this ever passes for a nonsense string, the field has silently widened
    and every parity assertion above is meaningless.
    """
    with pytest.raises(ValidationError):
        _SourceEnvelope.model_validate({"source": "not_a_real_source_kind"})


def test_retired_literal_source_string_is_rejected_by_the_typed_field() -> None:
    """The removed literal-value pseudo-source cannot re-enter the registry."""
    with pytest.raises(ValidationError):
        _SourceEnvelope.model_validate({"source": "constant_value"})


def test_every_enum_member_round_trips_through_the_typed_field() -> None:
    """Each canonical token validates to its member and back, byte-stable.

    Confirms the behaviour-preserving lift: the enum's string value equals the
    stored token, so a persisted ``source`` survives validation unchanged.
    """
    for member in BindingSourceKind:
        envelope = _SourceEnvelope.model_validate({"source": member.value})
        assert envelope.source is member
        assert envelope.source.value == member.value
