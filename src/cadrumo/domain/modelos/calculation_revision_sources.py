"""Persisted calculation source provenance and unresolved source conditions."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Final, Literal

from pydantic import BaseModel, Field, model_validator

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_CONFIG
from .errors import ModeloValidationError


class CalculationSourceRef(BaseModel):
    """One resolver-level source-object trace persisted on a calculation revision.

    The calculation source mesh (``cadrumo.application.aggregation``) resolves each
    registry binding source through an enrolled resolver and produces a typed
    ``CalculationSourceProvenance`` row per contributing source object. This is
    the DOMAIN-side, persistence-shaped projection of that provenance: it carries
    exactly the resolverâ†’source-objectâ†’fingerprint trace that lets an audit reader
    reconstruct which resolver mesh and which upstream source objects produced a
    revision, and whether those objects have since drifted.

    It deliberately does NOT carry ``legal_refs`` / ``source_refs`` â€” those are the
    per-casilla regulatory grounding already carried by
    :class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation` on the same
    revision; duplicating them here would fragment the grounding across two
    surfaces.

    ``source_casilla_ids`` is NOT grounding and the rationale above does
    not extend to it. It is a subject IDENTITY -- which casilla(s), if any,
    this source object's resolution feeds -- and nothing else on the revision
    carries it for the general (non-row-materialized) case; dropping it here
    was an omission the application-side
    :class:`~cadrumo.application.aggregation.source_mesh.CalculationSourceProvenance` did
    not itself make (it already carries the field). An empty tuple is honest
    when the originating resolver call site did not associate this row with a
    casilla â€” it is not fabricated as a claim of "no subject", only carried as
    "not linked at resolution time".

    Attributes:
        resolver_id: Exact canonical resolver identity that produced this row.
        resolved_binding_source: Canonical binding source owned by the resolver.
        contributor_source_kind: Upstream taxonomy token for this source node.
        contributor_binding_source: Canonical :class:`BindingSourceKind` when
            ``contributor_source_kind`` belongs to the binding taxonomy; ``None``
            for an external or non-binding contributor.
        lineage_role: Whether this row is the resolver-owned primary or supporting contributor.
        source_ref: Stable reference to the contributing source object
            (e.g. ``collectible_invoice:{invoice_id}``).
        fingerprint: Data-dependent digest of the contributing source object when
            the resolver produced one; ``None`` when the resolver emits a
            reference without a content digest.
        source_casilla_ids: Casilla identities this source object's resolution
            feeds, when the originating resolver associated one; empty when it
            did not. Carried straight from
    :attr:`~cadrumo.application.aggregation.source_mesh.CalculationSourceProvenance.source_casilla_ids`.
        dependency_treatment: The registry's declared dependency treatment for
            this carry, empty when the revision declares none. Unlike
            ``legal_refs`` / ``source_refs`` this carries no grounding duplicated
            elsewhere on the revision â€” it is the sole persisted trace of whether
            a carry is a ``factual_evidence`` fact to reconcile against or a
            ``direct_annual_settlement`` figure that settles the return, and an
            audit reader has no other way to recover that distinction after the
            fact. Carried here rather than gated here: the value is NOT withheld
            on the basis of its treatment.
        source_filing_year: The filing year of the source this node rests on,
            when the resolver recorded one: the source modelo's year for a
            relation carry, and the accrual year for a Modelo 193 disclosure
            phase row, which tells a pending row from a settled prior-accrual
            one. ``None`` means the year is unknown, including on every revision
            persisted before the field existed; it never means "the current
            year". It joins the revision identity only when present, so those
            revisions keep their content-addressed ids.
    """

    model_config = STRICT_FROZEN_CONFIG

    resolver_id: str = Field(min_length=1, max_length=128)
    resolved_binding_source: BindingSourceKind
    contributor_source_kind: str = Field(min_length=1, max_length=64)
    contributor_binding_source: BindingSourceKind | None
    lineage_role: CalculationSourceLineageRole
    source_ref: str = Field(min_length=1, max_length=256)
    parent_source_ref: str | None = Field(min_length=1, max_length=256)
    fingerprint: str | None = Field(default=None, min_length=1, max_length=256)
    source_casilla_ids: tuple[CasillaId, ...] = ()
    dependency_treatment: str = ""
    source_filing_year: FilingYear | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_coherent_lineage(self) -> CalculationSourceRef:
        try:
            contributor_kind = BindingSourceKind(self.contributor_source_kind)
        except ValueError:
            contributor_kind = None
        if self.contributor_binding_source is None:
            if contributor_kind is not None:
                raise ModeloValidationError(
                    "source provenance contributor_binding_source is required when contributor_source_kind "
                    "is a binding source kind",
                )
        elif contributor_kind is not self.contributor_binding_source:
            raise ModeloValidationError(
                "source provenance contributor_binding_source must equal contributor_source_kind",
            )
        if self.lineage_role is CalculationSourceLineageRole.PRIMARY:
            if self.parent_source_ref is not None:
                raise ModeloValidationError("primary source provenance cannot have a parent")
        elif self.parent_source_ref is None:
            raise ModeloValidationError("contributor source provenance requires a parent")
        return self


class CalculationSourceIssue(BaseModel):
    """One durable unresolved source condition found while calculating a revision.

    Resolver diagnostics are useful calculate-time operator feedback, but a
    filing-grade verification runs later against the persisted calculation
    revision.  This narrow envelope carries a source condition that reached no
    binding, without misrepresenting it as source provenance for a computed
    output.

    Every reason below must survive to the persisted revision, because each
    describes a condition the filing cannot treat as complete.
    ``unrouted_observation`` is a row no binding consumes at all.
    ``unrouted_declarable_quantity`` is an independent quantity that consumed
    rows carry and no binding drawing that quantity reaches â€” the row-keyed
    screens are silent on it by construction, so a verify or export gate that
    saw only the row condition would read their silence as confirmation.
    ``iva_selected_scope_evidence_failure`` is a ledger IVA row whose selected
    filing scope cannot be completed from its recorded tax evidence.
    ``iva_compensation_annual_source_evidence_failure`` is a required Modelo
    390 annual partition whose filed Modelo 303 source set is incomplete or
    stale. ``withholding_detail_absent`` is an annual withholding summary whose
    per-perceptor-clave detail store held no observation for the year, so its
    percepciones count rests on a zero the store cannot support. A contradictory
    source is refused during calculation before a revision can be persisted.

    The remaining reasons each mean a filed figure is missing or cannot be
    trusted. ``unresolved_binding`` is a box printed on the form whose declared
    source produced no value, named by ``casilla_id``, which must never read as
    a zero. ``unhandled_binding_source`` is a declared source with no
    executable route. ``source_domain_not_ready`` is a source store that could
    not be read yet. ``invoice_reverse_charge_cuota_not_derivable`` is a
    reverse-charge invoice whose IVA owed could not be derived.
    These block filing until a recalculation clears them.
    ``terminal_origin_mismatch`` is a value that reached the declaration by an
    undeclared route; it persists so a reopened declaration still shows it, but
    withholds nothing, because the route it reports may lack a terminal origin by
    design. ``ledger_amortization_row_unregistered`` is a ledger row in an
    amortization category no registered element owns.
    ``activity_asset_foral_territory`` is a period in a foral territory, whose
    amortization is determined under foral rules.
    ``activity_asset_residence_unresolved`` is a tax residence that could not be
    read while the register holds elements. These three persist in the same way:
    the amortization is left out and the rest of the declaration stands.
    ``binding_source`` is ``None`` only where the condition names no binding
    source kind.
    """

    model_config = STRICT_FROZEN_CONFIG

    reason: Literal[
        "unrouted_observation",
        "unrouted_declarable_quantity",
        "iva_selected_scope_evidence_failure",
        "iva_compensation_annual_source_evidence_failure",
        "withholding_detail_absent",
        "unresolved_binding",
        "terminal_origin_mismatch",
        "unhandled_binding_source",
        "source_domain_not_ready",
        "invoice_reverse_charge_cuota_not_derivable",
        "ledger_amortization_row_unregistered",
        "activity_asset_foral_territory",
        "activity_asset_residence_unresolved",
    ]
    binding_source: BindingSourceKind | None
    message: str = Field(min_length=1, max_length=512)
    resolver_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_ref: str | None = Field(default=None, min_length=1, max_length=256)
    casilla_id: CasillaId | None = None


ACTIVITY_ASSET_CLAIM_REF_PREFIX: Final = "activity-asset-claim:"
"""Prefix of the source reference naming one effective amortization claim."""

ACTIVITY_ASSET_SCHEDULE_REF_PREFIX: Final = "activity-asset-schedule:"
"""Prefix of the source reference naming one element schedule by its fingerprint."""


ACTIVITY_ASSET_DISPOSAL_REF_PREFIX: Final = "activity-asset-disposal:"
"""Prefix of the source reference naming one baja by the revision that records it."""


class ActivityAssetConsumption(BaseModel):
    """The activity-asset register state one calculation rested on.

    Claim identity hashes the claim's content, so a claim cannot name the
    calculation that consumed it. The calculation records the claims and
    schedules instead, and any difference between that record and what the
    register yields now means the calculation no longer reflects the register.

    Attributes:
        claim_ids: Sorted identities of the effective claims consumed.
        schedule_fingerprints: Sorted fingerprints of the element schedules
            consumed where no claim stood behind the amount (Modelo 130 accrual).
        disposal_revision_ids: Sorted identities of the revisions recording a baja
            the calculation's period reaches, so a late baja reads as drift even
            where it changed no claim.
    """

    model_config = STRICT_FROZEN_CONFIG

    claim_ids: tuple[str, ...] = ()
    schedule_fingerprints: tuple[str, ...] = ()
    disposal_revision_ids: tuple[str, ...] = ()

    @classmethod
    def from_source_refs(cls, source_refs: Iterable[str]) -> ActivityAssetConsumption:
        """Read the consumption out of source references, ignoring every other kind."""
        claims: set[str] = set()
        schedules: set[str] = set()
        disposals: set[str] = set()
        for source_ref in source_refs:
            if source_ref.startswith(ACTIVITY_ASSET_CLAIM_REF_PREFIX):
                claims.add(source_ref.removeprefix(ACTIVITY_ASSET_CLAIM_REF_PREFIX))
            elif source_ref.startswith(ACTIVITY_ASSET_SCHEDULE_REF_PREFIX):
                schedules.add(source_ref.removeprefix(ACTIVITY_ASSET_SCHEDULE_REF_PREFIX))
            elif source_ref.startswith(ACTIVITY_ASSET_DISPOSAL_REF_PREFIX):
                disposals.add(source_ref.removeprefix(ACTIVITY_ASSET_DISPOSAL_REF_PREFIX))
        return cls(
            claim_ids=tuple(sorted(claims)),
            schedule_fingerprints=tuple(sorted(schedules)),
            disposal_revision_ids=tuple(sorted(disposals)),
        )

    @property
    def is_empty(self) -> bool:
        """Whether the calculation rested on no register state."""
        return not self.claim_ids and not self.schedule_fingerprints and not self.disposal_revision_ids


def validate_revision_source_provenance(rows: Sequence[CalculationSourceRef]) -> None:
    """Require unique primary identities and a declared primary parent for each contributor."""
    primary_refs = tuple(row.source_ref for row in rows if row.lineage_role is CalculationSourceLineageRole.PRIMARY)
    if len(primary_refs) != len(set(primary_refs)):
        raise ModeloValidationError("source provenance primary reference is ambiguous")
    primary_ref_set = frozenset(primary_refs)
    if any(
        row.parent_source_ref not in primary_ref_set
        for row in rows
        if row.lineage_role is CalculationSourceLineageRole.CONTRIBUTOR
    ):
        raise ModeloValidationError("source provenance contributor parent does not resolve to a primary")
