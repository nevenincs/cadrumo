"""OFX financial provider backed by ``ofxtools``.

Provides :class:`OfxProvider`, an
:class:`~adapters.inbound.financial.providers.FinancialProvider`
implementation that wraps ``ofxtools`` to ingest every statement block
exposed by an OFX or QFX file. The ``_OfxAccountLike``,
``_OfxStatementLike`` and ``_OfxTransactionLike`` Protocol surfaces let the
adapter type-check against the spec-validated aggregates ``ofxtools``
returns without coupling to the library's descriptor-driven model classes.

``ofxtools`` is a strict, OFX-spec-conformant parser: it validates the
header, the ``SIGNON`` block, and every required statement element (a
``BANKTRANLIST`` carries ``DTSTART`` / ``DTEND``, an ``STMTRS`` carries a
``LEDGERBAL``) at conversion time, raising on a malformed document rather
than silently degrading. Real bank exports are spec-conformant, so the
strictness is a correctness gain over the previous permissive parser.

Each OFX transaction is projected into a
:class:`~adapters.inbound.financial.providers.ParsedLedgerRow`; the signed
``TRNAMT`` value determines
:class:`~domain.transactions.TransactionDirection` and the stored raw
transaction keeps the absolute magnitude plus OFX-native raw fields.

``ofxtools`` is GPL-3.0-only and therefore capability-gated behind the
``ofx`` optional extra: the import is lazy, guarded by
:func:`~core.require_optional_extra`, so a bare-core install keeps the rest
of the ledger import surface and refuses OFX sources with the extra's typed
machine identity rather than a rendered installation command.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol, override, runtime_checkable

from .....core.decimal.grammar import DecimalSeparator
from .....core.errors.hierarchy import CoreValidationError
from .....core.logging import get_logger
from .....core.optional_extras import (
    OFX_EXTRA,
    MissingOptionalExtraError,
    optional_extra_available,
    require_optional_extra,
)
from .....core.parsing import normalise_iso_4217_currency
from .....domain.transactions.raw_transaction import SourceFormat
from ._constants import OFX_EXTENSIONS
from .base import (
    FinancialProvider,
    FinancialValidationError,
    InvalidFinancialSourceError,
    ParsedLedgerRow,
    ProviderValidation,
    build_raw_transaction,
    default_currency,
    parse_amount_value,
    parse_date_value,
    synthesize_transaction_id,
)

_logger = get_logger(__name__)
_INPUT_OFX_SOURCE_LABEL = "<input-ofx>"


def _looks_like_ofx(path: Path) -> bool:
    """Return whether ``path`` plausibly is an OFX/QFX document, without ``ofxtools``.

    A cheap suffix + header sniff (the same markers the detection registry
    uses) so the missing-extra refusal fires only for sources the operator
    actually meant as OFX, while non-OFX probe candidates degrade to a miss.
    """
    if path.suffix.lower() in OFX_EXTENSIONS:
        return True
    try:
        head = path.read_bytes()[:256].upper()
    except OSError:
        return False
    return b"OFXHEADER" in head or b"<OFX>" in head or b"<BANKTRANLIST>" in head


class _OfxAccountLike(Protocol):
    """Minimal OFX account surface (``BANKACCTFROM`` / ``CCACCTFROM``)."""

    acctid: object


class _OfxTransactionLike(Protocol):
    """Minimal OFX transaction surface (``STMTTRN``) used by the provider."""

    trntype: object
    dtposted: object
    trnamt: object
    fitid: object
    name: object
    memo: object


@runtime_checkable
class _OfxStatementLike(Protocol):
    """Minimal OFX statement surface (``STMTRS`` / ``CCSTMTRS``)."""

    curdef: object
    #: Absent on statement kinds that carry no account block.
    account: _OfxAccountLike | None
    transactions: Iterable[_OfxTransactionLike]


@dataclass(frozen=True, slots=True)
class _ParsedOfxRow:
    """One OFX transaction's parsed fields, ready to project to a raw transaction."""

    transaction_id: str
    counterparty: str | None
    memo: str
    trntype: str
    description: str
    posted_at: object
    amount: Decimal
    booked_date: date


def _normalise_text_value(value: object, *, default: str = "") -> str:
    """Return a stripped text value, or ``default`` for absent/non-text data."""
    if not isinstance(value, str):
        return default
    return value.strip() or default


