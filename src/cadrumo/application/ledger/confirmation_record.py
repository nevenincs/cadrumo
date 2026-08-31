"""The persisted provenance of one human confirmation.

The review gate's third rule, and the one that makes the other two auditable: a
confirmation is itself a record, not merely an event that happened to an invoice.
It names who confirmed, when, which fields they asserted values for, which
findings they answered and how, and the content addresses of the evidence bytes
and the transcription the decision was taken against.

**A correction is an assertion, not an edit.** When the operator overrides a
field, the document-derived value is never overwritten in place. The draft's
envelope for that field is re-stamped :attr:`~core.FieldOrigin.OPERATOR` --- so
nothing downstream can read an operator's figure as something the document
stated --- while this record retains the PRIOR value and the PRIOR origin beside
the asserted one. That pairing is the whole point: the record can always answer
"what did the document say, and what did the operator assert instead", and an
override that merely overwrote could answer neither half.

**Why the content addresses ride here.** A consent withdrawal, or a later audit,
re-derives what a confirmation was actually taken against. Naming the evidence
and transcription by content address rather than by id means the re-derivation
can prove the bytes are the same bytes; an id alone survives the artefact being
replaced underneath it.

See Also:
    :class:`~application.ledger.confirmation_gate.ConfirmationBlocker`
        The findings whose resolutions this record carries.
    :class:`~application.ledger.evidence_draft.InvoiceDraft`
        The reading the assertions are recorded against.
    :class:`~domain.invoices.Invoice`
        The record the confirmation minted.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol, Self

from pydantic import BaseModel, Field, model_validator

from ...core.field_grounding import FieldGroundingOutcome
from ...core.field_origin import FieldOrigin
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.config import Settings
from ...core.hashing import content_hash_hex
from ...core.identity import BucketId, ContentDigest, InvoiceId
from ...core.time import UtcInstant, now
from .confirmation_gate import ConfirmationBlocker, FindingResolution
from .deterministic_findings import deterministic_check_names
from .evidence_draft import FieldProvenance, InvoiceDraft

__all__ = [
    "ConfirmationRecordDocument",
    "ConfirmationRecordRepositoryFactory",
    "ConfirmationRecordRepositoryProtocol",
    "FieldAssertion",
    "InvoiceConfirmationRecord",
    "ResolvedFinding",
    "bind_confirmation_record_repository_factory",
    "build_confirmation_record",
    "confirmation_record_object_key",
    "derive_confirmation_id",
    "field_assertions",
    "load_confirmation_records",
    "re_stamped_provenance",
    "read_confirmation_record",
    "write_confirmation_record",
]


class FieldAssertion(BaseModel):
    """One field the operator asserted a value for, beside what the document said.

    Attributes:
        field: Name of the :class:`~application.ledger.evidence_draft.InvoiceDraft` field.
        asserted_value: The value the operator asserted, as printed. Always
            carried as a string: the record is about what was CLAIMED, and
            re-typing it into the field's own type would re-run the parse the
            assertion exists to sit beside.
        prior_value: What the reading path proposed, or ``None`` when it
            proposed nothing --- a supplied value where the document was silent
            is a different act from a correction, and the record distinguishes
            them.
        prior_origin: How the prior value was obtained, or ``None`` when there
            was no prior value. Retained rather than discarded: "the operator
            corrected an exactly-read structured field" and "the operator
            corrected a vision guess" are not the same event, and only this
            field can tell them apart after the fact.
        prior_grounding: What checking the prior value survived, or ``None``.
    """

    model_config = STRICT_FROZEN_CONFIG

    field: str = Field(min_length=1)
    asserted_value: str
    prior_value: str | None = None
    prior_origin: FieldOrigin | None = None
    prior_grounding: FieldGroundingOutcome | None = None

    @model_validator(mode="after")
    def _a_prior_origin_needs_a_prior_value(self) -> Self:
        """Refuse an origin for a value the record does not carry.

        An origin standing alone claims the document said something while
        declining to say what, which reads to a later auditor as a correction
        whose original was lost rather than as a field the document never
        stated.
        """
        if self.prior_value is None and self.prior_origin is not None:
            raise ValueError("a prior origin describes a prior value; record the value or drop the origin")
        return self


class ResolvedFinding(BaseModel):
    """One blocking finding paired with the answer that cleared it.

    Stored as the pair rather than as the resolution alone. A resolution names a
    blocker by id, and an id whose blocker is not recorded beside it is
    unreadable the moment the draft is discarded --- which is exactly when the
    audit happens.

    Attributes:
        blocker: The finding as the gate raised it.
        resolution: The operator's explicit answer to it.
    """

    model_config = STRICT_FROZEN_CONFIG

    blocker: ConfirmationBlocker
    resolution: FindingResolution

    @model_validator(mode="after")
    def _the_resolution_answers_this_blocker(self) -> Self:
        """Refuse a pair whose two halves are about different findings."""
        if self.blocker.blocker_id != self.resolution.blocker_id:
            raise ValueError(
                f"resolution {self.resolution.blocker_id!r} does not answer blocker {self.blocker.blocker_id!r}",
            )
        return self


class InvoiceConfirmationRecord(BaseModel):
    """The provenance of exactly one operator confirmation.

    Attributes:
        confirmation_id: Clock-free derived address, folding the confirmed
            outcome rather than the moment. A retried confirm of the same
            document by the same actor asserting the same values addresses the
            same record instead of accumulating near-duplicates.
        bucket_id: The bucket the confirmation happened in.
        invoice_id: The invoice the confirmation minted or matched.
        evidence_reference: The evidence or attachment id confirmed from.
        evidence_sha256: Content address of the evidence bytes, so a later
            re-derivation can prove the same document was read.
        transcription_sha256: Content address of the stage-one transcription the
            draft was read from, or ``None`` when the reading lane produced
            none (the vision lane reads image to fields in one call).
        extractor: Which reader produced the draft, so a confirmation taken
            against a superseded extractor is identifiable.
        confirmed_by: Who confirmed.
        confirmed_at: When.
        assertions: Every field the operator asserted a value for, each carrying
            the prior value and origin.
        resolutions: Every blocking finding and the answer that cleared it.
    """

    model_config = STRICT_FROZEN_CONFIG

    confirmation_id: str = Field(min_length=16, max_length=16)
    bucket_id: BucketId
    invoice_id: InvoiceId
    evidence_reference: str = Field(min_length=1)
    evidence_sha256: ContentDigest | None = None
    transcription_sha256: ContentDigest | None = None
    extractor: str = Field(min_length=1)
    confirmed_by: str = Field(min_length=1)
    confirmed_at: UtcInstant
    assertions: tuple[FieldAssertion, ...] = ()
    resolutions: tuple[ResolvedFinding, ...] = ()
    checks_run: tuple[str, ...] | None = None
    """Which deterministic checks ran when this record was minted.

    Derived from the one declaration the readers execute
    (:data:`~application.ledger.deterministic_findings.DETERMINISTIC_CHECKS`), never restated, so a
    check added there reaches every later record without a second place to
    remember.

    ``None`` means the record makes NO CLAIM about which checks ran, and that is
    a third state rather than a shorthand for either extreme. Records minted
    before this field existed carry it, and they are not evidence that no check
    ran (a lie toward alarm) nor that every current check ran (a lie toward
    assurance) -- a record attests what ran at its own minting, and one that
    never recorded the set simply does not say. An empty tuple is a different
    claim entirely: that the set was recorded and was empty.

    Not backfilled, deliberately. The compatibility regime is pre-release, so
    reconstructing the set for existing records would be inventing a claim they
    never made -- which is the exact misreading this field exists to prevent.
    """


def derive_confirmation_id(
    *,
    bucket_id: str,
    invoice_id: str,
    evidence_reference: str,
    confirmed_by: str,
    assertions: Sequence[FieldAssertion],
    resolutions: Sequence[ResolvedFinding],
) -> str:
    """Return the clock-free derived address for one confirmation.

    Folds the OUTCOME --- who confirmed what, against which evidence, asserting
    which values, answering which findings --- and never the clock. A derived id
    that folded the timestamp would make an idempotent retry address a new
    record, which is the shape that lets one operator decision be counted twice.
    """
    return content_hash_hex(
        {
            "assertions": [assertion.model_dump(mode="json") for assertion in assertions],
            "bucket_id": bucket_id,
            "confirmed_by": confirmed_by,
            "evidence_reference": evidence_reference,
            "invoice_id": invoice_id,
            "resolutions": [resolved.model_dump(mode="json") for resolved in resolutions],
        },
    )[:16]


class ConfirmationRecordDocument(BaseModel):
    """One bucket's confirmation provenance records."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    records: tuple[InvoiceConfirmationRecord, ...] = ()


