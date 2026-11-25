"""The taxpayer a Sede view's captured session belongs to, read from AEAT before custody adopts it.

A person signs in inside the view by hand, with any provider, and may sign in
as someone other than the profile's taxpayer, including as a representative of
that taxpayer. The provider's landing probe only shows that the capture unlocks
a protected page, so it cannot tell who signed in. Before a capture is adopted,
the provider reads *Mis Expedientes* in its own context, seeded from the
capture, under that reader's guarded request and landing refusals. That request
names no taxpayer, so the NIF AEAT shows is the signed-in person's own, the
person whose data every later Sede read returns. It is compared with the
identity the provider would record. The person's page is never touched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....core.errors.hierarchy import AeatLoginAssertionError, ViewCaptureIdentityMismatchError
from .....core.identity.tax_id import same_tax_identifier
from ..sede.signed_in_identity import read_signed_in_nif

if TYPE_CHECKING:
    from .....application.auth.protocols import BrowserContextPort


async def require_signed_in_taxpayer(context: BrowserContextPort, *, expected_nif: str) -> None:
    """Refuse a captured session unless AEAT shows ``expected_nif`` as the person signed in.

    ``context`` is the provider's own context, seeded from the capture. A page
    AEAT does not serve to this session, a representation dialog, any page
    that is not *Mis Expedientes*, a page that shows no NIF and one that shows
    another NIF all refuse, so nothing is adopted. Only a NIF AEAT shows that
    is not ``expected_nif`` says who signed in.

    Raises:
        ViewCaptureIdentityMismatchError: When AEAT shows another person signed in.
        AeatLoginAssertionError: When the page shows no NIF.
        SedeError: When the page cannot be read for this session.
    """
    observed = await read_signed_in_nif(context)
    if observed is None:
        raise AeatLoginAssertionError("Mis Expedientes read for the Sede view's captured session shows no NIF")
    if not same_tax_identifier(observed, expected_nif):
        raise ViewCaptureIdentityMismatchError(
            "the session captured in the Sede view belongs to a taxpayer other than the configured identity",
        )


__all__ = ["require_signed_in_taxpayer"]
