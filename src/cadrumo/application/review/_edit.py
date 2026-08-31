"""Typed ``--set KEY=VALUE`` parser for record-edit commands.

The CLI exposes ``--set KEY=VALUE`` on ledger / invoice review-edit
commands. The canonical grammar:

- ledger:      ``--set category=software``, ``--set business.share=1.0``,
  ``--set reference=invoice-1``, ``--set comments=…``,
  ``--set document.path=…``
- invoice:     ``--set base=120.00``, ``--set iva.rate=21``,
  ``--set iva.amount=25.20``, ``--set iva.category=…``,
  ``--set retention.rate=15``, ``--set retention.amount=18.00``,
  ``--set payment.id=row_…``, ``--set reference=…``,
  ``--set comments=…``, ``--set document.path=…``

The CLI argv layer parses the raw strings; this module turns them
into typed :class:`EditClause` records and binds them to per-scope
:class:`LedgerEditSpec` / :class:`InvoiceEditSpec` records. Each spec
validates its closed
key catalogue, coerces each value to its typed shape (``Decimal``,
``Path``, free text, foreign-key id), and exposes typed accessors the
orchestration layer reads instead of re-parsing strings at every
edit-application call site.

The orchestration that applies an ``EditSpec`` to a stored
:class:`cadrumo.domain.transactions.Transaction` /
:class:`cadrumo.domain.invoices.Invoice` /
:class:`cadrumo.domain.filing.ModeloDraft` lives in the
``application/workflow`` state overlay.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.decimal.coercion import coerce_decimal
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...domain.invoices.enums import numeric_iva_rate_percentages
from .errors import EditParseError

_DECIMAL_RE = re.compile(r"^-?\d+(\.\d+)?$")
"""Reject malformed decimals before constructor; ruff-friendly fast path."""

__all__ = (
    "EditClause",
    "EditParseError",
    "InvoiceEditKey",
    "InvoiceEditSpec",
    "LedgerEditKey",
    "LedgerEditSpec",
    "parse_edit_clause",
    "parse_edit_clauses",
)


class EditClause(BaseModel):
    """One typed ``KEY=VALUE`` clause from a ``--set`` flag.

    The ``raw_value`` is the trimmed string before per-key coercion;
    typed coercion happens on the owning scope's spec.

    Attributes:
        key: Lowercase, dotted-or-flat identifier.
        raw_value: Trimmed value string.
    """

    model_config = _STRICT_FROZEN

    key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_.]*$")
    raw_value: str = Field(min_length=1, max_length=512)

    @field_validator("raw_value")
    @classmethod
    def _trim_value(cls, value: str) -> str:
        """Trim the value while rejecting blank-but-not-empty inputs."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("edit value must not be blank")
        return trimmed


def parse_edit_clause(raw: str) -> EditClause:
    """Parse one raw ``KEY=VALUE`` string into an :class:`EditClause`.

    Args:
        raw: The raw ``KEY=VALUE`` token supplied by the operator.

    Returns:
        A validated :class:`EditClause` with the parsed key and value.

    Raises:
        EditParseError: When the token is missing ``=``, has an empty
            key, or has an empty value.
    """
    if "=" not in raw:
        raise EditParseError(raw, reason="missing-equals")
    key_raw, _, value_raw = raw.partition("=")
    key = key_raw.strip().lower()
    value = value_raw.strip()
    if not key:
        raise EditParseError(raw, reason="empty-key")
    if not value:
        raise EditParseError(raw, reason="empty-value")
    try:
        return EditClause(key=key, raw_value=value)
    except ValueError as exc:
        raise EditParseError(raw, reason="invalid-value") from exc


