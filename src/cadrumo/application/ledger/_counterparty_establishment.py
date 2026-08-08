"""Where a counterparty is established, asked once and remembered against the entity.

Establishment is a property of the ENTITY, not of the invoice. A supplier in
Las Palmas is in Las Palmas on every document they ever send, so a pipeline that
carries the answer per invoice asks the same question every month and stores
four hundred copies of one fact.

That matters here because of what the paper does not say. A domestic Spanish
invoice routinely prints a bare ``B``-CIF, no country line, and a five-digit
postal code that France, Germany and Italy also use — so the printed evidence
establishes neither party's IVA territory, and the three Spanish territories
(peninsula and Balearics under LIVA, Canarias under IGIC, Ceuta and Melilla
under IPSI) are treated differently by law. The honest answer on that population
is to ask. The reason asking is viable rather than exhausting is this module:
**one question per counterparty whose paper is non-decisive, never one per
invoice.**

**An absent fact is never a territory.** There is no branch here that produces
:attr:`~domain.iva.IvaTerritorialScope.ES_MAINLAND` — or any other member — from
the absence of a record. The peninsula is the majority population, so a default
there would pass every test written by someone with mainland fixtures while
silently placing Canarian and Ceutan parties inside a territory their operations
are not subject to. Absence returns nothing and the caller asks.

**Identity is the canonical tax identifier, and nothing else.** The key is a
digest of :func:`~application.ledger.canonical_identity_token` — the same
authority the counterparty-role resolver already verifies candidates through, so
a printed ``ESB-1234567-4``, ``ES B12345674`` and ``B12345674`` all address one
record rather than three. A name is deliberately not identity: two unrelated
companies share one, and keying on it would hand one entity's territory to
another. An unverifiable identifier yields no key at all, which is the
conservative direction — no record is written and no record is found, so the
operator is asked again rather than answered wrongly.

**A stored fact never silently overrides the document, and the document never
silently overrides a stored fact.** Where a later document's printed evidence
resolves a territory and it disagrees with what the operator confirmed, that is
a real signal — a confirmed-Canarian party printing a French country code is
either a different entity, a changed establishment, or a mistaken assertion —
and none of the three is settled by preferring one side. The resolution carries
a :class:`CounterpartyEstablishmentContradiction` and NO fact, so a caller
cannot proceed on either value by accident.

See Also:
    :class:`~application.ledger.DeclaredFacts`
        The one channel a supplied fact reaches the criteria assembly through.
        This module produces a member of it and opens no second route.
    :func:`~application.ledger.canonical_identity_token`
        The identifier authority the counterparty key is derived from.
    :class:`~domain.iva.IvaTerritorialScope`
        The territory a confirmed fact carries.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, override

from pydantic import BaseModel, Field, model_validator

from ...adapters.persistence.storage import (
    LEDGER_COUNTERPARTY_ESTABLISHMENT_NAMESPACE,
    SecureBoundRepository,
    SensitivityClass,
)
from ...core import STRICT_FROZEN_CONFIG, ClassifierInputSource
from ...core.errors import CadrumoError
from ...core.hashing import sha256_hex
from ...core.time import now
from ...domain.iva import IvaTerritorialScope
from ._classification_assembly import DeclaredFact

if TYPE_CHECKING:
    from typing import Self

__all__ = [
    "CounterpartyEstablishmentConflictError",
    "CounterpartyEstablishmentContradiction",
    "CounterpartyEstablishmentFact",
    "CounterpartyEstablishmentInputError",
    "CounterpartyEstablishmentRepository",
    "CounterpartyEstablishmentResolution",
    "counterparty_establishment_key",
    "forget_counterparty_establishment",
    "record_counterparty_establishment",
    "resolve_counterparty_establishment",
]

_COUNTERPARTY_KEY_LENGTH: int = 64


def _canonical_identity_token(value: str, *, country_code: str | None) -> str | None:
    """Return the canonical identifier, deferring the import to call time.

    ``_identity_roles`` reaches the draft and grounding modules, which import
    each other, so importing it at module scope makes this module's import order
    decide whether that pair resolves. The deferral is the sanctioned cycle
    break and changes only WHEN the owning module executes: the symbol keeps its
    one home and one import path.
    """
    from ._identity_roles import canonical_identity_token

    return canonical_identity_token(value, country_code=country_code)


class CounterpartyEstablishmentInputError(CadrumoError):
    """Raised when a counterparty establishment assertion is not storable."""


class CounterpartyEstablishmentConflictError(CadrumoError):
    """Raised when an assertion contradicts the one already confirmed for a counterparty."""


def counterparty_establishment_key(
    tax_identifier: str,
    *,
    country_code: str | None = None,
) -> str | None:
    """Return the record key for a counterparty, or ``None`` when it has no identity.

    The key is the SHA-256 of the canonical identifier rather than the
    identifier itself, because it becomes the storage object key and an object
    key sits outside the encrypted payload: addressing a record by a real
    counterparty NIF would put a taxpayer's trading partner in the clear.

    Returning ``None`` for an identifier that does not verify is the whole
    treatment of that case. There is no fallback key derived from the raw
    string: two different unverifiable readings of one page would collide under
    it, and the collision would silently share one entity's territory with
    another.

    Args:
        tax_identifier: The counterparty's identifier as printed.
        country_code: The country the identifier is stated under, when the
            document says. ``None`` takes the Spanish path, matching the
            identifier authority — an unqualified identifier on a Spanish
            invoice is Spanish, and a foreign one printed without its prefix
            simply does not verify.

    Returns:
        The 64-character key, or ``None`` when the identifier does not verify.
    """
    token = _canonical_identity_token(tax_identifier, country_code=country_code)
    if token is None:
        return None
    return sha256_hex(token.encode())


class CounterpartyEstablishmentFact(BaseModel):
    """One confirmed statement of where a counterparty is established.

    Attributes:
        counterparty_key: The record key, derived from the canonical
            identifier. Clock-free: the same counterparty always addresses the
            same record, so a retry finds the existing one rather than minting a
            second.
        canonical_tax_identifier: The identifier in its canonical form, held
            inside the encrypted payload. Kept so an operator reviewing the
            store sees whom each record is about — the key alone is a digest.
        territorial_scope: The territory the operator confirmed.
        source: Who established it. Constrained to
            :attr:`~core.ClassifierInputSource.OPERATOR_ASSERTION`: the ladder's
            earlier rungs read printed evidence per document and are re-read per
            document, so a document-sourced value cached here would answer as an
            assertion and take the contradiction channel offline.
        asserted_by: The operator identity that confirmed it.
        asserted_at: When it was confirmed. A last-seen body field, never folded
            into the key.
        note: What the operator relied on, in their own words. Empty when they
            said nothing.
    """

    model_config = STRICT_FROZEN_CONFIG

    counterparty_key: str = Field(min_length=_COUNTERPARTY_KEY_LENGTH, max_length=_COUNTERPARTY_KEY_LENGTH)
    canonical_tax_identifier: str = Field(min_length=1)
    territorial_scope: IvaTerritorialScope
    source: ClassifierInputSource
    asserted_by: str = Field(min_length=1)
    asserted_at: datetime
    note: str = ""

    @model_validator(mode="after")
    def _only_an_operator_may_confirm(self) -> Self:
        """Refuse a fact this store is not the home for.

        ``source`` is required rather than defaulted so a persisted record
        states its provenance explicitly, and it is constrained rather than free
        so the store cannot quietly become a cache of document readings. A
        document-sourced territory is rung one or two of the ladder, re-read
        from each document's own page; remembering one here would answer later
        documents as though an operator had confirmed it, and would take the
        contradiction channel offline for exactly the population it protects.
        """
        if self.source is not ClassifierInputSource.OPERATOR_ASSERTION:
            raise ValueError(
                f"a counterparty establishment fact is confirmed by an operator, not by "
                f"{self.source.value}: document evidence is re-read per document rather than remembered",
            )
        return self

    @classmethod
    def create(
        cls,
        *,
        tax_identifier: str,
        territorial_scope: IvaTerritorialScope,
        asserted_by: str,
        country_code: str | None = None,
        note: str = "",
        asserted_at: datetime | None = None,
    ) -> Self:
        """Build a fact for one counterparty, refusing an identifier with no identity.

        Raises:
            CounterpartyEstablishmentInputError: When the identifier does not
                verify, so there is nothing stable to key the fact to.
        """
        token = _canonical_identity_token(tax_identifier, country_code=country_code)
        if token is None:
            raise CounterpartyEstablishmentInputError(
                f"the identifier {tax_identifier!r} does not verify, so an establishment fact "
                f"confirmed against it could not be found again on a later document",
                context={"tax_identifier": tax_identifier, "country_code": country_code},
            )
        return cls(
            counterparty_key=sha256_hex(token.encode()),
            canonical_tax_identifier=token,
            territorial_scope=territorial_scope,
            source=ClassifierInputSource.OPERATOR_ASSERTION,
            asserted_by=asserted_by,
            asserted_at=asserted_at or now(),
            note=note,
        )

    @property
    def declared_fact(self) -> DeclaredFact[IvaTerritorialScope]:
        """Return this fact in the form the criteria assembly consumes.

        The value and its attribution travel together, so a classification
        standing on a remembered assertion records that an operator said so —
        not that a document did.
        """
        return DeclaredFact[IvaTerritorialScope](value=self.territorial_scope, source=self.source)


class CounterpartyEstablishmentRepository(SecureBoundRepository[CounterpartyEstablishmentFact]):
    """Encrypted profile-local store of confirmed counterparty establishment facts.

    The namespace, its :class:`SensitivityClass`, schema version and object-key
    contract all come from
    :data:`~adapters.persistence.storage.LEDGER_COUNTERPARTY_ESTABLISHMENT_NAMESPACE`,
    so the record's confidentiality tier is declared once beside the namespace
    rather than restated here.
    Writes go through the shared single-writer envelope primitive rather than
    beside it, so a record here gets the same atomicity and encryption every
    other bucket-scoped record gets.
    """

    namespace: ClassVar[str] = LEDGER_COUNTERPARTY_ESTABLISHMENT_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = LEDGER_COUNTERPARTY_ESTABLISHMENT_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = LEDGER_COUNTERPARTY_ESTABLISHMENT_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = CounterpartyEstablishmentFact

    @override
    def extract_identifier(self, payload: CounterpartyEstablishmentFact) -> str:
        return payload.counterparty_key


class CounterpartyEstablishmentContradiction(BaseModel):
    """A later document's territory evidence disagreeing with the confirmed fact.

    Carried rather than resolved. The stored value is an operator's claim about
    an entity and the printed value is an issuer's claim about one document, and
    a disagreement is one of three things — a different entity behind a reused
    identifier, an establishment that moved, or an assertion made in error. None
    is settled by preferring a side, so both are shown and a human decides.

    Attributes:
        counterparty_key: The record the disagreement is about.
        canonical_tax_identifier: Whom, in readable form.
        confirmed_scope: What the operator confirmed for this counterparty.
        evidenced_scope: What this document's printed evidence resolved to.
        detail: The disagreement in words, for the operator-facing finding.
    """

    model_config = STRICT_FROZEN_CONFIG

    counterparty_key: str = Field(min_length=_COUNTERPARTY_KEY_LENGTH, max_length=_COUNTERPARTY_KEY_LENGTH)
    canonical_tax_identifier: str = Field(min_length=1)
    confirmed_scope: IvaTerritorialScope
    evidenced_scope: IvaTerritorialScope
    detail: str = Field(min_length=1)


class CounterpartyEstablishmentResolution(BaseModel):
    """What the store had to say about one counterparty on one document.

    Three states, and "probably" is not one of them: a usable fact, a
    contradiction, or neither. The two populated fields are mutually exclusive
    by construction — a contradicted resolution carries no fact, so a caller
    reading ``fact`` cannot proceed on a value the evidence disputes.

    Attributes:
        fact: The remembered assertion, in the channel the assembly consumes.
            ``None`` when nothing was confirmed for this counterparty, when the
            identifier had no identity, or when the evidence contradicts it.
        contradiction: The disagreement, when there is one.
    """

    model_config = STRICT_FROZEN_CONFIG

    fact: DeclaredFact[IvaTerritorialScope] | None = None
    contradiction: CounterpartyEstablishmentContradiction | None = None

    @property
    def contradicted(self) -> bool:
        """Return whether the evidence disputes the confirmed fact."""
        return self.contradiction is not None


def _repository(
    *,
    bucket_id: str,
    repository: CounterpartyEstablishmentRepository | None,
) -> CounterpartyEstablishmentRepository:
    """Return the injected repository, or one bound to ``bucket_id``."""
    if repository is not None:
        return repository
    return CounterpartyEstablishmentRepository(bucket_id=bucket_id)


def record_counterparty_establishment(
    *,
    bucket_id: str,
    tax_identifier: str,
    territorial_scope: IvaTerritorialScope,
    asserted_by: str,
    country_code: str | None = None,
    note: str = "",
    asserted_at: datetime | None = None,
    repository: CounterpartyEstablishmentRepository | None = None,
) -> CounterpartyEstablishmentFact:
    """Confirm where a counterparty is established, once, for every later document.

    Idempotent on the whole record rather than on the key alone. A retry
    carrying the same territory returns the STORED fact unchanged — the original
    ``asserted_at`` and ``asserted_by`` survive, because re-stamping them would
    make a repeated call look like a fresh confirmation. A call carrying a
    DIFFERENT territory refuses: overwriting would silently discard an answer
    the operator gave, and quietly reclassify every invoice already derived
    under it.

    A same-key call differing only in ``note`` is a genuine correction of free
    prose and is written through, since no classification stands on it.

    Args:
        bucket_id: Active profile bucket.
        tax_identifier: The counterparty's identifier as printed.
        territorial_scope: The territory the operator confirms.
        asserted_by: Operator identity making the claim.
        country_code: The country the identifier is stated under, if any.
        note: What the operator relied on. Free prose, never consulted.
        asserted_at: Override clock, for deterministic tests.
        repository: Injected store.

    Returns:
        The persisted fact, or the pre-existing one on an idempotent retry.

    Raises:
        CounterpartyEstablishmentInputError: When the identifier does not verify.
        CounterpartyEstablishmentConflictError: When a different territory is
            already confirmed for this counterparty.
    """
    fact = CounterpartyEstablishmentFact.create(
        tax_identifier=tax_identifier,
        territorial_scope=territorial_scope,
        asserted_by=asserted_by,
        country_code=country_code,
        note=note,
        asserted_at=asserted_at,
    )
    repo = _repository(bucket_id=bucket_id, repository=repository)
    existing = repo.load(fact.counterparty_key)
    if existing is not None:
        if existing.territorial_scope is not fact.territorial_scope:
            raise CounterpartyEstablishmentConflictError(
                f"{existing.canonical_tax_identifier} is already confirmed as established in "
                f"{existing.territorial_scope.value}, and this assertion says "
                f"{fact.territorial_scope.value}; withdraw the confirmed fact before replacing it",
                context={
                    "canonical_tax_identifier": existing.canonical_tax_identifier,
                    "confirmed_scope": existing.territorial_scope.value,
                    "asserted_scope": fact.territorial_scope.value,
                },
            )
        if existing.note == fact.note:
            return existing
        corrected = existing.model_copy(update={"note": fact.note})
        repo.save(corrected)
        return corrected
    repo.save(fact)
    return fact


def forget_counterparty_establishment(
    *,
    bucket_id: str,
    tax_identifier: str,
    country_code: str | None = None,
    repository: CounterpartyEstablishmentRepository | None = None,
) -> bool:
    """Withdraw a confirmed establishment fact, returning whether one was held.

    The sanctioned way to correct an assertion, and deliberately a separate act
    from making one: withdrawing states that the earlier answer was wrong, which
    an overwrite would have performed silently.
    """
    key = counterparty_establishment_key(tax_identifier, country_code=country_code)
    if key is None:
        return False
    return _repository(bucket_id=bucket_id, repository=repository).delete(key)


def resolve_counterparty_establishment(
    *,
    bucket_id: str,
    tax_identifier: str | None,
    country_code: str | None = None,
    evidenced_scope: IvaTerritorialScope | None = None,
    repository: CounterpartyEstablishmentRepository | None = None,
) -> CounterpartyEstablishmentResolution:
    """Ask the store what is confirmed about this counterparty, and never guess.

    The last rung of the establishment ladder. It is consulted after the printed
    evidence has had its turn, so ``evidenced_scope`` is what those rungs
    produced: ``None`` when the paper settled nothing, which is the case this
    rung exists for.

    Every path that does not find a usable fact returns an EMPTY resolution.
    There is no territory-shaped default anywhere in this function, and the
    empty resolution is what makes the caller ask.

    Args:
        bucket_id: Active profile bucket.
        tax_identifier: The counterparty's identifier as printed, or ``None``
            when the document printed none. ``None`` resolves to nothing: a
            document with no counterparty identifier has no entity to remember
            anything about.
        country_code: The country the identifier is stated under, if any.
        evidenced_scope: What the printed evidence resolved to, when it
            resolved. Supplied so agreement can be recorded and disagreement
            surfaced; never used to write.
        repository: Injected store.

    Returns:
        The fact, a contradiction, or neither.
    """
    if not (tax_identifier or "").strip():
        return CounterpartyEstablishmentResolution()
    key = counterparty_establishment_key(tax_identifier or "", country_code=country_code)
    if key is None:
        return CounterpartyEstablishmentResolution()

    stored = _repository(bucket_id=bucket_id, repository=repository).load(key)
    if stored is None:
        return CounterpartyEstablishmentResolution()

    if evidenced_scope is not None and evidenced_scope is not stored.territorial_scope:
        return CounterpartyEstablishmentResolution(
            contradiction=CounterpartyEstablishmentContradiction(
                counterparty_key=stored.counterparty_key,
                canonical_tax_identifier=stored.canonical_tax_identifier,
                confirmed_scope=stored.territorial_scope,
                evidenced_scope=evidenced_scope,
                detail=(
                    f"{stored.canonical_tax_identifier} was confirmed as established in "
                    f"{stored.territorial_scope.value}, but this document's printed evidence places "
                    f"the same party in {evidenced_scope.value}; one of the two is wrong and "
                    f"neither may be preferred without a decision"
                ),
            ),
        )

    return CounterpartyEstablishmentResolution(fact=stored.declared_fact)
