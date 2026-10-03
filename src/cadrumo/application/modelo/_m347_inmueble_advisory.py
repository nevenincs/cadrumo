"""Calculate-path advisory for the Modelo 347 inmueble records Cadrumo cannot yet produce.

RD 1065/2007 art. 34.1.d has the lessor of business premises relate each lease
apart from its other operations with the same tenant, and consign "las
referencias catastrales y los datos necesarios para la localización de los
inmuebles arrendados": the fichero's inmueble record. No ledger or profile
source carries a lease of business premises, so that record is never emitted,
and a return missing it looks complete.

The advisory fires only for a filer whose profile declares rendimientos del
capital inmobiliario for the ejercicio, the one profile fact that says the filer
lets property at all. It asserts nothing about the lease itself: the profile
cannot tell a vivienda from a local de negocio, so the message names the gap
and leaves the classification to the filer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ...core.modelo import Modelo
from ...core.period import Period
from ...domain.calculations.registry.ids import LegalRefId
from ...domain.calculations.registry.irpf_income_categories import require_irpf_income_category
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from ..user_profile.projections import projection_for_taxpayer
from .profile_readiness_gate import load_modelo_work_profile

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from .work_profile import ModeloWorkProfile

__all__ = ["M347_INMUEBLE_RECORD_UNSUPPORTED_SOURCE_KIND", "collect_m347_inmueble_record_diagnostics"]

#: Diagnostic ``source_kind`` for a 347 whose filer lets property and whose
#: inmueble records Cadrumo does not produce.
M347_INMUEBLE_RECORD_UNSUPPORTED_SOURCE_KIND: Final[str] = "m347_inmueble_record_unsupported"

#: The provision the advisory's message is a claim about: the lessor's duty to
#: relate each business-premises lease with its tenant, catastro reference and
#: location.
_ASSERTED_LEGAL_REFS: Final[tuple[LegalRefId, ...]] = ("rd-1065-2007:art-34.1.d",)

#: Registry token of the IRPF income category for letting real estate.
_CAPITAL_INMOBILIARIO_CATEGORY: Final[str] = "capital_inmobiliario"


def collect_m347_inmueble_record_diagnostics(
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None = None,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise a letting filer that its Modelo 347 carries no inmueble record.

    The profile is read as of the filing period's last day, the coordinate the
    347 source resolver reads the filer's other facts at, so a category
    declared only for another ejercicio does not fire.

    Args:
        modelo: Target modelo identifier; every modelo other than 347 is silent.
        period_token: Bare registry period token for the filing.
        filing_year: Filing year the profile is projected for.
        bucket_id: Bucket whose profile is read when ``profile`` is omitted.
        operation: The calculation's pinned authority.
        profile: The bucket's profile when the calculation already loaded it.

    Returns:
        One advisory, or an empty tuple when the modelo is not 347, the bucket
        has no profile, or the profile declares no capital inmobiliario income.
    """
    if modelo != Modelo("347").value:
        return ()
    loaded = profile or load_modelo_work_profile(
        bucket_id=bucket_id,
        profile_decode_context=operation.profile_decode_context(),
    )
    if loaded is None:
        return ()
    as_of = Period.from_year_and_code(filing_year, period_token).end_date
    taxpayer = projection_for_taxpayer(loaded.record, schema=loaded.profile_decode_context.schema, as_of=as_of)
    capital_inmobiliario = require_irpf_income_category(
        _CAPITAL_INMOBILIARIO_CATEGORY,
        effective_date=as_of,
        authority=operation,
    )
    if capital_inmobiliario not in taxpayer.irpf_income_categories:
        return ()
    return (
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind=M347_INMUEBLE_RECORD_UNSUPPORTED_SOURCE_KIND,
            message=(
                f"the profile declares rendimientos del capital inmobiliario for ejercicio {filing_year}, and "
                "arrendamiento de local de negocio is not yet supported: this Modelo 347 carries no inmueble "
                "record, which RD 1065/2007 art. 34.1.d requires for each business-premises lease with its "
                "tenant, referencia catastral and location"
            ),
            remedy="Declare the inmueble records for any business-premises lease outside Cadrumo before filing.",
            asserted_legal_refs=_ASSERTED_LEGAL_REFS,
        ),
    )