def confirmation_record_object_key(document: ConfirmationRecordDocument) -> str:
    """Return the bucket-scoped natural key for one confirmation document."""
    return document.bucket_id


class ConfirmationRecordRepositoryProtocol(Protocol):
    """Persistence operations required by confirmation-record policy."""

    def load(self, identifier: str) -> ConfirmationRecordDocument | None:
        """Load the document stored under ``identifier``, when present."""
        ...

    def save(self, payload: ConfirmationRecordDocument) -> None:
        """Persist one complete confirmation-record document."""
        ...


class ConfirmationRecordRepositoryFactory(Protocol):
    """Construct a confirmation repository for one bucket and storage configuration."""

    def __call__(
        self,
        *,
        bucket_id: str,
        settings: Settings | None,
    ) -> ConfirmationRecordRepositoryProtocol:
        """Return the encrypted repository bound to ``bucket_id``."""
        ...


_BOUND_CONFIRMATION_RECORD_REPOSITORY_FACTORY: ContextVar[ConfirmationRecordRepositoryFactory] = ContextVar(
    "cadrumo_confirmation_record_repository_factory"
)


@contextmanager
def bind_confirmation_record_repository_factory(
    factory: ConfirmationRecordRepositoryFactory,
) -> Generator[ConfirmationRecordRepositoryFactory]:
    """Bind one outward-composed confirmation repository factory."""
    token = _BOUND_CONFIRMATION_RECORD_REPOSITORY_FACTORY.set(factory)
    try:
        yield factory
    finally:
        _BOUND_CONFIRMATION_RECORD_REPOSITORY_FACTORY.reset(token)


