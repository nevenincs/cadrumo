"""The figures a Modelo form lets the filer state for earlier returns the application does not hold.

A carry the registry reads from earlier returns through a previous-filing
binding or a relation can take a figure the filer states in their place
(``attest_prior_value``). The form serves one entry per such carry it shows:
the binding a statement is submitted to, the earlier returns it stands in
for, the served words of the action, and why it is refused when it is. The
carries that stand in for the same earlier returns form one family, which the
filer withdraws as a whole.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from pydantic import Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...domain.calculations.registry.ids import BindingId
from ..operator_actions.projection import PreconditionVerdictSnapshot
from .edit_models import ModeloEditBindingIntentKind
from .work_form_declaration_facts import ModeloFormBase
from .work_form_field_vocabulary import ModeloFormBindingAddressV1, ModeloFormEarlierFiling


def prior_value_family_id(filings: Iterable[ModeloFormEarlierFiling]) -> str:
    """The family of the figures that stand in for ``filings``: one token per earlier return, in a fixed order."""
    keys = sorted({(filing.modelo, filing.period.filing_year, filing.period.registry_token) for filing in filings})
    return "+".join(f"{modelo}-{year}-{token}" for modelo, year, token in keys)


class ModeloFormPriorValueRefusal(StrEnum):
    """Why the form does not admit a figure stated for a carry's earlier returns."""

    #: The application holds an earlier return the carry reads, so the carry follows it.
    SOURCE_HELD = "source_held"


class ModeloFormPriorValueWithdrawal(ModeloFormBase):
    """The action that withdraws every figure the filer stated for one family's earlier returns.

    Applying it stages ``remove_override`` on each binding, in one review; each
    carry then holds no stated figure, as before the statement.
    """

    family_id: str = Field(min_length=1)
    #: The carries of the family holding a stated figure, each a binding the withdrawal is submitted to.
    binding_ids: tuple[BindingId, ...] = Field(min_length=1)
    intent: ModeloEditBindingIntentKind = ModeloEditBindingIntentKind.REMOVE_OVERRIDE
    #: The action, in the form's language.
    action_words: str = Field(min_length=1)
    #: What the withdrawal does to each carry, as a review lists each staged change.
    effect_words: str = Field(min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _removes_each_binding_once(self) -> ModeloFormPriorValueWithdrawal:
        if self.intent is not ModeloEditBindingIntentKind.REMOVE_OVERRIDE:
            raise ValueError("a withdrawal stages remove_override")
        if list(self.binding_ids) != sorted(set(self.binding_ids)):
            raise ValueError("a withdrawal names each binding once, in order")
        return self


class ModeloFormPriorValueAttestation(ModeloFormBase):
    """One carry the filer can state the figure of, for the earlier returns the application does not hold.

    Applying it stages ``attest_prior_value`` with the figure on
    :attr:`edit_address`. When :attr:`admitted` is ``False`` the statement is
    not offered: :attr:`refusal_words` say why and :attr:`refusal` is the way
    out, as a refusal verdict carries it.
    """

    binding_id: BindingId
    #: The address a statement or its withdrawal is submitted to.
    edit_address: ModeloFormBindingAddressV1
    intent: ModeloEditBindingIntentKind = ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE
    #: The family the carry belongs to: the carries standing in for the same earlier returns.
    family_id: str = Field(min_length=1)
    #: The earlier returns a stated figure stands in for, in the order the registry reads them.
    earlier_filings: tuple[ModeloFormEarlierFiling, ...] = Field(min_length=1)
    #: :attr:`earlier_filings` in the form's language.
    source_words: str = Field(min_length=1)
    #: The action, in the form's language.
    action_words: str = Field(min_length=1)
    #: What the statement records and what follows when an earlier return is added later.
    statement_words: str = Field(min_length=1)
    #: What the statement does to the carry, as a review lists each staged change.
    effect_words: str = Field(min_length=1)
    #: Whether the carry holds a figure the filer stated.
    stated: bool
    #: Whether the edit admits a statement on the carry now.
    admitted: bool
    refusal_reason: ModeloFormPriorValueRefusal | None = None
    #: Why the statement is not admitted, in the form's language.
    refusal_words: str | None = Field(default=None, min_length=1)
    #: The way out of the refusal, with its served words and the registered operations it submits.
    refusal: PreconditionVerdictSnapshot | None = None
    #: Withdraws every stated figure of :attr:`family_id`; ``None`` when none of the family is stated or
    #: a withdrawal is not admitted.
    withdrawal: ModeloFormPriorValueWithdrawal | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _refused_exactly_when_not_admitted(self) -> ModeloFormPriorValueAttestation:
        if self.intent is not ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE:
            raise ValueError("a prior-value entry stages attest_prior_value")
        if self.edit_address.binding_id != self.binding_id:
            raise ValueError("a prior-value entry is submitted to its own binding")
        refused = (self.refusal_reason, self.refusal_words, self.refusal)
        if self.admitted != all(item is None for item in refused) or (
            not self.admitted and any(item is None for item in refused)
        ):
            raise ValueError("a refused statement, and only one, carries its reason, words and way out")
        if self.withdrawal is not None and (
            self.withdrawal.family_id != self.family_id
            or (self.stated and self.binding_id not in self.withdrawal.binding_ids)
        ):
            raise ValueError("a withdrawal withdraws the entry's own family, the entry included when stated")
        return self


__all__ = [
    "ModeloFormPriorValueAttestation",
    "ModeloFormPriorValueRefusal",
    "ModeloFormPriorValueWithdrawal",
    "prior_value_family_id",
]
