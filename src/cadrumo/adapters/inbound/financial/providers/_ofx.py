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
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol, override, runtime_checkable

from ofxtools.Parser import OFXTree

from .....core.decimal import coerce_decimal
from .....core.logging import get_logger
from .....domain.transactions import SourceFormat
from ._base import (
    FinancialProvider,
    FinancialValidationError,
    InvalidFinancialSourceError,
    ParsedLedgerRow,
    ProviderValidation,
    build_raw_transaction,
    default_currency,
    parse_date_value,
    synthesize_transaction_id,
)

_logger = get_logger(__name__)
_INPUT_OFX_SOURCE_LABEL = "<input-ofx>"


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
    account: _OfxAccountLike
    transactions: Iterable[_OfxTransactionLike]


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
    supported_extensions = frozenset({".ofx", ".qfx"})
    source_format = SourceFormat.OFX
    # Corpus fixture is a synthetic OFX generated from the standard OFX 1.x spec;
    # the format is self-describing so structural fidelity is confirmed by parsing.
    verification_source = "synthetic_from_bank_published_text"
    provisional_pending_specimen = False

    @override
    def validate_source(self, path: Path) -> ProviderValidation:
        """Validate that the OFX file can be parsed and carries at least one transaction.

        Returns:
            A :class:`ProviderValidation` with the validation outcome.
        """
        try:
            statements = self._load_statements(path)
        except InvalidFinancialSourceError as exc:
            return ProviderValidation(is_valid=False, warnings=(str(exc),))
        transaction_count = sum(len(tuple(statement.transactions)) for statement in statements)
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
            currency = (getattr(statement, "curdef", None) or default_currency()).strip().upper()
            account = statement.account
            account_id = (getattr(account, "acctid", None) or "account") if account is not None else "account"
            for transaction in statement.transactions:
                source_row_index += 1
                try:
                    transaction_id = (getattr(transaction, "fitid", None) or "").strip()
                    if not transaction_id:
                        transaction_id = synthesize_transaction_id(
                            provider_name=f"{self.name}-{account_id}",
                            source_sha256=source_sha256,
                            source_row_index=source_row_index,
                        )
                    counterparty = (getattr(transaction, "name", None) or "").strip() or None
                    memo = (getattr(transaction, "memo", None) or "").strip()
                    trntype = (getattr(transaction, "trntype", None) or "").strip().upper()
                    description = memo or counterparty or trntype or "OFX transaction"
                    posted_at = getattr(transaction, "dtposted", None)
                    amount = coerce_decimal(getattr(transaction, "trnamt", None), default=Decimal("0")) or Decimal("0")
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
                raw_fields = {
                    "ACCTID": str(account_id),
                    "TRNTYPE": trntype,
                    "DTPOSTED": posted_at.isoformat() if isinstance(posted_at, datetime) else "",
                    "TRNAMT": str(getattr(transaction, "trnamt", "")),
                    "FITID": getattr(transaction, "fitid", None) or "",
                    "NAME": counterparty or "",
                    "MEMO": memo,
                }
                yield build_raw_transaction(
                    provider=self,
                    path=path,
                    source_sha256=source_sha256,
                    source_row_index=source_row_index,
                    provider_transaction_id=transaction_id,
                    booked_date=booked_date,
                    value_date=None,
                    amount=amount,
                    currency=currency,
                    counterparty=counterparty,
                    description=description,
                    raw_fields=raw_fields,
                )

    def _load_statements(self, path: Path) -> tuple[_OfxStatementLike, ...]:
        """Parse and spec-validate every statement block exposed by an OFX file."""
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