def _resolve_statement_context(statement: _OfxStatementLike) -> tuple[str, str]:
    """Return the ``(currency, account_id)`` context for one OFX statement block.

    The statement's ``CURDEF`` is validated against the same ISO 4217 shape
    policy the CSV column and the persisted
    :class:`~domain.transactions.RawTransaction` use
    (:func:`~core.parsing.normalise_iso_4217_currency`). A malformed
    ``CURDEF`` is refused here, naming the statement, rather than being passed
    through to fail later as an opaque model validation error.

    Raises:
        InvalidFinancialSourceError: ``CURDEF`` is not a three-letter ISO 4217
            code.
    """
    raw_currency = getattr(statement, "curdef", None) or default_currency()
    try:
        currency = normalise_iso_4217_currency(raw_currency)
    except CoreValidationError as exc:
        raise InvalidFinancialSourceError(
            f"OFX statement CURDEF must be a three-letter ISO 4217 code; got {raw_currency!r}",
        ) from exc
    account = statement.account
    account_id = _normalise_text_value(
        getattr(account, "acctid", None) if account is not None else None,
        default="account",
    )
    return currency, account_id


def _stripped_attr(source: object, attr: str) -> str:
    """Return ``source.attr`` coerced to a stripped string (empty when absent/None)."""
    return _normalise_text_value(getattr(source, attr, None))


