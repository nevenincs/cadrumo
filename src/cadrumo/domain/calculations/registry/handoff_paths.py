"""Classify canonical and exceptional cross-model handoff paths."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ....core import STRICT_FROZEN_CONFIG, CasillaId
from ....core.aggregation import BindingSourceKind
from .authority import ValidatedRegistryAuthority
from .bindings import bound_casilla_binding_ids
from .handoffs import RegistryRelationHandoffAudit, audit_registry_relation_handoffs
from .ids import BindingId, LegalRefId, ModeloId, RelationId, RevisionId, SourceRefId
from .iva_wallet_relation_targets import is_iva_wallet_owned_relation_target

__all__ = [
    "HandoffPathClassification",
    "RegistryHandoffPathAudit",
    "RelationHandoffPathRecord",
    "audit_registry_handoff_paths",
]


class RelationHandoffPathRecord(BaseModel):
    """One validated relation target classified by its runtime owner."""

    model_config = STRICT_FROZEN_CONFIG

    target_modelo: ModeloId
    target_revision: RevisionId
    relation_id: RelationId
    target_binding: BindingId
    target_binding_source: BindingSourceKind
    target_casilla_ids: tuple[CasillaId, ...]
    classification: Literal["canonical_relation_prefill", "iva_wallet_exception", "non_canonical"]
    resolver_owner: Literal["relation_mesh", "iva_wallet", "unresolved"]
    parallel_path: bool
    parallel_binding_ids: tuple[BindingId, ...] = ()
    parallel_casilla_ids: tuple[CasillaId, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    target_binding_legal_refs: tuple[LegalRefId, ...] = ()
    target_binding_source_refs: tuple[SourceRefId, ...] = ()


class HandoffPathClassification(BaseModel):
    """Finite counts for canonical, exceptional, and parallel handoff paths."""

    model_config = STRICT_FROZEN_CONFIG

    total: int = Field(ge=0)
    canonical_relation_prefill: int = Field(ge=0)
    iva_wallet_exception: int = Field(ge=0)
    non_canonical: int = Field(ge=0)
    parallel: int = Field(ge=0)


class RegistryHandoffPathAudit(BaseModel):
    """Authority-validated handoff-path inventory with preserved provenance."""

    model_config = STRICT_FROZEN_CONFIG

    records: tuple[RelationHandoffPathRecord, ...]

    @property
    def relation_count(self) -> int:
        """Return the number of relation targets classified."""
        return len(self.records)

    @property
    def classification(self) -> HandoffPathClassification:
        """Return finite counts without changing individual provenance rows."""
        return HandoffPathClassification(
            total=self.relation_count,
            canonical_relation_prefill=sum(
                record.classification == "canonical_relation_prefill" for record in self.records
            ),
            iva_wallet_exception=sum(record.classification == "iva_wallet_exception" for record in self.records),
            non_canonical=sum(record.classification == "non_canonical" for record in self.records),
            parallel=sum(record.parallel_path for record in self.records),
        )

    @property
    def by_revision(self) -> dict[tuple[ModeloId, RevisionId], tuple[RelationHandoffPathRecord, ...]]:
        """Group path rows by target revision."""
        grouped: dict[tuple[ModeloId, RevisionId], list[RelationHandoffPathRecord]] = {}
        for record in self.records:
            grouped.setdefault((record.target_modelo, record.target_revision), []).append(record)
        return {key: tuple(value) for key, value in grouped.items()}


def audit_registry_handoff_paths(authority: ValidatedRegistryAuthority) -> RegistryHandoffPathAudit:
    """Classify validated relation paths without inventing semantic repairs.

    The :class:`ValidatedRegistryAuthority` passed as ``authority`` validates the
    registry before any path is read, and remains the authority for rejecting a
    non-canonical relation/previous-filing collision. This audit only projects the validated
    topology and records the one accepted M303 IVA-wallet exception. A parallel
    path is also reported when a target casilla carries a second direct
    ``previous_filing`` binding.
    """
    authority.validate_registry()
    relation_inventory: RegistryRelationHandoffAudit = audit_registry_relation_handoffs(
        authority.modelos,
        authority.catalogues,
        source_root=authority.source_root,
    )
    records: list[RelationHandoffPathRecord] = []
    for inventory_record in relation_inventory.records:
        modelo = authority.modelo(str(inventory_record.target_modelo))
        revision = modelo.revisions[inventory_record.target_revision]
        bindings_by_id = {binding.id: binding for binding in revision.bindings}
        target_binding = bindings_by_id[inventory_record.target_binding]
        previous_filing_binding_ids = {
            binding.id for binding in revision.bindings if binding.source is BindingSourceKind.PREVIOUS_FILING
        }
        parallel_binding_ids: set[BindingId] = set()
        parallel_casilla_ids: set[CasillaId] = set()
        for casilla in revision.casillas:
            if casilla.id not in inventory_record.target_casilla_ids:
                continue
            competing = set(bound_casilla_binding_ids(casilla)).intersection(previous_filing_binding_ids)
            competing.discard(inventory_record.target_binding)
            if competing:
                parallel_casilla_ids.add(casilla.id)
                parallel_binding_ids.update(competing)
        wallet_owned = is_iva_wallet_owned_relation_target(
            modelo_id=str(inventory_record.target_modelo),
            revision_id=str(inventory_record.target_revision),
            relation_id=str(inventory_record.relation_id),
            target_binding=str(inventory_record.target_binding),
        )
        if wallet_owned:
            classification: Literal["canonical_relation_prefill", "iva_wallet_exception", "non_canonical"] = (
                "iva_wallet_exception"
            )
            resolver_owner: Literal["relation_mesh", "iva_wallet", "unresolved"] = "iva_wallet"
        elif inventory_record.target_binding_source is BindingSourceKind.RELATION_PREFILL:
            classification = "canonical_relation_prefill"
            resolver_owner = "relation_mesh"
        else:
            classification = "non_canonical"
            resolver_owner = "unresolved"
        records.append(
            RelationHandoffPathRecord(
                target_modelo=inventory_record.target_modelo,
                target_revision=inventory_record.target_revision,
                relation_id=inventory_record.relation_id,
                target_binding=inventory_record.target_binding,
                target_binding_source=target_binding.source,
                target_casilla_ids=inventory_record.target_casilla_ids,
                classification=classification,
                resolver_owner=resolver_owner,
                parallel_path=bool(parallel_binding_ids)
                or (target_binding.source is BindingSourceKind.PREVIOUS_FILING and not wallet_owned),
                parallel_binding_ids=tuple(sorted(parallel_binding_ids)),
                parallel_casilla_ids=tuple(sorted(parallel_casilla_ids)),
                legal_refs=inventory_record.legal_refs,
                source_refs=inventory_record.source_refs,
                target_binding_legal_refs=inventory_record.target_binding_legal_refs,
                target_binding_source_refs=inventory_record.target_binding_source_refs,
            ),
        )
    return RegistryHandoffPathAudit(records=tuple(records))
