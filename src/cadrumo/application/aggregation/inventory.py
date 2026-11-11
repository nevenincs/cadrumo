"""Encrypted inventory-ledger resolver for typed inventory binding projections.

It works with :class:`UserProfileRecord`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import ClassVar, Protocol, get_args

from pydantic import ValidationError

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.errors.hierarchy import InternalInvariantError
from ...core.hashing import content_hash_hex
from ...domain.calculations.registry.applicability import derive_taxpayer_files_economic_activity
from ...domain.calculations.registry.binding_temporal import SameTargetContext
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.inventory_anexo_d_applicability import inventory_anexo_d_applies
from ...domain.calculations.registry.inventory_bindings import InventoryProvider
from ...domain.calculations.registry.schema import BindingDefinition
from ...domain.calculations.row_source_identity import RowSourceIdentity
from ...domain.contribuyente.inventory.closing_foundations import InventoryLedgerError
from ...domain.contribuyente.inventory.records import InventoryLedger, InventoryLedgerDocument
from ...domain.contribuyente.inventory.valuation import compute_inventory_anexo_d_projection
from ...domain.user_profile.values import UserProfileRecord
from ..inventory.movement_claim_checks import InventoryClaimLedgerReads
from .inventory_claim_findings import inventory_claim_findings
from .modelo_bindings_support import STORAGE_DEGRADATION_ERRORS
from .source_diagnostic_reason import CalculationSourceDiagnosticReason
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)

_SOURCE = BindingSourceKind.INVENTORY
_ACTIVITIES_SECTION = "activities"
_ESTIMATION_REGIME_PATH = "irpf.estimation_regime"
_OWNED_SOURCES = (_SOURCE,)
VALUE_ATTRIBUTE_BY_OPERATION: Mapping[str, str] = {
    "complete_acquisition_cost": "complete_acquisition_total",
    "closing_minus_opening_positive": "variation_increase_value",
    "opening_minus_closing_positive": "variation_decrease_value",
}
_OPERATION_ANNOTATION = InventoryProvider.model_fields["row_field"].annotation
_CANONICAL_OPERATIONS = get_args(getattr(_OPERATION_ANNOTATION, "__value__", _OPERATION_ANNOTATION))
if set(VALUE_ATTRIBUTE_BY_OPERATION) != set(_CANONICAL_OPERATIONS):
    raise InternalInvariantError("inventory projection operation adapter is not exhaustive")


class InventoryLedgerRepositoryProtocol(Protocol):
    """Read boundary required by the inventory source resolver."""

    def load(self) -> InventoryLedgerDocument:
        """Load the encrypted inventory ledger document."""
        ...


def _inventory_bindings(context: CalculationSourceContext) -> tuple[BindingDefinition, ...]:
    return tuple(binding for binding in context.revision.bindings if binding.source is _SOURCE)


def _profile_declares_no_activity_income(context: CalculationSourceContext) -> bool:
    """Whether the filer's profile declares income categories that exclude an economic activity.

    The Anexo D inventory rows belong to the rendimientos de actividades
    economicas a filer carries on (LIRPF arts. 27 and 30): a filer who declares
    only employment, capital or other non-activity income holds no activity
    ledger because there is no activity to hold one for. Only that typed
    declaration counts. A profile that declares no income category at all, or
    a context with no profile, is unknown rather than inapplicable, and a
    missing ledger is then still reported.
    """
    if context.profile is None:
        return False
    from ..user_profile.projections import projection_for_taxpayer

    taxpayer = projection_for_taxpayer(context.profile.record, schema=context.profile.profile_decode_context.schema)
    return derive_taxpayer_files_economic_activity(taxpayer) is False


@dataclass(frozen=True, slots=True)
class _DirectEstimationActivities:
    """The activities the ejercicio holds in the direct-estimation activity block.

    ``regime_undeclared`` means an activity is in force on a day the profile states no estimation
    regime, so whether that activity belongs in the block is unknown and ``count`` is not final.
    """

    count: int
    regime_undeclared: bool


def _direct_estimation_activities(context: CalculationSourceContext) -> _DirectEstimationActivities | None:
    """Count the activities the ejercicio holds in the direct-estimation activity block.

    The block (ActividadEstDirecta) holds only activities in estimacion directa, so an activity
    counts on the days the profile's estimation regime is a direct-estimation one. Each activity
    is identified by its row together with the identifying values the row holds that day, so a
    row whose description or epigraph changes within the year counts once per identity: its two
    halves are two activities, of which one book can describe only one. The year is read on its
    first and last day and on each day a dated fact of the profile starts, or ends the day
    before; between those days no fact changes. ``None`` means no profile was read.

    Books are matched to these activities by count, not identity, because a book names its
    activity by the operator's own free-text identifier: two books for one activity of two
    still resolve here, and the export then refuses to choose between their two occurrences.
    """
    if context.profile is None:
        return None
    record = context.profile.record
    activities: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
    regime_undeclared = False
    for day in _fact_change_days(record, context.filing_year):
        day_activities, day_undeclared = _direct_estimation_activities_on(record, day)
        activities |= day_activities
        regime_undeclared = regime_undeclared or day_undeclared
    return _DirectEstimationActivities(count=len(activities), regime_undeclared=regime_undeclared)


def _fact_change_days(record: UserProfileRecord, filing_year: int) -> set[date]:
    """Return the days the ejercicio is read on: its ends and each day a dated profile fact starts or stops."""
    first, last = date(filing_year, 1, 1), date(filing_year, 12, 31)
    days = {first, last}
    for fact in record.facts:
        if fact.valid_from is not None and first <= fact.valid_from <= last:
            days.add(fact.valid_from)
        if fact.valid_to is not None and first <= fact.valid_to < last:
            days.add(fact.valid_to + timedelta(days=1))
    return days


def _direct_estimation_activities_on(
    record: UserProfileRecord, day: date
) -> tuple[set[tuple[str, tuple[tuple[str, str], ...]]], bool]:
    """Return the direct-estimation activities in force on ``day`` and whether their regime is undeclared."""
    from ...domain.calculations.registry.irpf_regimes import (
        irpf_estimation_regime_directa_normal_token,
        irpf_estimation_regime_directa_simplificada_token,
        irpf_estimation_regime_tokens,
    )
    from ..user_profile.completeness import profile_section_rows, profile_value_is_present
    from ..user_profile.projections import record_to_path_values

    declared = {str(token) for token in irpf_estimation_regime_tokens()}
    direct = {
        str(irpf_estimation_regime_directa_normal_token()),
        str(irpf_estimation_regime_directa_simplificada_token()),
    }
    values = record_to_path_values(record, as_of=day)
    present = [path for path, value in values.items() if profile_value_is_present(value)]
    rows = profile_section_rows(_ACTIVITIES_SECTION, present)
    regime = values.get(_ESTIMATION_REGIME_PATH, "").strip()
    regime_undeclared = bool(rows) and regime not in declared
    activities: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
    if regime not in direct:
        return activities, regime_undeclared
    for row, fields in rows.items():
        prefix = f"{_ACTIVITIES_SECTION}.{row}" if row else _ACTIVITIES_SECTION
        # Every populated field identifies the activity, so a later dated field that does not
        # identify it still splits the row in two and refuses rather than mismatching a book.
        activities.add((row, tuple(sorted((field, values[f"{prefix}.{field}"].strip()) for field in fields))))
    return activities, regime_undeclared


def _activity_books_refusal(
    activities: _DirectEstimationActivities | None,
    books: int,
    *,
    binding_ids: tuple[str, ...],
    filing_year: int,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution:
    if activities is not None and activities.regime_undeclared:
        diagnostic = _diagnostic(
            reason="source_domain_not_ready",
            state="estimation_regime_undeclared",
            message=(
                f"{books} {filing_year} inventory activity books are kept and the profile states no estimation "
                "regime on a day an activity is in force"
            ),
            remedy=(
                "Declare in the profile the IRPF estimation regime of the activities for every day of the "
                "ejercicio they are in force, so the Anexo D rows hold only activities in estimacion directa."
            ),
        )
    else:
        declared = (
            "no profile was read"
            if activities is None
            else f"the profile declares {activities.count} activities in estimacion directa"
        )
        diagnostic = _diagnostic(
            reason="source_domain_not_ready",
            state="activity_books_do_not_match_activities",
            message=f"{books} {filing_year} inventory activity books are kept and {declared} for the ejercicio",
            remedy=(
                "Keep one inventory book for each activity in estimacion directa in the ejercicio, a book "
                "with no existencias included, and none for an activity in estimacion objetiva. Declare in "
                "the profile the estimation regime and each such activity, with the dates an activity's "
                "description or epigraph changed, so each Anexo D row is one activity's."
            ),
        )
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        unresolved_binding_ids=binding_ids,
        diagnostics=(diagnostic,),
    )


def _diagnostic(
    *, reason: CalculationSourceDiagnosticReason, state: str, message: str, remedy: str | None = None
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason=reason,
        source_kind=_SOURCE.value,
        resolver_id=InventorySourceResolver.resolver_id,
        message=f"inventory source {state}: {message}",
        remedy=remedy,
    )


@dataclass(frozen=True, slots=True)
class _InventoryBindingTemplate:
    """Validated inventory row templates carried into ledger projection."""

    by_operation: Mapping[str, BindingDefinition]


def _resolve_inventory_binding_template(
    bindings: tuple[BindingDefinition, ...],
    *,
    binding_ids: tuple[str, ...],
    filing_year: int,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> _InventoryBindingTemplate | CalculationSourceResolution:
    """Validate selector shape, filing coordinate, and the complete operation cohort."""
    typed_bindings = _typed_inventory_bindings(
        bindings,
        binding_ids=binding_ids,
        resolver_id=resolver_id,
        owned_sources=owned_sources,
    )
    if isinstance(typed_bindings, CalculationSourceResolution):
        return typed_bindings
    coordinate_refusal = _inventory_coordinate_refusal(
        typed_bindings,
        binding_ids=binding_ids,
        filing_year=filing_year,
        resolver_id=resolver_id,
        owned_sources=owned_sources,
    )
    if coordinate_refusal is not None:
        return coordinate_refusal
    bindings_by_operation = _inventory_bindings_by_operation(
        typed_bindings,
        binding_ids=binding_ids,
        resolver_id=resolver_id,
        owned_sources=owned_sources,
    )
    if isinstance(bindings_by_operation, CalculationSourceResolution):
        return bindings_by_operation
    return _InventoryBindingTemplate(by_operation=bindings_by_operation)


def _typed_inventory_bindings(
    bindings: tuple[BindingDefinition, ...],
    *,
    binding_ids: tuple[str, ...],
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> list[tuple[BindingDefinition, InventoryProvider]] | CalculationSourceResolution:
    typed_bindings = [
        (binding, binding.provider) for binding in bindings if isinstance(binding.provider, InventoryProvider)
    ]
    if len(typed_bindings) == len(bindings):
        return typed_bindings
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        unresolved_binding_ids=binding_ids,
        diagnostics=(
            _diagnostic(
                reason="unresolved_derived_binding",
                state="selector_unreadable",
                message="one or more bindings do not carry the canonical inventory row template",
            ),
        ),
    )


def _inventory_coordinate_refusal(
    typed_bindings: list[tuple[BindingDefinition, InventoryProvider]],
    *,
    binding_ids: tuple[str, ...],
    filing_year: int,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution | None:
    # The declaration carries no authored year: it states timeless intent and the
    # filing context supplies the coordinate. The year guard is therefore a guard
    # on the temporal selector -- an inventory row template must rest on the
    # target's own filing coordinate rather than shifting off it.
    if any(not isinstance(selector.temporal, SameTargetContext) for _binding, selector in typed_bindings):
        return _template_refusal_resolution(
            binding_ids,
            "inventory binding must rest on the selected filing coordinate",
            resolver_id=resolver_id,
            owned_sources=owned_sources,
        )

    # Refuse an inapplicable filing year here, before the encrypted ledger is
    # read: the projection would refuse it anyway, but only after a load.
    try:
        applies = inventory_anexo_d_applies(filing_year=filing_year)
    except RegistryValidationError:
        applies = False
    if applies:
        return None
    return _template_refusal_resolution(
        binding_ids,
        "inventory row template is not applicable for the filing year",
        resolver_id=resolver_id,
        owned_sources=owned_sources,
    )


def _inventory_bindings_by_operation(
    typed_bindings: list[tuple[BindingDefinition, InventoryProvider]],
    *,
    binding_ids: tuple[str, ...],
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> dict[str, BindingDefinition] | CalculationSourceResolution:
    bindings_by_operation: dict[str, BindingDefinition] = {}
    for binding, selector in typed_bindings:
        operation = selector.row_field
        if operation in bindings_by_operation:
            return _template_refusal_resolution(
                binding_ids,
                "duplicate inventory operation row template",
                resolver_id=resolver_id,
                owned_sources=owned_sources,
            )
        bindings_by_operation[operation] = binding
    if set(bindings_by_operation) == set(_CANONICAL_OPERATIONS) and len(bindings_by_operation) == len(
        _CANONICAL_OPERATIONS
    ):
        return bindings_by_operation
    return _template_refusal_resolution(
        binding_ids,
        "inventory row-template cohort must contain each operation once",
        resolver_id=resolver_id,
        owned_sources=owned_sources,
    )


def _load_inventory_ledgers(
    repository: InventoryLedgerRepositoryProtocol,
    *,
    binding_ids: tuple[str, ...],
    filing_year: int,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> tuple[InventoryLedger, ...] | CalculationSourceResolution:
    """Read and select the deterministic filing-year activity ledger cohort."""
    try:
        document = repository.load()
    except InventoryLedgerError:
        return _storage_refusal_resolution(
            binding_ids,
            resolver_id=resolver_id,
            owned_sources=owned_sources,
        )
    selected = tuple(item for item in document.ledgers if item.year == filing_year)
    return _ledgers_or_not_ready(
        selected, binding_ids=binding_ids, filing_year=filing_year, resolver_id=resolver_id, owned_sources=owned_sources
    )


def _ledgers_or_not_ready(
    selected: tuple[InventoryLedger, ...],
    *,
    binding_ids: tuple[str, ...],
    filing_year: int,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> tuple[InventoryLedger, ...] | CalculationSourceResolution:
    """Return the live ledgers sorted by activity, or the first reason the cohort is not ready."""
    # A retired ledger with no stock facts has nothing to declare. One still
    # holding facts refuses rather than dropping them from the Anexo D rows,
    # because retirement is not proof that the stock never existed.
    if any(item.leaves_year_unresolved for item in selected):
        return _ledger_not_ready(
            binding_ids,
            resolver_id,
            owned_sources,
            state="retired_ledger_holds_stock_facts",
            message=f"a retired {filing_year} inventory activity ledger still holds stock facts",
        )
    ledgers = tuple(sorted((item for item in selected if not item.is_retired), key=lambda item: item.actividad_id))
    # The closing value is the operator's decision for the year, so a book that
    # has none yet is unfinished rather than inconsistent: the existencias
    # finales are unknown until it is recorded, and only then can the variation
    # of casillas 0177 and 0182 be derived.
    if any(item.closing_authority_record is None for item in ledgers):
        return _ledger_not_ready(
            binding_ids,
            resolver_id,
            owned_sources,
            state="closing_value_not_recorded",
            message=f"a {filing_year} inventory activity ledger has no recorded closing value",
            remedy=(
                "Record the year's closing value of each activity's inventory, the existencias finales "
                "valued at acquisition price, so the stock variation can be derived."
            ),
        )
    # A missing book is an unanswered question, not a statement that the activity
    # held no existencias: only a book closed at zero proves the zero rows.
    if not ledgers:
        return _ledger_not_ready(
            binding_ids,
            resolver_id,
            owned_sources,
            state="missing_activity_ledgers",
            message=f"no complete {filing_year} inventory activity ledger is available",
            remedy=(
                "Open the inventory book of each activity in estimacion directa for the ejercicio and record "
                "its closing value, the existencias finales valued at acquisition price. For an activity that "
                "held no existencias, open the book with no stock and record its closing at zero, so the rows "
                "read zero on that statement."
            ),
        )
    return ledgers


def _ledger_not_ready(
    binding_ids: tuple[str, ...],
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
    *,
    state: str,
    message: str,
    remedy: str | None = None,
) -> CalculationSourceResolution:
    """Return the not-ready resolution that leaves every binding unresolved."""
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        unresolved_binding_ids=binding_ids,
        diagnostics=(_diagnostic(reason="source_domain_not_ready", state=state, message=message, remedy=remedy),),
    )


def _row_provenance(content_fingerprint: str) -> CalculationSourceProvenance:
    """Name the activity record one row value rests on, addressed by its content.

    The terminal fact behind an inventory row value is one sealed activity
    projection, so the node is primary and carries the detail-record origin the
    provider registration admits. The reference addresses that record by its
    content digest rather than by ``actividad_id``: provenance is serialised
    into calculation persistence and operator-facing explanation, where the
    taxpayer's own activity identifier is not disclosable, and the digest names
    exactly one record without disclosing it.
    """
    return CalculationSourceProvenance(
        resolver_id=InventorySourceResolver.resolver_id,
        resolved_binding_source=_SOURCE,
        contributor_source_kind=_SOURCE.value,
        contributor_binding_source=_SOURCE,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref=f"inventory_activity:{content_fingerprint}",
        parent_source_ref=None,
        terminal_origin=TerminalOriginClass.DETAIL_RECORD,
        fingerprint=content_fingerprint,
    )


def _resolve_inventory_rows(
    ledgers: tuple[InventoryLedger, ...],
    *,
    binding_ids: tuple[str, ...],
    bindings_by_operation: Mapping[str, BindingDefinition],
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution:
    """Project each activity into row values, identities, and physical evidence diagnostics."""
    row_values: dict[tuple[str, int], Decimal | str] = {}
    row_identities: dict[tuple[str, int], RowSourceIdentity] = {}
    provenance: list[CalculationSourceProvenance] = []
    diagnostics: list[CalculationSourceDiagnostic] = []
    try:
        for row_index, ledger in enumerate(ledgers, start=1):
            projection = compute_inventory_anexo_d_projection(ledger)
            content_fingerprint = content_hash_hex(projection.model_dump(mode="json"))
            for operation, binding in bindings_by_operation.items():
                key = (binding.id, row_index)
                row_values[key] = getattr(projection, VALUE_ATTRIBUTE_BY_OPERATION[operation])
                row_identities[key] = RowSourceIdentity(
                    source_kind=_SOURCE,
                    source_row_identity=projection.actividad_id,
                    fingerprint=projection.projection_fingerprint,
                )
            # One node per activity record, not per produced value: the three
            # operation values of an activity rest on that one sealed
            # projection, and the envelope admits a primary source reference
            # once, because a second copy would state two terminal facts where
            # the taxpayer has one.
            provenance.append(_row_provenance(content_fingerprint))
            if projection.closing_conflict is not None:
                diagnostics.append(
                    _diagnostic(
                        reason="source_issue",
                        state="physical_closing_conflict",
                        message="one inventory activity retains a reviewed physical closing conflict",
                    ),
                )
    except (InventoryLedgerError, ValidationError):
        return _projection_refusal_resolution(
            binding_ids,
            resolver_id=resolver_id,
            owned_sources=owned_sources,
        )
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        row_binding_values=row_values,
        row_source_identities=row_identities,
        provenance=tuple(provenance),
        diagnostics=tuple(diagnostics),
    )


def _template_refusal_resolution(
    binding_ids: tuple[str, ...],
    message: str,
    *,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution:
    """Build the fail-closed result for an invalid inventory row-template cohort."""
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        unresolved_binding_ids=binding_ids,
        diagnostics=(
            _diagnostic(
                reason="unresolved_derived_binding",
                state="invalid_row_template_cohort",
                message=message,
            ),
        ),
    )


def _storage_refusal_resolution(
    binding_ids: tuple[str, ...],
    *,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution:
    """Build the fail-closed result for unreadable encrypted inventory storage."""
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        unresolved_binding_ids=binding_ids,
        diagnostics=(
            _diagnostic(
                reason="storage_degraded",
                state="repository_unreadable",
                message="encrypted inventory storage could not be read",
            ),
        ),
    )


def _projection_refusal_resolution(
    binding_ids: tuple[str, ...],
    *,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution:
    """Build the fail-closed result for incomplete or tampered activity projections."""
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        unresolved_binding_ids=binding_ids,
        diagnostics=(
            _diagnostic(
                reason="unresolved_derived_binding",
                state="incomplete_or_tampered_projection",
                message="inventory activity projection is incomplete or inconsistent",
            ),
        ),
    )


class InventorySourceResolver:
    """Resolve inventory bindings from one encrypted schema-v3 ledger document.

    This adapter selects an exact activity/year ledger and delegates every
    monetary and authority decision to the sealed inventory projection. It does
    not aggregate across activities, allocate values, enroll itself in the mesh,
    or provide a manual fallback.
    """

    resolver_id: ClassVar[str] = "inventory"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = _OWNED_SOURCES

    def __init__(
        self,
        *,
        inventory_repository: InventoryLedgerRepositoryProtocol | None = None,
        claim_reads: InventoryClaimLedgerReads | None = None,
    ) -> None:
        """Bind the optional repository used to read inventory facts.

        ``claim_reads`` is the ledger and asset register the purchases' ledger
        statements are checked against. Without it no statement is checked, so
        only a caller that reads the projection, not one that files it, omits it.
        """
        self._inventory_repository = inventory_repository
        self._claim_reads = claim_reads

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve inventory bindings for the selected calculation context."""
        bindings = _inventory_bindings(context)
        if not bindings:
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)
        binding_ids = tuple(sorted({binding.id for binding in bindings}))
        template = _resolve_inventory_binding_template(
            bindings,
            binding_ids=binding_ids,
            filing_year=context.filing_year,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
        )
        if isinstance(template, CalculationSourceResolution):
            return template
        if _profile_declares_no_activity_income(context):
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                unresolved_binding_ids=binding_ids,
                inapplicable_binding_ids=binding_ids,
            )
        if self._inventory_repository is None:
            return self._storage_refusal(binding_ids)
        ledgers = _load_inventory_ledgers(
            self._inventory_repository,
            binding_ids=binding_ids,
            filing_year=context.filing_year,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
        )
        if isinstance(ledgers, CalculationSourceResolution):
            return ledgers
        # Each row is one book and the activity block of the return is one activity, so a row is
        # an activity's only when every declared activity keeps its book. One book among several
        # activities would otherwise read as the return's one activity.
        activities = _direct_estimation_activities(context)
        if activities is None or activities.regime_undeclared or activities.count != len(ledgers):
            return _activity_books_refusal(
                activities,
                len(ledgers),
                binding_ids=binding_ids,
                filing_year=context.filing_year,
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
            )
        claim_refusal = self._claim_refusal(ledgers, binding_ids=binding_ids, filing_year=context.filing_year)
        if claim_refusal is not None:
            return claim_refusal
        return _resolve_inventory_rows(
            ledgers,
            binding_ids=binding_ids,
            bindings_by_operation=template.by_operation,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
        )

    def _claim_refusal(
        self, ledgers: tuple[InventoryLedger, ...], *, binding_ids: tuple[str, ...], filing_year: int
    ) -> CalculationSourceResolution | None:
        """Hold the rows back while a purchase's ledger statement does not stand, or is missing."""
        if self._claim_reads is None or self._inventory_repository is None:
            return None
        try:
            findings = inventory_claim_findings(
                self._inventory_repository.load(), ledgers, filing_year=filing_year, reads=self._claim_reads
            )
        except (InventoryLedgerError, *STORAGE_DEGRADATION_ERRORS):
            return self._storage_refusal(binding_ids)
        if not findings:
            return None
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            unresolved_binding_ids=binding_ids,
            diagnostics=tuple(
                _diagnostic(reason="source_domain_not_ready", state=state, message=message, remedy=remedy)
                for state, message, remedy in findings
            ),
        )

    def _storage_refusal(self, binding_ids: tuple[str, ...]) -> CalculationSourceResolution:
        return _storage_refusal_resolution(
            binding_ids,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
        )


__all__ = ["InventoryLedgerRepositoryProtocol", "InventorySourceResolver"]