def _repository(bucket_id: str, settings: Settings | None) -> ConfirmationRecordRepositoryProtocol:
    try:
        factory = _BOUND_CONFIRMATION_RECORD_REPOSITORY_FACTORY.get()
    except LookupError as error:
        raise RuntimeError("confirmation-record persistence has not been composed") from error
    return factory(bucket_id=bucket_id, settings=settings)


def load_confirmation_records(bucket_id: str, settings: Settings | None = None) -> ConfirmationRecordDocument:
    """Load a bucket's confirmation records, or an empty document when none exist."""
    document = _repository(bucket_id, settings).load(bucket_id)
    return document if document is not None else ConfirmationRecordDocument(bucket_id=bucket_id)


def read_confirmation_record(
    *,
    bucket_id: str,
    confirmation_id: str,
    settings: Settings | None = None,
) -> InvoiceConfirmationRecord | None:
    """Return one confirmation record by its derived id, or ``None``."""
    document = load_confirmation_records(bucket_id, settings)
    return next((row for row in document.records if row.confirmation_id == confirmation_id), None)


def write_confirmation_record(
    *,
    record: InvoiceConfirmationRecord,
    settings: Settings | None = None,
) -> InvoiceConfirmationRecord:
    """Persist one confirmation record, idempotently on its derived id.

    A retry of the same confirmation --- same actor, same evidence, same
    assertions, same resolutions --- addresses the record already stored and
    returns it unchanged rather than appending a second account of one human
    decision.
    """
    document = load_confirmation_records(record.bucket_id, settings)
    existing = next((row for row in document.records if row.confirmation_id == record.confirmation_id), None)
    if existing is not None:
        return existing
    updated = ConfirmationRecordDocument(
        bucket_id=record.bucket_id,
        records=(*document.records, record),
    )
    _repository(record.bucket_id, settings).save(updated)
    return record


def _printed(value: object | None) -> str | None:
    """Return a value as the record carries it, or ``None``."""
    if value is None:
        return None
    return format(value, "f") if hasattr(value, "as_tuple") else str(value)


def field_assertions(
    *,
    draft: InvoiceDraft,
    overrides: Mapping[str, object | None],
) -> tuple[FieldAssertion, ...]:
    """Return one assertion per field the operator actually supplied a value for.

    Args:
        draft: The reading the assertions are recorded against, supplying the
            prior value and the envelope that says how it was obtained.
        overrides: Operator-supplied values keyed by draft field name. A ``None``
            entry means the operator supplied nothing for that field and is
            skipped --- silence is not an assertion.

    Returns:
        Assertions in draft-field declaration order, so two confirmations of the
        same document derive the same id regardless of how the caller ordered
        its overrides.
    """
    envelopes = {envelope.field: envelope for envelope in draft.provenance}
    assertions: list[FieldAssertion] = []
    for field in type(draft).model_fields:
        if field not in overrides:
            continue
        supplied = overrides[field]
        if supplied is None:
            continue
        prior_value = _printed(getattr(draft, field, None))
        envelope = envelopes.get(field)
        assertions.append(
            FieldAssertion(
                field=field,
                asserted_value=str(_printed(supplied)),
                prior_value=prior_value,
                prior_origin=envelope.origin if (envelope is not None and prior_value is not None) else None,
                prior_grounding=(envelope.grounding if (envelope is not None and prior_value is not None) else None),
            ),
        )
    return tuple(assertions)