class OfxProvider(FinancialProvider):
    """Ingest raw transactions from OFX and QFX files.

    Multi-statement OFX files emit transactions from every statement
    block; the provider names the account in the synthetic
    transaction id and copies the OFX-native fields
    (``ACCTID``, ``TRNTYPE``, ``DTPOSTED``, ``TRNAMT``, ``FITID``,
    ``NAME``, ``MEMO``) into ``raw_fields`` for downstream auditing.
    The provider remains format-level: application ledger import owns
    persistence and bucket events.
    """

    name = "OFX provider"
    supported_extensions = OFX_EXTENSIONS
    source_format = SourceFormat.OFX
    # Corpus fixture is a synthetic OFX generated from the standard OFX 1.x spec;
    # the format is self-describing so structural fidelity is confirmed by parsing.
    verification_source = "synthetic_from_bank_published_text"
    provisional_pending_specimen = False

    @override
    def validate_source(self, path: Path) -> ProviderValidation:
        """Validate that the OFX file can be parsed and carries at least one transaction.

        Without the ``ofx`` optional extra installed this degrades along the
        detection contract: a source that does not look like OFX is reported
        as a plain probe miss carrying the extra's machine identity (so
        ``--provider auto`` detection of other formats keeps working), while a
        source that clearly IS OFX raises the typed
        :class:`~core.MissingOptionalExtraError` — never a silent
        "no provider matched". Neither branch renders an installation command;
        the recovery is resolved downstream from the extra's typed identity.

        Returns:
            A :class:`ProviderValidation` with the validation outcome.

        Raises:
            MissingOptionalExtraError: If the source looks like an OFX/QFX
                document but the ``ofx`` extra is not installed.
        """
        if not optional_extra_available(OFX_EXTRA):
            if _looks_like_ofx(path):
                raise MissingOptionalExtraError(OFX_EXTRA)
            return ProviderValidation(
                is_valid=False,
                unavailable_optional_extra={
                    "extra": OFX_EXTRA.extra,
                    "import_name": OFX_EXTRA.import_name,
                    "importable": False,
                },
            )
        try:
            statements = self._load_statements(path)
            source_sha256 = self._compute_sha256(self._read_source_bytes(path))
            transaction_count = 0
            for statement in statements:
                _, account_id = _resolve_statement_context(statement)
                for transaction in statement.transactions:
                    transaction_count += 1
                    self._parse_ofx_row(
                        transaction,
                        account_id=account_id,
                        source_sha256=source_sha256,
                        source_row_index=transaction_count,
                    )
        except InvalidFinancialSourceError as exc:
            return ProviderValidation(is_valid=False, warnings=(str(exc),))
        if transaction_count == 0:
            return ProviderValidation(
                is_valid=False,
                warnings=("OFX statement contains no transactions",),
            )
        return ProviderValidation(
            is_valid=True,
            warnings=(),
            detected_encoding="ofxtools",
            detected_dialect=f"account_count={len(statements)}",
        )

    @override
    def ingest(self, path: Path) -> Iterator[ParsedLedgerRow]:
        """Yield :class:`ParsedLedgerRow` records (magnitude + direction) from every OFX statement."""
        _logger.debug("ofx_provider ingest: loading source=<input-ofx>")
        source_bytes = self._read_source_bytes(path)
        source_sha256 = self._compute_sha256(source_bytes)
        source_row_index = 0
        for statement in self._load_statements(path):
            currency, account_id = _resolve_statement_context(statement)
            for transaction in statement.transactions:
                source_row_index += 1
                parsed = self._parse_ofx_row(
                    transaction,
                    account_id=account_id,
                    source_sha256=source_sha256,
                    source_row_index=source_row_index,
                )
                raw_fields = {
                    "ACCTID": str(account_id),
                    "TRNTYPE": parsed.trntype,
                    "DTPOSTED": parsed.posted_at.isoformat() if isinstance(parsed.posted_at, datetime) else "",
                    "TRNAMT": str(getattr(transaction, "trnamt", "")),
                    "FITID": getattr(transaction, "fitid", None) or "",
                    "NAME": parsed.counterparty or "",
                    "MEMO": parsed.memo,
                }
                yield build_raw_transaction(
                    provider=self,
                    path=path,
                    source_sha256=source_sha256,
                    source_row_index=source_row_index,
                    provider_transaction_id=parsed.transaction_id,
                    booked_date=parsed.booked_date,
                    value_date=None,
                    amount=parsed.amount,
                    currency=currency,
                    counterparty=parsed.counterparty,
                    description=parsed.description,
                    raw_fields=raw_fields,
                )

    def _parse_ofx_row(
        self,
        transaction: _OfxTransactionLike,
        *,
        account_id: str,
        source_sha256: str,
        source_row_index: int,
    ) -> _ParsedOfxRow:
        """Parse one OFX transaction into typed fields, refusing a malformed row.

        Raises:
            InvalidFinancialSourceError: When the transaction cannot be parsed.
        """
        try:
            transaction_id = _stripped_attr(transaction, "fitid")
            if not transaction_id:
                transaction_id = synthesize_transaction_id(
                    provider_name=f"{self.name}-{account_id}",
                    source_sha256=source_sha256,
                    source_row_index=source_row_index,
                )
            counterparty = _stripped_attr(transaction, "name") or None
            memo = _stripped_attr(transaction, "memo")
            trntype = _stripped_attr(transaction, "trntype").upper()
            description = memo or counterparty or trntype or "OFX transaction"
            posted_at = getattr(transaction, "dtposted", None)
            raw_amount = getattr(transaction, "trnamt", None)
            amount = parse_amount_value(str(raw_amount), decimal_separator=DecimalSeparator.PERIOD)
            booked_date = parse_date_value(posted_at, day_first=False)
        except (ValueError, FinancialValidationError) as exc:
            _logger.warning(
                "ofx_provider: parse error transaction=%d source=<input-ofx>",
                source_row_index,
                exc_info=True,
            )
            raise InvalidFinancialSourceError(
                f"OFX transaction {source_row_index} could not be parsed: {exc}",
            ) from exc
        return _ParsedOfxRow(
            transaction_id=transaction_id,
            counterparty=counterparty,
            memo=memo,
            trntype=trntype,
            description=description,
            posted_at=posted_at,
            amount=amount,
            booked_date=booked_date,
        )

    def _load_statements(self, path: Path) -> tuple[_OfxStatementLike, ...]:
        """Parse and spec-validate every statement block exposed by an OFX file.

        Raises:
            MissingOptionalExtraError: If the ``ofx`` extra is not installed.
        """
        require_optional_extra(OFX_EXTRA)
        from ofxtools.Parser import OFXTree

        tree = OFXTree()
        try:
            with path.open("rb") as handle:
                tree.parse(handle)
            parsed = tree.convert()
        # BROAD-EXCEPT-RATIONALE-OFX-PARSE: ofxtools surfaces several
        # unrelated failure types from its header parser and spec-validation
        # layer (OFXHeaderError, OFXSpecError, ParseError, ValueError) with no
        # single shared base. A broad catch guarantees conversion of every
        # parse miss to the typed InvalidFinancialSourceError below.
        except Exception as exc:
            # Debug, not error: this is reached during the ``--provider auto``
            # detection probe loop for every non-OFX (or unreadable) input,
            # where a parse miss is the expected, non-fatal signal that this
            # provider does not match. The failure is converted to an
            # InvalidFinancialSourceError that detection treats as a miss; the
            # operator-facing refusal is raised once by the caller. exc_info is
            # dropped so a probe miss never dumps a traceback to the operator.
            _logger.debug(
                "ofx_provider: failed to parse OFX file <input-ofx>: %s",
                type(exc).__name__,
            )
            raise InvalidFinancialSourceError(f"could not parse OFX file: {_INPUT_OFX_SOURCE_LABEL}") from exc
        statements = list(getattr(parsed, "statements", None) or [])
        if not statements:
            raise InvalidFinancialSourceError("OFX file does not contain a bank account statement")
        typed_statements: list[_OfxStatementLike] = []
        for statement in statements:
            if not isinstance(statement, _OfxStatementLike):
                raise InvalidFinancialSourceError(
                    f"OFX statement object is missing expected attributes: {type(statement).__name__}",
                )
            typed_statements.append(statement)
        return tuple(typed_statements)
