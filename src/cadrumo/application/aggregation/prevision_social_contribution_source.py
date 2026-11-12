"""Source mesh resolver for the Modelo 100 pension contribution boxes from contribution certificate records.

Each record of the ejercicio is placed in the box the pinned revision's placement
rows give its Modelo 345 clave and subclave, and each box sums the records placed
in it, with one provenance row per record. A box no record reaches is left blank
for the filer, never a proven zero.

What the boxes say beyond the records:

* No record for the ejercicio: the reduction is not computed from certificates,
  which is disclosed and does not block; leaving a contribution out can only
  raise the tax.
* A record the revision places in no box: every box no record fills stays open
  with the served words of the refusal and the door to enter the box as an
  operator value, until the filer enters a contribution box.
* A box placed only by the texts of an earlier ejercicio: the figure stands at
  calculation grade, and checking, exporting and recording wait, as for a
  capped binding.
* A box the filer typed beside records placed in it: the calculation's own
  comparison of operator boxes with source boxes reports any difference through
  the override door; neither figure replaces the other in silence.

Nothing here names an issuer or a plan by its tax identifier; provenance names a
record by its keyed references.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar, Final

from ...core.aggregation import BindingSourceKind, BindingValueOutcome, CalculationSourceLineageRole
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import normalise_supported_language, output_language, tr
from ...core.prevision_social import PrevisionSocialPlacementRefusal
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.prevision_social_contribution_bindings import (
    prevision_social_contribution_binding_by_casilla,
    prevision_social_contribution_bindings,
    revision_declares_prevision_social_contribution,
)
from ...domain.calculations.registry.prevision_social_placement import placement_texts_cover
from ...domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ...domain.renta.prevision_social_contribution_placement import ContributionPlacementRefused, place_contribution
from .modelo_bindings_support import STORAGE_DEGRADATION_ERRORS, empty_source_resolution
from .prevision_social_contribution_repository import (
    PrevisionSocialContributionPersistenceError,
    PrevisionSocialContributionRecordReader,
    prevision_social_contribution_record_key,
    served_placement_words_key,
)
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import source_context_operation, storage_degradation_resolution

if TYPE_CHECKING:
    from datetime import date

    from ...core.casilla_id import CasillaId
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.ids import BindingId
    from ...domain.calculations.registry.prevision_social_placement import PrevisionSocialPlacement
    from ...domain.calculations.registry.schema import ModeloRevision
    from ...domain.renta.prevision_social_contribution import PrevisionSocialContribution

__all__ = ["PREVISION_SOCIAL_CONTRIBUTION_REF_PREFIX", "PrevisionSocialContributionSourceResolver"]

PREVISION_SOCIAL_CONTRIBUTION_REF_PREFIX: Final = "prevision-social-contribution:"
"""The provenance reference of one record, by its object key of keyed references."""

_SOURCE_KIND: Final = BindingSourceKind.PREVISION_SOCIAL_CONTRIBUTION
_ENTER_DOOR: Final = "Enter the contribution boxes by hand with the modelo work edit action."
_RECORD_DOOR: Final = (
    "Record each pension contribution certificate with aeat app ledger prevision-social record, or enter the "
    "contribution boxes by hand with the modelo work edit action."
)
_CORRECT_DOOR: Final = (
    "Wait for this year's placement to be confirmed, or remove the record with aeat app ledger prevision-social "
    "remove and enter the box by hand with the modelo work edit action."
)
_NOT_CERTIFIED_WORDS: Final = "aggregation.prevision_social_contribution.served.not_certified"


def _catalogue_language() -> OutputLanguage:
    """The language a sentence rendered here from the catalogue is worded in: the one ``tr`` renders."""
    return OutputLanguage(normalise_supported_language(output_language()) or OutputLanguage.EN.value)


@dataclass(slots=True)
class _Placed:
    """The records placed in one family binding's box, and whether every row placing them cites this year."""

    records: list[PrevisionSocialContribution] = field(default_factory=list)
    own_year: bool = True

    @property
    def total(self) -> Decimal:
        return sum((record.amount for record in self.records), Decimal("0"))


@dataclass(frozen=True, slots=True)
class _Reading:
    placed: Mapping[BindingId, _Placed]
    refused: tuple[PrevisionSocialPlacementRefusal, ...]
    recorded: bool


def _rows_by_id(revision: ModeloRevision) -> dict[str, PrevisionSocialPlacement]:
    return {row.id: row for row in revision.prevision_social_placements}


def _row_cites_year(
    row: PrevisionSocialPlacement, *, start: date, end: date, operation: PinnedAuthorityOperation
) -> bool:
    def window(source_ref: str) -> tuple[date | None, date | None]:
        source = operation.source_reference(source_ref)
        return source.applies_from, source.applies_to

    return placement_texts_cover(row, span_from=start, span_to=end, source_window=window)


def _read(
    context: CalculationSourceContext,
    records: Sequence[PrevisionSocialContribution],
    operation: PinnedAuthorityOperation,
) -> _Reading:
    revision = context.revision
    owners = prevision_social_contribution_binding_by_casilla(revision)
    rows = _rows_by_id(revision)
    placed: dict[BindingId, _Placed] = {}
    refused: list[PrevisionSocialPlacementRefusal] = []
    for record in records:
        placement = place_contribution(revision, record)
        if isinstance(placement, ContributionPlacementRefused):
            refused.append(placement.reason)
            continue
        binding_id = owners.get(placement.casilla_id)
        if binding_id is None:
            raise RegistryValidationError(
                f"placement {placement.placement_id!r} names casilla {placement.casilla_id!r}, "
                "which no single family binding fills"
            )
        entry = placed.setdefault(binding_id, _Placed())
        entry.records.append(record)
        entry.own_year = entry.own_year and _row_cites_year(
            rows[placement.placement_id],
            start=context.period.start_date,
            end=context.period.end_date,
            operation=operation,
        )
    return _Reading(placed=placed, refused=tuple(dict.fromkeys(refused)), recorded=bool(records))


