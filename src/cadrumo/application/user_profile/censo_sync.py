"""Censo-derived profile signals, and the censal-read reconciliation.

Two things live here. The first is the read-only projection the ledger
proportional-deduction path consumes: the home-office afectación ratio
derived from the operator-declared ``vivienda_office`` m² facts on the
encrypted profile.

The second is the censal autofill: AEAT publishes the taxpayer's own
censal state at the *Mis Datos Censales* consulta, and
:func:`censal_facts_from_read` projects that read onto declared profile
paths so an operator does not retype what the authority already holds.
:func:`reconcile_censal_read` splits the projection against what the
record already carries — adopting only paths the operator left blank and
reporting every disagreement instead of overwriting a declared answer —
and the canonical ``user-profile.censo-review`` operation commits its encrypted
reviewed operand through the single cotejo apply authority.

``CENSO_SOURCE_TAG`` marks an AEAT-verified censo fact and the overview
calendar reads it to decide whether censo enrolment is verified. It was
dormant for as long as nothing stamped it; the censal read is what
finally does, so a profile carrying these facts drops the
``censo.enrolment_unverified`` advisory for censo-derived obligations.
That is correct only because the consulta is an official AEAT read —
anything parsed out of an operator-supplied artefact or a Censos WEB
editing surface earns the non-official token instead, never this one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.identity import IdentityError, validate_spanish_tax_id
from ...core.logging import get_logger
from ...domain.user_profile.values import UserProfileFact
from .censal_observation import CensalObservation, CensalObservationAddress
from .censo_errors import CensoSyncError

if TYPE_CHECKING:
    from ...domain.user_profile.values import UserProfileRecord
    from .profile_record_repository import ProfileRecordRepository
    from .projections import EffectiveFact

CENSO_SOURCE_TAG: Final = "aeat_censo_read"
"""``UserProfileFact.source`` value marking an AEAT-verified censo fact."""

_log = get_logger(__name__)

#: The profile's fiscal identity. Read from the censal projection to decide
#: OWNERSHIP of the read, and deliberately not adoptable — see below.
_TAX_ID_PATH: Final = "identity.tax_id"

#: Declared profile paths the censal consulta can fill, in emit order. Every
#: entry is a key declared by the user-profile schema; the reconciliation
#: refuses to invent one.
#:
#: ``identity.tax_id`` is deliberately ABSENT. Once the ownership refusal is in
#: force the path can never carry information: a read either belongs to this
#: profile, in which case its identity can only agree and adopting it is a
#: no-op, or it does not, in which case the whole read refuses before any path
#: is considered. A field that cannot carry information should not sit in an
#: adoptable set, where its presence implies it might.
CENSAL_ADOPTABLE_PATHS: Final = (
    "contact.fiscal_address",
    "contact.postcode",
    "contact.fiscal_address_cadastral_reference",
)


class CensalIdentityMismatchError(CensoSyncError):
    """The read belongs to a different taxpayer than the profile."""


def _assert_read_belongs_to_this_profile(
    recorded_identity: EffectiveFact | None,
    incoming_tax_id: str | None,
) -> None:
    """Refuse a read whose fiscal identity is not the profile's.

    A read of another taxpayer is not a disagreement to adjudicate — it is a
    read that should never have been applied, so it refuses rather than
    producing divergence rows. Adopting it would write a second person's
    fiscal identity and address onto a profile used to file, silently and
    with nothing for the operator to see.

    The session-level identity guard does not close this even now that it
    covers every provider: it binds the SESSION to the profile, and a
    session legitimately bound to this taxpayer can still be pointed at a
    page describing another. Ownership of the READ is a separate question
    from ownership of the session, so it is answered separately here.

    A profile with NO fiscal identity refuses, and the two ways it can be
    missing are kept apart because they need different things said to the
    operator:

    * NEVER SET — the profile is still mid-setup. One mints with zero facts,
      since completeness is only gated once setup finishes, so this is not a
      half-built edge case but the ordinary state of an unfinished profile.
      The operator is told to record their fiscal ID and how.
    * CLEARED — the operator deleted a field the schema requires. Refused even
      when the read carries the identity the profile used to hold: this guard
      answers whether ownership can be CONFIRMED, and a deletion says nothing
      about whose record a page describes.

    There is no first-read allowance. Removing it is the point rather than an
    oversight: both states previously read as "nothing to compare against, so
    accept", which is the fail-open shape this guard exists to remove.

    Requiring the identity first takes nothing from the operator. The pull does
    not fill the fiscal ID — it only reads it to confirm ownership — so there
    is nothing to be gained by pulling before stating who you are, and the ID
    is required to complete the profile in any case.

    Both sides are compared in the CANONICAL form
    :func:`~core.identity.validate_spanish_tax_id` returns, rather than by an
    ad-hoc strip-and-upper. That single change closes the guard's two ways of
    being wrong at once, and they fail in opposite directions:

    * A malformed identity — wrong length, or a checksum that does not hold —
      used to confirm ownership as long as both sides carried the same
      malformed string. "These two strings are equal" is not the question this
      guard answers; whether they name a taxpayer at all is prior to it, and a
      profile identity that names nobody cannot confirm that a read describes
      the profile's taxpayer.
    * Two spellings of ONE identity — ``12345678-Z`` against ``12345678Z`` —
      used to refuse as a different taxpayer. AEAT prints the identity the way
      it prints it, and an operator types it the way they hold it; the
      canonical form is what decides whether they are the same person, so the
      punctuation is removed on both sides before they are compared rather
      than on neither.

    The canonicalisation is applied HERE and not on the parsed read: the
    adapter's ``nif`` is documented as AEAT's verbatim rendering and other
    readers depend on that, so this normalises for its own decision instead of
    rewriting the evidence.

    Raises:
        CensalIdentityMismatchError: When the profile records no fiscal
            identity, when either side's identity is malformed, when the read
            carries none, or when the two name different taxpayers.
    """
    if recorded_identity is None:
        raise CensalIdentityMismatchError(
            translated_message="application.user_profile.errors.censal_read_identity_unset",
        )
    if recorded_identity.value is None or not recorded_identity.value.strip():
        raise CensalIdentityMismatchError(
            translated_message="application.user_profile.errors.censal_read_identity_cleared",
        )
    if not (incoming_tax_id or "").strip():
        raise CensalIdentityMismatchError(
            translated_message="application.user_profile.errors.censal_read_identity_absent",
        )
    try:
        existing = validate_spanish_tax_id(recorded_identity.value)
    except IdentityError as exc:
        raise CensalIdentityMismatchError(
            translated_message="application.user_profile.errors.censal_read_identity_profile_malformed",
        ) from exc
    try:
        incoming = validate_spanish_tax_id(incoming_tax_id or "")
    except IdentityError as exc:
        raise CensalIdentityMismatchError(
            translated_message="application.user_profile.errors.censal_read_identity_read_malformed",
        ) from exc
    if incoming != existing:
        raise CensalIdentityMismatchError(
            translated_message="application.user_profile.errors.censal_read_identity_mismatch",
        )


class CensalReconciliation(BaseModel):
    """The split of a censal read against what the profile already holds.

    ``adopted`` are facts for paths the record left blank, safe to write.
    ``divergences`` are paths where AEAT and the operator disagree: the
    operator's declared answer stands and the authority's value is
    recorded as evidence, never silently substituted.
    """

    model_config = STRICT_FROZEN_CONFIG

    adopted: tuple[UserProfileFact, ...] = ()
    divergences: tuple[tuple[str, str], ...] = ()


def _compose_address(domicilio: CensalObservationAddress) -> str | None:
    """Render the decomposed censal address as one display string.

    AEAT splits the address across a dozen positional fields; the profile
    declares a single ``contact.fiscal_address`` string, so the parts are
    joined in the order AEAT prints them. Absent parts are skipped rather
    than rendered as gaps.
    """
    street = " ".join(
        part
        for part in (
            domicilio.tipo_via,
            domicilio.nombre_via,
            domicilio.tipo_numero,
            domicilio.numero_casa,
            domicilio.calificacion_numero,
            domicilio.bloque,
            domicilio.portal,
            domicilio.escalera,
            domicilio.planta,
            domicilio.puerta,
            domicilio.complemento,
        )
        if part and part.strip()
    ).strip()
    tail = " ".join(
        part for part in (domicilio.codigo_postal, domicilio.municipio, domicilio.provincia) if part and part.strip()
    ).strip()
    composed = ", ".join(part for part in (street, tail) if part)
    return composed or None


def censal_facts_from_read(result: CensalObservation) -> tuple[UserProfileFact, ...]:
    """Project an AEAT censal consulta read onto declared profile facts.

    Every emitted fact carries :data:`CENSO_SOURCE_TAG`, the declared
    provenance token for an AEAT-verified censal read, and targets a path
    the user-profile schema declares.

    Deliberately absent: ``identity.name`` and ``identity.surnames``. AEAT
    renders one combined *Apellidos y Nombre* field, and recovering the
    split requires assuming the Spanish two-surname convention. That
    assumption silently mangles any name not following it — a
    single-surname holder with two given names parses as two surnames and
    one given name, reversing the operator's identity. There is no
    authority in the read for where the boundary falls, so the projection
    declines to guess rather than write a plausible-looking wrong name.

    The fiscal identity is NOT projected. The reconciliation needs it to
    decide whether the read belongs to this profile at all, but it takes
    it from the read directly rather than from here: carrying it in this
    tuple made a collection named for adoption silently load-bearing for
    an ownership refusal, so removing a path from the tuple would have
    switched that refusal off with nothing failing.

    Args:
        result: The parsed censal consulta read.

    Returns:
        The projected facts in :data:`CENSAL_ADOPTABLE_PATHS` order,
        omitting any path the read left empty.
    """
    candidates: dict[str, str | None] = {
        "contact.fiscal_address": _compose_address(result.domicilio_fiscal),
        "contact.postcode": result.domicilio_fiscal.codigo_postal,
        "contact.fiscal_address_cadastral_reference": result.domicilio_fiscal.referencia_catastral,
    }
    return tuple(
        UserProfileFact(path=path, value=value, source=CENSO_SOURCE_TAG)
        for path in CENSAL_ADOPTABLE_PATHS
        if (value := (candidates[path] or "").strip())
    )


def reconcile_censal_read(
    record: UserProfileRecord | None,
    facts: Sequence[UserProfileFact],
    *,
    incoming_identity: str | None,
) -> CensalReconciliation:
    """Split projected censal facts into safe adoptions and reported disagreements.

    Every decision below is taken against the operator's own
    :class:`UserProfileRecord`, read as the ordered fact history rather than a
    flattened value map: which side wrote a path, and whether it was later
    cleared, are facts about that history and are invisible in a value-only
    projection.

    A path the record leaves blank is adopted. A path whose recorded value
    already equals the read is a no-op and is emitted as neither. A path
    where the two differ is decided by WHO wrote the recorded value:

    * an operator-declared value is reported as a divergence and left
      standing — an autofill must not overwrite a declared answer just
      because the authority disagrees;
    * a value a previous censal read adopted is REFRESHED, because there is
      no operator answer to protect. Both sides are the authority's, one
      stale and one current, so reporting it as a disagreement would both
      strand the profile on the old value forever and assert a conflict
      that does not exist. A censal address change is the likeliest reason
      to pull at all, so this is the path that keeps a profile current.

    A path the operator explicitly CLEARED is never re-adopted, whatever
    wrote it originally. A clear is a declaration — *I do not want this on
    my profile* — and it is the one form of declaration a value-only
    projection cannot show, because a cleared path still projects its
    previous value. The authority's value is reported as a divergence
    instead of being written back: the operator's deletion stands, and they
    still learn that AEAT holds something there, which matters because they
    file against AEAT's record and not against their profile.

    Comparison is exact after a whitespace strip. No per-field
    normalisation is applied: deciding that two differently-written
    cadastral references or postcodes mean the same thing is a guess about
    an authority's format, and a spurious divergence is recoverable by the
    operator where a silent equation of two genuinely different values is
    not.

    Args:
        record: The active profile record, or ``None`` for a fresh profile.
        facts: The projected censal facts, which are the adoptable paths
            and nothing else.
        incoming_identity: The fiscal identity the read carries, taken
            from the read itself. It is a parameter rather than something
            recovered from ``facts`` because the ownership refusal below
            depends on it: routing it through the projection made a
            collection named for adoption silently load-bearing for a
            guard, so removing a path from that collection would have
            switched the guard off with nothing failing.

    Returns:
        The :class:`CensalReconciliation` split.
    """
    from .projections import record_to_effective_facts

    existing = record_to_effective_facts(record)
    _assert_read_belongs_to_this_profile(existing.get(_TAX_ID_PATH), incoming_identity)
    adopted: list[UserProfileFact] = []
    divergences: list[tuple[str, str]] = []
    for fact in facts:
        effective = existing.get(fact.path)
        incoming = str(fact.value)
        if effective is None:
            # Never set: nothing of the operator's to protect.
            adopted.append(fact)
            continue
        current = effective.value
        if current is None:
            # Cleared. Whose deletion it was decides, exactly as it does
            # for a value: an operator's clear is an answer to protect, and
            # one this app wrote is not. Asking the same question of both
            # branches is the point — the value branch consulted provenance
            # and this one did not, so a clear the app wrote earned the
            # protection meant for an operator's decision and the path
            # would never have been re-populated.
            #
            # A clear must therefore SAY who wrote it. The default source is
            # the operator's, so a clear the app writes with no operator
            # intent behind it has to stamp itself with a machine token or
            # it lands here indistinguishable from a declaration. Every
            # machine-written clear in the tree today follows an operator
            # action — a descendant removed, a divergence row superseded —
            # so the default is honest for all of them, and this note is
            # for whoever writes the first one that is not.
            if effective.source == CENSO_SOURCE_TAG:
                adopted.append(fact)
            else:
                divergences.append((fact.path, incoming))
        elif not current.strip():
            adopted.append(fact)
        elif current.strip() == incoming.strip():
            continue
        elif effective.source == CENSO_SOURCE_TAG:
            adopted.append(fact)
        else:
            divergences.append((fact.path, incoming))
    return CensalReconciliation(adopted=tuple(adopted), divergences=tuple(divergences))


class CensoSyncService:
    """Read-only censo-derived signals for the active profile bucket.

    The service no longer captures, compares, or applies censo snapshots
    (the live scrape was retired); it exposes the single surviving
    read: the home-office afectación ratio the ledger ratios and
    preflight paths consume via :meth:`bound_raw_afectacion_ratio`,
    derived from the operator-declared ``vivienda_office`` m² facts the
    operator maintains through ``config profile edit``.
    """

    def __init__(
        self,
        *,
        bucket_id: str,
        profiles: ProfileRecordRepository | None = None,
    ) -> None:
        """Initialize the service for one profile bucket and record repository.

        Args:
            bucket_id: Profile bucket identifier; surrounding whitespace is
                removed before the non-blank check.
            profiles: Optional repository for profile-record reads. When it is
                omitted, the current-session repository is resolved on demand.
        """
        self._bucket_id = bucket_id.strip()
        if not self._bucket_id:
            raise CensoSyncError(translated_message="errors.censo.bucket_id_blank")
        self._profiles = profiles

    @property
    def bucket_id(self) -> str:
        """Return the normalized bucket identifier bound to this service."""
        return self._bucket_id

    def bound_raw_afectacion_ratio(self, *, profile_id: str) -> Decimal | None:
        """Return ``office_m2 / total_m2`` from the operator-declared profile facts.

        Used by the ledger ratios CLI and the manual-transaction
        classify path to apply the legally-effective
        :func:`cadrumo.application.ledger.ratios.censo_override_warning`
        and :func:`cadrumo.application.ledger.ratios.censo_business_pct_for`
        helpers without each consumer re-implementing the profile-fact
        lookup. Reads the encrypted profile record's canonical path-value
        projection — the same operator-declared facts ``config profile
        edit`` writes and the deadline engine hydrates — so updating the
        ``vivienda_office`` m² through the CLI drives this ratio directly.
        Returns ``None`` when the profile has no persisted record OR when
        either ``vivienda_office.total_m2`` / ``vivienda_office.office_m2``
        is absent / non-decimal / zero.
        """
        from ...domain.user_profile.errors import ProfileNotFoundError
        from .profile_record_repository import ProfileRecordRepository
        from .projections import record_to_path_values

        repository = self._profiles or ProfileRecordRepository.for_current_session(self._bucket_id)
        try:
            record = repository.load(profile_id)
        except ProfileNotFoundError:
            return None
        return _raw_afectacion_ratio(record_to_path_values(record))


def _raw_afectacion_ratio(censo_facts: Mapping[str, str]) -> Decimal | None:
    total_raw = censo_facts.get("vivienda_office.total_m2")
    office_raw = censo_facts.get("vivienda_office.office_m2")
    if total_raw is None or office_raw is None:
        return None
    try:
        total = Decimal(total_raw)
        office = Decimal(office_raw)
    except (InvalidOperation, ValueError):
        _log.debug("censo raw afectacion ratio ignored: non-decimal censo surface", exc_info=True)
        return None
    if total <= Decimal("0") or office < Decimal("0") or office > total:
        _log.debug("censo raw afectacion ratio ignored: invalid censo ratio bounds")
        return None
    return office / total


def bound_raw_afectacion_ratio_for_bucket(bucket_id: str) -> Decimal | None:
    """Return the bucket's own censo-declared ``office_m2 / total_m2``, if any.

    The bucket IS the profile for this question, so the two identifiers the
    service takes separately collapse to one. Two call sites had each spelled
    that collapse out, which is one place too many for a rule about which id
    means what.

    The CLI listing deliberately does NOT use this: it resolves a profile_id
    that can differ from the bucket, and folding it in here would quietly answer
    a different question than it asked.

    Args:
        bucket_id: The bucket whose profile facts are read.

    Returns:
        The raw afectación proportion, or ``None`` when the profile is absent or
        declares no usable m².
    """
    return CensoSyncService(bucket_id=bucket_id).bound_raw_afectacion_ratio(profile_id=bucket_id)


__all__ = [
    "CENSAL_ADOPTABLE_PATHS",
    "CENSO_SOURCE_TAG",
    "CensalReconciliation",
    "CensoSyncService",
    "bound_raw_afectacion_ratio_for_bucket",
    "censal_facts_from_read",
    "reconcile_censal_read",
]