def re_stamped_provenance(
    *,
    draft: InvoiceDraft,
    assertions: Sequence[FieldAssertion],
) -> tuple[FieldProvenance, ...]:
    """Return *draft*'s envelopes with every asserted field re-stamped ``OPERATOR``.

    The other half of "a correction is an assertion". The prior envelope is
    REPLACED here rather than kept beside the new one, and that is deliberate:
    a draft field carries exactly one envelope, so leaving the document's
    envelope on a field the operator overrode would tell every downstream
    consumer the operator's figure was read from the document. The prior value
    and origin are not lost --- they are in the
    :class:`InvoiceConfirmationRecord`, which is the record that exists to hold
    them.

    An asserted field's outcome is :attr:`~core.FieldGroundingOutcome.UNANCHORED`
    and never ``ANCHORED``: an operator's value is not a reading of the document
    at all, so there is no verbatim occurrence it could be anchored to, and
    stamping one would launder an assertion into a corroborated reading.

    Args:
        draft: The reading whose envelopes are being re-stamped.
        assertions: The operator's assertions, one per overridden field.

    Returns:
        The envelope tuple, in the input order, with asserted fields replaced.
    """
    asserted = {assertion.field: assertion for assertion in assertions}
    if not asserted:
        return draft.provenance

    def _operator_envelope(assertion: FieldAssertion) -> FieldProvenance:
        prior = (
            f"the reading path proposed {assertion.prior_value!r}"
            f"{f' ({assertion.prior_origin.value})' if assertion.prior_origin is not None else ''}"
            if assertion.prior_value is not None
            else "the document stated nothing for this field"
        )
        return FieldProvenance(
            field=assertion.field,
            origin=FieldOrigin.OPERATOR,
            grounding=FieldGroundingOutcome.UNANCHORED,
            note=f"asserted by the operator at confirm; {prior}",
        )

    kept = tuple(envelope for envelope in draft.provenance if envelope.field not in asserted)
    replaced = tuple(
        _operator_envelope(asserted[envelope.field]) for envelope in draft.provenance if envelope.field in asserted
    )
    supplied_without_prior = tuple(
        _operator_envelope(assertion)
        for assertion in assertions
        if all(envelope.field != assertion.field for envelope in draft.provenance)
    )
    return (*kept, *replaced, *supplied_without_prior)


def build_confirmation_record(
    *,
    bucket_id: str,
    invoice_id: str,
    evidence_reference: str,
    evidence_sha256: str | None,
    draft: InvoiceDraft,
    extractor: str,
    confirmed_by: str,
    overrides: Mapping[str, object | None],
    blockers: Sequence[ConfirmationBlocker] = (),
    resolutions: Sequence[FindingResolution] = (),
) -> InvoiceConfirmationRecord:
    """Assemble the confirmation record for one confirmed draft.

    Args:
        bucket_id: The bucket the confirmation happened in.
        invoice_id: The invoice minted or matched.
        evidence_reference: The evidence or attachment id confirmed from.
        evidence_sha256: Content address of the evidence bytes, when known.
        draft: The reading confirmed, supplying prior values and the
            transcription address.
        extractor: Which reader produced the draft.
        confirmed_by: Who confirmed.
        overrides: Operator-supplied values keyed by draft field name.
        blockers: The blocking findings the gate raised.
        resolutions: The operator's answers, one per blocker.

    Returns:
        The assembled record, not yet persisted.
    """
    assertions = field_assertions(draft=draft, overrides=overrides)
    by_id = {resolution.blocker_id: resolution for resolution in resolutions}
    resolved = tuple(
        ResolvedFinding(blocker=blocker, resolution=by_id[blocker.blocker_id])
        for blocker in blockers
        if blocker.blocker_id in by_id
    )
    return InvoiceConfirmationRecord(
        confirmation_id=derive_confirmation_id(
            bucket_id=bucket_id,
            invoice_id=invoice_id,
            evidence_reference=evidence_reference,
            confirmed_by=confirmed_by,
            assertions=assertions,
            resolutions=resolved,
        ),
        bucket_id=bucket_id,
        invoice_id=invoice_id,
        evidence_reference=evidence_reference,
        evidence_sha256=evidence_sha256,
        transcription_sha256=draft.transcription_sha256,
        extractor=extractor,
        confirmed_by=confirmed_by,
        confirmed_at=now(),
        # Stamped from the one list the readers run, and deliberately NOT folded
        # into the derived id above. The id folds the OUTCOME -- who confirmed
        # what against which evidence -- so that a retry matches. Adding a check
        # would change every id if the set were folded in, and two records of the
        # same confirmation would stop matching because the product grew a check
        # between them, which is the idempotency guard failing for a reason that
        # has nothing to do with the confirmation.
        checks_run=deterministic_check_names(),
        assertions=assertions,
        resolutions=resolved,
    )
