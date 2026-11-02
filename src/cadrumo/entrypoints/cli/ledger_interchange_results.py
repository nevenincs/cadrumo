"""Typed ``--json`` payload schemas for ledger import and export commands.

Split from :mod:`ledger_results` along the interchange seam: the import
result with its nested validation, source and diagnostic reports, and the
export envelope with its serialised row. Each class is a strict
:class:`OutputSchema` subclass referenced as a deferred public schema target
by the ledger command specs. The application layer remains authoritative for
:class:`LedgerSourceImportResult` and :class:`LedgerExportResult`; these
envelopes project their JSON-coerced fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import NonNegativeInt, field_validator

from ...application.ledger.models import DiagnosticKind, DiagnosticMessage, DiagnosticSeverity, IsoDateText
from ...core.decimal.grammar import is_non_negative_canonical_decimal
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import SnapshotId
from ...core.identity.transaction_ids import TransactionId
from ...core.json_contract import OutputSchema
from ...core.parsing.codes import IsoCurrencyCode
from ...core.parsing.dates import parse_iso8601_date
from ...core.period import Period
from ...core.text_bounds import NonEmptyStr

if TYPE_CHECKING:
    from ...application.ledger.models import LedgerExportResult as _AppLedgerExportResult
    from ...application.ledger.models import LedgerSourceImportResult as _AppLedgerSourceImportResult


class LedgerImportTransactionRefPayload(OutputSchema):
    """One bucket-qualified transaction reference nested in the import result.

    Mirrors :class:`BucketTransactionRef`'s
    ``model_dump(mode="json")`` — replaces the former bare ``dict[str, object]``
    on the imported / skipped / likely-duplicate ref lists.
    """

    bucket_id: BucketId
    transaction_id: TransactionId


class LedgerImportValidationPayload(OutputSchema):
    """Source-file validation details from :class:`LedgerSourceValidationReport`."""

    valid: bool
    warnings: list[str] = []
    encoding: str | None = None
    dialect: str | None = None


class LedgerImportSourcePayload(OutputSchema):
    """Source-file verification details from :class:`LedgerSourceVerificationReport`."""

    requested: bool
    path: str | None = None
    sha256: str | None = None


class LedgerImportDiagnosticPayload(OutputSchema):
    """One :class:`LedgerImportDiagnosticReport` entry."""

    kind: DiagnosticKind
    severity: DiagnosticSeverity
    message: DiagnosticMessage
    source_path: str | None = None
    source_locator: str | None = None
    affected_transaction_ids: list[str] = []


class LedgerExportRowPayload(OutputSchema):
    """One serialised ledger row nested in ``aeat app ledger export``.

    Mirrors :class:`LedgerExportRow`'s
    ``model_dump(mode="json")``. The flow stays the non-negative ``amount``
    magnitude plus the ``direction`` authority; every other column is
    a string the serializer already emits ("" for an absent optional column).

    "Mirrors" is meant literally, and for four columns it was not true. The
    canonical row requires content in ``lifecycle_state``, ``direction``,
    ``description`` and ``business_classification``; this payload accepted an
    empty string in each. A payload looser than the record it projects lets a
    consumer validate a row the producer could never have emitted, so the
    published schema promised less than the data actually carries. The columns
    that are genuinely optional keep their ``""`` default -- that is the
    serializer's absent-column spelling, not a missing bound.
    """

    bucket_id: BucketId
    transaction_id: TransactionId
    lifecycle_state: NonEmptyStr
    invoice_id: str = ""
    booked_date: IsoDateText
    value_date: str = ""
    operation_date: str = ""
    accrual_date: str = ""
    effective_date: IsoDateText
    amount: NonEmptyStr
    currency: IsoCurrencyCode
    direction: NonEmptyStr
    counterparty: str = ""
    description: NonEmptyStr
    business_classification: NonEmptyStr
    business_pct: str = ""
    category_id: str = ""
    taxable_base: str = ""
    iva_rate: str = ""
    iva_amount: str = ""
    iva_category: str = ""
    counterparty_country: str = ""
    counterparty_identification_state: str = ""
    irpf_category: str = ""
    usage_ratio_id: str = ""
    prorrata_reference: str = ""
    purchase_invoice_evidence_id: str = ""
    attachment_ids: str = ""
    notes: str = ""
    created_by: str = ""
    created_source_command: str = ""
    source_jurisdiction: str = ""
    value_in_eur: str = ""
    fx_rate: str = ""

    @field_validator("booked_date", "effective_date")
    @classmethod
    @pydantic_validation_boundary
    def _require_iso_date(cls, value: str) -> str:
        """Keep exported mandatory dates parseable without changing their JSON wire form.

        Asked here AND on :class:`~application.ledger.models.LedgerExportRow`,
        deliberately. The row is where the rule now LIVES, so the CSV and the
        persisted snapshot are governed too rather than only the JSON path; this
        assertion stays because a projection that promises less than the record
        it mirrors is the divergence this module has already been corrected for
        twice. Both ask the same two predicates -- ``parse_iso8601_date`` and
        ``is_non_negative_canonical_decimal`` -- so the rule is stated once and
        checked twice, which is not the same as being written twice.
        """
        if parse_iso8601_date(value) is None:
            raise ValueError("must be an ISO-8601 date")
        return value

    @field_validator("value_date", "operation_date", "accrual_date")
    @classmethod
    @pydantic_validation_boundary
    def _validate_optional_iso_date(cls, value: str) -> str:
        if value:
            cls._require_iso_date(value)
        return value

    @field_validator("amount", "taxable_base", "iva_amount", "value_in_eur")
    @classmethod
    @pydantic_validation_boundary
    def _require_non_negative_decimal(cls, value: str) -> str:
        """Refuse an export amount the ledger could never have stored.

        The sign rule is the parser's own ``signed`` axis rather than a
        comparison written here: a ledger amount is a magnitude and direction
        lives on its own enum, so "non-negative" is a property of the grammar,
        not a threshold this payload gets to pick. Same shape the IVA wallet
        payload uses for the same reason.
        """
        if not value:
            return value
        if not is_non_negative_canonical_decimal(value):
            raise ValueError("must be a non-negative canonical decimal")
        return value


class LedgerExportPayload(OutputSchema):
    """JSON envelope for ``aeat app ledger export``.

    Distinct from the application
    :class:`LedgerExportResult`: the backend
    result carries the raw ``payload`` bytes and typed members (``BucketId``,
    ``ExportSerializationFormat``, ``LedgerExportRow``); this
    envelope projects the JSON-coerced metadata + row view and appends the
    operator-facing ``output_path``. Derive instances via
    :meth:`LedgerExportPayload.from_result`.
    """

    bucket_id: BucketId
    export_id: SnapshotId
    export_format: str
    media_type: str
    filename_extension: str
    row_count: NonNegativeInt
    byte_size: NonNegativeInt
    sha256: SnapshotId
    fieldnames: list[str]
    rows: list[LedgerExportRowPayload]
    bucket_event_ids: list[str] = []
    output_path: str

    @classmethod
    def from_result(cls, result: _AppLedgerExportResult, *, output_path: str) -> LedgerExportPayload:
        """Project the application export result into this CLI envelope.

        The raw ``payload`` bytes are excluded — the JSON envelope carries
        export metadata and the row projection, not the binary artefact (that
        is written to ``output_path``). ``model_dump(mode="json")`` performs the
        typed-id/enum/nested-row coercion so the envelope's loosened field types
        stay exactly consistent with the backend contract.

        Returns:
            :class:`LedgerExportPayload` ready for the CLI JSON envelope.
        """
        data = result.model_dump(mode="json", exclude={"payload"})
        data["output_path"] = output_path
        return cls.model_validate(data)


class LedgerImportPayload(OutputSchema):
    """JSON envelope for ``aeat app ledger import``.

    Distinct from the application
    :class:`LedgerSourceImportResult`: this
    envelope projects that result's JSON-coerced fields; non-blocking import
    advisories use the shared envelope ``notices`` channel.
    """

    rows: NonNegativeInt
    imported: NonNegativeInt
    skipped: NonNegativeInt
    likely_duplicates: NonNegativeInt = 0
    dry_run: bool
    verify: bool
    period: Period | None = None
    bucket_id: BucketId | None = None
    import_batch_id: str | None = None
    bucket_event_ids: list[str] = []
    imported_transaction_refs: list[LedgerImportTransactionRefPayload] = []
    skipped_transaction_refs: list[LedgerImportTransactionRefPayload] = []
    likely_duplicate_transaction_refs: list[LedgerImportTransactionRefPayload] = []
    # Tuples, mirroring the record: a DIRECTORY import produces one report per
    # file and the application fold now keeps them all. A single-file import
    # carries a one-element list.
    validations: list[LedgerImportValidationPayload]
    sources: list[LedgerImportSourcePayload]
    diagnostics: list[LedgerImportDiagnosticPayload] = []

    @classmethod
    def from_result(cls, result: _AppLedgerSourceImportResult) -> LedgerImportPayload:
        """Project the application import result into this CLI envelope.

        ``model_dump(mode="json")`` coerces the typed members (typed-ids, nested
        validation/source/diagnostic reports) to the JSON shape this envelope
        declares. Advisories are intentionally excluded because the shared
        envelope notice schema is their canonical transport.

        Returns:
            :class:`LedgerImportPayload` ready for the CLI JSON envelope.
        """
        data = result.model_dump(mode="json")
        return cls.model_validate(data)
