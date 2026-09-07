"""Project a calculation revision into its bundled ledger fact basis.

Three paths need the same bundle and for the same reason: a revision that
reaches a sealed state must carry the ledger facts it was computed from, or
nothing downstream can say whether the filing still matches the books. Verify
captures it at the moment it grants, the amendment path captures it at the
moment it stands in for verify, and the evidence-recapture verb rebuilds it
over facts that have not moved.

They differ only in which fingerprint the bundle is pegged to, so that is the
argument rather than the difference: verify and amend peg to a snapshot they
have just taken, and recapture pegs to the one already sealed. Everything else
-- which refs ground the bundle, which operator inputs become manual fact-basis
entries -- is one rule, and it lives here rather than being spelled out at each
call site, where two of the three copies had already drifted into being
maintained separately.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.irnr import M210GrossIncomeSourceMode
from ...domain.modelos.errors import ModeloValidationError
from ...domain.modelos.ledger_filing_snapshot import ManualFactBasisEntry
from ..aggregation.ledger_filing_snapshot import compute_ledger_filing_evidence

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from datetime import datetime

    from ...core.casilla_id import CasillaId
    from ...domain.calculations.registry.bindings import CasillaObservation
    from ...domain.modelos.calculation_revision import CalculationRevision
    from ...domain.modelos.ledger_filing_snapshot import LedgerFilingEvidence
    from ...domain.transactions.models import TransactionCatalogue


def normalised_observation_refs(
    observations: Iterable[CasillaObservation | None],
    field_name: str,
) -> tuple[str, ...]:
    """Return the distinct non-empty refs across ``observations``, refusing none.

    An empty result is refused rather than returned: a bundle grounded in no
    legal or source reference cannot be traced back to the authority it claims,
    and an empty tuple would look like a deliberate absence.
    """
    refs = tuple(
        dict.fromkeys(
            str(ref).strip()
            for observation in observations
            if observation is not None
            for ref in getattr(observation, field_name)
            if str(ref).strip()
        ),
    )
    if not refs:
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={"field_name": field_name, "observation_present": False},
        )
    return refs


def manual_fact_basis_entries(
    input_values_by_casilla_id: Mapping[CasillaId, str],
    observations: Iterable[CasillaObservation],
    *,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None,
) -> tuple[ManualFactBasisEntry, ...]:
    """Project a revision's operator casilla inputs into manual fact-basis entries.

    ``input_values_by_casilla_id`` holds the caller-supplied (operator-entered)
    casilla values that are not ledger-derived; each non-empty entry is part of
    the fact basis a filing artefact must explain. Blank values are skipped
    (they carry no fact). The M210 ledger-derived ``rendimientos_integros``
    input is deliberately excluded: it is present in the replay map so formula
    replay is exact, but its fact basis is the fingerprinted transaction
    evidence rather than a manual declaration.
    """
    observations_by_casilla_id = {observation.casilla_id: observation for observation in observations}
    return tuple(
        ManualFactBasisEntry(
            casilla_id=casilla,
            value=value,
            legal_refs=normalised_observation_refs((observations_by_casilla_id.get(casilla),), "legal_refs"),
            source_refs=normalised_observation_refs((observations_by_casilla_id.get(casilla),), "source_refs"),
        )
        for casilla, value in sorted(input_values_by_casilla_id.items())
        if value.strip()
        and not (
            m210_gross_income_source_mode is M210GrossIncomeSourceMode.LEDGER and casilla == "rendimientos_integros"
        )
    )


def capture_revision_ledger_evidence(
    *,
    revision: CalculationRevision,
    catalogue: TransactionCatalogue,
    snapshot_fingerprint: str,
    captured_at: datetime,
) -> LedgerFilingEvidence:
    """Bundle ``revision``'s fact basis, pegged to ``snapshot_fingerprint``.

    The contributor set is the revision's own ``source_transaction_ids``, so
    the bundle describes exactly the rows the calculation used. The caller
    supplies the fingerprint because that is the one thing the three callers
    legitimately disagree about: a fresh capture pegs to the snapshot it just
    took, while a recapture pegs to the one already sealed so the bundle stays
    bound to the facts the filing asserts.

    Args:
        revision: The revision whose fact basis is bundled.
        catalogue: The live transaction catalogue to project rows from.
        snapshot_fingerprint: The snapshot address this bundle belongs to.
        captured_at: Timestamp recorded on the bundle.

    Returns:
        The bundled :class:`LedgerFilingEvidence`.
    """
    grounded = bool(revision.source_transaction_ids)
    return compute_ledger_filing_evidence(
        source_transaction_ids=revision.source_transaction_ids,
        catalogue=catalogue,
        snapshot_fingerprint=snapshot_fingerprint,
        captured_at=captured_at,
        legal_refs=normalised_observation_refs(revision.observations, "legal_refs") if grounded else (),
        source_refs=normalised_observation_refs(revision.observations, "source_refs") if grounded else (),
        manual_entries=manual_fact_basis_entries(
            revision.input_values_by_casilla_id,
            revision.observations,
            m210_gross_income_source_mode=revision.m210_gross_income_source_mode,
        ),
    )


__all__ = [
    "capture_revision_ledger_evidence",
    "manual_fact_basis_entries",
    "normalised_observation_refs",
]
