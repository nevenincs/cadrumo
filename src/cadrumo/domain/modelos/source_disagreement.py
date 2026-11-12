"""The one typed record of two calculation sources disagreeing on the same figure.

A credit casilla compared with its cross-check sources, and a precedence tier
replacing a different lower-tier value, raise the same fact: which figure, which
sources, what each said, and which one the calculation used. One type gives one
finding key, one resolution record and one renderer; the persisted issue reason
is the only thing that says which screen raised it.

Every value keeps its own type. A comparison never narrows a date, a token or a
row set to an amount, so equality is decided per member and a disagreement on a
non-numeric channel is stated as what it is. An amount is held as canonical
decimal text, the one wire form a stored issue and a public result share, and
read back as a ``Decimal``.

``finding_key`` is the digest of everything that identifies the disagreement and
nothing that merely locates it: the work unit, an evidence fingerprint and a
snapshot id are left out, so a recalculation that reproduces the same sources
and amounts keeps the same key, and any changed amount, added or removed
source, different registry revision or changed declaration changes it. The key
is checked on load, so a stored fact whose content was altered is refused.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Final, Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.casilla_id import CasillaId
from ...core.decimal.grammar import DECIMAL_TEXT_MAX_LENGTH
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.hashing import content_hash_hex
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operator_action_enums import NoRecoveryOutcome
from .errors import ModeloValidatedRecord, ModeloValidationError

__all__ = [
    "DisagreementBooleanValue",
    "DisagreementDateValue",
    "DisagreementDecimalValue",
    "DisagreementEnumValue",
    "DisagreementRelationValue",
    "DisagreementRowsValue",
    "DisagreementScalarValue",
    "DisagreementTextValue",
    "DisagreementValue",
    "SourceDisagreementEntry",
    "SourceDisagreementFact",
    "SourceDisagreementRole",
]


class SourceDisagreementRole(StrEnum):
    """The part one source plays in a disagreement."""

    VALUE_SOURCE = "value_source"
    """The declared source of a credit casilla's value."""
    CROSS_CHECK = "cross_check"
    """A source the credit casilla is compared with."""
    PROFILE = "profile"
    BACKEND = "backend"
    BORRADOR = "borrador"
    CALLER = "caller"


_MACHINE_DECIMAL_TEXT: Final = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")
"""A sign, digits and an optional fraction: the only shape ``format(amount, "f")`` writes."""


def _is_machine_decimal_text(text: str) -> bool:
    """Whether ``text`` is exactly the canonical text of the decimal it spells.

    A stored amount is machine text, never operator input, so the operator
    grammar's refusal of a European thousands shape does not apply: ``12.500``
    is twelve and a half held to three places. Leading zeros, a ``+`` sign,
    exponents and separators other than one dot are refused because they do not
    survive the round trip through ``Decimal``.
    """
    if _MACHINE_DECIMAL_TEXT.fullmatch(text) is None:
        return False
    try:
        return format(Decimal(text), "f") == text
    except InvalidOperation:
        return False


class _DisagreementValueBase(BaseModel):
    model_config = STRICT_FROZEN_CONFIG


class _DisagreementAmountBase(_DisagreementValueBase):
    amount: str = Field(min_length=1, max_length=DECIMAL_TEXT_MAX_LENGTH)

    @field_validator("amount")
    @classmethod
    @pydantic_validation_boundary
    def _amount_is_canonical_decimal(cls, value: str) -> str:
        if not _is_machine_decimal_text(value):
            raise ModeloValidationError(
                "a disagreement amount must be canonical decimal text",
                no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                record=ModeloValidatedRecord.SOURCE_DISAGREEMENT,
            )
        return value

    @classmethod
    def of(cls, amount: Decimal) -> Self:
        """Hold ``amount`` as its canonical decimal text, keeping its exponent."""
        return cls(amount=format(amount, "f"))

    @property
    def decimal(self) -> Decimal:
        """Return the amount as a ``Decimal``."""
        return Decimal(self.amount)


class DisagreementDecimalValue(_DisagreementAmountBase):
    """A money, decimal or integer figure."""

    kind: Literal["decimal"] = "decimal"


class DisagreementEnumValue(_DisagreementValueBase):
    """A closed-vocabulary token."""

    kind: Literal["enum"] = "enum"
    token: str = Field(min_length=1, max_length=128)


class DisagreementDateValue(_DisagreementValueBase):
    """A date."""

    kind: Literal["date"] = "date"
    value: date


class DisagreementBooleanValue(_DisagreementValueBase):
    """A yes or no."""

    kind: Literal["boolean"] = "boolean"
    value: bool


class DisagreementTextValue(_DisagreementValueBase):
    """A free text figure."""

    kind: Literal["text"] = "text"
    value: str = Field(max_length=512)


class DisagreementRelationValue(_DisagreementAmountBase):
    """The value a registry relation resolved to."""

    kind: Literal["relation"] = "relation"


DisagreementScalarValue = Annotated[
    DisagreementDecimalValue
    | DisagreementEnumValue
    | DisagreementDateValue
    | DisagreementBooleanValue
    | DisagreementTextValue
    | DisagreementRelationValue,
    Field(discriminator="kind"),
]
"""One value of a scalar channel."""


class DisagreementRowsValue(_DisagreementValueBase):
    """The whole ordered row set one source states for a row channel."""

    kind: Literal["rows"] = "rows"
    rows: tuple[DisagreementScalarValue, ...]


