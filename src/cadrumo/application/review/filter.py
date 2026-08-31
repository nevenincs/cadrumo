"""Typed ``--filter KEY=VALUE`` parser for review commands.

The CLI routes every record-list command through ``--filter KEY=VALUE``
flags. Representative invocations:

- ``aeat app ledger review --filter status=pending --filter period=1T --filter year=2026``
- ``aeat app ledger review --filter issue=gap --filter period=1T --filter year=2026``
- ``aeat app ledger review --filter issue=duplicate --filter period=1T --filter year=2026``
- ``aeat app ledger review --filter import=import_003 --filter period=1T --filter year=2026``
- invoice evidence and modelo work-unit queue filters
- modelo status filters by period and modelo code

The CLI parses the raw argv strings; this module provides the typed
substrate that turns them into :class:`FilterClause` records and binds
them to per-scope :class:`LedgerReviewFilterSpec` /
:class:`InvoiceReviewFilterSpec` / :class:`DeclaracionReviewFilterSpec`
records. Each spec validates its own closed key catalogue, validates
each value against per-key rules (calendar period parsing, closed enum
values, identifier-shape checks), and exposes typed accessors the
orchestration layer reads instead of re-parsing strings at every
ReviewQueue / aggregator call site.

The specs are *parsing* surfaces; the actual filtering logic lives in
:class:`cadrumo.application.review.ReviewQueue` and the per-scope
adapters.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period, PeriodError
from ...domain.iva.classification import InvoiceKind
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ..transactions._diagnostics import LedgerImportDiagnosticKind
from .errors import FilterParseError

__all__ = (
    "DeclaracionReviewFilterKey",
    "DeclaracionReviewFilterSpec",
    "DeclaracionReviewStatus",
    "FilterClause",
    "InvoiceReviewFilterKey",
    "InvoiceReviewFilterSpec",
    "InvoiceReviewStatus",
    "LedgerReviewFilterKey",
    "LedgerReviewFilterSpec",
    "LedgerReviewStatus",
    "parse_filter_clause",
    "parse_filter_clauses",
)


class FilterClause(BaseModel):
    """One typed ``KEY=VALUE`` clause from a ``--filter`` flag.

    Attributes:
        key: Lowercase, dotted-or-flat identifier (``status``,
            ``period``, ``issue``, ``import``, ``kind``).
        value: Trimmed value string. Per-key validation lives on the
            owning :class:`LedgerReviewFilterSpec` /
            :class:`InvoiceReviewFilterSpec` /
            :class:`DeclaracionReviewFilterSpec`; this record is the
            generic substrate.
    """

    model_config = _STRICT_FROZEN

    key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_.]*$")
    value: str = Field(min_length=1, max_length=128)

    @field_validator("value")
    @classmethod
    def _trim_value(cls, value: str) -> str:
        """Trim the value while rejecting blank-but-not-empty inputs."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("filter value must not be blank")
        return trimmed


def parse_filter_clause(raw: str) -> FilterClause:
    """Parse one raw ``KEY=VALUE`` string into a :class:`FilterClause`.

    Args:
        raw: The raw ``KEY=VALUE`` token supplied by the operator.

    Returns:
        A validated :class:`FilterClause` with the parsed key and value.

    Raises:
        FilterParseError: When the token is missing ``=``, has an
            empty key, or has an empty value. The error carries the
            offending raw token verbatim.
    """
    if "=" not in raw:
        raise FilterParseError(raw, reason="missing-equals")
    key_raw, _, value_raw = raw.partition("=")
    key = key_raw.strip().lower()
    value = value_raw.strip()
    if not key:
        raise FilterParseError(raw, reason="empty-key")
    if not value:
        raise FilterParseError(raw, reason="empty-value")
    try:
        return FilterClause(key=key, value=value)
    except ValueError as exc:
        raise FilterParseError(raw, reason="invalid-value") from exc


def parse_filter_clauses(raw: Iterable[str]) -> tuple[FilterClause, ...]:
    """Parse a sequence of ``KEY=VALUE`` strings into typed :class:`FilterClause` instances.

    The order of input strings is preserved in the output tuple so the
    CLI can render a deterministic diagnostic.
    """
    return tuple(parse_filter_clause(item) for item in raw)


