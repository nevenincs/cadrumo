"""Taxpayer identity and declaration-contact producer values shared by the form and the export."""

from __future__ import annotations

from ...core.filing_producer_key import FilingProducerKey
from .producer_snapshot import DeclarationContactFacts, TaxpayerIdentityFacts


def identity_contact_producer_values(
    *,
    taxpayer_tax_id: str | None,
    identity: TaxpayerIdentityFacts,
    contact: DeclarationContactFacts,
) -> dict[FilingProducerKey, str | None]:
    """Project taxpayer and declaration-contact facts without requiring filing elections.

    The form and export use these same meanings. Missing identity components
    remain missing, and declaration contact never falls back to another party.
    """
    return {
        FilingProducerKey.TAXPAYER_TAX_ID: taxpayer_tax_id,
        FilingProducerKey.TAXPAYER_LEGAL_NAME: identity.legal_name,
        FilingProducerKey.TAXPAYER_GIVEN_NAME: identity.given_name,
        FilingProducerKey.TAXPAYER_SURNAMES: identity.surnames,
        FilingProducerKey.TAXPAYER_FULL_NAME: identity.full_name,
        # "Apellidos o Razon Social": the two are mutually exclusive by
        # construction -- a natural person carries surnames and no legal_name,
        # an entity carries legal_name and no surnames -- so this resolves to
        # whichever the filer actually has, and stays absent only when both are.
        FilingProducerKey.TAXPAYER_SURNAMES_OR_LEGAL_NAME: identity.surnames or identity.legal_name,
        # Read from the declaration's own contact fact, never from the taxpayer
        # or the presenter: under a gestor the persona con quien relacionarse is
        # routinely neither, and substituting either would name the wrong person
        # in AEAT's informativa header.
        FilingProducerKey.CONTACT_PERSON_PHONE: contact.phone,
        FilingProducerKey.CONTACT_PERSON_NAME: contact.full_name,
        FilingProducerKey.CONTACT_PERSON_SECONDARY_PHONE: contact.secondary_phone,
        FilingProducerKey.CONTACT_PERSON_EMAIL: contact.email,
    }
