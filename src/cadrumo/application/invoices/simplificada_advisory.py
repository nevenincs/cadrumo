"""Whether a factura simplificada needs the destinatario's NIF, and when we cannot tell.

RD 1619/2012 art. 6.1.d case 3.º asks for the destinatario's NIF on a domestic
factura simplificada whose issuer is established in the TAI. Deciding that takes
the invoice AND the issuing taxpayer's profile, so a surface must resolve the
profile before it can say anything at all — and the resolution can fail.

The failure is the reason this module exists. The rule was evaluated inside one
CLI notice builder that returned an empty list for five different situations: a
tax id already present, the predicate answering no, no active bucket, no stored
profile, and a profile that would not read. Four of those mean "nothing to
advise" and one means "we do not know" — and collapsing them made an operator
whose profile store is degraded indistinguishable from one whose invoice is
fine. They lose a real legal advisory and are never told the check did not run.

So the states stay distinct here, and a surface decides what to do with each.
Saying nothing on :attr:`SimplificadaTaxIdAdvisory.ISSUER_UNKNOWN` remains
correct for a notice channel — an advisory whose premise could not be evaluated
must not be asserted — but that is now the caller's decision rather than a
distinction the answer had already thrown away.

The legality itself is not restated here. Case 3.º has one authority,
:func:`~application.invoices.issuer_establishment.simplificada_requires_tax_id_for_domestic_issuer`,
and this module resolves the inputs that predicate needs and reports what it
answered.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .issuer_establishment import simplificada_requires_tax_id_for_domestic_issuer

if TYPE_CHECKING:
    from collections.abc import Callable

    from ...domain.deadlines.models import TaxpayerProfile
    from ...domain.invoices.models import Invoice

__all__ = [
    "SimplificadaTaxIdAdvisory",
    "resolve_simplificada_tax_id_advisory",
    "resolve_simplificada_tax_id_legal_refs",
]


class SimplificadaTaxIdAdvisory(StrEnum):
    """What case 3.º has to say about one invoice.

    Four answers rather than a boolean, because "no advisory" and "no answer"
    are different facts about the same invoice and only one of them is good
    news.
    """

    #: Case 3.º applies: a domestic ISSUED simplificada with no tax id, from a
    #: TAI-established issuer. Advisory weight — never a refusal.
    REQUIRED = "required"
    #: The predicate was evaluated against a resolved profile and answered no.
    NOT_REQUIRED = "not_required"
    #: The invoice already carries a counterparty tax id, so case 3.º has
    #: nothing further to ask for and no profile read is needed.
    ALREADY_IDENTIFIED = "already_identified"
    #: The issuing taxpayer could not be resolved — no active bucket, no stored
    #: profile, or a profile that would not read — so the establishment half of
    #: case 3.º is unknown and the rule was NOT evaluated.
    ISSUER_UNKNOWN = "issuer_unknown"


def resolve_simplificada_tax_id_legal_refs(
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> tuple[str, ...]:
    """Return the legal references carried by the simplified-invoice fact.

    The advisory predicate and the invoice model both consume the dated
    ``invoice-simplificada-counterparty-tax-id-applicability`` mapping.  Keep
    the notice provenance on that same resolved fact instead of repeating one
    of its legal-reference values in an entrypoint.

    Returns:
        The fact's ordered legal-reference identifiers.

    Raises:
        RegistryValidationError: If the fact does not resolve as a mapping or
            carries no provenance.
    """
    from datetime import date

    from ...domain.calculations.registry.errors import RegistryValidationError
    from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
    from ...domain.calculations.registry.schema_base import DateAxis

    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return resolve_simplificada_tax_id_legal_refs(operation=indexed_operation)

    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="invoice-simplificada-counterparty-tax-id-applicability",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date.today(),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("invoice applicability must resolve as a mapping fact")
    if not resolved.legal_refs:
        raise RegistryValidationError("invoice applicability is missing legal-reference provenance")
    return tuple(str(reference) for reference in resolved.legal_refs)


def _active_taxpayer_profile() -> TaxpayerProfile | None:
    """Resolve the active bucket's taxpayer profile, or ``None`` if it will not read.

    Imports are function-local for the cycle the sibling profile-backed
    advisories document: the profile package reaches back into this layer.

    Every failure collapses to ``None`` here on purpose. The three ways a
    profile can be unavailable are one fact for this rule — the issuer's
    establishment is unknown — and inventing a distinction no caller acts on
    differently would be a worse answer than the honest single one.
    """
    from ...core.bucket_pointer import resolve_active_bucket_id
    from ...domain.user_profile.errors import ProfileNotFoundError
    from ..user_profile.profile_record_repository import ProfileRecordRepository
    from ..user_profile.projections import projection_for_taxpayer

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        return None
    with bundled_indexed_authority().operation() as operation:
        try:
            profile_decode_context = operation.profile_decode_context()
            record = ProfileRecordRepository.for_current_session(
                bucket_id,
                profile_decode_context=profile_decode_context,
            ).load(bucket_id)
        except ProfileNotFoundError:
            return None
        except (OSError, ValueError):
            # A degraded profile read must not fail an invoice that is already
            # recorded. It must also not be reported as "nothing to advise".
            return None
        return projection_for_taxpayer(record, schema=profile_decode_context.schema)


def resolve_simplificada_tax_id_advisory(
    *,
    invoice: Invoice,
    profile_resolver: Callable[[], TaxpayerProfile | None] | None = None,
) -> SimplificadaTaxIdAdvisory:
    """Answer case 3.º for ``invoice``, or report that the issuer is unknown.

    The tax-id check runs before the profile is resolved. An invoice that
    already identifies its destinatario satisfies case 3.º whoever issued it,
    so reading the profile first would turn an answerable invoice into
    ``ISSUER_UNKNOWN`` on a degraded profile store for no reason.

    Args:
        invoice: The invoice to evaluate.
        profile_resolver: Resolves the issuing taxpayer's profile, returning
            ``None`` when it cannot be read. Defaults to the active bucket's.

    Returns:
        The advisory state. Only :attr:`SimplificadaTaxIdAdvisory.REQUIRED` is
        something to tell the operator; :attr:`SimplificadaTaxIdAdvisory.ISSUER_UNKNOWN`
        says the rule did not run, which is not the same as it passing.
    """
    if invoice.counterparty_tax_id is not None:
        return SimplificadaTaxIdAdvisory.ALREADY_IDENTIFIED
    resolve = _active_taxpayer_profile if profile_resolver is None else profile_resolver
    profile = resolve()
    if profile is None:
        return SimplificadaTaxIdAdvisory.ISSUER_UNKNOWN
    if simplificada_requires_tax_id_for_domestic_issuer(invoice, profile):
        return SimplificadaTaxIdAdvisory.REQUIRED
    return SimplificadaTaxIdAdvisory.NOT_REQUIRED