class PrevisionSocialContributionSourceResolver:
    """Resolve the family's bindings from the ejercicio's contribution certificate records."""

    resolver_id: ClassVar[str] = "prevision_social_contribution"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (_SOURCE_KIND,)

    def __init__(self, *, repository: PrevisionSocialContributionRecordReader) -> None:
        """Use the contribution records' read capability."""
        self._repository = repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Sum each box's placed records, and say what the boxes no record fills are waiting for."""
        revision = context.revision
        if not revision_declares_prevision_social_contribution(revision):
            return empty_source_resolution(self.resolver_id, self.owned_sources)
        try:
            records = self._repository.load_records(context.period.filing_year)
        except (PrevisionSocialContributionPersistenceError, *STORAGE_DEGRADATION_ERRORS) as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        with source_context_operation(context) as operation:
            reading = _read(context, records, operation)
        targets = {
            binding_id: casilla_id
            for casilla_id, binding_id in prevision_social_contribution_binding_by_casilla(revision).items()
        }
        family = tuple(binding.id for binding, _provider in prevision_social_contribution_bindings(revision))
        typed = bool(context.caller_casilla_ids & frozenset(targets.values()))
        empty = tuple(binding_id for binding_id in family if binding_id not in reading.placed)
        held_open = bool(reading.refused) and not typed
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values={binding_id: entry.total for binding_id, entry in reading.placed.items()},
            value_outcomes=dict.fromkeys(reading.placed, BindingValueOutcome.FROM_BEARING_ROWS),
            unresolved_binding_ids=empty,
            inapplicable_binding_ids=() if held_open else empty,
            diagnostics=(
                *(self._refused_diagnostics(reading.refused, empty, targets) if held_open else ()),
                *(() if reading.recorded else (self._not_certified(),)),
                *self._inherited_diagnostics(reading.placed, targets),
            ),
            provenance=tuple(
                self._node(record)
                for entry in reading.placed.values()
                for record in sorted(
                    entry.records, key=lambda item: prevision_social_contribution_record_key(item.identity)
                )
            ),
        )

    def _refused_diagnostics(
        self,
        refused: Sequence[PrevisionSocialPlacementRefusal],
        empty: Sequence[BindingId],
        targets: Mapping[BindingId, CasillaId],
    ) -> tuple[CalculationSourceDiagnostic, ...]:
        words = " ".join(tr(served_placement_words_key(reason)) for reason in refused)
        language = _catalogue_language()
        return tuple(
            CalculationSourceDiagnostic(
                reason="unresolved_binding",
                source_kind=_SOURCE_KIND.value,
                binding_source=_SOURCE_KIND,
                resolver_id=self.resolver_id,
                binding_id=binding_id,
                casilla_id=targets[binding_id],
                message=words,
                message_language=language,
                remedy=_ENTER_DOOR,
                fact=CalculationNoteFact.of(
                    CalculationNoteSentence.PREVISION_SOCIAL_CONTRIBUTION_NOT_PLACED,
                    box=targets[binding_id],
                    count=len(refused),
                ),
            )
            for binding_id in empty
        )

    def _not_certified(self) -> CalculationSourceDiagnostic:
        return CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind=_SOURCE_KIND.value,
            binding_source=_SOURCE_KIND,
            resolver_id=self.resolver_id,
            message=tr(_NOT_CERTIFIED_WORDS),
            message_language=_catalogue_language(),
            remedy=_RECORD_DOOR,
            fact=CalculationNoteFact.of(CalculationNoteSentence.PREVISION_SOCIAL_CONTRIBUTION_NOT_CERTIFIED),
        )

    def _inherited_diagnostics(
        self, placed: Mapping[BindingId, _Placed], targets: Mapping[BindingId, CasillaId]
    ) -> tuple[CalculationSourceDiagnostic, ...]:
        return tuple(
            CalculationSourceDiagnostic(
                reason="advisory_binding_value",
                source_kind=_SOURCE_KIND.value,
                binding_source=_SOURCE_KIND,
                resolver_id=self.resolver_id,
                binding_id=binding_id,
                casilla_id=targets[binding_id],
                source_ref=str(binding_id),
                message=(
                    f"binding {binding_id!r} gives box {targets[binding_id]} the value {entry.total}, placed only by "
                    "the official texts of an earlier ejercicio; its reach is calculation grade, so checking, "
                    "exporting and recording wait until this ejercicio's texts confirm the placement"
                ),
                remedy=_CORRECT_DOOR,
                fact=CalculationNoteFact.of(
                    CalculationNoteSentence.PREVISION_SOCIAL_PLACEMENT_INHERITED,
                    box=targets[binding_id],
                    amount=entry.total,
                ),
            )
            for binding_id, entry in placed.items()
            if not entry.own_year
        )

    def _node(self, record: PrevisionSocialContribution) -> CalculationSourceProvenance:
        return CalculationSourceProvenance(
            resolver_id=self.resolver_id,
            resolved_binding_source=_SOURCE_KIND,
            contributor_source_kind=_SOURCE_KIND.value,
            contributor_binding_source=_SOURCE_KIND,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=f"{PREVISION_SOCIAL_CONTRIBUTION_REF_PREFIX}{prevision_social_contribution_record_key(record.identity)}",
            parent_source_ref=None,
            fingerprint=record.evidence_fingerprint,
            terminal_origin=TerminalOriginClass.PAYER_CERTIFICATE,
        )