# ---------------------------------------------------------------------
# Per-scope key catalogues + value validators.
# ---------------------------------------------------------------------


class LedgerReviewFilterKey(StrEnum):
    """Closed catalogue of ``aeat app ledger review --filter`` keys.

    Attributes:
        STATUS: Lifecycle state of the row (``pending`` / ``reviewed``
            / ``skipped``).
        PERIOD: Filing period the row falls into, as a bare AEAT token:
            ``1T``..``4T`` (quarters), ``0A`` (annual), or ``01``..``12``
            (months). The filing year travels as a separate ``year=`` clause —
            there is no year-qualified combined token.
        YEAR: Filing year (``YYYY``) supplying the year context the bare
            ``period=`` token needs; required whenever ``period=`` is present.
        ISSUE: Filters to rows that carry an import-time diagnostic
            (``gap`` / ``duplicate`` / ``original-file`` / ``parser``).
        IMPORT: Filters to rows from a specific import-batch id.
        CLASSIFICATION: Filters to rows with a given business classification
            (``business`` / ``personal`` / ``mixed`` / ``not_yet_processed`` ...).
        DIRECTION: Filters to rows by money-flow direction — ``incoming``
            (ingreso), ``outgoing`` (gasto), or ``internal_transfer``.
    """

    STATUS = "status"
    PERIOD = "period"
    YEAR = "year"
    ISSUE = "issue"
    IMPORT = "import"
    CLASSIFICATION = "classification"
    TEXT = "text"
    DIRECTION = "direction"


class LedgerReviewStatus(StrEnum):
    """Closed catalogue of ledger ``status=`` filter values."""

    PENDING = "pending"
    REVIEWED = "reviewed"
    SKIPPED = "skipped"
    EXCLUDED = "excluded"


class InvoiceReviewFilterKey(StrEnum):
    """Closed catalogue of invoice-evidence review filter keys.

    Attributes:
        STATUS: Lifecycle state of the invoice (``pending`` /
            ``reviewed`` / ``matched``).
        KIND: Issued-vs-received discriminator. Values come from
            :class:`domain.iva.InvoiceKind`.
    """

    STATUS = "status"
    KIND = "kind"


class InvoiceReviewStatus(StrEnum):
    """Closed catalogue of invoice ``status=`` filter values."""

    PENDING = "pending"
    REVIEWED = "reviewed"
    MATCHED = "matched"
    PAID = "paid"


class DeclaracionReviewFilterKey(StrEnum):
    """Closed catalogue of modelo status filter keys.

    Attributes:
        STATUS: Lifecycle state of the draft (``pending`` /
            ``approved`` / ``stale`` / ``submitted`` /
            ``acknowledged``).
    """

    STATUS = "status"


class DeclaracionReviewStatus(StrEnum):
    """Closed catalogue of declaration ``status=`` filter values."""

    PENDING = "pending"
    APPROVED = "approved"
    STALE = "stale"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"


# ---------------------------------------------------------------------
# Spec records.
# ---------------------------------------------------------------------


def _ensure_unique_keys(
    clauses: tuple[FilterClause, ...],
    *,
    scope: str,
) -> None:
    """Reject filter specs that carry the same key twice.

    The CLI grammar surfaces one value per key; repeating a key would
    be ambiguous (intersection vs union). This helper enforces the
    one-clause-per-key invariant.
    """
    seen: set[str] = set()
    for clause in clauses:
        if clause.key in seen:
            raise FilterParseError(
                f"--filter {clause.key}={clause.value}",
                reason=f"duplicate-key-{scope}",
            )
        seen.add(clause.key)


def _ensure_known_keys(
    clauses: tuple[FilterClause, ...],
    *,
    scope: str,
    allowed: type[StrEnum],
) -> None:
    """Reject keys outside the per-scope catalogue."""
    valid = {member.value for member in allowed}
    for clause in clauses:
        if clause.key not in valid:
            raise FilterParseError(
                f"--filter {clause.key}={clause.value}",
                reason=f"unknown-key-{scope}",
            )


