"""Per-filing-year evidence the overview applicability verdicts are decided on.

The calendar decides each obligation for its own filing year, and two of its
inputs vary by year:

* the profile answers, because effective-dated sections such as the filing
  obligation thresholds may answer differently for different years. They are
  read through :func:`~cadrumo.application.user_profile.projections.projection_for_taxpayer`
  as of the last day of the year, the "año natural correspondiente" RGAT
  arts. 32.c and 33.1 judge the Modelo 347 threshold over;
* what the taxpayer's own records show about a payer fact. The payer-fact
  catalogue in force for the year declares, per fact, the modelo filing whose
  declared-record count answers it; that filing's own resolver computes the
  count, so the signal is built from the same invoice observations and the
  same threshold function the declaration itself is built from, never from a
  second reader.

The composition root binds both to its stores once per read; the builders only
ask for the years they evaluate, and each year is derived at most once.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from ...core.period import Period
from ...domain.calculations.registry.applicability import LedgerPayerFactDerivation
from ...domain.calculations.registry.applicability_payer_facts import resolve_payer_fact_catalogue
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.ids import BindingId
from ...domain.deadlines.models import TaxpayerProfile
from ..aggregation.source_mesh import CalculationSourceContext, CalculationSourceResolution
from ..invoices.source_resolver import InvoiceCatalogueSourceResolver
from ..invoices.source_resolver_ports import (
    InvoiceSourceCatalogueReader,
    InvoiceSourcePersistenceError,
    InvoiceSourceResolverPorts,
)
from ..user_profile.projections import projection_for_taxpayer

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.invoices.models import InvoiceCatalogue
    from ...domain.user_profile.schema import ProfileSchemaDefinition
    from ...domain.user_profile.values import UserProfileRecord


@dataclass(frozen=True, slots=True)
class FilingYearApplicabilityEvidence:
    """The per-filing-year inputs one overview read decides applicability on.

    Attributes:
        profile_for_year: The taxpayer profile projected as of the last day of
            a filing year.
        ledger_payer_facts_for_year: The ledger derivations of payer facts for
            a filing year, keyed by payer fact token; a fact with no
            derivation is absent.
    """

    profile_for_year: Callable[[int], TaxpayerProfile]
    ledger_payer_facts_for_year: Callable[[int], Mapping[str, LedgerPayerFactDerivation]]


class _CatalogueReadOnce:
    """Read the invoice catalogue once per overview read, failure included.

    Every filing year the read evaluates is resolved against the same catalogue
    snapshot, and a degraded store is reported the same way for each of them.
    """

    def __init__(self, reader: InvoiceSourceCatalogueReader) -> None:
        self._reader = reader
        self._catalogue: InvoiceCatalogue | None = None
        self._error: InvoiceSourcePersistenceError | None = None

    def load(self) -> InvoiceCatalogue:
        if self._error is not None:
            raise self._error
        if self._catalogue is None:
            try:
                self._catalogue = self._reader.load()
            except InvoiceSourcePersistenceError as exc:
                self._error = exc
                raise
        return self._catalogue


def _memoized[T](derive: Callable[[int], T]) -> Callable[[int], T]:
    derived: dict[int, T] = {}

    def lookup(filing_year: int) -> T:
        if filing_year not in derived:
            derived[filing_year] = derive(filing_year)
        return derived[filing_year]

    return lookup


def bind_filing_year_applicability_evidence(
    *,
    record: UserProfileRecord,
    schema: ProfileSchemaDefinition,
    bucket_id: str,
    invoice_source_ports: InvoiceSourceResolverPorts,
    operation: PinnedAuthorityOperation,
    today: date,
) -> FilingYearApplicabilityEvidence:
    """Bind the per-year profile projection and ledger derivation to one read's stores.

    Args:
        record: The active profile record.
        schema: The profile schema pinned to ``operation``.
        bucket_id: The profile bucket whose invoices are read.
        invoice_source_ports: The invoice read capability the filing resolver
            itself is composed with.
        operation: The read's generation-pinned authority operation.
        today: The read's reference date; a year not yet ended is never
            complete.

    Returns:
        Evidence that derives each year on first use.
    """
    ports = InvoiceSourceResolverPorts(catalogue_reader=_CatalogueReadOnce(invoice_source_ports.catalogue_reader))

    def profile_for_year(filing_year: int) -> TaxpayerProfile:
        return projection_for_taxpayer(record, schema=schema, as_of=date(filing_year, 12, 31))

    def ledger_for_year(filing_year: int) -> Mapping[str, LedgerPayerFactDerivation]:
        return derive_ledger_payer_facts(
            filing_year,
            bucket_id=bucket_id,
            invoice_source_ports=ports,
            operation=operation,
            today=today,
        )

    return FilingYearApplicabilityEvidence(
        profile_for_year=_memoized(profile_for_year),
        ledger_payer_facts_for_year=_memoized(ledger_for_year),
    )


def derive_ledger_payer_facts(
    filing_year: int,
    *,
    bucket_id: str,
    invoice_source_ports: InvoiceSourceResolverPorts,
    operation: PinnedAuthorityOperation,
    today: date,
) -> dict[str, LedgerPayerFactDerivation]:
    """Derive what the invoice ledger shows about payer facts for one filing year.

    Every payer fact whose catalogue entry for the year declares a
    :class:`~cadrumo.domain.calculations.registry.applicability_payer_facts.PayerFactLedgerSource`
    is answered from its source modelo, resolved exactly as that modelo's
    calculation resolves it, through :class:`InvoiceCatalogueSourceResolver`.
    A year outside the registry's or the source modelo's supported filing
    years yields no derivation.

    Args:
        filing_year: The filing year whose operations are read.
        bucket_id: The profile bucket whose invoices are read.
        invoice_source_ports: The invoice read capability.
        operation: The generation-pinned authority operation.
        today: The reference date deciding whether the year has ended.

    Returns:
        The derivation per payer fact token.

    Raises:
        RegistryValidationError: The source modelo's revision for the year does
            not declare the source's record-count binding.
    """
    resolver = InvoiceCatalogueSourceResolver(ports=invoice_source_ports)
    derived: dict[str, LedgerPayerFactDerivation] = {}
    if not operation.supported_filing_years().admits_filing_year(filing_year):
        return derived
    with validating_governed_facts(operation):
        for fact in resolve_payer_fact_catalogue(effective_date=date(filing_year, 12, 31)):
            source = fact.ledger_source
            if source is None:
                continue
            support = operation.modelo_directory(source.modelo).supported_filing_years
            if support is not None and not support.admits_filing_year(filing_year):
                continue
            revision = operation.revision_for_context(source.modelo, filing_year=filing_year, period=source.period)
            if all(binding.id != source.record_count_binding for binding in revision.bindings):
                raise RegistryValidationError(
                    f"payer fact {fact.token!r} ledger source names binding {source.record_count_binding!r}, which "
                    f"modelo {source.modelo.value!r} revision {revision.id!r} does not declare",
                )
            resolution = resolver.resolve(
                CalculationSourceContext(
                    bucket_id=bucket_id,
                    modelo=source.modelo.value,
                    filing_year=filing_year,
                    period=Period.from_year_and_code(filing_year, source.period),
                    revision=revision,
                    operation=operation,
                ),
            )
            derived[fact.token] = declared_record_count_derivation(
                resolution,
                record_count_binding=source.record_count_binding,
                year_ended=filing_year < today.year,
            )
    return derived


def declared_record_count_derivation(
    resolution: CalculationSourceResolution,
    *,
    record_count_binding: BindingId,
    year_ended: bool,
) -> LedgerPayerFactDerivation:
    """Read a payer fact off the declared-record count of one source resolution.

    A count above zero is a derived yes on the observed operations alone: a
    record the resolver had to withhold cannot remove an observed record
    except through a rectifying invoice, and a mistaken yes surfaces as a
    visible disagreement rather than a silent suppression. A zero count is a
    derived no only when the ledger is complete for the year: the year has
    ended, the resolver observed at least one operation and reported no
    diagnostic, since a diagnostic means an operation was withheld or could
    not be classified. Anything else is unknown.

    Args:
        resolution: The resolver's result for the modelo and filing year.
        record_count_binding: The binding carrying the declared-record count.
        year_ended: Whether the filing year has ended.

    Returns:
        The three-state derivation.
    """
    count = resolution.binding_values.get(record_count_binding)
    if count is None:
        return LedgerPayerFactDerivation.UNKNOWN
    if count > 0:
        return LedgerPayerFactDerivation.DERIVED_YES
    if not year_ended or resolution.diagnostics or not resolution.provenance:
        return LedgerPayerFactDerivation.UNKNOWN
    return LedgerPayerFactDerivation.DERIVED_NO


__all__ = [
    "FilingYearApplicabilityEvidence",
    "bind_filing_year_applicability_evidence",
    "declared_record_count_derivation",
    "derive_ledger_payer_facts",
]
