"""The limits a ledger entry form holds typed text to, read from their owners.

Whether a text is a number is the form's to see; how many decimals a field takes,
whether zero is a value, where a percentage stops and which scale a rate is typed
on are stated here, so every frontend reads one answer. So is how much text an
entry takes: each text limit is the bound of the request that carries the entry,
named by the module that owns the request, not a number of the form's.

A writer can be wider than its form: most money reaches the catalogue as a plain
decimal whatever its places. These are the limits of entry, not a claim that a
writer refuses everything beyond them.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel

from ...core.decimal.grammar import AMBIGUOUS_THOUSANDS_PATTERN, CENT_FRACTION_DIGITS, DECIMAL_TEXT_MAX_LENGTH
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.percentage import PERCENTAGE_BARE_FRACTION_CEILING, PERCENTAGE_ENTRY_DECIMALS, PERCENTAGE_MAX
from ...core.unit_proportion import UNIT_PROPORTION_MAX
from ...domain.buckets.event import BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH
from ...domain.identifiers import canonical_decimal_string
from ...domain.transactions.classification_rule import RULE_PATTERN_ENTRY_MAX_LENGTH
from .allocate_operation import LEDGER_ALLOCATE_RATIO_ID_MAX
from .classify_requests import LEDGER_CLASSIFY_SHORT_TEXT_MAX
from .counterparty_operation import LEDGER_COUNTERPARTY_NOTE_MAX, LEDGER_COUNTERPARTY_TAX_ID_MAX
from .evidence import LEDGER_EVIDENCE_LABEL_MAX, LEDGER_EVIDENCE_TEXT_MAX
from .own_account_operation import LEDGER_OWN_ACCOUNT_IBAN_MAX, LEDGER_OWN_ACCOUNT_SWIFT_BIC_MAX
from .split_operation import LEDGER_SPLIT_CHILDREN_MAX, LEDGER_SPLIT_PART_DESCRIPTION_MAX
from .update_contracts import LEDGER_GROUP_LABEL_MAX, LEDGER_UPDATE_TEXT_MAX

type DecimalRuleName = Literal["amount", "tax_amount", "quantity", "unit_price"]
type PercentUnit = Literal["points", "fraction"]
type PercentField = Literal["iva_rate", "retention_rate"]
type TextLimitName = Literal[
    "split_parts",
    "split_part_description",
    "entry_text",
    "group_label",
    "classify_token",
    "usage_ratio_id",
    "event_payload_value",
    "evidence_label",
    "evidence_note",
    "own_account_iban",
    "own_account_swift_bic",
    "counterparty_tax_id",
    "counterparty_note",
]


class LedgerEntryDecimalRule(BaseModel):
    """How many decimals one kind of figure takes, and whether zero is a value."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    rule: DecimalRuleName
    decimals: int
    zero: bool


class LedgerEntryPercentField(BaseModel):
    """The scale one field's rate is typed on."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    field: PercentField
    unit: PercentUnit


class LedgerEntryTextLimit(BaseModel):
    """The most characters (or, for a count, the most items) one kind of entry takes."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    name: TextLimitName
    max: int