def _enum_value_or_raise[E: StrEnum](
    clause: FilterClause,
    enum_cls: type[E],
    *,
    scope: str,
    case_fold: bool = False,
) -> E:
    """Coerce a clause value to an enum member or raise FilterParseError.

    Args:
        clause: The parsed clause to coerce.
        enum_cls: The closed enum to validate against.
        scope: Stable scope tag carried in the raised error code so the
            CLI can surface a per-scope repair hint.
        case_fold: When ``True``, the match is case-insensitive — the
            clause value is compared against the enum members ignoring
            case, so an operator may type either case on the command
            line. Used for lowercase-valued enums
            (:class:`domain.iva.InvoiceKind`, ``issued`` /
            ``received``) and for uppercase-valued enums
            (:class:`cadrumo.domain.transactions.BusinessClassification`
            ``BUSINESS``, :class:`~cadrumo.domain.transactions.TransactionDirection`
            ``INCOMING``) so ``classification=business`` resolves the same
            as ``classification=BUSINESS``.

    Returns:
        The matching enum member.

    Raises:
        FilterParseError: When the clause value is not a valid member
            of ``enum_cls``.
    """
    if case_fold:
        by_folded = {member.value.casefold(): member for member in enum_cls}
        member = by_folded.get(clause.value.casefold())
        if member is None:
            raise FilterParseError(
                f"--filter {clause.key}={clause.value}",
                reason=f"invalid-value-{scope}",
            )
        return member
    valid = {member.value for member in enum_cls}
    if clause.value not in valid:
        raise FilterParseError(
            f"--filter {clause.key}={clause.value}",
            reason=f"invalid-value-{scope}",
        )
    return enum_cls(clause.value)


def _filter_year_or_raise(clause: FilterClause) -> int:
    """Coerce a ``year=YYYY`` filter clause value to an ``int`` or raise.

    Args:
        clause: The parsed ``year=`` clause.

    Returns:
        The four-digit filing year as an ``int``.

    Raises:
        FilterParseError: When the value is not a four-digit year.
    """
    text = clause.value.strip()
    if len(text) == 4 and text.isdigit():
        return int(text)
    raise FilterParseError(
        f"--filter {clause.key}={clause.value}",
        reason="invalid-value-ledger-year",
    )


