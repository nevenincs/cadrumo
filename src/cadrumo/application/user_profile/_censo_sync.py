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
and :func:`apply_censal_read` commits the result through the single
cotejo apply authority.

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

from ...core import STRICT_FROZEN_CONFIG
from ...core.logging import get_logger
from ...domain.user_profile import UserProfileFact
from ._censo_errors import CensoSyncError

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.sede import CensalDatosResult, CensalDomicilio
    from ...domain.user_profile import UserProfileRecord
    from ..workflow import WorkflowState
    from ._repository import UserProfileLifecycleRepository

CENSO_SOURCE_TAG: Final = "aeat_censo_read"
"""``UserProfileFact.source`` value marking an AEAT-verified censo fact."""

CENSO_DERIVED_SOURCE_TAG: Final = "aeat_censo_derived"
"""``UserProfileFact.source`` for facts derived from an AEAT-verified censo."""

_log = get_logger(__name__)

#: Declared profile paths the censal consulta can fill, in emit order. Every
#: entry is a key declared by the user-profile schema; the reconciliation
#: refuses to invent one.
CENSAL_ADOPTABLE_PATHS: Final = (
    "identity.tax_id",
    "contact.fiscal_address",
    "contact.postcode",
    "contact.fiscal_address_cadastral_reference",
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


def _compose_address(domicilio: CensalDomicilio) -> str | None:
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


def censal_facts_from_read(result: CensalDatosResult) -> tuple[UserProfileFact, ...]:
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

    Args:
        result: The parsed censal consulta read.

    Returns:
        The projected facts, in :data:`CENSAL_ADOPTABLE_PATHS` order,
        omitting any path the read left empty.
    """
    candidates: dict[str, str | None] = {
        "identity.tax_id": result.identity.nif,
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
) -> CensalReconciliation:
    """Split projected censal facts into safe adoptions and reported disagreements.

    A path the record leaves blank is adopted. A path whose recorded value
    already equals the read is a no-op and is emitted as neither. A path
    where the two differ is a divergence: the operator declared something
    and an autofill must not overwrite a declared answer just because the
    authority disagrees.

    Args:
        record: The active profile record, or ``None`` for a fresh profile.
        facts: The projected censal facts.

    Returns:
        The :class:`CensalReconciliation` split.
    """
    from ._projections import record_to_path_values

    existing = record_to_path_values(record)
    adopted: list[UserProfileFact] = []
    divergences: list[tuple[str, str]] = []
    for fact in facts:
        current = existing.get(fact.path)
        incoming = str(fact.value)
        if current is None or not current.strip():
            adopted.append(fact)
        elif current.strip() != incoming.strip():
            divergences.append((fact.path, incoming))
    return CensalReconciliation(adopted=tuple(adopted), divergences=tuple(divergences))


def apply_censal_read(state: WorkflowState, result: CensalDatosResult) -> WorkflowState:
    """Commit a censal consulta read onto the active profile.

    Routes through :func:`~cadrumo.application.user_profile.apply_cotejo`,
    the single censal apply authority, so the commit emits exactly one
    ``CENSO_APPLIED`` event and never opens a parallel write path.
    Disagreements ride the same ``censo.divergencia`` namespace the
    artefact cotejo uses, so an operator sees unadopted authority values
    through one surface regardless of which transport produced them.

    Args:
        state: The workflow state carrying the active profile.
        result: The parsed censal consulta read.

    Returns:
        The updated workflow state; the caller persists it.
    """
    from ._cotejo_apply import CensoDivergence, apply_cotejo

    reconciliation = reconcile_censal_read(state.active_profile_record(), censal_facts_from_read(result))
    return apply_cotejo(
        state,
        adopted=reconciliation.adopted,
        divergences=tuple(
            CensoDivergence(axis=axis, artefact_value=value, source=CENSO_SOURCE_TAG)
            for axis, value in reconciliation.divergences
        ),
    )


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
        profiles: UserProfileLifecycleRepository | None = None,
    ) -> None:
        self._bucket_id = bucket_id.strip()
        if not self._bucket_id:
            raise CensoSyncError(translated_message="errors.censo.bucket_id_blank")
        self._profiles = profiles

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def bound_raw_afectacion_ratio(self, *, profile_id: str) -> Decimal | None:
        """Return ``office_m2 / total_m2`` from the operator-declared profile facts.

        Used by the ledger ratios CLI and the manual-transaction
        classify path to apply the legally-effective
        :func:`cadrumo.application.ledger._ratios.censo_override_warning`
        and :func:`cadrumo.application.ledger._ratios.censo_business_pct_for`
        helpers without each consumer re-implementing the profile-fact
        lookup. Reads the encrypted profile record's canonical path-value
        projection — the same operator-declared facts ``config profile
        edit`` writes and the deadline engine hydrates — so updating the
        ``vivienda_office`` m² through the CLI drives this ratio directly.
        Returns ``None`` when the profile has no persisted record OR when
        either ``vivienda_office.total_m2`` / ``vivienda_office.office_m2``
        is absent / non-decimal / zero.
        """
        from ...domain.user_profile import ProfileNotFoundError
        from ._projections import record_to_path_values
        from ._repository import UserProfileLifecycleRepository

        repository = self._profiles or UserProfileLifecycleRepository(bucket_id=self._bucket_id)
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


__all__ = [
    "CENSAL_ADOPTABLE_PATHS",
    "CENSO_DERIVED_SOURCE_TAG",
    "CENSO_SOURCE_TAG",
    "CensalReconciliation",
    "CensoSyncService",
    "apply_censal_read",
    "censal_facts_from_read",
    "reconcile_censal_read",
]
