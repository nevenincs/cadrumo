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
digest of :func:`~application.ledger.identity_roles.canonical_identity_token` — the same
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
    :class:`~application.ledger.classification_assembly.DeclaredFacts`
        The one channel a supplied fact reaches the criteria assembly through.
        This module produces a member of it and opens no second route.
    :func:`~application.ledger.identity_roles.canonical_identity_token`
        The identifier authority the counterparty key is derived from.
    :class:`~domain.iva.IvaTerritorialScope`
        The territory a confirmed fact carries.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, override

from pydantic import BaseModel, Field, model_validator

from ...adapters.persistence.storage.envelope._secure_repository import SecureBoundRepository
from ...adapters.persistence.storage.secure_object_namespaces import LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE
from ...core.classification.policies import SensitivityClass
from ...core.classifier_input_source import ClassifierInputSource
from ...core.errors.hierarchy import CadrumoError
from ...core.hashing import sha256_hex
from ...core.identity import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.clock import now
from ...domain.iva.classification import IvaTerritorialScope
from ...domain.iva.schema import EUMemberState
from .classification_assembly import DeclaredFact
from .preconditions import LedgerPreconditionCondition, LedgerPreconditionErrorMixin, ledger_no_recovery_verdict

if TYPE_CHECKING:
    from typing import Self

