"""Application service for the cross-period IVA prorrata register.

Thin orchestration over
:class:`adapters.persistence.profile.prorrata_register.ProrrataRegisterRepository`:
the caller declares a per-ejercicio prorrata entry, lists the register, and reads
one entry by ``(ejercicio, sector)`` key. The register is authoritative
profile-scoped state; this service owns no calculation, only the declare/list/get
surface. The LIVA arts. 102-106 compute substrate lives in the pure domain module
:mod:`domain.iva`, and the precedence-ladder resolution lives in
:mod:`domain.prorrata_register`.

The seed from the stamped prior settlement observation (art. 105.Uno), the
provenance-tagged art. 105.Dos/Tres overrides, and the settlement write-back are
built on top of this facade in later waves; this module is only the persistence
surface they compose over.

See Also:
    :mod:`domain.prorrata_register`
        Pure register records and the precedence-ladder resolver.
    :mod:`adapters.persistence.profile.prorrata_register`
        FINANCIAL secure-object repository that stores the profile-scoped
        register singleton.
    :mod:`domain.iva`
        Legal IVA prorrata substrate that supplies the definitive percentage
        and the art. 105.Cuatro regularisation cuota.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from ...adapters.persistence.profile.prorrata_register import (
    ProrrataRegisterRepository,
)
from ...core.prorrata_register import ProrrataProvisionalProvenance as _ProrrataProvisionalProvenance
from ...core.prorrata_register import ProrrataRegisterRegime as _ProrrataRegisterRegime
from ...domain.prorrata_register.register import (
    ProrrataProvisionalResolution,
    ProrrataRegister,
    ProrrataRegisterEntry,
    ProrrataRegisterValidationError,
    SectorDefinition,
    resolve_provisional_percentage,
)


class ProrrataRegisterService:
    """Declare, list, and read cross-period prorrata entries on the active profile."""

    def __init__(self, *, repository: ProrrataRegisterRepository | None = None) -> None:
        """Initialise the service, defaulting to the active-bucket register repository."""
        self._repository = repository if repository is not None else ProrrataRegisterRepository()

    def declare(self, entry: ProrrataRegisterEntry) -> ProrrataRegister:
        """Atomically add or replace ``entry`` by its ``(ejercicio, sector)`` key.

        Args:
            entry: The per-ejercicio prorrata entry to persist.

        Returns:
            The updated :class:`ProrrataRegister`.
        """
        return self._repository.upsert_entry(entry)

    def declare_especial_transition(self, entry: ProrrataRegisterEntry) -> ProrrataRegister:
        """Persist one current-period prorrata-especial option or revocation.

        The typed evidence is mandatory for this authoring path.  The register
        model enforces its regime, same-ejercicio mutual-exclusion, reference,
        and prior-especial lifecycle invariants during the repository's atomic
        singleton rebuild.
        """
        if entry.especial_transition is None:
            raise ProrrataRegisterValidationError("prorrata especial transition declaration requires typed evidence")
        return self._repository.upsert_entry(entry)

    def record_aeat_autorizada(
        self,
        *,
        ejercicio: int,
        provisional_percentage: Decimal,
        authorisation_reference: str,
        sector_id: str | None = None,
        regime: _ProrrataRegisterRegime = _ProrrataRegisterRegime.GENERAL,
    ) -> ProrrataRegister:
        """Record an art. 105.Dos AEAT-authorised provisional prorrata override.

        Args:
            ejercicio: Filing year whose provisional prorrata is authorised.
            provisional_percentage: AEAT-authorised provisional deduction percentage.
            authorisation_reference: Operator-held reference for the AEAT authorisation.
            sector_id: Optional sector identifier for sectores diferenciados.
            regime: Prorrata regime in force for the entry. Defaults to general.

        Returns:
            The updated :class:`ProrrataRegister`.
        """
        entry = ProrrataRegisterEntry(
            ejercicio=ejercicio,
            regime=regime,
            especial_transition=None,
            sector_id=sector_id,
            provisional_percentage=provisional_percentage,
            provisional_provenance=_ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
            authorisation_reference=authorisation_reference,
        )
        return self.declare(entry)

    def record_inicio_actividad(
        self,
        *,
        ejercicio: int,
        provisional_percentage: Decimal,
        proposal_reference: str,
        sector_id: str | None = None,
        regime: _ProrrataRegisterRegime = _ProrrataRegisterRegime.GENERAL,
    ) -> ProrrataRegister:
        """Record an art. 105.Tres inicio-de-actividades proposed prorrata override.

        Args:
            ejercicio: Filing year whose provisional prorrata is proposed for inicio.
            provisional_percentage: Proposed provisional deduction percentage.
            proposal_reference: Operator-held reference for the inicio proposal.
            sector_id: Optional sector identifier for sectores diferenciados.
            regime: Prorrata regime in force for the entry. Defaults to general.

        Returns:
            The updated :class:`ProrrataRegister`.
        """
        entry = ProrrataRegisterEntry(
            ejercicio=ejercicio,
            regime=regime,
            especial_transition=None,
            sector_id=sector_id,
            provisional_percentage=provisional_percentage,
            provisional_provenance=_ProrrataProvisionalProvenance.INICIO_ACTIVIDAD,
            authorisation_reference=proposal_reference,
        )
        return self.declare(entry)

    def declare_sector(self, definition: SectorDefinition) -> ProrrataRegister:
        """Atomically add or replace a differentiated-sector definition by ``sector_id``.

        The operator's art. 9.1.c partition is a legal judgment the ledger cannot
        infer, so it is declared here; once at least one sector is declared the
        register is sectorized and the per-sector apportionment routing applies
        (LIVA arts. 9.1.c / 101). Existing per-ejercicio entries are preserved.

        Args:
            definition: The differentiated-sector partition entry to persist.

        Returns:
            The updated :class:`ProrrataRegister`.
        """
        return self._repository.upsert_sector_definition(definition)

    def list_all(self) -> ProrrataRegister:
        """Return the full active-profile register.

        Returns:
            A :class:`ProrrataRegister`; empty when nothing has been declared.
        """
        return self._repository.load()

    def get(self, ejercicio: int, *, sector_id: str | None = None) -> ProrrataRegisterEntry | None:
        """Return the entry for a ``(ejercicio, sector)`` key, or ``None`` when absent.

        Args:
            ejercicio: Filing year to look up.
            sector_id: Sector identifier, or ``None`` for the whole-entity entry.

        Returns:
            The matching :class:`ProrrataRegisterEntry`, or ``None``.
        """
        return self._repository.load().entry_for(ejercicio, sector_id=sector_id)

    def resolve_provisional(
        self,
        ejercicio: int,
        *,
        sector_id: str | None = None,
        candidate_entries: Iterable[ProrrataRegisterEntry] = (),
    ) -> ProrrataProvisionalResolution:
        """Resolve the in-force provisional percentage through the single declared ladder.

        The persisted register carries at most one entry per ``(ejercicio,
        sector)``. Seed and override flows can supply same-key transient
        candidates so the application lookup still resolves through the domain
        ladder (`AEAT_AUTORIZADA` > `INICIO_ACTIVIDAD` >
        `CARRIED_PRIOR_DEFINITIVA`) rather than open-coding precedence here.

        Args:
            ejercicio: Filing year to resolve.
            sector_id: Sector identifier, or ``None`` for the whole-entity entry.
            candidate_entries: Additional same-key entries from seed/override
                resolution that have not necessarily been persisted yet.

        Returns:
            The domain :class:`ProrrataProvisionalResolution`.
        """
        register = self._repository.load()
        persisted = tuple(
            entry for entry in register.entries if entry.ejercicio == ejercicio and entry.sector_id == sector_id
        )
        transient = tuple(
            entry for entry in candidate_entries if entry.ejercicio == ejercicio and entry.sector_id == sector_id
        )
        return resolve_provisional_percentage((*persisted, *transient))
