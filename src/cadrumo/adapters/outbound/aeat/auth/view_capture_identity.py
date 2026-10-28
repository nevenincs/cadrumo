"""The taxpayer a Sede view's captured session belongs to, read from AEAT before custody adopts it.

A person signs in inside the view by hand, with any provider, and may sign in
as someone other than the profile's taxpayer. The provider's landing probe
only shows that the capture unlocks a protected page, so it cannot tell who
signed in. Before a capture is adopted, the provider reads the censal consulta
in its own context, seeded from the capture, through the censal reader's own
guarded request and landing refusals, and compares the NIF AEAT shows with the
identity the provider would record. The person's page is never touched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....core.errors.hierarchy import AeatLoginAssertionError, ViewCaptureIdentityMismatchError
from .....core.identity.tax_id import same_tax_identifier
from ..sede.censal_datos import read_censal_identity_nif

if TYPE_CHECKING:
    from .....application.auth.protocols import BrowserContextPort


async def require_signed_in_taxpayer(context: BrowserContextPort, *, expected_nif: str) -> None:
    """Refuse a captured session unless AEAT shows ``expected_nif`` as its signed-in taxpayer.

    ``context`` is the provider's own context, seeded from the capture. A
    consulta AEAT does not serve to this session, a representation dialog, a
    page that is not the consulta, a consulta that shows no NIF and one that
    shows another NIF all refuse, so nothing is adopted. Only a NIF AEAT
    shows that is not ``expected_nif`` says who signed in.

    Raises:
        ViewCaptureIdentityMismatchError: When AEAT shows another taxpayer signed in.
        AeatLoginAssertionError: When the consulta shows no NIF.
        SedeError: When the consulta cannot be read for this session.
    """
    observed = await read_censal_identity_nif(context, taxpayer_nif=expected_nif)
    if observed is None:
        raise AeatLoginAssertionError("the consulta read for the Sede view's captured session shows no NIF")
    if not same_tax_identifier(observed, expected_nif):
        raise ViewCaptureIdentityMismatchError(
            "the session captured in the Sede view belongs to a taxpayer other than the configured identity",
        )


__all__ = ["require_signed_in_taxpayer"]