__all__ = [
    "ConfirmedCounterpartyFacts",
    "ConfirmedCounterpartyFactsInputError",
    "ConfirmedCounterpartyFactsRepository",
    "ConfirmedCounterpartyResolution",
    "CounterpartyEstablishmentConflictError",
    "CounterpartyEstablishmentContradiction",
    "confirmed_counterparty_facts_key",
    "forget_confirmed_counterparty_facts",
    "record_confirmed_counterparty_facts",
    "resolve_confirmed_counterparty_facts",
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
    from .identity_roles import canonical_identity_token

    return canonical_identity_token(value, country_code=country_code)


class ConfirmedCounterpartyFactsInputError(LedgerPreconditionErrorMixin, CadrumoError):
    """Raised when a counterparty establishment assertion is not storable."""


class CounterpartyEstablishmentConflictError(CadrumoError):
    """Raised when an assertion contradicts the one already confirmed for a counterparty."""


def confirmed_counterparty_facts_key(
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
            document says. ``None`` asks the identifier's own prefix, matching
            the identifier authority — an unqualified identifier on a Spanish
            invoice is Spanish, a prefixed intra-community one names its own
            Member State, and a foreign one printed without its prefix simply
            does not verify.

            That distinction is load-bearing here rather than cosmetic. While
            the absence defaulted to Spain, a foreign counterparty whose
            document printed a prefixed IVA number and no address country got
            no key at all — so no confirmed establishment fact could be stored
            for them and none could be retrieved, disabling the ladder's
            remembered-fact rung for exactly the population the
            intra-community and export treatment exists for.

    Returns:
        The 64-character key, or ``None`` when the identifier does not verify.
    """
    token = _canonical_identity_token(tax_identifier, country_code=country_code)
    if token is None:
        return None
    return sha256_hex(token.encode())


class ConfirmedCounterpartyFacts(BaseModel):
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
        identification_state: The Member State that IVA-identifies this
            counterparty, when the operator has confirmed one. A DIFFERENT fact
            from :attr:`territorial_scope`, which is where the party is: Ley
            37/1992 art. 25 exempts on the registration, arts. 69-70 govern the
            place, and the two diverge in real trade. Neither is ever read for
            the other.

            ``None`` means unanswered, never "identified nowhere" and above all
            never "identified in Spain". A decision needing it refuses with a
            review item rather than reading the territory beside it.
        note: What the operator relied on, in their own words. Empty when they
            said nothing.
    """

    model_config = STRICT_FROZEN_CONFIG

    counterparty_key: ContentDigest
    canonical_tax_identifier: str = Field(min_length=1)
    territorial_scope: IvaTerritorialScope | None = None
    identification_state: EUMemberState | None = None
    source: ClassifierInputSource
    asserted_by: str = Field(min_length=1)
    asserted_at: datetime
    note: str = ""

    @model_validator(mode="after")
    def _only_an_operator_may_confirm(self) -> Self:
        """Refuse a fact this store is not the home for.

        ``source`` is required rather than defaulted so a persisted record
        states its provenance explicitly, and it is constrained rather than free
        so the store cannot quietly become a cache of document readings.

        A document-sourced territory is rung one or two of the ladder, re-read
        from each document's own page; remembering one here would answer later
        documents as though an operator had confirmed it, and would take the
        contradiction channel offline for exactly the population it protects.

        The identification axis inherits that rule, and inherits it MORE
        strongly rather than merely by symmetry. Ingestion reads identification
        TERMINALLY from a printed IVA prefix -- read once and treated as
        settled, with no later rung to revise it -- so a document-read
        identification cached here would answer every subsequent document as
        though an operator had confirmed the registration. That registration is
        the claim Ley 37/1992 art. 25 exempts on, so the value this store must
        refuse is precisely the one an exemption turns on.

        Do not relax this to "any source" for the identification axis. A second
        axis with weaker provenance rules than the one beside it would let the
        store answer as an assertion something no operator ever asserted.
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
        asserted_by: str,
        territorial_scope: IvaTerritorialScope | None = None,
        identification_state: EUMemberState | None = None,
        country_code: str | None = None,
        note: str = "",
        asserted_at: datetime | None = None,
    ) -> Self:
        """Build a fact for one counterparty, refusing an identifier with no identity.

        Raises:
            ConfirmedCounterpartyFactsInputError: When the identifier does not
                verify, so there is nothing stable to key the fact to.
        """
        token = _canonical_identity_token(tax_identifier, country_code=country_code)
        if token is None:
            raise ConfirmedCounterpartyFactsInputError(
                translated_message="errors.refused.refused_ledger_counterparty_establishment_input",
                context={"tax_identifier": tax_identifier, "country_code": country_code},
                precondition_verdict=ledger_no_recovery_verdict(
                    LedgerPreconditionCondition.COUNTERPARTY_IDENTIFIER_VALID,
                    facts={"counterparty_identifier_valid": False},
                ),
            )
        return cls(
            counterparty_key=sha256_hex(token.encode()),
            canonical_tax_identifier=token,
            territorial_scope=territorial_scope,
            identification_state=identification_state,
            source=ClassifierInputSource.OPERATOR_ASSERTION,
            asserted_by=asserted_by,
            asserted_at=asserted_at or now(),
            note=note,
        )

    @model_validator(mode="after")
    def _answers_at_least_one_question(self) -> ConfirmedCounterpartyFacts:
        """Refuse a record that confirms nothing.

        Both axes are optional because they are independent -- an operator may
        know which State IVA-identifies a counterparty without knowing where it
        is established, and the reverse. Neither answered is not a narrower
        assertion, it is an empty one, and an empty record is worse than no
        record: it addresses a counterparty, occupies the key, and answers every
        later question with silence that reads as a confirmed absence.
        """
        if self.territorial_scope is None and self.identification_state is None:
            message = (
                "a confirmed counterparty record must answer at least one of the "
                "territorial scope or the identification state"
            )
            raise ValueError(message)
        return self

    @property
    def declared_fact(self) -> DeclaredFact[IvaTerritorialScope] | None:
        """Return this fact in the form the criteria assembly consumes, or ``None``.

        The value and its attribution travel together, so a classification
        standing on a remembered assertion records that an operator said so —
        not that a document did.

        ``None`` when the operator answered the identification and left the
        territory open. That is a question NOT ASKED, and it must reach the
        assembly as a missing input rather than as any territory: the mainland is
        the majority answer, so a default here would be invisible in testing
        while placing Canarian and Ceutan counterparties inside a territory their
        operations are not subject to.
        """
        if self.territorial_scope is None:
            return None
        return DeclaredFact[IvaTerritorialScope](value=self.territorial_scope, source=self.source)

    @property
    def declared_identification(self) -> DeclaredFact[EUMemberState] | None:
        """Return the confirmed identification in the assembly's channel, or ``None``.

        ``None`` when the operator has not answered it. A caller must not read
        that as an answer -- it is the absence the review item exists for.
        """
        if self.identification_state is None:
            return None
        return DeclaredFact[EUMemberState](value=self.identification_state, source=self.source)


class ConfirmedCounterpartyFactsRepository(SecureBoundRepository[ConfirmedCounterpartyFacts]):
    """Encrypted profile-local store of confirmed counterparty establishment facts.

    The namespace, its :class:`SensitivityClass`, schema version and object-key
    contract all come from
    :data:`~adapters.persistence.storage.LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE`,
    so the record's confidentiality tier is declared once beside the namespace
    rather than restated here.
    Writes go through the shared single-writer envelope primitive rather than
    beside it, so a record here gets the same atomicity and encryption every
    other bucket-scoped record gets.
    """

    namespace: ClassVar[str] = LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = ConfirmedCounterpartyFacts

    @override
    def extract_identifier(self, payload: ConfirmedCounterpartyFacts) -> str:
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

    counterparty_key: ContentDigest
    canonical_tax_identifier: str = Field(min_length=1)
    confirmed_scope: IvaTerritorialScope
    evidenced_scope: IvaTerritorialScope
    detail: str = Field(min_length=1)


class ConfirmedCounterpartyResolution(BaseModel):
    """What the store had to say about one counterparty on one document.

    Three states, and "probably" is not one of them: a usable fact, a
    contradiction, or neither. The two populated fields are mutually exclusive
    by construction — a contradicted resolution carries no fact, so a caller
    reading ``fact`` cannot proceed on a value the evidence disputes.

    Attributes:
        fact: The remembered assertion, in the channel the assembly consumes.
            ``None`` when nothing was confirmed for this counterparty, when the
            identifier had no identity, or when the evidence contradicts it.
        identification: The confirmed Member State of IVA identification, in the
            same channel. ``None`` when the operator has not answered it, which
            is independent of whether the territory was answered -- the two are
            different questions about the same entity and either may stand
            alone. A caller must not read this ``None`` as "identified nowhere".
        contradiction: The disagreement, when there is one.
    """

    model_config = STRICT_FROZEN_CONFIG

    fact: DeclaredFact[IvaTerritorialScope] | None = None
    identification: DeclaredFact[EUMemberState] | None = None
    contradiction: CounterpartyEstablishmentContradiction | None = None

    @property
    def contradicted(self) -> bool:
        """Return whether the evidence disputes the confirmed fact."""
        return self.contradiction is not None


def _repository(
    *,
    bucket_id: str,
    repository: ConfirmedCounterpartyFactsRepository | None,
) -> ConfirmedCounterpartyFactsRepository:
    """Return the injected repository, or one bound to ``bucket_id``."""
    if repository is not None:
        return repository
    return ConfirmedCounterpartyFactsRepository(bucket_id=bucket_id)


def record_confirmed_counterparty_facts(
    *,
    bucket_id: str,
    tax_identifier: str,
    asserted_by: str,
    territorial_scope: IvaTerritorialScope | None = None,
    identification_state: EUMemberState | None = None,
    country_code: str | None = None,
    note: str = "",
    asserted_at: datetime | None = None,
    repository: ConfirmedCounterpartyFactsRepository | None = None,
) -> ConfirmedCounterpartyFacts:
    """Confirm where a counterparty is established, once, for every later document.

    Idempotent on the whole record rather than on the key alone. A retry
    carrying the same territory returns the STORED fact unchanged — the original
    ``asserted_at`` and ``asserted_by`` survive, because re-stamping them would
    make a repeated call look like a fresh confirmation. A call carrying a
    DIFFERENT territory refuses: overwriting would silently discard an answer
    the operator gave, and quietly reclassify every invoice already derived
    under it.

    The identification axis takes the same conflict rule, with one asymmetry
    that is not a softening. Supplying an identification where NONE is stored is
    an ADDITION -- the operator is answering a second question about the same
    entity, not replacing an answer -- so it is written through. Supplying a
    DIFFERENT one refuses exactly as a territory would. Supplying none leaves a
    stored answer standing, because ``None`` is an unasked question and reading
    it as "identified nowhere" would let a partial retry silently withdraw a
    fact art. 25 turns on.

    A same-key call differing only in ``note`` is a genuine correction of free
    prose and is written through, since no classification stands on it.

    Args:
        bucket_id: Active profile bucket.
        tax_identifier: The counterparty's identifier as printed.
        territorial_scope: The territory the operator confirms.
        asserted_by: Operator identity making the claim.
        identification_state: The Member State that IVA-identifies the
            counterparty, when the operator answers it. ``None`` does not
            answer the question and never erases a stored answer.
        country_code: The country the identifier is stated under, if any.
        note: What the operator relied on. Free prose, never consulted.
        asserted_at: Override clock, for deterministic tests.
        repository: Injected store.

    Returns:
        The persisted fact, or the pre-existing one on an idempotent retry.

    Raises:
        ConfirmedCounterpartyFactsInputError: When the identifier does not verify.
        CounterpartyEstablishmentConflictError: When a different territory, or
            a different identification, is already confirmed for this
            counterparty.
    """
    fact = ConfirmedCounterpartyFacts.create(
        tax_identifier=tax_identifier,
        territorial_scope=territorial_scope,
        asserted_by=asserted_by,
        identification_state=identification_state,
        country_code=country_code,
        note=note,
        asserted_at=asserted_at,
    )
    repo = _repository(bucket_id=bucket_id, repository=repository)
    existing = repo.load(fact.counterparty_key)
    if existing is not None:
        # Compared only where BOTH answers exist. A stored territory the new
        # assertion leaves open is not a disagreement -- it is a narrower
        # assertion, and refusing it would make an operator answering the
        # identification alone unable to do so for any counterparty already
        # confirmed. An assertion that CHANGES a stored territory still refuses.
        if (
            existing.territorial_scope is not None
            and fact.territorial_scope is not None
            and existing.territorial_scope is not fact.territorial_scope
        ):
            raise CounterpartyEstablishmentConflictError(
                translated_message="errors.refused.refused_ledger_counterparty_establishment_conflict",
                context={
                    "canonical_tax_identifier": existing.canonical_tax_identifier,
                    "confirmed_scope": existing.territorial_scope.value,
                    "asserted_scope": fact.territorial_scope.value,
                },
            )
        if (
            fact.identification_state is not None
            and existing.identification_state is not None
            and existing.identification_state is not fact.identification_state
        ):
            raise CounterpartyEstablishmentConflictError(
                translated_message="errors.refused.refused_ledger_counterparty_establishment_conflict",
                context={
                    "canonical_tax_identifier": existing.canonical_tax_identifier,
                    "confirmed_identification_state": existing.identification_state.value,
                    "asserted_identification_state": fact.identification_state.value,
                },
            )
        # An identification arriving where none was stored ANSWERS a question
        # rather than replacing an answer, so it is written through. A call that
        # supplies none leaves the stored one standing: `None` is an unasked
        # question, and treating it as an answer would let a retry that only
        # meant to correct a note silently withdraw the registration fact.
        added_identification = fact.identification_state is not None and existing.identification_state is None
        if existing.note == fact.note and not added_identification:
            return existing
        update: dict[str, object] = {"note": fact.note}
        if added_identification:
            update["identification_state"] = fact.identification_state
        corrected = existing.model_copy(update=update)
        repo.save(corrected)
        return corrected
    repo.save(fact)
    return fact


def forget_confirmed_counterparty_facts(
    *,
    bucket_id: str,
    tax_identifier: str,
    country_code: str | None = None,
    repository: ConfirmedCounterpartyFactsRepository | None = None,
) -> bool:
    """Withdraw a confirmed establishment fact, returning whether one was held.

    The sanctioned way to correct an assertion, and deliberately a separate act
    from making one: withdrawing states that the earlier answer was wrong, which
    an overwrite would have performed silently.
    """
    key = confirmed_counterparty_facts_key(tax_identifier, country_code=country_code)
    if key is None:
        return False
    return _repository(bucket_id=bucket_id, repository=repository).delete(key)


def resolve_confirmed_counterparty_facts(
    *,
    bucket_id: str,
    tax_identifier: str | None,
    country_code: str | None = None,
    evidenced_scope: IvaTerritorialScope | None = None,
    repository: ConfirmedCounterpartyFactsRepository | None = None,
) -> ConfirmedCounterpartyResolution:
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
        return ConfirmedCounterpartyResolution()
    key = confirmed_counterparty_facts_key(tax_identifier or "", country_code=country_code)
    if key is None:
        return ConfirmedCounterpartyResolution()

    stored = _repository(bucket_id=bucket_id, repository=repository).load(key)
    if stored is None:
        return ConfirmedCounterpartyResolution()

    if (
        evidenced_scope is not None
        and stored.territorial_scope is not None
        and evidenced_scope is not stored.territorial_scope
    ):
        return ConfirmedCounterpartyResolution(
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

    return ConfirmedCounterpartyResolution(
        fact=stored.declared_fact,
        identification=stored.declared_identification,
    )
