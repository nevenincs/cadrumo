"""Per-filing-year evidence the overview applicability verdicts are decided on.

The calendar decides each obligation for its own filing year, and two of its
inputs vary by year:

* the profile answers, because effective-dated sections such as the filing
  obligation thresholds may answer differently for different years. They are
  read through :func:`~cadrumo.application.user_profile.projections.projection_for_taxpayer`
  as of the last day of the year, the "año natural correspondiente" RGAT
  arts. 32.c and 33.1 judge the Modelo 347 threshold over;
* what the taxpayer's own records show about a payer fact. A modelo whose
  obligation turns on having anything to declare answers its own required payer
  fact from the declared-record count its filing resolver computes, so the
  signal is built from the same invoice observations and the same threshold
  function the declaration itself is built from, never from a second reader.

The composition root binds both to its stores once per read; the builders only
ask for the years they evaluate, and each year is derived at most once.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final

from ...core.modelo import Modelo
from ...core.period import Period
from ...domain.calculations.registry.applicability import (
    LedgerPayerFactDerivation,
    resolve_applicability_rule_from_operation,
)
from ...domain.calculations.registry.applicability_payer_facts import PayerFactProjection
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
class _DeclaredRecordCountSource:
    """A modelo whose required payer fact holds exactly when its filing declares a record."""

    modelo: Modelo
    period: str
    record_count_binding: BindingId


_DECLARED_RECORD_COUNT_SOURCES: Final[tuple[_DeclaredRecordCountSource, ...]] = (
    # RGAT art. 33.1 relates every person whose operations "hayan superado la
    # cifra de 3.005,06 euros durante el año natural correspondiente", and the
    # type 1 count is the number of declarado records the resolver builds with
    # that floor applied per counterparty and per bucket (clave C's 300,51
    # included), so a count above zero is the threshold fact itself.
    _DeclaredRecordCountSource(
        modelo=Modelo("347"),
        period="0A",
        record_count_binding="modelo-347-declarante-numero-personas-entidades",
    ),
)


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

    Each declared-record-count modelo is resolved exactly as its calculation
    resolves it, through :class:`InvoiceCatalogueSourceResolver`, and the
    record count it reports answers the modelo's required payer fact. A year
    outside the modelo's supported filing years yields no derivation.

    Args:
        filing_year: The filing year whose operations are read.
        bucket_id: The profile bucket whose invoices are read.
        invoice_source_ports: The invoice read capability.
        operation: The generation-pinned authority operation.
        today: The reference date deciding whether the year has ended.

    Returns:
        The derivation per payer fact token.

    Raises:
        RegistryValidationError: A declared-record-count modelo's applicability
            rule does not require a registry payer fact.
    """
    resolver = InvoiceCatalogueSourceResolver(ports=invoice_source_ports)
    derived: dict[str, LedgerPayerFactDerivation] = {}
    with validating_governed_facts(operation):
        for source in _DECLARED_RECORD_COUNT_SOURCES:
            support = operation.modelo_directory(source.modelo).supported_filing_years
            if support is not None and not support.admits_filing_year(filing_year):
                continue
            fact = resolve_applicability_rule_from_operation(operation, source.modelo).required_payer_fact
            if not isinstance(fact, PayerFactProjection):
                raise RegistryValidationError(
                    f"modelo {source.modelo.value!r} derives its payer fact from its declared records, but its "
                    "applicability rule requires no registry payer fact",
                )
            resolution = resolver.resolve(
                CalculationSourceContext(
                    bucket_id=bucket_id,
                    modelo=source.modelo.value,
                    filing_year=filing_year,
                    period=Period.from_year_and_code(filing_year, source.period),
                    revision=operation.revision_for_context(
                        source.modelo,
                        filing_year=filing_year,
                        period=source.period,
                    ),
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
