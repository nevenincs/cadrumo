"""OFX financial provider backed by `ofxparse`."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast

from ofxparse import OfxParser

from aeat.financial._raw_transaction import RawTransaction, SourceFormat
from aeat.financial.providers._base import (
    FinancialProvider,
    InvalidFinancialSourceError,
    ProviderValidation,
    build_raw_transaction,
    default_currency,
    parse_date_value,
    synthesize_transaction_id,
)


class _OfxTransactionLike(Protocol):
    """Minimal OFX transaction surface used by the provider."""

    date: object
    amount: object
    id: str | None
    payee: str | None
    memo: str | None
    type: str | None


class _OfxStatementLike(Protocol):
    """Minimal OFX statement surface used by the provider."""

    transactions: list[_OfxTransactionLike]
    currency: str | None


class _OfxAccountLike(Protocol):
    """Minimal OFX account surface used by the provider."""

    account_id: str | None
    number: str | None
    statement: _OfxStatementLike | None


class OfxProvider(FinancialProvider):
    """Ingest raw transactions from OFX and QFX files."""

    name = "OFX provider"
    supported_extensions = frozenset({".ofx", ".qfx"})
    source_format = SourceFormat.OFX

    def validate_source(self, path: Path) -> ProviderValidation:
        """Validate that the OFX file can be parsed and contains transactions."""
        try:
            account, statement = self._load_statement(path)
        except InvalidFinancialSourceError as exc:
            return ProviderValidation(is_valid=False, warnings=(str(exc),))
        if not statement.transactions:
            return ProviderValidation(
                is_valid=False,
                warnings=("OFX statement contains no transactions",),
            )
        account_id = getattr(account, "account_id", "") or getattr(account, "number", "")
        return ProviderValidation(
            is_valid=True,
            warnings=(),
            detected_encoding="ofxparse",
            detected_dialect=f"account={account_id or 'unknown'}",
        )

    def ingest(self, path: Path) -> Iterator[RawTransaction]:
        """Yield strict raw transactions from the first OFX account statement."""
        source_bytes = self._read_source_bytes(path)
        source_sha256 = self._compute_sha256(source_bytes)
        account, statement = self._load_statement(path)
        currency = (getattr(statement, "currency", None) or default_currency()).strip().upper()
        for source_row_index, transaction in enumerate(statement.transactions, start=1):
            transaction_id = (getattr(transaction, "id", None) or "").strip()
            if not transaction_id:
                transaction_id = synthesize_transaction_id(
                    provider_name=f"{self.name}-{getattr(account, 'account_id', 'account')}",
                    source_sha256=source_sha256,
                    source_row_index=source_row_index,
                )
            payee = (getattr(transaction, "payee", None) or "").strip() or None
            memo = (getattr(transaction, "memo", None) or "").strip()
            name = (getattr(transaction, "type", None) or "").strip().upper()
            description = memo or payee or name or "OFX transaction"
            posted_at = getattr(transaction, "date", None)
            raw_fields = {
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
                booked_date=parse_date_value(posted_at, day_first=False),
                value_date=None,
                amount=Decimal(str(getattr(transaction, "amount", "0"))),
                currency=currency,
                counterparty=payee,
                description=description,
                raw_fields=raw_fields,
            )

    def _load_statement(self, path: Path) -> tuple[_OfxAccountLike, _OfxStatementLike]:
        """Parse the first account statement from an OFX file."""
        try:
            with path.open("rb") as handle:
                parsed = OfxParser.parse(handle)
        except Exception as exc:  # pragma: no cover - validated in tests through error path
            raise InvalidFinancialSourceError(f"could not parse OFX file: {path}") from exc
        accounts = []
        if getattr(parsed, "accounts", None):
            accounts.extend(parsed.accounts)
        if getattr(parsed, "account", None):
            accounts.append(parsed.account)
        if not accounts:
            raise InvalidFinancialSourceError("OFX file does not contain a bank account statement")
        account = cast(_OfxAccountLike, accounts[0])
        statement = getattr(account, "statement", None)
        if statement is None:
            raise InvalidFinancialSourceError("OFX account does not expose a statement block")
        return account, cast(_OfxStatementLike, statement)