def parse_edit_clauses(raw: Iterable[str]) -> tuple[EditClause, ...]:
    """Parse a sequence of ``--set`` strings into :class:`EditClause` records, preserving input order."""
    return tuple(parse_edit_clause(item) for item in raw)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _coerce_decimal(clause: EditClause, *, scope: str) -> Decimal:
    """Coerce a clause value into :class:`Decimal` or raise EditParseError."""
    if not _DECIMAL_RE.fullmatch(clause.raw_value):
        raise EditParseError(
            f"--set {clause.key}={clause.raw_value}",
            reason=f"invalid-value-{scope}",
        )
    result = coerce_decimal(clause.raw_value)
    if result is None:
        raise EditParseError(
            f"--set {clause.key}={clause.raw_value}",
            reason=f"invalid-value-{scope}",
        )
    return result


def _coerce_invoice_amount(clause: EditClause, *, scope: str) -> Decimal:
    """Parse an invoice MONEY amount under the euro-cent contract used at creation.

    Every magnitude goes through the canonical grammar rather than
    :func:`_coerce_decimal`, because the tolerant helper RESOLVES the ambiguous
    Spanish thousands shape instead of refusing it: ``coerce_decimal("1.000")``
    answers one euro where the operator may have meant one thousand. That is not
    hypothetical here -- ``core.decimal.grammar`` records an operator's
    ``12.500`` euros being read as twelve fifty on a threshold field by exactly
    this route, which is why the ambiguity check was moved into the canonical
    parser.

    Rates deliberately keep the tolerant helper. A trailing zero cannot misread
    a rate, since ``12.500`` and ``12.5`` are the same percentage; on a
    magnitude the same text is a thousandfold error. The split is by what the
    value MEANS, not by which helper was nearest.
    """
    result = try_parse_canonical_decimal(clause.raw_value, max_fraction_digits=2)
    if result is None:
        raise EditParseError(
            f"--set {clause.key}={clause.raw_value}",
            reason=f"invalid-value-{scope}",
        )
    return result


def _coerce_invoice_taxable_base(clause: EditClause) -> Decimal:
    """Parse the invoice taxable base with the same euro-cent contract as creation."""
    return _coerce_invoice_amount(clause, scope="invoice-base")


_INVOICE_IVA_RATE_ALLOWED: frozenset[Decimal] = numeric_iva_rate_percentages()
"""Closed set of integer-percentage IVA rates the CLI accepts on
``--set iva.rate``.  Derived structurally from
:func:`cadrumo.domain.invoices.numeric_iva_rate_percentages` so it tracks
:class:`cadrumo.domain.invoices.IvaRate` membership (``RATE_0`` / ``RATE_4``
/ ``RATE_10`` / ``RATE_21``) without re-listing literals here.  The
underlying substrate at :func:`cadrumo.domain.iva.lookup_rate` is the
authority for the fractional percentages those slots resolve to at a date.

Rejecting non-canonical values at parse time keeps free-form Decimal IVA
rates from flowing through the edit spec into ledger records."""


def _coerce_invoice_iva_rate(clause: EditClause) -> Decimal:
    """Coerce ``--set iva.rate`` to a substrate-known IVA percentage.

    The CLI uses integer percentages (``21`` / ``10`` / ``4`` / ``0``);
    the spec stores them as a :class:`Decimal` so downstream review-state
    code can compare against ``Decimal("21")`` etc. Rejects any
    non-canonical value to anchor the review-edit boundary on the
    closed substrate slot taxonomy.
    """
    value = _coerce_decimal(clause, scope="invoice-iva-rate")
    if value not in _INVOICE_IVA_RATE_ALLOWED:
        raise EditParseError(
            f"--set {clause.key}={clause.raw_value}",
            reason="unsupported-iva-rate",
        )
    return value


def _coerce_invoice_retention_rate(clause: EditClause) -> Decimal:
    """Coerce ``--set retention.rate`` and bound it to ``[0, 100]``.

    IRPF retention rates are not yet centralised in a substrate; the
    edit spec restricts the value to the legal percentage envelope
    (``0`` through ``100`` inclusive) so review-state writes cannot
    introduce nonsense values into ledger records. Tightens the V-3
    boundary on the retention axis without committing to a closed
    rate enum that the substrate does not yet expose.
    """
    value = _coerce_decimal(clause, scope="invoice-retention-rate")
    if value < Decimal("0") or value > Decimal("100"):
        raise EditParseError(
            f"--set {clause.key}={clause.raw_value}",
            reason="retention-rate-out-of-range",
        )
    return value