DisagreementValue = Annotated[
    DisagreementDecimalValue
    | DisagreementEnumValue
    | DisagreementDateValue
    | DisagreementBooleanValue
    | DisagreementTextValue
    | DisagreementRelationValue
    | DisagreementRowsValue,
    Field(discriminator="kind"),
]
"""What one source states, in its own type."""


class SourceDisagreementEntry(BaseModel):
    """One source taking part in a disagreement and what it states.

    ``source_ref`` names the source without disclosing it: a payer is named by
    its keyed digest, never by a plaintext tax identifier. ``evidence_ref`` is
    the evidence fingerprint or snapshot id the value was read from; it locates
    the evidence and does not take part in the finding key.
    """

    model_config = STRICT_FROZEN_CONFIG

    role: SourceDisagreementRole
    source_family: str = Field(min_length=1, max_length=64)
    resolver_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_ref: str | None = Field(default=None, min_length=1, max_length=256)
    value: DisagreementValue
    evidence_ref: str | None = Field(default=None, min_length=1, max_length=256)

    def key_form(self) -> dict[str, object]:
        """Return the entry as it enters the finding key: everything but its evidence locator."""
        return dict[str, object](self.model_dump(mode="json", exclude={"evidence_ref"}))


class SourceDisagreementFact(BaseModel):
    """Two or more sources stating different values for one figure of one calculation.

    ``key`` is the figure: the casilla for a credit reconciliation, the binding,
    relation or casilla for a tier divergence. ``reached_casillas`` are the
    exported casillas the figure reaches. ``selected_role`` is the role whose
    value the calculation used. ``inputs_digest`` is the content digest of the
    registry declarations the comparison read, never the authority generation,
    which changes on every publication.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1, max_length=16)
    filing_year: FilingYear
    period: str = Field(min_length=1, max_length=16)
    work_unit_id: str = Field(min_length=1, max_length=256)
    registry_revision_id: str = Field(min_length=1, max_length=256)
    inputs_digest: str = Field(min_length=1, max_length=128)
    key: str = Field(min_length=1, max_length=128)
    value_channel: str = Field(min_length=1, max_length=32)
    reached_casillas: tuple[CasillaId, ...]
    sources: tuple[SourceDisagreementEntry, ...] = Field(min_length=2)
    selected_role: SourceDisagreementRole
    differing_row_indices: tuple[int, ...] = ()
    finding_key: str = Field(min_length=64, max_length=64)

    @classmethod
    def of(
        cls,
        *,
        modelo: str,
        filing_year: FilingYear,
        period: str,
        work_unit_id: str,
        registry_revision_id: str,
        inputs_digest: str,
        key: str,
        value_channel: str,
        reached_casillas: tuple[CasillaId, ...],
        sources: tuple[SourceDisagreementEntry, ...],
        selected_role: SourceDisagreementRole,
        differing_row_indices: tuple[int, ...] = (),
    ) -> SourceDisagreementFact:
        """Build the fact with its finding key derived from its own content."""
        return cls(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            work_unit_id=work_unit_id,
            registry_revision_id=registry_revision_id,
            inputs_digest=inputs_digest,
            key=key,
            value_channel=value_channel,
            reached_casillas=reached_casillas,
            sources=sources,
            selected_role=selected_role,
            differing_row_indices=differing_row_indices,
            finding_key=_finding_key(
                _identifying_form(
                    modelo=modelo,
                    filing_year=filing_year,
                    period=period,
                    registry_revision_id=registry_revision_id,
                    inputs_digest=inputs_digest,
                    key=key,
                    value_channel=value_channel,
                    reached_casillas=reached_casillas,
                    sources=sources,
                    selected_role=selected_role,
                    differing_row_indices=differing_row_indices,
                )
            ),
        )

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _finding_key_matches_content(self) -> Self:
        if self.selected_role not in {source.role for source in self.sources}:
            raise ModeloValidationError(
                "a disagreement's selected role must be the role of one of its sources",
                no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                record=ModeloValidatedRecord.SOURCE_DISAGREEMENT,
            )
        if self.finding_key != _finding_key(
            _identifying_form(
                modelo=self.modelo,
                filing_year=self.filing_year,
                period=self.period,
                registry_revision_id=self.registry_revision_id,
                inputs_digest=self.inputs_digest,
                key=self.key,
                value_channel=self.value_channel,
                reached_casillas=self.reached_casillas,
                sources=self.sources,
                selected_role=self.selected_role,
                differing_row_indices=self.differing_row_indices,
            )
        ):
            raise ModeloValidationError(
                "a disagreement's finding key does not match its content",
                no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                record=ModeloValidatedRecord.SOURCE_DISAGREEMENT,
            )
        return self


def _identifying_form(
    *,
    modelo: str,
    filing_year: FilingYear,
    period: str,
    registry_revision_id: str,
    inputs_digest: str,
    key: str,
    value_channel: str,
    reached_casillas: tuple[CasillaId, ...],
    sources: tuple[SourceDisagreementEntry, ...],
    selected_role: SourceDisagreementRole,
    differing_row_indices: tuple[int, ...],
) -> dict[str, object]:
    """Return what identifies a disagreement: everything except the work unit and the evidence locators."""
    return {
        "modelo": modelo,
        "filing_year": int(filing_year),
        "period": period,
        "registry_revision_id": registry_revision_id,
        "inputs_digest": inputs_digest,
        "key": key,
        "value_channel": value_channel,
        "reached_casillas": [str(casilla) for casilla in reached_casillas],
        "sources": [source.key_form() for source in sources],
        "selected_role": selected_role.value,
        "differing_row_indices": list(differing_row_indices),
    }


def _finding_key(identifying: dict[str, object]) -> str:
    return content_hash_hex(identifying)
