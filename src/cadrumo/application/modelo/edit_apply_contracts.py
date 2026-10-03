"""Bounded edit submission and settled result contracts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .edit_apply_operand_contracts import MODELO_EDIT_MANUAL_OVERRIDE_OPERAND
from .edit_apply_row_contracts import (
    EDIT_WIRE_DECIMAL_PATTERN,
    EDIT_WIRE_MODEL_CONFIG,
    DetailRowKindToken,
    ModeloDetailRowWireV1,
)
from .edit_apply_scalar_contracts import (
    ModeloEditApplyBindingIntentV1,
    ModeloEditApplyRowIntentV1,
    ModeloEditApplyScalarIntentV1,
)
from .edit_baseline_projection import ModeloEditApplyBaselineV1
from .edit_contract import ModeloEditMutationFamily
from .edit_models import (
    ModeloDetailRowEditIntentV1,
    ModeloEditDetailRowAddressV1,
    ModeloEditDetailRowIntentKind,
    ModeloEditSubmissionV1,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
)
from .edit_services import DETAIL_ROW_NATURAL_KEY_SEPARATOR
from .edit_value_grammar import ModeloEditValueGrammarV1


def _amount_within_declared_operand_bounds(
    value: int | str | bool | date | None,
    grammar: ModeloEditValueGrammarV1 | None,
) -> bool:
    """Report whether a money address's canonical amount stays inside the declared operand.

    The operand is a euro amount, so the bound applies to money addresses
    only: a ratio of ``0.125`` or a four-decimal quantity is a legitimate value
    that the money bound must not refuse. Only the declared range is judged
    here; a value that is not a canonical decimal, or a money amount finer than
    cents, is refused by the executor with its typed, address-level reason
    rather than by a validation error at the wire.
    """
    if grammar is None or not grammar.money_operand_bound or not isinstance(value, str):
        return True
    if EDIT_WIRE_DECIMAL_PATTERN.fullmatch(value) is None:
        return True
    amount = Decimal(value)
    return MODELO_EDIT_MANUAL_OVERRIDE_OPERAND.minimum <= amount <= MODELO_EDIT_MANUAL_OVERRIDE_OPERAND.maximum


class ModeloEditApplyDetailRowAddressV1(BaseModel):
    """Wire mirror of ModeloEditDetailRowAddressV1 carrying the key's components.

    The domain address holds a ``natural_key``: the row's own identity fields
    joined with ``|``. That joined string is a bounded free-form string, which
    is the same shape a passphrase has, so the credential-free journal check
    refuses it on the ``key`` token in its name and no schema predicate could
    tell the two apart.

    Nothing is exempted to get around that. The joined string is a derived
    convenience rather than information: every component is one of the row's
    own declared identity fields, already carried in the clear by the row
    mirrors in this module and already admitted by the same check. So the
    components cross instead, and ``to_address`` derives the key exactly as the
    domain type expects it.

    Carrying the components is also strictly less ambiguous than carrying the
    join, because a component that itself contains the separator is
    indistinguishable from a boundary once joined.
    """

    model_config = EDIT_WIRE_MODEL_CONFIG

    kind: Literal["detail_row"] = "detail_row"
    detail_row_kind: DetailRowKindToken
    identity_components: Annotated[
        tuple[Annotated[str, Field(min_length=1, max_length=200)], ...],
        Field(min_length=1, max_length=8),
    ]

    def to_address(self) -> ModeloEditDetailRowAddressV1:
        """Derive the domain address by joining the components it was built from."""
        return ModeloEditDetailRowAddressV1(
            detail_row_kind=self.detail_row_kind,
            natural_key=DETAIL_ROW_NATURAL_KEY_SEPARATOR.join(self.identity_components),
        )


class ModeloEditApplyDetailRowIntentV1(BaseModel):
    """Wire mirror of ModeloDetailRowEditIntentV1 with a payload-safe row."""

    model_config = EDIT_WIRE_MODEL_CONFIG

    address: ModeloEditApplyDetailRowAddressV1
    kind: ModeloEditDetailRowIntentKind
    row: ModeloDetailRowWireV1 | None = None

    def to_intent(self) -> ModeloDetailRowEditIntentV1:
        """Translate back to the real, fully re-validated domain intent."""
        return ModeloDetailRowEditIntentV1(
            address=self.address.to_address(),
            kind=self.kind,
            row=None if self.row is None else self.row.to_row(),
        )


class ModeloEditApplySubmissionV1(BaseModel):
    """Wire mirror of ModeloEditSubmissionV1 carrying a payload-safe baseline.

    Scalar, binding and row intents are mirrored only for their ``value``
    field: ``ModeloScalar`` (``Decimal | int | str | bool | date | None``)
    fails the operations payload-graph gate's validation/serialization
    schema-identity check, because ``Decimal`` validates from a number or a
    string but always serializes to a string. Every other field of these
    three families - addresses, intent kinds, ``move_to_index`` - is already
    payload-safe and carried through unchanged. This is a total translation:
    every field of every mirrored intent converts, nothing is dropped.

    ``detail_row_intents`` is carried, one wire type per per-modelo row kind.
    Each mirrors its row's ``Decimal`` fields as the exact characters
    submitted, and the two kinds that hydrate registry codes carry them raw so
    the real row type runs its own hydration during translation - one
    hydration shared with the CLI ``--row key=value`` path rather than a second
    copy free to drift.

    The address is mirrored too, and deliberately not by mirroring its
    ``natural_key``: see :class:`ModeloEditApplyDetailRowAddressV1` for why the
    components cross instead of the string derived from them.

    The mirrored payload is INPUT, not authority: ``apply_modelo_edit``
    re-resolves and independently re-validates every coordinate at the
    guarded commit point regardless of what this wire type carried, so a
    stale or forged mirror cannot be believed - a mismatch surfaces as the
    typed no-effect result, never a bad write.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    edit_contract_version: Literal[1] = 1
    baseline: ModeloEditApplyBaselineV1
    mutation_family: ModeloEditMutationFamily
    scalar_intents: Annotated[tuple[ModeloEditApplyScalarIntentV1, ...], Field(max_length=500)] = ()
    binding_intents: Annotated[tuple[ModeloEditApplyBindingIntentV1, ...], Field(max_length=500)] = ()
    row_intents: Annotated[tuple[ModeloEditApplyRowIntentV1, ...], Field(max_length=500)] = ()
    detail_row_intents: Annotated[tuple[ModeloEditApplyDetailRowIntentV1, ...], Field(max_length=500)] = ()

    @model_validator(mode="after")
    def _require_scalar_amounts_within_declared_operand_bounds(self) -> ModeloEditApplySubmissionV1:
        """Enforce the manual-override operand's declared range on money addresses.

        The broker path (`OperationTransientFinancialOperandProtocolV1`) that
        would normally enforce `MODELO_EDIT_MANUAL_OVERRIDE_OPERAND` is not
        reachable from any executor today (`OperationExecutorContext` has no
        accessor for it). The manual-override amount instead arrives here,
        through the already-admitted intent value, so this duplicates the
        bounds the declaration promises rather than leaving them unenforced.
        The bound is looked up by address in the baseline's admitted grammar,
        so only money casillas and money bindings are held to it. It should
        collapse into the broker once that wire lands.
        """
        grammars: dict[tuple[str, str], ModeloEditValueGrammarV1] = {}
        for entry in self.baseline.permitted_surface:
            if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1):
                grammars["writable_scalar", entry.casilla_id] = entry.grammar
            elif isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1):
                grammars["writable_binding_override", entry.binding_id] = entry.grammar
        for intent in self.scalar_intents:
            grammar = grammars.get(("writable_scalar", intent.address.casilla_id))
            if not _amount_within_declared_operand_bounds(intent.value, grammar):
                raise ValueError(
                    "scalar edit intent amount is outside the declared manual-override financial operand bounds"
                )
        for binding_intent in self.binding_intents:
            grammar = grammars.get(("writable_binding_override", binding_intent.address.binding_id))
            if not _amount_within_declared_operand_bounds(binding_intent.value, grammar):
                raise ValueError(
                    "binding edit intent amount is outside the declared manual-override financial operand bounds"
                )
        return self

    def to_submission(self) -> ModeloEditSubmissionV1:
        """Translate back to the real, fully re-validated domain submission."""
        return ModeloEditSubmissionV1(
            baseline=self.baseline.to_baseline(),
            mutation_family=self.mutation_family,
            scalar_intents=tuple(intent.to_intent() for intent in self.scalar_intents),
            binding_intents=tuple(intent.to_intent() for intent in self.binding_intents),
            row_intents=tuple(intent.to_intent() for intent in self.row_intents),
            detail_row_intents=tuple(intent.to_intent() for intent in self.detail_row_intents),
        )

    @classmethod
    def from_submission(cls, submission: ModeloEditSubmissionV1) -> ModeloEditApplySubmissionV1:
        """Mirror a domain submission onto the wire form the operation accepts.

        This is the direction an operator surface needs. The executor already
        owned wire-to-domain; without its inverse the registered apply
        operation had no caller outside this package's own tests, because a
        frontend that stages domain intents had no way to reach it.

        REFUSES A SUBMISSION CARRYING DETAIL ROWS, and the refusal is the
        honest answer rather than a gap. A domain
        :class:`ModeloEditDetailRowAddressV1` holds only the JOINED
        ``natural_key``, while the wire form carries the identity components
        that were joined to make it -- deliberately, per
        :class:`ModeloEditApplyDetailRowAddressV1`, because a component
        containing the separator is indistinguishable from a boundary once
        joined. Splitting the key here would reconstruct the components by
        guessing, and would guess wrong exactly when a taxpayer's own
        identifier contains the separator. A caller staging detail rows still
        holds the components and must build the wire address from those; it
        does not come back out of the domain address.
        """
        if submission.detail_row_intents:
            raise ValueError(
                "detail-row intents cannot be mirrored from a domain submission: the domain address "
                "carries only the joined natural key, and splitting it would guess the identity "
                "components. Build the wire detail-row address from the components at the point they "
                "were staged."
            )
        return cls(
            baseline=ModeloEditApplyBaselineV1.from_baseline(submission.baseline),
            mutation_family=submission.mutation_family,
            scalar_intents=tuple(
                ModeloEditApplyScalarIntentV1.from_intent(intent) for intent in submission.scalar_intents
            ),
            binding_intents=tuple(
                ModeloEditApplyBindingIntentV1.from_intent(intent) for intent in submission.binding_intents
            ),
            row_intents=tuple(ModeloEditApplyRowIntentV1.from_intent(intent) for intent in submission.row_intents),
        )


class ModeloEditApplyOperationRequestV1(BaseModel):
    """The admitted value-bearing edit submission held by secure-reference custody."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    submission: ModeloEditApplySubmissionV1


class ModeloEditApplyPublicResultV1(BaseModel):
    """The settled receipt id a caller outside this package may see.

    Only the id: the full receipt is the domain record of truth, addressable
    through the ModeloEditReceiptRepositoryPort capability, and this result exists to confirm
    which one a submission produced.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    result_version: int = 1
    receipt_id: Annotated[str, Field(min_length=1, max_length=128)]
    calculation_revision_id: Annotated[str, Field(min_length=1, max_length=128)]