def _coerce_share(clause: EditClause, *, scope: str) -> Decimal:
    """Coerce a clause value into a share Decimal in the inclusive 0..1 range."""
    value = _coerce_decimal(clause, scope=scope)
    if value < Decimal("0") or value > Decimal("1"):
        raise EditParseError(
            f"--set {clause.key}={clause.raw_value}",
            reason=f"invalid-value-{scope}",
        )
    return value


def _coerce_path(clause: EditClause) -> Path:
    """Coerce a clause value into :class:`pathlib.Path`.

    The parser does not check filesystem existence — the consuming
    use-case is responsible. Empty / blank values were rejected by
    :func:`parse_edit_clause` already.
    """
    return Path(clause.raw_value)


def _ensure_unique_keys(
    clauses: tuple[EditClause, ...],
    *,
    scope: str,
) -> None:
    """Reject ``--set`` specs that carry the same key twice."""
    seen: set[str] = set()
    for clause in clauses:
        if clause.key in seen:
            raise EditParseError(
                f"--set {clause.key}={clause.raw_value}",
                reason=f"duplicate-key-{scope}",
            )
        seen.add(clause.key)


def _ensure_known_keys(
    clauses: tuple[EditClause, ...],
    *,
    scope: str,
    allowed: set[str],
) -> None:
    """Reject keys outside the per-scope catalogue."""
    for clause in clauses:
        if clause.key not in allowed:
            raise EditParseError(
                f"--set {clause.key}={clause.raw_value}",
                reason=f"unknown-key-{scope}",
            )


# ---------------------------------------------------------------------
# Per-scope key catalogues
# ---------------------------------------------------------------------


class LedgerEditKey(StrEnum):
    """Closed catalogue of ``aeat app ledger update --set`` keys.

    Attributes:
        CATEGORY: Spending / income category foreign-key id.
        BUSINESS_SHARE: Decimal share in ``[0, 1]`` of the row that is
            business-related (mixed-use accounting).
        REFERENCE: Free-text user reference (invoice number, ticket
            id, contract id).
        COMMENTS: Free-text operator note.
        DOCUMENT_PATH: Filesystem path to a supporting document.
    """

    CATEGORY = "category"
    TREATMENT = "treatment"
    BUSINESS_SHARE = "business.share"
    REFERENCE = "reference"
    COMMENTS = "comments"
    DOCUMENT_PATH = "document.path"


class InvoiceEditKey(StrEnum):
    """Closed catalogue of invoice-evidence edit keys.

    Attributes:
        BASE: Decimal taxable base amount.
        IVA_RATE: Decimal IVA percentage (``21`` / ``10`` / ``4`` /
            ``0`` are the supported rates; the parser accepts any
            non-negative decimal so the grammar is not tied to a fixed
            rate table).
        IVA_AMOUNT: Decimal IVA amount.
        IVA_CATEGORY: Free-text IVA category.
        RETENTION_RATE: Decimal IRPF retention percentage.
        RETENTION_AMOUNT: Decimal IRPF retention amount.
        PAYMENT_ID: Foreign-key transaction id linked as the payment.
        REFERENCE: Free-text invoice reference.
        COMMENTS: Free-text operator note.
        DOCUMENT_PATH: Filesystem path to the invoice file.
    """

    BASE = "base"
    IVA_RATE = "iva.rate"
    IVA_AMOUNT = "iva.amount"
    IVA_CATEGORY = "iva.category"
    RETENTION_RATE = "retention.rate"
    RETENTION_AMOUNT = "retention.amount"
    PAYMENT_ID = "payment.id"
    REFERENCE = "reference"
    COMMENTS = "comments"
    DOCUMENT_PATH = "document.path"