class LedgerReviewFilterSpec(BaseModel):
    """Typed ``aeat app ledger review --filter`` spec.

    Attributes:
        clauses: The raw clauses, in input order. Empty when the
            command is invoked without ``--filter``.
        status: Resolved :class:`LedgerReviewStatus` if ``status=`` was
            provided.
        period: Resolved filing period when ``period=`` and ``year=`` were
            provided. The raw clauses remain available on :attr:`clauses`;
            consumers receive the core value object directly.
        issue: Resolved :class:`LedgerImportDiagnosticKind` if ``issue=`` was
            provided.
        import_id: Raw import-batch id if ``import=`` was provided.
            Identifier-shape validation lives on the
            :class:`cadrumo.application.transactions` import surface.
    """

    model_config = _STRICT_FROZEN

    clauses: tuple[FilterClause, ...] = ()
    status: LedgerReviewStatus | None = None
    period: Period | None = None
    issue: LedgerImportDiagnosticKind | None = None
    import_id: str | None = None
    classification: BusinessClassification | None = None
    text: str | None = None
    direction: TransactionDirection | None = None

    @classmethod
    def from_strings(cls, raw: Iterable[str]) -> LedgerReviewFilterSpec:
        """Parse ``--filter`` arguments into a typed :class:`LedgerReviewFilterSpec`."""
        clauses = parse_filter_clauses(raw)
        _ensure_known_keys(clauses, scope="ledger", allowed=LedgerReviewFilterKey)
        _ensure_unique_keys(clauses, scope="ledger")
        status: LedgerReviewStatus | None = None
        period_code: str | None = None
        filing_year: int | None = None
        issue: LedgerImportDiagnosticKind | None = None
        import_id: str | None = None
        classification: BusinessClassification | None = None
        text: str | None = None
        direction: TransactionDirection | None = None
        for clause in clauses:
            if clause.key == LedgerReviewFilterKey.STATUS:
                status = _enum_value_or_raise(
                    clause,
                    LedgerReviewStatus,
                    scope="ledger-status",
                )
            elif clause.key == LedgerReviewFilterKey.PERIOD:
                period_code = clause.value
            elif clause.key == LedgerReviewFilterKey.YEAR:
                filing_year = _filter_year_or_raise(clause)
            elif clause.key == LedgerReviewFilterKey.ISSUE:
                issue = _enum_value_or_raise(
                    clause,
                    LedgerImportDiagnosticKind,
                    scope="ledger-issue",
                )
            elif clause.key == LedgerReviewFilterKey.IMPORT:
                import_id = clause.value
            elif clause.key == LedgerReviewFilterKey.CLASSIFICATION:
                # case_fold so an operator may type the natural lowercase
                # (classification=business) as well as the enum-cased BUSINESS;
                # mirrors the invoice `kind` filter's case-folding.
                classification = _enum_value_or_raise(
                    clause,
                    BusinessClassification,
                    scope="ledger-classification",
                    case_fold=True,
                )
            elif clause.key == LedgerReviewFilterKey.TEXT:
                text = clause.value
            elif clause.key == LedgerReviewFilterKey.DIRECTION:
                # case_fold so direction=ingreso-equivalent lowercase (incoming /
                # outgoing / internal_transfer) resolves as well as the enum case.
                direction = _enum_value_or_raise(
                    clause,
                    TransactionDirection,
                    scope="ledger-direction",
                    case_fold=True,
                )
        period: Period | None = None
        if (period_code is not None) != (filing_year is not None):
            raise FilterParseError(
                "--filter period=/year=",
                reason="ledger-period-year-pairing",
            )
        if period_code is not None and filing_year is not None:
            try:
                period = Period.from_year_and_code(filing_year, period_code)
            except PeriodError as exc:
                raise FilterParseError(
                    f"--filter period={period_code}",
                    reason="invalid-value-ledger-period",
                ) from exc
            if not period.has_date_span():
                raise FilterParseError(
                    f"--filter period={period_code}",
                    reason="invalid-value-ledger-period",
                )
        return cls(
            clauses=clauses,
            status=status,
            period=period,
            issue=issue,
            import_id=import_id,
            classification=classification,
            text=text,
            direction=direction,
        )

    @model_validator(mode="after")
    def _enforce_clause_consistency(self) -> LedgerReviewFilterSpec:
        """Resolved fields must agree with the clauses tuple.

        The validator catches direct construction (skipping
        :meth:`from_strings`) that drops the typed fields out of sync
        with the raw clauses.
        """
        present_keys = {clause.key for clause in self.clauses}
        if (LedgerReviewFilterKey.STATUS in present_keys) != (self.status is not None):
            raise ValueError("clauses[status] / status field disagree")
        has_period_clause = LedgerReviewFilterKey.PERIOD in present_keys
        has_year_clause = LedgerReviewFilterKey.YEAR in present_keys
        if has_period_clause != has_year_clause:
            raise FilterParseError(
                "--filter period=/year=",
                reason="ledger-period-year-pairing",
            )
        if has_period_clause != (self.period is not None):
            raise ValueError("clauses[period] / period field disagree")
        if self.period is not None:
            clauses_by_key = {clause.key: clause for clause in self.clauses}
            period_clause = clauses_by_key[LedgerReviewFilterKey.PERIOD]
            year_clause = clauses_by_key[LedgerReviewFilterKey.YEAR]
            try:
                expected_period = Period.from_year_and_code(
                    _filter_year_or_raise(year_clause),
                    period_clause.value,
                )
            except (FilterParseError, PeriodError) as exc:
                raise ValueError("clauses[period/year] / period field disagree") from exc
            if expected_period != self.period:
                raise ValueError("clauses[period/year] / period field disagree")
        if (LedgerReviewFilterKey.ISSUE in present_keys) != (self.issue is not None):
            raise ValueError("clauses[issue] / issue field disagree")
        if (LedgerReviewFilterKey.IMPORT in present_keys) != (self.import_id is not None):
            raise ValueError("clauses[import] / import_id field disagree")
        if (LedgerReviewFilterKey.CLASSIFICATION in present_keys) != (self.classification is not None):
            raise ValueError("clauses[classification] / classification field disagree")
        if (LedgerReviewFilterKey.TEXT in present_keys) != (self.text is not None):
            raise ValueError("clauses[text] / text field disagree")
        if (LedgerReviewFilterKey.DIRECTION in present_keys) != (self.direction is not None):
            raise ValueError("clauses[direction] / direction field disagree")
        return self