class LedgerEntryLimitsProjection(BaseModel):
    """Every limit a ledger entry form holds typed text to."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    decimal_text_max: int
    two_way_decimal: str
    decimal_rules: tuple[LedgerEntryDecimalRule, ...]
    percent_decimals: int
    percent_points_max: str
    percent_fraction_max: str
    percent_bare_fraction_ceiling: str
    document_percent_fields: tuple[LedgerEntryPercentField, ...]
    rule_pattern_max: int
    text_limits: tuple[LedgerEntryTextLimit, ...]


_INVOICE_LINE_ENTRY_DECIMALS: Final = 6
"""The fraction digits an invoice line's quantity or unit price is typed with; the line's own model has no cap."""

_DECIMAL_RULES: Final[tuple[LedgerEntryDecimalRule, ...]] = (
    # A movement's amount is a magnitude: the ledger's writers refuse zero and take cents.
    LedgerEntryDecimalRule(rule="amount", decimals=CENT_FRACTION_DIGITS, zero=False),
    LedgerEntryDecimalRule(rule="tax_amount", decimals=CENT_FRACTION_DIGITS, zero=True),
    # An invoice line refuses a zero quantity and takes a unit price of zero.
    LedgerEntryDecimalRule(rule="quantity", decimals=_INVOICE_LINE_ENTRY_DECIMALS, zero=False),
    LedgerEntryDecimalRule(rule="unit_price", decimals=_INVOICE_LINE_ENTRY_DECIMALS, zero=True),
)

# The scale a document's rate is read and corrected on: a reading and an evidence record keep points.
_DOCUMENT_PERCENT_FIELDS: Final[tuple[LedgerEntryPercentField, ...]] = (
    LedgerEntryPercentField(field="iva_rate", unit="points"),
    LedgerEntryPercentField(field="retention_rate", unit="points"),
)

# Where a limit is a request's own bound it is named by the module that owns the request; a reason or
# an operator's note is bound by what a bucket event payload value takes, since it is recorded there.
_TEXT_LIMITS: Final[tuple[LedgerEntryTextLimit, ...]] = (
    LedgerEntryTextLimit(name="split_parts", max=LEDGER_SPLIT_CHILDREN_MAX),
    LedgerEntryTextLimit(name="split_part_description", max=LEDGER_SPLIT_PART_DESCRIPTION_MAX),
    LedgerEntryTextLimit(name="entry_text", max=LEDGER_UPDATE_TEXT_MAX),
    LedgerEntryTextLimit(name="group_label", max=LEDGER_GROUP_LABEL_MAX),
    LedgerEntryTextLimit(name="classify_token", max=LEDGER_CLASSIFY_SHORT_TEXT_MAX),
    LedgerEntryTextLimit(name="usage_ratio_id", max=LEDGER_ALLOCATE_RATIO_ID_MAX),
    LedgerEntryTextLimit(name="event_payload_value", max=BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH),
    LedgerEntryTextLimit(name="evidence_label", max=LEDGER_EVIDENCE_LABEL_MAX),
    LedgerEntryTextLimit(name="evidence_note", max=LEDGER_EVIDENCE_TEXT_MAX),
    LedgerEntryTextLimit(name="own_account_iban", max=LEDGER_OWN_ACCOUNT_IBAN_MAX),
    LedgerEntryTextLimit(name="own_account_swift_bic", max=LEDGER_OWN_ACCOUNT_SWIFT_BIC_MAX),
    LedgerEntryTextLimit(name="counterparty_tax_id", max=LEDGER_COUNTERPARTY_TAX_ID_MAX),
    LedgerEntryTextLimit(name="counterparty_note", max=LEDGER_COUNTERPARTY_NOTE_MAX),
)


def ledger_entry_limits() -> LedgerEntryLimitsProjection:
    """Answer the limits from the constants their owners hold."""
    return LedgerEntryLimitsProjection(
        decimal_text_max=DECIMAL_TEXT_MAX_LENGTH,
        two_way_decimal=AMBIGUOUS_THOUSANDS_PATTERN,
        decimal_rules=_DECIMAL_RULES,
        percent_decimals=PERCENTAGE_ENTRY_DECIMALS,
        percent_points_max=canonical_decimal_string(PERCENTAGE_MAX),
        percent_fraction_max=canonical_decimal_string(UNIT_PROPORTION_MAX),
        percent_bare_fraction_ceiling=canonical_decimal_string(PERCENTAGE_BARE_FRACTION_CEILING),
        document_percent_fields=_DOCUMENT_PERCENT_FIELDS,
        rule_pattern_max=RULE_PATTERN_ENTRY_MAX_LENGTH,
        text_limits=_TEXT_LIMITS,
    )


__all__ = [
    "LedgerEntryDecimalRule",
    "LedgerEntryLimitsProjection",
    "LedgerEntryPercentField",
    "LedgerEntryTextLimit",
    "ledger_entry_limits",
]