# ---------------------------------------------------------------------
# Spec records
# ---------------------------------------------------------------------


class LedgerEditSpec(BaseModel):
    """Typed ``aeat app ledger update --set`` spec.

    Attributes:
        clauses: Raw clauses in input order.
        category: Resolved spending / income category id.
        business_share: Resolved business share (0..1).
        reference: Resolved free-text reference.
        comments: Resolved free-text comments.
        document_path: Resolved supporting-document path.
    """

    model_config = _STRICT_FROZEN

    clauses: tuple[EditClause, ...] = ()
    category: str | None = None
    business_share: Decimal | None = None
    reference: str | None = None
    comments: str | None = None
    document_path: Path | None = None

    @classmethod
    def from_strings(cls, raw: Iterable[str]) -> LedgerEditSpec:
        """Parse ``--set`` arguments into a typed ledger spec.

        Returns a :class:`LedgerEditSpec` with fields populated from the
        parsed ``key=value`` clause strings.
        """
        clauses = parse_edit_clauses(raw)
        valid = {member.value for member in LedgerEditKey}
        _ensure_known_keys(clauses, scope="ledger", allowed=valid)
        _ensure_unique_keys(clauses, scope="ledger")
        category: str | None = None
        business_share: Decimal | None = None
        reference: str | None = None
        comments: str | None = None
        document_path: Path | None = None
        for clause in clauses:
            if clause.key in {LedgerEditKey.CATEGORY, LedgerEditKey.TREATMENT}:
                category = clause.raw_value
            elif clause.key == LedgerEditKey.BUSINESS_SHARE:
                business_share = _coerce_share(clause, scope="ledger-business-share")
            elif clause.key == LedgerEditKey.REFERENCE:
                reference = clause.raw_value
            elif clause.key == LedgerEditKey.COMMENTS:
                comments = clause.raw_value
            elif clause.key == LedgerEditKey.DOCUMENT_PATH:
                document_path = _coerce_path(clause)
        return cls(
            clauses=clauses,
            category=category,
            business_share=business_share,
            reference=reference,
            comments=comments,
            document_path=document_path,
        )

    @model_validator(mode="after")
    def _enforce_clause_consistency(self) -> LedgerEditSpec:
        """Resolved fields must agree with the clauses tuple."""
        present = {clause.key for clause in self.clauses}
        if (LedgerEditKey.CATEGORY in present or LedgerEditKey.TREATMENT in present) != (self.category is not None):
            raise ValueError("clauses[category] / category field disagree")
        if (LedgerEditKey.BUSINESS_SHARE in present) != (self.business_share is not None):
            raise ValueError("clauses[business.share] / business_share field disagree")
        if (LedgerEditKey.REFERENCE in present) != (self.reference is not None):
            raise ValueError("clauses[reference] / reference field disagree")
        if (LedgerEditKey.COMMENTS in present) != (self.comments is not None):
            raise ValueError("clauses[comments] / comments field disagree")
        if (LedgerEditKey.DOCUMENT_PATH in present) != (self.document_path is not None):
            raise ValueError("clauses[document.path] / document_path field disagree")
        return self


