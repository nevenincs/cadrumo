"""Immutable invoice catalogues and authenticated stored catalogue reads."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from types import MappingProxyType
from typing import Final, Self, final, override

from pydantic import BaseModel, Field, ModelWrapValidatorHandler, field_serializer, field_validator, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.type_adapters import OBJECT_TUPLE_ADAPTER, STR_KEYED_MAPPING_ADAPTER
from ..iva.schema import InvoiceKind
from ._validation_pass import invoice_validation_pass
from .errors import InvoiceValidationError
from .models import AUTHENTICATED_STORED_READ, Invoice


class InvoiceCatalogue(BaseModel):
    """Immutable invoice catalogue keyed by ``invoice_id``."""

    model_config = _STRICT_FROZEN

    invoices: Mapping[str, Invoice] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _coerce_catalogue_input(cls, data: object) -> object:
        """Accept a catalogue, its canonical payload, or an iterable of invoices.

        A mapping arrives here as one of two things: the canonical serialized
        payload, which carries its entries under ``invoices``, or the field
        kwargs of a direct construction, which for a catalogue with no entries
        is empty. A NON-EMPTY mapping with no ``invoices`` key is neither. It
        is a catalogue serialized without its wrapper -- a shape nothing in
        this codebase writes -- and it is refused rather than wrapped: wrapping
        promotes an arbitrary mapping into a catalogue whose keys no writer
        ever established to be invoice ids, and the resulting record is
        indistinguishable afterwards from one that was written correctly.
        """
        if isinstance(data, cls):
            return data
        if isinstance(data, Mapping):
            payload = STR_KEYED_MAPPING_ADAPTER.validate_python(data)
            if payload and "invoices" not in payload:
                raise InvoiceValidationError(
                    "invoice catalogue payload must carry its entries under the 'invoices' key; "
                    f"got a bare mapping of {len(payload)} top-level entries",
                )
            return payload
        if isinstance(data, Iterable) and not isinstance(data, str | bytes):
            invoices: dict[str, Invoice] = {}
            for item in OBJECT_TUPLE_ADAPTER.validate_python(data):
                invoice = item if isinstance(item, Invoice) else Invoice.model_validate(item)
                if invoice.invoice_id in invoices:
                    raise InvoiceValidationError(f"duplicate invoice_id: {invoice.invoice_id}")
                invoices[invoice.invoice_id] = invoice
            return {"invoices": invoices}
        return data

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_mapping_keys(self) -> Self:
        for key, invoice in self.invoices.items():
            if key != invoice.invoice_id:
                raise InvoiceValidationError(f"catalogue key {key!r} does not match invoice_id {invoice.invoice_id!r}")
        return self

    @field_validator("invoices")
    @classmethod
    def _freeze_invoices(cls, value: Mapping[str, Invoice]) -> Mapping[str, Invoice]:
        return MappingProxyType(dict(value))

    @field_serializer("invoices")
    def _serialize_invoices(self, value: Mapping[str, Invoice]) -> dict[str, Invoice]:
        return dict(value)

    # Declared after every other model validator so it encloses them all.
    @model_validator(mode="wrap")
    @classmethod
    def _validate_in_one_pass(cls, data: object, handler: ModelWrapValidatorHandler[Self]) -> Self:
        """Share one registry pass across every invoice this catalogue validates."""
        with invoice_validation_pass():
            return handler(data)

    @override
    def __iter__(self) -> Iterator[Invoice]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional Pydantic catalogue iteration adapter; the established public API yields Invoice records, not BaseModel field-value tuples
        """Iterate over catalogue invoices."""
        return iter(self.invoices.values())

    def __len__(self) -> int:
        """Return the number of invoices in the catalogue."""
        return len(self.invoices)

    def __contains__(self, invoice_id: object) -> bool:
        """Return whether the catalogue contains ``invoice_id``."""
        if isinstance(invoice_id, Invoice):
            return invoice_id.invoice_id in self.invoices
        if isinstance(invoice_id, str):
            return invoice_id in self.invoices
        return False

    def get(self, invoice_id: str) -> Invoice | None:
        """Fetch one invoice by ID if present.

        Args:
            invoice_id: Stable invoice identifier.

        Returns:
            The matching :class:`Invoice`, or ``None`` when absent.
        """
        return self.invoices.get(invoice_id)

    def values(self) -> Iterator[Invoice]:
        """Iterate over catalogue :class:`Invoice` records."""
        return iter(self.invoices.values())


_INVOICE_KIND_TOKENS: Final[frozenset[str]] = frozenset(member.value for member in InvoiceKind)


@final
class StoredInvoiceCatalogue:
    """The invoices of an authenticated current-schema catalogue, validated as they are read.

    Built only by :func:`decode_authenticated_invoice_catalogue`, after the
    secure store has decrypted and authenticated the catalogue in the same
    call and confirmed it was written under the current schema version. The
    records stay as their decoded JSON objects until a read asks for one, so
    a read pays only for the invoices it returns. Each invoice handed out is
    validated then with every check a full read applies -- types, field
    constraints, the dated registry vocabulary and rules, the totals -- except
    re-deriving its stored id, which the store's authentication already
    proves. :class:`InvoiceCatalogue` remains the form every write, import and
    calculation path reads.

    This is read-only. Nothing here can be saved: the repository's write
    methods take an :class:`InvoiceCatalogue` and read the stored catalogue
    through full validation.
    """

    __slots__ = ("_records",)

    def __init__(self, records: Mapping[str, Mapping[str, object]], *, _authenticated: object = None) -> None:
        """Hold ``records``; only :func:`decode_authenticated_invoice_catalogue` may construct one."""
        if _authenticated is not AUTHENTICATED_STORED_READ:
            raise TypeError("a StoredInvoiceCatalogue is built only by decode_authenticated_invoice_catalogue")
        self._records: Mapping[str, Mapping[str, object]] = MappingProxyType(dict(records))

    def __len__(self) -> int:
        """Return the number of stored invoices."""
        return len(self._records)

    def __contains__(self, invoice_id: object) -> bool:
        """Return whether ``invoice_id`` keys a stored invoice."""
        return isinstance(invoice_id, str) and invoice_id in self._records

    def invoice_ids(self) -> tuple[str, ...]:
        """Return every stored invoice id in catalogue order, validating none of them."""
        return tuple(self._records)

    def attributed_bucket_ids(self) -> frozenset[str]:
        """Return every profile bucket a stored invoice is attributed to.

        Read from the stored field without validating the invoice, so a
        foreign record is refused even by a read that never returns it.

        Raises:
            InvoiceValidationError: A stored ``bucket_id`` is not text.
        """
        attributed: set[str] = set()
        for record in self._records.values():
            value = record.get("bucket_id")
            if value is None:
                continue
            if not isinstance(value, str):
                raise InvoiceValidationError("a stored invoice bucket_id must be a string")
            text = value.strip()
            if text:
                attributed.add(text)
        return frozenset(attributed)

    def get(self, invoice_id: str) -> Invoice | None:
        """Validate and return one stored invoice, or ``None`` when no record has that id."""
        record = self._records.get(invoice_id)
        if record is None:
            return None
        return _validate_stored_invoice(invoice_id, record)

    def require(self, invoice_id: str) -> Invoice:
        """Validate and return one stored invoice.

        Raises:
            KeyError: No stored record has ``invoice_id``.
        """
        return _validate_stored_invoice(invoice_id, self._records[invoice_id])

    def values(self, *, kind: InvoiceKind | None = None) -> tuple[Invoice, ...]:
        """Validate and return the stored invoices in catalogue order, optionally only those of ``kind``.

        A record whose stored kind is another valid kind is passed over
        without validation. Any other record, including one whose kind is not
        a valid token at all, is validated, so a malformed record refuses the
        read rather than dropping out of a filtered one. Every invoice
        validates inside one registry pass, as a catalogue decode does.
        """
        selected: list[Invoice] = []
        with invoice_validation_pass():
            for invoice_id, record in self._records.items():
                stored_kind = record.get("kind")
                if (
                    kind is not None
                    and isinstance(stored_kind, str)
                    and stored_kind in _INVOICE_KIND_TOKENS
                    and stored_kind != kind.value
                ):
                    continue
                invoice = _validate_stored_invoice(invoice_id, record)
                if kind is None or invoice.kind is kind:
                    selected.append(invoice)
        return tuple(selected)


def _validate_stored_invoice(invoice_id: str, record: Mapping[str, object]) -> Invoice:
    """Validate one authenticated stored record and check it is keyed by its own id."""
    invoice = Invoice.model_validate(record, context=AUTHENTICATED_STORED_READ)
    if invoice.invoice_id != invoice_id:
        raise InvoiceValidationError(f"catalogue key {invoice_id!r} does not match invoice_id {invoice.invoice_id!r}")
    return invoice


def decode_authenticated_invoice_catalogue(records: Mapping[str, Mapping[str, object]]) -> StoredInvoiceCatalogue:
    """Wrap the invoice records of a catalogue the secure store has just authenticated.

    The one entry point to the trusted read. The invoice catalogue repository
    calls it only from its authenticated read, with the ``invoices`` mapping
    of a catalogue the secure store decrypted, authenticated against its
    namespace, key and schema version, and confirmed current in that same
    call. Passing anything else trusts a record no store authenticated: a
    write, import, edit or intake path constructs :class:`Invoice` or
    :class:`InvoiceCatalogue` directly and keeps full admission.

    Args:
        records: Each stored invoice's decoded JSON object, keyed by invoice id.

    Returns:
        A read-only view that validates each invoice as it is read.
    """
    return StoredInvoiceCatalogue(records, _authenticated=AUTHENTICATED_STORED_READ)