class InvoiceReviewFilterSpec(BaseModel):
    """Typed invoice-evidence review filter spec.

    Attributes:
        clauses: Raw clauses in input order.
        status: Resolved :class:`InvoiceReviewStatus`.
        kind: Resolved :class:`domain.iva.InvoiceKind`
            (``issued`` / ``received``).
    """

    model_config = _STRICT_FROZEN

    clauses: tuple[FilterClause, ...] = ()
    status: InvoiceReviewStatus | None = None
    kind: InvoiceKind | None = None

    @classmethod
    def from_strings(cls, raw: Iterable[str]) -> InvoiceReviewFilterSpec:
        """Parse ``--filter`` arguments into a typed invoice spec.

        Returns an :class:`InvoiceReviewFilterSpec` with filter fields
        populated from the parsed ``key=value`` clause strings.
        """
        clauses = parse_filter_clauses(raw)
        _ensure_known_keys(clauses, scope="invoice", allowed=InvoiceReviewFilterKey)
        _ensure_unique_keys(clauses, scope="invoice")
        status: InvoiceReviewStatus | None = None
        kind: InvoiceKind | None = None
        for clause in clauses:
            if clause.key == InvoiceReviewFilterKey.STATUS:
                status = _enum_value_or_raise(
                    clause,
                    InvoiceReviewStatus,
                    scope="invoice-status",
                )
            elif clause.key == InvoiceReviewFilterKey.KIND:
                kind = _enum_value_or_raise(
                    clause,
                    InvoiceKind,
                    scope="invoice-kind",
                    case_fold=True,
                )
        return cls(clauses=clauses, status=status, kind=kind)

    @model_validator(mode="after")
    def _enforce_clause_consistency(self) -> InvoiceReviewFilterSpec:
        """Resolved fields must agree with the clauses tuple."""
        present_keys = {clause.key for clause in self.clauses}
        if (InvoiceReviewFilterKey.STATUS in present_keys) != (self.status is not None):
            raise ValueError("clauses[status] / status field disagree")
        if (InvoiceReviewFilterKey.KIND in present_keys) != (self.kind is not None):
            raise ValueError("clauses[kind] / kind field disagree")
        return self


class DeclaracionReviewFilterSpec(BaseModel):
    """Typed modelo status filter spec.

    Attributes:
        clauses: Raw clauses in input order.
        status: Resolved :class:`DeclaracionReviewStatus`.
    """

    model_config = _STRICT_FROZEN

    clauses: tuple[FilterClause, ...] = ()
    status: DeclaracionReviewStatus | None = None

    @classmethod
    def from_strings(cls, raw: Iterable[str]) -> DeclaracionReviewFilterSpec:
        """Parse ``--filter`` arguments into a typed :class:`DeclaracionReviewFilterSpec`."""
        clauses = parse_filter_clauses(raw)
        _ensure_known_keys(clauses, scope="declaration", allowed=DeclaracionReviewFilterKey)
        _ensure_unique_keys(clauses, scope="declaration")
        status: DeclaracionReviewStatus | None = None
        for clause in clauses:
            if clause.key == DeclaracionReviewFilterKey.STATUS:
                status = _enum_value_or_raise(
                    clause,
                    DeclaracionReviewStatus,
                    scope="declaration-status",
                )
        return cls(clauses=clauses, status=status)

    @model_validator(mode="after")
    def _enforce_clause_consistency(self) -> DeclaracionReviewFilterSpec:
        """Resolved fields must agree with the clauses tuple."""
        present_keys = {clause.key for clause in self.clauses}
        if (DeclaracionReviewFilterKey.STATUS in present_keys) != (self.status is not None):
            raise ValueError("clauses[status] / status field disagree")
        return self


__all__ = [
    "DeclaracionReviewFilterKey",
    "DeclaracionReviewFilterSpec",
    "DeclaracionReviewStatus",
    "FilterClause",
    "FilterParseError",
    "InvoiceReviewFilterKey",
    "InvoiceReviewFilterSpec",
    "InvoiceReviewStatus",
    "LedgerReviewFilterKey",
    "LedgerReviewFilterSpec",
    "LedgerReviewStatus",
    "parse_filter_clause",
    "parse_filter_clauses",
]