class InvoiceEditSpec(BaseModel):
    """Typed invoice-evidence edit spec.

    Attributes:
        clauses: Raw clauses in input order.
        base: Decimal taxable base.
        iva_rate: Decimal IVA percentage.
        iva_amount: Decimal IVA amount.
        iva_category: Free-text IVA category.
        retention_rate: Decimal IRPF retention percentage.
        retention_amount: Decimal IRPF retention amount.
        payment_id: Foreign-key transaction id.
        reference: Free-text invoice reference.
        comments: Free-text operator note.
        document_path: Path to the invoice file.
    """

    model_config = _STRICT_FROZEN

    clauses: tuple[EditClause, ...] = ()
    base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    iva_category: str | None = None
    retention_rate: Decimal | None = None
    retention_amount: Decimal | None = None
    payment_id: str | None = None
    reference: str | None = None
    comments: str | None = None
    document_path: Path | None = None

    @classmethod
    def from_strings(cls, raw: Iterable[str]) -> InvoiceEditSpec:
        """Parse ``--set`` arguments into a typed :class:`InvoiceEditSpec`."""
        clauses = parse_edit_clauses(raw)
        valid = {member.value for member in InvoiceEditKey}
        _ensure_known_keys(clauses, scope="invoice", allowed=valid)
        _ensure_unique_keys(clauses, scope="invoice")
        base: Decimal | None = None
        iva_rate: Decimal | None = None
        iva_amount: Decimal | None = None
        iva_category: str | None = None
        retention_rate: Decimal | None = None
        retention_amount: Decimal | None = None
        payment_id: str | None = None
        reference: str | None = None
        comments: str | None = None
        document_path: Path | None = None
        for clause in clauses:
            if clause.key == InvoiceEditKey.BASE:
                base = _coerce_invoice_taxable_base(clause)
            elif clause.key == InvoiceEditKey.IVA_RATE:
                iva_rate = _coerce_invoice_iva_rate(clause)
            elif clause.key == InvoiceEditKey.IVA_AMOUNT:
                iva_amount = _coerce_invoice_amount(clause, scope="invoice-iva-amount")
            elif clause.key == InvoiceEditKey.IVA_CATEGORY:
                iva_category = clause.raw_value
            elif clause.key == InvoiceEditKey.RETENTION_RATE:
                retention_rate = _coerce_invoice_retention_rate(clause)
            elif clause.key == InvoiceEditKey.RETENTION_AMOUNT:
                retention_amount = _coerce_invoice_amount(clause, scope="invoice-retention-amount")
            elif clause.key == InvoiceEditKey.PAYMENT_ID:
                payment_id = clause.raw_value
            elif clause.key == InvoiceEditKey.REFERENCE:
                reference = clause.raw_value
            elif clause.key == InvoiceEditKey.COMMENTS:
                comments = clause.raw_value
            elif clause.key == InvoiceEditKey.DOCUMENT_PATH:
                document_path = _coerce_path(clause)
        return cls(
            clauses=clauses,
            base=base,
            iva_rate=iva_rate,
            iva_amount=iva_amount,
            iva_category=iva_category,
            retention_rate=retention_rate,
            retention_amount=retention_amount,
            payment_id=payment_id,
            reference=reference,
            comments=comments,
            document_path=document_path,
        )

    @model_validator(mode="after")
    def _enforce_clause_consistency(self) -> InvoiceEditSpec:
        """Resolved fields must agree with the clauses tuple."""
        present = {clause.key for clause in self.clauses}
        checks = (
            (InvoiceEditKey.BASE, self.base, "base"),
            (InvoiceEditKey.IVA_RATE, self.iva_rate, "iva.rate"),
            (InvoiceEditKey.IVA_AMOUNT, self.iva_amount, "iva.amount"),
            (InvoiceEditKey.IVA_CATEGORY, self.iva_category, "iva.category"),
            (InvoiceEditKey.RETENTION_RATE, self.retention_rate, "retention.rate"),
            (InvoiceEditKey.RETENTION_AMOUNT, self.retention_amount, "retention.amount"),
            (InvoiceEditKey.PAYMENT_ID, self.payment_id, "payment.id"),
            (InvoiceEditKey.REFERENCE, self.reference, "reference"),
            (InvoiceEditKey.COMMENTS, self.comments, "comments"),
            (InvoiceEditKey.DOCUMENT_PATH, self.document_path, "document.path"),
        )
        for key, value, label in checks:
            if (key in present) != (value is not None):
                raise ValueError(f"clauses[{label}] / {label} field disagree")
        return self


__all__ = [
    "EditClause",
    "EditParseError",
    "InvoiceEditKey",
    "InvoiceEditSpec",
    "LedgerEditKey",
    "LedgerEditSpec",
    "parse_edit_clause",
    "parse_edit_clauses",
]
