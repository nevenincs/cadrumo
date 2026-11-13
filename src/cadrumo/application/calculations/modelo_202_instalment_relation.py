"""Credit a relation that reads one Modelo 202 instalment from that instalment's own resolution."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.relation_prefill_bindings import RelationPrefillProvider
from ...domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ...domain.calculations.registry.schema import RegistrySnapshot
from ..storage.calc_sheets.records import RelationValue, SheetRelationProvenance
from ..user_profile.profile_read_ports import ProfilePathValuesReadPort
from .modelo_200_instalment_credit import instalment_credit, settled_instalment

if TYPE_CHECKING:
    from ...domain.calculations.registry.applicability_modelo202 import Modelo202Modality
    from .modelo_202_instalment_resolution import Modelo202InstalmentResolver


def modelo_202_modality_for_bucket(
    bucket_id: str,
    *,
    filing_year: int,
    operation: PinnedAuthorityOperation,
    profile_path_values_reader: ProfilePathValuesReadPort,
) -> Modelo202Modality | None:
    """Derive the Modelo 202 modality of ``filing_year`` from the bucket's wizard-free profile projection.

    ``None`` when the bucket holds no profile. The rule is the single modality
    definition (:func:`modelo_202_modality_from_path_values`).
    """
    from ...domain.calculations.registry.applicability_modelo202 import modelo_202_modality_from_path_values

    values = profile_path_values_reader.load_path_values(bucket_id=bucket_id)
    if values is None:
        return None
    return modelo_202_modality_from_path_values(values, filing_year=filing_year, authority=operation)


def reads_modelo_202_instalment(snapshot: RegistrySnapshot, *, operation: PinnedAuthorityOperation) -> bool:
    """Return whether the snapshot carries a binding credited from a single Modelo 202 instalment."""
    return any(
        settled_instalment(provider, filing_year=snapshot.filing_year, operation=operation) is not None
        for _, provider in relation_prefill_bindings_for_period(snapshot.revision, period=snapshot.period)
    )


def instalment_relation_value(
    unresolved: RelationValue,
    provider: RelationPrefillProvider,
    *,
    filing_year: int,
    resolved_at: datetime,
    instalment_resolver: Modelo202InstalmentResolver | None,
    operation: PinnedAuthorityOperation,
) -> RelationValue | None:
    """Credit an unfolded Modelo 202 instalment binding from the instalment's own resolution.

    ``unresolved`` is the relation's unresolved value, which carries the registry
    relation's source identity and grounding. ``None`` when no resolver is bound
    or the binding does not read a single instalment, so the fold's other rules decide.
    """
    if instalment_resolver is None:
        return None
    instalment = settled_instalment(provider, filing_year=filing_year, operation=operation)
    if instalment is None:
        return None
    credit = instalment_credit(
        instalment_resolver(instalment),
        source_modelo=str(provider.source_modelo),
        source_casilla_ids=provider.declared_source_casilla_ids,
    )
    if credit.value is None:
        return RelationValue(
            relation=unresolved.relation,
            value=None,
            source_modelo=unresolved.source_modelo,
            source_casilla_ids=unresolved.source_casilla_ids,
            dependency_treatment=unresolved.dependency_treatment,
            legal_refs=unresolved.legal_refs,
            source_refs=unresolved.source_refs,
            note=credit.note,
        )
    return RelationValue(
        relation=unresolved.relation,
        value=credit.value,
        provenance=SheetRelationProvenance.OPERATOR_MANUAL,
        source_modelo=unresolved.source_modelo,
        source_casilla_ids=unresolved.source_casilla_ids,
        dependency_treatment=unresolved.dependency_treatment,
        legal_refs=tuple(dict.fromkeys((*unresolved.legal_refs, *credit.legal_refs))),
        source_refs=unresolved.source_refs,
        source_filing_year=instalment.filing_year,
        source_periods=(instalment.registry_token,),
        resolved_at=resolved_at,
        note=credit.note,
    )


__all__ = [
    "instalment_relation_value",
    "modelo_202_modality_for_bucket",
    "reads_modelo_202_instalment",
]
