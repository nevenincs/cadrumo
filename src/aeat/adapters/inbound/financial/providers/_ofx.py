"""OFX financial provider backed by ``ofxparse``.

Provides :class:`OfxProvider`, an
:class:`aeat.adapters.inbound.financial.providers._base.FinancialProvider`
implementation that wraps ``ofxparse`` to ingest every account and
statement block exposed by an OFX or QFX file. The
:class:`_OfxAccountLike`, :class:`_OfxStatementLike` and
:class:`_OfxTransactionLike` Protocol surfaces let the adapter type-
check against the duck-typed objects ``ofxparse`` returns without
introducing an extra dependency.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Protocol, override, runtime_checkable

from ofxparse import OfxParser

from .....core.decimal import coerce_decimal
from .....core.logging import get_logger
from .....domain.transactions import RawTransaction, SourceFormat
from ._base import (
    FinancialProvider,
    FinancialValidationError,
    InvalidFinancialSourceError,
    ProviderValidation,
    build_raw_transaction,
    default_currency,
    parse_date_value,
    synthesize_transaction_id,
)

_logger = get_logger(__name__)
_INPUT_OFX_SOURCE_LABEL = "<input-ofx>"


class _OfxTransactionLike(Protocol):
    """Minimal OFX transaction surface used by the provider."""

    date: object
    amount: object
    id: str | None
    payee: str | None
    memo: str | None
    type: str | None


@runtime_checkable
class _OfxStatementLike(Protocol):
    """Minimal OFX statement surface used by the provider."""

    transactions: list[_OfxTransactionLike]
    currency: str | None


@runtime_checkable
class _OfxAccountLike(Protocol):
    """Minimal OFX account surface used by the provider."""

    account_id: str | None
    number: str | None
    statement: _OfxStatementLike | None


class OfxProvider(FinancialProvider):
    """Ingest raw transactions from OFX and QFX files.

    Multi-account OFX files emit transactions from every statement
    block; the provider names the account in the synthetic
    transaction id and copies the OFX-native fields
    (``ACCTID``, ``TRNTYPE``, ``DTPOSTED``, ``TRNAMT``, ``FITID``,
    ``NAME``, ``MEMO``) into ``raw_fields`` for downstream auditing.
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
            accounts = self._load_accounts(path)
        except InvalidFinancialSourceError as exc:
            return ProviderValidation(is_valid=False, warnings=(str(exc),))
        statements = tuple(_iter_account_statements(accounts))
        transaction_count = sum(len(statement.transactions) for _, statement in statements)
        if transaction_count == 0:
            return ProviderValidation(
                is_valid=False,
                warnings=("OFX statement contains no transactions",),
            )
        return ProviderValidation(
            is_valid=True,
            warnings=(),
            detected_encoding="ofxparse",
            detected_dialect=f"account_count={len(statements)}",
        )

    @override
    def ingest(self, path: Path) -> Iterator[RawTransaction]:
        """Yield strict :class:`RawTransaction` records from every OFX account statement."""
        _logger.debug("ofx_provider ingest: loading source=<input-ofx>")
        source_bytes = self._read_source_bytes(path)
        source_sha256 = self._compute_sha256(source_bytes)
        source_row_index = 0
        for account, statement in _iter_account_statements(self._load_accounts(path)):
            currency = (getattr(statement, "currency", None) or default_currency()).strip().upper()
            account_id = getattr(account, "account_id", None) or getattr(account, "number", None) or "account"
            for transaction in statement.transactions:
                source_row_index += 1
                try:
                    transaction_id = (getattr(transaction, "id", None) or "").strip()
                    if not transaction_id:
                        transaction_id = synthesize_transaction_id(
                            provider_name=f"{self.name}-{account_id}",
                            source_sha256=source_sha256,
                            source_row_index=source_row_index,
                        )
                    payee = (getattr(transaction, "payee", None) or "").strip() or None
                    memo = (getattr(transaction, "memo", None) or "").strip()
                    name = (getattr(transaction, "type", None) or "").strip().upper()
                    description = memo or payee or name or "OFX transaction"
                    posted_at = getattr(transaction, "date", None)
                    amount = coerce_decimal(getattr(transaction, "amount", None), default=Decimal("0")) or Decimal("0")
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
                    "TRNTYPE": name,
                    "DTPOSTED": posted_at.isoformat() if posted_at else "",
                    "TRNAMT": str(getattr(transaction, "amount", "")),
                    "FITID": getattr(transaction, "id", None) or "",
                    "NAME": payee or "",
                    "MEMO": memo,
                }
                yield build_raw_transaction(
                    provider=self,
                    path=path,
                    source_sha256=source_sha256,
                    source_row_index=source_row_index,
                    transaction_id=transaction_id,
                    booked_date=booked_date,
                    value_date=None,
                    amount=amount,
                    currency=currency,
                    counterparty=payee,
                    description=description,
                    raw_fields=raw_fields,
                )

    def _load_accounts(self, path: Path) -> tuple[_OfxAccountLike, ...]:
        """Parse every account exposed by an OFX file."""
        try:
            with path.open("rb") as handle:
                parsed = OfxParser.parse(handle)
        # BROAD-EXCEPT-RATIONALE-OFX-TEARDOWN: ofxparse raises base
        # Exception, ValueError, and TypeError from its parsing surface.
        # The library does not expose a typed exception hierarchy, so a
        # broad catch is required to guarantee conversion.
        except Exception as exc:
            _logger.error(
                "ofx_provider: failed to parse OFX file <input-ofx>: %s",
                type(exc).__name__,
                exc_info=True,
            )
            raise InvalidFinancialSourceError(f"could not parse OFX file: {_INPUT_OFX_SOURCE_LABEL}") from exc
        accounts = []
        _multi = getattr(parsed, "accounts", None)
        if _multi:
            accounts.extend(_multi)
        _single = getattr(parsed, "account", None)
        if _single:
            accounts.append(_single)
        if not accounts:
            raise InvalidFinancialSourceError("OFX file does not contain a bank account statement")
        typed_accounts: list[_OfxAccountLike] = []
        seen_accounts: set[int] = set()
        for account in accounts:
            marker = id(account)
            if marker in seen_accounts:
                continue
            seen_accounts.add(marker)
            if not isinstance(account, _OfxAccountLike):
                raise InvalidFinancialSourceError(
                    f"OFX account object is missing expected attributes: {type(account).__name__}"
                )
            typed_accounts.append(account)
        if not any(getattr(account, "statement", None) is not None for account in typed_accounts):
            raise InvalidFinancialSourceError("OFX account does not expose a statement block")
        return tuple(typed_accounts)


def _iter_account_statements(
    accounts: tuple[_OfxAccountLike, ...],
) -> Iterator[tuple[_OfxAccountLike, _OfxStatementLike]]:
    """Yield every account that exposes a statement block."""
    for account in accounts:
        statement = getattr(account, "statement", None)
        if statement is not None and isinstance(statement, _OfxStatementLike):
            yield account, statement
